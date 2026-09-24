# t-4c35b9 测试记录（父卡 t-41f158 / T-1「定义新契约类型与端口」· 阶段 test）

- 测试时间：2026-09-24T23:20+0800
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 工作目录 `packages/web/dsh-pmboard`
- 被测对象（实现基线 `adb4bd77`，已合并 `main` `9e5ebf60`）：
  - `packages/web/dsh-pmboard/src/shared/protocol.ts`（`InterruptionRecord` / `DesignDocRegistration` / `PendingConfirmation` / `PendingConfirmationOutcome` / `PENDING_CONFIRM_TICKET_PREFIX` / `RequirementRecord.interruption?`）
  - `packages/web/dsh-pmboard/src/application/ports.ts`（`PendingConfirmPort` / `UseCaseDeps.pendingConfirms?`）
  - `packages/web/dsh-pmboard/tests/contract-shapes.test.ts`（131 行 / 8 例）
- 测试结论：**目标命令全绿** —— 契约门禁 2 文件 / 27 用例全通过（exit 0）；`tsc` 错误数 23（= 基线 23）、被测 3 文件 0 报错。两项验收标准均满足。

---

## 1. 目标命令 ①：契约门禁 + 输出契约回归

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts
```

实际输出：

```
 ✓ tests/contract-shapes.test.ts (8 tests) 2ms
 ✓ tests/output-contract.test.ts (19 tests) 78ms

 Test Files  2 passed (2)
      Tests  27 passed (27)
```

- 退出码：**0**（全绿）
- 判定：与验收「两测试文件全绿」一致。

### 1.1 `contract-shapes.test.ts` 逐例（本卡契约形状门禁，8/8 通过）

```
 ✓ T-1 断点记录（FR-6 / I-8） > 字段表：at/reason/stage/pendingAction 必填，tool 可选
 ✓ T-1 断点记录（FR-6 / I-8） > 挂在需求上且可选：存量记录读出即「无断点」（undefined，不是空对象）
 ✓ T-3 逐份登记态投影（FR-1 / I-1 design_docs[]） > 五个必填 + 两个可选，与 I-1 字段表一致
 ✓ T-3 逐份登记态投影（FR-1 / I-1 design_docs[]） > 「未登记 / 待确认 / 已落章」三态由三个布尔区分（闸门文案分叉的事实源）
 ✓ T-4 挂起确认（FR-3 / I-3 I-4） > ticket 前缀固定 pc-；字段表与 T-4 一致
 ✓ T-4 挂起确认（FR-3 / I-3 I-4） > 回执结果：confirmed/advanced 必填，用户选择与意见可选
 ✓ T-4 挂起确认（FR-3 / I-3 I-4） > 端口面只有 register/get/settle；UseCaseDeps 允许缺省（未装配 = 旧阻塞语义）
 ✓ I-1 kind=design 的事实前提 > 'design' 已是合法产物种类（登记入口不会撞枚举）
```

覆盖设计口径：I-1 / I-3 / I-4 / I-8 与 data-model T-1 / T-3 / T-4；运行时键集合（`Object.keys().sort()`）+ `expectTypeOf` 精确类型双断言。

### 1.2 `output-contract.test.ts`（回归面，19/19 通过）

- 5 例输出字段 ⊆ `output.schema` 声明（archive_submit / verify_submit / ask_confirm 成功路径 / ask_confirm 非肯定项 / ask_confirm fallback=board）。
- 14 例静态扫描（扫描器总覆盖 1 例 + 13 个 `define*` 工具各 1 例）：扫描器覆盖全部工具文件（≥9 个工具工厂）且 `defineAcceptSheetTool` / `defineAdvanceTool` / `defineAskConfirmTool` / `defineCaptureTool` / `defineCreateTool` / `defineDecomposeTool` / `defineMoveTool` / `defineStatusTool` / `defineSubmitTool` / `defineTaskExecuteTool` / `defineTaskMoveTool` / `defineTaskReportTool` / `defineTaskStatusTool` 的全部 `return` 分支键均已声明。
- 判定：本卡纯类型/端口新增（无工具输出变更），回归面不新增失败。

## 2. 目标命令 ②：类型基线

```bash
cd packages/web/dsh-pmboard
npx tsc --noEmit -p tsconfig.json
```

实际输出（摘要）：

```
error TS 计数 = 23          # = 本卡基线 23（拆分计划 D-1）
被测 3 文件命中 = 0         # contract-shapes.test.ts / shared/protocol.ts / application/ports.ts
报错文件（8 个，均为基线存量，非本卡引入）：
  src/adapters/CaptureHook.ts                         (1)
  src/application/gate/handlers/h3-inject.ts          (1)
  src/application/internal/node-input-package.ts      (1)
  src/domain/template/render.ts                       (6)
  src/domain/template/resolve.ts                      (5)
  src/gate-wiring.ts                                  (1)
  tests/gate-aware-questions.test.ts                  (2)
  tests/template-address-injection.test.ts            (6)
```

- `EXIT=2`：tsc 检出错即非 0，属预期；判定依据是验收口径「**错误数 ≤ 23 且新增文件 0 报错**」，非退出码。
- 错误总数 **23 = 基线 23**（拆分计划 D-1），被测 3 文件命中 **0** 条。
- 佐证「非本卡引入」：T-1 提交 `adb4bd77` 只改被测 3 文件（+254/-1，且 -1 系 `ports.ts` 单行 import 拆成多行），diff 为纯新增类型/端口/测试，未触碰上表任一报错文件。

---

## 3. 测试结论

1. 目标命令 ①（`npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts`）：**2 files / 27 tests 全绿，exit 0**。
2. 目标命令 ②（`npx tsc --noEmit -p tsconfig.json`）：**错误数 23 = 基线，被测 3 文件 0 报错**。
3. 本卡为 test 阶段，只执行目标命令并落本记录；**未修改任何实现/测试源码**，本轮新增产物仅本文件。
4. 端到端行为验收不在本卡（属 T-13）；本卡只确认 T-1 契约形状门禁与类型基线达成。
