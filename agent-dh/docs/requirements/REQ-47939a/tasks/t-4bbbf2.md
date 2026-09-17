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
## 汇报 1（2026-09-17T11:58:58.940Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

t5 复核通过：六个适配器落地并实现 t1 端口（仓储/文档/时钟/ID/会话/弹框），原子写有故障注入断言；适配器尚未接入工具调用链属 t8 范围，已显式标注为并存实现。

### 完成项

- 发起窗口独立复核全部通过（见 docs/requirements/REQ-47939a/verification.md 的 t5 段）
- 卡面验收命令 → 40 passed；6 个适配器文件齐备；新模块全部 ≤400 行
- 原子写断言核验：tests/application/repository.test.ts 含 10 处 tmp/rename 相关断言（含 rename 失败不污染目标的故障注入）
- 客户端构建门：pnpm build:client + verify-client-build.mjs 通过
- 诚实标注：SessionProbeAdapter/UserQuestionsAdapter 等端口方法尚未切进工具调用链，agent-tools 私有认证/弹框逻辑仍在 → 切换属 t8，届时行为需逐字保持

### 改动文件

- `docs/requirements/REQ-47939a/verification.md`
- `packages/pages/dsh-pmboard/src/adapters/JsonLedgerRepository.ts`
- `packages/pages/dsh-pmboard/src/adapters/FileDocRepository.ts`
- `packages/pages/dsh-pmboard/src/adapters/SystemClock.ts`
- `packages/pages/dsh-pmboard/src/adapters/RandomIdFactory.ts`
- `packages/pages/dsh-pmboard/src/adapters/SessionProbeAdapter.ts`
- `packages/pages/dsh-pmboard/src/adapters/UserQuestionsAdapter.ts`
- `packages/pages/dsh-pmboard/tests/application/repository.test.ts`

### 下一步

t6 用例层（12 用例 + 3 查询投影）依赖 t2-t5 已全部就绪。

---
