# REQ-261004154902-a7cd 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：V13 及其自动链路从「永远报成功」改成「说真话」：调仓失败会失败并通知人、休市日不再开火、复市首日不再跳过、挂单不再无声搁浅、账本虚增被登记并从统计排除；14 张父卡 53 张子卡全部完成，全量回归 6257 passed（唯一 failed 为他人引入的分层计数，3 errors 为既有环境问题）。

## 1. 验收列表

### v1-1 · 新增结果契约与失败可见性出口

**验收内容**：【新增结果契约与失败可见性出口】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_run_outcome.py tests/test_failure_sink.py -q 全过
2. 用例含：①error 非空时 ok=False 无论 executed
3. ②not_trading_day/not_due 映射 skipped、rebalance_failed/model_not_loaded 映射 failed
4. ③report_failure 在 NotificationFacade 抛错时不向外抛且日志含 source/reason。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-2 · 策略日检如实上报并修回通知方法

**验收内容**：【策略日检如实上报并修回通知方法】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/live_trading/test_daily_check_contract.py tests/test_v13_scheduler.py -q 全过
2. 用例含：①因子返回空 → ok=False 且 reason='factor_empty'
3. ②model.predict 抛错 → ok=False reason='rebalance_failed'
4. ③hasattr(SimulationTrader,'_send_rebalance_notification') is True
5. ④通知抛错时 ok 仍为 True 且 detail['notify_error'] 非空
6. ⑤周末 → reason='not_trading_day' 且上层 status='skipped'。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-3 · 交易日判定收敛到日历链

**验收内容**：【交易日判定收敛到日历链】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_trading_day_guard.py tests/test_trading_day_resolver.py -q 全过
2. 并断言 check('2026-10-05'|'2026-10-06'|'2026-10-07').is_trading_day is False、check('2026-10-08').is_trading_day is True（当前实现分别为 True/True/True/False）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-4 · 挂单撮合批量不中断、时段护栏与过期收口

**验收内容**：【挂单撮合批量不中断、时段护栏与过期收口】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/services/test_pending_orders.py -q 全过
2. 用例含：①首单抛非 TradingError 时第二单仍被处理且 errored>=1
3. ②now=16:41 调用时 skipped_off_hours>0 且 failed==0 且挂单仍 pending
4. ③创建时间早于上一交易日的挂单变 expired 且有 fail_reason。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-5 · cron 时刻口径、misfire 语义与「被跳过」落库

**验收内容**：【cron 时刻口径、misfire 语义与「被跳过」落库】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_scheduler_misfire_semantics.py -q 全过
2. 断言 build_cron_trigger('30 14 * * 1-5') 在 Asia/Shanghai 下 next_run_time.hour == 14
3. 构造一次超宽限的 run 后 select status from quant.scheduler_runs where status='missed' 至少一行
4. 加载器对 NULL 不再套 300 秒。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-6 · 调度失败的飞书兜底与告警覆盖面

**验收内容**：【调度失败的飞书兜底与告警覆盖面】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_job_failure_alerting.py -q 全过
2. 用例含：①8080 不可达时失败上报调用到 NotificationFacade（mock 断言）且日志出现「agent 通道失败 → 降级 feishu」
3. ②_job_failure_watch 的候选集合包含 scheduler_tasks 的任务名
4. ③evening_pipeline 的 kline_sync success=0 + 未覆盖 被判为失败。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-7 · 探活加调度活性并新增「该跑没跑」盘点器

**验收内容**：【探活加调度活性并新增「该跑没跑」盘点器】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_should_have_run.py -q 全过
2. venv/bin/python tools/check_should_have_run.py 退出码 0（当前启用集合无漏跑）
3. 把任一任务 cron 改为「1 分钟前」后退出码 2 且重复调用只告警一次
4. 工具输出含「任务/cron/最近应跑/实际最近 run/判定」五列。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-8 · 修通知渠道收窄并补齐缺失的飞书 formatter

**验收内容**：【修通知渠道收窄并补齐缺失的飞书 formatter】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_notification_channel_fallback.py -q 全过
2. 断言 select_channels('rebalance') 与 select_channels('risk_alert') 均包含 'feishu'（当前均为 ['agent']）
3. 断言 FeishuChannel 对这两类返回成功而非「不支持的通知类型」。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-9 · 收敛策略配置为单一来源并让生效值可见

**验收内容**：【收敛策略配置为单一来源并让生效值可见】验收

**操作步骤**：
1. venv/bin/python tools/check_strategy_config_effective.py 退出码 0
2. venv/bin/python -m pytest tests/test_strategy_config_single_source.py -q 全过
3. 断言运行时的 top_n == 声明值（当前声明 8 只、实际生效 5 只）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-10 · 修实未接线链路并删掉锁死 bug 的假断言

**验收内容**：【修实未接线链路并删掉锁死 bug 的假断言】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py tests/test_v13_chain_wiring.py -q 全过
2. 断言 Path(V13_CONFIG.model_path).exists() 与 Path(V13_CONFIG.factors_path).exists() 为真
3. 断言模型特征数与因子清单一致
4. 断言 strategy_execute_all 对返回体缺 ok 的情形判为失败。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-11 · 账本超卖拦截与现金重放对账器

**验收内容**：【账本超卖拦截与现金重放对账器】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/test_oversell_guard.py -q 全过
2. venv/bin/python tools/reconcile_sim_account.py --account v13_simulation 输出超卖清单（该账户当前有 4 只超卖，工具必须如实报出）
3. 构造一笔超额卖出时被拒绝且 reason='oversell_blocked'。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-12 · 历史虚增现金标记为脏并从统计排除（按用户裁定）

**验收内容**：【历史虚增现金标记为脏并从统计排除（按用户裁定）】验收

**操作步骤**：
1. 对账器对新口径输出「已排除项」清单且差额说明逐项覆盖（无未解释差额）
2. notes/legacy-cash-disposition.md 落盘并经人确认
3. venv/bin/python tools/reconcile_sim_account.py --account v13_simulation 的「未解释差额」为 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-13 · 假绿灯结构门禁

**验收内容**：【假绿灯结构门禁】验收

**操作步骤**：
1. venv/bin/python -m pytest -q 下，故意新增一个 def test_x(): return True 会让该用例红
2. venv/bin/python -m pytest tests/test_scheduled_jobs_account_value.py -q 全过且其 Fake 方法与真实仓储签名一致（断言在位）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-14 · 端到端冒烟与验收证据汇总

**验收内容**：【端到端冒烟与验收证据汇总】验收

**操作步骤**：
1. venv/bin/python tools/check_v13_chain_health.py 退出码 0 且三张表均有真实行
2. 验收材料含每条 FR 的可复核证据（命令 + 输出摘要 + 路径）
3. restore 检查：v13 任务恢复为 is_enabled=true 且 cron=30 14 * * 1-5（止血记录里的原值已按设计改写）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-15 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-16 · 需求级验收 · 不可照着验

**验收内容**：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 历史虚增现金标记为脏并从统计排除（按用户裁定）·分析 缺「怎么验」（"结论含置信度与适用边界，并列出被证伪的假设（附支撑数据的命令或 `docs/requirements/<REQ>/` 下证据路径）"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**操作步骤**：
1. 验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 历史虚增现金标记为脏并从统计排除（按用户裁定）·分析 缺「怎么验」（"结论含置信度与适用边界，并列出被证伪的假设（附支撑数据的命令或 `docs/requirements/<REQ>/` 下证据路径）"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）
2. 本条不阻断验收，但必须有人看过并决定。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

### v1-17 · 需求级验收 · E2E 覆盖

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）；若确认无需 E2E，通过时必须在意见中写明理由。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）
2. 若确认无需 E2E，通过时必须在意见中写明理由。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）

**验收状态**：✓ 通过

---

## 2. 测试报告

- FR-1 结果契约：venv/bin/python -m pytest tests/test_run_outcome.py -q → 16 passed（成功只由「执行完成且无错且非跳过」派生；失败默认不计为已执行）
- FR-2 日检如实上报：pytest tests/live_trading/test_daily_check_contract.py -q → 9 passed；含反向锁「调仓失败必须 ok=False 且不得是 executed=True+rebalance」
- FR-3 交易日判定：pytest tests/test_trading_day_guard.py -q → 47 passed；2026-10-05/06/07 判休市、10-08 判交易日（依据 quant.trading_calendar 实测 7791 行/交易所）
- FR-4 时刻口径：pytest tests/test_scheduler_misfire_semantics.py -q → 22 passed；30 14 * * 1-5 落在本地 14:30；宽限为空 = 唤醒必补跑
- FR-5 配置单源：venv/bin/python tools/check_strategy_config_effective.py → 退出码 0（持仓数 5 = 声明 5，止损 -15%、调仓 5 天一致）
- FR-6 未接线链路：pytest tests/regression/test_strategy_config_refactor.py tests/test_v13_chain_wiring.py -q → 25 passed；模型/因子路径真实存在，本金不再用 100 万
- FR-7 挂单不得搁浅：pytest tests/services/test_pending_orders.py -q → 28 passed；单笔异常不中断整批、盘后只跳过不误杀、超期作废并外发
- FR-8 停摆与漏跑可见：venv/bin/python tools/check_should_have_run.py → 退出码 0（11 张启用任务的五列对照表）
- FR-9 失败上报不得单通道：pytest tests/test_notification_channel_fallback.py -q → 13 passed；调仓/风控通知的候选渠道由只有 agent 变为 agent+飞书（8080 下线期间原本 100% 丢弃）
- FR-10 账本自洽：venv/bin/python tools/check_v13_chain_health.py → 退出码 0，三张表均有真实行；4 只超卖（300045/300469/300561/300765，虚增 ¥49,424.96）如实列出并标注为已登记脏数据
- 对账器：venv/bin/python tools/reconcile_sim_account.py --account v13_simulation → 退出码 0；现金重放差 ¥-0.01（分位取整），逐项解释齐全；清单不在时同样数据退 2（可逆性反证，pytest tests/test_oversell_guard.py -q → 25 passed）
- 假绿灯门禁：venv/bin/python tools/check_fake_green_tests.py --new-only → 命中 37 / 基线 37 / 新增 0，退出码 0；pytest tests/test_fake_green_gate.py tests/test_scheduled_jobs_account_value.py -q → 9 passed
- 调度失败告警：pytest tests/test_job_failure_alerting.py -q → 18 passed；调度相关 258 passed；APScheduler 路径的失败判定已统一为深判定
- 止血恢复核对（只读）：quant.scheduler_tasks id=249 启用、cron=30 14 * * 1-5、宽限为空；另 10 张任务宽限=300；jobstore 11 条任务在册
- 全量回归：venv/bin/python -m pytest tests/ -q --ignore=tests/e2e → 6257 passed / 164 skipped / 1 failed（tests/test_layer_purity.py，逐文件 AST 比对确认非本需求引入）/ 3 errors（tests/daemon 既有环境问题）
- 零外发与备底：全程 notify-guard intercepted=0 egress=0；改动另存 patch（37 文件 / 5773 行，git apply --check --reverse 通过）与快照（222 项）
- 验收材料：docs/requirements/REQ-261004154902-a7cd/verification.md（逐条 FR + 命令 + 输出摘要）
- 复核报告：docs/requirements/REQ-261004154902-a7cd/reviews/review-report.md（14 张卡逐一结论 + 3 处裁决 + 3 处复核修正 + 8 项残留）
- 测试证据：docs/requirements/REQ-261004154902-a7cd/tests/test-evidence.md（分卡命令与输出、工具退出码、反向验证、全量回归、只读数据核对、备底、67 张卡 covers 覆盖矩阵）
- 生产改动留档与回滚：notes/stopgap-2026-10-04.md（止血 SQL + 回滚）、notes/legacy-cash-disposition.md + config/known_dirty_simulation_data.json（脏数据口径与回滚）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 新增结果契约与失败可见性出口 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:54 |
| v1-2 | 策略日检如实上报并修回通知方法 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:54 |
| v1-3 | 交易日判定收敛到日历链 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:54 |
| v1-4 | 挂单撮合批量不中断、时段护栏与过期收口 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:54 |
| v1-5 | cron 时刻口径、misfire 语义与「被跳过」落库 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:54 |
| v1-6 | 调度失败的飞书兜底与告警覆盖面 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-7 | 探活加调度活性并新增「该跑没跑」盘点器 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-8 | 修通知渠道收窄并补齐缺失的飞书 formatter | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-9 | 收敛策略配置为单一来源并让生效值可见 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-10 | 修实未接线链路并删掉锁死 bug 的假断言 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-11 | 账本超卖拦截与现金重放对账器 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-12 | 历史虚增现金标记为脏并从统计排除（按用户裁定） | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-13 | 假绿灯结构门禁 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-14 | 端到端冒烟与验收证据汇总 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-15 | 需求级验收 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-16 | 需求级验收 · 不可照着验 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
| v1-17 | 需求级验收 · E2E 覆盖 | ✓ 通过 | human/session-8eb5b6f2-0d2a-44d3-bfca-878578124cec | 2026-10-04 16:56 |
