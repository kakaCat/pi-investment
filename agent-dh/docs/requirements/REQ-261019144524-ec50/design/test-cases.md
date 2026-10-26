# 测试用例（spike 口径：验收复核命令集）

> spike 不写自动化测试（类型档：不为探针写测试）。本文件以**可复核命令 + 预期结果**形式给出验收用例，
> 与 [../report.md](../report.md) §3 的 P1-P4 对照表一一对应。实测证据快照见 [../tests/verification-evidence.md](../tests/verification-evidence.md)。

| # | 用例 | 复核命令 | 预期结果 | 实测（2026-10-19） |
|---|---|---|---|---|
| TC-1 | W1 通道选择结论 | 读 agent-os/internal/kernel/scheduler/executor.go L105-115 | webhook_url 非空 → webhook 优先分支 | ✅ 一致（w-503df447 独立核验） |
| TC-2 | /bin/true 报错解释 | `ls /bin/true` | No such file or directory（本机 macOS /bin 无 true） | ✅ 一致 |
| TC-3 | P2 周报 payload | `scheduler_manage(action=get, task_id=afe560bc-dc9b-4692-982f-1cd1a10e85d6)` | payload.prompt 含三 KPI 采集指令与降频规则 | ✅（t-954eb4 update 后 get 复核一致） |
| TC-4 | W3 record→report 链路 | `signal_track(action=report, start_date=2026-10-19, end_date=2026-10-19)` | 当日信号含测试信号 ID 166（reason 标注【SOP验收测试信号】） | ✅ 4 条含 ID 166 |
| TC-5 | W3 回填任务活性 | `scheduler_manage(action=list)` | signal_perf_backfill_daily 近 7 日有 ✅ | ✅ last 2026-10-16T15:45 ✅ |
| TC-6 | W4 策略库无硬删 | `strategy_list` | 现存 163/178/179/193/202 共 5 条，与清单一致 | ✅ 一致（0 删除） |
| TC-7 | W4 经验库口径 | `psql quant_investment -c "SELECT count(*) FROM memories WHERE category='experience'"` | 343 条；五桶计数见 w4-experience §1 | ✅ 343 |
| TC-8 | P3 自有样本现状 | `decision_scores` 逐条看 `items[].context.account` | 本账户（agents.json instance.account）覆盖条数如实报告 | 实测 0 条（27 条全策略线回填）——P3 数值指标未达，报告 §3 诚实声明 |
| TC-9 | 无新开仓纪律 | `position_list(account_name=<本实例投资账户>)` | 持仓 002007/600000 两只，市值 1.54 万，与 RFC 017 快照一致 | ✅ 无新开仓 |
| TC-10 | P1 失败根因口径 | `agent_os_logs(source=scheduler, grep="connection refused")` + scheduler_manage list | 10-14~10-19 失败=DSH 停机；恢复后 webhook 任务 ✅ | ✅ 口径修正成立（成功率指标未达，见报告 §3） |
