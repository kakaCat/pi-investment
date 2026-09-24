# t-dde78e 联调记录（父卡 t-954348 / T-5「分化 G2 闸门文案并统一拒绝信封」· 阶段 integrate）

- 联调时间：2026-09-25T00:26+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（运行 banner 为准，darwin-arm64）· 测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 联调对象（接口）：
  - **I-9 闸门拒绝信封**：`envelope(f)`（唯一拼接入口，`src/application/internal/gate-feedback.ts`）+ `checkDesignCompletenessGate`（`src/application/internal/design-gates.ts`，未登记/待确认分叉）+ 真工具路径 `reqboard_move(to=decomposing)`（`MoveRequirement` → 抛错消息）
  - **I-3 弹框（已确认早返回补 `gate_failure`）**：`reqboard_ask_confirm`（`src/application/use-cases/AskConfirm.ts`）
- 结论：**接口联调通过** —— 5 个用例的「请求样例 → 期望响应 → 实际返回」三者一致（5/5 MATCH）；未登记与待确认两条拒绝文案同 `code`（`design_doc_incomplete`）但**互不相同**，各带唯一可行命令；目标测试 27/27 绿。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-tdde78e.test.ts`（跑完即删），对 I-9/I-3 各发真实调用，逐字段打印并比较「请求样例 / 期望响应 / 实际返回」。临时目录内预置 `docs/requirements/REQ-tdd001/requirement.md` 与 5 份 `design/*.md`（architecture / data-model / interfaces / test-cases / use-cases），台账按用例分别登记产物。

### C1 — I-9 `envelope(f)` 三要素拼接（纯函数）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"lead":"reqboard_move 未执行：","what":"docs/requirements/REQ-x/design/use-cases.md","why":"设计文档未在产物簿登记","how":"调 reqboard_submit(kind=design) 登记后再推进"}` |
| 期望响应 | `reqboard_move 未执行：docs/requirements/REQ-x/design/use-cases.md —— 设计文档未在产物簿登记。补齐：调 reqboard_submit(kind=design) 登记后再推进` |
| 实际返回 | 与期望**逐字相同** |
| 判定 | **一致（MATCH）** |

### C2 — I-9 `checkDesignCompletenessGate` **未登记**分叉（函数层）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"docs":"FileDocRepository<REQ-tdd001>","reqArtifactsRegistered":["architecture.md","data-model.md","interfaces.md","test-cases.md"]}`（磁盘 5 份、产物簿 4 份，缺 use-cases.md） |
| 期望响应 | `{code:"design_doc_incomplete", kind:"design", gaps:["docs/requirements/REQ-tdd001/design/use-cases.md 未登记（产物簿无此条，先调 reqboard_submit(kind=design)）"], message:"design → decomposing 的设计文档集：…未登记… —— 设计文档集未交齐或未全部确认。补齐：未交的按 templates/design/*.md 落盘，未登记的调 reqboard_submit(kind=design)，待确认的调 reqboard_ask_confirm(target=artifact, kind=design)"}` |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

### C3 — I-9 `checkDesignCompletenessGate` **待确认**分叉（函数层，同 code 不同话）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"docs":"FileDocRepository<REQ-tdd001>","reqArtifactsRegistered":[5 份],"unconfirmed":["use-cases.md"]}`（全部登记，use-cases.md 无 confirmedAt） |
| 期望响应 | `{code:"design_doc_incomplete", kind:"design", gaps:["docs/requirements/REQ-tdd001/design/use-cases.md 待确认（已登记未落章，先调 reqboard_ask_confirm(target=artifact, kind=design)）"], message:"…待确认… —— …。补齐：…"}` |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

- A2 核对：C2 与 C3 同 `code=design_doc_incomplete`，但 `gaps` 与 `message` 两串**不相同**（未登记 → `reqboard_submit(kind=design)`；待确认 → `reqboard_ask_confirm(...)`），两种病因两种话成立。

### C4 — I-9 真工具路径（`reqboard_move` 未登记拒绝）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_move","args":{"to":"decomposing"},"windowKey":"session-tdde78e"}` |
| 期望响应 | 抛错 `{code:"design_doc_incomplete", message:"reqboard_move 未执行：design → decomposing 的设计文档集：…use-cases.md 未登记… —— …。补齐：…（design_doc_incomplete）"}` |
| 实际返回 | 与期望**逐字相同** |
| 判定 | **一致（MATCH）** |

### C5 — I-3 `reqboard_ask_confirm` 已确认早返回补 `gate_failure`（TC-4）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_ask_confirm","args":{"target":"artifact","kind":"design","question":"确认？","options":["确认"]},"windowKey":"session-tdde78e"}`；前置：已确认产物覆盖磁盘 4/5，磁盘多 1 份未登记 |
| 期望响应 | `{success:true, confirmed:true, advanced:false, gate_failure:{code:"design_doc_incomplete", kind:"design", gaps:["…/use-cases.md 未登记（…先调 reqboard_submit(kind=design)）"], message:"… —— …。补齐：…"}, note:"产物 design 已确认，未重复弹框（FR-9/FR-11）；design → decomposing 未推进：…。仍有 1 份未登记"}` |
| 实际返回 | 与期望逐字段相同（含 `gate_failure.kind="design"`） |
| 判定 | **一致（MATCH）** |

探针执行结果（`--reporter=verbose`，逐例 `VERDICT MATCH`）：

```
 ✓ tests/__probe-tdde78e.test.ts > t-dde78e 联调：I-9 拒绝信封 + I-3 早返回 gate_failure > C1 envelope() 三要素拼接（纯函数）
 ✓ tests/__probe-tdde78e.test.ts > t-dde78e 联调：I-9 拒绝信封 + I-3 早返回 gate_failure > C2 I-9 checkDesignCompletenessGate 未登记分叉（函数层）
 ✓ tests/__probe-tdde78e.test.ts > t-dde78e 联调：I-9 拒绝信封 + I-3 早返回 gate_failure > C3 I-9 checkDesignCompletenessGate 待确认分叉（函数层，同 code 不同话）
 ✓ tests/__probe-tdde78e.test.ts > t-dde78e 联调：I-9 拒绝信封 + I-3 早返回 gate_failure > C4 I-9 真工具路径 reqboard_move(to=decomposing) 未登记拒绝
 ✓ tests/__probe-tdde78e.test.ts > t-dde78e 联调：I-9 拒绝信封 + I-3 早返回 gate_failure > C5 I-3 reqboard_ask_confirm 已确认早返回补 gate_failure

 Test Files  1 passed (1)
      Tests  5 passed (5)
```

首次运行时 C5 报 MISMATCH，定位为**探针期望值漏写 `gate_failure.kind="design"`**（非实现缺陷）：补齐期望值后 5/5 MATCH。据此确认返回体形态与设计契约（`GateFailure = {code, kind, gaps, message}`）一致。

---

## 2. 目标命令与输出摘要

### 2.1 T-5 验收命令（父卡 acceptance）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts
```

实际输出：

```
 ✓ tests/gate-feedback-envelope.test.ts (5 tests) 33ms
 ✓ tests/design-gate-messages.test.ts (6 tests) 69ms
 ✓ tests/design-completeness-gate.test.ts (16 tests) 190ms

 Test Files  3 passed (3)
      Tests  27 passed (27)
```

- 期望：全绿（含拆解计划「基线缺口」里 2 个历史红例 —— `design-completeness-gate.test.ts` 原 2 例失败）
- 实际：27/27 通过，退出码 0 —— 与期望一致

### 2.2 弹框回归（I-3 改动面）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ask-confirm.test.ts tests/confirm-evidence.test.ts
```

实际输出：

```
 ✓ tests/confirm-evidence.test.ts (6 tests) 76ms
 ✓ tests/ask-confirm.test.ts (11 tests) 137ms

 Test Files  2 passed (2)
      Tests  17 passed (17)
```

- 期望：I-3 的 `gate_failure` 早返回改动不回归既有确认语义与文字证据核验
- 实际：17/17 通过，退出码 0 —— 与期望一致

---

## 3. 联调结论

1. 接口 I-9（拒绝信封 `envelope` / `checkDesignCompletenessGate` 两种病因 / `reqboard_move` 真工具路径）与 I-3（`reqboard_ask_confirm` 已确认早返回补 `gate_failure`）的**请求样例 → 期望响应 → 实际返回**三方一致，**5/5 例 MATCH**。
2. 同一条 `design_doc_incomplete`：**未登记**消息含「未登记」+ `reqboard_submit(kind=design)`；**待确认**消息含「待确认」+ `reqboard_ask_confirm(target=artifact, kind=design)`；两串不相同。所有拒绝 `message` 含 `——` 与 `补齐：`，`how` 命中可执行锚点（`reqboard_*` / `templates/`）。
3. `code` 与 `gaps` 结构未因改文案而变化（`kind="design"` 随 `GateFailure` 一并透出，护栏强度不降）。
4. 目标命令 `npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts` **27/27 绿**；I-3 回归 17/17 绿。
5. 本卡为 integrate 阶段，只执行上述命令与探针并落本记录；**未修改任何实现或测试源码**，本轮新增产物仅本文件；临时探针 `tests/__probe-tdde78e.test.ts` 已在本轮内删除（`rm -f`，复核 `No such file or directory`）。
