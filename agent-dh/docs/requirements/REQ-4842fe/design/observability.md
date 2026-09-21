---
req_id: REQ-4842fe
doc: design/observability
serves: FR-11, FR-12, FR-13
status: design
---

# REQ-4842fe 设计 · 运行与可观测

## 1. 推进事件日志  `serves: FR-11`

**位置**：需求目录 `docs/requirements/<REQ>/advance-log.md`（append-only）+ 台账内 `advance.history[]`（结构化，供看板渲染）。

**事件记录字段**：

| 字段 | 说明 |
|---|---|
| `at` | 事件触发时点 |
| `requirementId` | 需求 id |
| `event` | OPEN_PARENT / RUN_SUBTASK / FINALIZE_PARENT / ROLLUP / PAUSE |
| `parentId` / `subtaskId` | 涉及卡片（无则空） |
| `outcome` | ok / failed / skipped / noop |
| `durationMs` | 本步耗时 |
| `detail` | 一句话：做了什么、为什么停 |

**幂等标注**：`outcome=noop` 表示"事件被触发但台账无变化"（重复触发、无 ready 卡）；连续 noop 计入停滞计数。

## 2. 看板进度口径  `serves: FR-12`

| 指标 | 口径 |
|---|---|
| 父卡进度 | 该需求下 `done` 父卡数 / 父卡总数（不含 canceled） |
| 子卡进度 | 该需求下 `done` 子卡数 / 子卡总数 |
| 当前在跑 | 状态为 `in_progress` 的卡（父卡 ≤ 上限），看板上高亮 |
| 自动状态徽标 | `运行中`（autoRun=true 且有人在跑）/ `已暂停`（autoRun=false）/ `熔断`（autoRun=false 且触发原因为停滞/连续失败）/ `手动`（存量卡） |
| 停滞计数 | 连续 noop 次数（仅供参考，达阈值即熔断） |

## 3. 告警与弹框  `serves: FR-13`

**唯一人工交互面 = 会话内弹框**（2026-09-21 用户裁定：**只有弹框**——不另做告警通道、不发飞书、不接通知面；宿主日志仅作排障留痕）。弹框**内容模板**：

```
【实施链暂停】REQ-4842fe
· 卡住位置：父卡 t-abc123 / 子卡 t-def456（stageKind=test，第 2 次尝试）
· 失败原因：<run stopReason / 凭证门哪一项不过 / 跨卡覆盖>
· 已做处理：autoRun 已置 false，链停在 implementing，未进验收
· 可选处置：重跑该卡 / 退回上游重新描述需求 / 取消
```

**落点（FR-16）**：同一文本以 `ask_user_question` 抛出，三选一直接落处置动作，人不需要进看板找入口。

**熔断**：连续失败达阈值（默认 3）或连续 noop 达阈值（默认 5）→ 同样暂停 + **同口径会话弹框**（`reason=熔断`），不发飞书。

## 4. autoRun 的持久化与恢复  `serves: FR-12`

- **持久化位置**：台账 `RequirementRecord.autoRun`（非内存、非进程态）；
- **重启恢复**：进程启动 / 面板重启后，扫描 `autoRun=true` 且状态非 accepting 的需求 → 续跑下一个推进事件（崩溃不丢链）；
- **单飞锁恢复**：`advance.lockAt` 超过 stale 阈值（默认 15 分钟）视为持有者已死，可被接管；
- **人工开关**：暂停 = `autoRun=false`（不推下一张牌，已在跑的 run 允许跑完）；继续 = `autoRun=true` + 触发一次事件；终止 = 暂停 + 取消在跑卡（取消是人工门）。

## 5. 排障入口  `serves: FR-11, FR-13`

| 想回答的问题 | 看哪里 |
|---|---|
| 链走到哪一步了 | 看板需求卡进度 + `advance-log.md` 末几行 |
| 为什么停了 | 最后一条 `outcome=failed/paused` 事件 + 子卡失败评论 + 告警记录 |
| 是不是重复干活了 | 事件日志中同一 `subtaskId` 的 `ok` 次数（应 ≤1，其余为 noop/失败重试） |
| 这次返工改了什么 | 卡片 `revisions`（kind=update/rollback/reopen） |
| 是否发生过跨卡覆盖 | 子卡失败评论中的冲突标记 + 涉及文件 mtime |
| 自动链是否还在跑 | 需求卡的自动状态徽标 + `autoRun` 字段 |
