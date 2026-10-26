# 验收实测证据快照（2026-10-19 · w-503df447）

> 对应 design/test-cases.md 的 TC-1 ~ TC-10。全部为本窗口实调/实测的原始证据摘要；数据源与时点标注对齐 R-013。

## TC-1/TC-2 W1 通道与 /bin/true

- `executor.go` L109-115 实读：`if task.WebhookURL != "" { executeWebhook } else if task.Command != "" { executeCommand }`——webhook 优先分支与诊断报告一致。
- `ls /bin/true` → `No such file or directory`；`ls -la /usr/bin/true` → 存在（-rwxr-xr-x）。本机 /bin 仅 37 条目。
- scheduler.go L166-180 实读：UpdateTask 仅 `Schedule`/`Enabled` 变化才 remove+重排；L321-323 cron 闭包捕获任务指针快照。

## TC-3 P2 周报 payload

- weekly-report-m6（afe560bc-dc9b-4692-982f-1cd1a10e85d6）payload 经 t-954eb4 改写，含【北极星 KPI 速览】【KPI-2 账户过滤】【降频判定】【可复核性】四强制段；update 后 get 复核全文一致（t-954eb4 汇报，2026-10-19）。

## TC-4/TC-5 W3 链路实测

- `signal_track(record, 600011, C, 7.68, manual)` → 返回 `已记录信号 ID 166`（price_check verified，dev 0.26%）。
- `signal_track(report, 2026-10-19~2026-10-19)` → 4 条信号含 ID 166，reason 完整可见（2026-10-19 22:19 实调）。
- `scheduler_manage(list)`：signal_perf_backfill_daily（1deba5ac）✅ 启用、27 次运行、last 2026-10-16T15:45 ✅（2026-10-19 实调）。

## TC-6/TC-7 W4 盘点复核

- `strategy_list` → total=5（202/193/163/178/179），全 unmeasured，与 w4-strategy §1 表一致；本卡零删除。
- psql 全量：`memories WHERE category='experience'` = 343 条；五桶 A73/B8/C13/D64/E185（分桶 SQL 与逐桶结局分布见 w4-experience §1）；E 桶 10 月仅 1 条（流入已自然停止）。

## TC-8 P3 自有样本

- `decision_scores(limit=30)` → 27 条；逐条核对 `context.account`：v13_simulation / v14_simulation / missed_signal_capture（无账户）——**本账户覆盖 0 条**（2026-10-19 实调）。汇总 meanExcessPct=-10.24%、big_loss 18/27 为策略线成绩，不作本账户先验（R-018/R-019）。

## TC-9 无新开仓

- `position_list(account_name=agent_brain)`（2026-10-19 实调）：002007 华兰生物 1100 股（-1.54%）、600000 浦发银行 100 股（+8.30%），总市值 1.54 万——与 RFC 017 起草快照一致，本需求全程零新开仓。

## TC-10 P1 根因口径

- task_runs 2026-10-14~10-19 失败记录错误清一色 `dial tcp 127.0.0.1:13080: connect: connection refused`（W1 诊断）；10-19 午后 DSH 恢复后 webhook 任务（realtime-check 14:30 ✅、daily-audit 19:00 ✅、daily-review 18:00 ✅、post-market 18:30 ✅、attribution 18:40 ✅、m4 16:53 ✅）全部成功——通道无 bug、断在对端存活。
- task_delivery_backlog：90 条中 31 delivered / **59 failed 永久丢失**（耗尽 10 次补投上限），无告警。

## 附：spike 无自动化测试的声明

类型档（spike 实施）：「不为探针写测试或文档，除非它要进正式代码」。本需求零代码改动，故 tests/ 仅含本证据快照，无单元/E2E 测试。

## 覆盖映射（每任务 → 验证用例）

> spike 的"测试"= 可复核命令与实测证据；每张卡由其所属工作包的 TC 覆盖。

- TC-1/TC-2/TC-10 覆盖 W1 诊断链：covers: t-1790d5；covers: t-531b46；covers: t-aa8733；covers: t-386642
- t-f4e050 的验证 = 复核卡判 fail 驱动用户取消（reviews/review-summary.md）：covers: t-f4e050；covers: t-73356d；covers: t-3560e9
- TC-3 覆盖 W2 KPI 链：covers: t-954eb4；covers: t-d176e2；covers: t-eab3f3
- TC-4/TC-5 覆盖 W3 SOP 链：covers: t-557f90；covers: t-c7a81f；covers: t-5ed45b
- TC-6/TC-7 覆盖 W4 治理双链：covers: t-ab4c82；covers: t-ee21d9；covers: t-542f40；covers: t-5c0823；covers: t-9bae04；covers: t-86eed7；covers: t-84e0f3；covers: t-2a366f
- TC-9 + RFC 017 文件检查（design/test-cases.md t-381c5a 验收标准①②③）覆盖 W3 授权链：covers: t-38602b；covers: t-381c5a；covers: t-6ec327
- 汇总卡的验证 = 本文件 + report.md §3 对照表可复跑：covers: t-c5c85c；covers: t-9b2a59
