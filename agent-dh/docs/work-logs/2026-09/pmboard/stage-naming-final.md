# 需求流水线节点命名统一（最终口径）

> **性质**：命名规范说明（长期有效）。**唯一事实源**仍是 [docs/architecture/workflow-stages.md](../../../docs/architecture/workflow-stages.md)；
> 本文只解释「为什么是这些名字」与「旧名对应什么」，供人读与回溯。
>
> 本文出现的旧名（技术设计 / 实施计划 / `planning` 键）**只作历史对照**，代码与提示词里不得再使用。

## 1. 七个节点的中英文名

| 序 | 节点（中文） | 节点（英文 key / English） | 回答的问题 | 产出 |
|---|-------------|---------------------------|-----------|------|
| 1 | 立项 | `draft` / Intake | 做什么主题？ | 需求卡 |
| 2 | 需求分析 | `brainstorming` / Analysis | 这个主题要做什么？ | 需求文档 `requirement.md` |
| 3 | 设计 | `design` / Design | 怎么做？ | 设计文档 `design/*.md` |
| 4 | 拆分 | `decomposing` / Breakdown | 做的步骤是什么？ | 拆分计划 `plan.md` + 任务表 |
| 5 | 实施 | `implementing` / Implementation | 按步骤落地 | 代码、任务卡 `tasks/t-*.md` |
| 6 | 验收 | `accepting` / Acceptance | 文档所写是否都已按设计完成？ | 验收材料 + 验收单 |
| 7 | 归档 | `archived` / Archive | —— | 归档材料 |

另有历史状态 `done`（完成）与 `canceled`（取消），不属七个主节点。

## 2. 本次三处改名

| 对象 | 旧名 | 新名 | 理由 |
|------|------|------|------|
| 节点 3 键 | `planning` | **`design`** | 中文叫「设计」，英文键却叫 planning（计划）——中英两套语义；「拆分才是计划」，键名必须与中文一致 |
| 节点 3 中文 | 技术设计 | **设计** | 节点问的是「怎么做」，设计本身即含技术；「技术」二字冗余 |
| `plan.md` 产物 | 实施计划 | **拆分计划** | 该产物属于**拆分**节点（做的步骤），叫「实施计划」会与**实施**节点撞名 |

**为什么 `plan.md` 归「拆分」而不归「设计」**（用户口径）：

- 设计 = 怎么做（产出 `design/*.md`）；
- 拆分 = 把设计切成**步骤**（产出 `plan.md` + 任务表）；
- 实施 = 按步骤**落地**（产出任务卡与代码）。

所以「写计划」这件事发生在**拆分**节点；`design`（设计）节点只写设计文档。

**与代码闸门的时序（现状，2026-09-19）**：`plan.md` 语义上归**拆分**，但当前代码把它作为
**离开设计节点**的必备产物与人工确认门（`src/domain/artifact/ArtifactSpec.ts`：
`STAGE_ARTIFACT_REQUIREMENTS.design = ['plan']`、`ARTIFACT_CONFIRM_GATES['design>decomposing'] = 'plan'`）
——即"拆分计划在设计节点出口提交并确认，拆分节点据此落任务卡"。本次改名（REQ-81aabd）**不动任何闸门**；
要把 `plan.md` 的闸门位置真正挪到拆分节点，须另立需求。

## 3. 完整语义链（用户原话）

1. **立项** —— 做什么主题；
2. **需求分析** —— 这个主题做什么；
3. **设计** —— 怎么做；
4. **拆分** —— 做的步骤；但还需要仔细地把步骤拆分成**任务**去实施；
5. **实施** —— 落地步骤；
6. **验收** —— 按验收单确认，「按照之前文档写的内容都按照设计完成了」；
7. **归档** —— 归档文档、合并知识库。

## 4. 书写规范

**代码里**：键用英文，展示用中文，注释写「中文（英文）」。

```ts
design:      { label: '设计' }   // ✅ 设计（design）
decomposing: { label: '拆分' }   // ✅ 拆分（decomposing）
```

**文档里**：首次出现写「中文（英文 / English）」，此后可只用中文。

```markdown
✅ 设计阶段（design / Design）
✅ 拆分计划（plan.md）
```

## 5. 改名的落地范围

| 层 | 文件 | 状态 |
|----|------|------|
| 权威文档 | `docs/architecture/workflow-stages.md` | ✅ 已改 |
| 状态机 | `src/domain/requirement/RequirementStatus.ts`（含 `design` 键与迁移表） | ✅ 已改 |
| 旧名归一 | `src/domain/legacy/LegacyStatus.ts`（`reviewing→brainstorming`、`planning→design`；状态 + `statusHistory` + `artifacts[].stage`） | ✅ 已改 |
| 台账迁移 | `scripts/migrate-ledger.ts`（v6→v7，C11 回填 `artifacts[].stage`） | ✅ 已改 |
| 迁移编排 | `agent-dh/scripts/req81aabd-restart-and-migrate.sh`（停→迁移→起，见 §6 第 4 条的时序硬约束） | ✅ 已加 |
| 服务端契约 | `src/shared/protocol.ts`（`REQBOARD_SCHEMA_VERSION=7`）、`src/domain/artifact/ArtifactSpec.ts` | ✅ 已改 |
| 提示词分片 | `src/domain/prompt/fragments/design/**/*.md`（目录改名 + 重新生成 `generated/fragments.ts`） | ✅ 已改 |
| 工具描述 | `src/tools/{SubmitTool,DecomposeTool,AskConfirmTool,MoveTool}/` | ✅ 已改 |
| 界面文案 | `src/client/**`（含 `stage-panel.ts`、`views/artifacts.ts`、`styles/*` 的 `--pm-c-design`） | ✅ 已改 |
| 应用层文案 | `src/application/**`（门禁报错、评论、支撑文案） | ✅ 已改 |
| 本目录文档 | `docs/*.md` | ✅ 已改 |

> 旧名只在**历史记录**里保留：`docs/work-logs/**`、被测台账样本 `tests/fixtures/ledger-v4-sample.json`
> 与 P0 冻结提示词文本；运行时读路径**零兼容**，旧台账一律由迁移修好。

## 6. 修改流程（下次再改名）

1. 先改唯一事实源 `docs/architecture/workflow-stages.md`；
2. 再改 `RequirementStatus.ts` 的流水线注释与 `shared/protocol.ts` 的契约文案；
3. 全仓检索旧术语并替换（含 `fragments/**/*.md` 与 `.mjs` 脚本里的 `STAGES`/`VENDOR_MAIN_SKILLS`）；
4. 若是**键**改名：同步加 `LegacyStatus` 别名 + `migrate-ledger.ts` 新版本号（幂等、可 `--verify`），并跑一次 `--dry-run`；
   ⚠️ **`--apply` 必须在「进程已停、新进程未起」的窗口内执行**：台账仓储是 load-once + 每次写入全量重写、
   没有 reload API，进程活着时做外部迁移会在下一次 reqboard 写入时被内存旧快照静默覆盖（2026-09-19 实测复现）。
   现成编排：`bash agent-dh/scripts/req81aabd-restart-and-migrate.sh`（**detached** 运行，日志
   `.dsh-data/req81aabd-restart.log`）；
5. **重新生成**提示词分片：`node scripts/inline-prompt-fragments.mjs && node scripts/check-prompt-fragments.mjs`；
6. `pnpm typecheck` + `npx vitest run`；界面文案改动还要 `pnpm build:client && node scripts/verify-client-build.mjs` 再重启。

## 7. 禁止的做法

- ❌ 只改代码注释、不更新权威文档（形成两份真相）；
- ❌ 只改一部分文件（半通状态比没改更难查）；
- ❌ 手改 `src/domain/prompt/generated/fragments.ts`（生成产物，下次生成即被覆盖）；
- ❌ 继续使用「技术设计」「实施计划」「`planning`」指代节点 3；
- ❌ 只改中文名、不改英文键（中英两套语义正是本次要修的病）。

---

**生效时间**：2026-09-19
**用户裁定**：「拆分才是计划，技术设计就设计」；「planning = 设计，英文为什么不直接改成 Design」→ 键一并改为 `design`。
