# t-fbde12 立项降级路径不丢文档位置

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
立项降级路径不丢文档位置

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/create-doc-location.test.ts 全绿；不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts（增 doc_location 入参 + 输出 schema 增 doc_location/defaults_used）、packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts、packages/web/dsh-pmboard/src/application/internal/support.ts（createRequirementDirect 接 docBasePath + 回落标记）；新增 packages/web/dsh-pmboard/tests/create-doc-location.test.ts。

## 上游产出摘要（dependsSummary）
- 定义新契约类型与端口

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
