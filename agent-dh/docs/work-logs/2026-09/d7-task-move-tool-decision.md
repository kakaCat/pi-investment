---
id: d7-task-move-tool-decision
title: D7 决策记录与需求草案：agent 侧任务流转工具缺失（选 B 改提示词）
summary: 实测 task_move/move 两工具未注册（改面 33 文件 75 处），选 B 需先答"是否放弃 agent 自主推进与 Dive 模式"，含影响清单、分步方案与验收标准。
type: worklog
status: living
updated: 2026-09-27
owners: [w-9f2c6c84]
tags: [reqboard, task-move, prompt, dive, decision, draft]
---

# D7 决策记录与需求草案：agent 侧任务流转工具缺失

> 本页是 **D1–D7 缺陷清单**中 D7 的展开（见同目录 `reqboard-decompose-flow-defects.md`）。
> 结论:**选 B（改提示词）不是一次轻档修正，而是产品方向的反转**——须立正式需求并由人先答一个前置问题。

## 一、问题

路由提示词/节点纪律要求「调 `reqboard_task_move(to=in_progress)` 取任务卡全文」，但：

- `src/tools/` 下**无 TaskMoveTool**；
- 实际注册的 15 个工具名中**既无 `reqboard_task_move` 也无 `reqboard_move`**；
- 但 `tests/apply-wiring.test.ts` 断言应注册 **15 个工具且期望集合含这两个名字** → 该测试**当前 4/4 失败**（缺口的直接证据）；
- 能力仅存在于 HTTP 层：`src/http/routers/tasks.ts:72 handleTaskMove` ← `src/http/routes.ts:235 POST .../task/move`（**看板 UI 走这条**）。

→ **agent 无法推进任何任务/需求状态**；本需求 14 卡停在 `todo` 即其后果；全仓 465 个任务的 agent 侧流转同样受影响。
→ 长期未暴露的原因：看板人工操作仍可用，"人点得动"掩盖了"agent 调不动"，且失败测试淹没在 193 个基线失败里。

## 二、两条路径

| | A · 补齐工具（**推荐**） | B · 改提示词（本草案） |
|---|---|---|
| 做法 | 新增 `src/tools/TaskMoveTool/`（+ `reqboard_move`），复用 `handleTaskMove` 校验逻辑 | 删除提示词中"调 task_move/move"的指引，改为"由人在看板操作"；同步改测试期望 |
| 改面 | 小（新增 2 工具 + 注册） | **大**：18 个 src 文件 45 处 + 15 个测试文件 30 处 |
| 与既定意图 | **一致** | **反转** |
| 代价 | 无 | 放弃 agent 自主推进 + **Dive 自动模式失效** |

### 为什么 B 是"反转"而非措辞修正

纪律文本源头 `src/application/internal/capture-section.ts:186`：

```
'状态推进纪律（计划批准之后，其余都由窗口自己维护，不需要用户手动点按钮）：',
'- 拆分后需求会自动进入拆分态；任务开工/完成用 reqboard_task_move 推进',
'- 任务全部 done 时系统自动把需求推进到 accepting（验收）；交付并自检通过后',
'  用 reqboard_move 自行推进到 done。',
```

**「不需要用户手动点按钮」是明写的设计意图。** 选 B 等于把它改成"任务状态一律由人点"。

## 三、影响面清单（实测）

**src（18 文件 / 45 处，按处数降序）**

```
7  src/application/internal/capture-section.ts      ← 纪律文本生成（提示词真身）
6  src/domain/workflow/DoneEvidenceSpec.ts          ← 完工凭证门
6  src/application/use-cases/AmendTaskAcceptance.ts ← 验收项修订通道
3  src/domain/prompt/generated/fragments.ts
3  src/application/internal/interruption.ts         ← 断点 pendingAction
2  src/tools/render-summaries.ts
2  src/client/toolviews/rows/task-move.ts           ← 看板工具视图
2  src/application/use-cases/SubmitVerification.ts  ← 报错里指引用 task_move 修订
2  src/application/use-cases/Decompose.ts
1  src/tools/ClearPauseTool/prompt.ts
1  src/domain/workflow/RollupSpec.ts
1  src/domain/legacy/LegacyStatus.ts
1  src/client/node-panel-process.ts
1  src/application/use-cases/SyncRequirementMarks.ts
1  src/application/use-cases/ConfirmArtifact.ts
1  src/application/query/QueryState.ts
1  src/application/internal/gate-feedback.ts
1  src/adapters/FailureAlert.ts
```

**tests（15 文件 / 30 处）**：`apply-wiring`(4) · `workflow-script-contract`(3) · `toolviews-contract`(3) ·
`interruption-checkpoint`(3) · `e2e/dive-full-flow`(3) · `capture-hook`(3) · `gate-feedback-envelope`(2) ·
`triad-gate` · `tools-status` · `tools-schema` · `stage-prompts` · `e2e-design-handoff` ·
`design-completeness-gate` · `decompose-tools` · `capture`（各 1）

### 选 B 的连带失效（必须一并处置）

| 关联能力 | 依赖点 | 后果 |
|---|---|---|
| **完工凭证门** | `DoneEvidenceSpec.ts`(6) | done 门依赖"task_move 汇报"作凭证 → 需重设计 |
| **验收项修订通道** | `AmendTaskAcceptance.ts`(6) + `SubmitVerification.ts` 报错文案 | "不可验证项"将**无法修订** |
| **Dive 自动模式** | `tests/e2e/dive-full-flow.test.ts`(3) 及 dive-* | 自动续跑 + 自动推进任务链**整体失效** |
| **看板工具视图** | `client/toolviews/rows/task-move.ts`、`node-panel-process.ts` | 渲染这些工具调用的 UI 成为死代码 |
| **断点续跑指引** | `interruption.ts`(3) | pendingAction 指向不存在的工具 |

## 四、前置决策点（须人先答）

> **问：我们是否放弃「agent 自主跑完需求链（含 Dive 自动模式）」这个能力？**

- **否** → 应选 **A**（补齐工具），与 capture-section 第 186 行既定意图一致，改面小。
- **是** → 走本草案 B，范围应含：33 文件提示词/文案改写 + 15 测试期望更新 +
  `DoneEvidenceSpec`/`AmendTaskAcceptance` 重设计 + 明确 **Dive 模式存废**。

## 五、B 的分步实施方案（若决策为"是"）

1. **决策与范围冻结**：明确 Dive 存废、完工凭证与验收修订的替代通道（人工看板？）
2. **提示词层**：改 `capture-section.ts` 纪律文本（"不需要用户手动点按钮" → "状态流转由人在看板操作"）；
   清 `fragments.ts` / `ClearPauseTool/prompt.ts` / `interruption.ts` 的指引
3. **领域层**：重设计 `DoneEvidenceSpec`（凭证来源改为看板操作留痕）与 `AmendTaskAcceptance`（替代修订通道）
4. **文案层**：`SubmitVerification`/`ConfirmArtifact`/`Decompose`/`FailureAlert`/`gate-feedback` 的错误与提示
5. **客户端**：移除/改造 `toolviews/rows/task-move.ts`、`node-panel-process.ts`
6. **测试**：更新上述 15 个测试文件的期望（`apply-wiring` 期望集合删两个名字并改长度断言；
   `stage-prompts` 的 implementing 期望移除 `reqboard_task_move`；`e2e/dive-full-flow` 按 Dive 存废调整）
7. **验证**：`tsc` 零新增错误 · 全量测试失败集合 ⊆ 基线 · `pnpm build` + 重启 + 看板人工跑通一次任务流转

## 六、验收标准（B）

- 提示词中不再出现"调 `reqboard_task_move`/`reqboard_move`"的指引；
- `apply-wiring.test.ts` 工具集合断言与其实际注册一致并通过；
- 看板人工完成一次「任务开工 → 完成」并产生与旧流程等价的留痕（执行时间 / 完工记录）；
- 若保留 Dive：另需明确其替代推进机制；若放弃：其测试与配置一并移除且无残留引用。

## 七、风险与回退

- **风险**：高（33 文件连锁 + 涉及 Dive 存废 + 完工凭证门语义变化）。
- **回退**：全部为提示词/文案/测试调整，无数据迁移；如决策反复，回滚代码即可，台账无副作用。
- **建议**：**先做 A**。A 与既有设计意图一致、改面小，且能立刻解开"agent 调不动任务"的死结；
  若日后确实要转为"人工流转"，那时再做 B，且 B 会小很多（因为 A 已把工具补回，B 只需决定是否暴露）。


## 八、补充核实：Dive 是否已接管状态管理？（2026-09-27 实测）

**结论：不支持。Dive 从未实际接管状态管理。**

### 8.1 Dive 的 armed 从未开启过

src/application/dive/session-driver.ts:23-24 原文：

    ⚠️ 不变量：以上任何一项都不得加 if (!armed) return。Dive 的语义是"armed 才自动推进"，
    而这些是"人点头后的必要收尾/交接/记录"；**全仓至今 0 个需求开过 armed**，
    一旦被门控，流水线立刻停摆。

→ Dive 自动模式处于"已实现但从未启用"状态。本需求亦为 autoRun=true 而 dive=null。

### 8.2 Dive 机制 = 编排器（驱动 agent），不自己改状态

| 检查 | 实测结果 |
|------|---------|
| Dive 内部是否调用 transitionRequirement | 否（grep 无命中）|
| Dive 内部是否推进任务状态 | 否 |
| Dive 的"下一动作"形态 | 告诉 agent 去调工具：idle-capture-actions.ts:64 → 请立即调 reqboard_ask_confirm(...) |
| Dive 核心动作 | session-driver.ts：阶段纪律提示词注入（onStagePrompt）+ 节点结算 + 里程碑催办 |
| stage-configs.ts 是否含状态流转 | 否 |

→ **Dive 依赖 agent 工具存在**；它不能替代缺失的 reqboard_move / reqboard_task_move。

### 8.3 因此 D7 的影响更严重（而非更轻）

Dive 路径同样走不通：即使开启 armed，它注入的指令仍是"去调那些不存在的工具"。
D1+D2+D7 三重叠加解释了需求的静默停滞：

    批准计划 → 委托 Dive 落库（D1）
      → 该需求 dive=null，全仓也没人开过（D2）
        → 即使启用，Dive 让 agent 去调 task_move/ move
          → 这两个工具未注册（D7）
    结果：台账 0 任务、DAG/泳道/覆盖度全空、零告警

### 8.4 决策问题需改写

原草案的前置问题应改为：

> **状态流转的执行者，是 Dive 本身，还是被 Dive 驱动的 agent？**

- 答「**agent**」→ 走 **A**：补回 reqboard_move / reqboard_task_move（复用 handleTaskMove）。
  改面小，且这正是让"Dive 编排"可行的前提。
- 答「**Dive 本身**」→ 需立正式需求做架构改动：Dive 从编排器变为执行者
  （在 round-driver/session-driver 内直接调 transitionRequirement 与任务流转），
  并重新定义它与五道人工门、与台账的关系。此为**方向性变更**，改面远大于 A 或 B。


## 九、修正：弹框通道覆盖到哪一层（2026-09-27 复核）

用户提出"弹框点击确认不就自动推进了吗"——**对一半**，且这条修正收窄了 D7 的严重性。

### 9.1 弹框确实原子自动推进（成立）

证据：本需求状态时间线全部 by=human，理由均为"确认弹框后自动推进（reqboard_ask_confirm）"。
实现：confirm-settle.ts —— 落章 + transitionRequirement 一个调用完成。

### 9.2 但弹框只覆盖「需求阶段 + 产物」，不覆盖「任务」

| 检查 | 实测 |
|------|------|
| ask_confirm 的 target 取值 | 只有 artifact / plan，**没有 task** |
| confirm-settle 调用的流转 | 只有需求级 transitionRequirement（第176/236行），不碰任务 |
| 任务状态状态机 | 独立一套 TASK_TRANSITIONS / assertTaskTransition |
| 任务状态变更入口 | 只有 HTTP：tasks.ts:72 handleTaskMove（看板按钮）——**无弹框形态** |

→ 14 张 todo 卡**点弹框推不动**；弹框只能推进需求阶段并落章产物。

### 9.3 由此暴露的新缺陷（D3 的另一表现）

**需求能在「0 任务」情况下从 draft 一路走到 implementing 乃至提交验收**，因为：

    需求阶段推进（弹框 / confirm-settle）  ←→  任务状态（独立状态机 + HTTP / 缺失工具）
                        两条通道互不校验

阶段推进**从不检查**该阶段任务是否已落库/已完成。这不只是"批准时不落库"（D1），
而是**整条阶段推进链都不校验任务侧完整性**（D3 的完整形态）。

### 9.4 严重性修正（自我更正）

| 通道 | 状态 | 受 D7 影响 |
|------|------|-----------|
| 需求阶段推进 | 弹框可用（已验证） | **否** |
| 任务状态推进 | 弹框做不到；agent 工具缺失；仅剩看板 HTTP | 是——影响 DAG / 泳道 / 实施覆盖度 / rollup 归口信号，**但不阻断需求走到验收** |

此前"agent 侧任务流转全断 → 影响整条流水线"的说法**夸大了**：D7 断的是任务级流转与质量信号，
**不是整条需求流水线**（需求阶段可纯靠弹框推进）。

### 9.5 修正后的结论

1. **需求能否交付**：弹框已够用（本需求验收材料已落章）。
2. **14 卡为何还要管**：它们承载 DAG / 泳道 / 实施覆盖度等可读质量信号。
3. **推进它们的最省路径**：**看板人工点**（走现成 handleTaskMove HTTP）——**零代码改动**。
4. **路径 A（补 agent 工具）的定位**：是"让 agent/Dive 能自主推进任务链"的**能力建设**，
   **不是本需求的交付前置**。
5. **真正该修的**：D3（阶段推进不校验任务完整性）。需求级收敛点的状态机校验已交付；
   业务前置条件校验仍未加。
