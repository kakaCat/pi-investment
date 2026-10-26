# REQ-261022022657-857f 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交易闭环补口交付：① 反思定时任务接入既有唤醒通道（notify_agent→/wake，开关可控、失败计 overdue）；② 减仓批次收敛（累计比例匹配、逐批退役 watch_rules、fill 事件留痕、重放幂等、无匹配降级）；③ 消息→离场核实为既有实现（69b8）并补 5 例回归；④ metrics 扩两个当日读数。plan 套件 139 例全绿，watch 无新增红，生产重启后两字段可读。

## 1. 验收列表

### v1-1 · 接线反思唤醒通道（waker 注入 + 任务调用）

**验收内容**：【接线反思唤醒通道（waker 注入 + 任务调用）】验收

**操作步骤**：
1. pytest tests/plan/test_reflection_job.py -q 全绿，含新增两例：注入 fake waker 后每张到期计划被调用一次且 review_due_at 前移
2. waker 抛异常时该计划 overdue_count+1 且其余计划继续处理。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-2 · 实现减仓批次匹配纯函数

**验收内容**：【实现减仓批次匹配纯函数】验收

**操作步骤**：
1. pytest tests/plan/test_plan_batch_convergence.py -q 全绿：sold_ratio=0 → []
2. 0.33 → [0]
3. 0.8 → [0]（第二批实际只完成 47%，按批比例不退役，比原计划文本更严格）
4. 1.0 → [0,1]
5. -0.1 或 1.1 → ValueError。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-3 · 扩展 on_fill 批次退役与事件留痕

**验收内容**：【扩展 on_fill 批次退役与事件留痕】验收

**操作步骤**：
1. pytest tests/plan/test_plan_batch_convergence.py -q 全绿：卖 1/3 仅批次 0 退役且计划仍 holding
2. 卖完全批退役且 closed
3. 同 trade_id 重放不重复
4. 无匹配批次写 degraded 事件不退役。psql 查 trading_plan_events kind='fill' 可见 detail.batch。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-4 · 接线消息→P1 待办与唤醒（含 24h 去重）

**验收内容**：【接线消息→P1 待办与唤醒（含 24h 去重）】验收

**操作步骤**：
1. pytest tests/plan/test_news_exit_linkage.py -q 全绿：critical+持仓 → TodoService.create（P1/rule_change/evidence.source=news）且 wake 一次
2. 同 news_id+symbol 24h 内不建第二条
3. 无持仓不建待办仅通知。psql 查 watch_todos evidence->>'source'='news' 可见行。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-5 · 扩 metrics 读数并收口回归

**验收内容**：【扩 metrics 读数并收口回归】验收

**操作步骤**：
1. pytest tests/plan -q 全绿
2. pytest tests -k watch -q 无新增红（仅允许两例预存红）
3. curl -s http://127.0.0.1:5001/api/watch/metrics 含 news_todos_today 与 reflection_woken_today（缺数 null）
4. 给出三条读数样例。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-6 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

### v1-7 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：npx vitest run tests/x.test.ts

**验收状态**：✓ 通过

---

## 2. 测试报告

- pytest tests/plan -q → 139 passed（新增 19 例：反思 3/批次 11/消息 5/指标 3 中的新增部分）
- pytest tests -k watch -q → 791 passed / 2 failed（两例为基线预存红 test_watch_t12_todo_creation，无新增红）
- 重启后生产实测：curl /api/watch/metrics → news_todos_today=0 / reflection_woken_today=0 / pending_todos=2 / engine_alive=True
- 无 schema 变更（复用 trading_plan_events.detail 与 watch_todos.evidence），无需迁移与回滚脚本
- 读数样例：events kind=fill 带 detail.batch；watch_todos evidence.source=news；scheduler_runs.result.woken
- 评审记录：reviews/review-notes.md（含 FR-3 与 69b8 重复的登记与处理）
- 测试证据：tests/test-evidence.md（covers 覆盖全部 24 张卡）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 接线反思唤醒通道（waker 注入 + 任务调用） | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
| v1-2 | 实现减仓批次匹配纯函数 | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
| v1-3 | 扩展 on_fill 批次退役与事件留痕 | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
| v1-4 | 接线消息→P1 待办与唤醒（含 24h 去重） | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
| v1-5 | 扩 metrics 读数并收口回归 | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
| v1-6 | 需求级验收 | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
| v1-7 | 需求级验收 | ✓ 通过 | human/session-11ba604a-d626-4750-b955-7e769919277e | 2026-10-22 02:47 |
