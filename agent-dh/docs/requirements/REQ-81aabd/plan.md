---
req_id: REQ-81aabd
title: 拆分计划 · 需求流水线节点名称统一（设计/拆分）+ 设计文档建模
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# REQ-81aabd 拆分计划（plan.md）

> 本文档回答「做的步骤」。每步的**怎么做**在 `design/*.md`；需求全貌在 `requirement.md`。
> 实施落地时把步骤拆成任务卡（decomposing），任务卡再带 `requirement_refs` 回到需求条款。

## 0. 目标与做法（一句话）

把节点 3 的键 `planning` 与显示名「技术设计」一并改为 `design` /「设计」、`plan.md` 旧称「实施计划」
改为「拆分计划」，把 `design/*.md` 建模为 `design` 产物种类并在设计节点逐份显示 ✅ 已交 / ⬜ 未交，
存量台账由 v6→v7 一次性迁移归一——**只加呈现，不动任何闸门**。

## 1. 步骤（任务表）

| key | 步骤 | 阶段 | 端侧 | 依赖 | 验收（可证伪） |
|-----|------|------|------|------|----------------|
| t1 | 节点键改名 `planning` → `design`（状态机/协议/提示词分片/全仓字面量） | implement | fullstack | — | 包目录 `npx vitest run` 全绿；`grep -rn "planning" packages/pages/dsh-pmboard/src` 命中 0（`src/domain/legacy/LegacyStatus.ts` 别名表除外）；`node scripts/check-prompt-fragments.mjs` OK |
| t2 | 设计文档种类建模与旧条目回填 | implement | backend | — | `npx vitest run tests/sync-artifacts.test.ts tests/domain/artifact.test.ts` 全绿；需求台账中出现 `kind="design"`、`stage="design"` 的条目 |
| t3 | 设计节点逐份交付状态展示 | implement | frontend | t2 | `npx vitest run tests/stage-panel.test.ts tests/stage-detail.test.ts` 全绿；打开项目看板 → 设计节点 → 每份设计文档一行含 `data-design-doc` 与 ✅已交/⬜未交 |
| t4 | 台账 v6→v7 迁移脚本与实迁执行 | implement | backend | t1, t2 | `node --import tsx/esm scripts/migrate-ledger.ts --file .dsh-data/dsh-reqboard.json --dry-run` 退出码 0 且白名单外 diff 为 0；`--apply` 后 `--verify` 输出 0 问题项；`grep -c '"planning"' .dsh-data/dsh-reqboard.json` 仅剩正文措辞 |
| t5 | 文档同步、客户端重建与验收材料 | doc | doc | t1, t2, t3, t4 | `pnpm build:client && node scripts/verify-client-build.mjs` 输出 OK；`grep -c planning lib/client.js` 为 0；`docs/requirements/REQ-81aabd/{requirement.md,plan.md,design/*.md}` 可从看板打开 |

### 覆盖对照（serves）

| 需求条款 | 落点步骤 |
|----------|----------|
| FR-1 节点 3 键 `planning` → `design`、显示名「设计」 | t1 |
| FR-2 拆分计划 = `plan.md` | t1, t5 |
| FR-3 `design` kind + `design/*.md` 归位 | t2 |
| FR-4 设计节点逐份 已交/未交（不改门禁） | t3 |
| FR-5 旧 `notes` 条目回填 | t2 |
| FR-6 全仓旧名清理 + 客户端重建 | t1, t5 |
| FR-7 台账键名迁移（v6 → v7） | t4 |

## 2. 每步的实施要点（覆盖 design/*.md）

| 步骤 | 改哪些文件 | 怎么做 | 见设计 |
|------|-----------|--------|--------|
| t1 | `src/domain/requirement/RequirementStatus.ts`、`src/shared/protocol.ts`、`src/domain/prompt/fragments/design/**`（目录改名）、`src/domain/prompt/generated/fragments.ts`（重生成）、`scripts/inline-prompt-fragments.mjs`、`src/tools/**`、`src/client/*.ts`、`tests/**`、`tests/fixtures/stage-prompts-baseline.json`（键改名） | 键与字面量逐处替换；分片目录 `git mv planning design` 后重跑 `node scripts/inline-prompt-fragments.mjs`；`REQBOARD_SCHEMA_VERSION` 6→7 | design/interfaces.md §2、design/data-model.md §7 |
| t2 | `src/domain/artifact/ArtifactSpec.ts`、`src/adapters/ArtifactSync.ts`、`tests/domain/artifact.test.ts`、`tests/sync-artifacts.test.ts` | 加 `design` 种类与路径规则；同步时对 `autoDiscovered` 条目重算并回填 | design/data-model.md §1-4 |
| t3 | `src/application/internal/design-docs.ts`（新）、`src/application/query/QueryStageDetail.ts`、`src/shared/protocol.ts`、`src/client/stage-panel.ts` | 纯函数算出逐份状态 → 协议字段 → 面板渲染，带稳定 DOM 属性 | design/architecture.md §1、design/interfaces.md §3-4 |
| t4 | `src/domain/legacy/LegacyStatus.ts`、`scripts/migrate-ledger.ts`、`tests/migration.test.ts` | 别名表加 `planning → design`；新增 C11 回填 `artifacts[].stage`；白名单补数组下标分支；版本推进到 7 并实迁线上台账 | design/data-model.md §7、design/test-cases.md TC-13/14 |
| t5 | `packages/pages/dsh-pmboard/docs/stage-naming-final.md`、`docs/architecture/workflow-stages.md`、`docs/requirements/REQ-81aabd/**`、`lib/client.js`、`lib/client.cjs` | 文档同步 + 重建客户端 + 提交验收材料 | design/test-cases.md §1 |

## 3. 风险与回退

| 风险 | 处置 |
|------|------|
| 改名漏一处 → 看板与代码不一致 | t1 用 grep 全仓核验（不是"我记得改过"）；漏处补改，不改基线 |
| 客户端未重建 → 线上仍是旧渲染 | t5 跑 `node scripts/verify-client-build.mjs`，并 grep 旧名 0 命中 |
| `design` 被误加进必备产物 → 四类需求凭空多卡点 | 单测锁死（TC-2）；回归失败即回退该行 |
| 回填覆盖人工登记条目 | 回填仅限 `autoDiscovered === true`；单测 TC-5 锁死 |
| 提示词分片改了没重新内联 | t1 跑 `node scripts/inline-prompt-fragments.mjs` + `node scripts/check-prompt-fragments.mjs` |
| 迁移把正文历史措辞也改了 | 只归一状态类字段（status/statusHistory/artifacts[].stage），白名单外 diff 必须为 0；`--verify` 独立复核 |
| 老进程在迁移后又写回 `planning` | 迁移 `--apply` 与重启串行执行（先迁后启），重启在最后一步 |

## 4. 验收方式

按验收单逐项确认（`reqboard_submit(kind=verification)`），以命令输出与看板实际渲染为准；
不满足"照着重跑一遍能复现"的项一律不许通过。
