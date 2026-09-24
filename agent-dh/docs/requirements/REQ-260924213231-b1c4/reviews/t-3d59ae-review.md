# t-3d59ae 复核记录（父卡 t-9f96a1 / T-11「pm 弹框统一来源标志」· 阶段 review）

- 复核时间：2026-09-25T01:51+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 复核对象（FR-8 / I-7 / UC-5 / TC-14；父卡 T-11「pm 弹框统一来源标志」）：
  - 新增 `src/domain/text/pm-badge.ts`（`PM_BADGE_PREFIX='📋 PM · '` + `pmHeader()`）
  - `src/application/use-cases/AskConfirm.ts:135`、`src/application/use-cases/AcceptSheet.ts:67,162`、
    `src/application/internal/capture-mapping.ts:99,113,122,131`、`src/application/use-cases/HandleFailure.ts:42`
    —— 4 文 8 处 header 构造点全部改走 `pmHeader()`
  - 新增 `tests/pm-question-badge.test.ts`（7 例）
  - 旁证（本卡未改，仅作边界核对）：`src/adapters/UserQuestionsAdapter.ts:32-46`、`src/adapters/GateAwareQuestions.ts:48-69`、
    `src/application/ports.ts:156-161`（`AskQuestion.header?: string`）、`src/application/use-cases/CaptureRequirement.ts:137-146,163,180`
- 设计依据（比对基线）：`requirement.md` FR-8（L113-116）+ A6（L22）+ §5 不做什么（L81）；`design/use-cases.md` UC-5（L75-84）；
  `design/interfaces.md` I-7（L20）；`design/architecture.md` L17/L53/L94/L107/L243-247；`design/test-cases.md` TC-14（L41）
  + 头部 `serves:` 约定（L9）+ 落点表（L113）；`decomposition.md` L43/L68/L104/L107/L120/L144/L159；任务卡 `tasks/t-9f96a1.md`
- 复核方式：**只读复核 + 独立复跑 + 一次性探针独立见证**（不采信上游自述）：逐条比对设计契约、源码穷举核对、
  独立运行父卡验收命令与全量套件、另写一次性探针（真用例捕 header + 孤儿用例读数）后**已删除**

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 | `requirement.md` FR-8 / A6 | pm 插件发起的提问**统一带可辨识来源标志**（落 header 前缀）；标志由 pm 侧在构造 questions 处统一注入，**不依赖 agent 在 question 文本里手写 emoji**；宿主原生 `ask_user_question` 保持原样；**不改宿主 DSH 包**（§5 L81）。验收 A6 = 不读正文即可分辨，且标志非 agent 手写 |
| 用例 | `design/use-cases.md` UC-5 | ① pm 侧构造问题（AskConfirm / AcceptSheet / capture 四问 / 失败处置）统一经 `pmHeader()`；② 人看 header 前缀判定来源，无前缀 = 宿主原生；异常流：agent 不得靠正文 emoji 冒充，标志由 pm 侧注入、与 agent 文案无关 |
| 接口 | `design/interfaces.md` I-7 | pm 侧构造的**每个**问题的 `header` 以固定前缀 `📋 PM · ` 开头；兼容性 = **只改 header 文本，不改宿主 schema**；无新增错误语义 |
| 架构 | `design/architecture.md` L53/L107 | 弹框来源标志 = 新增 `domain/text/pm-badge.ts`（`pmHeader(text)` 返回 `📋 PM · {text}`），**四处构造点**统一调用（AskConfirm / AcceptSheet / capture-mapping / HandleFailure） |
| 测试用例 | `design/test-cases.md` TC-14（L41） | 触发 ask_confirm / accept_sheet / capture 三处弹框 → 三者 header 均以 `📋 PM · ` 开头；宿主 ask_user_question 不带该前缀 |
| 测试约定 | `design/test-cases.md` L9 + 落点表 | 落点表列出的每个测试文件，**头部 20 行内必须带 `// serves: FR-x`**（否则验收时计入孤儿用例） |
| 计划 | `decomposition.md` L120（T-11 行）+ L43/L68 | 落点 = 新增 `pm-badge.ts` + 四文件 header 改 `pmHeader` + 新增 `pm-question-badge.test.ts`；验收命令 = `npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts` 全绿 |
| 计划 | `decomposition.md` D-1（L84-88）+ 基线表（L185-193） | 基线红已知（7 文件/9 例 + tsc 23）；本次只保证**不新增失败**；D-6/RISK-2 要求 `AskConfirm.ts` 每步后仍 ≤400 行 |
| 任务卡 | `tasks/t-9f96a1.md` 得到什么结果 | 目标测试全绿；四处 `AskQuestion.header` 均以 `📋 PM · ` 开头；宿主原生不带该前缀 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | FR-8 / I-7 / architecture L107：pm 侧构造的**每个**问题 header 带固定前缀，**四处**构造点 | 4 文 8 处 header 全部 `pmHeader(...)`：`AskConfirm.ts:135`、`AcceptSheet.ts:67,162`、`capture-mapping.ts:99,113,122,131`、`HandleFailure.ts:42` | **无偏离**。依据：源码 grep（§3.6）+ 探针实测 9 条 header 全带前缀（§3.5 PROBE_OUT） |
| R2 | 穷举：pm 侧是否还有**未被覆盖**的弹框构造点 | 全 src 内 `questions.ask(` 仅 4 个站点：AskConfirm / AcceptSheet / CaptureRequirement / HandleFailure；其中 CaptureRequirement 经 `buildCaptureIntentQuestions`/`buildCaptureDetailQuestions`（capture-mapping）取 header。无第五个弹框入口 | **无偏离**（覆盖完整，无遗漏）。依据：§3.5 PROBE_SITES + §3.6 源码穷举 |
| R3 | I-7 兼容性：**只改 header 文本，不改宿主 schema** | `AskQuestion` 定义未动（`ports.ts:156-161`，`header?: string` 在 HEAD 即已存在）；两个通道适配器（`UserQuestionsAdapter`/`GateAwareQuestions`）**零改动**，questions/answers 原样进出 | **无偏离**。依据：`git show HEAD:...ports.ts \| grep header` → 命中 158 行；`git status` 未列出两适配器 |
| R4 | FR-8 / UC-5 异常流：标志**不注入正文**，正文与 agent 文案无关 | 探针在 `reqboard_ask_confirm` 的 question 正文故意塞入 `📋 PM · ` → 正文**逐字原样透传**，header 仍只加一次前缀（`['📋 PM · 确认']`） | **无偏离**。依据：§3.5 PROBE_OUT `askConfirm.bodies` 与实现（`AskConfirm.ts:132-136` 只包 header） |
| R5 | 前缀字面量唯一，别处硬写 = 漂移（`pm-badge.ts:17-18,21-27` 自述 + 卡面测试） | `PM_BADGE_PREFIX` 在 `src` 下**仅**出现在 `domain/text/pm-badge.ts`；4 个调用点均 import `pmHeader` 且不含字面量 | **无偏离**。依据：§3.5 PROBE_SITES `headerCarriers`；`pm-question-badge.test.ts` 静态扫描断言（第 151-169 行） |
| R6 | `pmHeader` 语义：只加前缀、不做幂等去重（重复调用得两个前缀，响亮可见） | `pmHeader(text) = PM_BADGE_PREFIX + text`（`pm-badge.ts:26-28`）；模块注释 L23-25 明确「不幂等去重」，与实现一致 | **无偏离**。依据：`pm-badge.ts:26-28` + 卡面测试第 1 例 |
| R7 | FR-8：**宿主原生提问不带该前缀**（不误伤） | 宿主原生提问不经 `pmHeader`（pm 侧唯一注入点是四处用例；`svc.ask` 只做通道转发） | **无偏离**（就「pm 不篡改宿主提问」而言）。依据：`UserQuestionsAdapter.ts:32-46`、`GateAwareQuestions.ts:48-69`；旁证 O-5 说明「正文冒充」不被拦截属设计边界 |
| R8 | 尺寸纪律（D-6/RISK-2：`AskConfirm.ts` ≤400 行）+ 卡面文件规模 | `AskConfirm.ts` 241 行（359 → 241，因 T-6 抽取落章逻辑而缩小）、`AcceptSheet.ts` 250、`capture-mapping.ts` 212、`HandleFailure.ts` 124、`pm-badge.ts` 28、测试 170 行 | **无偏离**。依据：`wc -l`（§3.6） |
| R9 | 父卡验收命令：`pm-question-badge.test.ts` + `capture.test.ts` + `ask-confirm.test.ts` 全绿 | 独立复跑 **3 文件 38/38 绿，exit 0**；关联回归 9 文件 75/76（唯一红 size-budget，见 O-2，非本卡） | **无偏离**。依据：§3.1/§3.2 |
| R10 | D-1：类型检查增量 0（基线 23，新增文件 0 报错） | `tsc --noEmit` **24** 条（23 条 D-1 基线 + 第 24 条为 T-6 新文件 `tests/ask-confirm-pending.test.ts`，已由 T-6 复核记录）；本卡 6 文件命中 **0** 条 | **不判本卡偏离**（增量 0）。依据：§3.4 |
| R11 | 测试约定（test-cases.md L9 + 落点表）：头部 20 行内声明 `serves: FR-x` | `pm-question-badge.test.ts` 头部 20 行**无 `serves:` 声明**（L2 只有「T-11 / FR-8 · I-7 / TC-14」）；本需求自己的孤儿检查 `testFileHasServesHeader`（要求 `serves\s*[:：]`）判其为**缺映射** | **有偏离**（D-A，约定/门禁可见项，警告级不阻断）。依据：§3.5 PROBE_ORPHANS + `content-gate-wiring.ts:228-231,250-260` |
| R12 | 计划落点文件清单（decomposition L120）：5 源文件 + 1 测试文件，无越界 | 实现改动恰为计划 5 源 + 1 新增测试 + 1 新增源（`pm-badge.ts`）；**另有一处计划外必要适配**：`tests/auto-chain-approval.test.ts`（+1 import `pmHeader`、1 断言 `'确认'` → `pmHeader('确认')`） | **基本无偏离**，附观察 O-1（计划的改动盘点漏记该既有测试适配，属必要的连带修改，非功能偏离） |

---

## 2. 偏离与观察项

### D-A（有偏离 · 测试约定/门禁可见项 · 低 · 建议父卡收尾前顺手补）

**设计与实现偏离**：`design/test-cases.md` L9 明确规定「测试文件落点表列出的每个文件，头部 20 行内必须带
`// serves: FR-x`（否则验收时计入孤儿用例）」，且实现侧有机械判定：
`testFileHasServesHeader(text)` = 前 20 行内匹配 `serves\s*[:：]`（`content-gate-wiring.ts:228-231`），
`collectOrphanTestFiles` 会拿 `design/test-cases.md` 的「实际文件」列逐个文件核对（同文件 L250-260），
非空则给验收单**追加一条需求级 pending 项**「孤儿用例（缺映射）…请补 serves: 声明」（警告级、不阻断，`AcceptanceSheetSpec.ts:145-154`）。

实测（§3.5 PROBE_ORPHANS）：本需求落点表共 11 个文件，判定结果 —— **6 个 OK / 4 个 miss / 1 个不存在**：

- miss：`tests/confirm-evidence.test.ts`（既有文件）、`tests/design-registration.test.ts`（T-3）、
  `tests/zero-arg-binding.test.ts`（T-7）、**`tests/pm-question-badge.test.ts`（本卡 T-11）**
- absent：`tests/e2e-design-handoff.test.ts`（T-13，尚未落盘）

- **影响**：不阻断本卡验收（该项是警告级、只进入验收面），但本卡交付物会被标为「缺映射」，验收时人要额外裁决一次。
- **建议**（一行文档级修改，本 review 卡只读未动）：在 `tests/pm-question-badge.test.ts` 头部注释补
  `serves: FR-8`（与同需求 `design-gate-messages.test.ts`/`ask-confirm-pending.test.ts` 等 6 个文件的写法一致）。
  另 3 个 miss + 1 个 absent 属 T-3 / T-5（既有文件）/ T-7 / T-13 的范围，见 O-3。

### O-1（观察项 · 计划落点漏记一处必要适配）

`tests/auto-chain-approval.test.ts` 被本卡连带修改（1 个 import + 1 行断言：`'确认'` → `pmHeader('确认')`，见 §3.6 diff）。
这是 T-11 改 header 后**必须**做的既有测试适配（否则该套件必红），功能上无问题；只是 `decomposition.md` L120 的
T-11 落点清单与 L43/L68 的改动盘点都未列此文件。**建议**：在卡面/计划备注一句「含既有断言适配 1 处」，不必返工。

### O-2（观察项 · 非本卡）：size-budget 门禁 2 处红

`tests/size-budget.test.ts` 判 2 个超标文件：`index.ts = 458`（D-1/D-2 已登记的基线/ T-12 范围）与
`Decompose.ts = 401`。后者 HEAD 为 400（恰好不超），本需求 T-9 在 `Decompose.ts` 插入 `const stampCheckpoint` import
与 1 行 `stampCheckpoint(r, nowTs, 'reqboard_decompose')`（`git diff` 见 §3.6）**单行推过阈值** → 新增一处红。
本卡 6 文件（最大 `AcceptSheet.ts` 250 行）均远离阈值，**与本卡无关**；建议父卡/验收把「`Decompose.ts` 401」并入
T-12 的瘦身范围或单列一处收尾。

### O-3（观察项 · 跨卡，供父卡收尾参考）：落点表 4 个文件缺 `serves:` + 1 个 E2E 文件未落盘

见 D-A 的实测清单。`tests/e2e-design-handoff.test.ts`（T-13 的 E2E 落点）当前**文件不存在**，
`collectOrphanTestFiles` 因 `docs.exists(f)` 为假会跳过它（不报孤儿），但 TC-19(E2E) 的落点缺口仍未闭环。
均不属本卡范围，仅登记以免验收时才发现。

### O-4（观察项 · 非本卡）：全量套件新增 1 例红（`language-layer.test.ts`，归 T-8）

全量套件 7 文件/8 例红（D-1 基线 7 文件/9 例）：`design-completeness-gate` 的 2 例已由 T-5 修绿，
但出现 1 例新红 —— `language-layer.test.ts` 断言设计提示词含「每节**必须**标注服务哪条功能点」，
而 T-8 改写 `design/light/overrides.md` 后文本变为「覆盖 2 · 每节标注服务哪条功能点」（`git diff` 见 §3.6），
既有断言未同步。**归 T-8，与本卡无关**。建议 T-8/父卡收尾时同步该断言（或把措辞改回）。

### O-5（观察项 · 措辞级，非偏离）：正文手写假前缀不被拦截，属设计边界

`pm-badge.ts:8-10` 的注释写「不读正文即可分辨，且 **agent 伪造不了**」。严格说：pm 侧**无法**阻止 agent 在
宿主原生 `ask_user_question` 的 question **正文**里手写 `📋 PM · `（探针实测正文逐字透传，见 §3.5）。
FR-8 的真实要求是「标志由 pm 侧注入、**不依赖** agent 正文 emoji」，且 `requirement.md` §5 明确「不改宿主 DSH 包」，
故这是**设计边界而非实现缺陷**；建议把注释措辞收敛为「header 标志不由 agent 文本派生」以免过度承诺。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（独立复跑，与上游自述一致）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts
```

实际输出（尾部）：

```
 ✓ tests/capture.test.ts (20 tests) 5ms
 ✓ tests/pm-question-badge.test.ts (7 tests) 16ms
 ✓ tests/ask-confirm.test.ts (11 tests) 113ms

 Test Files  3 passed (3)
      Tests  38 passed (38)
```

判定：**38/38 全绿、退出码 0** —— 覆盖 TC-14（四处 header 带前缀 + 正文不带 + 字面量唯一 + 四处均 import `pmHeader`）。

### 3.2 关联回归（弹框/壳/契约/尺寸）

```bash
npx vitest run tests/tools-dispatch.test.ts tests/output-contract.test.ts tests/tools-schema.test.ts \
  tests/auto-chain-approval.test.ts tests/accept-sheet-tool.test.ts tests/ask-confirm-pending.test.ts \
  tests/failure-handling.test.ts tests/size-budget.test.ts tests/gate-aware-questions.test.ts
```

```
 Test Files  1 failed | 8 passed (9)
      Tests  1 failed | 75 passed (76)
```

- 唯一红 = `size-budget.test.ts`（`index.ts`/ `Decompose.ts`，见 O-2）。
- 其余 8 文件全绿，含 `tools-dispatch`（真工具分派链）、`output-contract`（返回键静态扫描）、
  `auto-chain-approval`（既有 header 断言已适配 `pmHeader`）、`gate-aware-questions`（装饰器未受影响）。

### 3.3 全量套件（核「不新增失败」；D-1 口径）

```bash
npx vitest run
```

```
 Test Files  7 failed | 150 passed (157)
      Tests  8 failed | 1850 passed (1858)
```

红名单：`client-view`(1)、`language-layer`(1)、`layer-boundary`(1)、`size-budget`(1)、
`template-address-injection`(2)、`typecheck`(1)、`application/repository`(1)。

对比 D-1 基线（7 文件/9 例）：`design-completeness-gate` 2 例 **已修绿**（T-5）；新增 1 例
`language-layer`（**T-8**，见 O-4）。**本卡（FR-8）无任何新增红** —— T-11 只改 header 文本，不触及上述文件。

### 3.4 类型检查（`npx tsc --noEmit -p tsconfig.json`）

```bash
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -c 'error TS'                     # → 24
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E 'pm-badge|AskConfirm|AcceptSheet|capture-mapping|HandleFailure|pm-question-badge' | head   # → 空
```

- 总数 **24** = D-1 基线 23 + 1（`tests/ask-confirm-pending.test.ts(55,36)`，T-6 已记录）。
- 本卡 6 文件命中 **0** 条 —— 满足「新增文件 0 报错 / 增量 0」。

### 3.5 一次性探针（真用例捕 header + 孤儿用例读数，跑完即删）

探针 `tests/__probe-t3d59ae.test.ts`（3 例，运行后已删除并复核 `No such file or directory`）：

```
 ✓ tests/__probe-t3d59ae.test.ts (3 tests) 19ms

 Test Files  1 passed (1)
      Tests  3 passed (3)
```

**A. 四处构造点实捕 header（真用例，非重复卡面测试）**

```
PROBE_OUT {"askConfirm":{"headers":[["📋 PM · 确认"]],
 "bodies":[["确认需求文档？📋 PM · （正文里的假标志）"]]},
 "acceptSheet":{"headers":[["📋 PM · 需求级验收","📋 PM · 验收项 t-000001"],["📋 PM · 验收通过"]]},
 "failure":{"headers":[["📋 PM · 实施链已暂停"]],"choice":"rerun"},
 "capture":{"headers":[["📋 PM · 需求名称"],["📋 PM · 需求类型","📋 PM · 提示词难度","📋 PM · 需求文档位置"]],
 "success":true,"status":"brainstorming"}}
```

- 9 条 header 全带 `📋 PM · `；立项四问走**真用例** `captureRequirement`（两段弹框），落地 `brainstorming`。
- `askConfirm.bodies` 证明**正文原样透传**（agent 在正文写的前缀不被剥离、也不影响 header）——R4/O-5 的直接证据。

**B. 穷举 `src` 内全部弹框构造点**

```
PROBE_SITES {"askSites":["application/use-cases/AcceptSheet.ts","application/use-cases/AskConfirm.ts",
 "application/use-cases/CaptureRequirement.ts","application/use-cases/HandleFailure.ts"],
 "headerCarriers":["application/internal/capture-mapping.ts","application/use-cases/AcceptSheet.ts",
 "application/use-cases/AskConfirm.ts","application/use-cases/HandleFailure.ts","domain/text/pm-badge.ts"]}
```

- `questions.ask(` 站点**恰为 4 个**，无第五个弹框入口；`pmHeader` 载体恰为「定义 1 + 四处构造点」，与 architecture L107 逐字对应。

**C. 孤儿用例读数（真实文件 + 本需求自己的判定函数）**

```
PROBE_ORPHANS {"total":11,
 "ok":[".../ask-confirm-pending.test.ts",".../create-doc-location.test.ts",".../design-gate-messages.test.ts",
       ".../design-prompt-registration.test.ts",".../gate-feedback-envelope.test.ts",".../interruption-checkpoint.test.ts"],
 "miss":[".../confirm-evidence.test.ts",".../design-registration.test.ts",".../pm-question-badge.test.ts",".../zero-arg-binding.test.ts"],
 "absent":[".../e2e-design-handoff.test.ts"]}
```

- 读法与实现一致：`parseDocument` + `testFilesFromDesign`（取落点表「实际文件」列）+ `testFileHasServesHeader`（前 20 行）。

### 3.6 源码面核对（grep / diff / HEAD 对照）

```bash
# 1) header 构造点穷举（src）
grep -rn 'header:' packages/web/dsh-pmboard/src | ...   # 仅 8 处 pmHeader + doc-parse 的无关 parse 结构
# 2) 字面量唯一
grep -rn 'PM_BADGE_PREFIX' packages/web/dsh-pmboard/src # 仅 domain/text/pm-badge.ts
# 3) HOST schema 未动
git show HEAD:./packages/web/dsh-pmboard/src/application/ports.ts | grep -n header   # → 158: header?: string（HEAD 即存在）
# 4) 四文件 header diff（逐字机械替换）
git diff HEAD -- .../AskConfirm.ts .../AcceptSheet.ts .../HandleFailure.ts .../capture-mapping.ts | grep -E '^[+-].*(pmHeader|header:)'
#   -header: '需求名称' / '需求类型' / '提示词难度' / '需求文档位置' / '验收通过' / '实施链已暂停' / '确认'
#   +header: pmHeader('…')   （另 AcceptSheet 第二处为 it.source.kind === 'requirement' ? … : fmt(…)
#                             改为 pmHeader(it.source.kind === …)）
# 5) 规模
wc -l src/domain/text/pm-badge.ts src/application/use-cases/AskConfirm.ts src/application/use-cases/AcceptSheet.ts \
      src/application/internal/capture-mapping.ts src/application/use-cases/HandleFailure.ts tests/pm-question-badge.test.ts
#   → 28 / 241 / 250 / 212 / 124 / 170
# 6) size-budget 归因
git diff HEAD -- .../Decompose.ts   # +import stampCheckpoint；-return { requirements: [r] }
                                     # +stampCheckpoint(r, nowTs, 'reqboard_decompose'); return { requirements: [r] }
# 7) language-layer 归因（T-8）
git diff HEAD -- .../design/light/overrides.md | grep 每节
#   -- [ ] **覆盖 1 · 每节必须标注服务哪条功能点**…
#   +- [ ] **覆盖 2 · 每节标注服务哪条功能点**…
```

---

## 4. 复核结论

1. **卡面验收达标**：父卡验收命令 3 文件 **38/38 绿（exit 0）**；四处（4 文 8 处）`AskQuestion.header` 均以
   `📋 PM · ` 开头，**且经独立探针在真用例（含真 `captureRequirement`）上实捕 9 条 header 复验**；
   宿主原生提问不经 `pmHeader`、不带前缀；正文不被注入；前缀字面量唯一在 `pm-badge.ts`。
2. **契约合规**：I-7「只改 header 文本、不改宿主 schema」成立（`header?: string` 在 HEAD 已存在，适配器零改动）；
   覆盖穷举无遗漏（`questions.ask(` 站点恰 4 个，全部覆盖或经单一构造源覆盖）。
3. **发现 1 项低严重度偏离（D-A，非功能）**：本卡交付的 `tests/pm-question-badge.test.ts` 头部 20 行缺 `serves: FR-8`
   声明，会被本需求自己的孤儿检查判为「缺映射」，在验收单上追加一条警告级 pending 项。**建议一行补记**（本卡只读未改）。
4. **另 5 项观察项**：O-1 计划落点漏记 1 处既有测试适配（`auto-chain-approval`）；O-2 `size-budget` 2 红（`index.ts` 属 D-1/T-12；`Decompose.ts` 401 由 T-9 引入）；O-3 落点表 4 文件缺 `serves:` + 1 个 E2E 文件未落盘（跨卡）；O-4 全量套件新增 1 红归 T-8（`language-layer`）；O-5 `pm-badge.ts` 注释措辞过度承诺（正文假前缀不可拦截，属设计边界）。**均不阻断本卡，无一项归因于 T-11 的实现缺陷。**
5. **无护栏放松、无越界破坏**：宿主 schema/适配器未动；`output-contract`/`tools-schema`/`tools-dispatch` 全绿；
   本卡 6 文件 tsc 命中 0 条；尺寸远低于 400 行阈值。
6. **卡面纪律**：本卡为 review 阶段，**只读复核 + 落本记录**；一次性探针已删除，未修改任何实现/测试/配置源码。
   本轮新增产物仅本文件。
7. **复核结论：通过（卡面验收达标）；附 D-A 一项低严重度约定偏离（建议一行补 `serves: FR-8`）与 5 项观察项，均不阻塞父卡收尾。**
