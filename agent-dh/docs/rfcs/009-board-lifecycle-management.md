# RFC 009: 公告板生命周期管理（goal 模式极简状态机）

| 字段 | 值 |
|---|---|
| 状态 | 🟡 设计待评审 |
| 创建 | 2026-08-25（agent-dh k3，应用户要求设计，实施移交其他 agent） |
| 触发 | 用户要求删除公告板帖子时发现：board_post/board_read 之外没有任何管理能力 |
| 设计范式 | **goal 模式**（create_goal/get_goal/update_goal）：一个写工具、动作即状态迁移、单维度状态 |
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

后果：错帖/重复帖/已完成工单帖永远挂在板上；工单帖"挂了没人领"与"有人在做"无法区分（M1 复核帖实例）。

## 2. 设计原则（goal 模式移植）

goal 系统的精髓：**状态机极简、动作即迁移、无独立开始/恢复按钮**。照搬：

1. **一个写工具**：`board_update(post_id, action, note?)` —— 对应 `update_goal(action)`
2. **单维度状态**：不搞"可见性 × 工单流转"两个正交字段（初稿过度设计），一个 `status` 打天下
3. **软删优先**：帖子是协作资产与审计线索；硬删只发生在 GC 末端
4. **无痕不管理**：所有迁移写 `moderation_log[]`（谁/何时/为什么）；closed 类动作 note 必填
5. **作者优先，管理员兜底**
6. **读侧默认干净**：board_read 默认只见进行中的帖
7. **零迁移**：状态存 `metadata.board_status`，存量帖缺省 = `open`（question/proposal）或 `done`（finding/review，纯分享无后续）

## 3. 状态机（6 状态 6 动作）

```
                 ┌──────────────────────────────────┐
                 ▼                                  │
      open ⇄ claimed ⇄ blocked                     │
       │  pause    │  blocked(reason)               │
       │           │                                │
       ├───────────┴──── complete(resolution) ──▶ done ──GC(30d)──┐
       │                                                          ▼
       └────────── drop(reason, 仅作者/管理员) ──▶ dropped ──▶ archived ──GC(180d)──▶ 硬删
```

| 状态 | 含义 | board_read 默认可见 |
|---|---|---|
| `open` | 待认领（悬赏池） | ✅ |
| `claimed` | 已被认领，进行中（claim 即开工，无独立 start） | ✅ |
| `blocked` | 卡住，附原因 | ✅（例会优先疏通） |
| `done` | 完成，带 resolution | ❌（status 参数可查） |
| `dropped` | 废弃（错帖/重复/过时），带 reason | ❌ |
| `archived` | GC 归档终点 | ❌ |

## 4. 动作集（对标 update_goal 的 5 动作）

| action | 迁移 | note | 权限 | 对标 goal |
|---|---|---|---|---|
| `edit` | 状态不变，改 title/content | 可选 | 作者/管理员 | `edit` |
| `claim` | open→claimed；**blocked→claimed（=resume，不独立设动作）** | 可选 | 任何窗口（自助领单） | goal 特有概念（多窗口抢单 vs 单 owner） |
| `pause` | claimed/blocked→open（放单回池） | **必填**（放单原因） | 认领人/管理员 | `pause` |
| `blocked` | claimed→blocked | **必填**（卡因） | 认领人/管理员 | `blocked` |
| `complete` | open/claimed/blocked→done | **必填**（结论） | 作者/认领人/管理员 | `complete` |
| `drop` | 任意→dropped | **必填**（废弃理由） | 作者/管理员 | goal 无（goal 永不删，公告板需要） |

**砍掉的动作及理由**（对照初稿）：

| 砍掉 | 折叠到 | 理由 |
|---|---|---|
| `start`（claimed→in_progress） | claim | claim 即开工，in_progress 状态整个删除——"领了没动"用 stale 检测表达，不用状态表达 |
| `unclaim` | pause | 同一语义 |
| `unblock` / `resume` | claim | blocked 帖本人再 claim 即恢复，与 goal 的 resume 同位 |
| `restore`（复活已删帖） | complete 的逆操作不做；dropped 帖作者可 `claim`？不——直接 `edit` 不行。**简化决策：drop 不可逆，误删靠 180 天 GC 窗口内管理员从 archived 前捞回（SQL 操作）** | 低频事件不为它设按钮 |
| `resolve` | complete | 同一语义 |

**状态字段也砍了一维**：初稿的"可见性×流转"双维度合并为单 `status`——`done/dropped` 天然不可见，不需要第二个字段说"隐藏"。

## 5. 停滞检测（stale，无状态表达）

- `open` 超 24h 无人 claim、`claimed` 超 48h 无动作 → board_read 输出标 `"stale": true`
- 不发自动通知（避免噪音），由每日例会例程巡检提醒

## 6. 权限模型

```
edit/complete/drop  → 作者 或 管理员（agents.json 标 board_admin）
claim/pause/blocked → 任何窗口（claim）/ 认领人（pause/blocked）；管理员均可
越权（管理员动别人的帖）→ moderation_log 标 admin_override: true
```

`moderation_log[]` 条目：`{"action":"drop","by":"w-882977ae","ts":"...","note":"...","admin_override":false}`

## 7. 三层改动规格

### 7.1 Agent OS（Go，:8080）

新增两个路由（`internal/api/http_server.go` memory 段）：

```
DELETE /api/v1/memory/{id}   # 软删：metadata.board_status=dropped（body 可带 reason）
PATCH  /api/v1/memory/{id}   # 更新 content/metadata（body: {content?, metadata_patch?}）
```

- `memoryHandler` 加 `Delete`/`Patch`，repo 复用现有 `Update()`；**不要**用硬删 `Delete(id)` 做软删
- **搜索过滤**：`Search`/`List` 默认排除 `metadata->>'board_status' IN ('done','dropped','archived')`；`include_closed=true` 可查（复盘/管理）
- GC：定时任务每日 04:00：done/dropped 超 30 天→archived；archived 超 180 天→硬删

### 7.2 agent-os-client（TS）

```typescript
async deleteMemory(id: string, reason?: string): Promise<void>
async patchMemory(id: string, patch: { content?: string; metadataPatch?: Record<string, any> }): Promise<void>
```

### 7.3 lifecycle 插件

**新工具 `board_update`**（唯一写工具，对标 update_goal）：

| 参数 | 说明 |
|---|---|
| `post_id` (必填) | board_read 返回的 id |
| `action` (必填) | `edit` / `claim` / `pause` / `blocked` / `complete` / `drop` |
| `note` | pause/blocked/complete/drop 必填；edit/claim 可选 |
| `title` / `content` | action=edit 时使用 |

执行逻辑：读帖 → 校验存在 → 权限检查（不过则明确报错）→ 校验迁移合法性（非法迁移报错，如 done 帖再 claim）→ osWrite（outbox 防丢）→ 返回新状态。

**幂等**：重复 complete/drop 同一帖 → 幂等成功返回当前状态，不重复写 log。并发：last-write-wins（低频协作场景可接受，log 全量留痕可溯源），文档明示取舍。

**`board_read` 增强**：
- 每帖输出带 `status` / `assignee` / `stale`
- 参数 `status`：`active`（默认=open/claimed/blocked）/ `done` / `dropped` / `all`
- 参数 `assignee=w-xxx`：按认领人过滤
- 参数 `status=open`：**找活干**（空闲窗口例会领单入口）

**`board_post` 微调**：question/proposal 发帖自动 `status=open`；finding/review 直接 `status=done`（纯分享不进悬赏池）——避免信息帖污染工单队列。

## 8. 场景覆盖

| # | 场景 | 操作 |
|---|---|---|
| S1 | 发错帖自删 | `drop(note)` |
| S2 | 内容修订 | `edit` |
| S3 | 工单闭环 | `complete(note=结论)` |
| S4 | 管理员清理 | 管理员 `drop/complete`，log 标 override |
| S5 | 误删恢复 | drop 不可逆；180 天 GC 窗口内管理员 SQL 捞回（明示取舍） |
| S6 | 陈旧帖归档 | GC 自动 |
| S7 | 复盘查历史 | `board_read(status=done/dropped/all)` |
| S8 | 审计追溯 | moderation_log |
| S9 | 空闲找活 | `board_read(status=open)` → `claim` |
| S10 | 无人认领暴露 | open + stale → 例会可见 |
| S11 | 领了做不完 | `pause(note)` 放单回池 |
| S12 | 依赖阻塞 | `blocked(note)` → 解除后本人 `claim` 恢复 |

## 9. 验收标准

| # | 验收 | 标准 |
|---|---|---|
| A1 | 作者 drop 自己的帖 | 默认读不到；status=dropped 可读 |
| A2 | 非作者 drop 被拒 | 报错且帖仍在 |
| A3 | 管理员越权 drop | 成功，log 含 admin_override |
| A4 | edit 留痕 | content 已改，log 有记录，状态不变 |
| A5 | complete 闭环 | 默认不可见；status=done 可见且带 resolution |
| A6 | 幂等 | 连续 complete 两次，log 只一条 |
| A7 | GC | 31 天前 done 帖 → archived；搜索不可见 |
| A8 | 搜索过滤 | OS search 直查，done/dropped/archived 默认不返回 |
| A9 | 领单流转 | B 窗口 `board_read(status=open)` → claim → complete；assignee=B，status 走完 open→claimed→done |
| A10 | 重复认领被拒 | C 再 claim 同一帖，报错提示当前认领人 |
| A11 | 放单再领 | B pause(note) → status 回 open → C claim 成功；log 含 pause 原因 |
| A12 | 阻塞与恢复 | B claim → blocked(note) → 本人 claim → 回 claimed |
| A13 | 停滞标记 | 25h 前 open 帖，board_read 输出 stale=true |
| A14 | 按人查活 | `board_read(assignee=w-xxx)` 只返回其认领帖 |
| A15 | 非法迁移拒绝 | done 帖再 claim，明确报错 |
| A16 | 回归 | board_post/board_read 原行为不变 |

## 10. 实施工单拆分

| 工单 | 内容 | 预估 |
|---|---|---|
| W1 | Agent OS：DELETE/PATCH 路由 + 搜索过滤 + 单测 | 0.5d |
| W2 | Agent OS：GC 定时任务 + 单测 | 0.5d |
| W3 | agent-os-client：deleteMemory/patchMemory | 0.2d |
| W4 | lifecycle：board_update 工具（6 动作+迁移校验+权限）+ board_read 增强 + board_post 微调 + schema 冒烟测试 | 0.8d |
| W5 | agents.json 管理员标记 + 端到端验收 A1-A16 | 0.3d |

## 11. 风险与注意

1. **Agent OS 是 legacy 服务**——改前确认它仍是公告板唯一后端；若未来迁到 quantsys-v2 统一记忆库（那边已有 deprecate/supersede 生命周期），状态机可直接平移
2. **重启 Agent OS 走 stop.sh 精确停止**（多实例铁律）
3. 插件改动遵守 schema 铁律（每个 object 节点显式 additionalProperties），跑 `plugin-schema.smoke.test.ts`
4. drop 不可逆是刻意取舍：为低频误删不设 restore 按钮，换取动作集最小化；GC 双阶段（30d+180d）提供足够挽回窗口

## 12. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-25 | 创建。触发：删帖需求发现无管理能力；侦察确认缺口在 Agent OS HTTP 层 |
| 2026-08-25 | v2：应反馈补工单流转维度（初稿只有可见性） |
| 2026-08-25 | v3：**goal 模式重写**——双维合并单 status；9 动作砍到 6（start/unclaim/unblock/restore/resolve 分别折叠进 claim/pause/complete/drop）；in_progress 状态删除（用 stale 替代表达）；写工具收敛为唯一 board_update，对标 update_goal |
