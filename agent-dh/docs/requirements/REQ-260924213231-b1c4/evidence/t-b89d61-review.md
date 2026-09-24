# t-b89d61 复核记录（父卡 t-7b5e7a / T-9「实现断点常驻与续跑输入包」· 阶段 review）

- 复核时间：2026-09-25T≈01:2x+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 工作目录 `agent-dh` · HEAD `9e5ebf60`
- 复核对象（FR-6 / I-8 / T-1）：
  - 新增 `packages/web/dsh-pmboard/src/application/internal/interruption.ts`（`turnEndOutcome` / `nextActionFor` / `stampCheckpoint` / `stampInterruption`）
  - 新增 `packages/web/dsh-pmboard/src/application/use-cases/NoteInterruption.ts`（B′ 工具入口 + B 事件入口）
  - 新增 `packages/web/dsh-pmboard/src/tools/NoteInterruptionTool/`（三段式工具壳 + prompt）
  - 改 `src/adapters/CaptureHook.ts`（`onTurnFinished` 信号）、`src/application/internal/node-input-package.ts`（`## 断点` 节）
  - 改 `src/application/use-cases/{SubmitArtifact,MoveRequirement,Decompose,MoveTask,AcceptSheet}.ts` + `src/application/internal/confirm-settle.ts`（`stampCheckpoint`）、`src/index.ts`（异步边界 + 注册）
  - 测试 `packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts`
- 设计依据（比对基线）：`design/architecture.md` §「FR-6 断点留痕：实现细节」（L109-168）、`design/interfaces.md` §I-8（L21/L49-70）、`design/data-model.md` T-1（L30/L36-60）、`design/test-cases.md` TC-15/15b/16（L42-43/L67-79）、任务卡 `tasks/t-7b5e7a.md` 验收标准
- 复核方式：**只读复核**（不改任何实现/测试源码），逐点比对设计契约与实物 + 独立复跑父卡验收命令与相关回归 + `tsx` 运行时探针复现关键语义（不采信上游自述）

> 说明：依据本卡验收「对设计与实现的偏离逐条给出结论；无偏离时显式写明『无偏离』及依据」，§1 逐条给结论，§2 单列偏离项并标注性质与是否阻断。

---

## 1. 逐条复核结论（设计与实现）

| 编号 | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | I-8 工具契约：name=`reqboard_note_interruption`；`reason` 必填、`requirement_id` 可选；输出 `success` / `requirement_id` / `interruption{at,reason,stage,pendingAction,tool?}` / `note`（interfaces.md:21,49-54） | 三段式薄壳，字段/必填/输出 schema 逐一对齐；各 object 节点显式 `additionalProperties` | **无偏离**。依据：`NoteInterruptionTool.ts:17-57`、`prompt.ts:8-9`、`index.ts:406`；测试 L148-160 断言 name/required/schema 形状。 |
| R2 | `turnEndOutcome(data)` 值域：completed / max-tokens / blocked → 非异常；aborted → `aborted:<cause.kind>`；interrupted → `interrupted`；error → `error:<code>:<message>`（上游流超时落此）（architecture.md:127-131；data-model.md:46-56） | 逐值匹配；`aborted` 读 `reason.reason.kind`，与宿主 `TurnEndReasonMap`（dsh-session `types.d.ts:167-169`：`{kind:'aborted',reason:TurnEndCancelCause}`）一致；缺失 cause/error 字段回退 `unknown`/空串 | **无偏离**。依据：`interruption.ts:33-54`；运行时探针（§3.5）输出 `aborted:user`、`error:UPSTREAM_STREAM_IDLE:stream idle 3m`。 |
| R3 | 形态不认识 → 返回 `undefined`（不猜、不误报；A 的 checkpoint 仍在）（architecture.md:131；RISK-4） | `{}` / `undefined` / `null` / `{reason:{}}` / `{reason:'success'}` / `{reason:{kind:'weird'}}` 全部 → `undefined`，且不抛 | **无偏离**。依据：`interruption.ts:56-65`；测试 L94-101；探针 `turnEndOutcome({})=undefined`。 |
| R4 | `nextActionFor(req)` 是「弹框 / 输入包 / 断点**共用**的下一步命令唯一事实源」（interfaces.md:70） | 仅 `stampCheckpoint` / `stampInterruption` 调用它；`node-input-package` 的 `## 下一步` 仍取 `STAGE_CHAIN[stage].label`（静态链声明），`AskConfirm` 全未调用 | **偏离（口径，非功能缺陷）→ D-1**。依据：`grep nextActionFor` 仅 interruption.ts:110/124 两处调用；`node-input-package.ts:83`（`next: chain.label`）；`chain.ts:26-58`；探针显示两者取值不同（brainstorming：`reqboard_submit(kind=requirement)` vs `…reqboard_ask_confirm(target=artifact, kind=requirement)…`）。影响：`## 断点` 节的「未完成动作」确由 nextActionFor 产出（经 `bp.pendingAction` 带出输入包），但 `## 下一步` 与其非同源，「弹框共用」未落地。不阻断。 |
| R5 | `stampCheckpoint` 幂等：`stage` 与 `pendingAction` 都未变时不写、不 bump（architecture.md:135-136；protocol.ts:842） | 判定条件额外要求 `prev.reason === 'checkpoint'`；当上一条为异常原因且 stage/pending 未变时**仍重写**并返回 true | **偏离（轻微，行为可辩护）→ D-2**。依据：`interruption.ts:109-117`；探针 A：checkpoint(implementing,reqboard_task_run) → error 覆盖 → 同态再交棒 → `wrote=true` 且 reason 回到 `checkpoint`（设计字面应「不写」）。纯 checkpoint 路径幂等成立（探针 B：`wrote=false` 且内容逐字不变）。 |
| R6 | `stampInterruption`（写入器 B/B′）覆盖 `reason`、**保留** `pendingAction`（interfaces.md:61；architecture.md:137） | `reason` 覆盖 ✓；`pendingAction` 由 `nextActionFor(req)` 按**当前状态重算**（非字面保留旧值） | **偏离（字面口径）/ 实质等价 → D-3**。B 事件路径（turn/end）同回合状态未变 → 重算值 == 原值；B′ 工具迟调用时按当前态重算（`NoteInterruption.ts:11` 自陈）。依据：`interruption.ts:123-131`。 |
| R7 | 写入器 A 覆盖 6 个交棒用例（ask_confirm / move / submit / decompose / task_move / accept_sheet 各一行）（architecture.md:138-139） | `confirm-settle.ts:72/142/183/240`（ask_confirm）、`MoveRequirement.ts:140`、`SubmitArtifact.ts:136/279`、`Decompose.ts:381`、`MoveTask.ts:154`、`AcceptSheet.ts:115/214` | **无偏离（覆盖齐）**。注：任务卡实施方案写「`AskConfirm.ts`（stampCheckpoint）」，实际落在其抽出的 `internal/confirm-settle.ts`（AskConfirm 调 `applyConfirmDecision`/`recordDeclinedConfirmation`，见 `AskConfirm.ts:29,198,220`）；系文件级落点差异、等价实现，见 D-2b。 |
| R8 | 写入器 B 接缝：`CaptureHookDeps` 增 `onTurnFinished?(windowKey,outcome,session)`；turn/end 分支读 `evt.data` → `turnEndOutcome` → **只发信号**；组合根接异步边界；异常只 warn 不冒泡（architecture.md:141-145；interfaces.md:68） | `CaptureHook.ts:258-262` 计算 outcome 后仅回调信号（不写会话）；`index.ts:331-338` `if(!outcome.abnormal) return` + `setImmediate` + `.catch(logger.warn)`；`noteInterruptionForWindow` 空入参即返回、永不抛 | **无偏离**。依据：`CaptureHook.ts:255-263`、`index.ts:327-338`、`NoteInterruption.ts:102-115`；测试 L117-144、L139-144；`tests/capture-hook.test.ts` 26/26 绿。 |
| R9 | 写入器 B′：`reqboard_note_interruption(reason)` → 绑定窗口校验 + mutate + comment（architecture.md:146-147；I-8） | `requireLiveDriver` + `openRequirementsFor` 绑定校验 → `repo.mutate`（`stampInterruption` + `[断点]` 系统评论 + version/updatedAt）→ 回执；空 reason 抛 `REQBOARD_INVALID_INPUT`，无绑定需求抛 `REQBOARD_NO_BOUND_REQ` | **无偏离**。依据：`NoteInterruption.ts:33-100`；测试 L162-189。附加错误码 `REQBOARD_NOT_BOUND_TO_WINDOW`（显式 id 不属于本窗口）为只增键，见 O-3。 |
| R10 | 输入包在「未决问题」之后**条件追加** `## 断点`（仅当 `requirement.interruption` 存在），含阶段/未完成动作/原因/时间；老需求无字段 → 输出与改造前**逐字节一致**（architecture.md:148-150） | `projectLedger` 增 `breakpoint` 投影，无断点 = 空串；`buildNodeInputPackage` 仅非空时插入节（位于 `## 未决问题` 与 `## 下一步` 之间）；`breakpointText` 四要素齐 | **无偏离**。依据：`node-input-package.ts:93-106,140-142,162`；测试 L193-239（含 `build({...legacy,interruption:undefined})` 逐字节相等断言）。 |
| R11 | T-1 数据模型：字段 `at/reason/stage/pendingAction/tool?`；同一需求**单对象后写覆盖**，避免两份真相（data-model.md:36-60） | `protocol.ts:847-858` 字段一致；`buildInterruption` 整体替换单对象 | **无偏离**。依据：`interruption.ts:133-147`；测试 L182-189（后写覆盖）、L40-52。另 data-model.md 值域表内部不一致，见 D-4（文档级）。 |
| R12 | 分层规范：application 不 import `node:` / adapters（architecture.md:224；layer-boundary 门禁） | `interruption.ts` 零 I/O（仅 import shared/protocol）；`NoteInterruption.ts` 只 import application/internal + domain | **无偏离**。依据：两文件 import 清单；`tests/layer-boundary.test.ts` 红例仍**仅** `application/internal/diag-log.ts`（基线），新增文件未入越界清单。 |
| R13 | 尺寸规范：单文件 ≤400 行（architecture.md:225） | `Decompose.ts` 因 T-9 新增 1 行 `import` 由 HEAD 400 → 401（size-budget 白名单外）；`index.ts` 434 → 458 属分解计划 D-2 已登记的基线超标（T-12 负责） | **偏离（新增 1 个超标文件）→ D-5**。依据：size-budget 输出 `Decompose.ts = 401`、`index.ts = 458`；HEAD/工作区同法计数 400/401。 |
| R14 | 父卡验收 4 项：只交棒 → `reason==='checkpoint'` 且 pendingAction 非空；turn/end `error` → `error:UPSTREAM_STREAM_IDLE:…`；重建输入含 `## 断点` 与 pendingAction；老需求 → 逐字节不变（tasks/t-7b5e7a.md） | 4 项全部实测成立，目标文件 15/15 绿 | **无偏离**。依据：§3.1 独立复跑输出。 |

---

## 2. 偏离与观察项

**未发现阻塞性（行为）偏离**：父卡 4 项验收全部成立，FR-6 三层写入（A 常驻 checkpoint / B turn/end 补原因 / B′ 工具兜底）与输入包条件追加均按 architecture.md 的语义落地。以下 5 项均为轻微/文档级，逐项标注性质与是否阻断。

- **D-1（口径偏离，非功能缺陷，不阻断）· `nextActionFor` 未成为「弹框/输入包/断点」唯一事实源**
  - 出处：interfaces.md:70。实物：只有断点两函数用它；输入包 `## 下一步` 仍用 `STAGE_CHAIN[stage].label`，AskConfirm 未用（§1 R4）。
  - 影响：`## 断点` 节的「未完成动作」与 `## 下一步` 可能给出**不同命令**（探针：`reqboard_submit(kind=requirement)` vs `reqboard_ask_confirm(target=artifact, kind=requirement)`）。断点节自身自洽（值来自 nextActionFor），故不构成缺陷，但「唯一事实源」措辞与实际不符。
  - 建议（二选一，可不在本卡执行）：① 让输入包 `next` 走 `nextActionFor(requirement)` 收口；② 修正 interfaces.md:70 措辞为「断点与输入包断点节共用」。

- **D-2（轻微实现偏离，行为可辩护，不阻断）· `stampCheckpoint` 幂等多一个 `reason==='checkpoint'` 前置条件**
  - 出处：architecture.md:135-136 与 protocol.ts:842 均写「stage+pendingAction 未变则不写」。实物：`interruption.ts:112` 额外要求 `prev.reason==='checkpoint'`。
  - 实测差异：异常原因在案且同态再交棒时，实现会重写回 `checkpoint`（探针 A：`wrote=true`）；设计字面要求不写。
  - 评估：新交棒成功即意味已续跑，覆盖陈旧 error 原因可辩护；仅「异常原因被同态交棒刷掉」这一边界与字面不符。
  - 建议：在 `protocol.ts:842` / architecture.md 同步该边界（或去掉额外条件），二者取一。

- **D-2b（文件落点偏离，等价实现，不阻断）· ask_confirm 的 `stampCheckpoint` 落在 `internal/confirm-settle.ts` 而非 `AskConfirm.ts`**
  - 任务卡实施方案列 `AskConfirm.ts（stampCheckpoint）`；实物在 T-6 抽出的 `confirm-settle.ts`（唯一实现，AskConfirm 调用），覆盖同步确认 / 未确认留痕 / 推进 / 门合并四条路径。
  - 评估：行为等价且更符合「两份实现必漂移」的抽取动机（D-6），仅卡面文件清单滞后。

- **D-3（字面口径偏离，实质等价，不阻断）· 写入器 B/B′ 的 `pendingAction` 是「按当前态重算」而非「保留旧值」**
  - interfaces.md:61 写「保留 `pendingAction`」；实物 `interruption.ts:124` 用 `nextActionFor(req)` 重算。
  - 评估：B 事件路径同回合状态不变，重算值 == 旧值；B′ 迟调用按当前态重算更贴近「当前下一步」。建议同步文档措辞。

- **D-4（设计文档内部不一致，文档级，不阻断）· data-model.md T-1 值域表 `max-tokens`/`blocked` 行**
  - data-model.md:51-52 的「写进 `interruption.reason`」列填了 `max-tokens`/`blocked`，与同表「是否异常=否」及 architecture.md:159「completed/max-tokens/blocked → 不补写」自相矛盾。
  - 实物跟随 architecture.md/interfaces.md（组合根 `if(!outcome.abnormal) return` 不写）——实现自洽。建议把 data-model 该两格改为「（不补写）」。

- **D-5（新增超标文件，工程门禁，不阻断本次验收但建议本卡收尾）· `Decompose.ts` 401 行**
  - T-9 在 `Decompose.ts` 加 1 行 `import`，把 HEAD 的 400 行（恰在门禁口径上）顶到 401，成为 size-budget 白名单外超标文件。
  - 影响：size-budget 本已因基线 `index.ts` 红；即便 T-12 修完 `index.ts`，该门禁仍会因 `Decompose.ts=401` 保持红。T-9 属 1 行量级可自清。
  - 建议：把该 import 折进既有 import 行或删 1 行空白使 `Decompose.ts ≤ 400`；或由父卡补一张卡显式接收。

**观察项（无行为影响）**

- **O-1（测试质量）· 幂等「不写」路径未被直接断言**：`tests/interruption-checkpoint.test.ts:64-80` 标题为「同一 stage + 同一 pendingAction 再交棒不重写」，但用例做了 `draft→brainstorming→draft→brainstorming` 两次转移，实际断言的是「重写后 version 变大」，未覆盖 `stampCheckpoint` 返回 false 的不写路径。建议补一条「同态连调两次 → 第二次数值/时间戳不变」的断言（也与 D-2 的边界一并锁定）。
- **O-2（仓库卫生，非 T-9 产物）· `packages/web/dsh-pmboard/tmp-integrate-probe.ts` 遗留**：文件头写「联调探针（T-8 integrate）」，属 T-8 遗留的未跟踪临时文件（非 T-9 产物）；建议对应卡清理，避免混入提交。
- **O-3（契约只增）· `reqboard_note_interruption` 额外的 `REQBOARD_NOT_BOUND_TO_WINDOW`**：interfaces.md I-8 只列 `REQBOARD_INVALID_INPUT`（reason 空）；实物对「显式 `requirement_id` 不属本窗口」多抛一个码。新工具、纯只增，无兼容风险；可选在 I-8 补登。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（复跑）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/interruption-checkpoint.test.ts
```

```
 ✓ tests/interruption-checkpoint.test.ts (15 tests) 8ms
 Test Files  1 passed (1)
      Tests  15 passed (15)
```

判定：**15/15 通过，退出码 0** —— 覆盖父卡 4 项验收（checkpoint / turn-end error 覆盖 / `## 断点`+pendingAction / legacy 逐字节不变）。

### 3.2 接线与契约回归

```bash
npx vitest run tests/interruption-checkpoint.test.ts tests/tools-dispatch.test.ts tests/apply-wiring.test.ts tests/output-contract.test.ts
```

```
 ✓ tests/tools-dispatch.test.ts (4 tests) 5ms
 ✓ tests/interruption-checkpoint.test.ts (15 tests) 8ms
 ✓ tests/output-contract.test.ts (21 tests) 92ms
 ✓ tests/apply-wiring.test.ts (4 tests) 17ms
 Test Files  4 passed (4)
      Tests  44 passed (44)
```

- `tools-dispatch` 断言工具目录含 `NoteInterruptionTool`；`apply-wiring` 断言注册工具名含 `reqboard_note_interruption`（工具数 13→15）；`output-contract` 断言返回键已声明 —— **接线生效**。

### 3.3 被触碰文件回归

```bash
npx vitest run tests/capture-hook.test.ts tests/isolate-node-context.test.ts
```

```
 ✓ tests/capture-hook.test.ts (26 tests) 8ms
 ✓ tests/isolate-node-context.test.ts (29 tests) 24ms
 Test Files  2 passed (2)
      Tests  55 passed (55)
```

### 3.4 分层 / 尺寸门禁（2 红，均归因）

```bash
npx vitest run tests/layer-boundary.test.ts tests/size-budget.test.ts
```

- `layer-boundary`：唯一红例 `application/internal/diag-log.ts -> node:fs / node:path` —— **基线既有**（`diag-log.ts` 不在本需求改动清单），T-9 新增文件**未入越界清单**。
- `size-budget`：`application/use-cases/Decompose.ts = 401`（T-9 引入，见 D-5）、`index.ts = 458`（基线 D-2，T-12 负责）。
- HEAD/工作区同法计数：`Decompose.ts` = 400 / 401（`split('\n').length` 口径，与 size-budget.test.ts 一致）。

### 3.5 运行时探针（`npx tsx`，独立复现语义）

```
A after checkpoint: {"at":1000,"reason":"checkpoint","stage":"implementing","pendingAction":"reqboard_task_run","tool":"reqboard_task_move"}
A after error    : {"at":2000,"reason":"error:X:y","stage":"implementing","pendingAction":"reqboard_task_run","tool":"turn/end"}
A same-stage checkpoint rewrote? true {"at":3000,"reason":"checkpoint",...}        ← D-2 边界
B pure idempotent wrote? false unchanged? true                                    ← 纯 checkpoint 幂等成立
nextActionFor(brainstorming,no artifacts) = reqboard_submit(kind=requirement)
chain.label(brainstorming)                = 下一步：design —— 用 reqboard_ask_confirm(target=artifact, kind=requirement) 交棒…   ← D-1
turnEndOutcome({}) = undefined
turnEndOutcome(aborted) = {"abnormal":true,"reason":"aborted:user"}
```

### 3.6 类型检查（`npx tsc --noEmit -p tsconfig.json`）

- 合计 **24 条**错误；T-9 **新增文件 0 条**（`interruption.ts` / `NoteInterruption.ts` / `NoteInterruptionTool.ts` / `prompt.ts` 均无）。
- 命中 T-9 触碰文件的 2 条（`CaptureHook.ts:93`、`node-input-package.ts:204`，均为 `category: RequirementCategory|undefined`）不在 T-9 diff hunk 内、位于 HEAD 同文本处，**非 T-9 引入**；其余为 template/H3 基线与 T-6 测试（`ask-confirm-pending.test.ts:55`）。

---

## 4. 复核结论

1. **父卡 t-7b5e7a（T-9 / FR-6）验收全部成立**：只交棒写 `checkpoint`+pendingAction、`turn/end` 异常覆盖 reason、输入包条件追加 `## 断点`、老需求逐字节不变 —— 目标测试 15/15 绿，接线/契约/CaptureHook 回归 99/99 绿。
2. **无阻塞性实现偏离**：三层写入与输入包渲染与 architecture.md/interfaces.md/data-model.md 的契约逐条一致（R1-R3、R7-R12、R14 均「无偏离」并给出依据）。
3. **5 项非阻塞偏离**：D-1（`nextActionFor` 未成唯一事实源·口径）、D-2（checkpoint 幂等边界）、D-2b（ask_confirm 落点文件）、D-3（pendingAction 重算 vs 保留·字面）、D-5（`Decompose.ts` 401·工程门禁）；另有 1 项设计文档内部不一致 D-4 与 3 项观察项（O-1 幂等断言缺、O-2 T-8 遗留探针、O-3 附加错误码）。
4. **建议（不阻断父卡收尾）**：D-5 以 1 行修复随 T-9 收尾（或父卡补卡接收）；D-1/D-2/D-3/D-4 为文档/口径对齐项，可在收尾或后续维护中一并处理。
5. 本卡为 review 阶段：**未修改任何实现或测试源码**，本轮新增产物仅本文件。

---

> 复核人：实施子代理（t-b89d61）· 2026-09-25（本轮执行内）
