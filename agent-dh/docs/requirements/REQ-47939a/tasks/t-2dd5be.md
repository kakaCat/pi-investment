# t-2dd5be HTTP 路由改薄（删除重复状态校验）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
HTTP 路由改薄（删除重复状态校验）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run tests/routes-rollup.test.ts tests/reqboard.test.ts tests/api-client.test.ts 全绿；src/http/routes.ts 存在且该文件内 grep 不到 status === 字面量比较（状态判断只在 domain）。

## 实施方案（implementation）
src/host/routes.ts → src/http/routes.ts + src/http/routers/{requirements,tasks,stages,verdicts,artifacts,triage}.ts；删除原 :285/:347/:355 的重复状态校验改为调用例（错误→HTTP 状态映射集中一处）；既有路由测试指向新入口。验证：npx vitest run tests/routes-rollup.test.ts tests/reqboard.test.ts tests/api-client.test.ts。

## 上游产出摘要（dependsSummary）
- 用例层落地（12 用例 + 3 查询投影）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
