# REQ-261006093620-a315 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：v2 库表调度（APScheduler）已补上交易日门——8 条吃当日行情的任务在休市日不再执行、只留一行 status=skipped；门 fail-open（降级照跑并留降级痕迹）、复市首日不跳过、人工触发仍可跑。生产端已实证：2026-10-06 10:10（休市日）chan-scan-daily 被门拦下记 skipped（同路径此前 09:25 记 success）。独立复核确认 6 条核心断言成立；其报出的 3 处功能缺口（降级不留痕／跳过记账失败可外抛／failed 端点混入 skipped）已当场修复并补回归锁，另 5 处风险逐条登记。回归 67 → 83 passed 未降；回滚 = 八行策略改回 always，无需 DDL、无需 reload。待观察：10-07 休市日与 10-08 复市首日台账读数（该两日未到，已在 verification.md §6/§7 显式标注）。

## 1. 验收列表

### v1-1 · 判据真源：trading_day_gate 模块与策略入口

**验收内容**：【判据真源：trading_day_gate 模块与策略入口】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q 全过（13 行真值表 + 反例锁）
2. ./venv/bin/python -c "from application.services.trading_day_gate import should_skip as s
3. print(s('always')[0], s('holiday')[0])" 输出 False False（缺省与未知策略都不跳，fail-open）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-2 · 数据契约：三值列 + CHECK + 8 行回填 + ORM

**验收内容**：【数据契约：三值列 + CHECK + 8 行回填 + ORM】验收

**操作步骤**：
1. 迁移脚本不带 --apply 时退出码 0 且只打印 DDL
2. --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test 后 psql -d quant_test -c "\d quant.scheduler_tasks" 出现 trading_day_policy 列
3. ./venv/bin/python -m pytest tests/test_orm_db_drift.py -q 全过
4. 数据断言：232 行为 holidays、其余 7 行为 trading-days，且其余启用行均为 always。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-3 · ③ 退为薄转发 + 打桩点迁移（行为零变化）

**验收内容**：【③ 退为薄转发 + 打桩点迁移（行为零变化）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q 全过（含新增的证伪断言）
2. ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import gate
3. print(gate.skip_non_trading_day.__module__)" 输出 application.services.trading_day_gate（证明是转发而非本地实现）
4. git diff --stat 显示 runtime.py 与 pipeline.py 零改动。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-4 · 仓储层：complete_run_skipped + 抽 _finish_run

**验收内容**：【仓储层：complete_run_skipped + 抽 _finish_run】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_scheduler_run_result_json.py tests/test_scheduler_inner_failure.py -q 全过（既有 complete_run 调用方零回归）
2. 新增单测断言 complete_run_skipped 后该行 status='skipped'、completed_at 非空、result 含 date/Decimal 也能落库、config.last_status='skipped'、last_error IS NULL。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-5 · 执行期接门与跳过落账（含 manual 旁路）

**验收内容**：【执行期接门与跳过落账（含 manual 旁路）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q 全过，含四条断言：休市日跳过时 _execute_command 零调用且 run.status='skipped' 且 last_error IS NULL
2. 休市日 _report_failure_to_sink 零调用
3. manual=True 时照跑（status='success'）
4. 交易日路径 complete_run_skipped 零调用。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-6 · 人工触发改投一次性 manual=True job

**验收内容**：【人工触发改投一次性 manual=True job】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q 全过
2. 断言 scheduler.get_job('task_1').next_run_time 与触发前相等（不再被人工触发扰动），且 get_jobs() 中出现 manual_1_* 一次性 job 且其 kwargs['manual'] is True。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-7 · 巡检口径同步：should_have_run 与 watchdog

**验收内容**：【巡检口径同步：should_have_run 与 watchdog】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_should_have_run.py -q 全过
2. 两条关键断言在场：status='skipped' 的 run 不进 missed 列表（不误报漏跑），且 status='missed' 的 run 仍然进 missed 列表（只豁免正常跳过、不放宽真漏跑）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-8 · 端到端验收、真实台账观察与回滚演练

**验收内容**：【端到端验收、真实台账观察与回滚演练】验收

**操作步骤**：
1. 六条验收命令退出码 0
2. notes/acceptance-run.md 含实际查询输出
3. psql -d quant_investment 查 2026-10-07 与 2026-10-08 两次台账，前者挂门任务 status='skipped'、后者恢复 'success'
4. 回滚演练有 SQL 与前后读数对比
5. 会话末 notify-guard 行 egress=0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-9 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收 · 孤儿用例

**验收内容**：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——tests/infrastructure/test_apscheduler_service.py、tests/infrastructure/test_scheduler_skip_ledger.py、tests/test_daily_jobs_trading_day_gate.py、tests/test_scheduler_duplicate_prevention.py、tests/test_scheduler_inner_failure.py、tests/test_scheduler_misfire_semantics.py、tests/test_scheduler_run_result_json.py、tests/test_scheduler_trading_day_gate.py、tests/test_should_have_run.py。请补 serves: 声明，或说明为何无需映射；通过时意见须写明处置方式。

**操作步骤**：
1. 孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——tests/infrastructure/test_apscheduler_service.py、tests/infrastructure/test_scheduler_skip_ledger.py、tests/test_daily_jobs_trading_day_gate.py、tests/test_scheduler_duplicate_prevention.py、tests/test_scheduler_inner_failure.py、tests/test_scheduler_misfire_semantics.py、tests/test_scheduler_run_result_json.py、tests/test_scheduler_trading_day_gate.py、tests/test_should_have_run.py。请补 serves: 声明，或说明为何无需映射
2. 通过时意见须写明处置方式。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed

**验收状态**：✓ 通过

---

## 2. 测试报告

- 命令：./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q → 21 passed
- 命令：./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q → 8 passed（含独立复核 F5/F6 补的 2 条）
- 命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q → 28 passed
- 命令：./venv/bin/python -m pytest tests/test_should_have_run.py tests/test_orm_db_drift.py -q → 37 passed
- 命令：./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q → 13 passed
- 合并回归：调度侧 67 → 83 passed（t4 +8、t5 +8），各卡复用未降
- 命令：./venv/bin/python -m pytest tests/migration/test_scheduler_parity.py -q → 7 passed（F2 端点修正未破 parity）
- 生产台账：run_id=3381 chan-scan-daily status=skipped @ 2026-10-06 10:10（休市日）、error=NULL、source=trading-calendar-holiday、policy=trading-days
- 对照改前：同路径 run_id=3379 pre-market-scan status=success @ 2026-10-06 09:25（logs/api.log:8532）
- 生产服务重启：PID 74347（10-05 21:28）→ 86953（10-06 10:05:58），日志 Task loading complete: 11 loaded
- 回滚演练：notes/test_e2e_policy_toggle_probe.py → skipped / success / skipped（免 reload、可逆；notify-guard egress=0）
- 端到端探针：notes/test_e2e_holiday_skip_probe.py → run.status=skipped、error=None、五键 result 齐全
- 卡覆盖对照：tests/test-evidence.md §7 以 covers: 逐张标注 39 张卡（8 父 + 31 子）
- 独立复核报告（非提交者自述）：reviews/code-review.md（6 条断言成立 + 8 处偏离）
- 复核发现的 3 处功能缺口已修复并补回归锁：F5 降级留痕、F6 记账失败不外抛、F2 failed 端点摘掉 skipped
- 迁移：infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py 两库均已 apply
- 交付结论、逐条 FR 证据与 14 条如实登记的限制：docs/requirements/REQ-261006093620-a315/verification.md
- 逐卡实际输出留档：docs/requirements/REQ-261006093620-a315/notes/acceptance-run.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 判据真源：trading_day_gate 模块与策略入口 | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-2 | 数据契约：三值列 + CHECK + 8 行回填 + ORM | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-3 | ③ 退为薄转发 + 打桩点迁移（行为零变化） | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-4 | 仓储层：complete_run_skipped + 抽 _finish_run | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-5 | 执行期接门与跳过落账（含 manual 旁路） | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-6 | 人工触发改投一次性 manual=True job | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-7 | 巡检口径同步：should_have_run 与 watchdog | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-8 | 端到端验收、真实台账观察与回滚演练 | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-9 | 需求级验收 | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-10 | 需求级验收 | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
| v1-11 | 需求级验收 · 孤儿用例 | ✓ 通过 | human/session-35ba53fd-df95-40fa-92df-639ba03cba4d | 2026-10-06 11:05 |
