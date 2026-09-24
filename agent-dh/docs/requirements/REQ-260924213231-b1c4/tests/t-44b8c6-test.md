# t-44b8c6 测试记录（父卡 t-954348 / T-5「分化 G2 闸门文案并统一拒绝信封」· 阶段 test）

- 测试时间：2026-09-25T00:29+0800（本轮执行内）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（FR-2；实现改动均为工作区未提交状态，本卡只读不改）：
  - **I-9 拒绝信封** `envelope(f)` + `GATE_HOW_ANCHOR` —— `packages/web/dsh-pmboard/src/application/internal/gate-feedback.ts`（新增，untracked）：拒绝消息三要素的唯一拼接入口 `<lead><what> —— <why>。补齐：<how>`
  - **G2 文案分化** `checkDesignCompletenessGate` —— `packages/web/dsh-pmboard/src/application/internal/design-gates.ts`（工作区修改 `51/17`：`art === undefined`（未登记）/ `confirmedAt === undefined`（待确认）分叉；拆分内容门与可打开性门走 envelope）
  - **6 处 GateFailure.message 收口** —— `packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts`（工作区修改 `37/24`）
  - **I-3 已确认早返回补 `gate_failure`** —— `packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`（工作区修改 `14/2`）
  - 用例侧：`tests/design-gate-messages.test.ts`（新增，untracked，171 行 / 6 例）、`tests/gate-feedback-envelope.test.ts`（新增，untracked，262 行 / 5 例）、`tests/design-completeness-gate.test.ts`（工作区修改 `6/6`，271 行 / 16 例）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts` → **3 files / 27 tests 通过，exit 0**。父卡三条业务口径（未登记含「未登记」+ `reqboard_submit(kind=design)` / 待确认含「待确认」+ `reqboard_ask_confirm` / 两串不相同）与逐 code「含 `——` 与 `补齐：`」均由用例逐条锁定并复跑通过；`design-completeness-gate.test.ts` 历史 2 红例已转绿。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令（父卡 t-954348「得到什么结果」验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts --reporter=verbose
```

实际输出（逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/gate-feedback-envelope.test.ts > envelope 拼接契约（唯一入口） > 三要素按 <what> —— <why>。补齐：<how> 拼接，lead 可前置
 ✓ tests/design-gate-messages.test.ts > TC-2/TC-3 两种病因两种话（同一 code，两串不相同） > TC-2 未登记：move 拒绝消息含「未登记」+ reqboard_submit(kind=design)，且带 why/how 信封
 ✓ tests/design-gate-messages.test.ts > TC-2/TC-3 两种病因两种话（同一 code，两串不相同） > TC-3 待确认：move 拒绝消息含「待确认」+ reqboard_ask_confirm
 ✓ tests/gate-feedback-envelope.test.ts > TC-21 逐 code 三要素（真实触发闸门，不是拼串） > I-9 的每个 code：含 —— 与 补齐：，且 how 命中可执行锚点
 ✓ tests/gate-feedback-envelope.test.ts > TC-21 负例：code 与 gaps 结构未因改文案而变化（护栏强度不降） > design_doc_incomplete.gaps 仍逐份点名，且区分未登记/待确认
 ✓ tests/gate-feedback-envelope.test.ts > TC-21 负例：code 与 gaps 结构未因改文案而变化（护栏强度不降） > requirement_uncovered.gaps 仍是结构化编号清单
 ✓ tests/gate-feedback-envelope.test.ts > TC-21 负例：code 与 gaps 结构未因改文案而变化（护栏强度不降） > assertArtifactOpenable 仍抛原名 code（形态判定未动）
 ✓ tests/design-gate-messages.test.ts > TC-2/TC-3 两种病因两种话（同一 code，两串不相同） > TC-3 待确认（闸门函数层）：checkDesignCompletenessGate 同 code 出「待确认」+ 确认命令
 ✓ tests/design-gate-messages.test.ts > TC-2/TC-3 两种病因两种话（同一 code，两串不相同） > 同一条 design_doc_incomplete，「未登记」与「待确认」两串不相同
 ✓ tests/design-gate-messages.test.ts > TC-4 ask_confirm 早返回补 G2 缺口（不再与 move 互相矛盾） > 全部落章 + 磁盘多一份未登记 → confirmed=true, advanced=false, gaps 点名未登记件
 ✓ tests/design-gate-messages.test.ts > TC-4 ask_confirm 早返回补 G2 缺口（不再与 move 互相矛盾） > 全部落章且磁盘无新增 → 早返回不带 gate_failure（不制造噪声）
 ✓ tests/design-completeness-gate.test.ts > 缺文档（use-cases.md 未交）→ 四条转移路径全拒 design_doc_incomplete > 路径① 会话 reqboard_move → 拒，消息点名 use-cases.md
 ✓ tests/design-completeness-gate.test.ts > 缺文档（use-cases.md 未交）→ 四条转移路径全拒 design_doc_incomplete > 路径② 会话弹框确认后自动推进 → 拦，gate_failure 带缺口（落章保留）
 ✓ tests/design-completeness-gate.test.ts > 缺文档（use-cases.md 未交）→ 四条转移路径全拒 design_doc_incomplete > 路径③ 看板移动端点 → 400 design_doc_incomplete
 ✓ tests/design-completeness-gate.test.ts > 缺文档（use-cases.md 未交）→ 四条转移路径全拒 design_doc_incomplete > 路径④ 看板确认后自动推进 → 拦，gate_failure 带缺口（落章保留）
 ✓ tests/design-completeness-gate.test.ts > 磁盘有但未登记 → 拒（UC-4 / FR-2：未登记 ≠ 待确认） > 四路径全拒，gaps 含未登记路径（不再与「待确认」同文案）
 ✓ tests/design-completeness-gate.test.ts > 磁盘有但未登记 → 拒（UC-4 / FR-2：未登记 ≠ 待确认） > 已登记但未确认 → assertArtifactGates 成组判定先拦（artifact_not_confirmed，gaps 列未确认路径）
 ✓ tests/design-completeness-gate.test.ts > 全交齐且全确认 → 放行 > 会话 move 放行
 ✓ tests/design-completeness-gate.test.ts > 全交齐且全确认 → 放行 > 看板 move 放行
 ✓ tests/design-completeness-gate.test.ts > 全交齐且全确认 → 放行 > 弹框确认补齐最后一份的章 → 自动推进放行
 ✓ tests/design-completeness-gate.test.ts > 全交齐且全确认 → 放行 > 看板确认补齐首份的章 → 自动推进放行
 ✓ tests/design-completeness-gate.test.ts > front-matter 策略参与①（UC-2） > sides=frontend → frontend.md 必交，缺则拒并点名
 ✓ tests/design-completeness-gate.test.ts > front-matter 策略参与①（UC-2） > sides=frontend 且交齐 frontend.md → 放行（backend.md 不要求）
 ✓ tests/design-completeness-gate.test.ts > front-matter 策略参与①（UC-2） > design_exempt 有效 → 缺 use-cases.md 也放行
 ✓ tests/design-completeness-gate.test.ts > front-matter 策略参与①（UC-2） > design_exempt 空理由 → 豁免无效，仍拒并注明
 ✓ tests/design-completeness-gate.test.ts > isLegacy 存量需求 → 全部新闸门放行（FR-6） > 无 artifacts 字段 → 会话 move 放行
 ✓ tests/design-completeness-gate.test.ts > isLegacy 存量需求 → 全部新闸门放行（FR-6） > 无 artifacts 字段 → 看板 move 放行

 Test Files  3 passed (3)
      Tests  27 passed (27)
   Start at  00:29:45
   Duration  722ms (transform 374ms, setup 973ms, tests 312ms, environment 0ms, prepare 92ms)
```

- 退出码：**0**（全绿）
- 判定：与父卡任务卡 `tasks/t-954348.md` 验收命令「`npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts` 全绿」一致；`design-completeness-gate.test.ts` 16 例含拆分计划记录的历史 2 红例，本轮**已转绿**。

## 2. 父卡业务口径逐条核对（对照用例断言与源码）

| 父卡验收口径 | 对应用例 / 源码证据 | 结果 |
|---|---|---|
| 未登记消息含「未登记」+ `reqboard_submit(kind=design)` | `design-gate-messages.test.ts` TC-2（L95-105：断言 code=`design_doc_incomplete`、含「未登记」、含 `reqboard_submit(kind=design)`、含 `——`、含 `补齐：`）；源码 `design-gates.ts:178` | ✅ |
| 待确认消息含「待确认」+ `reqboard_ask_confirm` | `design-gate-messages.test.ts` TC-3 两例（L107-125）；源码 `design-gates.ts:180` | ✅ |
| 两串不相同（同一 code 两种病因两种话） | `design-gate-messages.test.ts`「同一条 design_doc_incomplete，两串不相同」（L127-145：`not.toBe`）+ `gate-feedback-envelope.test.ts` 负例 `gaps` 逐字对比（L236-249） | ✅ |
| 逐 code 断言含 `——` 与 `补齐：` | `gate-feedback-envelope.test.ts` TC-21（L224-231：12 个 code 真实触发闸门，逐条断言 code、含 `——`、含 `补齐：`、how 命中 `GATE_HOW_ANCHOR`） | ✅ |

- 说明（口径落点）：move/看板全路径上 `assertArtifactGates` 的 `artifact_not_confirmed` 门先于 G2 完整性门拦截，故 TC-3「待确认」文案同时锁在**闸门函数层** `checkDesignCompletenessGate`（测试文件头 L11-13 已注明）；TC-2 未登记走真实 `reqboard_move(to=decomposing)` 工具路径。

## 3. 补充回归（直接消费方护栏，非父卡验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ask-confirm.test.ts tests/confirm-evidence.test.ts
```

实际输出：

```
 ✓ tests/confirm-evidence.test.ts (6 tests) 72ms
 ✓ tests/ask-confirm.test.ts (11 tests) 139ms

 Test Files  2 passed (2)
      Tests  17 passed (17)
```

- 退出码：**0**。`AskConfirm.ts`（I-3 已确认早返回补 `gate_failure`）与 `ConfirmArtifact.ts`（`REQBOARD_EVIDENCE_FAKE` 文案走 envelope）为 T-5 改动面，回归全绿 —— 文案替换未改判定、证据核验护栏（TC-18）仍生效。

## 4. 改动归属（本卡未改任何源码/用例）

```bash
git diff --numstat -- packages/web/dsh-pmboard/src/application/internal/design-gates.ts \
  packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts \
  packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts \
  packages/web/dsh-pmboard/tests/design-completeness-gate.test.ts
```

实际输出：

```
37	24	agent-dh/packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts
51	17	agent-dh/packages/web/dsh-pmboard/src/application/internal/design-gates.ts
14	2	agent-dh/packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts
6	6	agent-dh/packages/web/dsh-pmboard/tests/design-completeness-gate.test.ts
```

- 另两处用例与信封模块在 HEAD 上为 untracked（`??`）：`src/application/internal/gate-feedback.ts`、`tests/design-gate-messages.test.ts`、`tests/gate-feedback-envelope.test.ts`。
- 以上全部为**父卡 t-954348（T-5，implement 阶段）的待提交工作区改动**；本卡（test 阶段）**只读不改**，本轮新增产物仅本证据文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-44b8c6-test.md`。HEAD = `9e5ebf60`（branch `main`），与上游复核记录 t-792c94 一致。

## 5. 测试结论

1. 目标命令 `npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts`：**3 files / 27 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. 父卡三条业务口径（未登记 / 待确认分叉两串不同、逐 code `——`+`补齐：`）均由用例逐条锁定且通过；`design-completeness-gate.test.ts` 历史 2 红例转绿。
3. 补充回归 `ask-confirm` + `confirm-evidence` **17/17 绿**，改动面（AskConfirm / ConfirmArtifact 文案）无回归。
4. 本卡为 test 阶段，只执行上述命令并落本记录；未修改任何实现或测试源码。
