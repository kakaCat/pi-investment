# t-bcca7b node-panel.ts 加入口按钮并删除执行流程块调用与入参·复核

> 任务卡骨架（由窗口 `session-f17b3bd0` 按已批准计划补写——本环境的 auto-chain 执行器未产出 run 证据，故这三张父卡的子卡文档未自动生成；内容取自父卡 **t-2eb71d** 的批准实施方案与验收标准）

## 在做什么
对照设计不变量逐条复核：node-panel.ts 加入口按钮并删除执行流程块调用与入参

## 解决什么问题
防「改面板改坏看板」与「静默失败」两类回归。

## 范围
- 阶段：implement
- 端侧：frontend
- 子卡阶段：review

## 得到什么结果

grep -n "injection\|isolation" src/client/node-panel.ts 无匹配；在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel-process-map.test.ts 全绿。

## 实施方案（implementation）
renderHead 内相对时间之后追加 button.dsh-pm-np-board-entry[data-action=np-board-entry][data-req]（文案固定 项目看板 ↗，跳过与正常分支共用）；删除 renderProcessFold 调用、ProcessFoldContext、NodePanelInput.injection/isolation 与相关 import 及头注；同步 tests/node-panel.test.ts。
对照 design/interfaces.md I-6 五条不变量逐条留证；确认看板消费方（board-mount.ts）与后端路由未被触碰。

## 上游产出摘要（dependsSummary）
- t-1d3596

## 执行方式提示（executorHint）
本卡所属父卡（t-2eb71d）的实现已在本窗口完成并通过验证；证据见 reviews/review-report.md 与 tests/test-report.md。不读会话历史，按本卡自足执行。
