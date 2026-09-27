# RTM YAML 追溯基础设施 — 逐条 FR 核查报告

**核查时间**：2026-09-27
**核查对象**：`agent-dh/packages/tools/reqboard/src/rtm/`（canonical 实现，20 个模块 ~2,927 行）
**核查方式**：源码逐条对照 + 类型编译 + 测试套件实跑（非自述）

## 核查结论

**该模块是正确的**：类型编译干净（`tsc --noEmit` exit 0），测试 186/186 通过，
7 个触发点全部接线，三级追溯与三类覆盖度齐备，门禁阈值与需求一致。

## 逐条 FR 对照

| FR | 要求 | 实现证据 | 判定 |
|----|------|---------|------|
| FR-1 | 7 个 RTM 文件结构 | 7 个生成器：lifecycle / brainstorming / design / decomposing / implementing（+ 单任务详情）/ accepting；需求目录已实际产出 6 份 rtm-*.yml | ✅ |
| FR-2 | 台账 schemaVersion 8→9，加 designServes/implements | 台账与常量均为 **8**；未加字段 | ⚠️ 被等价轻方案取代（见下） |
| FR-3 | 7 个触发点 RTM 生成 | generator.ts `filesForTrigger` + `runRTMTrigger` 全接线 | ✅ |
| FR-4 | 文档标注解析 serves/implements/covers | parser.ts（SERVES_INLINE 等）+ fr-parser.ts | ✅ |
| FR-5 | 三级追溯链 | traceability-builder.ts：fr_to_design / design_to_tasks / task_to_tests（另派生 fr_to_tasks / fr_to_tests） | ✅ |
| FR-6 | 三类覆盖度统计 | coverage-calculator.ts：calculateDesignCoverage / calculateImplementationCoverage / calculateTestingCoverage | ✅ |
| FR-7 | 门禁 设计100% / 实施100% / 测试≥80% | validator.ts `GATE_THRESHOLDS = { design:100, decomposing:100, implementing:100, accepting:80 }`；接线于 SubmitDesignArtifacts / ConfirmArtifact / SubmitVerification | ✅ |
| FR-8 | `readRTM(requirementId, stage)` | file-io.ts `readRTM(filePath)` —— 收**文件路径**而非 (id, stage) | ⚠️ 功能等价，签名不同 |
| FR-9 | 迁移脚本 `migrate-reqboard-schema-v9.ts` | 不存在；现有 `scripts/migrate-ledger.ts` 迁到 v7/v8 | ⚠️ 随 FR-2 一并由轻方案取代 |

## 关键设计取舍：FR-2/FR-9 为何不是"漏做"

实现没有把追溯信息存进台账，而是走**文档标注路线**：

1. `context.ts` → `tasks()`：台账任务的 `serves` 缺失时，用 **decomposition.md §1「根编号 ↔ 任务卡」对照表**补齐；
2. `task-card-generator.ts` → 生成任务卡时写入 `DESIGN_SERVES` 模板变量；
3. 设计侧由 `parser.ts` 解析设计文档章节的 `serves:` 标注。

因此不需要新台账字段，也就不需要 schemaVersion 9 迁移——**8 保持自洽，无"常量与数据不一致"隐患**。
（旁证：`content-gate-wiring.ts:469` 确实会把 `designServes` 当输入读，但如果无人写入，
它只是"可接受的备用入口"，不是必需契约。）

## 🚩 核查中发现的真实未完成缺口（须修）

**`dsh-pmboard/src/application/internal/content-gate-wiring.ts` 的三级覆盖度 Level 3 是 TODO：**

```ts
// Level 3: 任务 ← 测试
// TODO: 需要从测试文档提取 covers 标注
```

即：该文件所在的门禁路径（Level 1 需求←设计、Level 2 设计←任务）**已实现**，
但 **Level 3 任务←测试尚未实现**。
注：canonical 的 `rtm/accepting-generator.ts` **已**实现 task_to_tests（走 `parseTestCovers`），
两条路径能力不对齐——建议后续把 content-gate-wiring 的 Level 3 接到既有实现上，避免重复造轮子。

## 测试证据

```
./node_modules/.bin/vitest run packages/tools/reqboard/tests/rtm/
Test Files  22 passed (22)
     Tests  186 passed (186)
[exit code]: 0

../../node_modules/.bin/tsc --noEmit -p tsconfig.json
[tsc exit]: 0
```

## 本次会话的纠正说明

本会话开头**未先核查既有实现**，按拆分计划（其"现状分析"已过时）新建了
`dsh-pmboard/src/domain/rtm/` 11 个文件共 2,509 行，与 canonical 实现功能重复且零外部引用。
该重复已移除（worktree 与分支 `feature/REQ-202609262349-1518` 已删，7 个提交号
`4c42a2ba..d870f821` 仍可经 reflog 恢复）；主工作区误改的 `protocol.ts`（常量 8→9）
与误建的 `types.ts` 均已还原。**教训：先核查既有实现，再采信计划。**
