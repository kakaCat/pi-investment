# t-7fb8e4 加矩阵对照断言并校准设计落点

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
加矩阵对照断言并校准设计落点

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
npx vitest run tests/template-address.test.ts -t 矩阵 绿；故意给 (design, bug) 塞一条表项后断言变红；docs/requirements/REQ-260922213356-4a45/design/architecture.md 的落点路径与实现路径逐条一致。

## 实施方案（implementation）
在 packages/web/dsh-pmboard/tests/template-address.test.ts 增「节点×类型矩阵对照」用例：以显式矩阵常量逐格断言 resolveNodeTemplates 输出（等价于文档流程图与代码一致）；校准 docs/requirements/REQ-260922213356-4a45/design/architecture.md 的模块落点与「同源」实现说明（表成员判定 + 守护单测，取代运行时 import 门禁规则）。

## 上游产出摘要（dependsSummary）
- 补空集兼容回归与回退开关

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T15:29:18.105Z，窗口 session-2c955dd9-15b6-4cc5-8a0b-67ff978455aa）

文档画的"哪个节点该产哪些模板"矩阵与代码逐格对齐：谁改了代码忘了改文档矩阵会被测出来；同时把设计文档的落点表校准成实际文件，图与代码一致。

### 完成项

- 在 tests/template-address.test.ts 增 T-8 两例：显式矩阵 == resolveNodeTemplates 逐格输出；门禁启用的每个 (节点,类型) 组合都必须在矩阵里出现（漏一格即红）
- 在 design/architecture.md 追加「实现落点校准（T-8）」：设计名→实际文件对照，并说明层边界下"同源"改为表成员判定 + 守护单测
- typecheck 绿；两个地址测试文件共 36 例绿

### 改动文件

- `packages/web/dsh-pmboard/tests/template-address.test.ts`
- `docs/requirements/REQ-260922213356-4a45/design/architecture.md`

### 下一步

8 张卡中 7 张已 done；仅父卡 t-32b532（T-1）仍 in_progress——其 4 张子卡（t-26b426/t-78ba18/t-70a0ec/t-57ec0f）需人工在看板取消（子卡 done 需真实 workflow run，而引擎不可用）。取消后即可收尾该父卡，需求方能进入验收。

---
