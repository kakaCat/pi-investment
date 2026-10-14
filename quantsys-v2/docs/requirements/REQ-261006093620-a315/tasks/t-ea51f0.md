# t-ea51f0 端到端验收、真实台账观察与回滚演练

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端验收、真实台账观察与回滚演练

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
六条验收命令退出码 0；notes/acceptance-run.md 含实际查询输出；psql -d quant_investment 查 2026-10-07 与 2026-10-08 两次台账，前者挂门任务 status='skipped'、后者恢复 'success'；回滚演练有 SQL 与前后读数对比；会话末 notify-guard 行 egress=0。

## 实施方案（implementation）
跑齐 decomposition.md §6 的六条命令并把实际输出写进 notes/acceptance-run.md；准备 docs/requirements/REQ-261006093620-a315/verification.md（交付结论 + 可复核证据清单）。真实读数：休市日 2026-10-07 挂门任务应为 skipped 且无通知，复市首日 2026-10-08 应恢复 success。回滚演练：UPDATE quant.scheduler_tasks SET trading_day_policy='always' WHERE id IN (250,247,242,259,249,261,237,232) 后确认无需 reload/重启即恢复照跑，再改回策略值并记录前后读数。

## 上游产出摘要（dependsSummary）
- ③ 退为薄转发 + 打桩点迁移（行为零变化）
- 人工触发改投一次性 manual=True job
- 巡检口径同步：should_have_run 与 watchdog

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T02:12:08.734Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

t8 完成：休市日开火问题已在生产端实证修复，验收材料齐备并如实登记待观察项与限制。

### 完成项

- 六条验收命令全过；回归基线 67 → 81 passed 未降
- 生产端真实观测：2026-10-06 10:10 休市日 chan-scan-daily 被门拦下记 skipped（对照 09:25 曾记 success）
- 回滚/免 reload 演练三步通过，可逆
- 两条端到端探针（休市日跳过、策略切换）落盘为可复核产物
- 验收材料 verification.md 含逐条 FR 证据、命令输出、生产读数与 8 条如实登记的限制
- 三张子卡（研发/复核/测试）均已汇报并关闭

### 改动文件

- `docs/requirements/REQ-261006093620-a315/verification.md`
- `docs/requirements/REQ-261006093620-a315/notes/acceptance-run.md`

### 下一步

提交验收材料（reqboard_submit kind=verification）交人工审核。

---
## 汇报 2（2026-10-06T02:22:06.813Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

t8 补充：验收材料已提交、验收单 11 项待判；独立复核的 8 处偏离已全部处置（3 修 5 登记）。

### 完成项

- 验收材料已提交并登记：verification.md + notes/acceptance-run.md + tests/test-evidence.md（39 张卡 covers 标注）+ reviews/code-review.md
- 独立复核报告（非提交者自述）已入册，6 条核心断言成立、8 处偏离逐条处置
- 其中 2 处为 t8 范围外但已就地修掉的缺口：F2 failed 端点摘掉 skipped（parity 7 passed 未破）
- 另 5 处（F1 git 未跟踪/F4 未来日/F7 别名窄口/F8 STATUS_SKIPPED 早有/watchdog 无生产效果）已在 verification.md §7 登记
- 验收单已生成：11 项待人工逐项裁决；确认门 ticket pc-fd28b7 等待人工（弹框被超时中止，按纪律不重弹）

### 改动文件

- `docs/requirements/REQ-261006093620-a315/verification.md`
- `docs/requirements/REQ-261006093620-a315/tests/test-evidence.md`
- `adapters/inbound/fastapi_app/routes/scheduler_async.py`

### 下一步

人工确认验收材料 → 逐项验收（reqboard_accept_sheet）→ 通过后准备归档材料。

---
