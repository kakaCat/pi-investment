# t-738238 复核记录（父卡 t-f8ed18「先定契约：挂起确认能标出「被中止」，判定口径只留一处」· 阶段 review）

- 复核时间：2026-09-27（本轮执行内）
- 复核环境：darwin-arm64 · vitest 1.6.1 · 工作目录 `/Users/yunpeng/pi-investment/agent-dh`
- 验收标准（本卡）：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据
- 复核对象（父卡交付面）：
  - `src/shared/protocol.ts` L958-962：`PendingConfirmation.interruptedAt?: number`
  - `src/application/ports.ts` L322-326：`PendingConfirmPort.markInterrupted(ticket)`
  - `src/adapters/PendingConfirmRegistry.ts` L94-109：`markInterrupted` + `expired` 单点
  - `src/application/internal/pending-guard.ts`（新增，L27-75）：共享谓词 / 过滤 / 常量 / 文案
  - `src/application/use-cases/ConfirmReceipt.ts` L29/L56/L101-126：改用共享谓词 + 中止文案
  - 契约测试 `tests/pending-guard.test.ts`（9 例）、联调 `tests/pending-guard-integration.test.ts`（7 例）
- 设计依据（比对基线）：
  - `design/data-model.md` T-1（L29-52）、T-2（L54-68）、T-3（L70-83）、约束（L85-93）
  - `design/interfaces.md` I-2（L77-89）、I-3（L91-114）、I-4（L116-136）、I-6（L146-151）
  - `design/architecture.md` L21/L55/L90-91/L114/L122-124/L134/L152
  - `design/use-cases.md` UC-3（L47-61）
  - `design/test-cases.md` TC-15（L40）
  - 父卡实施方案与「得到什么结果」：`tasks/t-f8ed18.md` L16/L19
- 复核方式：**只读复核 + 独立复跑 + 逐字比对**（不采信上游自述）：`git show HEAD` 取原私有谓词逐字对照、`git diff` 核对改动面、独立复跑验收与关联用例、`tsc --noEmit` 过滤本卡文件

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 数据模型 T-1 | data-model.md L40/L46-52 | `interruptedAt?: number` 新增可选；写首次；过期基准 = `interruptedAt ?? createdAt`，窗口 = `LIMITS.confirmEvidenceWindowMs` |
| 数据模型 T-3 | data-model.md L70-83 | `targetConfirmedInLedger` 从 `ConfirmReceipt.ts:76-80` **逐字提取、零行为变化**；守卫与回执共用 |
| 接口 I-4 | interfaces.md L116-136 | 端口 5 方法；`markInterrupted(ticket)` 只写首次、未知 ticket → undefined（不抛）；`get`/`pendingForWindow` 过期基准改为 `(interruptedAt ?? createdAt) + ttlMs` |
| 接口 I-3 | interfaces.md L91-114 | 守卫判定升级为「未作答 **且** 台账未落章才拦」；挂载点 4 条写路径；拒绝文案三要素 |
| 接口 I-6 | interfaces.md L146-151 | 回执键/错误码逐字不变；**仅当**记录带 `interruptedAt` 且尚未作答时 `note` 改中止文案 |
| 接口 I-2 | interfaces.md L77-89 | `blocked_tools` 常量 = 4 条写路径；`recovery` 含取回执 + 看板两条路径 |
| 单元口径 | test-cases.md L40（TC-15） | `markInterrupted` 两次幂等；过期基准 = `interruptedAt + ttl`，`createdAt` 早也不提前失效 |
| 父卡方案 | tasks/t-f8ed18.md L19 | 五步：协议字段 / 端口方法 / 注册表实现与过期基准 / 新增 pending-guard（谓词 + 过滤 + 常量 + 文案）/ 回执改用共享谓词与中止文案 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | `PendingConfirmation` 增可选 `interruptedAt?: number`（T-1 L40、父卡 L19①） | protocol.ts L962 逐字新增可选字段（L958-961 JSDoc，缺省=未中止；内存态，未碰持久化 schema） | **无偏离** |
| R2 | 端口增 `markInterrupted(ticket): PendingConfirmation \| undefined`，不抛（I-4 L124-125、父卡 L19②） | ports.ts L326 签名逐字一致 | **无偏离** |
| R3 | `markInterrupted` 幂等，只写首次（I-4 L134、T-1 L40） | registry L98-103 `if (found.interruptedAt === undefined) found.interruptedAt = this.now()`；单测 L69-78 锁定二次调用不变 | **无偏离** |
| R4 | 未知 ticket → undefined，不抛（I-4 L124） | registry L99-100 未命中即返回 undefined；单测 L64-67、联调 L192-195 | **无偏离** |
| R5 | `get` / `pendingForWindow` 过期基准改 `(interruptedAt ?? createdAt) + ttlMs`（I-4 L132、父卡 L19③） | registry L106-109 `expired()` 单点取 `record.interruptedAt ?? record.createdAt`，L72/L88 两处调用；单测 L80-92、联调③ L170-190 | **无偏离** |
| R6 | `targetConfirmedInLedger` 从 `ConfirmReceipt.ts:76-80` **逐字提取、零行为变化**（T-3 L70-83、父卡 L19④） | pending-guard.ts L46-50 三行函数体与 `git show HEAD` 原 `confirmedInLedger` **逐字一致**（plan→`approvedAt`；artifact→该 kind 成组 `confirmedAt`）；函数名按设计改为 `targetConfirmedInLedger` | **无偏离** |
| R7 | `ConfirmReceipt` 删私有谓词、改用共享谓词（父卡 L19⑤、T-3 L81） | ConfirmReceipt.ts 私有函数已删（`grep confirmedInLedger src/` 0 命中）；L56 改调 `targetConfirmedInLedger` | **无偏离** |
| R8 | `livePendingConfirm(deps, windowKey)` 滤已 settle/已过期/台账已落章（T-2 L67、父卡 L19④） | pending-guard.ts L58-65：settle/过期由 `pendingForWindow` 过滤，台账落章由共享谓词过滤；台账查不到需求时保守留挂（与 UC-3 异常流② L59 一致） | **无偏离** |
| R9 | `PENDING_CONFIRM_BLOCKED_TOOLS` = 4 条写路径（I-2 L64、I-3 L104-106） | pending-guard.ts L27-32 顺序/内容一致（submit/decompose/move/task_move） | **无偏离** |
| R10 | 恢复文案常量含「收到作答前不得产出下游产物」+ 取回执 + 看板（I-2 L65、I-3 L108-114） | pending-guard.ts L38-40 三锚点齐全；另含 L71-75 拒绝文案（architecture L114 归位到本文件）；单测 L115-127 | **无偏离** |
| R11 | I-6：`interruptedAt` 且尚未作答时 `note` 改中止文案；键/错误码不变 | ConfirmReceipt.ts L114-117 中止文案（含看板 + 重新发起 + 不得产出下游产物）；L61 传入 `rec.interruptedAt !== undefined`；返回体键未增删 | **主体无偏离**；组合态优先级见 §2 D-1 |
| R12 | 兼容：`PendingConfirmationOutcome` 4 键、回执键逐字不变（I-4 L136、I-6 L148） | ConfirmReceipt 返回体 L63-73 与 HEAD 同键；`ask-confirm-pending.test.ts` 11 例、`pending-guard.test.ts` 9 例全绿 | **无偏离** |

---

## 2. 偏离与观察项

**总判定：父卡交付面（5 文件 + 契约测试）对设计**无功能偏离**（R1–R12 全过，其中 R11 存在一处设计未裁定的组合态文案优先级，见 D-1）；下列 4 条均为不阻断项。**

### D-1（口径偏差 · 回执文案在「已落章」组合态下的优先级 · 不构成 FR 破坏）
设计 `interfaces.md` I-6 字面为「confirmed 以台账为准…**仅当**记录带 `interruptedAt` 且尚未作答时，`note` 改为中止文案」，`data-model.md` T-1 亦把「`outcome === undefined && interruptedAt !== undefined`」定义为「等待被中止」。
实现把两个 `confirmed` 分支置于中止分支之前（`ConfirmReceipt.ts` L108-117），故组合态「`interruptedAt` 已写 + `outcome` 未回填 + 台账已落章」返回「已确认…（以台账为准）」而非中止文案。该组合态可达：UC-3 步骤 4（L56）人在看板确认写 `confirmedAt`，注册表 `outcome` 仍为 `undefined`。
**结论**：不构成设计偏离的 FR 破坏——I-6 首句要求「confirmed 以台账为准」，且此态下已落章、不存在「丢掉等待」的静默态；联调测试 `pending-guard-integration.test.ts` L129-158 已按「台账优先」逐字钉死期望。**但设计文档未显式裁定该组合态的文案优先级**，建议在 I-6/T-1 补一句「台账已落章优先于中止文案」；本记录即为该口径的复核备注。不阻断验收。

### D-2（形状门禁未同步 · 计划归属 t5，但计划文字漏列该条 · 非 t1 实施偏离）
t1 新增 `PendingConfirmation.interruptedAt` 后，`tests/contract-shapes.test.ts` L93-101 的 PendingConfirmation **精确形状断言**（`expectTypeOf(...).toEqualTypeOf<{…没有 interruptedAt…}>`）产生 3 处 TS 报错中的 1 处（TS2344，`interruptedAt: "Expected: never, Actual: number"`）；另 2 处（L116、L123）是端口 4→5 方法断言。
拆分计划把 `contract-shapes.test.ts` 归 t5，但只写「PendingConfirmPort 形状断言更新为 5 方法」，**未提 L93 该条**。
**结论**：属计划归属的**已知延后**，t1 五文件 `tsc` 0 报错（§3.4），**非 t1 实施偏离**；但 t5 必须连同 L92-101 一并更新（加 `interruptedAt?: number`），否则该门禁（自述「把设计文档字段表逐字钉死」）与 `data-model.md` T-1 字段表不一致，建议 t5 验收补一条断言。

### O-1（端口注释泛化过头 · 非设计偏离）
`ports.ts` L306 与 `PendingConfirmRegistry.ts` L14 把注释放宽为「各方法都不抛：未知 ticket / 窗口不符 / 已过期一律返回 undefined」（原为「三个方法」），但 `markInterrupted`（registry L98-103）只查 `records` 是否有该 ticket，**不做过期检查**：对已过期 ticket 仍返回记录，且以其 `interruptedAt` 为基准「复活」一个完整 TTL。
设计 I-4 对 `markInterrupted` 只约定「未知 ticket → undefined（不抛）」，故**不构成设计偏离**；但注释与实现不一致，建议把注释限定到 `get`/`pendingForWindow`，或给 `markInterrupted` 补 `expired()` 判定。

### O-2（跨卡未收口 · 属 t3 范围 · 非 t1 偏离）
`src/application/internal/support.ts` L344-345 的 `assertNoPendingConfirm` 仍直接 `pendingForWindow`，未改用 `livePendingConfirm`；拆分计划 L65 明确该接线归 t3。故「判定口径只留一处」的**守卫侧**尚未闭合，属后续卡的正常未收口，**不构成 t1 偏离**。当前 src 中 `targetConfirmedInLedger` 只有一处定义（pending-guard.ts L46），无重复拷贝。

### O-3（并行工作线导致的红 · 与 t1 交付面无关）
本工作区同时存在其它工作线的改动（`AskConfirm.ts` / `MoveTask.ts` / `RunStatusTool.ts` 等）。`output-contract.test.ts` 4 例红（AdvanceTool/ClearPauseTool/RunStatusTool/TaskMoveTool）与 `ask-confirm.test.ts` 1 例红（t08 闸门问题卡）均落在 t1 交付面之外的文件/特性，非 t1 引入（§3.5）。

---

## 3. 复核证据（命令与输出）

### 3.1 父卡验收命令独立复跑（t-f8ed18.md L16）
```
$ cd /Users/yunpeng/pi-investment/agent-dh
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts
 ✓ packages/web/dsh-pmboard/tests/pending-guard.test.ts  (9 tests) 3ms
 Test Files  1 passed (1)
      Tests  9 passed (9)          # exit 0 —— 三项验收断言均覆盖
```
覆盖：`targetConfirmedInLedger` plan/artifact 成组（L46-61）、`markInterrupted` 幂等 + 未知 ticket（L64-78）、过期基准（L80-92）、`livePendingConfirm` 过滤（L95-113）、常量文案锚点（L115-127）。

### 3.2 联调（跨模块接缝）独立复跑
```
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts
 ✓ packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts  (7 tests) 66ms
 Test Files  1 passed (1)
      Tests  7 passed (7)          # exit 0
```
覆盖：adapter→回执中止文案（L89-111）、共享谓词 ↔ 台账落章（L129-158）、过期基准经真实工具返回码（L170-190）、端口 5 方法运行时形状（L198-204）。

### 3.3 关联回归（挂起/回执链路不退化）
```
$ node_modules/.bin/vitest run tests/ask-confirm-pending.test.ts \
    tests/confirm-pending-guard.test.ts tests/contract-shapes.test.ts
 ✓ ask-confirm-pending.test.ts  (11 tests) 269ms
 ✓ confirm-pending-guard.test.ts  (4 tests) 7ms
 ✓ contract-shapes.test.ts  (8 tests) 2ms     # 运行期绿；TS 报错见 3.4
 Test Files  3 passed (3) / Tests  23 passed (23)
```

### 3.4 类型面：本卡五文件 0 报错
```
$ node_modules/.bin/tsc --noEmit -p packages/web/dsh-pmboard/tsconfig.json 2>&1 | tee /tmp/tc-out.txt | wc -l
     171
$ grep -E 'pending-guard\.ts|PendingConfirmRegistry\.ts|ConfirmReceipt\.ts|protocol\.ts|application/ports\.ts' /tmp/tc-out.txt
（无输出）                        # t1 五文件命中 0 条
$ grep -E 'contract-shapes' /tmp/tc-out.txt
tests/contract-shapes.test.ts(93,55): TS2344  # PendingConfirmation 精确形状（见 D-2）
tests/contract-shapes.test.ts(116,11): TS2741 # 端口 5 方法
tests/contract-shapes.test.ts(123,60): TS2344 # 端口 5 方法
```

### 3.5 并发红项定位（与 t1 无关）
```
$ node_modules/.bin/vitest run tests/contract-shapes.test.ts tests/confirm-pending-guard.test.ts \
    tests/output-contract.test.ts tests/ask-confirm.test.ts tests/pending-guard-integration.test.ts
 ✓ contract-shapes.test.ts (8) ✓ confirm-pending-guard.test.ts (4) ✓ pending-guard-integration.test.ts (7)
 ❯ output-contract.test.ts (23 | 4 failed)   # defineAdvanceTool/ClearPauseTool/RunStatusTool/TaskMoveTool
 ❯ ask-confirm.test.ts (11 | 1 failed)       # t08 闸门问题卡（MoveTask 侧）
 Test Files  2 failed | 3 passed  /  Tests  5 failed | 48 passed
```
红项目标文件均不在父卡交付面（t1 仅 5 源文件 + pending-guard.test.ts）。

### 3.6 逐字提取核对（原私有谓词 vs 共享谓词）
```
$ git show HEAD:agent-dh/packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts | sed -n '70,85p'
function confirmedInLedger(req: RequirementRecord, rec: PendingConfirmation): boolean {
  if (rec.target === 'plan') return req.plan?.approvedAt !== undefined
  const arts = (req.artifacts ?? []).filter(a => a.kind === rec.kind)
  return arts.length > 0 && arts.every(a => a.confirmedAt !== undefined)
}
$ grep -n confirmedInLedger packages/web/dsh-pmboard/src -r
（无输出 → 私有拷贝已删，判定口径仅余 pending-guard.ts:46 一处）
```

---

## 4. 结论

- **父卡 t-f8ed18 设计与实现：无功能偏离。** R1–R12 全部满足设计基线（data-model T-1/T-2/T-3、interfaces I-2/I-3/I-4/I-6、architecture L114、use-cases UC-3、test-cases TC-15、父卡五步方案）：协议字段、端口方法、注册表幂等与过期基准、共享谓词逐字提取、守卫过滤与常量、回执中正文案均一致；无迁移、无 schema 变更。
- 唯一与设计**文本**不一致的是回执文案在「已落章」组合态下的优先级（**D-1**）：实现与联调测试按「台账优先」，I-6/T-1 未显式裁定 → 建议设计补一句，**不阻断**。
- **D-2** 为计划归属 t5 的形状门禁延后（t5 需补 contract-shapes L92-101 一条）；**O-1/O-2/O-3** 为无害注释/跨卡未收口/并发红项，均不构成 t1 偏离。

复核人：实施子代理（t-738238）；时间：2026-09-27
