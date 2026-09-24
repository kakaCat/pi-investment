# t-792c94 复核记录（父卡 t-954348 / T-5「分化 G2 闸门文案并统一拒绝信封」· 阶段 review）

- 复核时间：2026-09-25T≈00:27+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`（branch `main`）
- 复核对象（研发 t-114ef1 产出）：
  - `packages/web/dsh-pmboard/src/application/internal/gate-feedback.ts`（新增，envelope 唯一拼接入口 + `GATE_HOW_ANCHOR`）
  - `packages/web/dsh-pmboard/src/application/internal/design-gates.ts`（G2 gaps 分叉 + 拆分内容门/可打开性门走 envelope）
  - `packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts`（6 处 GateFailure.message 走 envelope）
  - `packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`（已确认早返回补 `gate_failure`）
  - 用例侧（仅改文案，不改判定）：`use-cases/SubmitArtifact.ts`（REQBOARD_MISSING_REQUIRED_DOC）、`use-cases/ConfirmArtifact.ts`（REQBOARD_EVIDENCE_FAKE）
  - `tests/design-gate-messages.test.ts`（TC-2/3/4）、`tests/gate-feedback-envelope.test.ts`（TC-21/22）、`tests/design-completeness-gate.test.ts`（校准 + 历史 2 红转绿）
- 设计依据（比对基线）：`design/interfaces.md` §I-9（含 12 code 覆盖清单与 `<tool> 未执行：<what> —— <why>。补齐：<how>` 格式）、`design/architecture.md` §「闸门拒绝信封」（L170-201，含 how 锚点与零信任核对）、`design/test-cases.md` TC-2/TC-3/TC-4/TC-21/TC-22/TC-18、`decomposition.md` T-5 行 + D-3 + 修改盘点、任务卡 `tasks/t-954348.md` acceptance
- 复核方式：读 `git diff` 逐点比对设计契约（区分「只改文案」与「改判定」）+ 独立复跑父卡验收命令与相关回归（不采信上游自述）；另核对 envelope 是否为唯一拼接入口、I-9 的 12 个 code 是否全部走信封、全量套件是否新增失败。

---

## 1. 逐条复核结论（设计与实现）

| 编号 | 设计点（出处） | 实现 | 结论 |
|---|---|---|---|
| R1 | 新增 `gate-feedback.ts`：`envelope(f)` 为拒绝消息三要素的**唯一拼接入口**，形态 `<what> —— <why>。补齐：<how>`，`lead` 可选（interfaces.md §I-9 / architecture.md L175-179） | `envelope()` 仅一处 `fmt('{lead}{what} —— {why}。补齐：{how}')`；全仓 `'补齐：'` 模板只此一处（其余均为注释） | **无偏离**。依据：gate-feedback.ts:46-53；`grep '补齐：' src/**/*.ts` 仅命中该文件（与 `.md` 无关）。额外导出 `GATE_HOW_ANCHOR`（实现与测试共用同一锚点正则，见 R7），属**加法不改契约**。 |
| R2 | `design-gates.ts`：G2 gaps 按 `art === undefined`（未登记）/ `confirmedAt === undefined`（待确认）**分叉**，各带唯一命令（interfaces.md §I-9 E-7/E-8、T-5 test-cases TC-2/TC-3） | `checkDesignCompletenessGate` 两个分支分别 push「未登记（产物簿无此条，先调 reqboard_submit(kind=design)）」/「待确认（已登记未落章，先调 reqboard_ask_confirm(target=artifact, kind=design)）」；原 `art === undefined \|\| art.confirmedAt === undefined` 的判定**并集不变** | **无偏离**。依据：design-gates.ts:173-182；`design-gate-messages.test.ts`「同一条 design_doc_incomplete，两串不相同」逐字断言（L127-145）。 |
| R3 | `design-gates.ts`：`checkDesignDecompositionGate` 与可打开性门（`REQBOARD_ARTIFACT_NOT_OPENABLE`/`REQBOARD_FILE_MISSING`）文案走 envelope，判定不动（interfaces.md §I-9 覆盖 code 表） | 拆分内容门 `envelope({what/why/how})`；`openableError` 改收 `GateFeedback` 并 `envelope(f) + '（code）'`；4 个 `openableError` 调用点补 why/how，形态判定顺序（空/反斜杠+..→归一→pseudo/outside→exists）逐字未动 | **无偏离**。依据：design-gates.ts:44-66、:79-123；`git diff` 只重写 message 形参（R3 见 §3.3）。 |
| R4 | `content-gate-wiring.ts`：**6 处** GateFailure.message 统一走 envelope（判定逻辑不动）（T-5 implementation / D-3） | `requirement_uncovered` / `design_orphan` / `requirement_missing_clauses` / `requirement_clause_sequence_gap` / `requirement_clause_duplicates` / `dangling_reference` 均改 `envelope({...})`；`code`/`gaps`/kind 与判定条件未改 | **无偏离**。依据：content-gate-wiring.ts:97-107、:138-148、:176-218、:377-391；`git diff` 6 处均为 message 替换。 |
| R5 | `AskConfirm.ts`：`alreadyConfirmed` 早返回先跑 G2，补 `gate_failure` + 「仍有 N 份未登记」（interfaces.md §I-3、architecture.md L101/L237、TC-4） | 早返回分支对 `targetKind==='artifact' && kindRaw==='design'` 调 `checkDesignCompletenessGate`；有缺口时返回体注入 `gate_failure` 并 `note` 追加「design → decomposing 未推进：{msg}。仍有 {n} 份未登记」；无缺口时不带该键（不制造噪声） | **无偏离**。依据：AskConfirm.ts:76-95；`design-gate-messages.test.ts` TC-4 两例（带缺口 / 无缺口）。 |
| R6 | 护栏强度不降（NFR-2 / D-3）：`code` 与 `gaps` 结构不变；`REQBOARD_EVIDENCE_FAKE` 仍拒（TC-18）；`how` 变更不等于放松判定 | `AssertArtifactGates` 等两级登记态闸门判定未动；`REQBOARD_EVIDENCE_FAKE` 仅在 envelope 包裹下保留原 `check.ok` 判定与 code；`gate-feedback-envelope.test.ts` 负例断言 `gaps` 逐项字符串与 code 不变 | **无偏离**。依据：`gate-feedback-envelope.test.ts`「TC-21 负例」（3 例）；`confirm-evidence.test.ts` 6/6 绿（见 §3.2）。 |
| R7 | I-9 的 **12 个 code** 每条 message 含 `——` 与 `补齐：`，且 how 命中可执行锚点（`/reqboard_[a-z_]+/` / `templates/` / `design_exempt`）（architecture.md L200-201、TC-21） | `gate-feedback-envelope.test.ts` 用**真实触发闸门**（非拼串）逐 code 产 12 例并断言三要素 + `GATE_HOW_ANCHOR`（导出共用）；含 design_doc_incomplete 两态、design_orphan、dangling_reference、requirement_uncovered、requirement_missing/sequence/duplicates、design_contains_decomposition、两 openable code、REQBOARD_MISSING_REQUIRED_DOC、REQBOARD_EVIDENCE_FAKE | **无偏离**。依据：`gate-feedback-envelope.test.ts` L123-232（12 例逐一断言 code/——/补齐：/锚点）；12 个 code 的**构造点全部**已走 envelope（见 §3.4 逐 code 定位）。 |
| R8 | TC-22 集成：`design_orphan` → 「补 serves: FR-#」；`REQBOARD_MISSING_REQUIRED_DOC` → 「按 templates/design 生成或 design_exempt」（test-cases.md TC-22） | 两条 how 实际文本分别为「在标题行补 serves: FR-#（多值逗号分隔）后重调 reqboard_submit(kind=plan)…」与「按 templates/design/*.md 生成缺失设计文档… design_exempt=<文件名>=理由」；TC-22 两例真实触发（闸门函数 / `reqboard_submit(kind=plan)` 真工具） | **无偏离**。依据：content-gate-wiring.ts:146、SubmitArtifact.ts:231；`gate-feedback-envelope.test.ts` 例 3 与例 11。 |
| R9 | 测试落点与基线红例：三文件全绿（含 `design-completeness-gate.test.ts` 基线 2 个历史红例）（tasks/t-954348.md acceptance） | 独立复跑 3 文件 **27/27 绿**；全量套件 `design-completeness-gate.test.ts` 已转绿（基线 7 文件/9 用例失败 → 6 文件/7 用例，**净 -1 文件 / -2 用例**，无新增失败） | **无偏离**，见 §3.1、§3.5。 |
| R10 | `interfaces.md` §I-9 覆盖 code 表**逐字**含 `design_doc_incomplete` 与 `design_contains_decomposition`，即两 code 全部出现路径都应走信封 | G2 两 code 在**工具/用例/看板主路径**均走 envelope；但看板侧 `http/routers/requirements.ts` 两处「docs 端口未装配」的 fail-closed 分支产出**同 code、非信封**消息 | **有偏离（低危，见 §2 D-1）**：仅在 `deps.docs === undefined` 的部署异常路径可达，非内容闸门判定；不在 `decomposition.md` T-5 修改盘点的文件清单内。 |
| R11 | I-9 格式行 `<tool> 未执行：<what> —— <why>。补齐：<how>`（interfaces.md L22 / architecture.md L178，`lead` 为「工具上下文」） | `requirement_*`/openable/design_contains_decomposition 的 lead 均带工具名（如 `reqboard_requirement_submit 未执行：`、`reqboard_plan_submit 未执行：`）；`design_orphan`/`dangling_reference` 沿用改造前的前缀 `提交未执行：`（无 `reqboard_*`） | **有偏离（外观级，见 §2 D-2）**：不符合格式行字面；但保留的是改造前既有前缀，且 how 段点名 `reqboard_submit(kind=plan)`；TC-21/父卡验收均只断言 `——` 与 `补齐：`，不影响可证伪性。 |
| R12 | T-5 不负责 FR-8（pm 弹框来源标志）：`header` 改 `📋 PM · ` 属 T-11（decomposition T-11） | AskConfirm.ts:111 `header: '确认'` 未改 | **不判偏离**：属 T-11 落点，T-5 卡范围不含；T-11 尚未合入时保持旧文案是预期状态。 |

---

## 2. 偏离与观察项

**未发现阻塞性（行为）偏离。** 以下为 2 项非阻塞偏离 + 2 项观察项：

- **D-1（低危偏离，I-9 覆盖完整性）**：`http/routers/requirements.ts` 两处 fail-closed 分支产出未走 envelope 的同 code 消息——
  `g2CompletenessFailure`（:39，`deps.docs === undefined`）返回 `{code:'design_doc_incomplete', message:'design → decomposing 被拦：文档读取端口未装配，无法核验文档集完整性'}`；
  `handleArtifactConfirm`（:203，`deps.docs === undefined`）抛 `{code:'design_contains_decomposition', message:'确认被拦：文档读取端口未装配，无法扫描设计文档拆分内容'}`。
  设计 I-9 的 code 覆盖表把两 code 都列为信封对象，故字面上这两条不算「统一走 envelope」。
  **判定**：可达条件仅为「docs 端口未装配」的部署异常（正常装配下不可达），非内容判定结果，且该文件不在 T-5 修改盘点清单（implementation 只列 design-gates / content-gate-wiring / AskConfirm / SubmitArtifact / ConfirmArtifact）。
  建议（可选、不阻塞）：下阶段或 T-12 顺手把这两条 fail-closed 文案也走 `envelope()`（或显式在 I-9 旁注明「部署异常 fail-closed 消息不在信封契约内」），以消除 code 与信封覆盖表的字面差。
- **D-2（外观级偏离，lead 前缀）**：`design_orphan` / `dangling_reference` 的 lead 为 `提交未执行：`，非 I-9 格式行的 `<tool> 未执行：`（对应工具应为 `reqboard_submit(kind=plan)`）。
  **判定**：该前缀为改造前原文，T-5 仅重排 why/how；how 已点名可执行命令；TC-21 与父卡验收不校验前缀。**不阻塞**。建议：若追求 I-9 格式行的字面一致，可把 lead 改为 `reqboard_submit(kind=plan) 未执行：`。
- **O-1（观察，无触发路径）**：architecture.md L198 写「`gap` 为空/形态不认识时不伪造 why，如实写『未分类缺口』并给通用下一步」，实现中无「未分类缺口」分支。核对：所有产 `GateFailure` 的闸门在 `gaps.length === 0` 时均提前 `return undefined`（content-gate-wiring:95/136/184/219/375、design-gates:43/184），`what/why/how` 均为常量非空，故该回退**不可达**；`envelope` 缺失字段会由 `fmt` 直接抛错（不产出 `undefined` 脏文案）。无当前行为影响。
- **O-2（观察，实现耦合）**：AskConfirm 早返回的未登记计数用 `gaps.filter(g => g.includes('未登记'))`（AskConfirm.ts:83），语义正确但耦合 G2 gap 的中文措辞；若未来改措辞，计数会静默归零（`note` 少一句，不影响推进/落章）。建议（可选）：由闸门返回结构化计数或按 code 明细判。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（复跑）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts
```

实际输出（退出码 0）：

```
 ✓ tests/gate-feedback-envelope.test.ts (5 tests) 43ms
 ✓ tests/design-gate-messages.test.ts (6 tests) 70ms
 ✓ tests/design-completeness-gate.test.ts (16 tests) 197ms

 Test Files  3 passed (3)
      Tests  27 passed (27)
```

判定：**与父卡 acceptance 一致**（27/27 绿，含 `design-completeness-gate.test.ts` 的历史 2 红已转绿）。

### 3.2 相关回归（I-3 / TC-18 改动面）

```bash
npx vitest run tests/ask-confirm.test.ts tests/confirm-evidence.test.ts
```

```
 ✓ tests/confirm-evidence.test.ts (6 tests) 290ms
 ✓ tests/ask-confirm.test.ts (11 tests) 595ms

 Test Files  2 passed (2)
      Tests  17 passed (17)
```

判定：AskConfirm 早返回补 `gate_failure` 未回归既有确认语义；`REQBOARD_EVIDENCE_FAKE` 证据核验护栏仍生效（6/6）。

### 3.3 diff 性质确认（「只改文案不改判定」）

```bash
git diff -- src/application/internal/design-gates.ts src/application/internal/content-gate-wiring.ts \
  src/application/use-cases/SubmitArtifact.ts src/application/use-cases/ConfirmArtifact.ts
```

读 diff 结论：

- `content-gate-wiring.ts`：6 处 `message:` 由旧 `fmt(...)`/字符串拼接换成 `envelope({...})`，`code`/`gaps`/`return` 条件**逐字未动**；
- `design-gates.ts`：`openableError` 形参由 `message: string` 改为 `f: GateFeedback`，4 个调用点补 why/how，**形态判定顺序与 `docs.exists` 分支未动**；`checkDesignCompletenessGate` 的 `if` 由「或」拆成两分支（判定并集不变）；`checkDesignDecompositionGate` 仅换 message；
- `SubmitArtifact.ts` / `ConfirmArtifact.ts`：各 1 处 `reject(...)` 文案改 `envelope(...)`，code 与触发条件未动；
- `AskConfirm.ts`：仅在 `alreadyConfirmed` 分支内新增 G2 查询与返回键，旧返回键与文案逐字保留其余部分。

### 3.4 I-9 的 12 个 code 构造点逐一定位

```bash
# 逐 code grep（packages/web/dsh-pmboard/src，*.ts）
```

结论（构造点 → 是否 envelope）：

| code | 构造点 | envelope |
|---|---|---|
| design_doc_incomplete | design-gates.ts:186 | ✓ |
| design_orphan | content-gate-wiring.ts:139 | ✓ |
| dangling_reference | content-gate-wiring.ts:381 | ✓ |
| requirement_uncovered | content-gate-wiring.ts:98 | ✓ |
| requirement_missing_clauses | content-gate-wiring.ts:178 | ✓ |
| requirement_clause_sequence_gap | content-gate-wiring.ts:193 | ✓ |
| requirement_clause_duplicates | content-gate-wiring.ts:209 | ✓ |
| REQBOARD_MISSING_REQUIRED_DOC | SubmitArtifact.ts:233 | ✓ |
| REQBOARD_ARTIFACT_NOT_OPENABLE | design-gates.ts:83/91/102/109 | ✓ |
| REQBOARD_FILE_MISSING | design-gates.ts:116 | ✓ |
| design_contains_decomposition | design-gates.ts:45 | ✓ |
| REQBOARD_EVIDENCE_FAKE | ConfirmArtifact.ts:56 | ✓ |

（表外两处同 code 的 fail-closed 分支见 §2 D-1。）

### 3.5 全量套件（基线对比，防新增失败）

```bash
npx vitest run 2>&1 | grep -E 'FAIL|Test Files|Tests '
```

```
 FAIL  tests/application/repository.test.ts > … RandomIdFactory：前缀与 6 位 hex 格式
 FAIL  tests/client-view.test.ts > buildBoard > excludes archived and canceled from lanes…
 FAIL  tests/layer-boundary.test.ts > … application/ 不得 import 禁止项
 FAIL  tests/size-budget.test.ts > … src 下所有 .ts 单文件 ≤ 400 行
 FAIL  tests/template-address-injection.test.ts > TC-11 压缩路径…（2 例）
 FAIL  tests/typecheck.test.ts > … tsc --noEmit 零错误
 Test Files  6 failed | 146 passed (152)
      Tests  7 failed | 1801 passed (1808)
```

- 基线（decomposition.md §基线缺口）：7 文件 / 9 用例失败。现为 **6 文件 / 7 用例失败**，差额恰为 `design-completeness-gate.test.ts` 的 2 个历史红例（T-5 修绿）——**无新增失败**。
- 逐项归因（均为基线既有、与 T-5 无关）：
  - `size-budget.test.ts` → 仅 `index.ts = 434 行`（D-2，T-12 范围）；新增 `gate-feedback.ts` 53 行远低于上限，无新超标文件；
  - `layer-boundary.test.ts` → 仅 `application/internal/diag-log.ts -> node:fs/node:path`（基线既有）；T-5 新增 `gate-feedback.ts` 只 import `domain/text/fmt.js`，未新增越界；
  - `typecheck.test.ts` → 23 条（与基线同量级，主要在 `domain/template/*`）；
  - `repository.test.ts` / `client-view.test.ts` / `template-address-injection.test.ts` → 基线既有。

### 3.6 envelope 唯一性核对

```bash
grep -rn '补齐：' packages/web/dsh-pmboard/src --include='*.ts'
```

结论：模板字符串仅 `gate-feedback.ts:47` 一处，其余命中均为注释/文档描述；未发现第二套拼接实现。

---

## 4. 结论

1. T-5 实现与 `interfaces.md` §I-9、`architecture.md` §闸门拒绝信封、TC-2/3/4/21/22、T-5 卡 acceptance **逐条一致**：R1–R9 全部「无偏离」并给出依据；R12 属 T-11 不判。
2. 发现 **2 项非阻塞偏离**：D-1（看板侧两处「docs 端口未装配」fail-closed 分支未走 envelope，仅部署异常路径可达、不在本卡文件清单）；D-2（`design_orphan`/`dangling_reference` 的 `lead` 沿用旧前缀 `提交未执行：`，不符 I-9 格式行字面但不影响验收与可证伪性）。另有 O-1（「未分类缺口」回退不可达）、O-2（未登记计数耦合中文字面）两项观察。
3. 独立复跑：父卡验收命令 **27/27 绿**；`ask-confirm`+`confirm-evidence` 回归 **17/17 绿**；全量套件较基线**净减 1 文件 / 2 用例失败，零新增失败**；`git diff` 证实所有改动均为「文案替换 / 新增返回键」，判定与 `code`/`gaps` 结构未动（NFR-2 护栏强度不降）。
4. **复核结论：通过（T-5 可进入测试阶段 t-44b8c6）**。D-1/D-2 为可选加固项，不构成本卡返工理由。
