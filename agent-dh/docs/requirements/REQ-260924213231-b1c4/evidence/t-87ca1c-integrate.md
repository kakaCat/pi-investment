# t-87ca1c 联调记录（父卡 t-145cb0 / T-13「迁移兼容卡与 E2E 复跑」· 阶段 integrate）

- 联调时间：2026-09-25T02:16+0800
- 联调环境：node v22.23.2 · vitest/2.1.9 (darwin-arm64) · 工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口 / 接缝，编号对齐 `design/interfaces.md`）：
  - **I-1** `reqboard_submit(kind=design)` —— `src/tools/SubmitTool/SubmitTool.ts` + 用例 `src/application/use-cases/SubmitArtifact.ts`（FR-1）
  - **I-3** `reqboard_ask_confirm(target=artifact, kind=design)`（弹框路径，默认自动推进） —— `src/tools/AskConfirmTool/AskConfirmTool.ts`
  - **I-9 / E-3 / E-8** 闸门拒绝信封 —— `MoveRequirement.ts` 的 `REQBOARD_MISSING_ARTIFACT` / `REQBOARD_ARTIFACT_NOT_CONFIRMED`
  - **迁移兼容** `scripts/migrate-ledger.ts`（真实样本 v4 → v7 无损、老需求不注入 `interruption`）
  - **FR-6 续跑输入包** `src/application/internal/node-input-package.ts`（老需求无 `interruption` 逐字节兼容）
- 结论：**接口联调通过** —— **8/8 例 MATCH**（请求样例 / 期望响应 / 实际返回三者一致）；
  目标命令 `npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts` **3 文件 / 25 用例全绿（exit 0）**。
  全量套件另有 **1 例新增红**（`language-layer.test.ts`，非本卡文件、归 T-8），见 §5-F-1 —— 父卡验收的「失败集合 ⊆ 基线且不新增失败」一项因此**未达成**，需在 T-8 侧收口。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**一次性探针** `tests/__probe-t87ca1c.test.ts`（对真实工具壳 + 真实适配器 `JsonLedgerRepository`/`FileDocRepository` 发调用；跑完已 `rm` 删除，`tests/` 下无 `__probe-t87ca1c` 残留），逐例打印「请求样例 / 期望响应 / 实际返回」并比较。

### C1 — I-1 `reqboard_submit(kind=design)`（落盘 5 份后登记）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"kind":"design"}`（exec = `{agent:{id:'session-e2e-design-001'}}`，需求 REQ-e2e001 status=design，design/ 下已落 5 份） |
| 期望响应 | `{"success":true,"requirement_id":"REQ-e2e001","registered_count":5,"design_docs":[{"name":"architecture.md","on_disk":true,"registered":true,"confirmed":false},{"name":"data-model.md","on_disk":true,"registered":true,"confirmed":false},{"name":"interfaces.md","on_disk":true,"registered":true,"confirmed":false},{"name":"test-cases.md","on_disk":true,"registered":true,"confirmed":false},{"name":"use-cases.md","on_disk":true,"registered":true,"confirmed":false}]}` |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

```
C1 REQUEST : {"kind":"design"}
C1 EXPECTED: {"success":true,"requirement_id":"REQ-e2e001","registered_count":5,"design_docs":[{"name":"architecture.md","on_disk":true,"registered":true,"confirmed":false},{"name":"data-model.md","on_disk":true,"registered":true,"confirmed":false},{"name":"interfaces.md","on_disk":true,"registered":true,"confirmed":false},{"name":"test-cases.md","on_disk":true,"registered":true,"confirmed":false},{"name":"use-cases.md","on_disk":true,"registered":true,"confirmed":false}]}
C1 ACTUAL  : {"success":true,"requirement_id":"REQ-e2e001","registered_count":5,"design_docs":[{"name":"architecture.md","on_disk":true,"registered":true,"confirmed":false},{"name":"data-model.md","on_disk":true,"registered":true,"confirmed":false},{"name":"interfaces.md","on_disk":true,"registered":true,"confirmed":false},{"name":"test-cases.md","on_disk":true,"registered":true,"confirmed":false},{"name":"use-cases.md","on_disk":true,"registered":true,"confirmed":false}]}
C1 VERDICT : MATCH
```

### C2 — I-3 `reqboard_ask_confirm(target=artifact, kind=design)`（肯定项，默认自动推进）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"target":"artifact","kind":"design","question":"设计文档已完成，是否确认进入拆分？","options":["确认，进入拆分","需要修改"]}`（假弹框通道返回首个肯定项，证明走弹框路径） |
| 期望响应 | `{"success":true,"requirement_id":"REQ-e2e001","confirmed":true,"advanced":true,"to":"decomposing"}` |
| 实际返回 | 与期望逐字段相同（同验：5 份全部落章 `confirmedAt` 非空、需求 status=decomposing） |
| 判定 | **一致（MATCH）** |

```
C2 REQUEST : {"target":"artifact","kind":"design","options":["确认，进入拆分","需要修改"]}
C2 EXPECTED: {"success":true,"requirement_id":"REQ-e2e001","confirmed":true,"advanced":true,"to":"decomposing"}
C2 ACTUAL  : {"success":true,"requirement_id":"REQ-e2e001","confirmed":true,"advanced":true,"to":"decomposing"}
C2 VERDICT : MATCH
```

### C3 — I-9 / E-3 闸门：登记前 move 被拦（修的是入口，不是闸门）

| 项 | 内容 |
|---|---|
| 请求样例 | `reqboard_move` `{"to":"decomposing"}`（文档已落盘但产物簿无 `kind=design`） |
| 期望响应 | 拒绝码 `REQBOARD_MISSING_ARTIFACT` |
| 实际返回 | `REQBOARD_MISSING_ARTIFACT` |
| 判定 | **一致（MATCH）** |

```
C3 REQUEST : {"to":"decomposing"}
C3 EXPECTED: {"error_code":"REQBOARD_MISSING_ARTIFACT"}
C3 ACTUAL  : {"error_code":"REQBOARD_MISSING_ARTIFACT"}
C3 VERDICT : MATCH
```

### C4 — I-9 / E-8 两态文案分叉：已登记未落章时 move 报待确认

| 项 | 内容 |
|---|---|
| 请求样例 | submit 后立刻 `reqboard_move` `{"to":"decomposing"}` |
| 期望响应 | 拒绝码 `REQBOARD_ARTIFACT_NOT_CONFIRMED`（与 C3 不同态） |
| 实际返回 | `REQBOARD_ARTIFACT_NOT_CONFIRMED` |
| 判定 | **一致（MATCH）** |

```
C4 REQUEST : {"to":"decomposing"}
C4 EXPECTED: {"error_code":"REQBOARD_ARTIFACT_NOT_CONFIRMED"}
C4 ACTUAL  : {"error_code":"REQBOARD_ARTIFACT_NOT_CONFIRMED"}
C4 VERDICT : MATCH
```

### C5 — 字面三步链：submit → ask_confirm(`advance:false`) → move

| 项 | 内容 |
|---|---|
| 请求样例 | `{"submit":{"kind":"design"},"ask":{"advance":false},"move":{"to":"decomposing"}}` |
| 期望响应 | `{"ask":{"success":true,"requirement_id":"REQ-e2e001","confirmed":true,"advanced":false,"to":"design"},"move":{"success":true,"requirement_id":"REQ-e2e001","to":"decomposing"},"statusAfterMove":"decomposing"}`（`advance:false` 只落章不推进，`to` 回显当前状态 design；推进由显式 move 完成） |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

```
C5 REQUEST : {"submit":{"kind":"design"},"ask":{"advance":false},"move":{"to":"decomposing"}}
C5 EXPECTED: {"ask":{"success":true,"requirement_id":"REQ-e2e001","confirmed":true,"advanced":false,"to":"design"},"move":{"success":true,"requirement_id":"REQ-e2e001","to":"decomposing"},"statusAfterMove":"decomposing"}
C5 ACTUAL  : {"ask":{"success":true,"requirement_id":"REQ-e2e001","confirmed":true,"advanced":false,"to":"design"},"move":{"success":true,"requirement_id":"REQ-e2e001","to":"decomposing"},"statusAfterMove":"decomposing"}
C5 VERDICT : MATCH
```

### C6 — 迁移兼容：legacy（`artifacts` 空/undefined）需求 design→decomposing 仍放行

| 项 | 内容 |
|---|---|
| 请求样例 | 需求 `artifacts: undefined`（存量），`reqboard_move` `{"to":"decomposing"}` |
| 期望响应 | `{"move":{"success":true,"requirement_id":"REQ-e2e001","to":"decomposing"},"statusAfterMove":"decomposing","artifacts":0}`（放行不等于伪造：产物簿仍空） |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

```
C6 REQUEST : {"to":"decomposing"}
C6 EXPECTED: {"move":{"success":true,"requirement_id":"REQ-e2e001","to":"decomposing"},"statusAfterMove":"decomposing","artifacts":0}
C6 ACTUAL  : {"move":{"success":true,"requirement_id":"REQ-e2e001","to":"decomposing"},"statusAfterMove":"decomposing","artifacts":0}
C6 VERDICT : MATCH
```

### C7 — 迁移接口：v4 真实样本 → v7 无损且不注入 `interruption`

| 项 | 内容 |
|---|---|
| 请求样例 | `{"migrate":"tests/fixtures/ledger-v4-sample.json","now":1700000000000}`（34 需求 / 97 任务真实副本，2026-09-17 冻结） |
| 期望响应 | `{"schemaVersion":7,"migrations":3,"requirements":34,"tasks":97,"triages":2,"whitelistOutside":0,"interruptionInjected":false}` |
| 实际返回 | 与期望逐字段相同（白名单外差异 0 条；老需求无 `interruption` 字段不被凭空注入） |
| 判定 | **一致（MATCH）** |

```
C7 REQUEST : {"migrate":"ledger-v4-sample.json","now":1700000000000}
C7 EXPECTED: {"schemaVersion":7,"migrations":3,"requirements":34,"tasks":97,"triages":2,"whitelistOutside":0,"interruptionInjected":false}
C7 ACTUAL  : {"schemaVersion":7,"migrations":3,"requirements":34,"tasks":97,"triages":2,"whitelistOutside":0,"interruptionInjected":false}
C7 VERDICT : MATCH
```

### C8 — FR-6 老需求无 `interruption`：续跑输入包逐字节不变

| 项 | 内容 |
|---|---|
| 请求样例 | `buildNodeInputPackage({stage:'brainstorming', requirement: 老需求})` 与 `{...老需求, interruption: undefined}` 两次构建 |
| 期望响应 | `{"identicalWhenExplicitUndefined":true,"hasBreakpointSection":false,"legacyLayoutIntact":true}`（不出现「## 断点」节；`## 未决问题\n（无）\n\n## 下一步` 布局原样） |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

```
C8 REQUEST : {"legacyInterruption":"absent","variant":"explicit-undefined"}
C8 EXPECTED: {"identicalWhenExplicitUndefined":true,"hasBreakpointSection":false,"legacyLayoutIntact":true}
C8 ACTUAL  : {"identicalWhenExplicitUndefined":true,"hasBreakpointSection":false,"legacyLayoutIntact":true}
C8 VERDICT : MATCH
```

> 探针汇总：`PROBE_TOTAL=8 MATCH=8 MISMATCH=0`（`Tests 9 passed` 含汇总例）/ exit 0；跑完 `rm` 删除，`tests/__probe-t87ca1c.test.ts` 不存在（`ls` → No such file or directory）。

---

## 2. 目标命令（父卡 T-13 验收命令）与输出摘要

```
$ cd packages/web/dsh-pmboard
$ npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts
 ✓ tests/migration.test.ts (9 tests) 33ms
 ✓ tests/consistency.test.ts (11 tests) 3ms
 ✓ tests/e2e-design-handoff.test.ts (5 tests) 86ms

 Test Files  3 passed (3)
      Tests  25 passed (25)
   Start at  02:16:10
TRIO_EXIT=0
```

- `e2e-design-handoff.test.ts` 5 例（TC-19，E2E 落点，本卡新增文件）：
  1. 登记前 move 仍被产物存在门拦住：`REQBOARD_MISSING_ARTIFACT`（修的是入口，不是闸门）
  2. 登记 ≠ 落章：submit 后未确认时 move 报 `REQBOARD_ARTIFACT_NOT_CONFIRMED`（两态文案分叉）
  3. 一次通过（A1）：submit(kind=design) → ask_confirm（默认自动推进）→ 需求直接进入 decomposing，全程无 `REQBOARD_MISSING_ARTIFACT`
  4. 字面三步链（卡面顺序）：落盘 5 份 → submit(design) → ask_confirm(advance:false) → move(decomposing) 一次通过
  5. 迁移兼容：legacy（artifacts 空）存量需求 design→decomposing 仍放行，不要求登记/确认
- `migration.test.ts` 9 例（既有文件，本卡只回归未改动）：真实样本 v4→v7 链式升级无损（白名单外 0 条）、幂等、C3/C4/C6/C7/C8/C9/C10 逐项语义。
- `consistency.test.ts` 11 例回归绿。

---

## 3. 全量回归 vs 基线（拆分计划 D-1）

```
$ npx vitest run
 Test Files  6 failed | 152 passed (158)
      Tests  7 failed | 1856 passed (1863)
FULL_EXIT=1
```

| 失败文件 | 例数 | 是否在 D-1 基线表 | 归因 |
|---|---|---|---|
| `tests/typecheck.test.ts` | 1 | 是（基线 23 条） | 存量（REQ-260922213356-4a45 遗留） |
| `tests/template-address-injection.test.ts` | 2 | 是 | 存量 |
| `tests/layer-boundary.test.ts` | 1 | 是（`diag-log.ts` import `node:fs/node:path`） | 存量 |
| `tests/client-view.test.ts` | 1 | 是 | 存量 |
| `tests/application/repository.test.ts` | 1 | 是 | 存量 |
| `tests/language-layer.test.ts` | 1 | **否** | **新增（F-1，归 T-8）** |

- 转绿（较基线净减）：`design-completeness-gate.test.ts`（基线 2 例，T-5 修绿）、`size-budget.test.ts`（基线 1 例，T-12 修绿）。
- 失败**例数** 9 → 7、**文件数** 7 → 6；但 `language-layer` 为基线表外新增 → **未满足「失败集合 ⊆ 基线且不新增失败」**（见 F-1）。

---

## 4. 类型基线（旁证，非本卡验收命令）

```
$ npx tsc --noEmit -p tsconfig.json
error TS 计数 = 24        # 基线 23（D-1）
本卡两文件（e2e-design-handoff.test.ts / migration.test.ts）命中 0 条
```

- 第 24 条 = `tests/ask-confirm-pending.test.ts(55,36): TS2322`，由 T-6 引入（T-6 复核 `t-51fc46-review.md` §3/D-A 已记录，非本卡）。
- 报错文件分布（本轮 grep 复核）：`tests/template-address-injection.test.ts` 6、`src/domain/template/render.ts` 6、`src/domain/template/resolve.ts` 5、`tests/gate-aware-questions.test.ts` 2、`tests/ask-confirm-pending.test.ts` 1、`src/gate-wiring.ts` 1、`src/application/internal/node-input-package.ts` 1、`src/application/gate/handlers/h3-inject.ts` 1、`src/adapters/CaptureHook.ts` 1。

---

## 5. 发现（本卡/本链范围外，交父卡处置）

### F-1（**新增红**，阻塞父卡验收）· `tests/language-layer.test.ts` 断言与实际提示词分片不一致

- 实测（本轮复现）：`tests/language-layer.test.ts:62`
  `AssertionError: expected '{"text":"# 设计（design）· 轻档\n\n> 2026-0…' to contain '每节必须标注服务哪条功能点'`；实际 design/light 文本为
  「覆盖 2 · 每节标注服务哪条功能点」（无「必须」）。
- 根因（已独立核实）：**T-8（FR-5）** 重写 `src/domain/prompt/fragments/design/light/overrides.md`，把旧条目
  「覆盖 1 · 每节**必须**标注服务哪条功能点」并入新「覆盖 2 · 每节标注服务哪条功能点」，字面短语消失；
  本轮 `grep -c '每节必须标注服务哪条功能点' src/domain/prompt/generated/fragments.ts` → **0**。
- 该文件（`language-layer.test.ts`）未被本需求任何卡改动（`git status` 干净，无 M 标记）。
- 归属：`t-3d59ae-review.md` §O-4、`t-6a3070-integrate.md` §O-2、`t-57bfa5-review.md` §3.5 均已登记为「归 T-8 或其复核卡对齐断言」。
- 建议：由 T-8 收口（对齐断言到新措辞，或把「必须」保留回分片并同步重生成 `generated/fragments.ts` + P1 基线）。本卡不做（`domain/prompt/**` 与 `language-layer.test.ts` 均不在 T-13 计划落点 T-1/T-3 内）。

### O-1（观察项）· `tsc` 24 条 vs 基线 23

- 多出的 1 条为 T-6 新测试 `tests/ask-confirm-pending.test.ts:55`（见 §4）；不改变测试失败集合（`typecheck.test.ts` 在基线上本就红），已在 T-6 复核记录，交父卡决定是否收尾。

### O-2（观察项）· `tests/tmp-integrate-probe.ts` 残留在包根

- `packages/web/dsh-pmboard/tmp-integrate-probe.ts`（T-8 integrate 卡的探针，未删）为未跟踪文件；不在本卡范围，未处置，报父卡。

---

## 6. 结论

1. **本卡验收（接口联调）达成**：C1–C8 **8/8 MATCH**，请求样例 / 期望响应 / 实际返回三者一致；目标命令 **3 文件 / 25 用例全绿（exit 0）**。
2. 迁移兼容边界同时守住：迁移接口对 v4 真实样本无损且不注入 `interruption`（C7）；续跑输入包对老需求逐字节不变（C8）；闸门 legacy 放行（C6）。
3. **父卡 T-13 验收的「`npx vitest run` 失败集合 ⊆ 基线且不新增失败」未达成**：唯一新增红为 `language-layer.test.ts`（F-1，归 T-8，本卡范围外）。其余 6 例均为 D-1 已登记基线红，且 `design-completeness-gate` / `size-budget` 两项基线红已转绿。
4. 本卡仅产出本文件（探针已删，未触碰任何实现/测试文件；`tmp-integrate-probe.ts` 非本卡产物，见 O-2）。
