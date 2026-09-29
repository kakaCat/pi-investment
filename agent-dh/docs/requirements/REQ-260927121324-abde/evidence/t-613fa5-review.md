# t-613fa5 复核记录（父卡 t-f6ee83「需求迁移写路径统一经收敛点并带写时快照」· 阶段 review）

- 复核时间：2026-09-27（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 验收标准（本卡）：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据
- 复核对象（父卡交付面 = 需求迁移写路径的 4 个文件、7 个接口面）：
  - `src/application/internal/confirm-settle.ts`（:293 正常分支 / :320 收尾兜底分支，补 `snap`）
  - `src/http/routers/requirements.ts`（:104-127 `req/move` 五连写改经收敛点；:274-284 看板确认即推进补 `snap` + actor 带 `sessionId`）
  - `src/http/routers/verdicts.ts`（:106-117 验收通过/退回五连写改经收敛点；:179-180 `applyVerdicts` 补第 8 实参 `snap`）
  - `src/application/use-cases/HandleFailure.ts`（:88-94 upstream / :112-118 cancel，直接赋值改经收敛点）
- 设计依据（比对基线）：
  - `design/backend.md` §逐文件改动（需求迁移）（L31-46）
  - `design/interfaces.md` §需求迁移收敛点调用契约（L39-66）、§HTTP 入口（L106-120）、§错误与降级语义（L131-139）
  - `design/architecture.md` §写路径收敛点 1（L83-91）、§根因→修点对照 R2（L72-74）、§逐条功能点 FR-1/FR-2/FR-3（L156-162）、§唯一性纪律（L109-112）
  - 父卡任务卡 `tasks/t-f6ee83.md`「得到什么结果」/「实施方案」
- 复核方式：**只读复核 + 独立复跑 + 源码逐条比对**（不采信上游自述）：`git diff HEAD` 核对改动面、逐条读实现与设计比对、独立复跑父卡 2 条验收命令与架构可证伪命令、`tsc` 过滤

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 后端逐文件改动 | `design/backend.md` L31-46 | confirm-settle :278/:304 两分支补 `snap: captureSnapshot(deps, d.windowKey)`；requirements.ts `req/move` 删五连写改经 `transitionRequirement`（会话码=请求体 `sessionId` → `r.sourceSessionId`，无则诚实不传）；确认即推进补 `snap`+actor 带 sessionId；verdicts.ts :106 五连写改经收敛点、:170 `applyVerdicts` 补第 8 实参 `snap`；HandleFailure :87/:109 改经收敛点，`snap` 用 `req.sourceSessionId` |
| 调用契约表 | `design/interfaces.md` L53-66 | 7 个本卡接口面「现状 → 目标」逐条列出；「有会话上下文必须传，无 → 不结算不带快照」 |
| 语义与降级 | `design/interfaces.md` L131-139 | 会话端口抛错 → 兜底，不阻断主流；无会话上下文 → `snap=undefined`，读路径 `degraded=true`；绝不用 0/单端累计冒充 |
| 收敛点唯一性 | `design/architecture.md` L109-112 | `req.status` 的写只允许出现在 `transitionRequirement` 内 |
| 父卡验收 | `tasks/t-f6ee83.md` | grep 只剩收敛点一处；3 个测试文件通过 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | 弹框批准计划→实施（正常分支）补 `snap: captureSnapshot(deps, d.windowKey)`（backend L33-34、interfaces L59） | `confirm-settle.ts:289-294`，`snap: captureSnapshot(deps, d.windowKey)`（:293）；actor 带 `sessionId: d.windowKey` | **无偏离** |
| R2 | 同路径收尾兜底分支同补 `snap`（backend L33-34、interfaces L60） | `confirm-settle.ts:316-321`，`snap: captureSnapshot(deps, d.windowKey)`（:320） | **无偏离** |
| R3 | 看板「移动」五连写改经 `transitionRequirement`（backend L36-38、interfaces L62） | `requirements.ts:113-122`：原 `req.status/version/updatedAt/updatedBy/recordStatus` 五连写已删，改为 `transitionRequirement(req, to, { at, actor, reason, snap })`（:117） | **无偏离** |
| R4 | 会话码优先级：请求体可选 `sessionId` → `r.sourceSessionId`；都没有诚实不传（backend L38、interfaces L119） | `requirements.ts:90-91` 读可选 `sessionId`（`normalizeText(...) || undefined`）；`:115-116` `sid = sessionId ?? req.sourceSessionId`，`snap` 仅在 `sid !== undefined` 时取；`:119/:121` actor/snap 条件展开 | **无偏离** |
| R5 | 看板确认即推进补 `snap: ctx.deps.tokenSnapshot?.(windowKey)`，`windowKey=confirmed.sourceSessionId`，actor 带 `sessionId`（backend L39-40、interfaces L61） | `requirements.ts:253` `windowKey=confirmed.sourceSessionId`；`:275` `confirmSnap`；`:281` actor 带 sessionId；`:283` 条件传 `snap` | **无偏离** |
| R6 | 看板验收通过/退回五连写改经收敛点 + 快照（backend L42-43、interfaces L63） | `verdicts.ts:106-117`：五连写已删，`transitionRequirement(r, to, {...})`（:110），`verifySnap` 取 `r.sourceSessionId`、非空才取（:108-109/:116） | **无偏离** |
| R7 | 看板逐项裁决 `applyVerdicts` 补第 8 实参 `snap`（backend L44、interfaces L64） | `verdicts.ts:177-181`：`verdictSnap` 取 `r.sourceSessionId`，作为第 8 实参传入；`internal/verdicts.ts:95-105` 第 8 形参即 `snap?: TokenSnapshot`，`:142-149` 用它结算离开节点 | **无偏离** |
| R8 | 失败处置 upstream/cancel 两处直接赋值改经收敛点，`snap` 用 `req.sourceSessionId`，取不到不传（backend L45-46、interfaces L65） | `HandleFailure.ts:88-94`（`snapshotForWindow(deps, req.sourceSessionId)` + 条件展开）与 `:112-118`：原 `assertReqTransition`+`req.status=`+`recordStatus` 已删，只留 `transitionRequirement` | **无偏离** |
| R9 | 收敛点唯一性：`req.status`/`r.status` 的写只允许在 `transitionRequirement` 内（architecture L109-112） | `grep -rn "req\.status = \\|r\.status = " src/application src/http` → 仅 `token-usage.ts:291`（`transitionRequirement` 体内）+ 同文件 :278 的**注释**行；无其它写入点 | **无偏离**（计数口径见观察项 O-1） |
| R10 | 不阻断主流：会话端口抛错不得让迁移失败（interfaces L135） | HTTP 4 个面走 `ctx.deps.tokenSnapshot?.()`（生产装配 `src/index.ts:430-436` 自带 try/catch → undefined，见 O-3）；confirm-settle 用 `captureSnapshot`（自带 try/catch → `unavailable`）；HandleFailure 用 `snapshotForWindow`（委托 `captureSnapshot`，永不抛） | **无偏离**（错误语义差异见 O-3） |
| R11 | 无会话上下文诚实不传快照，禁止 0/单端累计冒充（interfaces L136、architecture L143） | 三处均以「取不到 → `undefined` → 条件展开不传」实现；`HandleFailure` 无 `sourceSessionId` 时 `snapshotForWindow` 直接返回 undefined | **无偏离** |
| R12 | 不新增字段、不改 schemaVersion（architecture L28/L184） | `grep REQBOARD_SCHEMA_VERSION` → `shared/protocol.ts:1220` 仍为 8；本卡 diff 未碰 `shared/protocol.ts` | **无偏离** |
| R13 | 端侧不动（backend L11-12、interfaces L120） | `git diff HEAD --stat -- src/client` → 无输出 | **无偏离** |
| R14 | 父卡验收命令 2：3 个测试文件通过 | `token-transition-helper(3) + verdicts-and-rework(10) + confirm-settle-plan-persist(2)` = **15 passed / 0 failed**（§3.2） | **无偏离** |
| R15 | 架构可证伪判据：4 个 token 测试文件 0 failed | `ledger-v6-token(8) + token-usage(11) + token-transition-helper(3) + token-fallback(3)` = **25 passed / 0 failed**（§3.3） | **无偏离** |

---

## 2. 偏离与观察项

**总判定：t-f6ee83 设计与实现——无偏离（R1–R15 全过）。下列 3 条为不阻断的观察项（grep 计数含注释行 / 冗余双校验 / HTTP 面错误语义差异），均不影响本卡契约与父卡验收。**

### O-1（grep 计数口径：父卡「只剩一处」实为 2 行匹配，其中 1 行为注释 · 不构成偏离）
父卡验收命令 `grep -rn "req\.status = \\|r\.status = " src/application src/http` 实测输出 2 行，均由 `token-usage.ts` 产生：
```
src/application/internal/token-usage.ts:278:  //    都记得校验。此前本函数直接 `req.status = to` 无任何校验，于是：
src/application/internal/token-usage.ts:291:  req.status = to
```
:278 是解释历史事故的**注释**（不含可执行赋值），:291 是 `transitionRequirement` 体内的**唯一真实写点**。
**判定：不构成实现偏离** —— 父卡实现方案本身就把该注释与写点放在同一收敛点；「一处」指**写入点**唯一（且文件唯一），满足 `design/architecture.md` L111 的唯一性纪律。上游联调记录 `t-b36ec5-integrate.md` §2 的「只剩收敛点自身一处」表述未区分注释行，属表述精度问题，非实现问题。

### O-2（`requirements.ts` 冗余双校验 · 不构成偏离）
`handleReqMove` 在 `req/move` 里既保留 mutate 前的 `assertReqTransition(req.status, to, actor)`（`requirements.ts:106`），`transitionRequirement` 内部（`token-usage.ts:283-285`）又做一次同参数校验。两次断言完全等价（`actor` 与 `opts.actor.kind` 同源），首次即拦截非法转移，**行为与设计一致、无副作用**。设计 `backend.md` 未要求删除原有显式校验；`assertArtifactGates` 的双检是既有设计明确的「预检+复查防并发漂移」模式（同文件注释 :92-93）。**判定：不构成偏离**（建议后续清理时可去掉重复断言，纯整洁性）。

### O-3（HTTP 面与 use-case 面的错误语义差异 · 设计自身的选择 · 不构成偏离）
`confirm-settle` / `HandleFailure` 用 `captureSnapshot`（端口抛错 → `{source:'unavailable'}`，仍落账、读路径据此判 degraded）；4 个 HTTP 面用 `ctx.deps.tokenSnapshot?.(...)`（生产装配 `src/index.ts:430-436` 捕获异常 → `undefined`，即「没有快照」而非「试过拿不到」）。
**判定：不构成偏离** —— `design/backend.md` L39 与 `interfaces.md` L61 对 HTTP 面**逐字**指定了 `ctx.deps.tokenSnapshot?.(windowKey)`，实现忠实执行设计；且两条降级形态在 FR-7 的 `hasSnapshotGap`（缺失或 `unavailable` 同等计 degraded）下**读路径结果一致**，无功能损失。

### 附：上游联调记录笔误（不影响本卡判定）
`t-b36ec5-integrate.md` §1 记「本卡交付面…共 **6 个文件**、7 个接口面」；本卡实测改动面为 **4 个文件**（`git diff --stat`：confirm-settle / HandleFailure / requirements / verdicts，22+31+22+27 行级增删）。7 个接口面全部落在这 4 个文件内，覆盖结论不受影响，属联调记录笔误。

---

## 3. 复核证据（命令与输出）

### 3.1 收敛点唯一性（父卡验收命令 1，独立复跑）
```
$ cd packages/web/dsh-pmboard
$ grep -rn "req\.status = \|r\.status = " src/application src/http
src/application/internal/token-usage.ts:278:  //    都记得校验。此前本函数直接 `req.status = to` 无任何校验，于是：
src/application/internal/token-usage.ts:291:  req.status = to
```
唯一真实写入点 = `token-usage.ts:291`（`transitionRequirement` 体内）；:278 为注释。

### 3.2 父卡验收命令 2（3 个测试文件独立复跑）
```
$ npx vitest run tests/token-transition-helper.test.ts tests/verdicts-and-rework.test.ts tests/confirm-settle-plan-persist.test.ts
 ✓ tests/token-transition-helper.test.ts (3 tests) 2ms
 ✓ tests/confirm-settle-plan-persist.test.ts (2 tests) 23ms
 ✓ tests/verdicts-and-rework.test.ts (10 tests) 138ms
 Test Files  3 passed (3)
      Tests  15 passed (15)      # exit 0
```

### 3.3 架构可证伪命令（4 个 token 测试文件独立复跑）
```
$ npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts
 ✓ tests/token-transition-helper.test.ts (3 tests)
 ✓ tests/token-usage.test.ts (11 tests)
 ✓ tests/token-fallback.test.ts (3 tests)
 ✓ tests/ledger-v6-token.test.ts (8 tests)
 Test Files  4 passed (4)
      Tests  25 passed (25)     # exit 0
```
（对照 `requirement.md` L40 的起始态「3 failed | 16 passed」——3 例红已随实现转绿。）

### 3.4 改动面（`git diff HEAD`，本卡 4 文件）
```
$ git diff HEAD --stat -- src/http/routers/requirements.ts src/http/routers/verdicts.ts \
    src/application/use-cases/HandleFailure.ts src/application/internal/confirm-settle.ts
 src/application/internal/confirm-settle.ts     | 13 +++++++++
 src/application/use-cases/HandleFailure.ts     | 31 +++++++++++++---------
 src/http/routers/requirements.ts               | 22 ++++++++++-----
 src/http/routers/verdicts.ts                   | 27 ++++++++++++-------
 4 files changed, 65 insertions(+), 28 deletions(-)
```
逐 hunk 核对：confirm-settle 两分支各补 1 行 `snap`（另一 hunk 为并行工作线的幂等守卫，非本卡）；HandleFailure 两分支以 `transitionRequirement` 替换「assert + status= + version/updatedAt/updatedBy + recordStatus」；requirements 三处（sessionId 读入 / 五连写 → 收敛点 / 确认即推进 snap+actor）；verdicts 两处（五连写 → 收敛点 / applyVerdicts 第 8 实参）。

### 3.5 数据契约与端侧（不越界）
```
$ grep -rn "REQBOARD_SCHEMA_VERSION" src/ | head -1
src/shared/protocol.ts:1220:export const REQBOARD_SCHEMA_VERSION = 8
$ git diff HEAD --stat -- src/client
（无输出）
```

### 3.6 类型面独立复核
```
$ npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "confirm-settle|HandleFailure|verdicts.ts"
（无输出）                                   # 本卡 4 文件中 3 个命中 0 条
$ npx tsc --noEmit -p tsconfig.json 2>&1 | grep "src/http/routers/requirements.ts"
src/http/routers/requirements.ts(437,23): error TS2352: Conversion of type '{...}' to type 'UseCaseDeps' ...
```
该唯一报错在 `handleReqDecompose` 的 `boardDeps` 区域（:437），不在本卡任何 diff hunk 内（本卡 hunk 为 :87/:110/:271），属仓库存量类型债（`tsc` 全仓大量同类存量报错），**非本卡引入**。

---

## 4. 结论

- **t-f6ee83「需求迁移写路径统一经收敛点并带写时快照」设计与实现：无偏离。** R1–R15 全部满足设计基线（`backend.md` §逐文件改动 + `interfaces.md` §调用契约/§HTTP 入口/§错误与降级 + `architecture.md` §收敛点1/§唯一性纪律/§FR-1/2/3 + 父卡「得到什么结果」/「实施方案」）：7 个接口面逐条落位、会话码优先级与「取不到诚实不传」一致、`req.status` 写点唯一、schema 保持 8、端侧零改动。
- 无任何功能偏离；唯一与设计文本的差异均为**表述/整洁性**层面（O-1 grep 计数含注释、O-2 冗余双校验、O-3 HTTP 面错误语义系设计逐字指定），不构成实现偏离。
- 遗留（不属本卡）：FR-8 结构守卫单测（`tests/requirement-transition-guard.test.ts`）在 t7（`tasks/t-9b87a6.md`）范围，尚未落盘；FR-6 派生推进提供者、FR-7 读路径 degraded 分属 t5/t6，均不在本卡范围。
- 联调记录 `t-b36ec5-integrate.md` 的「6 个文件」为笔误（实测 4 个），不影响 7 个接口面的覆盖结论。

复核人：实施子代理（t-613fa5）；时间：2026-09-27
