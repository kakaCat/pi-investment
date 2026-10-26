# 接口说明（spike 口径）

> 本 spike 不新增/变更任何 API 接口。本文件登记调研中**实际调用过的工具/接口面**及其实测行为（含缺陷），作为报告结论的复核入口。

## 实测接口行为台账（2026-10-19）

| 接口/工具 | 实测行为 | 缺陷/口径 |
|---|---|---|
| `strategy_list` / `GET /api/strategies` | 返回 user 5 条；builtin 17 条经后端分页拉全 | 全 unmeasured；`status` 只由 structure 派生不代表业绩 |
| `POST /api/backtest/strategy` | 策略 202/002007 一年窗：equity 100000→82664、184 天有持仓 | trades 只记已平仓往返，窗口末不强制平仓 |
| `evolution_run`（propose） | 后端诚实降级，但工具 schema 必填 best_params/best_metrics/fitness → 硬错误 | **连续第 4 周复现**；同一事实 evolution_leaderboard 可正常读出 degraded_reason |
| `signal_track record/report` | record→report 链路实测通过（测试信号 ID 166 当日可见） | C 级落库+回填机制已闭环（report 82 条中 C 级 53 条） |
| `decision_scores` | 27 条全量返回，含 band/excessReturnPct/learnedLesson | 无 account 过滤参数；全量均值 -10.24% 是策略线成绩 |
| `scheduler_manage list` | 60 任务全量状态可读 | "上次结果"是单点快照，成功率统计需自算窗口 |
| `reqboard_task_run` 自动链 | 本需求期间驱动 6 张父卡展开/闭环 | 观测面缺口：FINALIZE_PARENT 失败只落 advance-log 无人消费；t-9bae04 三子卡速通假完成（17 秒/张、lastReport 全空） |

## agent-os 侧接口（W1 只读诊断）

- 执行通道选择：executor.go L109-115（webhook_url 非空 → webhook 优先）；executeCommand L209-235（绝对路径直接 exec，不查 PATH）。
- 残留陷阱：UpdateTask 仅 schedule/enabled 变化才重排（scheduler.go L167）——只改 command/webhook_url 必须重启 agent-os 才生效。

接口变更声明：本需求未变更任何接口契约；上述缺陷均登记为后续实施卡建议（report.md §5），不在本 spike 修复。
