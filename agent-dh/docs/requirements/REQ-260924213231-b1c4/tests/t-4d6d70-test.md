# t-4d6d70 测试记录（父卡 t-5f2a65 / T-6「弹框改非阻塞投递并加回执工具」· 阶段 test）

- 测试时间：2026-09-25T00:50+0800（本轮执行内）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（FR-3 / I-3 / I-4；实现改动均为工作区未提交状态，本卡只读不改）：
  - **I-3 弹框非阻塞投递**（宽限赛跑 / 挂起 / 后台落章）—— `packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`（工作区修改 `150/270`）+ `src/application/internal/pending-confirm.ts`（新增，untracked）
  - **I-4 回执用例**（以台账为准、幂等）—— `src/application/use-cases/ConfirmReceipt.ts`（新增，untracked）+ `src/application/internal/confirm-settle.ts`（新增，untracked）+ `src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts`（新增，untracked）
  - **T-4 挂起确认注册表**（窗口绑定 / TTL）—— `src/adapters/PendingConfirmRegistry.ts`（新增，untracked）
  - **宽限配置**（可调不可关）—— `src/domain/limits.ts`（工作区修改 `9/0`）
  - **装配与工具注册**—— `src/index.ts`（工作区修改 `10/2`）、`src/tools/index.ts`（工作区修改 `1/0`）
  - 用例侧：`tests/ask-confirm-pending.test.ts`（新增，untracked，252 行 / 11 例）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts` → **2 files / 22 tests 通过，exit 0**。父卡三条业务口径（永不 resolve + 宽限 20ms → `pending=true` + ticket 非空不抛 / 作答后 `reqboard_confirm_receipt(ticket)` → `confirmed=true, advanced=true` / 台账 `confirmedAt` 已写）均由用例逐条锁定并复跑通过。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令（父卡 t-5f2a65「得到什么结果」验收命令）

> 任务卡 `tasks/t-5f2a65.md` L16：`npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts` 全绿。

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/ask-confirm.test.ts (11 tests) 149ms
 ✓ tests/ask-confirm-pending.test.ts (11 tests) 270ms

 Test Files  2 passed (2)
      Tests  22 passed (22)
   Start at  00:50:35
   Duration  802ms (transform 273ms, setup 0ms, collect 697ms, tests 420ms, environment 0ms, prepare 79ms)
```

- 退出码：**0**（全绿）
- 判定：与任务卡验收命令一致 —— 新增用例文件 11/11、既有回归文件 11/11，全部通过。

### 1.1 逐例明细（`--reporter=verbose`，22/22 通过）

```
 ✓ tests/ask-confirm-pending.test.ts > T-6 弹框非阻塞投递（FR-3 / I-3） > TC-5 超宽限：questions.ask 永不 resolve + 宽限 20ms → pending=true + ticket，不抛、不判失败
 ✓ tests/ask-confirm-pending.test.ts > T-6 弹框非阻塞投递（FR-3 / I-3） > TC-6 宽限内作答肯定项 → 旧语义逐字回归（confirmed=true, advanced=true，无 pending 键）
 ✓ tests/ask-confirm-pending.test.ts > T-6 弹框非阻塞投递（FR-3 / I-3） > 宽限内作答非肯定项 → 不落章不推进，回执带用户意见
 ✓ tests/ask-confirm-pending.test.ts > T-6 弹框非阻塞投递（FR-3 / I-3） > 未装配注册表 = 旧阻塞语义：inline_grace_ms 不生效，等作答才返回
 ✓ tests/ask-confirm-pending.test.ts > T-6 弹框非阻塞投递（FR-3 / I-3） > inline_grace_ms 非法 → REQBOARD_INVALID_INPUT（不静默回落）
 ✓ tests/ask-confirm-pending.test.ts > T-6 回执（FR-3 / I-4） > TC-7 超宽限 ticket → 作答后台落章 → reqboard_confirm_receipt 返回 confirmed=true, advanced=true
 ✓ tests/ask-confirm-pending.test.ts > T-6 回执（FR-3 / I-4） > TC-8 未知 ticket → REQBOARD_UNKNOWN_TICKET
 ✓ tests/ask-confirm-pending.test.ts > T-6 回执（FR-3 / I-4） > ticket 跨窗口不可取用（窗口绑定）→ REQBOARD_UNKNOWN_TICKET
 ✓ tests/ask-confirm-pending.test.ts > T-6 回执（FR-3 / I-4） > 挂起尚未作答 → 回执如实返回 confirmed=false（不判失败、不猜）
 ✓ tests/ask-confirm-pending.test.ts > T-6 回执（FR-3 / I-4） > 后台作答为否定项 → 回执带 user_choice 且节点未推进
 ✓ tests/ask-confirm-pending.test.ts > T-6 防重弹（回归） > TC-20 产物已确认 → 不再弹框（弹框端口 0 次），返回「已确认」
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > 肯定答复 → 落章 + 自动推进（brainstorming → design），evidence 留痕
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > 选"需要修改" → 不落章、不推进、留痕
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > userQuestions 服务缺失 → fallback=board（不死锁，提示看板通道）
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > subagent 调用（DELEGATED_CALLER）→ fallback=board 降级提示
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > 用户取消（ASK_ABORTED）→ 中性返回不报错、不推进
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > target=plan：肯定答复 → 批准计划 + 推进 design → decomposing
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > 闸门问题卡（t08）：move 被人工闸门拒绝时返回可直接喂给 ask_confirm 的问题卡
 ✓ tests/ask-confirm.test.ts > reqboard_ask_confirm > 缺产物时落章失败（kind 对不上）
 ✓ tests/ask-confirm.test.ts > T-E3: 弹框题干长度纪律（REQ-308b9a t5 / AC-7.6） > 超长题干被截到 popupQuestionMax（防选项被挤出可视区）
 ✓ tests/ask-confirm.test.ts > T-7: 确认门纪律与防重弹（REQ-260922213356-4a45 FR-9/FR-11） > 同一产物已确认 → 不再弹框（弹框端口调用 0 次）
 ✓ tests/ask-confirm.test.ts > T-7: 确认门纪律与防重弹（REQ-260922213356-4a45 FR-9/FR-11） > iron-rules 含三条确认纪律（先答后确认 / 文字确认走 evidence / 同产物不重复弹框）
```

## 2. 父卡验收口径逐条核对（对照 test-cases.md 与用例断言）

| 父卡验收口径（任务卡 L16） | 设计用例 | 对应用例 | 结果 |
|---|---|---|---|
| `questions.ask` 永不 resolve + 宽限 20ms → 返回 `pending=true` 且 ticket 非空、不抛错 | TC-5（test-cases.md:32，I-3/T-4） | `ask-confirm-pending.test.ts`「TC-5 超宽限」：断言 `success=true`、`pending=true`、`confirmed=false`、`advanced=false`、`ticket.startsWith('pc-')`、`requirement_id='REQ-abc123'`，且台账未改动（`confirmedAt` 未写、状态仍 `brainstorming`） | ✅ |
| 作答后 `reqboard_confirm_receipt(ticket)` 返回 `confirmed=true, advanced=true` | TC-7（test-cases.md:34，I-4） | `ask-confirm-pending.test.ts`「TC-7」：超宽限拿 ticket → 后台作答 → 回执工具返回 `success=true, confirmed=true, advanced=true, from='brainstorming', to='design'`，且唤醒投递 1 次、文案含 `reqboard_confirm_receipt` | ✅ |
| 台账 `confirmedAt` 已写 | TC-7（同条） | `ask-confirm-pending.test.ts`「TC-7」`waitFor(() => first().artifacts?.[0]?.confirmedAt !== undefined && first().status === 'design')`；并断言 `confirmedVia='session'` | ✅ |

- 覆盖的 FR-3 设计用例：**TC-5 / TC-6 / TC-7 / TC-8 / TC-20（5/5）**，与 test-cases.md:108 的落点表（`ask-confirm-pending.test.ts`）一致；另有 6 例为验收口径加固（非肯定项、未装配注册表回退旧阻塞语义、非法宽限、跨窗口 ticket、未作答回执如实返回、后台否定项）。

## 3. 补充：计划级 T-6 命令（含 size-budget）与全量回归

### 3.1 计划级命令（decomposition.md L115 口径）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts tests/size-budget.test.ts
```

实际输出（摘要）：

```
 ❯ tests/size-budget.test.ts (5 tests | 1 failed) 15ms
     → 超标文件（未在白名单内）：index.ts = 442 行
 ✓ tests/ask-confirm.test.ts (11 tests) 155ms
 ✓ tests/ask-confirm-pending.test.ts (11 tests) 265ms

 Test Files  1 failed | 2 passed (3)
      Tests  1 failed | 26 passed (27)
```

- 退出码：1。判定依据为计划表口径「**中 ask-confirm 两文件全绿**」：两文件 22/22 绿成立。
- `size-budget` 唯一红例 = `index.ts` 442 行 > 400，属 **T-12「组合根瘦身使尺寸门禁转绿」**范围（该卡依赖 T-9），非本卡验收项；父卡任务卡 `t-5f2a65.md` 已把该文件从验收命令中剔除。

### 3.2 全量回归（`npx vitest run`）

```
 Test Files  6 failed | 147 passed (153)
      Tests  7 failed | 1813 passed (1820)
```

失败集合（6 文件 / 7 例，**逐条命中拆分计划记录的基线缺口**）：

| 失败文件 | 例数 | 是否本需求范围 |
|---|---|---|
| `tests/client-view.test.ts` | 1 | 否（基线） |
| `tests/template-address-injection.test.ts` | 2 | 否（基线） |
| `tests/layer-boundary.test.ts` | 1 | 否（基线） |
| `tests/application/repository.test.ts` | 1 | 否（基线） |
| `tests/size-budget.test.ts` | 1 | 是 → T-12（未完成） |
| `tests/typecheck.test.ts` | 1 | 部分（见 §4） |

- 基线（拆分计划 L180-183：`7 failed | 140 passed (147)` / `9 failed | 1761 passed (1770)`）→ 本轮 `6 failed / 7 failed`：**文件数 -1、失败例数 -2**，差额恰为 `tests/design-completeness-gate.test.ts` 的历史 2 红例（T-5 已修绿）。
- 结论：**失败集合 ⊆ 基线，未新增失败文件**。
- 说明：本卡为 T-6 的 test 阶段，按链尾放行口径跑全量以确认「不新增失败」；T-13 的 E2E 复跑不在本卡。

## 4. 残留观察（非本卡范围，已在复核卡登记）

1. **新增 1 条类型错误**：`npx tsc --noEmit -p tsconfig.json` 报 **24 条**（基线 23，`typecheck.test.ts` 在基线上本就红）。第 24 条为本需求引入：
   `tests/ask-confirm-pending.test.ts(55,36): error TS2322`（`deliver` 返回 `unknown` 不满足 `AgentDeliveryPort.deliver → DeliveryResult`）。
   该条已由复核记录 `evidence/t-51fc46-review.md`（R17 / D-A）逐条登记，结论为「不影响运行、不新增失败文件，**建议收尾前一行修复（非阻塞）**」。
   本卡为 test 阶段，按本需求 test 卡统一纪律（见 §5）**只读不改**，故未修改该测试源码；修复落在收尾环节。
2. `src/index.ts` 442 行 → `size-budget` 红，属 T-12；T-12 完成后该命令可全绿。

## 5. 改动归属（本卡未改任何源码/用例）

```bash
git diff --numstat -- src/domain/limits.ts src/application/use-cases/AskConfirm.ts src/index.ts src/tools/index.ts
git status --short -- src/adapters/PendingConfirmRegistry.ts src/application/use-cases/ConfirmReceipt.ts src/application/internal/confirm-settle.ts src/application/internal/pending-confirm.ts src/tools/ConfirmReceiptTool tests/ask-confirm-pending.test.ts
```

实际输出：

```
150	270	agent-dh/packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts
9	0	agent-dh/packages/web/dsh-pmboard/src/domain/limits.ts
10	2	agent-dh/packages/web/dsh-pmboard/src/index.ts
1	0	agent-dh/packages/web/dsh-pmboard/src/tools/index.ts
--- untracked ---
?? src/adapters/PendingConfirmRegistry.ts
?? src/application/internal/confirm-settle.ts
?? src/application/internal/pending-confirm.ts
?? src/application/use-cases/ConfirmReceipt.ts
?? src/tools/ConfirmReceiptTool/
?? tests/ask-confirm-pending.test.ts
```

- 以上全部为**父卡 t-5f2a65（T-6，implement 阶段）的待提交工作区改动**；本卡（test 阶段）**只读不改**，本轮新增产物仅本证据文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-4d6d70-test.md`。HEAD = `9e5ebf60`（branch `main`），与上游联调记录 t-74ab2d、复核记录 t-51fc46 一致。

## 6. 测试结论

1. 目标命令 `npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts`：**2 files / 22 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. 父卡三条业务口径（永不 resolve+宽限 20ms → pending+ticket 不抛 / 回执 confirmed+advanced / 台账 confirmedAt 已写）均由用例逐条锁定且通过；FR-3 的 5 个设计用例（TC-5/6/7/8/20）5/5 覆盖。
3. 全量回归「失败集合 ⊆ 基线」，`design-completeness-gate` 历史 2 红例已转绿，未新增失败文件；`size-budget` 红为 T-12 范围。
4. 残留 1 条新增类型错误已在复核卡（t-51fc46 R17/D-A）登记并建议收尾前一行修复；本卡按 test 阶段纪律只读不改。
5. 本卡为 test 阶段，只执行上述命令并落本记录；**未修改任何实现、适配器或测试源码**，本轮新增产物仅本文件。
