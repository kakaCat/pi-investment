# t-bfb1ad 契约卡：toolviews 数据契约 + 纯函数骨架 + renderSmart 签名

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
契约卡：toolviews 数据契约 + 纯函数骨架 + renderSmart 签名

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
cd packages/pages/dsh-pmboard && npx vitest run tests/toolviews-contract 通过：parseArgs 对半截 JSON 返回 undefined、中文映射覆盖 task_move 7 个 to 值、renderSmart 输出首行 ≤120 字符且不含 '{'

## 实施方案（implementation）
新建 src/client/toolviews/shared.ts（纯函数，不依赖 react）+ tests/toolviews-contract.test.ts；src/tools/shared.ts 加 renderSmart（不改 renderJson）

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T03:05:37.478Z，窗口 session-85447f15-ee57-44ef-8fd0-d8526111c0b3）

契约卡完成：toolviews 数据契约（parseArgs/resultJson/中文映射/fallbackModel 纯函数，不 throw 契约）+ host renderSmart 签名落地，契约单测 17/17 绿、typecheck 干净

### 完成项

- src/client/toolviews/shared.ts：block 形态/parseArgs（半截 JSON→undefined）/resultText/resultJson/5 张中文映射表/CardSummary 契约/fallbackModel（永不 null）
- src/tools/shared.ts 新增 renderSmart（首行中文摘要 ≤120 单行 + JSON 明细；renderJson 保留未改）
- tests/toolviews-contract.test.ts：17 用例四档覆盖（正常/缺字段/畸形/error），vitest 全绿
- typecheck 退出码 0

### 改动文件

- `packages/pages/dsh-pmboard/src/client/toolviews/shared.ts`
- `packages/pages/dsh-pmboard/src/tools/shared.ts`
- `packages/pages/dsh-pmboard/tests/toolviews-contract.test.ts`

### 下一步

t2 骨架接线：注册入口 + BizRow 布局 + task_move 示范卡（t-3e64cb）

---
