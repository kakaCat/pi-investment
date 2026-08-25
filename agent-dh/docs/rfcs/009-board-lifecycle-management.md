# RFC 009: 公告板生命周期管理（删除/修订/闭环/归档）

| 字段 | 值 |
|---|---|
| 状态 | 🟡 设计待评审 |
| 创建 | 2026-08-25（agent-dh k3，应用户要求设计，实施移交其他 agent） |
| 触发 | 用户要求删除公告板帖子时发现：board_post/board_read 之外没有任何管理能力 |
| 涉及层 | Agent OS（Go :8080）→ agent-os-client（TS）→ lifecycle 插件（board_* 工具） |

---

## 1. 现状与问题

公告板帖 = Agent OS `memories` 表记录（tag `office:board`，content 内含 `marker: office-board-post`）。能力分布：

| 层 | 现有能力 | 缺口 |
|---|---|---|
| Agent OS HTTP API | `GET/POST /api/v1/memory`、`GET /search`、tags CRUD | **memory 无 DELETE/UPDATE 路由**（`http_server.go:77-82`） |
| Agent OS repo 层 | `Update()`（含 metadata，:87）、`Delete(id)` 硬删（:132）、CLI `memory delete` | 能力没暴露 HTTP |
| agent-os-client | `memory.search()` / `memory.write()` | 无 delete/update |
| lifecycle 插件 | `board_post` / `board_read` | 无管理工具；board_read 无状态过滤 |

后果：错帖/重复帖/已完成工单帖永远挂在板上，信息噪声随时间单调增长（本次 M1 复核帖即触发案例）。

## 2. 设计原则

1. **软删优先**：帖子是协作资产与审计线索，硬删只在 GC 阶段发生；删除 = 打状态标记
2. **无痕不管理**：所有管理操作必须留痕（谁、何时、为什么），删帖理由必填
3. **作者优先，管理员兜底**：窗口只能改自己的帖；管理员窗口可仲裁
4. **读侧默认干净**：board_read 默认只见活跃帖，历史帖显式可查
5. **不动表结构**：用现有 `metadata`(JSONB) + `updated_at` 承载状态机，零迁移

## 3. 场景覆盖清单（设计目标）

| # | 场景 | 方案 | 状态终态 |
|---|---|---|---|
| S1 | 发错帖/重复帖，作者自删 | `board_manage(action=delete, reason)` | `deleted` |
| S2 | 内容笔误/补充进展 | `board_manage(action=update, title/content)` 原地修订，自动追加修订记录 | 保持 `active` |
| S3 | 工单帖闭环（问题已修复） | `board_manage(action=resolve, resolution)` 标记已解决+结论，默认从读侧隐藏 | `resolved` |
| S4 | 管理员清理违规/过时帖 | 管理员窗口 `delete/resolve` 任意帖 | `deleted/resolved` |
| S5 | 误删恢复 | `board_manage(action=restore)` | 回到 `active` |
| S6 | 陈旧帖自动归档 | GC：resolved/deleted 超过 N 天（默认 30）→ `archived`；archived 超 180 天 → 硬删 | `archived`→硬删 |
| S7 | 查看历史帖（复盘） | `board_read(status=resolved/deleted/all)` | — |
| S8 | 帖子状态变更的审计追溯 | 每次操作追加 `metadata.moderation_log[]` | — |

**显式不做**（本期）：已读/未读跟踪（属 inbox 语义，公告板是广播不是信箱）；回帖/评论线程（用 window_message 或新发帖引用原帖 id）；钉选置顶（需求未出现）。

## 4. 状态机

```
        post
         │
         ▼
      active ──resolve──▶ resolved ──┐
         │  ▲                        │ GC(30d)
  delete │  │ restore                ▼
         ▼  │                     archived ──GC(180d)──▶ 硬删
      deleted ──────────────────────┘
           GC(30d)
```

- 状态存于 `metadata.board_status`（缺省 = `active`，存量帖零迁移兼容）
- `resolved` 帖携带 `metadata.resolution`（结论一句话）
- `deleted` 帖携带 `metadata.delete_reason`

## 4A. 工单流转状态（与可见性正交的第二维度）

**问题**：公告板实际承载工单板职能（"补工单"、"4 个遗留问题待修"类帖子），但 §4 的可见性状态回答不了"**这张工单谁领了、做到哪了、是不是没人接**"——M1 复核帖挂 40 分钟无人领时无法区分"没人看到"与"有人在做"。

**设计**：两个正交维度，互不影响：

| 维度 | 字段 | 取值 | 回答 |
|---|---|---|---|
| 可见性（§4） | `metadata.board_status` | active / resolved / deleted / archived | 帖子还在板上吗 |
| 工单流转（本节） | `metadata.work_status` | open / claimed / in_progress / blocked / done | 活干到哪了 |

```
open ──claim──▶ claimed ──开工──▶ in_progress ──resolve──▶ done
  ▲               │                     │
  │            unclaim               block（附原因）
  │               │                     │
  │               ▼                     ▼
  └──────────── open ◀──unblock──── blocked
```

规则：

1. **只有 kind 为工单性质的帖进入流转**：`finding` 纯分享无需流转（work_status 恒空）；`question/review/proposal` 发帖时可带 `needs_action: true` 进入 open（默认：question/proposal 自动 open，finding/review 不进入）
2. **claim 自助领单**：任何窗口 `board_manage(action=claim)`，写 `metadata.assignee`（窗口编码）+ `claimed_at`；一个帖同时只能一个 assignee，重复 claim 报错并提示当前认领人
3. **unclaim 放单**：认领人可放回（`unclaim_reason` 必填，如"排期冲突"），回到 open 供他人领
4. **block/unblock**：认领人标记卡住 + 原因（如"等上游数据"）；例会巡检时 blocked 帖优先讨论
5. **done 与 resolved 联动**：`resolve` 动作同时置 `work_status=done` + `board_status=resolved`，一次操作双维闭环
6. **停滞检测**（stale）：`open` 超 24h 无人 claim、`in_progress` 超 48h 无进展更新 → board_read 输出标 `"stale": true`；由每日例会例程巡检并提醒（不发自动通知，避免噪音）
7. **权限**：claim/unclaim/block 开放给所有窗口（自助协作）；只有 assignee 或管理员能推进 in_progress/done；作者可随时 resolve 自己的帖（视为"已自行处理"）

board_manage 新增动作：`claim` / `unclaim(reason)` / `start`（claimed→in_progress）/ `block(reason)` / `unblock`。

board_read 增强：
- 输出每帖带 `work_status` / `assignee` / `stale` 字段
- 新增过滤参数 `work_status=open`（**找活干**：例会时空闲窗口一键领取清单）
- 新增过滤参数 `assignee=w-xxx`（看某窗口手上有什么活）

新增场景：

| # | 场景 | 方案 |
|---|---|---|
| S9 | 空闲窗口找活 | `board_read(work_status=open)` → `claim` → `start` |
| S10 | 工单无人认领暴露 | open + stale 24h → 例会可见，不再"挂着没人知道" |
| S11 | 认领后做不完 | `unclaim(reason)` 放回池子，原因留痕 |
| S12 | 依赖外部阻塞 | `block(reason)`，例会优先疏通 |
| S13 | 与 assign_task 派单的关系 | 派单（office 定向任务）不进公告板；公告板是**公开悬赏池**。若帖子被 assign_task 定向派出，发帖人可 update 注明"已派 w-xxx"，避免重复认领 |

## 5. 三层改动规格

### 5.1 Agent OS（Go，:8080）

新增两个路由（`internal/api/http_server.go` memory 段）：

```
DELETE /api/v1/memory/{id}          # 软删：metadata.board_status=deleted（body 可带 reason）
PATCH  /api/v1/memory/{id}          # 更新 content/metadata（body: {content?, metadata_patch?}）
```

实现要点：
- `memoryHandler` 加 `Delete` / `Patch`，repo 层复用现有 `Update()`（已支持 metadata 写入）；**不要**用现有硬删 `Delete(id)` 做软删
- **搜索过滤**：`memoryHandler.Search` 与 `List` 默认排除 `metadata->>'board_status' IN ('deleted','archived')`；加查询参数 `include_moderated=true` 时可返回（管理/复盘用途）
- GC：新增定时任务（复用 Agent OS 现有 scheduler）每日 04:00 执行状态迁移与硬删；写成独立函数便于测试

### 5.2 agent-os-client（TS）

`memory-client.ts` 增加：

```typescript
async deleteMemory(id: string, reason?: string): Promise<void>
async patchMemory(id: string, patch: { content?: string; metadataPatch?: Record<string, any> }): Promise<void>
```

### 5.3 lifecycle 插件（board 工具族）

**新工具 `board_manage`**：

| 参数 | 说明 |
|---|---|
| `post_id` (必填) | 目标帖 id（board_read 返回的 id） |
| `action` (必填) | `delete` / `update` / `resolve` / `restore` |
| `reason` | delete 必填；其他可选 |
| `title` / `content` | action=update 时使用 |
| `resolution` | action=resolve 时必填（结论） |

执行逻辑：
1. 读目标帖，校验存在
2. **权限检查**（§6）不通过 → 明确报错（不静默）
3. 走 osWrite 写通道（复用 outbox 防丢机制）：patch metadata.board_status / moderation_log 等
4. 返回新状态

**`board_read` 增强**：

| 参数 | 说明 |
|---|---|
| `status` | `active`（默认）/ `resolved` / `deleted` / `all` |
| `kind` / `limit` | 保持现状 |

## 6. 权限模型

```
操作者 == 帖子的 from 窗口      → delete/update/resolve/restore 全允许
操作者在管理员白名单            → 允许操作任意帖（reason 必填）
其他                            → 拒绝，报错注明"仅作者或管理员可管理此帖"
```

- 管理员白名单：`agents.json` 中 agent 增加 `"board_admin": true` 标记（初始建议：主投资脑窗口）
- 所有管理操作（含被允许的越权操作）都写 `moderation_log`，越权操作额外标 `"admin_override": true`

`moderation_log[]` 条目结构：

```json
{"action": "delete", "by": "w-882977ae", "ts": "...", "reason": "...", "admin_override": false}
```

## 7. 幂等与并发

- 重复 delete/resolve 同一帖：幂等成功（返回当前状态，不重复写 log）
- 并发修订同一帖：不引入版本锁（公告板低频协作场景，last-write-wins 可接受），修订记录保留全部历史可溯源——文档明示此取舍
- restore 只从 deleted/resolved → active；对 active 帖调用幂等成功

## 8. 验收标准

| # | 验收 | 命令/方法 | 标准 |
|---|---|---|---|
| A1 | 作者自删 | board_manage(delete) 自己发的帖 → board_read | 默认读不到；status=deleted 可读 |
| A2 | 非作者被拒 | 另一窗口 delete 该帖 | 报错且帖子仍在 |
| A3 | 管理员越权删 | 白名单窗口 delete | 成功，moderation_log 含 admin_override |
| A4 | 修订留痕 | update 后读 metadata | content 已改，moderation_log 有记录 |
| A5 | 闭环 | resolve + resolution → board_read 默认 | 不可见；status=resolved 可见且带结论 |
| A6 | 恢复 | restore 已删帖 | 回到 active，log 完整 |
| A7 | 幂等 | 连续 delete 两次 | 都成功，log 只一条 |
| A8 | GC | 构造 31 天前 deleted 帖跑 GC | 转 archived；搜索/List 不可见 |
| A9 | 搜索过滤 | OS `/api/v1/memory/search` 直查 | deleted/archived 默认不返回 |
| A10 | 回归 | board_post/board_read 原有行为 | 不变（active 帖正常发读） |
| A11 | 领单闭环 | A 窗口发 question 帖 → B 窗口 `board_read(work_status=open)` 看到 → claim → start → resolve | work_status 走完 open→claimed→in_progress→done；assignee=B |
| A12 | 重复认领被拒 | C 窗口再 claim 同一帖 | 报错并提示当前认领人 |
| A13 | 放单再领 | B unclaim → C claim 成功 | work_status 回 open 再进 claimed；log 含 unclaim_reason |
| A14 | 阻塞与恢复 | B claim 后 block(reason) → unblock | 状态正确流转，原因留痕 |
| A15 | 停滞标记 | 构造 25h 前 open 帖 | board_read 输出 stale=true |
| A16 | 按人查活 | `board_read(assignee=w-xxx)` | 只返回该窗口认领的帖 |

## 9. 实施工单拆分（移交实施 agent）

| 工单 | 内容 | 预估 |
|---|---|---|
| W1 | Agent OS：DELETE/PATCH 路由 + 搜索过滤 + 单测 | 0.5d |
| W2 | Agent OS：GC 定时任务（状态迁移+硬删）+ 单测 | 0.5d |
| W3 | agent-os-client：deleteMemory/patchMemory | 0.2d |
| W4 | lifecycle：board_manage 工具（含 §4 管理动作 + §4A claim/unclaim/start/block/unblock 流转动作）+ 权限校验 + board_read status/work_status/assignee 参数 + schema 冒烟测试 | 1d |
| W5 | agents.json 管理员标记 + 端到端验收 A1-A16 | 0.3d |

## 10. 风险与注意

1. **Agent OS 是"legacy"服务**——改它前先确认它仍是公告板唯一后端（本 RFC 侦察时是）；若未来迁移到 quantsys-v2 统一记忆库，本设计的状态机与权限模型可直接平移（quantsys-v2 memory 已有 deprecate/supersede 生命周期，迁移反而更简单）
2. **重启 Agent OS 需走 stop.sh 精确停止**（多实例铁律）
3. 插件改动遵守 schema 铁律（每个 object 节点显式 additionalProperties）并跑 `plugin-schema.smoke.test.ts`
4. 硬删不可逆：GC 硬删前 180 天窗口足够复盘追溯；如需更保守可调大

## 11. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-25 | 创建。触发：用户要求删公告板帖发现无删除能力；侦察确认能力缺口在 Agent OS HTTP 层（repo/CLI 有而 API 无） |
| 2026-08-25 | 补充 §4A 工单流转状态（用户指出遗漏）：open/claimed/in_progress/blocked/done 与可见性正交；board_manage 增 claim 等 5 动作；board_read 增 work_status/assignee 过滤与 stale 标记；验收 A11-A16 |
