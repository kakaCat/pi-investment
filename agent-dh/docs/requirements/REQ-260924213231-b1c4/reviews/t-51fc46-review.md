# t-51fc46 复核记录（父卡 t-5f2a65 / T-6「弹框改非阻塞投递并加回执工具」· 阶段 review）

- 复核时间：2026-09-25T00:47+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 复核对象（FR-3 / I-3 / I-4 / T-4；父卡验收 = ask-confirm 两文件全绿）：
  - `src/domain/limits.ts`（新增 `confirmInlineGraceMs = 30_000`）
  - `src/adapters/PendingConfirmRegistry.ts`（新增，`PendingConfirmPort` 唯一实现）
  - `src/application/use-cases/ConfirmReceipt.ts`（新增，回执用例）
  - `src/tools/ConfirmReceiptTool/{ConfirmReceiptTool,index,prompt}.ts`（新增工具壳）
  - `src/application/use-cases/AskConfirm.ts`（宽限赛跑 / 挂起 / 后台落章接线）
  - `src/application/internal/pending-confirm.ts` + `src/application/internal/confirm-settle.ts`（**计划外**新增的两个内部模块）
  - `src/index.ts`（`PendingConfirmRegistry` 装配 + `defineConfirmReceiptTool` 注册）
  - `tests/ask-confirm-pending.test.ts`（新增，TC-5/6/7/8/20 + 兼容性例）
- 设计依据（比对基线）：`requirement.md` FR-3；`design/architecture.md` L32-35 / L78-88 / L92 / L102 / L238；`design/interfaces.md` I-3/I-4 + E-3/E-4/E-5；`design/data-model.md` T-4（L33/L62-72/L81-82）；`design/use-cases.md` UC-3；`design/test-cases.md` TC-5/6/7/8/20 + 落点表；`decomposition.md` D-1/D-5/D-6 + T-6 验收行；任务卡 `tasks/t-5f2a65.md`
- 复核方式：**只读复核 + 独立复跑**（不采信上游自述）：逐条比对设计契约、对照 HEAD 版本 diff、独立运行父卡验收命令与相关回归、另写一次性探针验证 4 个契约点（跑完即删）

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 | `requirement.md` FR-3 | 人在环确认的等待不占用调用方预算（异步投递 + 回执），不再出现 120s 判定失败 |
| 架构 | `architecture.md` L102 | `questions.ask` 与宽限计时器**赛跑**：宽限内=旧语义；超宽限=登记 ticket 立即返回，并在 `.then()` 后台落章/推进/唤醒；回执按 ticket 查 |
| 架构 | `architecture.md` L83-87 | 超宽限返回 `pending+ticket`（**不判失败**）→（后台）作答到达 → 落章+推进+唤醒 → 回执 `confirmed=true, advanced=true` |
| 接口 | `interfaces.md` I-3 | 入参既有 + `inline_grace_ms?`（缺省取配置）；出参既有 + `pending?`/`ticket?`；**宽限内作答与原语义逐字一致**；错误 E-3/E-4 不变 |
| 接口 | `interfaces.md` I-4 | `reqboard_confirm_receipt(ticket)` → `success/confirmed/advanced/from/to/requirement_id/note`；`confirmed` **以台账为准** |
| 接口 | `interfaces.md` E-5 | 未知/过期 ticket → `REQBOARD_UNKNOWN_TICKET`，引导改读 `reqboard_status.design_docs[].confirmed` |
| 数据模型 | `data-model.md` T-4 | `ticket`(pc- 前缀)/`windowKey`/`requirementId`/`target`/`kind?`/`createdAt`(超 `confirmEvidenceWindowMs` 过期)/`outcome?`；ticket 唯一、窗口绑定 |
| 计划 | `decomposition.md` D-5/D-6 | 不改宿主 schema、不抬调用方预算；宽限内逐字一致；`AskConfirm` 保持 ≤400 行（抽取保持单点实现） |
| 计划 | `decomposition.md` D-1 | 基线红已知；本次只保证「不新增失败」；typecheck 口径 = 错误数 ≤ 基线 23 且**新增文件 0 报错** |
| 任务卡 | `tasks/t-5f2a65.md` 得到什么结果 | 两文件全绿；永不 resolve + 宽限 20ms → `pending=true`+ticket 非空不抛；作答后回执 `confirmed=true, advanced=true` 且台账 confirmedAt 已写 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | FR-3：人在环等待不再被调用方预算掐断 | `raceAsk()` 让 `questions.ask` 与宽限计时器赛跑，超宽限**立即返回**（不再 await 到宿主/调用方超时）；返回体 `pending=true` | **无偏离**。依据：`internal/pending-confirm.ts:48-58,81-117`、`use-cases/AskConfirm.ts:153-158` |
| R2 | `architecture.md` L102 / L83-84：超宽限 = 登记 ticket + `pending=true`（不判失败） | `suspendConfirm` 先 `port.register()` 拿 ticket，再返回 `{success:true, confirmed:false, advanced:false, pending:true, ticket, requirement_id, note}`；**未抛错、未判失败** | **无偏离**。依据：`internal/pending-confirm.ts:87-116`；`tests/ask-confirm-pending.test.ts` TC-5（永不 resolve + 20ms → pending/ticket/不抛/台账未改） |
| R3 | I-3：宽限内作答与原阻塞语义**逐字一致**（兼容性矩阵） | 宽限内分支直接调 `settleAnswers`；与 HEAD 的落章/推进/返回体逐字对照一致（`from`/`to`/`note` 拼接同源；落章写 `confirmedVia='session'`） | **无偏离**。依据：`AskConfirm.ts:156`；对照 `git show HEAD:.../AskConfirm.ts` 的对应块；测试 TC-6（`pending`/`ticket` 均 `undefined`，字段与旧一致）；`ask-confirm.test.ts` 11/11 绿 |
| R4 | I-3：`inline_grace_ms?` 缺省取配置；非法不静默回落 | 合法正数才生效，否则 `REQBOARD_INVALID_INPUT`；缺省取 `LIMITS.confirmInlineGraceMs` | **无偏离**。依据：`AskConfirm.ts:67-71,154`、`domain/limits.ts:41`（30s，显著小于 120s）；测试「非法 → REQBOARD_INVALID_INPUT」 |
| R5 | I-3：出参只增 `pending?`/`ticket?`，既有键不动 | `pending`/`ticket` 已在 `AskConfirmTool` 输出 schema 声明；既有键未改 | **无偏离**。依据：`tools/AskConfirmTool/AskConfirmTool.ts:59-60`；`output-contract.test.ts` 20/20 绿、`tools-schema.test.ts` 3/3 绿 |
| R6 | I-4：新工具 `reqboard_confirm_receipt(ticket)` 字段集 | 工具壳 schema + 用例返回 `success/confirmed/advanced/from/to/requirement_id/note`（另可选 `user_choice/user_feedback`，由 UC-3 异常流③ 指定） | **无偏离**。依据：`tools/ConfirmReceiptTool/ConfirmReceiptTool.ts:28-43`、`use-cases/ConfirmReceipt.ts:62-72`；`apply-wiring.test.ts` 断言注册名 |
| R7 | E-5：未知/跨窗口/过期 → `REQBOARD_UNKNOWN_TICKET`，引导读 `design_docs[].confirmed` | 注册表 `get` 三项校验（未知/窗口不符/超 TTL）一律 `undefined` → 用例抛 `REQBOARD_UNKNOWN_TICKET`，文案含「改调 reqboard_status 读 design_docs[].confirmed」 | **无偏离**。依据：`adapters/PendingConfirmRegistry.ts:66-72`、`ConfirmReceipt.ts:41-48`；测试 TC-8 + 跨窗口例；探针 P1/P4 独立复现 |
| R8 | I-4：`confirmed` **以台账为准**（artifact `confirmedAt` / plan `approvedAt`） | `confirmedInLedger()`：plan→`plan.approvedAt`；artifact→该 kind 产物**成组** `every(confirmedAt!==undefined)`（与落章成组语义一致） | **无偏离**。依据：`ConfirmReceipt.ts:55,76-80`；探针 P2（注册表无 outcome、台账已被看板写 `confirmedAt` → `confirmed=true`）独立证实「以台账为准」 |
| R9 | I-4：`advanced`/`from`/`to` 还原 + 幂等 | 从 `statusHistory` 中 ticket 登记之后的确认推进事件还原（原因常量单点于 `confirm-settle.ts`）；重复调用不写台账 | **无偏离**。依据：`ConfirmReceipt.ts:82-99`；探针 P3（两次调用逐字相同且不 bump version） |
| R10 | data-model T-4：`PendingConfirmation` 字段集 + `pc-` 前缀 + 窗口绑定 + `confirmEvidenceWindowMs` 过期 | 字段集合与设计逐字一致；`newTicket` 默认 `pc-` + 6 位 hex；`get` 校验 `windowKey` 且 `now-createdAt>ttlMs`（默认 `LIMITS.confirmEvidenceWindowMs`） | **无偏离**。依据：`shared/protocol.ts:875-891`、`PendingConfirmRegistry.ts:41-72`；探针 P1（字段集/前缀/跨窗口/TTL 过期/plan 不带 kind）独立复现 |
| R11 | `architecture.md` L85：后台作答到达 → 落章+推进+**唤醒窗口** | `suspendConfirm` 的 `ask.then` 里跑同一 `settleAnswers`，成功回填 `port.settle(ticket,outcome)` 并 `deps.delivery?.deliver()` 投递含取回执命令；失败/拒绝只回填 `confirmed=false`，**绝不上抛** | **无偏离**。依据：`pending-confirm.ts:95-127`；TC-7 断言 `delivered` 恰 1 次且含 `reqboard_confirm_receipt` |
| R12 | 兼容性矩阵：未装配 `pendingConfirms` = 旧阻塞语义，`inline_grace_ms` 不生效 | `deps.pendingConfirms===undefined` 分支完全走旧 `await ask` 路径 | **无偏离**。依据：`AskConfirm.ts:143-151`；测试「未装配注册表 = 旧阻塞语义」 |
| R13 | D-6：`AskConfirm` 保持 ≤400 行，且「落章+推进」单一实现 | `AskConfirm.ts` 359→**240 行**；落章+推进抽为 `confirm-settle.ts`（同步/后台共用），赛跑/挂起抽为 `pending-confirm.ts`——两模块**不在**计划「新增 13 文件」清单内，D-6 指定的落点是 `ConfirmReceipt.ts` 侧 | **意图无偏离，落点有偏离（结构性，非行为）**：见 §2 **D-A**。行为等价、尺寸达标（240<400）；仅文件清单与 D-6 措辞不一致 |
| R14 | 装配：`src/index.ts` 注册工具 + 注入注册表；三段式工具目录 | `new PendingConfirmRegistry()` → `useCaseDeps.pendingConfirms`；`tools.register(defineConfirmReceiptTool(useCaseDeps))`；新目录含 `ConfirmReceiptTool.ts/prompt.ts/index.ts` | **无偏离**。依据：`src/index.ts:50,222,365-366,386`、`tools/index.ts:20`；`apply-wiring.test.ts` 4/4、`tools-dispatch.test.ts` 4/4 绿 |
| R15 | NFR-2：同一产物不重复弹框（护栏不降） | 已确认早返回路径未因 T-6 失效；TC-20 断言弹框端口仅 1 次 | **无偏离**。依据：`AskConfirm.ts:88-111`；测试 TC-20 |
| R16 | 尺寸门禁（`size-budget`） | `index.ts` 442 行 > 400（HEAD 433）；T-6 自身接线使其 +8~9 行 | **不判 T-6 偏离（已知基线红）**：`decomposition.md` D-2/T-12 已明定由 T-12 修绿，T-6 验收行只要求「ask-confirm 两文件全绿」；白名单外**无新增**超标文件（新增四文件 49/88/122/128 行） |
| R17 | D-1/T-1 基线纪律：typecheck 错误数 ≤ 基线 23 且**新增文件 0 报错** | `tsc --noEmit` 报 **24** 条（基线 23）；新增的第 24 条落在 **T-6 新文件** `tests/ask-confirm-pending.test.ts:55:36`（`TS2322`） | **有偏离（新增文件 1 条类型错误）**：见 §3 **D-A**。不新增失败**文件**（`typecheck.test.ts` 本就红，失败集合仍是基线子集），但破坏「新增文件 0 报错」纪律；建议收尾前一行修复 |
| R18 | I-4/工具契约：`REQBOARD_INVALID_INPUT`（空 ticket）/ `REQBOARD_STORE_INCONSISTENT`（需求不在台账） | 实现新增了这两个错误码（I-4 的错误列只写 E-5） | **扩展（未列于 I-4），非行为偏离**；见 §2 观察项 **O-3** |

---

## 2. 偏离与观察项

**未发现行为级（契约）偏离。** 发现 1 项**结构性偏离**与 3 项观察项，均不阻断父卡收尾：

- **D-A（结构性落点偏离 · 非行为）**：T-6 实际新增两个**计划外**内部模块
  `src/application/internal/confirm-settle.ts`（292 行）与 `src/application/internal/pending-confirm.ts`（128 行）；
  `decomposition.md`「新增（13 个源文件）」清单与 D-6（「抽到 `ConfirmReceipt.ts` 侧」）均未登记它们。
  判定：**意图满足**（落章+推进单点实现、`AskConfirm` 降到 240 行、非阻塞机制与响应组装解耦），
  **无行为差异**；仅文件清单/落点与计划措辞不一致。建议：收尾时在 `decomposition.md` 改动盘点补记这两文件（文档维护，不必返工代码）。
- **O-1（低风险 · 非偏离）**：ticket 唯一性是**概率**唯一（`randomInt(0,0xffffff)` 6 位 hex，`records.set` 碰撞即静默覆盖）；
  设计 `data-model.md:66` 只要求「`pc-` + 随机 id」，故不算契约偏离。另，注册表**无淘汰**、
  过期记录在进程长跑中不回收（设计未要求）。当前量级（每需求个位数 ticket）无实际影响。
- **O-2（文档痕迹 · 非实现偏离）**：`index.ts` 装配使该文件 433→442 行，与 T-12 的修绿目标叠加；
  已在 D-2 预期内（`decomposition.md` L89-92）。无新增白名单外超标文件。
- **O-3（契约扩展 · 非行为偏离）**：`reqboard_confirm_receipt` 新增两个未列于 I-4 错误列的错误码
  （空 ticket → `REQBOARD_INVALID_INPUT`；需求不在台账 → `REQBOARD_STORE_INCONSISTENT`）。
  二者均为仓内既有通用 code、且是更精确的失败语义；I-4 只说 E-5 必现，未禁止补充入参校验。建议在 I-4 错误列补一行即可。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（复跑，与上游自述一致）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts
```

实际输出：

```
 ✓ tests/ask-confirm.test.ts (11 tests) 157ms
 ✓ tests/ask-confirm-pending.test.ts (11 tests) 272ms

 Test Files  2 passed (2)
      Tests  22 passed (22)
```

判定：**2/2 文件、22/22 用例通过，退出码 0** —— 与父卡验收期望一致（TC-5/6/7/8/20 全覆盖）。

### 3.2 接口层回归（schema / 输出契约 / 分发 / 装配 / 契约形状）

```bash
npx vitest run tests/output-contract.test.ts tests/tools-schema.test.ts tests/tools-dispatch.test.ts tests/apply-wiring.test.ts tests/contract-shapes.test.ts tests/size-budget.test.ts
```

- `output-contract.test.ts` **20/20 绿**（新工具返回键全部已在 schema 声明；含 `ConfirmReceipt` 映射）
- `tools-schema.test.ts` **3/3 绿**（`additionalProperties` 铁律）
- `tools-dispatch.test.ts` **4/4 绿**（`ConfirmReceiptTool` 三段式与目录清单）
- `apply-wiring.test.ts` **4/4 绿**（`reqboard_confirm_receipt` 已注册）
- `contract-shapes.test.ts` **8/8 绿**（`PendingConfirmation` 字段契约）
- `size-budget.test.ts` **1 红**：`index.ts = 442 行` —— **基线既有、由 T-12 修绿**（见 R16）

合计 5 绿 1 红（43/44 通过）。

### 3.3 全量套件（确认失败集合 ⊆ 基线，无新增失败文件）

```bash
npx vitest run
```

实际输出（摘要）：

```
 Test Files  6 failed | 147 passed (153)
      Tests  7 failed | 1813 passed (1820)
```

失败用例 7 条全部落在 `decomposition.md` D-1 已登记的基线缺口（`typecheck` / `template-address-injection`×2 /
`size-budget` / `layer-boundary` / `client-view` / `application/repository`）；
基线红例 `design-completeness-gate.test.ts`（T-5 已修复）现转绿 —— 失败**文件**集合是基线的真子集，无新增失败文件。

### 3.4 类型门禁（`tsc --noEmit`：24 条 vs 基线 23）

```bash
npx tsc --noEmit -p tsconfig.json
```

- 24 条错误中 23 条位于 D-1 已登记的基线文件（`domain/template/*`、`gate-wiring.ts`、`CaptureHook.ts` 等，均非 T-6 文件未修改）。
- **新增第 24 条 = T-6 新文件**：`tests/ask-confirm-pending.test.ts(55,36): TS2322`
  —— `makeDeps` 的 `opts.delivery` 声明为 `{ deliver: (w, m) => unknown }`，
  赋给 `deps.delivery: AgentDeliveryPort`（`deliver(): DeliveryResult`）时不兼容。
  运行时无影响（该 mock 在 TC-7 中真实返回 `{ delivered: true }` 并通过）；
  修复面一行（把 mock 返回类型标注为 `DeliveryResult` / `{ delivered: boolean; reason?: string }`）。

### 3.5 一次性契约探针（独立复现，跑完即删）

本轮另写 `tests/__probe-t51fc46.test.ts`（4 例，已删除并复核 `No such file or directory`）：

```
 ✓ tests/__probe-t51fc46.test.ts (4 tests) 27ms
 Test Files  1 passed (1)
      Tests  4 passed (4)
```

- **P1** 注册表契约：字段集 `{ticket,windowKey,requirementId,target,kind?,createdAt}`、`pc-` 前缀、
  跨窗口 `get`→undefined、超 TTL→undefined、`target=plan` 不带 `kind` —— 与 T-4 一致
- **P2** 回执**以台账为准**：注册表无 outcome、台账已被「看板确认」写 `confirmedAt` → `confirmed=true, advanced=false`（不依赖注册表）
- **P3** 回执**幂等**：两次调用返回逐字相同、台账 version 不变
- **P4** 空 ticket → `REQBOARD_INVALID_INPUT`

---

## 4. 复核结论

1. **行为契约逐条无偏离**：R1–R12、R14–R16、R18 均「无偏离/不判偏离」并给出代码坐标与独立证据；
   FR-3 的结构性目标（等待不再占用调用方预算、超宽限不判失败、后台落章+推进+唤醒、回执以台账为准）全部实测成立。
2. **父卡验收命令独立复跑 22/22 全绿**；接口层回归 43/44（唯一红为基线 `index.ts` 尺寸，T-12 范围）。
3. **偏离清单**：1 项结构性落点偏离（**D-A**，无行为影响，建议补文档）+ 3 项观察项（O-1 概率唯一/无淘汰、O-2 index 尺寸叠加、O-3 错误码扩展）。
4. **新增 1 条类型错误（R17/D-A）**：`tests/ask-confirm-pending.test.ts:55`，不新增失败文件、不影响运行，但违反「新增文件 0 报错」基线纪律；**建议收尾前一行修复**（非阻塞）。
5. 本卡为 review 阶段，**只读复核 + 落本记录**；未修改任何实现、测试或配置源码。本轮新增产物仅本文件。
6. **复核结论：通过（附带 1 项建议修复项，不阻塞父卡收尾）。**
