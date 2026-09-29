# t-f9462e 复核记录（父卡 t-806d6e「新增执行快照收敛助手（任务执行唯一写入口）」· 阶段 review）

- 复核时间：2026-09-27（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 验收标准（本卡）：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据
- 复核对象（t1 交付面 = `src/application/internal/token-usage.ts` 的 6 个新增导出）：
  - `openExecution(task, spec, snap?)`（:148）
  - `closeExecutions(task, opts, snap?)`（:175）
  - `refreshRunningExecution(task, snap, sessionId?)`（:192）
  - `snapshotForWindow(deps, windowKey?)`（:207）
  - `safeWindowKey(deps, exec?)`（:216）
  - `snapshotProviderFor(deps, windowKey?)`（:230）
  - 新增契约测试 `tests/execution-snapshot-helpers.test.ts`（14 例）
- 设计依据（比对基线）：
  - `design/interfaces.md` §执行快照助手（L68-104）、§写路径助手（L13-37）、§错误与降级语义（L131-139）
  - `design/architecture.md` §收敛点 2（L93-100）、§唯一性纪律（L109-112）、§数据流（L114-135）
  - `design/data-model.md` §② ExecutionTokenUsage（L42-49）、§④ ExecutionRecord（L59-69）、§不变式（L71-80）
  - `design/backend.md` §逐文件改动（任务执行）（L48-57）、§自动链与无会话路径（L59-68）
  - 父卡任务卡 `tasks/t-806d6e.md`「得到什么结果」/「实施方案」（L16、L19）
- 复核方式：**只读复核 + 独立复跑 + 源码/signature 逐条比对**（不采信上游自述）：`git diff` 核对改动面、逐条比对 6 个导出的签名与语义、独立复跑 3 组测试命令与 `tsc` 过滤

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 接口设计 | `design/interfaces.md` §执行快照助手 | `openExecution` 落记录+写 start（born-failed 不写）；`closeExecutions` 闭合全部 running+写 end/delta，返回条数；`refreshRunningExecution` 刷最近一条同会话 running 的 end/delta（不改 outcome），返回 boolean；**snap=undefined → 只落/闭合记录、不写任何 token 字段**；**不抛** |
| 接口设计 | `design/interfaces.md` §写路径助手 | `snapshotForWindow`（缺失/空串→undefined，取不到→unavailable）；`safeWindowKey`（解析不到→undefined）；`snapshotProviderFor`（显式窗口码优先→退回 `req.sourceSessionId`→都无 undefined）；**永不抛** |
| 架构 | `design/architecture.md` L62/L93-100 | 任务执行收敛点 = 上述 3 个执行助手；`beginExecutionToken` 复活（不再是死代码） |
| 架构 | `design/architecture.md` L109-112 | 唯一性纪律：`task.executions` 的增改与 `execution.tokenUsage` 的写只允许出现在 `application/internal/token-usage.ts` |
| 数据模型 | `design/data-model.md` L42-49/L74-76 | 缺失≠0；delta 三条件（两端 projection + 会话不冲突，任一方 sessionId 缺省视为兼容）；**不新增字段、schemaVersion 保持 8** |
| 后端实施 | `design/backend.md` L50-51 | 执行助手内部调用既有 `beginExecutionToken`/`endExecutionToken`（这两个仍是 token 字段唯一写点） |
| 父卡方案 | `tasks/t-806d6e.md` L19 | 6 个导出；born-failed 不写 start；snap=undefined 不写 token 字段；不抛错 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | 落点/命名：6 个助手全部在 `src/application/internal/token-usage.ts`（interfaces L15、backend L18） | 6 个导出逐字落在该文件（:148/:175/:192/:207/:216/:230）；父卡 grep 计数 = **6** | **无偏离**（§3.1/§3.5） |
| R2 | `openExecution(task, spec, snap?): ExecutionRecord`；落记录+写 start（interfaces L80、L71） | 签名一致；返回被 push 的同一对象（测试 `e === t.executions[0]`）；running+snap 可得时经 `beginExecutionToken` 写 start 并清 delta | **无偏离**（§3.2） |
| R3 | born-failed（`outcome==='failed'`）**不写 start**，直接以终止记录落账（interfaces L93-94、父卡 L19） | `outcome==='failed'` 时 `endedAt=at`、带可选 `error`，**不调用** `beginExecutionToken`，`tokenUsage` 缺省 | **无偏离**。定值证据：`execution-snapshot-helpers.test.ts:33-40`（`tokenUsage` undefined） |
| R4 | `closeExecutions(task, opts, snap?): number`；闭合**全部** running、写 end/delta，返回条数；snap=undefined 只闭合（interfaces L82-84、L92） | 签名/返回一致；`for` 全量闭合、已闭合（非 running）跳过；snap 有值才 `endExecutionToken`；`opts.error` 仅在给出时写 | **无偏离**（§3.2） |
| R5 | `refreshRunningExecution(task, snap, sessionId?): boolean`；命中最近一条**同会话** running 写 end/delta、**不改 outcome**；未命中不写（interfaces L86-87） | 从尾部反查，命中即写并 `true`；`outcome` 保持 `running`；`sessionId` 缺省=不限会话；未命中 `false` 且零写 | **无偏离**（§3.2） |
| R6 | 内部**一律**调既有 `beginExecutionToken`/`endExecutionToken`，token 字段唯一写点不散（backend L50-51、父卡 L19） | 全部 token 字段写入只经这两个函数（`:159`/`:182`/`:197`）；助手自身不直接写 `tokenUsage` 字段 | **无偏离**（§3.3） |
| R7 | snap=`undefined` → 只落/闭合执行记录，**不写任何 token 字段**（interfaces L92、父卡 L19） | `openExecution`/`closeExecutions` 在 snap undefined 时不创建 `tokenUsage`；测试断言 `tokenUsage`/`end`/`delta` 为 undefined | **无偏离**（§3.2） |
| R8 | `snapshotForWindow(deps, windowKey?)`：缺失/空串→undefined（不伪造）；有码取不到→`captureSnapshot` 兜底 `unavailable`（interfaces L21-22、L36） | `typeof !== 'string' \|\| length===0 → undefined`；否则 `captureSnapshot`（内部 try/catch → unavailable） | **无偏离**（§3.2） |
| R9 | `safeWindowKey(deps, exec?)`：无 exec/端口抛错→undefined；`'system'` 视为无（interfaces L25、调用点表 L103、backend L63） | `try { deps.session.windowKey(exec) }`；非字符串/空串/`'system'`→undefined；异常→undefined | **无偏离**（§3.2；`'system'` 口径的出处见观察项 O-3） |
| R10 | `snapshotProviderFor(deps, windowKey?)`：显式窗口码优先，退回 `req.sourceSessionId`，都无→undefined | 与设计一致；显式码为空串时退回 `sourceSessionId`；都无时不触达端口（`snapshotForWindow` 直接 undefined） | **无偏离**（§3.2） |
| R11 | 永不抛（interfaces L36、父卡 L19）：快照是旁路证据 | 6 个函数无可抛路径：执行助手不碰端口；两个解析函数各自 try/catch；提供者委托前两者 | **无偏离**（§3.1） |
| R12 | 不新增字段、不改 schemaVersion（保持 8）（data-model L10/L22） | `git diff` 纯新增 132 行：只加类型 import `TaskRecord` + 2 个入参 interface + 6 个函数；未改 `shared/protocol.ts` 的 token 类型、未动 schemaVersion | **无偏离**（§3.4） |
| R13 | delta 不变式：两端 projection + 会话不冲突（任一方 sessionId 缺省视为兼容）才产出，否则缺省（data-model L74-76） | 复用既有 `endExecutionToken`，其 `sameSession` 判定 = `start.sessionId===undefined \|\| snap.sessionId===undefined \|\| 相等`，不满足则 `delete usage.delta` | **无偏离**（§3.3；未改动既有口径） |
| R14 | `beginExecutionToken` 不再是死代码（architecture L16/L62） | `grep -rn beginExecutionToken src/` → 定义 1 处 + **真实调用方** `token-usage.ts:159`（不再是"只有定义没有调用方"） | **无偏离**（§3.3） |
| R15 | 父卡「得到什么结果」：grep 计数 6 | 实测 6（§3.1） | **无偏离** |

---

## 2. 偏离与观察项

**总判定：t1 设计与实现——无功能偏离（R1–R15 全过）；下列 5 条为不阻断的观察项（设计稿计数自相矛盾 / 跨卡收口 / 描述分散 / 设计未穷举测试文件 / 边界细化），均不影响本卡契约与父卡验收。**

### D-1（设计稿自相矛盾 · 计数"4" vs 逐条"6" · 不构成实现偏离）
`design/interfaces.md:10` 与 `design/backend.md:18` 的**汇总句**写「本次只新增 4 个内部助手函数」「新增 4 个助手」；但同一文档的逐条定义是 **6 个新增导出**（interfaces §写路径助手 3 个标「新增」+ §执行快照助手 3 个；backend L18 所在行亦指向同一模块），父卡实施方案与 `decomposition.md` 亦写 6 个导出。

**判定：不构成实现偏离** —— 实现逐字对应**设计的逐条定义**（R1–R10 全过），并非实现多写；「4」是设计汇总句的计数笔误（疑似把 §写路径助手代码块里的 4 条目——其中 `captureSnapshot` 是既有——当成了新增数，漏计 §执行快照助手的 3 个）。**建议**：t10 同步说明书/RTM 时把两处汇总改为 6（文档面修订，无代码影响）。

### O-1（跨卡观察 · ReportTask 尚未收口到 refreshRunningExecution · 属 t3/t5 范围）
现状 `src/application/use-cases/ReportTask.ts:136` 仍**直接** `endExecutionToken(e, snap)`，未改经新助手 `refreshRunningExecution`。设计/拆分已明确这是 t3（`decomposition.md` 改动盘点：`ReportTask.ts` :136 改 refreshRunningExecution；`design/backend.md` L57 同）。t1 交付面只提供助手，**不要求**接线。**判定：不构成 t1 偏离**；但诚实提示——在 t3 接线前，"任务执行唯一入口"（FR-8）尚未闭合，`src/` 内仍有助手之外的执行收尾调用方，随 t3 收口。

### O-2（描述分散 · `safeWindowKey` 的 `'system'` 口径 · 不构成偏离）
`design/interfaces.md` §写路径助手对 `safeWindowKey` 的注释（L25）只写「无 exec / 端口抛错→undefined」，未提 `'system'`；但同文件调用点表 L103（`'system'` 视为无）与 `design/backend.md` L63（`'system'` 不当作真实会话）明确要求。实现按**更严**的口径执行（含非字符串脏值也判 undefined）。**判定：不构成偏离**；建议后续把口径归并到接口签名注释处。

### O-3（覆盖口径 · 新增契约测试文件未列于设计用例表 · 不构成偏离）
设计 `design/test-cases.md` 的 20 例清单（T-1…T-20）「实际文件」列到 `tests/token-usage.test.ts`、`tests/ledger-v6-token.test.ts` 等，**未列** `tests/execution-snapshot-helpers.test.ts`；该文件是 t1 新增的 14 例助手契约测试（覆盖 R2–R10）。**判定：不构成偏离**——设计未穷举测试文件，新增属**补充覆盖**且与既有用例无冲突（25/25 绿，§3.2）。

### O-4（设计未定义边界的实现细化 · 不构成偏离）
`refreshRunningExecution` 的会话过滤按 `e.sessionId !== sessionId` **严格**匹配（执行记录 `sessionId` 缺省时，显式 `sessionId` 查询不命中）；而 `endExecutionToken` 的 delta 兼容判定把任一方的 `sessionId` 缺省视为兼容。两处口径不对称。设计未定义「执行记录 sessionId 缺省时是否算同会话」这一边界。**判定：不构成偏离**（设计未承诺该边界），实现选择严格匹配并由契约测试锁定（`execution-snapshot-helpers.test.ts:90-95`）；建议在接口文档补一句，避免后续误读。

### O-5（无害的存量注释 · 不构成偏离）
`token-usage.ts` 模块头仍标注「REQ-a33899 t3」，文件现同时承载 REQ-260927121324-abde t1 的助手块（该块自带 banner 注释）。纯注释，无行为影响；可在后续文档同步时顺手更新。

---

## 3. 复核证据（命令与输出）

### 3.1 导出面与不抛性（源码 + grep 独立复核）
```
$ grep -nE "export function (openExecution|closeExecutions|refreshRunningExecution|snapshotForWindow|safeWindowKey|snapshotProviderFor)" src/application/internal/token-usage.ts | wc -l
       6
$ grep -nE "export function (openExecution|...)" src/application/internal/token-usage.ts
148:openExecution  175:closeExecutions  192:refreshRunningExecution
207:snapshotForWindow  216:safeWindowKey  230:snapshotProviderFor
```
不抛性：执行助手（:148/:175/:192）不触达端口，仅操作内存对象；`snapshotForWindow`（:207）委托既有 `captureSnapshot`（内部 try/catch → `unavailable`）；`safeWindowKey`（:216）自带 try/catch；`snapshotProviderFor`（:230）只委托前两者。

### 3.2 t1 契约测试独立复跑（真实模块 + 内存端口）
```
$ cd packages/web/dsh-pmboard
$ npx vitest run tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts
 ✓ tests/token-usage.test.ts (11 tests) 3ms
 ✓ tests/execution-snapshot-helpers.test.ts (14 tests) 4ms
 Test Files  2 passed (2)
      Tests  25 passed (25)
   Duration  250ms        # exit 0
```
14 例助手契约覆盖：openExecution running/born-failed/no-snap（3）、closeExecutions 闭合/无快照/跳过已闭合（2）、refresh 命中/未命中/缺省会话（3）、snapshotForWindow 缺失空串/抛错（2）、safeWindowKey 正常与哨兵/脏值（2）、snapshotProviderFor 优先与回落（1）、unavailable 不产 delta（1）。

### 3.3 token 字段唯一写点复核
```
$ grep -rn "beginExecutionToken" src/
src/application/internal/token-usage.ts:86  export function beginExecutionToken(...)
src/application/internal/token-usage.ts:159   if (outcome === 'running' && snap !== undefined) beginExecutionToken(...)   # 真实调用方（复活）
$ grep -rn "endExecutionToken" src/
src/application/internal/token-usage.ts:96  （定义）
src/application/internal/token-usage.ts:182 / :197  （closeExecutions / refreshRunningExecution 内调用）
src/application/use-cases/ReportTask.ts:136  （存量调用方 → 见 O-1，t3 收口）
```
助手块内 token 字段写入只经 `beginExecutionToken`/`endExecutionToken`（助手自身不直接写 `tokenUsage`）；`beginExecutionToken` 已不再是无调用方的死代码。

### 3.4 改动面（纯新增、无既有语义改动、未碰数据契约）
```
$ git diff --stat -- agent-dh/packages/web/dsh-pmboard/src/application/internal/token-usage.ts
 .../token-usage.ts | 132 +++++++++++++++++++++
 1 file changed, 132 insertions(+)
$ git status --porcelain -- src tests   # t1 相关两行
 M agent-dh/packages/web/dsh-pmboard/src/application/internal/token-usage.ts
?? agent-dh/packages/web/dsh-pmboard/tests/execution-snapshot-helpers.test.ts
```
diff 仅含：`+ type TaskRecord` import、`OpenExecutionSpec`/`CloseExecutionsOpts`、6 个函数与注释；**0 删除行**，未改既有 `captureSnapshot`/`beginExecutionToken`/`endExecutionToken`/`transitionRequirement`。工作区其余改动（confirm-settle/ExecuteTask/ports/PendingConfirmRegistry 等）分属并行工作线（t2/t5 等），t1 未越界。

### 3.5 父卡验收命令（t1 分包口径）
```
$ grep -nE "export function (openExecution|closeExecutions|refreshRunningExecution|snapshotForWindow|safeWindowKey|snapshotProviderFor)" src/application/internal/token-usage.ts | wc -l
       6                        # 期望 6，实际 6
```

### 3.6 类型面独立复核
```
$ npx tsc --noEmit -p tsconfig.json 2>&1 | tee /tmp/t1_tsc.txt | grep -E "token-usage|execution-snapshot-helpers"
（无输出）                        # t1 两文件命中 0 条
$ grep -cE "error TS" /tmp/t1_tsc.txt
     118                          # 全部为与 t1 无关文件的存量报错
```

### 3.7 关联既有用例当前态（诚实声明：非本卡交付面）
```
$ npx vitest run tests/ledger-v6-token.test.ts
 Test Files  1 failed (1)
      Tests  3 failed | 5 passed (8)
```
3 例红（写时快照：任务执行）原因是**调用方尚未改经助手**（`MoveTask.executions.push` 未替换），属 t3 卡（`tasks/t-030788.md`）接线范围——与联调卡 `evidence/t-6b6559-integrate.md` §4 的声明一致；t1 的 6 个导出契约已由 §3.2 全绿锁定。

---

## 4. 结论

- **t1「新增执行快照收敛助手」设计与实现：无偏离。** R1–R15 全部满足设计基线（interfaces §执行快照助手/§写路径助手 + architecture §收敛点2/唯一性纪律 + data-model §②/§④/不变式 + backend §逐任务执行 + 父卡「得到什么结果」/「实施方案」）：6 个导出逐字落点、签名与语义一致、内部只经 `beginExecutionToken`/`endExecutionToken`、born-failed 不写 start、snap=undefined 不写 token 字段、永不抛、纯新增 132 行且未碰数据契约（schemaVersion 保持 8）。
- 唯一与设计文本的不一致是 **摘要计数**（interfaces L10 / backend L18 写「4 个助手」vs 逐条与实现均为 6），属**设计稿笔误**，不构成实现偏离；建议 t10 文档同步时更正。
- 观察项 O-1（ReportTask 仍直调 `endExecutionToken`）为 t3/t5 范围的正常未收口，**不阻断本卡**；O-2..O-5 为描述分散/覆盖补充/边界细化/存量注释，均无害。
- 遗留（不属 t1）：`tests/ledger-v6-token.test.ts` 3 例红随 t3 接线转绿；FR-8「唯一入口」在 t3 接线完成后闭合。

复核人：实施子代理（t-f9462e）；时间：2026-09-27
