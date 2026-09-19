# t-df5d0c 裁决后回填验收结果表

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
裁决后回填验收结果表

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test，tests/verdicts-and-rework.test.ts 的 T-I9 断言 verification.md 的验收结果表包含 编号/验收项/状态/验收人/验收时间 五列。

## 实施方案（implementation）
verdicts 落地后按新 sheet 重渲染并覆写 docs/requirements/<REQ>/verification.md 的「验收结果」段。

## 上游产出摘要（dependsSummary）
- FR-8 验收失败自动回退实施（application）
- verification.md 结构化生成 + 9 类文档完整性检查

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
