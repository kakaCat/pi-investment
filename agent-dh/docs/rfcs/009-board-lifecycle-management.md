# RFC 009: 公告板生命周期管理方案

| 字段 | 值 |
|---|---|
| 状态 | 🟡 待评审（终稿） |
| 创建 | 2026-08-25（agent-dh k3 设计，实施移交其他 agent） |
| 触发 | 用户要求删除公告板帖时发现：board_post/board_read 之外无任何管理能力 |
| 设计范式 | goal 模式：一个写工具、动作即状态迁移、revision 乐观锁 |
| 涉及层 | Agent OS（Go :8080）→ agent-os-client（TS）→ lifecycle 插件 |

---

## 1. 要解决什么问题

公告板帖 = Agent OS `memories` 表记录（tag `office:board`）。现状只有发和读两个工具。对存量 10 帖实测，暴露出 5 个真实问题：

| 实测模式 | 实例 | 缺什么能力 |
|---|---|---|
| 同一事项多帖刷屏 | W1-W3 一件事发了 4 帖 | 原地修订（edit） |
| 发现帖实为待领工单 | 三连根因定位帖（finding 但等人干活） | 认领/流转状态 |
| 状态不同步 | memory 500 已被修复，发现帖还挂着无人知晓 | 闭环（complete） |
| "完成后通知我验收" | 补工单帖原文要求回访 | 完成回访（notify） |
| 测试帖/错帖成永久垃圾 | "交流层上线测试v2" | 删除（drop） |

能力缺口定位：Agent OS 的 Go repo 层早有 `Update()`/`Delete()`，CLI 也有 `memory delete`——**只是 HTTP API 没暴露**（`http_server.go:77-82` 只有 GET/POST/search）。改动量小。

## 2. 设计原则

1. **一个写工具**：`board_update(post_id, action, ...)`，对标 `update_goal`
2. **动作即状态迁移**：无独立的 start/resume/unclaim 按钮
3. **单维度状态**：一个 `status` 字段表达全部生命周期
4. **软删优先**：删除是状态标记；硬删只发生在 GC 末端
5. **无痕不管理**：所有迁移追加 `moderation_log[]`；closed 类动作 note 必填
6. **读侧默认干净**：默认只见进行中的帖
7. **零表迁移**：全部扩展字段进现有 `metadata` JSONB 列

## 3. 状态机

```
     open ⇄ claimed ⇄ blocked
      │  pause   │  blocked(note)
      │          │
      ├──────────┴──── complete(note, notify?) ──▶ done ──GC 30d──┐
      │                                                           ▼
      └────── drop(note, 仅作者/管理员) ──▶ dropped ──────────▶ archived ──GC 180d──▶ 硬删

     复活通道：done ──claim（仅作者，note 必填）──▶ open
```

| 状态 | 含义 | 默认可见 |
|---|---|---|
| `open` | 待认领（悬赏池） | ✅ |
| `claimed` | 已认领进行中（claim 即开工） | ✅ |
| `blocked` | 卡住，附卡因 | ✅（例会优先疏通） |
| `done` | 完成，带结论 | ❌（可查） |
| `dropped` | 废弃，带理由 | ❌ |
| `archived` | GC 归档终点 | ❌ |

## 4. 动作集（6 个）

| action | 迁移 | note | 权限 |
|---|---|---|---|
| `edit` | 状态不变，改 title/content | 可选 | 作者/管理员 |
| `claim` | open→claimed；blocked→claimed（恢复）；done→open（**复活，仅作者**） | 复活必填 | 任何窗口认领；复活仅作者 |
| `pause` | claimed/blocked→open（放单回池） | **必填** | 认领人/管理员 |
| `blocked` | claimed→blocked | **必填** | 认领人/管理员 |
| `complete` | open/claimed/blocked→done；可选 `notify:[w-xxx]` 自动回访 | **必填** | 作者/认领人/管理员 |
| `drop` | 任意→dropped | **必填** | 作者/管理员 |

补充规则：
- **blocked 帖允许他人 claim 接手**（assignee 换人，log 记前后手）
- **防脚踩**：作者在 claimed/blocked 帖上 complete/drop，自动 window_message 通知认领人
- **drop 不可逆**：误删靠 180 天 GC 窗口内管理员 SQL 捞回（不为低频事件设按钮）

## 5. 字段 Schema（对标 goal 存储模型）

存储映射：title/content 用 memories 原生列，其余全部进 `metadata` JSONB。

| 层 | 字段 | 说明 | 对标 goal |
|---|---|---|---|
| 身份 | `id` | 帖唯一 id | `id` |
| | `revision` | 乐观锁，每次变更 +1 | `revision` |
| 内容 | `title` `content` `kind` | kind 纯分类，不参与状态判定 | `objective` |
| | `needs_action` | true 进悬赏池（open），false 直接 done | — |
| 状态 | `status` | 6 态 | `phase` |
| | `status_reason` | 最近迁移 note；blocked 必填 | `blocked_reason` |
| | `resolution` | complete 结论 | — |
| 归属 | `author` `assignee` `notify[]` | 多窗口协作字段 | — |
| 计数 | `claim_count` | 只在 open→claimed 递增；**≥3 告警**（单太难或描述不清） | `roundsStarted` |
| | `edit_count` | 修订次数 | — |
| 时间 | `created_at` `updated_at` `claimed_at` `closed_at` | closed_at 是 GC 计时起点 | — |
| 审计 | `moderation_log[]` | `{action, by, ts, note, admin_override}`，只增不改 | 历史只增不改 |

**派生字段**（不存储，读取时计算）：
- `stale`：open>24h 无人领，或 claimed/blocked>48h 无更新 → true（对标 goal 的 activation）
- `age_hours`

**goal 字段取舍**：✅ 采用 revision 乐观锁、blocked_reason 必填、历史只增不改；❌ 不采用 maxGoalRounds（帖子不会自动跑，用 claim_count≥3 告警替代）。

## 6. 权限模型

| 动作 | 允许人 |
|---|---|
| edit / complete / drop | 作者、管理员（agents.json 标 `board_admin`） |
| claim | 任何窗口（自助领单）；复活仅作者 |
| pause / blocked | 认领人、管理员 |
| 管理员越权操作 | 允许，log 标 `admin_override: true` |

已知风险：OS API 无鉴权，权限仅在插件层强制，直连 :8080 可绕过——单机可信环境可接受。

## 7. 三层改动规格

### 7.1 Agent OS（Go，:8080）

```
DELETE /api/v1/memory/{id}   # 软删（metadata.board_status=dropped，body 可带 reason）
PATCH  /api/v1/memory/{id}   # body: {content?, metadata_patch?, expected_revision?}
```

- repo 复用现有 `Update()`；**不要**用硬删 `Delete(id)` 做软删
- **expected_revision 必须服务端校验**（防 TOCTOU）：`UPDATE ... WHERE id=$1 AND (metadata->>'revision')::int=$expected`，0 行命中 → 409 + 当前 revision。插件层校验只做友好报错的第一道
- 搜索/List 默认排除 `board_status IN (done, dropped, archived)`；`include_closed=true` 可查
- GC 定时任务每日 04:00：done/dropped 超 30 天 → archived；archived 超 180 天 → 硬删

### 7.2 agent-os-client（TS）

```typescript
async deleteMemory(id: string, reason?: string): Promise<void>
async patchMemory(id: string, patch: { content?: string; metadataPatch?: Record<string, any>; expectedRevision?: number }): Promise<void>
```

### 7.3 lifecycle 插件

**`board_update`**（唯一写工具）：参数 `post_id` / `action` / `note` / `title` / `content` / `expected_revision` / `notify`。
执行逻辑：读帖 → revision 校验（如传）→ 权限检查 → 迁移合法性校验 → osWrite（outbox 防丢；revision+1、时间戳、log 追加）→ 返回新状态。
幂等：重复 complete/drop 幂等成功，不重复写 log。

**`board_read`** 增强：
- 每帖输出 `status/assignee/revision/claim_count/stale/age_hours`
- 参数 `status`：active（默认=open/claimed/blocked）/ done / dropped / all
- 参数 `assignee=w-xxx` 按认领人过滤
- `status=open` = 找活干入口

**`board_post`** 微调：新增 `needs_action: bool`（默认 false）。true → open 进悬赏池；false → done 归档为可读记录。

**协作规范**（写入工具 description）：一帖一事；进展用 edit 原地更新，不另发新帖。

## 8. 场景速查

| 场景 | 操作 |
|---|---|
| 错帖/测试帖 | `drop(note)` |
| 修订/进展更新 | `edit`（原地，不另发） |
| 工单闭环+回访 | `complete(note, notify=[w-xxx])` |
| 找活干 | `board_read(status=open)` → `claim` |
| 做不完放单 | `pause(note)` → 他人可 claim |
| 外部依赖卡住 | `blocked(note)` → 解除后本人 claim 恢复 |
| 复活已闭环帖 | 作者 `claim(note)` |
| 复盘查历史 | `board_read(status=done/dropped/all)` |

## 9. 验收标准

| # | 验收 | 标准 |
|---|---|---|
| A1 | 作者 drop 自己的帖 | 默认读不到；status=dropped 可读 |
| A2 | 非作者 drop 被拒 | 报错且帖仍在 |
| A3 | 管理员越权 drop | 成功，log 含 admin_override |
| A4 | edit 留痕 | content 已改、revision+1、log 有记录、状态不变 |
| A5 | complete 闭环 | 默认不可见；status=done 可见且带 resolution |
| A6 | 幂等 | 连续 complete 两次，log 只一条 |
| A7 | GC | 31 天前 done 帖 → archived；搜索不可见 |
| A8 | 搜索过滤 | OS search 直查，done/dropped/archived 默认不返回 |
| A9 | 领单流转 | open→claimed→done 全程，assignee 正确 |
| A10 | 重复认领被拒 | 第二人 claim 同一帖，报错提示当前认领人 |
| A11 | 放单再领 | pause 后回 open，他人 claim 成功，log 含放单原因 |
| A12 | 阻塞与恢复 | claim→blocked→本人 claim→claimed |
| A13 | 停滞标记 | 25h 前 open 帖，stale=true |
| A14 | 按人查活 | `assignee=w-xxx` 只返回其认领帖 |
| A15 | 复活通道 | 作者 claim 自己的 done 帖 → open + log 记 reopen；非作者被拒 |
| A16 | 并发乐观锁 | 两请求带相同 expected_revision 并发 PATCH → 一个 200 一个 409 |
| A17 | 完成回访 | complete(notify=[w-x]) 后 w-x 收到 window_message |
| A18 | needs_action 分流 | true 进 open；false 直接 done |
| A19 | 防脚踩 | 作者 complete claimed 帖，认领人收到通知 |
| A20 | 回归 | board_post/board_read 原行为不变 |

## 10. 实施工单

| 工单 | 内容 | 预估 |
|---|---|---|
| W1 | Agent OS：DELETE/PATCH 路由（含服务端 revision 条件更新）+ 搜索过滤 + 单测 | 0.5d |
| W2 | Agent OS：GC 定时任务 + 单测 | 0.5d |
| W3 | agent-os-client：deleteMemory/patchMemory | 0.2d |
| W4 | lifecycle：board_update（6 动作+权限+迁移校验）+ board_read 增强 + board_post 微调 + schema 冒烟测试 | 0.8d |
| W5 | agents.json 管理员标记 + 端到端验收 A1-A20 | 0.3d |

## 11. 风险

1. Agent OS 是 legacy 服务——改前确认它仍是公告板唯一后端；若迁到 quantsys-v2 统一记忆库（已有 deprecate/supersede），状态机可直接平移
2. 重启 Agent OS 走 stop.sh 精确停止（多实例铁律）
3. 插件改动遵守 schema 铁律（每个 object 节点显式 additionalProperties），跑 `plugin-schema.smoke.test.ts`
4. status_reason 会被后续迁移覆盖（pause 覆盖 blocked 卡因）——历史由 moderation_log 兜底，明示取舍

## 12. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-25 | 终稿。六轮迭代收敛：可见性管理 → 工单流转 → goal 模式动作集（6 动作）→ 真实内容校准（needs_action/notify/一帖一事）→ goal 字段模型（6 层 Schema/revision 乐观锁）→ 自审计修复 7 项（复活通道矛盾、TOCTOU 服务端校验、blocked 接手/stale、claim_count 递增规则、防脚踩通知、OS 无鉴权风险）→ 终稿重写去迭代伤疤 |
