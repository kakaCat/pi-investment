# t-c579d7 复核记录（父卡 t-41f158 / T-1「定义新契约类型与端口」· 阶段 review）

- 复核时间：2026-09-24T23:20+0800
- 复核对象（实现）：`packages/web/dsh-pmboard/src/shared/protocol.ts`、`packages/web/dsh-pmboard/src/application/ports.ts`、`packages/web/dsh-pmboard/tests/contract-shapes.test.ts`
- 复核基准（设计）：`design/data-model.md`（T-1/T-3/T-4 字段明细与索引约束）、`design/interfaces.md`（I-1/I-4/I-8 字段与兼容性）、`design/architecture.md`（§挂起确认注册表 / FR-3 改动点）、`decomposition.md`（T-1 落点与验收标准）
- 实现基线快照：`git show --name-only adb4bd77` = 仅上述 3 个文件（+254/-1）；已合并 `main`（merge 9e5ebf60）
- 复核结论：**实现与设计 0 处偏离**；1 处「设计留白、实施补全」（端口方法签名，不构成偏离）；2 处设计文档自身口径 nits（不影响实现判定）。

---

## 1. 逐条复核结论（设计与实现对照）

| # | 复核项 | 设计出处 | 实现出处 | 结论 | 依据 |
|---|---|---|---|---|---|
| 1 | `InterruptionRecord`：`at`/`reason`/`stage`/`pendingAction` 必填，`tool?` 可选 | data-model.md L38-44 | protocol.ts:840-851 | **无偏离** | 5 个字段名、类型（`number`/`string`/`string`/`string`/`string?`）与必填性与字段表逐字一致；设计 `stage` 声明类型即 `string`，实现同 |
| 2 | `RequirementRecord.interruption?`（可选，缺省=无断点） | data-model.md L30、兼容表 L88 | protocol.ts:940-945 | **无偏离** | 声明为可选字段 `interruption?: InterruptionRecord`；注释明确「缺省 = 无断点（存量记录读出即旧行为，续跑输入包逐字节不变）」，与「旧数据怎么办」一致 |
| 3 | `DesignDocRegistration`：`name`/`path`/`on_disk`/`registered`/`confirmed` 必填，`exempted?`/`conditional?` 可选；派生投影不落盘 | data-model.md L32；interfaces.md L31-37 | protocol.ts:434-449 | **无偏离** | 7 字段名/类型/必填性逐条一致（`conditional?: 'frontend' \| 'backend'`）；注释「派生投影，**不落盘**」与 data-model「派生（不持久化）」一致 |
| 4 | `PendingConfirmation`：`ticket`/`windowKey`/`requirementId`/`target`/`createdAt` 必填，`kind?`/`outcome?` 可选 | data-model.md L64-72 | protocol.ts:853-881 | **无偏离** | 字段表逐条一致：`target: 'artifact' \| 'plan'`、`kind?: ArtifactKind`（对应设计「ArtifactKind（可选）」）、`createdAt: number`；`outcome` 与设计 `{confirmed;advanced;userChoice?;userFeedback?}` 逐字段一致 |
| 5 | `outcome` 提为具名类型（`PendingConfirmationOutcome`） | data-model.md L72（内联结构） | protocol.ts:853-859 | **无偏离** | 结构性新增导出名，键集合与嵌套类型不变（形状测试以 `toEqualTypeOf` 钉死）；属只增不改，消费方忽略即兼容 |
| 6 | ticket 前缀 `pc-` 固定 | data-model.md L66「前缀 `pc-` + 随机 id」 | protocol.ts:884 `PENDING_CONFIRM_TICKET_PREFIX = 'pc-'` | **无偏离** | 常量值 `'pc-'` 与设计一致；「随机 id / 全局唯一」属生成实现（T-6 `PendingConfirmRegistry`），本卡按卡面约束**不含行为** |
| 7 | `PendingConfirmPort`（`register`/`get`/`settle`，均不抛）+ `UseCaseDeps.pendingConfirms?` | architecture.md L47/L102（点名 `ports.ts` 的 `PendingConfirmPort`）；分解计划 L54；data-model 索引与约束 L81-82 | ports.ts:256-277、ports.ts:300-306 | **无偏离**（设计留白、实施补全） | 见 §2「留白说明」：设计未逐字规定方法签名，实现按 T-4 字段表 + 「ticket 唯一 / 窗口绑定 / outcome 回填」三条约束落定：`register({windowKey,requirementId,target,kind?})`、`get(ticket,windowKey)`、`settle(ticket,outcome)`，返回 `PendingConfirmation`（异窗口/未知 ticket → `undefined`）；`pendingConfirms?` 为可选，注释「缺省 = 未装配非阻塞能力 → 弹框保持旧的阻塞语义」，与 I-3 兼容性列「宽限内作答与原语义逐字一致」对齐 |
| 8 | 卡面约束「先立类型/端口，**不写行为**」 | 任务卡 implementation 段；分解计划 L47 | 全仓 grep + commit 范围 | **无偏离** | `adb4bd77` 仅 3 文件（+254/-1）；`pendingConfirms|PendingConfirmPort|PENDING_CONFIRM_TICKET_PREFIX` 全仓命中仅 `protocol.ts` / `ports.ts` / `contract-shapes.test.ts`（无任何用例或适配器消费）→ 端口未装配、无运行时行为 |
| 9 | 依赖方向：application 只依赖 domain 与 shared 的**类型** | architecture.md §2（protocol.ts 头注 L7-16） | ports.ts:13-22 | **无偏离** | 新增 3 个导入（`ArtifactKind`/`PendingConfirmation`/`PendingConfirmationOutcome`）全部在 `import type {…}` 内（编译期擦除）；`layer-boundary` 实测失败项仍仅 `application/internal/diag-log.ts -> node:fs/node:path`（基线存量），未新增越界 |
| 10 | 新增 `tests/contract-shapes.test.ts` 锁死字段表 | 分解计划 L47/L110；卡验收首句 | tests/contract-shapes.test.ts（131 行 / 8 例） | **无偏离** | 运行时键集合（`Object.keys().sort()`）+ `expectTypeOf` 精确类型双断言覆盖 4 个类型 + 端口面；一处弱断言见 §3-观察 |
| 11 | 兼容性：只增不改 | interfaces.md §兼容性矩阵 L130-138 | 3 文件 diff | **无偏离** | 3 个新增接口/1 个新增可选字段/1 个新增常量/1 个新增可选端口槽/1 个新测试文件；无既有键改名、无删除行（-1 行系 `ports.ts` 单行 import 拆成多行） |
| 12 | 验收标准：两测试文件全绿 | 任务卡「得到什么结果」 | 实测命令 | **无偏离** | `npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts` → 2 files / 27 tests passed（exit 0） |
| 13 | 验收标准：`tsc --noEmit` 错误数 ≤ 23 且新增文件 0 报错 | 任务卡「得到什么结果」；分解计划 D-1 | 实测命令 | **无偏离** | 计数 = 23（=基线 23）；三个文件命中 0 条 |
| 14 | 不新增回归失败 | 分解计划「基线缺口」表 L185-193 | 实测命令 | **无偏离** | 全量 `npx vitest run` → 7 failed files / 9 failed tests（149 files / 1783 tests）；失败集合与基线表逐条同（design-completeness-gate×2、layer-boundary×1、size-budget×1、template-address-injection×2、typecheck×1、client-view×1、repository×1），无新增 |

---

## 2. 设计留白说明（非偏离，下游卡须知）

`PendingConfirmPort` 的方法签名（方法名、参数形态、返回 `undefined` 的降级语义）在 design 文档中**只有点名**（architecture.md L47/L102、分解计划 L54），没有像 I-1/I-4/I-8 那样的字段明细表。本卡按以下三处已有约束事实推定并落定签名，故判定为「留白补全」而非偏离：

| 推定依据 | 出处 | 落定结果 |
|---|---|---|
| `PendingConfirmation` 字段表（决定 register 入参与返回） | data-model.md L64-72 | `register(input: {windowKey,requirementId,target,kind?}): PendingConfirmation` |
| 「ticket 窗口绑定：`windowKey` 必须等于调用窗口」 | data-model.md L82 | `get(ticket, windowKey)`；异窗口 → `undefined`（不抛，由用例降级读台账） |
| 「outcome 后台作答后回填」（缺省=尚未作答） | data-model.md L72 | `settle(ticket, outcome)`；未知 ticket → `undefined`；幂等 |

**下游风险提示（供 T-6/T-9 消费，不是本卡缺陷）**：该签名现为**事实契约**，若 T-6 实现 `PendingConfirmRegistry` 时改了参数形态，需回改 `contract-shapes.test.ts` 并同步 architecture.md —— 否则「设计留白」会变成「两处口径」。同时 I-4 的**工具**契约（`reqboard_confirm_receipt(ticket)` 返回 `success/confirmed/advanced/from/to/requirement_id/note`，interfaces.md L17）本卡未涉及，属 T-6，确认实现未越界。

---

## 3. 设计文档口径 nits（文档自身不一致，实现取合理一侧）

| # | nit | 位置 | 实现取值 | 判定 |
|---|---|---|---|---|
| N-1 | `PendingConfirmation` 关键字段列写 `kind`（未标 ?），字段明细表写「`kind` 必填=否」 | data-model.md L33 vs L70 | 取明细表：`kind?: ArtifactKind` | 合理。概览列是字段枚举、明细表才是契约；形状测试按明细表钉死。建议后续修订文档时把 L33 的 `kind` 标为 `kind?` |
| N-2 | `InterruptionRecord.stage` 明细表类型 `string`，接口注释写「`RequirementStatus` 之一」 | data-model.md L42 vs protocol.ts:845-846 | 取明细表：`stage: string` | 合理。设计未要求收窄为 `RequirementStatus`；注释只表达语义（当前态），不收窄类型可避免存量/未来状态值撞类型。非偏离 |

---

## 4. 复核观察（不改判定，供后续卡）

- **O-1（弱断言）**：`contract-shapes.test.ts:52-56` 的「存量记录读出即『无断点』」用 `const legacy = {} as RequirementRecord` 断言 `legacy.interruption === undefined` —— 这是同义反复（空对象上该键必然 undefined，未经任何解析/反序列化路径），**不能**替代 TC-16「老需求无 `interruption` → 输入包逐字节不变」的 legacy 保证（分解计划 L164 指向 T-9 的 `tests/interruption-checkpoint.test.ts`）。结论：本卡在该点上证据偏弱但**不违规**（卡面只要求形状门禁）；建议 T-9 保留输入包逐字节断言。
- **O-2（预存事实核验）**：`contract-shapes.test.ts:127-130` 断言 `'design' ∈ ALL_ARTIFACT_KINDS` —— 该枚举值**本卡之前即存在**（`src/domain/artifact/ArtifactSpec.ts:21-22`，REQ-81aabd / 2026-09-21 裁定），非 T-1 改动；与分解计划「组件说明：T-3 才增 `SUBMIT_KINDS` 的 design」一致，不构成越界新增。本卡只是把它作为「登记入口不会撞枚举」的事实前提核验。
- **O-3（落点合规）**：新增 3 个记录形状直接声明在 `shared/protocol.ts`，而 `protocol.ts` 头注规定「领域规则的**数据与判定**迁 `src/domain/**`，本文件做再导出」。判定不违规：这 3 个是**记录形状**（与 `RequirementRecord`/`StageArtifact` 同类，后者一直在 protocol.ts），且分解计划 L53 明确指定落点为 protocol.ts；`PendingConfirmation.kind` 引用 domain 的 `ArtifactKind` 而非另立枚举，无口径分裂。

---

## 5. 证据（命令 + 输出摘要）

### 5.1 契约门禁（卡验收 ①）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts
```

```
 ✓ tests/contract-shapes.test.ts (8 tests) 2ms
 ✓ tests/output-contract.test.ts (19 tests) 80ms
 Test Files  2 passed (2)
      Tests  27 passed (27)
```

退出码 0 —— 与验收「两文件全绿」一致。

### 5.2 类型基线（卡验收 ②）

```bash
cd packages/web/dsh-pmboard
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -c "error TS"          # → 23
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "contract-shapes|shared/protocol|application/ports" | wc -l   # → 0
```

- 错误总数 `23` = 基线 23（分解计划 D-1）；本卡 3 个文件命中 `0` 条。
- 报错文件 8 个（`CaptureHook.ts`/`h3-inject.ts`/`node-input-package.ts`/`template/render.ts`/`template/resolve.ts`/`gate-wiring.ts`/`gate-aware-questions.test.ts`/`template-address-injection.test.ts`）——均为基线存量，无一条来自本卡文件。
- `EXIT=2`（tsc 有错即非 0，符合预期；判定依据是「计数 ≤ 23 且新文件 0 报错」）。

### 5.3 全量回归（无新增失败）

```bash
npx vitest run
```

```
 Test Files  7 failed | 142 passed (149)
      Tests  9 failed | 1774 passed (1783)
```

失败集合（7 文件 / 9 例）与分解计划「基线缺口」表逐条同名：`design-completeness-gate`×2、`layer-boundary`×1、`size-budget`×1、`template-address-injection`×2、`typecheck`×1、`client-view`×1、`repository`×1 → **无新增失败**。（基线 147 files/1770 tests 中的 +2 files/+13 tests 来自 T-1 的 `contract-shapes.test.ts`(8) 与本工作区 T-7 的 `tests/zero-arg-binding.test.ts`(5)，均非失败。）

### 5.4 层边界未被本卡破坏

```bash
npx vitest run tests/layer-boundary.test.ts
```

```
application/ 出现越界 import：
application/internal/diag-log.ts -> node:fs
application/internal/diag-log.ts -> node:path
 Test Files  1 failed (1)   Tests  1 failed | 8 passed (9)
```

越界项仅基线存量 `diag-log.ts`，`application/ports.ts` 的新增导入全部为 `import type`，未被列出。

### 5.5 范围与无行为核验

```bash
git show --stat adb4bd77
git show --name-only --pretty=format: adb4bd77
```

```
 .../web/dsh-pmboard/src/application/ports.ts       |  39 +++++-
 .../web/dsh-pmboard/src/shared/protocol.ts         |  85 +++++++++++++
 .../web/dsh-pmboard/tests/contract-shapes.test.ts  | 131 +++++++++++++++++++++
 3 files changed, 254 insertions(+), 1 deletion(-)
```

`pendingConfirms|PendingConfirmPort|PENDING_CONFIRM_TICKET_PREFIX` 全仓（`packages/web/dsh-pmboard`）命中 11 处，全部落在 `protocol.ts` / `ports.ts` / `contract-shapes.test.ts` 三个文件内 → 端口零装配、零行为，符合「先立类型/端口，不写行为」。

---

## 6. 复核结论

1. **实现与设计 0 处偏离**：data-model.md 的 T-1/T-3/T-4 字段表（名称、类型、必填性）、`RequirementRecord.interruption?` 的可选与缺省语义、`pc-` 前缀、兼容性「只增不改」、依赖方向、卡面「不写行为」范围约束、两条验收标准与「不新增回归失败」，共 14 项逐条核对**全部无偏离**（§1 表）。
2. **1 处设计留白**（`PendingConfirmPort` 方法签名，§2）：实现按设计既有约束推定，判定非偏离；已在 §2 把该签名标为「下游事实契约」并提示回改义务。
3. **2 处文档口径 nit**（§3）：均属设计文档自身不一致，实现取合理一侧，非实现偏离。
4. **3 条观察**（§4）：其中 O-1（legacy 断言同义反复）建议由 T-9 的输入包逐字节断言补足，其余两条为事实澄清。
5. 本卡为纯契约，**无运行时行为**；端到端行为验收在 T-13（与联调记录 §4 结论一致）。

> 复核未修改任何实现文件；本轮仅新增本记录文件。
