# t-bf3d34 复核记录（REQ-260927121324-abde · 父卡 t-9b87a6「新增执行与迁移收敛的结构守卫单测」· 阶段 review）

- 复核时间：2026-09-27 15:12（CST）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `/Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard`
- 验收标准（本卡）：**对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据**
- 复核对象（t-bf3d34 交付面 = 研发子卡 t-d108cf 新增的 2 个结构守卫单测，git 状态为 untracked/新增）：
  - `packages/web/dsh-pmboard/tests/execution-token-guard.test.ts`（108 行）
  - `packages/web/dsh-pmboard/tests/requirement-transition-guard.test.ts`（109 行）
- **总判定：核心设计落点 7/7 全部落位，无阻断性偏离、无需返工**；另识别 **2 条轻微偏离（D-1 匹配前缀比设计文本更宽 → 潜在误报面；D-2 注释需求归属不一致）** + 4 条**残余边界**（设计文本只承诺字面式样的已知边界），均不阻断本卡验收。

## 0. 设计基线（R-013：标注来源与时点）

设计基线取自以下文档（读取时点 2026-09-27 15:10–15:12 CST）：

| 出处 | 位置 | 对本卡的约束 |
|---|---|---|
| 本卡实施方案 | 子卡 t-bf3d34 卡片 `implementation` | 新增 execution-token-guard（src 全部 .ts，排除 token-usage.ts，断言无 `executions.push(` 与 tokenUsage 赋值，读引用不算）；新增 requirement-transition-guard（src/application+src/http 内无 `req.status`/`r.status` 直接赋值，收敛点内除外）；违规时打印文件与行号 |
| `design/backend.md` §结构性守卫（行 77–85） | `docs/requirements/REQ-260927121324-abde/design/backend.md` | 同上；补充：`tokenUsage ??=` / `.tokenUsage = `，`domain/legacy/LegacyStatus.ts` 不在扫描范围 |
| `design/architecture.md` §唯一性纪律（行 ~105） | 同目录 `design/architecture.md` | `src/` 内 `execution.tokenUsage` 的写与 `task.executions` 的增改只允许出现在 `application/internal/token-usage.ts` |
| `design/test-cases.md` T-18/T-19（行 57–58） | 同目录 `design/test-cases.md` | T-18→`tests/execution-token-guard.test.ts`；T-19→`tests/requirement-transition-guard.test.ts` |

被测实现（源文件，读取时点同上）：`tests/execution-token-guard.test.ts`、`tests/requirement-transition-guard.test.ts`（均 untracked 新增，未提交）。

## 1. 逐条偏离结论（设计点 → 实现 → 判定）

| 编号 | 设计要求 | 实现事实 | 判定 |
|---|---|---|---|
| P-1 扫描范围（执行守卫） | 读 `src` 下全部 `.ts`，排除 `application/internal/token-usage.ts` | `collectTs(SRC)` 递归收集；`scanned = allFiles.filter(f => f !== CONVERGENCE)`；断言 `scanned.length === allFiles.length - 1` | **无偏离**。实测 src 共 299 个 `.ts`，排除后 298；排除项写错路径时 `scanned.length` 断言会直接变红（防路径写错假绿） |
| P-2 扫描范围（迁移守卫） | 读 `src/application` 与 `src/http` | `collectTs(APP)` + `collectTs(HTTP)`，排除 `token-usage.ts` | **无偏离**。实测 121 个 `.ts`，排除后 120；`domain/legacy` 天然不在扫描范围，与设计注一致 |
| P-3 禁用式样（执行） | 不含 `executions.push(` 与 `tokenUsage` 赋值，读引用不算 | 正则 `executions\s*\.\s*push\s*\(`、`\btokenUsage\s*(?:\?\?=\|\+=\|-=\|\|\|=\|&&=\|=)(?!=)`；注释经 TS 词法器剥离（保留换行，行号不变） | **无偏离（且为超集）**。除设计点名的 `??=`/`=` 外还覆盖 `+=`/`-=`/`\|\|=`/`&&=`；`const n = req.tokenUsage?.totals ?? 0`、`if (req.tokenUsage === undefined)`、`interface X { tokenUsage?: … }`、注释反例均不误报（守卫内建反例断言实测通过） |
| P-4 禁用式样（迁移） | 不含 `req.status` / `r.status` 直接赋值 | `\breq\.status\s*=(?!=)`、`\br\.status\s*=(?!=)`；注释剥离 | **无偏离**。`===`/`!==`/读取/注释不匹配；`myreq.status =` 因 `\b` 不误报 |
| P-5 报点格式 | 违规时断言信息打印文件与行号 | 拼 `relative(PKG_ROOT, file) + ':' + '第 N 行 · 式样 → 原文`，作为 `expect(violations, msg).toEqual([])` 的 message | **无偏离**。故障注入实测逐字打印 `src/http/__guard_fault_probe__.ts:第 3 行 · executions.push( → task.executions.push(exec)`（详见 §2） |
| P-6 唯一收敛点例外 | `token-usage.ts` 收敛点内部除外 | 两守卫各自排除 `CONVERGENCE`，并**额外断言该文件仍存在且仍承担写点**（`openExecution`/`closeExecutions`/`task.executions.push(execution)`；`transitionRequirement`/`req.status = to`） | **无偏离**（额外护栏属增强，防「删掉收敛点让守卫空过」的假绿，方向与设计 §唯一性纪律一致） |
| P-7 用例登记与纳入套件 | T-18/T-19 对应上述两个文件 | 两文件位于设计指定路径；`vitest.config.ts` `include: ['tests/**/*.test.ts']` → 自动纳入 `pnpm test` | **无偏离**。常驻回归防线真实生效，非仅在显式命令下运行 |

## 2. 独立复核证据（命令与输出摘要）

数据时点：2026-09-27 15:10–15:12（CST）；工作目录 `packages/web/dsh-pmboard`。

**① 正向复跑（父卡验收命令）**

    $ npx vitest run tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts
     ✓ tests/requirement-transition-guard.test.ts (4 tests) 68ms
     ✓ tests/execution-token-guard.test.ts (4 tests) 123ms
     Test Files  2 passed (2) / Tests  8 passed (8)      ← exit 0

**② 故障注入实测（本人独立执行，探针跑完即删；验证「守卫真会变红」而非永不报警）**

    临时写入 src/http/__guard_fault_probe__.ts（3 处违规）后复跑：
     × 需求状态迁移结构守卫 · 唯一收敛点 > src/application 与 src/http 内无 req.status / r.status 直接赋值
       → src/http/__guard_fault_probe__.ts:第 9 行 · req.status 直接赋值 → req.status = to
     × 执行/token 结构守卫 · 唯一写入口 > src 下（token-usage.ts 之外）无 executions.push( 与 tokenUsage 赋值
       → src/http/__guard_fault_probe__.ts:第 3 行 · executions.push( → task.executions.push(exec)
       → src/http/__guard_fault_probe__.ts:第 6 行 · tokenUsage 赋值 → execution.tokenUsage = usage
     Test Files  2 failed (2) / Tests  2 failed | 6 passed (8)
    $ rm -f src/http/__guard_fault_probe__.ts && 复跑 → Test Files 2 passed / Tests 8 passed（绿灯恢复，探针无残留）

**③ 交叉核查（防扫描器假绿）**

    $ find src -name '*.ts' | wc -l                              → 299
    $ find src/application src/http -name '*.ts' | wc -l         → 121
    $ grep -rn "req.status = \|r.status = " src/application src/http
      src/application/internal/token-usage.ts:278   （注释）
      src/application/internal/token-usage.ts:291   （收敛点唯一实现 req.status = to）
    $ grep -rn "beginExecutionToken" src
      src/application/internal/token-usage.ts:86  （定义）:114（注释）:159（openExecution 内调用）
      → `grep` 结论与守卫判定一致，收敛点唯一性属实。

**④ 类型与套件接线**

    $ npx tsc --noEmit -p tsconfig.json  → 本包共 114 条既有 TS error（分布于其它在改文件），
      过滤 execution-token-guard / requirement-transition-guard → 0 命中（两守卫文件类型干净）。
    $ cat vitest.config.ts  → include: ['tests/**/*.test.ts']（两守卫自动纳入 pnpm test）

**⑤ 正则边界探针（本人用 node 复现守卫正则，定位 D-1 与残余边界）**

    /\btokenUsage\s*(?:\?\?=|\+=|-=|\|\|=|&&=|=)(?!=)/：
      MATCH   "execution.tokenUsage = usage"        （本应命中 ✓）
      MATCH   "const tokenUsage = { a: 1 }"          （局部变量声明，误报面 ← D-1）
      no-hit  "const n = req.tokenUsage?.totals ?? 0"（读引用不误报 ✓）
      no-hit  "task?.executions?.push(exec)"         （等价逃逸 ← R-3）
      no-hit  "task.executions[\"push\"](exec)"      （等价逃逸 ← R-3）
      no-hit  "obj[\"tokenUsage\"] = x"               （等价逃逸 ← R-3）
    /\breq\.status\s*=(?!=)/：
      MATCH   "req.status = to"                      （本应命中 ✓）
      no-hit  "req.status === to" / "const s = req.status"（不误报 ✓）
      no-hit  "req.status += x" / "req[\"status\"] = to" / "target.status = to"（残余边界 ← R-1/R-2/R-3）
      MATCH   "const msg = \"req.status = to\""      （字符串字面量误报面 ← R-4）

## 3. 偏离项（轻微、非阻断）

**D-1｜tokenUsage 赋值正则未限定字段访问符（实现比设计文本更宽，带潜在误报面）**

- 设计文本（backend.md §结构性守卫）：`tokenUsage ??= ` / **`.tokenUsage = `**（`=` 分支带前置字段访问符 `.`）。
- 实现：`\btokenUsage\s*(?:…|=)(?!=)`，`=` 分支**不要求**前置 `.`，因此 `const tokenUsage = …` / `let tokenUsage = …` 这类**局部变量声明**也会被判违规（node 复现见 §2⑤）。
- 影响：方向为**收紧（不漏报）**，非放松；当前 src 内无此写法，故对本次「零命中」结论无影响。风险面是未来维护者在非收敛点写局部别名 `const tokenUsage = task.tokenUsage` 会被误红（属显式红灯，不静默）。
- 结论：**轻微偏离**。建议（后续卡，不阻断本卡）：或把 `=` 分支收紧为 `[.\[]?\s*tokenUsage`（要求字段访问上下文），或补一条「局部变量声明不误报」的反例断言明确边界。

**D-2｜requirement-transition-guard 头部注释的需求归属不一致（追溯性偏差）**

- `tests/requirement-transition-guard.test.ts` 头注为「REQ-b545fe t1 / 2026-09-27 补」，而设计（backend.md §结构性守卫 / test-cases T-19）把该守卫登记为 **REQ-260927121324-abde 的 T-19**；同批的 `execution-token-guard.test.ts` 头注则写 `REQ-260927121324-abde t1`。
- `REQ-b545fe` 是本需求的前序需求（REQ-260927121324-abde/requirement.md §R2 明确其为 `transitionRequirement` 收敛点的建设方），故该引用并非无意义，但与本卡的 FR 归属（FR-1/FR-8/FR-9）不一致，属**注释层追溯偏差**。
- 影响：仅影响阅读者定位需求来源，不影响任何断言与行为。
- 结论：**轻微偏离**。建议把注释统一为 `REQ-260927121324-abde`（并保留「承接 REQ-b545fe 收敛点」一句作背景）。

## 4. 残余边界（设计只承诺字面式样，非偏离）

1. **R-1 逐行匹配**：跨行写法（`req\n  .status = to`、`task.executions\n  .push(e)`）不覆盖。卡片实施方案要求的正是「不含 `req.status = ` 字面」，当前 src 无此类写法。
2. **R-2 变量名限定**：迁移守卫只认 `req` / `r`；改名后直写（如 `target.status = to`、`item.status = to`）会漏。实测 application+http 内需求态直写仅收敛点 1 处，无改名残留；更强保证需 AST 级校验，超出本卡范围。
3. **R-3 等价逃逸**：`executions?.push(`、`executions['push'](`、`obj['tokenUsage'] = `、`unshift/splice` 等不匹配。设计只点名 `executions.push(` 与 tokenUsage 赋值字面，属已知边界。
4. **R-4 字符串字面量保留**：执行守卫注释已明示「字符串字面量保留（更严格：宁可误报，不可漏报）」；迁移守卫同为注释剥离、字符串保留，故含 `"req.status = to"` 的字符串也会命中（当前 src 无此类字符串）。属有意取舍的误报侧边界，非漏报。

## 5. 结论

- 设计 7 个约束点（P-1…P-7）**全部落位，逐条判定「无偏离」**，依据见 §1 与 §2 的独立复跑/故障注入/交叉核查。
- 守卫**真会变红**：故障注入 3 处违规全部命中，报点格式严格为「文件:第 N 行 · 式样 → 原文」，满足「违规时断言信息打印文件与行号」；探针已清理、真实 `src` 零改动。
- 守卫**不误报**：读引用 / 类型声明 / 比较 / 注释四类反例均通过（P-3/P-4）。
- 未发现阻断性偏离，**无需返工**；D-1、D-2 为轻微偏离（建议后续卡收口），R-1…R-4 为设计范围外的已知边界，登记供复核与后续卡参考。
