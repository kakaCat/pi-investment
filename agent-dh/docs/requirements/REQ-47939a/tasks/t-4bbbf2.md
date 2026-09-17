# t-4bbbf2 适配器落地（仓储/文档/时钟/ID/会话/弹框）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
适配器落地（仓储/文档/时钟/ID/会话/弹框）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run tests/application/repository.test.ts tests/capture-hook.test.ts 全绿；src/adapters/JsonLedgerRepository.ts 与 src/adapters/FileDocRepository.ts 存在；断言台账写入走临时文件+rename（原子性）且损坏台账被隔离不抛。

## 实施方案（implementation）
src/host/store.ts → src/adapters/JsonLedgerRepository.ts（实现 read/snapshot/mutate/replaceAll，保留原子写与损坏隔离）；agent-tools 内嵌 fs 落盘 + sync-artifacts.ts → src/adapters/FileDocRepository.ts；新增 src/adapters/SystemClock.ts 与 RandomIdFactory.ts；capture-hook 会话部分 → src/adapters/SessionProbeAdapter.ts；deps.userQuestions 接缝 → src/adapters/UserQuestionsAdapter.ts。新增 tests/application/repository.test.ts（临时目录真实现）。验证：npx vitest run tests/application/repository.test.ts tests/capture-hook.test.ts。

## 上游产出摘要（dependsSummary）
- 立层边界门禁与端口骨架

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
