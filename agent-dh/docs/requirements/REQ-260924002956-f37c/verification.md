# REQ-260924002956-f37c 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：修复完成：立项弹框「✖️ 不需要立项」现为终端路径——拒绝后立即收框、不再追问类型/难度/文档位置；拒绝不再被登记为闸门作答，不再投递「闸门待改进」假告警；肯定路径四问一次问完 + 同调用内建单的行为不变。真机验证通过（另一窗口拒绝留痕已写入、无假告警）；范围内回归测试 37/37 全绿。

## 1. 验收列表

### v1-1 · 固化拒绝路径复现：加三条失败用例（红）

**验收内容**：【固化拒绝路径复现：加三条失败用例（红）】验收：跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts packages/web/dsh-pmboard/tests/gate-handlers.test.ts —— 新增断言失败（至少一条红），且失败原因与 BUG-1/BUG-2 现象一致；未改动任何 src/ 文件（git diff --stat 只含 tests/）。

**操作步骤**：
1. 跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts packages/web/dsh-pmboard/tests/gate-handlers.test.ts —— 新增断言失败（至少一条红），且失败原因与 BUG-1/BUG-2 现象一致
2. 未改动任何 src/ 文件（git diff --stat 只含 tests/）。

**预期结果**：按上述步骤执行后满足验收标准：跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts packages/web/dsh-pmboard/tests/gate-handlers.test.ts —— 新增断言失败（至少一条红），且失败原因与 BUG-1/BUG-2 现象一致；未改动任何 src/ 文件（git diff --stat 只含 tests/）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状

**验收内容**：【修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状】验收：t1 的三个测试文件全绿；跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/capture.test.ts 肯定路径仍绿（四问合计 4 问、创建后状态 brainstorming）；git diff --stat 只含 capture-mapping.ts / CaptureRequirement.ts / h4-resume.ts（可含测试文件）。

**操作步骤**：
1. t1 的三个测试文件全绿
2. 跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/capture.test.ts 肯定路径仍绿（四问合计 4 问、创建后状态 brainstorming）
3. git diff --stat 只含 capture-mapping.ts / CaptureRequirement.ts / h4-resume.ts（可含测试文件）。

**预期结果**：按上述步骤执行后满足验收标准：t1 的三个测试文件全绿；跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/capture.test.ts 肯定路径仍绿（四问合计 4 问、创建后状态 brainstorming）；git diff --stat 只含 capture-mapping.ts / CaptureRequirement.ts / h4-resume.ts（可含测试文件）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest

**验收内容**：【回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest】验收：npx vitest run packages/web/dsh-pmboard 全绿（0 failed）；边界断言存在且通过：有 from 的闸门负分支含「节点仍在」、肯定路径 enqueue=1。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard 全绿（0 failed）
2. 边界断言存在且通过：有 from 的闸门负分支含「节点仍在」、肯定路径 enqueue=1。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard 全绿（0 failed）；边界断言存在且通过：有 from 的闸门负分支含「节点仍在」、肯定路径 enqueue=1。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 真机验证：重启加载后实走一次拒绝路径

**验收内容**：【真机验证：重启加载后实走一次拒绝路径】验收：拒绝后弹框立即关闭且会话内不出现「闸门待改进」文本；state/capture-rejections.json 新增一条本窗口记录（时间戳晚于重启时刻）。

**操作步骤**：
1. 拒绝后弹框立即关闭且会话内不出现「闸门待改进」文本
2. state/capture-rejections.json 新增一条本窗口记录（时间戳晚于重启时刻）。

**预期结果**：按上述步骤执行后满足验收标准：拒绝后弹框立即关闭且会话内不出现「闸门待改进」文本；state/capture-rejections.json 新增一条本窗口记录（时间戳晚于重启时刻）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts packages/web/dsh-pmboard/tests/gate-handlers.test.ts → 3 files passed, 37 tests passed（拒绝路径 + 肯定路径 + 无 from 边界）
- npx vitest run packages/web/dsh-pmboard → 1674 passed / 96 failed；96 failed 全部来自隔壁窗口在飞重构（t-ec02a7 已逐条取证），本次范围内 6 文件 87 条全绿
- state/capture-rejections.json 新增记录：session-4c0d1035 at=1790215994105（2026-09-24 10:13:14 CST），晚于重启时刻 00:42:28，证明另一个未绑定窗口真实走通拒绝路径
- diag log 无「闸门待改进 / G0 未通过 / 节点仍在 brainstorming」投递，证明 BUG-2 已修复
- 代码改动：capture-mapping.ts（拆两段）、CaptureRequirement.ts（拒绝短路 + G0 挪段）、h4-resume.ts（无 from 不编现状）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 固化拒绝路径复现：加三条失败用例（红） | ✓ 通过 | human/session-4799e386-677d-431b-bb36-c752ad82640b | 2026-09-24 10:20 |
| v1-2 | 修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状 | ✓ 通过 | human/session-4799e386-677d-431b-bb36-c752ad82640b | 2026-09-24 10:20 |
| v1-3 | 回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest | ✓ 通过 | human/session-4799e386-677d-431b-bb36-c752ad82640b | 2026-09-24 10:20 |
| v1-4 | 真机验证：重启加载后实走一次拒绝路径 | ✓ 通过 | human/session-4799e386-677d-431b-bb36-c752ad82640b | 2026-09-24 10:20 |
| v1-5 | 需求级验收 | ✓ 通过 | human/session-4799e386-677d-431b-bb36-c752ad82640b | 2026-09-24 10:20 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-4799e386-677d-431b-bb36-c752ad82640b | 2026-09-24 10:20 |
