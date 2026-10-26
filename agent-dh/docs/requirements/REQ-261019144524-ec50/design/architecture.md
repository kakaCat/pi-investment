# 架构说明（spike 口径）

> 本需求为 spike（调研定方案），交付物是**结论与清单**而非生产代码（类型档：只做验证所需最小动作）。
> 本文件按验收 9 类文档口径落盘，说明本次调研触碰的系统架构面；正式设计总览见 [design.md](design.md)。

## 涉及的架构组件（只读调研范围）

| 组件 | 位置 | 本需求的动作 |
|---|---|---|
| agent-os 调度器执行器 | agent-os/internal/kernel/scheduler/executor.go（L109-115 webhook 优先；L209-235 executeCommand）、scheduler.go（L166-180 UpdateTask 重排条件；L321-323 cron 闭包快照） | 只读诊断（W1），结论：通道选择无 bug，不改动 |
| quantsys-v2 信号追踪 | signal_tracking_service.py（update_performance 不按 grade 过滤）、signal_jobs.py（SignalPerfBackfillJob） | 只读核查（W3），结论：C 级落库+回填已闭环 |
| quantsys-v2 策略/经验存储 | quant.strategy_configs（5 条）、memories 表 category='experience'（343 条）、派生表 backtest_results / evolution_runs / evolution_strategy_runs | 只读盘点（W4），处置待用户裁决 |
| reqboard 自动实施链 | packages/web/dsh-pmboard（advance-select / DoneEvidenceSpec / SubmitVerification） | 本需求实施期间的实测样本（FINALIZE_PARENT 凭证门、子卡速通假完成 2 例），结论进报告 §5 后续卡建议 |

## 唯一写动作

- weekly-report-m6 定时任务 payload 改写（W2 验收项，scheduler_manage update）；
- signal_track 测试信号 ID 166（W3 验收项，reason 标注测试用途）。

架构边界声明：未修改任何交易规则/仓位/止损（需求边界 + R-016）；未改 agent-os/quantsys-v2 任何代码。
