# t-cea897 旧文件删除 + 尺寸/边界门禁 + 全量回归

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
旧文件删除 + 尺寸/边界门禁 + 全量回归

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run 全绿且 tests/size-budget.test.ts 与 tests/layer-boundary.test.ts 通过；src/host/agent-tools.ts 不存在（existsSync 为 false）；src 下所有 .ts 单文件 ≤400 行，白名单在测试内显式列出并注明理由。

## 实施方案（implementation）
删除 src/host/ 整目录（含 agent-tools.ts 2946 行）与逐一确认无引用的死代码分支（每删一处列进任务汇报）；新增 tests/size-budget.test.ts（单文件 ≤400 行 + src/host/agent-tools.ts 不存在 + 显式白名单及理由）；跑全量回归并修净。验证：npx vitest run（全量）+ wc -l。

## 上游产出摘要（dependsSummary）
- HTTP 路由改薄（删除重复状态校验）
- 工具壳拆分与 13→9 收敛

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
