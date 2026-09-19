# t-552eeb verification.md 结构化生成 + 9 类文档完整性检查

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
verification.md 结构化生成 + 9 类文档完整性检查

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test，T-U5/T-U6/T-U7/T-I7/T-I8 全绿；生成的 docs/requirements/<REQ>/verification.md 包含验收列表/测试报告/文档完整性检查/验收结果四段。

## 实施方案（implementation）
新增 src/domain/workflow/VerificationDoc.ts（renderVerificationDoc 纯渲染四段）与 DocCompleteness.ts（checkDocCompleteness）；SubmitVerification.ts 生成文件并在缺项时抛 REQBOARD_DOC_INCOMPLETE。

## 上游产出摘要（dependsSummary）
- 扩展验收项状态与通过判据（domain）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
