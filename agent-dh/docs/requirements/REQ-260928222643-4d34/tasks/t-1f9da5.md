# t-1f9da5 新增一次性交接持有器 src/client/board-focus.ts·研发

> 任务卡骨架（由窗口 `session-f17b3bd0` 按已批准计划补写——本环境的 auto-chain 执行器未产出 run 证据，故这三张父卡的子卡文档未自动生成；内容取自父卡 **t-3e952f** 的批准实施方案与验收标准）

## 在做什么
实现本卡的代码改动：新增一次性交接持有器 src/client/board-focus.ts

## 解决什么问题
把批准计划里的实现落到源码，并为其附带可执行的单测。

## 范围
- 阶段：implement
- 端侧：frontend
- 子卡阶段：dev

## 得到什么结果

在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿；grep -c "export function" src/client/board-focus.ts 输出 4。

## 实施方案（implementation）
新建 packages/web/dsh-pmboard/src/client/board-focus.ts（零 import）：模块级 pendingReqId + 四个导出 requestBoardFocus/takeBoardFocus/clearBoardFocus/peekBoardFocus；take 取走即清、空串不登记、不写 storage/URL；新建 tests/board-focus.test.ts 覆盖 TC-6。
按父卡实施方案完成源码与单测。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
本卡所属父卡（t-3e952f）的实现已在本窗口完成并通过验证；证据见 reviews/review-report.md 与 tests/test-report.md。不读会话历史，按本卡自足执行。
