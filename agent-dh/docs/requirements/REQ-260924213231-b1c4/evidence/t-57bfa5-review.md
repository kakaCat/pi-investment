# t-57bfa5 复核记录（父卡 t-800d53 / T-12「组合根瘦身使尺寸门禁转绿」· 阶段 review）

- 复核时间：2026-09-25T02:00+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 复核对象（父卡 T-12 / 计划偏差 D-2；工程规范卡，不接 FR）：
  - 新增 `packages/web/dsh-pmboard/src/plugin-config.ts`（42 行）：`PluginConfig` + `dshHomePath()` + `nodeIsolationEnabled()`
  - 新增 `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts`（161 行）：`createCaptureRuntime()` + `assembleCaptureHook()`
  - `packages/web/dsh-pmboard/src/index.ts`：移除上述两块（433 → 357 行），第 73 行再导出 `dshHomePath` / `nodeIsolationEnabled`
- 设计依据（比对基线）：`decomposition.md` D-2（L84-92）+ T-12 行（L120）+ RISK-2/RISK-3；`design/architecture.md` L225（单文件 ≤400 行 + `tests/size-budget.test.ts`）；任务卡 `tasks/t-800d53.md`「得到什么结果」+「实施方案」
- 复核方式：**只读复核 + 独立复跑 + 一次性 tsx 探针独立见证**（不采信上游自述）——`git` 对照移除块与新增块、逐行核对注释随迁、独立运行父卡三条验收命令、全量套件与基线（D-1）逐项对照、另写一次性 `.mts` 探针验证再导出同一性后**已删除**

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 计划 | `decomposition.md` D-2 | 把配置/路径纯函数与捕获根装配从 `src/index.ts` 抽到 `src/plugin-config.ts` 与 `src/wiring/pm-capture-root.ts`；`dshHomePath`/`nodeIsolationEnabled` 由 index.ts **再导出**保持既有 import 兼容；把 index.ts 降到 ≤400 行使 `tests/size-budget.test.ts` 转绿 |
| 计划 | `decomposition.md` T-12 行 | 落点 = index.ts + plugin-config.ts + wiring/pm-capture-root.ts；验收 = `npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts` 全绿 + `wc -l src/index.ts ≤ 400` + `nodeIsolationEnabled` 仍可从 `src/index.ts` import 且行为不变 |
| 计划 | `decomposition.md` RISK-2/RISK-3 | 单文件上限 400；同文件卡串行（index.ts 链 T-6→T-9→T-12） |
| 架构 | `design/architecture.md` L225 | 尺寸纪律：单文件 ≤400 行，门禁 `tests/size-budget.test.ts`；「新能力各自独立模块」 |
| 任务卡 | `tasks/t-800d53.md`「得到什么结果」/「实施方案」 | 三条验收命令全绿；`wc -l src/index.ts ≤ 400`；`nodeIsolationEnabled` 从 index.ts 可 import 行为不变；抽取配置/路径纯函数与捕获根装配两处 |
| 基线 | `decomposition.md` D-1 + 基线缺口表 | 基线红已知（7 文件/9 例 + tsc 23 条）；本次只保证**不新增失败** |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | D-2/T-12：两个新文件的**落点与命名** | 恰为 `src/plugin-config.ts`（42 行）与 `src/wiring/pm-capture-root.ts`（161 行）；无第三个文件、无路径漂移 | **无偏离**。依据：`git status --short` 仅 `?? src/plugin-config.ts` / `?? src/wiring/`（§3.6） |
| R2 | D-2：**配置/路径纯函数**抽取完整（含 `PluginConfig`） | `PluginConfig` + `dshHomePath` + `nodeIsolationEnabled` 逐行搬到 plugin-config.ts，注释（含 REQ-422af1 与事故出处）逐字保留；index.ts 内**无残留定义**（仅 import + 再导出 + 调用点） | **无偏离**。依据：`git diff HEAD -- src/index.ts` 移除块（原 L72-105）与 plugin-config.ts 逐行一致；全 src grep 定义仅此一处（§3.6） |
| R3 | D-2：**捕获根装配**抽取（三张共享表 + 唯一投递实现 + hook 装配） | `createCaptureRuntime()` 建 `pendingCapture`/`toolTrace`/`recentUserMsgs`/`deliverer`；`assembleCaptureHook()` 承载原闭包回调链（`onBoundWindowActivity`/`onStagePrompt`/`onTurnEnd`/`onTurnFinished` + 节点-1 诊断日志）；index.ts 只留装配顺序 | **无偏离**。依据：`git diff` 移除块（原 L254-330）与 pm-capture-root.ts 对照；`apply()` 冒烟 `tests/apply-wiring.test.ts` 全绿（§3.1/§3.5） |
| R4 | D-2：index.ts **再导出** `dshHomePath`/`nodeIsolationEnabled`，既有 import 兼容 | index.ts:73 `export { dshHomePath, nodeIsolationEnabled }`（自 plugin-config.js import 后直出）；探针实测二者与 plugin-config 导出为**同一函数对象**（非转发 wrapper） | **无偏离**。依据：§3.3 探针 `sameDshHomePath:true / sameNodeIsolation:true`；`tests/isolate-node-context.test.ts:38` 从 `../src/index.js` import 该函数，29/29 绿 |
| R5 | 父卡验收：目标三文件全绿 | 独立复跑 **3 文件 60/60 绿（exit 0）**：size-budget 5、capture-hook 26、isolate-node-context 29 | **无偏离**。依据：§3.1 |
| R6 | D-2/架构 L225：`src/index.ts` ≤400 且 size-budget 转绿 | `index.ts` **357 行 ≤ 400**（抽取前 433）；新文件亦在门禁内（plugin-config 42 / pm-capture-root 161；门禁递归扫 `src/**/*.ts`） | **无偏离**。依据：§3.2 |
| R7 | 行为零变更（抽取不得改语义） | 目标测试全绿；`apply()` 冒烟全绿；全量套件失败 7 例 ⊆ 基线 9 例（size-budget 由本卡转绿），**T-12 未新增任何失败** | **无偏离**。依据：§3.5 全量套件与 D-1 基线逐项对照 |
| R8 | 依赖方向/层边界不新增越界 | 新 `wiring/` 为组合根延伸（与 index.ts 同向：可引 adapters/application/`@deepseek-ai`）；`tests/layer-boundary.test.ts` 检查面为 domain/application/shared，**未新增越界**（该文件当前唯一红是 diag-log.ts，属 D-1 基线） | **无偏离**。依据：`tests/layer-boundary.test.ts:46-65` 规则面 + §3.5 失败清单 |
| R9 | 类型纪律（D-1：新增文件 0 报错；tsconfig `noUnusedLocals`/`noUnusedParameters` 均 true） | `tsc --noEmit` 24 条 = 基线 23 + 1（T-6 新测试 `tests/ask-confirm-pending.test.ts`）；**T-12 三文件命中 0 条**（无未用 import，说明抽取后清理干净） | **不判本卡偏离**（增量 0）。依据：§3.4 |
| R10 | 注释随代码搬（pm-capture-root.ts 头声明的硬约束） | 原 hook 说明块（用户裁定 #2/#3）成为 `assembleCaptureHook` 的 docstring；`onStagePrompt`/`onTurnEnd`/`onTurnFinished` 各自的「为什么」注释（含 D-17 时序纪律、事故出处）逐条随迁 | **无偏离**。依据：源码对照（§3.6） |
| R11 | 计划落点文件清单，无越界改动 | T-12 只改 index.ts + 新增两文件；`git status` 里其余改动分属 T-1..T-11（各自文件） | **无偏离**。依据：§3.6 |

---

## 2. 偏离与观察项

**总判定：T-12 设计与实现——无功能偏离（R1–R11 全过）；下列 4 条为不阻断的观察项（新增公开面 / 跨卡托管 / 新目录 / 覆盖口径），不影响父卡验收。**

### O-1（观察 · 公开面新增 · 无害）
`PluginConfig` 抽取前是 index.ts 内的**非导出** interface（`git show HEAD` 第 72 行 `interface PluginConfig`，无 `export`）；抽取后 plugin-config.ts 将其 `export`，index.ts 只 import 类型、**不**再导出。故 `src/index.ts` 对外面**无变化**（除 D-2 指定的两个函数再导出）；`PluginConfig` 的新增导出只对 `plugin-config.js` 可见，无外部消费者（全 src grep）。判定：不存在越界的公开面扩张。

### O-2（观察 · 新增导出类型 · 无害）
pm-capture-root.ts 新导出 `PendingCaptureMessage` / `CaptureRuntime` / `CaptureRuntimeDeps` / `CaptureHookAssemblyDeps`，并把原内联类型 `{windowKey;text;capturedAt}` 命名为 `PendingCaptureMessage`、把 `import('./adapters/SessionProbeAdapter.js').RecentUserMsg` 改为 `import type`。结构等价、纯署名，无行为影响（目标测试 + apply 冒烟均绿）。

### O-3（观察 · 跨卡代码托管 · 需父卡知悉）
`onTurnFinished`（FR-6 / T-9 新增的回调）随本次「整块搬」从 T-9 的落点 `src/index.ts` 迁到 `src/wiring/pm-capture-root.ts`；T-9 任务卡落点清单未列该文件。这是 T-12 依赖 T-9 且串行执行的必然结果，行为由 `tests/interruption-checkpoint.test.ts`（T-9 用例，全量套件中为绿）+ `assembleCaptureHook` 的惰性 `useCaseDeps: () => useCaseDeps` 承接（T-9 的 D-17 异步边界语义不变）。判定：非功能偏离；仅提示后续按「文件归属」审账时需知道该回调现居 wiring 文件。

### O-4（观察 · 新目录 `src/wiring/` · 已由计划授权）
`src/wiring/` 为本次新建顶层目录，`design/architecture.md` 的分层依赖表（domain/application/adapters/tools/http/client/shared）未列 `wiring`。但 `decomposition.md` T-12 行与 D-2 **显式**指定该路径，且 `tests/layer-boundary.test.ts` 规则面不含 `wiring`（不产生越界判定）。判定：按**已批准计划**无偏离；仅提示设计文档层表可后续补记 `wiring = 组合根延伸`。

### O-5（观察 · 覆盖口径 · 不阻断）
父卡指定的三条测试中，`capture-hook.test.ts` 直测 adapters 层 `createSessionEventCaptureHook`（本次未改动该文件），`isolate-node-context.test.ts` 直测隔离路径（本次未改动）；真正驱动**被搬代码**的是 `tests/apply-wiring.test.ts`（调 `apply()` → `createCaptureRuntime` + `assembleCaptureHook` 实跑，全绿）与 t-a45bcd 联调卡的一次性探针（C4/C5 直测两函数）。即被搬代码的行为证据充分，但主目标三条测试里没有一条**直接**单测 `assembleCaptureHook`。判定：不属偏离（计划只要求这三条）；作为加强项建议，未来 `pm-capture-root.ts` 再演进时补一条直接单测。

---

## 3. 复核证据（命令与输出）

### 3.1 父卡验收命令复跑（独立执行）
```
$ cd packages/web/dsh-pmboard && npx vitest run \
    tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts
 ✓ tests/capture-hook.test.ts (26 tests) 7ms
 ✓ tests/isolate-node-context.test.ts (29 tests) 21ms
 Test Files  3 passed (3)
      Tests  60 passed (60)
   Duration  664ms        # exit 0
```
关联：`tests/apply-wiring.test.ts`（调 `apply()` 的宿主接线冒烟，全量套件中为绿）——覆盖被搬装配的实跑路径。

### 3.2 尺寸门禁
```
$ wc -l src/index.ts src/plugin-config.ts src/wiring/pm-capture-root.ts
     357 src/index.ts
      42 src/plugin-config.ts
     161 src/wiring/pm-capture-root.ts
     560 total
```
`tests/size-budget.test.ts` 递归扫 `src/**/*.ts`（L22-31、L66-71），三文件均 ≤400 且不在白名单（白名单仅 `client/*` 与 `shared/protocol.ts`）；该文件 **5/5 绿**（旧红：index.ts 433 行）。抽取前基线：`git show HEAD:...src/index.ts | wc -l` → **433**。

### 3.3 再导出同一性（一次性探针，跑完已删）
```
$ npx tsx /tmp/probe-t12.mts      # 临时文件，随后 rm -f
RESULT {"sameDshHomePath":true,"sameNodeIsolation":true,"hasBoth":true}
```
`import * as m from 'src/index.js'` 与 `import * as c from 'src/plugin-config.js'`：两导出为**同一函数对象**（`m.dshHomePath === c.dshHomePath`）。

### 3.4 类型检查增量
```
$ npx tsc --noEmit -p tsconfig.json
---TOTAL--- 24        # 基线 23（D-1）+ 1（tests/ask-confirm-pending.test.ts，T-6 新文件）
```
24 条命中文件：CaptureHook.ts / h3-inject.ts / node-input-package.ts / domain/template/{render,resolve}.ts / gate-wiring.ts / 5 个 tests —— **`src/index.ts`、`src/plugin-config.ts`、`src/wiring/pm-capture-root.ts` 命中 0 条**。tsconfig `noUnusedLocals=true`、`noUnusedParameters=true`（第 16-17 行），0 报错即证明抽取后无未用 import/参数。

### 3.5 全量套件 vs 基线（D-1：7 文件/9 例 + tsc 23）
```
$ npx vitest run
 Test Files  6 failed | 151 passed (157)
      Tests  7 failed | 1851 passed (1858)
```
失败清单（已逐项归因，均非本卡）：
- `tests/client-view.test.ts` 1 / `tests/template-address-injection.test.ts` 2 / `tests/layer-boundary.test.ts` 1 / `tests/application/repository.test.ts` 1 / `tests/typecheck.test.ts` 1 —— **D-1 已列基线**；
- `tests/language-layer.test.ts` 1（基线未列）：断言 `'每节必须标注服务哪条功能点'` 与实际片段 `'覆盖 2 · 每节标注服务哪条功能点'` 不一致——成因在 `design/light/overrides.md` 提示词正文（T-8 卡范围），**非 T-12**（T-12 未触碰提示词片段）；
- 对比基线：`size-budget`（本卡）与 `design-completeness-gate`（T-5）已由红转绿；本卡**未新增失败**。

### 3.6 源码对照（抽取保真）
```
$ git diff HEAD -- src/index.ts --stat
 .../src/index.ts | 146 ++++++-------------------
 1 file changed, 35 insertions(+), 111 deletions(-)
```
- 移除块①（原 L72-105：`PluginConfig` + `dshHomePath` + `nodeIsolationEnabled`）→ plugin-config.ts **逐行等值**（含注释），仅 interface 前加 `export`。
- 移除块②（原 L254-330：三张共享表 + `AgentDeliverer` + `captureHookDeps` + `session/event` 订阅 + 节点-1 日志）→ pm-capture-root.ts（改为 deps 注入，回调体逐字迁移；T-9 的 `onTurnFinished` 一并迁入）。
- index.ts 交叉引用自检：`dshHomePath`/`nodeIsolationEnabled` 在 src 下的**定义**只剩 plugin-config.ts（其余为调用点与再导出）；`AgentDeliverer`/`createSessionEventCaptureHook`/`CaptureHookDeps`/`ToolTraceEntry`/`draftRequirementsFor`/`applyPickupAdvance`/`RequirementRecord` 的 import 已从 index.ts 移除且无残留引用。
- `git status --short`（新文件）：`?? src/plugin-config.ts`、`?? src/wiring/`。

---

## 4. 结论

- **T-12 设计与实现：无偏离。** R1–R11 全部满足设计基线（D-2 + T-12 行 + 架构 L225 + 任务卡验收）：父卡三条验收命令独立复跑 **60/60 绿**、`index.ts` **357 行 ≤400**、`nodeIsolationEnabled` 从 `src/index.ts` 可 import 且与 plugin-config 导出**同一函数**、行为零变更（全量套件未新增失败）。
- 观察项 O-1..O-5 均为无害 / 已由计划授权 / 仅需留痕，不阻断父卡收尾。
- 遗留（不属本卡）：`index.ts` 已 357 行，后续若再往组合根加接线需继续盯 400 行门禁；`tests/language-layer.test.ts` 1 例新红归 T-8 卡收口。

复核人：实施子代理（t-57bfa5）；时间：2026-09-25T02:00+0800
