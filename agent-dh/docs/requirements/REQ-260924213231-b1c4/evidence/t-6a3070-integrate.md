# t-6a3070 联调记录（父卡 t-7b5e7a / T-9「实现断点常驻与续跑输入包」· 阶段 integrate）

- 联调时间：2026-09-25T01:12+0800
- 联调环境：node v22.23.2 · vitest/2.1.9 (darwin-arm64) · 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口 / 接缝，编号对齐 `design/interfaces.md`）：
  - **I-8** `reqboard_note_interruption(reason, requirement_id?)`（新工具，B′ 写入源）
    —— `src/tools/NoteInterruptionTool/NoteInterruptionTool.ts` + 用例 `src/application/use-cases/NoteInterruption.ts`
  - **I-8 内部接缝** `onTurnFinished?(windowKey, outcome, session)`（B 写入源信号）
    —— `src/adapters/CaptureHook.ts`（`turn/end` 分支，`interfaces.md:61` 记为 225-251，实现现为 233-263）
  - **I-8 纯函数** `turnEndOutcome(data)` / `nextActionFor(req)` / `stampCheckpoint`
    —— `src/application/internal/interruption.ts`（`design/interfaces.md:64-70`）
  - **FR-6 续跑输入包** `buildNodeInputPackage({requirement})` → `projection.breakpoint` →「## 断点」节
    —— `src/application/internal/node-input-package.ts`
  - **组合根接线** `src/index.ts`（异步边界 + 工具注册）
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回三者一致（**5/5 例 MATCH**）；
  目标测试 `tests/interruption-checkpoint.test.ts` **15/15 绿**；接线回归 `tools-dispatch` / `apply-wiring` 全绿。
  另有 2 项**非本卡验收范围**的观察项（size-budget 新增 1 个超标文件、language-layer 新增 1 红例），见 §5。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-t6a3070.test.ts`（跑完即删），对断点链各接口发真实调用，
逐字段打印「请求样例 / 期望响应 / 实际返回」并比较。全部走内存端口（`tests/application/harness`），不落盘。

### C1 — I-8 工具 `reqboard_note_interruption`（B′ 写入源，真实 `tool.execute`）

| 项 | 内容 |
|---|---|
| 请求样例 | `{ reason: 'upstream stream idle 3m ×5' }`（`exec = { agent: { id: 'session-w-001' } }`，窗口绑定需求 `REQ-000001` status=implementing） |
| 期望响应 | `{success:true, requirement_id:'REQ-000001', interruption:{at:1000000, reason:'upstream stream idle 3m ×5', stage:'implementing', pendingAction:'reqboard_task_run', tool:'reqboard_note_interruption'}, note:'已记断点：…（阶段 implementing，下一步 reqboard_task_run）'}` |
| 实际返回 | 与期望逐字段相同（`at` 由注入时钟给出） |
| 判定 | **一致（MATCH）** |

```
C1 REQUEST : {"reason":"upstream stream idle 3m ×5"}
C1 EXPECTED: {"success":true,"requirement_id":"REQ-000001","interruption":{"at":1000000,"reason":"upstream stream idle 3m ×5","stage":"implementing","pendingAction":"reqboard_task_run","tool":"reqboard_note_interruption"},"note":"已记断点：upstream stream idle 3m ×5（阶段 implementing，下一步 reqboard_task_run）"}
C1 ACTUAL  : {"success":true,"requirement_id":"REQ-000001","interruption":{"at":1000000,"reason":"upstream stream idle 3m ×5","stage":"implementing","pendingAction":"reqboard_task_run","tool":"reqboard_note_interruption"},"note":"已记断点：upstream stream idle 3m ×5（阶段 implementing，下一步 reqboard_task_run）"}
C1 VERDICT : MATCH
```

- 落库侧同验：台账 `requirements[0].interruption.reason === 'upstream stream idle 3m ×5'`，且 `comments` 出现 `[断点]` 系统评论（用例写 comment 契约成立）。

### C2 — I-8 工具错误路径（拒绝信封）

| 项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| reason 全空白 | `REQBOARD_INVALID_INPUT` | `REQBOARD_INVALID_INPUT` | **一致** |
| 本窗口无绑定需求 | `REQBOARD_NO_BOUND_REQ` | `REQBOARD_NO_BOUND_REQ` | **一致** |

```
C2 EXPECTED: {"emptyReason":"REQBOARD_INVALID_INPUT","unbound":"REQBOARD_NO_BOUND_REQ"}
C2 ACTUAL  : {"emptyReason":"REQBOARD_INVALID_INPUT","unbound":"REQBOARD_NO_BOUND_REQ"}
C2 VERDICT : MATCH
```

### C3 — 写入器 A → B 联调（交棒 checkpoint → `turn/end` 异常补新）

| 项 | 内容 |
|---|---|
| 请求样例（A） | `executeMoveRequirement(deps, {to:'brainstorming'}, exec)`（draft → brainstorming） |
| 期望（A） | 台账 `interruption={reason:'checkpoint', stage:'brainstorming', pendingAction:'reqboard_submit(kind=requirement)', tool:'reqboard_move'}` |
| 实际（A） | `{"at":1000000,"reason":"checkpoint","stage":"brainstorming","pendingAction":"reqboard_submit(kind=requirement)","tool":"reqboard_move"}` **一致（MATCH）** |
| 请求样例（B） | `CaptureHook` 喂 `{type:'turn/end', data:{turn:1, reason:{kind:'error', error:{code:'UPSTREAM_STREAM_IDLE', message:'stream idle 3m'}}}}` → 信号 `onTurnFinished` → 组合根异步边界 `noteInterruptionForWindow(deps, W, outcome.reason, 'turn/end')` |
| 期望（B） | 信号 `{wk:'session-w-001', abnormal:true, reason:'error:UPSTREAM_STREAM_IDLE:stream idle 3m'}`；台账 `reason` 覆盖为 error 原文，`stage`/`pendingAction` 按状态重算保持不变，`tool='turn/end'` |
| 实际（B） | `[{"wk":"session-w-001","abnormal":true,"reason":"error:UPSTREAM_STREAM_IDLE:stream idle 3m"}]`；`{"at":1000000,"reason":"error:UPSTREAM_STREAM_IDLE:stream idle 3m","stage":"brainstorming","pendingAction":"reqboard_submit(kind=requirement)","tool":"turn/end"}` |
| 判定 | **一致（MATCH）** |

```
C3 A-after-handoff: {"at":1000000,"reason":"checkpoint","stage":"brainstorming","pendingAction":"reqboard_submit(kind=requirement)","tool":"reqboard_move"}
C3 B-signal      : [{"wk":"session-w-001","abnormal":true,"reason":"error:UPSTREAM_STREAM_IDLE:stream idle 3m"}]
C3 EXPECTED      : {"reason":"error:UPSTREAM_STREAM_IDLE:stream idle 3m","stage":"brainstorming","pendingAction":"reqboard_submit(kind=requirement)","tool":"turn/end"}
C3 ACTUAL        : {"at":1000000,"reason":"error:UPSTREAM_STREAM_IDLE:stream idle 3m","stage":"brainstorming","pendingAction":"reqboard_submit(kind=requirement)","tool":"turn/end"}
C3 VERDICT       : MATCH
```

- 说明：A（checkpoint）是「死亡之前就已存在」的常驻断点；B 仅在 `abnormal=true` 时补新原因，非异常形态（completed/max-tokens/blocked）不发警告信号，畸形态（`{}` / `{reason:{}}`）`turnEndOutcome` 返回 `undefined` 不猜——与 `design/interfaces.md:68` 一致。

### C4 — FR-6 续跑输入包（有断点追加 / 老需求逐字节不变）

| 项 | 内容 |
|---|---|
| 请求样例（有断点） | `buildNodeInputPackage({stage:'brainstorming', requirement: <含 error 断点的台账记录>, requirementDoc:'# 需求文档\n', requirementDocPath})` |
| 期望响应 | 文本含 `## 断点` 且含 `- 当前阶段：brainstorming`、`- 未完成动作：reqboard_submit(kind=requirement)`、`- 中断原因：error:UPSTREAM_STREAM_IDLE…`、`- 记录时间：…`；断点节位于「## 未决问题」与「## 下一步」之间 |
| 实际返回 | `{containsBreakpointSection:true, containsPendingAction:true, containsReason:true}` |
| 判定 | **一致（MATCH）** |
| 请求样例（老需求） | 无 `interruption` 字段的 `RequirementRecord`（以及显式 `interruption:undefined`） |
| 期望响应 | 不出现 `## 断点`，输出与「键缺省」逐字节一致（`## 未决问题\n（无）\n\n## 下一步` 布局不变） |
| 实际返回 | 两者 `=== ` 相同字符串；`legacyText.includes('## 断点') === false` |
| 判定 | **一致（MATCH，byte-identical）** |

```
C4 EXPECTED: {"containsBreakpointSection":true,"containsPendingAction":true,"containsReason":true}
C4 ACTUAL  : {"containsBreakpointSection":true,"containsPendingAction":true,"containsReason":true}
C4 VERDICT : MATCH
C4-legacy EXPECTED(has 断点): false
C4-legacy ACTUAL (has 断点): false
C4-legacy VERDICT: MATCH(byte-identical)
```

### C5 — I-8 单对象语义（后写覆盖前写）

| 项 | 内容 |
|---|---|
| 请求样例 | 先 `noteInterruption({reason:'first'})`，时钟 +1000ms 后 `noteInterruption({reason:'second'})` |
| 期望响应 | 两次独立回执；台账始终只保留**一个** `interruption`，最终 `reason='second'` |
| 实际返回 | `{first:'first', second:'second', ledger:'second'}` |
| 判定 | **一致（MATCH）** |

### C6 — 探针执行结果

```
 ✓ tests/__probe-t6a3070.test.ts (5 tests) 6ms
 Test Files  1 passed (1)
      Tests  5 passed (5)
```

## 2. 目标命令与输出摘要

### 2.1 目标回归（T-9 验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/interruption-checkpoint.test.ts
```

```
 ✓ tests/interruption-checkpoint.test.ts (15 tests) 8ms
 Test Files  1 passed (1)
      Tests  15 passed (15)
```

- 期望：全绿（`reason==='checkpoint'` 且 pendingAction 非空 / `turn/end error` 覆盖 / 输入包含 `## 断点` / 老需求逐字节不变 / 畸形态不误报）
- 实际：15/15 通过，退出码 0 —— 与期望一致

### 2.2 接线与注册回归

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/interruption-checkpoint.test.ts tests/tools-dispatch.test.ts tests/apply-wiring.test.ts
```

```
 ✓ tests/apply-wiring.test.ts (4 tests) 17ms
 Test Files  3 passed (3)
      Tests  23 passed (23)
```

- `tools-dispatch`（`tests/tools-dispatch.test.ts:22-25`）断言三段式工具清单含 `NoteInterruptionTool`；
- `apply-wiring`（`tests/apply-wiring.test.ts:99`）断言 `apply()` 后注册的工具名含 `reqboard_note_interruption`
  （对应 `src/index.ts:406` 的 `toolsCtx.tools.register(defineNoteInterruptionTool(useCaseDeps))`）——**接线生效**。

### 2.3 组合根接线点位核对（`src/index.ts`)

| 接线 | 位置 | 内容 |
|---|---|---|
| B 信号 → 异步边界 | `src/index.ts:331-338` | `onTurnFinished: (windowKey, outcome) => { if (!outcome.abnormal) return; setImmediate(() => { void noteInterruptionForWindow(...).catch(...) }) }`（D-17：监听器内不写台账） |
| 工具注册 | `src/index.ts:406` | `defineNoteInterruptionTool(useCaseDeps)` |
| 工具清单文案 | `src/index.ts:410` | 提示词工具枚举含 `reqboard_note_interruption` |
| 工具导出 | `src/tools/index.ts:25` | `defineNoteInterruptionTool, NOTE_INTERRUPTION_PROMPT` |
| 输出契约登记 | `tests/output-contract.test.ts:341-342` | `NoteInterruption: ['application/use-cases/NoteInterruption.ts']` |

### 2.4 全量回归（对照分解计划「基线缺口」表）

```bash
cd packages/web/dsh-pmboard
npx vitest run
```

```
 Test Files  7 failed | 149 passed (156)
      Tests  8 failed | 1843 passed (1851)
```

失败文件（7）与例数（8）：

| 失败文件 | 例数 | 是否基线（`decomposition.md` §基线缺口） |
|---|---|---|
| `tests/client-view.test.ts` | 1 | 是（基线） |
| `tests/template-address-injection.test.ts` | 2 | 是（基线） |
| `tests/layer-boundary.test.ts` | 1 | 是（基线） |
| `tests/application/repository.test.ts` | 1 | 是（基线） |
| `tests/size-budget.test.ts` | 1 | 是（基线红；但红例内**新增 1 个超标文件**，见 §5-O1） |
| `tests/language-layer.test.ts` | 1 | **否**（新增，非 T-9 范围，见 §5-O2） |
| `tests/typecheck.test.ts` | 1（24 条错误） | 是（基线红，基线 23 条） |
| `tests/design-completeness-gate.test.ts` | 0 | 基线 2 红 → **已转绿**（T-5 修复生效） |

- 基线：`7 failed | 140 passed (147)`、`Tests 9 failed | 1761 passed (1770)`；本卡实测 `7 failed | 149 passed (156)`、`Tests 8 failed | 1843 passed (1851)`。
- **失败测试数 9 → 8**（design-completeness-gate 2 例转绿），失败**文件数持平**（design-completeness-gate 出列、language-layer 入列）。
- `.ts` 源码 24 条类型错误中：本卡新增三文件（`interruption.ts` / `NoteInterruption.ts` / `NoteInterruptionTool.ts`+ `prompt.ts`）**0 报错**；T-9 触碰文件里出现的 2 条
  （`src/adapters/CaptureHook.ts:93`、`src/application/internal/node-input-package.ts:204`，均为 `category: RequirementCategory|undefined`）
  在 `HEAD` 同位置已存在（`git show HEAD:…CaptureHook.ts` 第 92 行同文本；`node-input-package.ts` 的 address 段未被 T-9 改动）——**非本卡引入**。

## 3. 分层与兼容核验

- `tests/layer-boundary.test.ts` 仍只红在存量 `application/internal/diag-log.ts`（`node:fs`/`node:path`）——本卡新增的
  `application/internal/interruption.ts` 与 `application/use-cases/NoteInterruption.ts` **未出现在越界清单**（application 层零 `node:`/adapters 依赖）。
- 老需求兼容：C4 实测 `interruption` 缺省与显式 `undefined` 两种输入产出**逐字节相同**，且不追加 `## 断点` 节（`node-input-package.ts:141-142,162` 的条件追加成立）。
- 事件路径容错：`noteInterruptionForWindow` 在「窗口无绑定需求 / 空 reason / 空窗口」三种情况返回 `undefined` 且**不抛**（`tests/interruption-checkpoint.test.ts:139-144` 绿），事件路径不会打断流水线。

## 4. 联调结论

1. I-8 工具 `reqboard_note_interruption`、事件接缝 `onTurnFinished`、纯函数 `turnEndOutcome/nextActionFor/stampCheckpoint`、FR-6 输入包「## 断点」节——
   **请求样例 → 期望响应 → 实际返回三方一致（5/5 MATCH）**，且工具错误路径（空 reason / 无绑定需求）拒绝码与设计一致。
2. 写入器 A（交棒 checkpoint，常驻）与写入器 B（`turn/end` 异常补新）、B′（工具显式补写）三层语义成立；
   台账单对象、后写覆盖前写；`pendingAction` 与 `nextActionFor` 同源。
3. 续跑输入包在「有断点」时带出阶段/未完成动作/原因/时间四要素，在「老需求」时输出逐字节不变（零回归）。
4. 接线生效：`src/index.ts:331-338` 异步边界 + `:406` 工具注册；`tools-dispatch` / `apply-wiring` 断言通过。
5. 目标命令 `tests/interruption-checkpoint.test.ts` **15/15 绿**；全量回归失败测试数 9 → 8，无本卡引入的失败。

## 5. 观察项（非本卡验收范围，供父卡/复核决策）

### O-1 · `size-budget` 红例内**新增** 1 个白名单外超标文件：`application/use-cases/Decompose.ts = 401 行`

```
npx vitest run tests/size-budget.test.ts
 ❯ tests/size-budget.test.ts (5 tests | 1 failed)
   - Array [ { "lines": 401, "path": "application/use-cases/Decompose.ts" },
             { "lines": 458, "path": "index.ts" } ]
```

- `index.ts`（HEAD 434 → 现 458）是分解计划 D-2/T-12 已登记的基线超标项，由 T-12 修绿；`Decompose.ts` **不是**（T-12 落点为 `index.ts` / `plugin-config.ts` / `wiring/pm-capture-root.ts`）。
- 归因：`git diff` 显示 T-9 在 `Decompose.ts` 只加了 1 行 `import { stampCheckpoint } from '../internal/interruption.js'`（调用行与 `return` 合并，净 0）——HEAD 恰为 400 行（门禁口径），`+1` 即越界（`HEAD=400 → WORKTREE=401`，用与 `size-budget.test.ts` 相同的计数口径复核）。
- 影响：`size-budget` 本已是基线红，本卡未改变其「1 红例」的通过态；但 T-12 修完 `index.ts` 后，该门禁**仍会因 `Decompose.ts=401` 保持红**。
- 建议（父卡 T-9 范围内、1 行量级，本卡为 integrate 未代改）：把该 `import` 折进既有 import 或删 1 行空白使 `Decompose.ts ≤ 400`；或由父卡补一张卡接收。

### O-2 · `tests/language-layer.test.ts` 新增 1 红例（非 T-9 引入）

```
❯ tests/language-layer.test.ts (7 tests | 1 failed)
  tests/language-layer.test.ts:62  expect(s).toContain('每节必须标注服务哪条功能点')
```

- 归因：该断言依赖 `domain/prompt/fragments/design/light/overrides.md` 的原文；T-8（FR-5 提示词改写）把
  「覆盖 1 · 每节必须标注服务哪条功能点」改写为「覆盖 2 · 每节标注服务哪条功能点」，短语不再逐字命中。
- 与本卡（T-9）无关（`git diff` 未触碰 `domain/prompt/**` 与 `language-layer.test.ts`），记录以便 T-8 或其复核卡对齐断言。

---

> 本卡为 integrate 阶段：只执行上述目标命令与临时探针并落本记录，**未修改任何实现或测试源码**。
> 临时探针 `tests/__probe-t6a3070.test.ts` 与计数脚本已在本轮内删除（`rm -f`；`glob **/__probe-t6a3070*` 返回 `[]`，复核不存在）。
> 本轮新增产物：本文件（`docs/requirements/REQ-260924213231-b1c4/evidence/t-6a3070-integrate.md`）。
