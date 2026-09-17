# REQ-47939a 拆分 · 代码层面变更盘点 + 任务卡

> 阶段：decomposing · 上游：`requirement.md` + `plan.md` + `design/*.md`（4 份）
> 本文件回答：**新增**什么、**修改**什么（精确到模块/函数）、**删除**什么、怎么分工作流、多少工作量。

## 1. 新增（新增文件/接口）

| # | 新增 | 说明 |
|---|------|------|
| N1 | `src/domain/{errors,requirement/RequirementStatus,requirement/Requirement,task/TaskStatus,task/Task,task/Acceptability,workflow/RollupSpec,workflow/GateSpec,workflow/DoneEvidenceSpec,workflow/DecomposeSpec,workflow/AcceptanceSheetSpec,workflow/DocSyncSpec,workflow/MilestoneSpec,artifact/ArtifactSpec,stage/StagePromptSpec,ledger/LedgerV5}.ts`（≈16 个模块） | 纯领域规则，零 I/O |
| N2 | `src/application/ports.ts`（6 个端口）+ `src/application/use-cases/*.ts`（12 个用例）+ `src/application/query/*.ts`（3 个查询投影） | 用例编排，只依赖端口 |
| N3 | `src/adapters/{JsonLedgerRepository,FileDocRepository,SystemClock,RandomIdFactory,SessionProbeAdapter,UserQuestionsAdapter}.ts`（6 个） | 端口实现，I/O 唯一入口 |
| N4 | `src/tools/<9 个>/<Name>Tool.ts + prompt.ts + index.ts`（27 个文件） | 三段式工具壳 |
| N5 | `src/http/routers/{requirements,tasks,stages,verdicts,artifacts,triage}.ts`（6 个） | 按资源切分的路由 |
| N6 | `tests/domain/*.test.ts`（≈9 个）、`tests/application/*.test.ts`（≈6 个）、`tests/migration.test.ts`、`tests/layer-boundary.test.ts`、`tests/size-budget.test.ts`、`tests/fixtures/ledger-v4-sample.json` | L1/L2/L6/L7 测试 |
| N7 | `scripts/migrate-ledger.mjs`、`scripts/replay-req.mjs` | 迁移脚本 + A7 重放脚本 |
| N8 | `src/client/views/*.ts`（6 个）、`src/client/render/dom-utils.ts`、`src/client/styles/*.ts`（5 个） | P1 客户端分片 |
| N9 | 台账字段 `migrations: {from,to,at,by}[]`；`VerificationItem.source` 判别联合 | v5 数据结构（见 migration.md） |

## 2. 修改（精确到模块/函数）

| # | 文件 | 改什么 |
|---|------|--------|
| M1 | `src/shared/protocol.ts`（1,302 行） | 规则常量迁址 domain 后**再导出**（`REQ_TRANSITIONS`/`HUMAN_ONLY_*`/`TASK_TRANSITIONS`/`ARCHIVE_DOC_RULES`/`STAGE_ARTIFACT_REQUIREMENTS`/`ARTIFACT_CONFIRM_GATES`/`CATEGORY_FLOW_PROFILES`/`STAGE_PROMPTS`）；删除 `LEGACY_REQ_STATUS_ALIASES` 与其 5 处引用（`:104/1136/1166/1177/1183`）；删 `projectId`/`parentId`；`category`/`statusHistory` 转必填；`REQBOARD_SCHEMA_VERSION` → 5 |
| M2 | `src/host/routes.ts`（1,074 行） → `src/http/` | 删除 `:285/:347/:355` 的**重复状态校验**，改为调用例；HTTP 状态码映射集中到一处 |
| M3 | `src/host/store.ts` → `adapters/JsonLedgerRepository.ts` | 实现 `ReqboardRepository` 端口；删 `backfill*` 读时兜底（迁移后不再需要）；保留原子写与损坏隔离 |
| M4 | `src/host/capture-hook.ts` → `adapters/SessionProbeAdapter.ts` + `domain/workflow/MilestoneSpec.ts` | 会话事件订阅留适配层；提醒判定（30min）进 domain |
| M5 | `src/index.ts`（255 行） | 变为组合根：装配 adapters → use-cases → tools/http；工具注册从 13 项改 9 项 |
| M6 | `src/client/{api,board-mount,stage-panel,view,types,conversation-progress}.ts` | import 路径随分层调整；**DOM 结构与类名不变**；可从 `shared/protocol` 复用 domain 规则 |
| M7 | `docs/architecture/workflow-stages.md` | 阶段职责里的工具名同步（13→9） |
| M8 | `docs/rfcs/014-requirement-board.md` | 增补 §15 分层落地记录 |
| M9 | `docs/architecture/TOOLS_INVENTORY.md`、`docs/architecture/glossary.md` | 工具清单与术语更新 |

## 3. 删除

| # | 删除 | 依据 |
|---|------|------|
| D1 | `src/host/agent-tools.ts`（2,946 行） | 拆为 `tools/` + `application/` + `domain/`；搬完即删（禁止新旧并存） |
| D2 | `src/host/routes.ts`、`store.ts`、`rollup.ts`、`artifact-gates.ts`、`verdicts.ts`、`sync-artifacts.ts`、`capture-hook.ts`、`stage-prompts.ts`、`capture.ts`、`classifier.ts`、`session-sync.ts`、`stage-detail.ts`（`host/` 整目录） | 内容全部落到四层后删除 |
| D3 | `LEGACY_REQ_STATUS_ALIASES`（含 5 处引用） | 迁移后历史状态名已归一 |
| D4 | `backfillRequirementHistory` / `backfillTaskHistory` 的**读时调用**（函数本体保留给迁移脚本复用） | 迁移后 `statusHistory` 必填 |
| D5 | `RequirementRecord.projectId` / `parentId` | 全仓引用 0（实测） |
| D6 | `src/host/` 里被搬走的死代码分支（如 `routes.ts` 里为旧 triage 流程保留的旁路） | 拆分时逐一确认无引用后删（每删一处须在任务汇报里列出） |

## 4. 工作流划分与工作量预估

| 批次 | 任务 | 预估（会话批次/人时） |
|------|------|---------------------|
| B1 骨架与门禁 | t1 | 0.5 批 / 2h |
| B2 领域搬迁（可并行） | t2 · t3 · t4 | 3 批 / 12h |
| B3 适配器 | t5 | 1 批 / 4h |
| B4 用例与入口 | t6 · t7 · t8 | 3 批 / 14h |
| B5 收口与迁移 | t9 · t10 | 1.5 批 / 6h |
| B6 客户端 | t11 · t12 | 2 批 / 8h |
| B7 文档与归档 | t13 | 0.5 批 / 2h |
| **合计** | 13 个任务 | **≈11.5 批 / 48h** |

## 5. 任务卡（四要素：做什么 + 怎么做 + 怎么算完 + 依赖）

见 `reqboard_decompose` 落库结果（看板「任务」页与甘特图据此渲染）。每张卡的 `implementation` 写明改哪些文件/步骤/验证方式，`acceptance` 给出可机械判定的判据。

**依赖 DAG**：
```
t1 ─┬─ t2 ─┐
    ├─ t3 ─┼─ t6 ─┬─ t7 ─┐
    ├─ t4 ─┘       └─ t8 ─┴─ t9 ─┬─ t10 ─┐
    └─ t5 ────────────────────────┘        ├─ t13
                        t9 ─ t11 ─ t12 ────┘
```

## 6. 任务卡全文（落库稿件 · 13 张）

| key | 标题 | phase/side | 依赖 | 验收锚点（摘要） |
|-----|------|-----------|------|-----------------|
| t1 | 立层边界门禁与端口骨架 | implement/backend | — | `npx vitest run tests/layer-boundary.test.ts` 通过 + 扫描器命中下限断言 |
| t2 | 领域搬迁A：状态机+可证伪验收+产物规则 | implement/backend | t1 | `tests/domain` + `tests/reqboard.test.ts` 全绿；表驱动逐项断言 |
| t3 | 领域搬迁B：rollup+done凭证门+幂等+文档同步+里程碑 | implement/backend | t1 | `tests/domain` + `tests/rollup.test.ts` 全绿；freeze 入参不抛 |
| t4 | 领域搬迁C：验收单规约（生成/裁决/返工） | implement/backend | t1 | `tests/verification-sheet.test.ts` + `tests/verdicts-and-rework.test.ts` 全绿 |
| t5 | 适配器落地（仓储/文档/时钟/ID/会话/弹框） | implement/backend | t1 | `tests/application/repository.test.ts` 全绿；原子写断言 |
| t6 | 用例层落地（12 用例 + 3 查询投影） | implement/backend | t2,t3,t4,t5 | `tests/application` 全绿；测试内无 `mkdtempSync`（内存端口） |
| t7 | HTTP 路由改薄（删除重复状态校验） | implement/backend | t6 | 路由三件测试全绿；`src/http/routes.ts` 内 grep 无 `status === '` |
| t8 | 工具壳拆分与 13→9 收敛 | implement/backend | t6 | `tests/output-contract.test.ts` + `plugin-schema.smoke.test.ts` 通过；分派表驱动 |
| t9 | 旧文件删除 + 尺寸/边界门禁 + 全量回归 | implement/backend | t7,t8 | 全量绿；`src/host/agent-tools.ts` 不存在；单文件 ≤400 行 |
| t10 | 账本 v4→v5 无损迁移 | implement/backend | t9 | `--dry-run` 白名单外 diff=0；`migration-report.md` 含 34/84 复核行 |
| t11 | 客户端 view.ts 按视图区拆分 | implement/frontend | t9 | `tests/client-view.test.ts` 等三件全绿；6 个分片存在 |
| t12 | 客户端 styles.ts 分层 + 构建门 | implement/frontend | t11 | `pnpm build:client` + `verify-client-build.mjs` 通过 |
| t13 | 文档演进与死代码清理 + 归档材料 | doc/doc | t10,t12 | `wiki_probe.py` 无死链；两份文档内出现 9 个收敛后工具名 |

> 落库方式：`reqboard_decompose(tasks=[...])`（本需求计划不含任务表 → 路径 A「创作型」，decompose 即任务卡创作口）。每张卡的 `implementation` 已在落库载荷中写明改哪些文件/步骤/验证方式。
