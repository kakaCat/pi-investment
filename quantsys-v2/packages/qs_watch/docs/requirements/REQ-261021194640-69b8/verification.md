# REQ-261021194640-69b8 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：三条接缝交付完成：①成交回写（中立端口 + execute_trade 落库后发事件 + 收敛器五场景）②消息投递（消息桥 + 新闻/政策扫描接入 + 盘后窗口）③待办闭环（关闭接规则联动 + 执行期限 + 三态统计）。回归 1195 passed / 2 存量基线失败（实现前已复现，非本期引入）。生产只读核查完成，执行统计可读；新链路待服务重启生效。评审与测试证据见 reviews/ 与 tests/（含 33 张任务卡 covers 标注）。

## 1. 验收列表

### v1-1 · 建交易包中立成交端口并保留旧路径转发

**验收内容**：【建交易包中立成交端口并保留旧路径转发】验收

**操作步骤**：
1. venv/bin/python -m pytest tests/application/test_fill_port.py -q 退出码 0
2. 断言注册/注销生效、旧 import 等价、无监听者时 notify_fill 返回 False 且不抛错。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-2 · 待办证据列与部分索引

**验收内容**：【待办证据列与部分索引】验收

**操作步骤**：
1. venv/bin/python infrastructure/persistence/migrations/20261021_watch_todos_evidence.py 退出码 0（dry-run）
2. --apply 重跑 0 行变更
3. pytest tests/repositories/test_watch_todo_repository.py -q 退出码 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-3 · 补挂止损/止盈写持仓状态

**验收内容**：【补挂止损/止盈写持仓状态】验收

**操作步骤**：
1. pytest tests/application/test_watch_position_lifecycle.py -q 退出码 0
2. 新用例断言补挂后规则 position_state='holding'，且下一拍退出族规则不被状态门跳过。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-4 · 关闭待办接规则变更联动

**验收内容**：【关闭待办接规则变更联动】验收

**操作步骤**：
1. pytest tests/application/test_rule_change_linkage.py tests/application/test_watch_todo_close_rule_change.py -q 退出码 0
2. 断言 ignored+rule_change 后规则字段变化、watch_rule_changes 新增 1 行且 trigger_id 非空
3. 重复 close 返回 409。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-5 · 执行期限巡检与时区归一

**验收内容**：【执行期限巡检与时区归一】验收

**操作步骤**：
1. pytest tests/application/test_sla_job.py -q 退出码 0
2. 期限前 1 分钟回执 0 条、期限后 1 分钟 1 条、重复 tick 仍 1 条
3. 带时区/裸时间/跨日三组断言通过
4. 待办未被写成 expired。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-6 · 真实成交落库后发事件

**验收内容**：【真实成交落库后发事件】验收

**操作步骤**：
1. pytest tests/application/test_account_trade_fill_callback.py -q 退出码 0
2. 断言卖出成交后监听方收到 action='sell' 且 trade_id 非空
3. 注入抛错监听器时成交返回成功且日志含 fill_notify_error。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-7 · 消息→P1 待办桥（critical 建单 + 唤醒）

**验收内容**：【消息→P1 待办桥（critical 建单 + 唤醒）】验收

**操作步骤**：
1. pytest tests/application/test_news_todo_bridge.py -q 退出码 0
2. critical 建 1 条待办并唤醒 1 次、soft 建 0 条、重复 dispatch 待办数不增、单条失败进 errors 且不抛错。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-8 · 执行闭环统计端点

**验收内容**：【执行闭环统计端点】验收

**操作步骤**：
1. pytest tests/api/test_watch_exec_stats.py -q 退出码 0
2. 空数据返回全 0
3. 构造三类样本后 executed/declined/timeout 分别命中
4. 分位与台账查询一致
5. 治理类不进分母。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-9 · 新闻与政策扫描接入消息桥

**验收内容**：【新闻与政策扫描接入消息桥】验收

**操作步骤**：
1. pytest tests/application/test_news_watch_service.py tests/application/test_policy_watch_service.py -q 退出码 0
2. critical 命中建 1 条待办、soft 建 0 条
3. bridge 未注入时行为与现状一致。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-10 · sidecar 拆盘中/盘后，盘后消息可扫

**验收内容**：【sidecar 拆盘中/盘后，盘后消息可扫】验收

**操作步骤**：
1. pytest tests/application/test_watch_sidecar_window.py -q 退出码 0
2. 16:30 时钟下消息扫描执行、回填与生命周期任务不重复执行
3. 非交易日不扫
4. 窗外返回 scanned=False 不抛错。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-11 · 成交收敛端到端场景

**验收内容**：【成交收敛端到端场景】验收

**操作步骤**：
1. pytest tests/scenarios/test_watch_fill_converge.py -q 退出码 0
2. 五条断言逐条通过（待办 handled、触发 handled、exit 规则退役、position_state=none、时延只写一次）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-12 · 组合根装配与降级开关

**验收内容**：【组合根装配与降级开关】验收

**操作步骤**：
1. pytest tests/application/test_fill_sync_factory_wiring.py tests/application/test_watch_factory_news_bridge.py -q 退出码 0
2. 未注入桥/联动时行为与现状一致
3. 装配异常时引擎仍启动且日志含降级原因。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-13 · 回归与生产只读核查

**验收内容**：【回归与生产只读核查】验收

**操作步骤**：
1. venv/bin/python -m pytest tests -k "watch or fill or todo or trading" -q 退出码 0（存量 2 例失败先定性并记录）
2. 三条只读 SQL 均返回结果且与设计预期一致。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-14 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-15 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

## 2. 测试报告

- docs/requirements/REQ-261021194640-69b8/verification-evidence.md（回归读数 + 生产只读核查 + 生效条件 + 遗留）
- docs/requirements/REQ-261021194640-69b8/reviews/review-report.md（设计↔实现↔裁定对照）
- docs/requirements/REQ-261021194640-69b8/tests/test-evidence.md（测试证据 + 33 张卡 covers 标注）
- docs/requirements/REQ-261021194640-69b8/requirement.md（需求与 3 条 D-x 裁定）
- docs/requirements/REQ-261021194640-69b8/decomposition.md（13 卡拆分与接口对照）
- docs/requirements/REQ-261021194640-69b8/tasks/t-c6c5d2.md（成交端口：24 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-a5fa64.md（成交发包：4 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-2ff7ca.md（收敛场景：5 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-27e8c7.md（消息桥：6 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-88d4da.md（扫描接入：6 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-3ef50b.md（盘后窗口：5 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-e95a2a.md（关闭联动：8 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-e29f67.md（执行期限：42 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-b8d5ae.md（统计端点：5 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-e416b7.md（装配：3 例）
- docs/requirements/REQ-261021194640-69b8/tasks/t-f9a9b3.md（回归与生产核查）
- docs/requirements/REQ-261021194640-69b8/tasks/t-0846ee.md（证据列迁移）
- docs/requirements/REQ-261021194640-69b8/tasks/t-c18a41.md（补挂状态：7 例）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 建交易包中立成交端口并保留旧路径转发 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:40 |
| v1-2 | 待办证据列与部分索引 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:40 |
| v1-3 | 补挂止损/止盈写持仓状态 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:40 |
| v1-4 | 关闭待办接规则变更联动 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:40 |
| v1-5 | 执行期限巡检与时区归一 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:40 |
| v1-6 | 真实成交落库后发事件 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:41 |
| v1-7 | 消息→P1 待办桥（critical 建单 + 唤醒） | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:41 |
| v1-8 | 执行闭环统计端点 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:41 |
| v1-9 | 新闻与政策扫描接入消息桥 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:41 |
| v1-10 | sidecar 拆盘中/盘后，盘后消息可扫 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:41 |
| v1-11 | 成交收敛端到端场景 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:42 |
| v1-12 | 组合根装配与降级开关 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:42 |
| v1-13 | 回归与生产只读核查 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:42 |
| v1-14 | 需求级验收 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:42 |
| v1-15 | 需求级验收 | ✓ 通过 | human/session-c0714366-6e5b-42e9-9b20-c259d58b3820 | 2026-10-21 21:42 |
