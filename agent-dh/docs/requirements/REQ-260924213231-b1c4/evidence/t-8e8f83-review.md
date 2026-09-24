# t-8e8f83 复核记录（父卡 t-fbde12 / T-10「立项降级路径不丢文档位置」· 阶段 review）

- 复核时间：2026-09-25T01:41+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 复核对象（FR-7 / I-6 / UC-4 / TC-11~TC-13；父卡 T-10「立项降级路径不丢文档位置」）：
  - `src/tools/CreateTool/CreateTool.ts`（入参 schema 增 `doc_location`；输出 schema 增 `doc_location`/`defaults_used`）
  - `src/application/use-cases/CreateRequirement.ts`（`resolveDocBasePath` → `createRequirementDirect({ …docBasePath })`；返回补 `doc_location`/`defaults_used`）
  - `src/application/internal/support.ts`（`resolveDocBasePath` 取值/回落/拒绝；`createRequirementDirect` 把回落值写进台账 `docBasePath`）
  - `tests/create-doc-location.test.ts`（新增，5 例）
  - 旁证（非本卡改动）：`src/application/internal/node-input-package.ts:224-232 requirementDocPath()`、`src/application/internal/capture-mapping.ts:25-56`
- 设计依据（比对基线）：`requirement.md` FR-7（L109-113）；`design/use-cases.md` UC-4（L63-73）；
  `design/interfaces.md` I-6（L19）+ E-6（L124）；`design/architecture.md` L17/L52/L63/L106/L231-240；
  `design/data-model.md` L34/L89；`design/test-cases.md` TC-11/12/13（L38-40）；
  `decomposition.md` L66（改动盘点）+ L84-88（D-1 基线）+ L119（T-10 行）；任务卡 `tasks/t-fbde12.md`
- 复核方式：**只读复核 + 独立复跑**（不采信上游自述）：逐条比对设计契约、对照 HEAD 版本 diff、独立运行父卡验收命令与关联回归、另写一次性探针独立见证「返回状态与台账状态」（跑完即删）

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 | `requirement.md` FR-7 | 降级路径能取到文档位置（工具暴露入参），或至少显式回落并留痕；消费端缺省仍为 `docs/requirements/<REQ>/`，保持向后兼容；验收=不传位置时返回值/台账可见「已回落默认」；传自定义位置（如 `docs/rfcs/`）时产物路径按它生成 |
| 用例 | `design/use-cases.md` UC-4 | ② agent 调 `reqboard_create(title, category, prompt_difficulty, doc_location?)`；③ 返回值含 `doc_location` 与 `defaults_used`，台账写入 `docBasePath`；异常流=位置形态非法（绝对路径 / 含 `..`）→ `REQBOARD_INVALID_INPUT`，**不静默改路径**；后置=文档路径三面（返回值 / 台账 / 输入包）一致 |
| 接口 | `design/interfaces.md` I-6 | 入参既有 + `doc_location?`；出参既有键 + `doc_location`、`defaults_used[]`；**`status` 为推进后终态**；兼容性=只增键、缺省与旧行为逐字一致 |
| 接口 | `design/interfaces.md` E-6 | `doc_location` 形态非法 → `REQBOARD_INVALID_INPUT`（须为工作区相对目录） |
| 架构 | `design/architecture.md` L52 / L106 / L240 | L52「`reqboard_create` 增 `doc_location`，回落留痕，**并推进到终态**」；L106「增 `doc_location` 入参 → `createRequirementDirect({ …docBasePath })`；返回补 `doc_location`/`defaults_used`；**随后复用 `advanceDraftToBrainstorming`（从 `CaptureRequirement.ts` 提到 `internal/`）返回终态**」；L240 位置缺省 → 回落 `docs/requirements/<REQ>/` 并记 `defaults_used`（返回体 + 台账 `docBasePath`） |
| 数据模型 | `design/data-model.md` T-5 / L89 | `RequirementRecord.docBasePath`（既有）= 需求文档目录，立项时写入；L89「返回体**只增键**；`reqboard_create` 不传 `doc_location` 时 `docBasePath` 写既有缺省值，`requirementDocPath()` 输出逐字节不变」 |
| 测试用例 | `design/test-cases.md` TC-11/12/13 | TC-11 不传 → 返回含 `doc_location=docs/requirements/<REQ>/`、`defaults_used` 含 doc_location；TC-12 传 `docs/rfcs/` → 台账 `docBasePath='docs/rfcs/'`、产物路径按它生成；TC-13 返回 `status='brainstorming'`（**或如实 draft + 未推进说明**），与台账一致 |
| 计划 | `decomposition.md` L66 / L119 | L66 改动盘点：`CreateTool.ts` + `CreateRequirement.ts` + `support.ts`「增 `doc_location` 入参 → `docBasePath` + `defaults_used` + **推进终态**」；L119 T-10 验收=目标测试全绿、回落留痕且台账同值、自定义路径生效、返回 status 与台账一致 |
| 计划 | `decomposition.md` D-1 | 基线红已知；本次只保证「不新增失败」；typecheck 口径 = 错误数 ≤ 基线 23 且**新增文件 0 报错** |
| 任务卡 | `tasks/t-fbde12.md` 得到什么结果 | `npx vitest run tests/create-doc-location.test.ts` 全绿；不传 → 返回 `doc_location='docs/requirements/<REQ>/'` 且 `defaults_used` 含 doc_location、台账 `docBasePath` 同值；传 `docs/rfcs/` → 台账与产物路径按它生成；返回 status 与台账一致 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | I-6：`reqboard_create` 入参既有 + `doc_location?` | `CreateTool.ts:47-51` 声明可选 string 参数（描述含「不传 / 空串 → 回落 …并在 defaults_used 标注」）；用例 `CreateRequirement.ts:31,38` 读取 `a.doc_location` | **无偏离**。依据：`CreateTool.ts:47-51`、`CreateRequirement.ts:31,38`；schema 面测试（`create-doc-location.test.ts` 第 5 例）断言 `paramType='string'` |
| R2 | I-6：出参既有键 + `doc_location`、`defaults_used[]` | `CreateTool.ts:63-68` 两个新键已在输出 schema 声明（`additionalProperties:false`，未声明的键会被 output-contract 抓）；用例 `CreateRequirement.ts:55-56` 返回 | **无偏离**。依据：`CreateTool.ts:63-68`、`CreateRequirement.ts:55-56`；`output-contract.test.ts` 21/21 绿、`tools-schema.test.ts` 3/3 绿 |
| R3 | I-6「`status` 为推进后终态」+ architecture L52/L106「**并推进到终态** / 随后复用 `advanceDraftToBrainstorming`（提到 `internal/`）返回终态」+ decomposition L66「+ 推进终态」 | 用例 `CreateRequirement.ts:53` 直接返回 `status: req.status`；`support.ts:266-277` 建单即 `status:'draft'`，**没有** `advanceDraftToBrainstorming` 复用/抽取，也没有任何 draft→brainstorming 推进；探针实测 `status='draft'`、`statusHistory=['draft']`、台账 `status='draft'` | **有偏离**（功能未闭环，D-A）。依据：`CreateRequirement.ts:53`、`support.ts:266-277`、`CaptureRequirement.ts:59-79`（`advanceDraftToBrainstorming` 仍为**局部函数、未提到 `internal/`**）、§3.4 探针输出。注：卡面验收「返回 status 与台账一致」**满足**（TC-13 括注允许「如实 draft」），但括注要求的**「未推进说明」**在 `note` 中也未出现，且 NFR-1「要么返回终态、要么明示会被接手窗口自动推进」两条**都没选** |
| R4 | UC-4 异常流 / E-6：绝对路径、含 `..` → `REQBOARD_INVALID_INPUT`，不静默改路径 | `support.ts:223-249`：非字符串 / 绝对（`/`、`~`、`\`、盘符）/ 含 `..` 段 → `reject(..., 'REQBOARD_INVALID_INPUT')`；用例在 `createRequirementDirect` **之前**调用（失败即不写台账） | **无偏离**。依据：`support.ts:223-249`、`CreateRequirement.ts:37-38`；测试第 4 例 4 种非法形态全拒且台账 0 条 |
| R5 | UC-4 后置条件：文档路径三面（返回值 / 台账 / 输入包）一致 | 返回 `doc_location = req.docBasePath ?? doc.docBasePath`（`CreateRequirement.ts:55`）；台账 `docBasePath` 恒写值（`support.ts:265,275`）；消费端 `requirementDocPath()` 同源拼接（`node-input-package.ts:224-232`） | **无偏离**。依据：测试 TC-11/TC-12 断言 `out.doc_location`、`req.docBasePath`、`requirementDocPath(req)` 三者同源 |
| R6 | FR-7 验收：不传位置→返回值/台账可见「已回落默认」；传自定义位置→产物路径按它生成 | 不传/空串 → `defaults_used=['doc_location']` + `note` 含「回落」+ 台账写 `docs/requirements/<REQ>/`；传 `docs/rfcs/` → `defaults_used=[]`、台账 `docs/rfcs/`、`requirementDocPath()=docs/rfcs/<REQ-id>/requirement.md` | **无偏离**。依据：测试 TC-11/TC-12 全绿；§3.4 探针实测默认值；integrate 证据 `t-d52c67` §1.A/B 19/19 MATCH |
| R7 | data-model L89 兼容：旧记录不改；`requirementDocPath()` 缺省逐字节不变 | `requirementDocPath()` 第 227 行缺省分支 `?? 'docs/requirements/<REQ>/'` **未改动**；`createRequirementDirect` 只影响**新建**记录（旧记录不回溯） | **无偏离**（就路径解析而言）。依据：`node-input-package.ts:227` 与 HEAD 对照逐字一致；`create-doc-location.test.ts` 老记录缺省断言通过。注：既有键 `note` 在默认分支被改写，见 D-B |
| R8 | 回落标记与弹框路径同源（不静默猜） | `defaults_used` 取值 `CAPTURE_QUESTION_IDS.doc_location`（=`'doc_location'`）；默认值 `CAPTURE_DEFAULTS.docLocation`（=`'docs/requirements/<REQ>/'`）——与 `capture-mapping.ts:25-56` 单一事实源一致 | **无偏离**。依据：`CreateRequirement.ts:18,47`、`support.ts:25-27,224-231`、`capture-mapping.ts:29,56`、`capture-mapping.ts:190-196`（弹框路径同口径） |
| R9 | Schema 铁律（每个 object 节点显式 `additionalProperties`） | `CreateTool.ts:56` `additionalProperties:false`；`doc_location` 是 string 属性（非 object）；`defaults_used` 的 `items` 为 string | **无偏离**。依据：`tools-schema.test.ts` 3/3 绿、`tools-dispatch.test.ts` 4/4 绿 |
| R10 | 任务卡落点文件清单 | 实际改动恰为计划 4 文件（`CreateTool.ts`/`CreateRequirement.ts`/`support.ts`/`tests/create-doc-location.test.ts`），未越界 | **无偏离**。依据：`git status` + 逐文件 diff；`node-input-package.ts` 的改动属 FR-6/T-9，不在本卡 |
| R11 | D-1/T-1 基线纪律：typecheck 错误数 ≤ 23 且**新增文件 0 报错** | `npx tsc --noEmit -p tsconfig.json` 报 **24** 条（基线 23）；本卡 4 文件命中 **0** 条；第 24 条为 **T-6 新文件** `tests/ask-confirm-pending.test.ts:55:36`（已由 T-6 复核 `t-51fc46` §3.4/D-A 记录在案，非本卡引入） | **不判本卡偏离**。依据：§3.3；FR-7 文件 0 命中，符合 T-10 口径（增量 = 0） |
| R12 | 父卡验收命令：`create-doc-location.test.ts` 全绿 | 独立复跑 5/5 绿（exit 0）；接口层 `tools-dispatch` 4/4 绿 | **无偏离**。依据：§3.1/§3.2 |

---

## 2. 偏离与观察项

### D-A（有偏离 · 功能未闭环 · 建议父卡收尾前裁决）

**设计与实现偏离**：`architecture.md` L52/L106 与 `decomposition.md` L66 均要求 T-10「**推进到终态**」——
具体路径是「复用 `advanceDraftToBrainstorming`（从 `CaptureRequirement.ts` 提到 `internal/`）返回终态」。
实测该函数仍是 `CaptureRequirement.ts:59-79` 的**局部函数**（HEAD 未提取），`CreateRequirement.ts` 也没有任何推进调用：
`reqboard_create` 返回 `status='draft'`，台账亦停在 `draft`（探针：`statusHistory=['draft']`）。

- **影响**：A5/NFR-1 的「三面一致可解释」只做到「返回值 = 台账」（这一条满足卡面验收），未做到「返回终态」或
  设计要求的「随后复用推进」；同时 TC-13 括注允许的备份口径「如实 draft + **未推进说明**」也未落实——
  当前 `note`（`CreateRequirement.ts:57-59`）只说「REQ 已在看板 draft 泳道立即可见」，没有一句
  「尚未推进 / 会被接手窗口自动推进」。
- **建议（二选一，均需人裁决）**：① 按 `architecture.md` L106 补实现（抽 `advanceDraftToBrainstorming` 到
  `internal/` 并复用，返回 `brainstorming`）；或 ② 把 I-6/architecture L106/decomposition L66 的「推进终态」
  收敛为 TC-13 的口径，并让 `note` 补一句明确的未推进说明。**本 review 卡只读，未改实现。**

### D-B（有偏离 · 兼容性措辞级 · 低）

I-6 兼容性列与 data-model L89 写「**只增键**；缺省与旧行为**逐字一致**」，但实现把既有键 `note` 的值在
**默认分支**也改写了（旧值以「本窗口已绑定」结尾，新值追加「未提供 doc_location → 已回落默认文档位置 …」，
见 `CreateRequirement.ts:57-59`）。这是「改既有键值」而非「只增键」。
判定：与 FR-7「回落可见」的要求存在设计内部张力——`defaults_used` 已足以承载「回落可见」，`note` 追加属增值。
**建议**：改 `interfaces.md` I-6 / `data-model.md` L89 的措辞（允许 `note` 追加回落说明），不必返工实现。

### O-1（观察项 · 非契约偏离）：工具提示词未同步「第四问」

`CreateTool/prompt.ts` 仍写「用户三问 / 按用户确认值调用——title、category、prompt_difficulty、summary、reason」，
未提 `doc_location`。入参 schema 已暴露该参数（模型可见），FR-7 的「工具暴露入参」达标；
但存在「降级路径 prompt 与工具参数不同步」的提示词一致性问题。属文档/提示词维护，非功能偏离。

### O-2（观察项 · 非矛盾）：额外加严的两条校验

`support.ts:227-234` 额外拒绝「非字符串」与「超长 > `LIMITS.pathMax`(400)」。E-6 只规定「形态非法 → 拒绝」，
未列这两条；二者与设计**不矛盾**（都属于「响亮失败、不静默改路径」）。同 `trim()` 后空串回落默认，
与工具描述一致。建议在 I-6/E-6 补一句可，不必返工。

### O-3（观察项 · 非本卡）：`tsc` 24 vs 基线 23

第 24 条为 T-6 新文件已知偏差（`t-51fc46-review.md` §3.4/D-A 已记录），本卡未引入任何新类型错误。
`size-budget`（`index.ts` 458 行）与 `layer-boundary` 各 1 红为 D-1 已登记基线红（T-12 范围），与本卡无关。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（独立复跑，与上游自述一致）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/create-doc-location.test.ts
```

实际输出：

```
 ✓ tests/create-doc-location.test.ts (5 tests) 42ms

 Test Files  1 passed (1)
      Tests  5 passed (5)
```

判定：**5/5 全绿、退出码 0** —— 覆盖 TC-11（回落+留痕+台账同值+消费端同源）、TC-12（自定义路径生效）、
TC-13（status 与台账一致）、异常流（4 种非法形态拒绝且不写台账）、schema 三键。

### 3.2 接口层回归（schema / 输出契约 / 分发）

```bash
npx vitest run tests/tools-dispatch.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts
```

```
 ✓ tests/tools-dispatch.test.ts (4 tests)
 ✓ tests/tools-schema.test.ts (3 tests)
 ✓ tests/output-contract.test.ts (21 tests)

 Test Files  3 passed (3)
      Tests  28 passed (28)
```

（与 3.1 合并一次运行的合计：**4 文件 33/33 绿**。）

### 3.3 类型检查（`npx tsc --noEmit -p tsconfig.json`）

```bash
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "error TS" | wc -l            # → 24
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "CreateTool|CreateRequirement|internal/support|create-doc-location" | wc -l   # → 0
```

- 错误总数 **24**；其中 **23 条为 D-1 基线**，第 24 条 `tests/ask-confirm-pending.test.ts(55,36): TS2322` 由 T-6 引入（`t-51fc46-review.md` 已记录）。
- 本卡 4 文件命中 **0** 条 —— 满足 T-10「增量 0」。

### 3.4 一次性探针（独立见证「返回状态 vs 台账状态」，跑完即删）

本轮另写 `tests/__probe-t8e8f83.test.ts`（1 例，跑后删除并复核 `No such file or directory`）：

```
 ✓ tests/__probe-t8e8f83.test.ts (1 test) 8ms
PROBE_OUT {"status":"draft","doc_location":"docs/requirements/<REQ>/","defaults_used":["doc_location"],
"note":"已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定。未提供 doc_location → 已回落默认文档位置 docs/requirements/<REQ>/（见 defaults_used，不静默猜）。",
"ledgerStatus":"draft","ledgerDocBasePath":"docs/requirements/<REQ>/","history":["draft"]}
```

- 见证三事：① 返回值与台账 `status` 一致（= `draft`，卡面验收满足）；②`doc_location` 与台账 `docBasePath` 同值且 `defaults_used` 留痕（R5/R6 成立）；
  ③ **无 draft→brainstorming 推进**（`history` 仅 `['draft']`）——D-A 的直接证据。

### 3.5 关联回归（capture 路径 / 装配 / 契约形状 / 基线红）

```bash
npx vitest run tests/capture-tool.test.ts tests/capture.test.ts tests/apply-wiring.test.ts tests/size-budget.test.ts tests/contract-shapes.test.ts
```

- 4 文件 **52/52 绿**（capture 两文件、apply-wiring、contract-shapes）——`support.ts` 改动未回归弹框立项路径。
- 唯一红为 `size-budget.test.ts`（`index.ts = 458 行`）——D-1/D-2 已登记基线红，由 T-12 修绿，与本卡无关。
- 另跑 `layer-boundary.test.ts`：8 通过 / 1 失败（基线 `diag-log.ts` 越界），`support.ts` 新增的 `capture-mapping`/`limits` import 均为 application→application/domain 同向，未新增越界。

---

## 4. 复核结论

1. **卡面验收三条全部满足**：目标测试 `create-doc-location.test.ts` 5/5 绿；不传 `doc_location` → 返回 `docs/requirements/<REQ>/` 且 `defaults_used` 含 doc_location、台账 `docBasePath` 同值；传 `docs/rfcs/` → 台账与产物路径按它生成；返回 `status` 与台账一致（独立探针见证）。
2. **发现 1 项功能级设计-实现偏离（D-A）**：I-6 / architecture L52-L106 / decomposition L66 要求的「推进终态（复用 `advanceDraftToBrainstorming`）」未实现，返回与台账停在 `draft`；TC-13 允许的备份口径「如实 draft + 未推进说明」中的说明也缺失。**建议父卡收尾前裁决**（补实现或收敛设计措辞）。
3. **另 1 项兼容性措辞偏离（D-B，低）+ 3 项观察项（O-1/O-2/O-3）**，均不阻断卡面验收。
4. **无护栏放松**：非法路径响亮失败且不写台账（R4）；未声明返回键被 output-contract 锁死（R2/R9）。
5. 本卡为 review 阶段，**只读复核 + 落本记录**；未修改任何实现、测试或配置源码（探针文件已删除）。本轮新增产物仅本文件。
6. **复核结论：通过（卡面验收达标）；附 1 项待裁决的设计偏离 D-A，不阻塞本卡，但建议父卡收尾前闭环。**
