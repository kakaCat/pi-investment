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
## 汇报 1（2026-09-17T11:44:29.360Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

t1 完成：立起可失败的层边界门禁与端口骨架——新增 domain 错误码表、application 六端口接口、层边界机械检查测试（9 用例全绿）。本任务未搬任何规则。

### 完成项

- src/domain/errors.ts：REQBOARD_ERROR_CODES（14 个领域语义码，对应 design/domain-model.md §7）+ domainError/hasErrorCode 构造与判定（纯数据+纯函数，零 import）
- src/application/ports.ts：六个端口接口（ReqboardRepository/DocRepository/Clock/IdFactory/SessionProbe/UserQuestionPort）+ LedgerView/MutableLedger/LedgerChange/UseCaseDeps，全部只 import type
- tests/layer-boundary.test.ts：9 个用例——依赖方向（domain/application/shared 三层逐条断言越界 import）、domain 禁 node:/Date.now/Math.random、tools|http 禁状态字面量比较、两条扫描器自检（≥20 文件 + extractImports 抽样）
- 故障注入实测（门禁必须能红）：注入 import node:fs 到 domain → 「domain/ 出现越界 import」红；注入 Date.now() 到 domain → 「domain/ 出现非确定性来源」红；两次还原后 9/9 绿
- 设计文档同步：architecture.md §2 表把 application 的允许项补上 `../shared/protocol.js`（仅 type）——t1 实现时发现需要用 shared 的现有台账类型，避免在 t1 就复制一份 entity 类型
- 全量回归：504 passed / 1 failed（失败项为本需求之前既存在的 tests/board-info-fixes.test.ts 验收态操作条，不归属本次改动）
- 客户端构建门：pnpm build:client + verify-client-build.mjs 哨兵通过（done 凭证门的构建新鲜度检查要求 packages/pages/*/src/** 改动必须伴随构建，本次为宿主层改动，仍按规则重建）

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/errors.ts`
- `packages/pages/dsh-pmboard/src/application/ports.ts`
- `packages/pages/dsh-pmboard/tests/layer-boundary.test.ts`
- `docs/requirements/REQ-47939a/design/architecture.md`
- `packages/pages/dsh-pmboard/lib/client.js`

### 下一步

t2/t3/t4（三块领域搬迁，均依赖 t1，可并行）；t2 先把 protocol.ts 的状态机表搬进 domain 并改为再导出。另记录一条待优化线索：done 凭证门的构建新鲜度检查对 packages/pages/<pkg>/src/** 一刀切，宿主层改动也要求重建客户端；t9 收口时可考虑细化为仅 src/client/** 触发。

---
