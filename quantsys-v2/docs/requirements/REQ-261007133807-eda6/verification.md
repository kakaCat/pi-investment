# REQ-261007133807-eda6 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：「何时叫 agent」判据已收敛为唯一纯函数出口（decide_escalation，12 步顺序表 + 15 个受控理由码），理由码落库可查（watch_triggers 两列，两库已迁移）、卡面可读（两条渲染路径都写「升级原因」，非唤醒卡不多一行）、规则侧可见（写入口缺省显式化 + 读接口回显「何时会叫我」）、文档与码表同源（陈旧文案归零）。唤醒量不变（2/4 回归锁），既有相关 92 条用例零改动全绿。

## 1. 验收列表

### v1-1 · 落码表与裁决结果契约（EscalationCode + Verdict）

**验收内容**：【落码表与裁决结果契约（EscalationCode + Verdict）】验收

**操作步骤**：
1. pytest tests/services/test_watch_escalation_verdict.py -q -k code_table 全绿
2. python -c 断言 len(EscalationCode.ALL)==15 且 set(PATH_LABEL)==set(ALL)，退出码 0
3. 对 Verdict 赋值抛 FrozenInstanceError。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-2 · 收敛出唯一裁决出口 decide_escalation（15 条顺序表）

**验收内容**：【收敛出唯一裁决出口 decide_escalation（15 条顺序表）】验收

**操作步骤**：
1. pytest tests/services/test_watch_escalation_verdict.py -q 全绿（15 行逐行命中对应码，含 BUDGET_EXHAUSTED / OBSERVE_INTENT / AMOUNT_BELOW_THRESHOLD / SAME_TOPIC_COOLDOWN / ECONOMIC_BELOW_K / DEDUPED / UNKNOWN）
2. 同一输入经 decide_escalation 与 decide_escalation_paths 的 code 逐字段相同
3. pct_change 条件缺 MetricKind.PCT_CHANGE 时抛 WatchMetricContractViolation。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-3 · 规则侧显式化与人话说明（explain_escalation + 默认值显式化）

**验收内容**：【规则侧显式化与人话说明（explain_escalation + 默认值显式化）】验收

**操作步骤**：
1. pytest tests/domain/test_escalation_policy_defaults.py -q 全绿
2. python -c 断言 EscalationPolicy.default().to_dict()=={'auto_escalate': True, 'anomaly_change_pct': 5.0}
3. 对 escalation_policy=None 的规则 explain_escalation 返回值包含「未声明」且非空。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-4 · 兼容壳：EscalationChecker.should_escalate 委托出口

**验收内容**：【兼容壳：EscalationChecker.should_escalate 委托出口】验收

**操作步骤**：
1. pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py -q 全绿且 git diff 显示这两个测试文件零改动
2. EscalationChecker(auto_escalate=False 规则).should_escalate(...) 返回 None（与改造前一致）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-5 · 处置映射：disposition.decide 接受 Verdict

**验收内容**：【处置映射：disposition.decide 接受 Verdict】验收

**操作步骤**：
1. pytest tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py -q 全绿且两文件零改动
2. 同一输入下 disposition=='escalated' 的条数与改造前一致（用例逐条对拍）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-6 · tick() 单链路接线（裁决 → 处置 → 去重覆盖 → 通知）

**验收内容**：【tick() 单链路接线（裁决 → 处置 → 去重覆盖 → 通知）】验收

**操作步骤**：
1. pytest tests/services/test_watch_engine.py -q 全绿
2. 断言一次 tick 事件里含 escalation_code
3. 构造去重命中用例断言 reason 文本包含「原判」且 code=='DEDUPED'。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-7 · 迁移：watch_triggers 加两列（两个库都跑）

**验收内容**：【迁移：watch_triggers 加两列（两个库都跑）】验收

**操作步骤**：
1. python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test 退出码 0 并打印两列存在
2. 同一脚本对 quant_investment 再跑一次仍退出码 0（幂等）
3. pytest tests/test_orm_db_drift.py -q 全绿。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-8 · 落库两列 + 通知变量透传

**验收内容**：【落库两列 + 通知变量透传】验收

**操作步骤**：
1. pytest tests/services/test_watch_trigger_escalation_columns.py -q 全绿
2. 断言 deduped 与 auto_observed 两种处置的行 escalation_code 非 NULL
3. 模拟写库异常时通知仍发出且日志含 error。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-9 · 卡面「升级原因」行（旧渲染 + 分级渲染两条路径）

**验收内容**：【卡面「升级原因」行（旧渲染 + 分级渲染两条路径）】验收

**操作步骤**：
1. pytest tests/notification/test_watch_escalation_reason_line.py -q 全绿
2. 同一组变量喂两条渲染路径，两处「升级原因」行同形
3. escalation_code 与 reason 都为空时该行不出现
4. 变量缺失（旧调用方）时输出与改造前逐字相同。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-10 · 规则写入口缺省显式化（含批量与输入校验）

**验收内容**：【规则写入口缺省显式化（含批量与输入校验）】验收

**操作步骤**：
1. pytest tests/adapters/test_watch_rules_api_policy.py -q 全绿
2. 不传 escalation_policy 建规则后 psql 读回 escalation_policy 非空且等于 {'auto_escalate': true, 'anomaly_change_pct': 5.0}
3. 传非对象仍 400
4. 传 anomaly_change_pct=0 返回 400。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-11 · 规则读接口回显「何时会叫我」

**验收内容**：【规则读接口回显「何时会叫我」】验收

**操作步骤**：
1. pytest tests/adapters/test_watch_rules_api_policy.py -q -k explain 全绿
2. 响应同时含 escalation_policy 原值与非空 escalation_explain
3. 对存量 NULL 策略规则调用后 psql 复核 escalation_policy 仍为 NULL（读不篡改）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-12 · 判据文档与码表同源（修陈旧文案 + 契约判据表）

**验收内容**：【判据文档与码表同源（修陈旧文案 + 契约判据表）】验收

**操作步骤**：
1. pytest tests/services/test_watch_contract_parity.py -q 全绿（文档码集合 == EscalationCode.ALL）
2. grep -rn "触发频率异常" application/ domain/ docs/architecture/ 0 命中。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-13 · 端到端验收：触发 → 库有码 → 卡有理由（含唤醒量回归锁）

**验收内容**：【端到端验收：触发 → 库有码 → 卡有理由（含唤醒量回归锁）】验收

**操作步骤**：
1. pytest tests/application/test_watch_escalation_e2e.py -q 全绿且 notify-guard 输出 intercepted=声明值 与 egress=0
2. pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py tests/services/test_watch_engine.py -q 全绿
3. 两条 grep 结构判据 0 命中。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-14 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-15 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- ① 单一裁决出口：pytest tests/services/test_watch_escalation_verdict.py -q → 26 passed
- ② 理由码落库：pytest tests/services/test_watch_trigger_escalation_columns.py -q → 6 passed（真库两列）
- ③ 卡面：pytest tests/notification/test_watch_escalation_reason_line.py -q → 10 passed（两路径同形）
- ④ 规则侧：pytest tests/domain/test_escalation_policy_defaults.py tests/adapters/test_watch_rules_api_policy.py -q → 22 passed（含库回读）
- ⑤ 不破现状 + 唤醒量锁：92 passed（7 个文件）
- ⑥ 文档同源：pytest tests/services/test_watch_contract_parity.py -q → 4 passed；grep 触发频率异常 → 0 命中
- 迁移：20261007_watch_trigger_escalation.py --apply 两库 exit 0（幂等；89 行历史 NULL 不回填）
- 结构判据：-k "l2_wake or stale_removed" → 2 passed（L2 比较点仅 3 处非判定路由）
- 端到端：test_watch_escalation_e2e.py → 5 passed，notify-guard intercepted=0 egress=0
- 测试库清洁：quant_test → rules 0 / triggers 0
- 逐任务覆盖：tests/evidence.md §六 60 张卡逐条 covers 标注
- 评审报告：reviews/code-review.md（自查式，7 条发现 + 反向证据）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 落码表与裁决结果契约（EscalationCode + Verdict） | ⬜ 待验收 |  |  |
| v1-2 | 收敛出唯一裁决出口 decide_escalation（15 条顺序表） | ⬜ 待验收 |  |  |
| v1-3 | 规则侧显式化与人话说明（explain_escalation + 默认值显式化） | ⬜ 待验收 |  |  |
| v1-4 | 兼容壳：EscalationChecker.should_escalate 委托出口 | ⬜ 待验收 |  |  |
| v1-5 | 处置映射：disposition.decide 接受 Verdict | ⬜ 待验收 |  |  |
| v1-6 | tick() 单链路接线（裁决 → 处置 → 去重覆盖 → 通知） | ⬜ 待验收 |  |  |
| v1-7 | 迁移：watch_triggers 加两列（两个库都跑） | ⬜ 待验收 |  |  |
| v1-8 | 落库两列 + 通知变量透传 | ⬜ 待验收 |  |  |
| v1-9 | 卡面「升级原因」行（旧渲染 + 分级渲染两条路径） | ⬜ 待验收 |  |  |
| v1-10 | 规则写入口缺省显式化（含批量与输入校验） | ⬜ 待验收 |  |  |
| v1-11 | 规则读接口回显「何时会叫我」 | ⬜ 待验收 |  |  |
| v1-12 | 判据文档与码表同源（修陈旧文案 + 契约判据表） | ⬜ 待验收 |  |  |
| v1-13 | 端到端验收：触发 → 库有码 → 卡有理由（含唤醒量回归锁） | ⬜ 待验收 |  |  |
| v1-14 | 需求级验收 | ⬜ 待验收 |  |  |
| v1-15 | 需求级验收 | ⬜ 待验收 |  |  |
