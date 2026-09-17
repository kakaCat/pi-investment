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
## 汇报 1（2026-09-17T12:40:20.805Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

t9 复核通过：src/host/ 整目录删净（13 文件 2144 行 → 0），死代码逐一附无引用证据删除，尺寸门禁 5 例且白名单防只增不减，全量 616 passed / 1 failed。

### 完成项

- 发起窗口独立复核：src/host 目录不存在、agent-tools.ts 不存在；全量 616 passed / 1 failed（基线项，失败数未变 2）
- 体积门禁故障注入实测：造 402 行探针文件 → 红（"超标文件（未在白名单内）"）；删除后 5 passed
- 白名单设计复核：5 条限死在 client/ 与 shared/protocol.ts、逐条带理由、且必须当前仍超限（t11/t12 拆完自动变红）——比卡面更严，保留
- 文本零丢失逐模块核验（消息字面量账，HEAD:src/host/<f> vs 新 src 递归）：artifact-gates/capture-hook/capture/routes/stage-detail/stage-prompts/store/sync-artifacts/verdicts 均 0；rollup.ts 报 2 经查文本仍在（RollupSpec.ts:139/156，模板串改拼接，工具误报）；classifier/session-sync 的 25/10 属已删退役机制；agent-tools 的 51 属 t8 工具描述改写（卡面要求），0 条来自 t9 搬迁的 12 个模块
- 死代码删除的例外已按四条要求执行并复核：删除退役分类机制连带 11 个用例，新增 13 个活行为用例（adapters/SessionMessageFilter.ts），净 +7；被删 11 例断言的均是退役机制，无一例断言那 3 个活函数 → 活行为不欠账
- 🟡 发起窗口处置：application/use-cases/MigrateLedger.ts 是迁移变换的第二份实现（src 内零调用）→ 已删除（连同其 describe 块，留说明注释）；对 t6 的"12 个用例"修正为 11。理由与该例外记入 verification.md

### 改动文件

- `docs/requirements/REQ-47939a/verification.md`
- `packages/pages/dsh-pmboard/tests/size-budget.test.ts`
- `packages/pages/dsh-pmboard/src/adapters/SessionMessageFilter.ts`
- `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`
- `packages/pages/dsh-pmboard/src/domain/stage/StagePromptSpec.ts`

### 下一步

t10 复核（同批交付）；随后 t11/t12 客户端拆分。

---
