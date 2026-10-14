# REQ-261005203907-2b8c 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：DailyJobs 宿主已装上任务级交易日门。休市日不再对冻结快照空跑，也不再为空跑发通知；跳过在台账留一行 status=skipped（与「根本没跑」可区分）；门 fail-open（日历降级照跑并标注 degraded）；复市首日不跳过；evening_pipeline 保留 K 线段（休市日唯一缺口修复路径）只跳因子段。零 DDL、零迁移、零开关。验收：门用例 27 + 晚间管线用例 6 + 既有回归 37 = 70 passed（提交前当次运行），通知守卫 egress=0，静态检查 0 命中。两项如实报出：① 门需重启宿主才生效，本次未重启（需人拍板）；② 10-06/10-07/10-08 的真实观察窗口未到，已写成可执行复跑清单。

## 1. 验收列表

### v1-1 · 门模块与 JobDef 字段（接口先行）

**验收内容**：【门模块与 JobDef 字段（接口先行）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q -k "truth or holiday or degraded" 全过
2. 另断言 JobDef('x', dtime(0,0), (0,), lambda: {}, 'd').trading_days_only is False（位置参数兼容）
3. 断言 skip_non_trading_day 在 check 抛异常时不抛、返回 skip=False。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-2 · 宿主接线：_run_job 跳过早退 + 3 任务置位

**验收内容**：【宿主接线：_run_job 跳过早退 + 3 任务置位】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q 全过
2. 用例断言 send_mock.call_count == 0 且 marks[0][0] == 'skipped'
3. 断言 {j.job_id for j in JOBS if j.trading_days_only} == {'pool_daily_refresh','chip_distribution','evolution_fitness'}。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-3 · 晚间管线：因子段局部跳过（K 线段原样）

**验收内容**：【晚间管线：因子段局部跳过（K 线段原样）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q 全过
2. 其中 test_holiday_fresh_kline_skips_factor 断言 handle_factor_compute 未被调用，test_trading_day_never_skips_factor 断言交易日下 handle_factor_compute 被调用一次，test_holiday_kline_error_still_computes_then_raises 断言抛 RuntimeError。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-4 · 兼容与回滚核验（零 DDL / 既有消费者行为）

**验收内容**：【兼容与回滚核验（零 DDL / 既有消费者行为）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_pool_refresh_daily.py -q 全过（既有 TestIsDue 三分支不回归）
2. git diff --name-only 不含 infrastructure/persistence/migrations/**
3. notes/compat-rollback.md 落盘且含实际命令输出。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-5 · 回归 + 真实休市日/复市首日观察

**验收内容**：【回归 + 真实休市日/复市首日观察】验收

**操作步骤**：
1. 四条命令退出码 0
2. notes/holiday-observation.md 含实际查询输出与命令原文（不是『应该没问题』）
3. 若观察窗口未到，文件里显式列出待观察项与复跑命令
4. 会话末打印的 notify-guard 行 egress=0、offenders=[]。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-6 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-7 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收 · E2E 覆盖

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）；若确认无需 E2E，通过时必须在意见中写明理由。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）
2. 若确认无需 E2E，通过时必须在意见中写明理由。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q → 70 passed, 1 warning（提交前当次运行）
- 命令：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q → 27 passed（TC-1 真值表 13 + 宿主接线 8 + 兼容判据 6）
- 命令：./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q → 6 passed（六行真值表，含交易日绝不跳因子的回归锁）
- 通知守卫：全部运行打印 notify-guard intercepted=0 egress=0 offenders=[]（测试期零真实外发）
- 测试证据台账：docs/requirements/REQ-261005203907-2b8c/tests/test-evidence.md（汇总 + 分文件 + TC 逐条对照 + 静态检查 + 未覆盖三项 + 20 张卡的 covers 标注）
- 评审报告：docs/requirements/REQ-261005203907-2b8c/reviews/code-review.md（改动清单 + 逐条对照设计无偏离 + 发现 R-1~R-5）
- 证据文件：docs/requirements/REQ-261005203907-2b8c/notes/holiday-observation.md（改造前基线实测 + 服务启动时间证据 + 待观察项与复跑命令）
- 证据文件：docs/requirements/REQ-261005203907-2b8c/notes/compat-rollback.md（零 DDL 实测：无迁移改动 / status 为 text 无 CHECK / 测试库同形 + 三步回滚）
- 代码落点：adapters/inbound/fastapi_app/daily_jobs/gate.py（新建：fail-open 判定 + 五键注解，永不抛）
- 代码落点：adapters/inbound/fastapi_app/daily_jobs/runtime.py:104-124（早退点在开始通知之前；写 status=skipped；不观测 duration）
- 代码落点：adapters/inbound/fastapi_app/daily_jobs/registry.py（pool_daily_refresh / chip_distribution / evolution_fitness 三处置 trading_days_only=True）
- 代码落点：adapters/inbound/fastapi_app/daily_jobs/pipeline.py:119-135（因子段局部跳过；K 线段与 error 上抛语义零改动）
- 静态检查：tools/check_undefined_names.py 与 tools/analyze_layer_violations.py 对本需求 4 个改动文件均 0 命中；py_compile OK（ruff 未安装，如实标注未跑）
- 台账基线实测（2026-10-05 休市日）：pool_daily_refresh success 22.1 秒、evening_pipeline running 53.4 分钟、chip_distribution running 13.5 分钟
- 阻塞项 1（需人拍板）：门只在宿主线程重启后生效——服务进程 2026-10-05 09:09:10 启动（早于改动落盘），本次未重启生产服务，命令见 holiday-observation.md §3.1
- 阻塞项 2（窗口未到）：休市日 10-06/10-07 与复市首日 10-08 的真实台账观察未发生，已写成可执行复跑清单（holiday-observation.md §3.2/§3.3）
- 已知缺口：fail-open 降级路径仅单元验证，未在真实日历源故障下实测（理由见 holiday-observation.md §4）
- 既有问题（非本需求引入）：tests/test_daily_jobs_notify_truthfulness.py 的 streak capsys 断言在宽选择集下 order-dependent 失败、单跑通过

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 门模块与 JobDef 字段（接口先行） | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-2 | 宿主接线：_run_job 跳过早退 + 3 任务置位 | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-3 | 晚间管线：因子段局部跳过（K 线段原样） | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-4 | 兼容与回滚核验（零 DDL / 既有消费者行为） | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-5 | 回归 + 真实休市日/复市首日观察 | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-6 | 需求级验收 | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-7 | 需求级验收 | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
| v1-8 | 需求级验收 · E2E 覆盖 | ✓ 通过 | human/session-b97ce139-00d0-456f-b147-6b897bcb5369 | 2026-10-05 21:29 |
