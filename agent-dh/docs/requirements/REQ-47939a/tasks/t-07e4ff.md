# t-07e4ff 立层边界门禁与端口骨架

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
立层边界门禁与端口骨架

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run tests/layer-boundary.test.ts 通过；src/domain/errors.ts 与 src/application/ports.ts 存在且被该测试引用；测试内含"扫描器命中文件数"下限断言（防扫描器失效假绿）。

## 实施方案（implementation）
新建 src/domain/errors.ts（REQBOARD_* 错误码常量，照 design/domain-model.md §7）；新建 src/application/ports.ts（ReqboardRepository/DocRepository/Clock/IdFactory/SessionProbe/UserQuestionPort，签名照 §5）；新建 tests/layer-boundary.test.ts（读 src/**/*.ts 文本，正则抽取 import 并断言 design/architecture.md §2 依赖方向表；断言 src/domain 无 node: / Date.now / Math.random；断言 src/tools 与 src/http 无 status === 字面量；末尾断言扫描器命中文件数 ≥N 防静默失效）。验证：npx vitest run tests/layer-boundary.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
