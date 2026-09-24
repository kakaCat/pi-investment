# t-6eca2a 新增 kind=design 登记用例与工具入口

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增 kind=design 登记用例与工具入口

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿；首次 registered_count=5、二次=0；空目录返回 0 且不谎报成功

## 实施方案（implementation）
新增 packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts；改 packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts（SUBMIT_KINDS 增 design + 分派 + schema）与 packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts；新增 packages/web/dsh-pmboard/tests/design-registration.test.ts。

## 上游产出摘要（dependsSummary）
- 下沉产物发现核心并薄壳化 ArtifactSync

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
