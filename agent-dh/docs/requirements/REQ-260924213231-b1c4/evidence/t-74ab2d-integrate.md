# t-74ab2d 联调记录（父卡 t-5f2a65 / T-6「弹框改非阻塞投递并加回执工具」· 阶段 integrate）

- 联调时间：2026-09-25T00:41+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（运行 banner 为准，darwin-arm64）· 测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 联调对象（接口）：
  - **I-3 弹框非阻塞投递**：`reqboard_ask_confirm`（`src/application/use-cases/AskConfirm.ts` → `src/application/internal/pending-confirm.ts`，宽限赛跑/挂起/后台落章）
  - **I-4 挂起确认回执**：`reqboard_confirm_receipt(ticket)`（`src/application/use-cases/ConfirmReceipt.ts` + `src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts`），注册表 `src/adapters/PendingConfirmRegistry.ts`，组合根装配 `src/index.ts`（含 `PendingConfirmRegistry` 装配）
- 结论：**接口联调通过** —— 7 例「请求样例 → 期望响应 → 实际返回」三方一致（7/7 MATCH）；父卡验收两文件 **22/22 绿**；接口层回归（schema/契约/分发/装配）**31/31 绿**。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-t74ab2d.test.ts`（跑完即删），对 I-3/I-4 各发真实工具调用（真 `defineAskConfirmTool` / `defineConfirmReceiptTool` + 真 `PendingConfirmRegistry` + 真 `JsonLedgerRepository`，仅 `questions.ask` 与 `clock` 按卡面注入），逐字段打印并比较「请求样例 / 期望响应 / 实际返回」。断言口径：期望键逐键 `JSON.stringify` 相等、未声明的多键判 MISMATCH（`<string>`/`<pc>`/`<contains:…>` 为通配）。台账 seed：`REQ-abc123`（brainstorming，已登记产物 `requirement`），窗口 `session-t74ab2d`。

### C1 — I-3 超宽限挂起（不判失败）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_ask_confirm","args":{"target":"artifact","kind":"requirement","question":"需求文档已完成，是否确认进入设计？","inline_grace_ms":20},"windowKey":"session-t74ab2d"}`；前置：`questions.ask` 返回**永不 resolve** 的 promise |
| 期望响应 | `{"success":true,"confirmed":false,"advanced":false,"pending":true,"ticket":"pc-…","requirement_id":"REQ-abc123","note":"<非空字符串>"}` |
| 实际返回 | `{"success":true,"confirmed":false,"advanced":false,"pending":true,"ticket":"pc-b16b70","requirement_id":"REQ-abc123","note":"弹框已投递，超宽限仍未作答：已登记挂起确认（不判失败）。人作答后会后台自动落章/推进；请稍后调 reqboard_confirm_receipt(ticket=\"pc-b16b70\") 取回执，或调 reqboard_status 读确认态"}` |
| 判定 | **一致（MATCH）** |

### C2 — I-3 宽限内作答 = 旧阻塞语义逐字一致（兼容性矩阵）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_ask_confirm","args":{"target":"artifact","kind":"requirement","question":"需求文档已完成，是否确认进入设计？"},"windowKey":"session-t74ab2d"}`；前置：`questions.ask` 立即作答肯定项 |
| 期望响应 | `{"success":true,"confirmed":true,"advanced":true,"from":"brainstorming","to":"design","requirement_id":"REQ-abc123","note":"<非空字符串>"}`（**且无 `pending` / `ticket` 键**） |
| 实际返回 | `{"success":true,"confirmed":true,"advanced":true,"from":"brainstorming","to":"design","requirement_id":"REQ-abc123","note":"已落章（via=session），已推进：brainstorming → design"}`；`out.pending`/`out.ticket` 均 `undefined` |
| 判定 | **一致（MATCH）** |

### C3 — I-4 后台落章后取回执（以台账为准）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_confirm_receipt","args":{"ticket":"pc-b16b70"},"windowKey":"session-t74ab2d"}`；前置（接 C1）：人作答肯定项 → 等后台落章（`confirmedAt` 已写且状态 `design`） |
| 期望响应 | `{"success":true,"confirmed":true,"advanced":true,"from":"brainstorming","to":"design","requirement_id":"REQ-abc123","note":"回执：已确认并推进 brainstorming → design（以台账为准）"}` |
| 实际返回 | 与期望**逐字相同** |
| 台账事实 | `confirmedAt=1790268098849`、`confirmedVia=session`、`status=design` |
| 唤醒投递 | 1 次，首条 `"session-t74ab2d:用户已在确认弹框作答（ticket pc-b16b70）：已落章并推进。请调 reqboard_confirm_receipt(ticket=\"pc-b16b70\") 取回执"` |
| 判定 | **一致（MATCH）** |

### C4 — I-4 未知 ticket 拒绝（E-5）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_confirm_receipt","args":{"ticket":"pc-无"},"windowKey":"session-t74ab2d"}` |
| 期望响应 | 抛错 `{"code":"REQBOARD_UNKNOWN_TICKET","message":"<含「reqboard_status 读 design_docs[].confirmed」>"}` |
| 实际返回 | `{"code":"REQBOARD_UNKNOWN_TICKET","message":"reqboard_confirm_receipt 未执行：ticket pc-无 未知或已过期（不属于本窗口或超出有效期）——回执事务已不可查，改调 reqboard_status 读 design_docs[].confirmed（以台账为准）（REQBOARD_UNKNOWN_TICKET）"}` |
| 判定 | **一致（MATCH）** |

### C5 — I-4 挂起未作答 → 如实返回 confirmed=false（不判失败、不猜）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"tool":"reqboard_confirm_receipt","args":{"ticket":"pc-c8ecdd"},"windowKey":"session-t74ab2d"}`；前置（接 C1 同型挂起）：`questions.ask` 永不 resolve、后台尚未作答 |
| 期望响应 | `{"success":true,"confirmed":false,"advanced":false,"from":"brainstorming","to":"brainstorming","requirement_id":"REQ-abc123","note":"回执：挂起确认尚未作答——人作答后后台自动落章/推进；也可请用户走看板确认"}` |
| 实际返回 | 与期望**逐字相同** |
| 判定 | **一致（MATCH）** |

### C6a — I-4 工具壳契约（名称 / 必填入参 / 响应键）

| 项 | 内容 |
|---|---|
| 请求样例 | `defineConfirmReceiptTool(deps)`（构造即校验 schema 与工具名） |
| 期望响应 | `{"name":"reqboard_confirm_receipt","paramRequired":["ticket"],"ticketType":"string","schemaKeys":["success","confirmed","advanced","from","to","requirement_id","user_choice","user_feedback","note"]}` |
| 实际返回 | 与期望逐字段相同（`defineTool` 把属性上的 `required:true` 归一为对象级 `required:["ticket"]`） |
| 判定 | **一致（MATCH）** |

### C6b — 组合根装配（`src/index.ts`）

| 项 | 内容 |
|---|---|
| 请求样例 | 扫 `src/index.ts` 源码 |
| 期望响应 | `{"imported":true,"registered":true,"pendingRegistryAssembled":true}`（导入 `defineConfirmReceiptTool`、`toolsCtx.tools.register(defineConfirmReceiptTool(useCaseDeps))`、`pendingConfirms` 装配并注入 `useCaseDeps`） |
| 实际返回 | 与期望一致 |
| 判定 | **一致（MATCH）** |

探针执行结果（`--reporter=verbose`，逐例 `VERDICT MATCH`）：

```
 ✓ tests/__probe-t74ab2d.test.ts > t-74ab2d 联调探针：I-3 弹框非阻塞 + I-4 回执 > C1/C3 I-3 超宽限挂起 → I-4 后台落章后取回执
 ✓ tests/__probe-t74ab2d.test.ts > t-74ab2d 联调探针：I-3 弹框非阻塞 + I-4 回执 > C2 I-3 宽限内作答 = 旧阻塞语义逐字一致
 ✓ tests/__probe-t74ab2d.test.ts > t-74ab2d 联调探针：I-3 弹框非阻塞 + I-4 回执 > C4 I-4 未知 ticket → REQBOARD_UNKNOWN_TICKET
 ✓ tests/__probe-t74ab2d.test.ts > t-74ab2d 联调探针：I-3 弹框非阻塞 + I-4 回执 > C5 I-4 挂起未作答 → confirmed=false（不判失败、不猜）
 ✓ tests/__probe-t74ab2d.test.ts > t-74ab2d 联调探针：I-3 弹框非阻塞 + I-4 回执 > C6 I-4 工具契约（名称/必填入参）+ index.ts 装配
 ✓ tests/__probe-t74ab2d.test.ts > t-74ab2d 联调探针：I-3 弹框非阻塞 + I-4 回执 > 汇总
   → 汇总 7 例：MATCH 7 / MISMATCH 0

 Test Files  1 passed (1)
      Tests  6 passed (6)
```

首次运行时 C6a 报 MISMATCH，定位为**探针期望值写法错**（把属性级 `ticket.required===true` 当期望，实际 `defineTool` 已归一为对象级 `parameters.required===["ticket"]`），**非实现缺陷**：改用归一后形状断言即 7/7 MATCH。据此确认 I-4 工具壳的入参必填与响应键集合与 `design/interfaces.md` I-4 字段明细一致。

---

## 2. 目标命令与输出摘要

### 2.1 父卡验收命令（t-5f2a65 acceptance）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/ask-confirm.test.ts (11 tests) 153ms
 ✓ tests/ask-confirm-pending.test.ts (11 tests) 280ms

 Test Files  2 passed (2)
      Tests  22 passed (22)
```

- 期望：两文件全绿（TC-5/TC-6/TC-7/TC-8/TC-20 覆盖 FR-3）
- 实际：22/22 通过，退出码 0 —— 与期望一致

### 2.2 接口层回归（schema / 契约 / 分发 / 装配）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/tools-schema.test.ts tests/output-contract.test.ts tests/tools-dispatch.test.ts tests/apply-wiring.test.ts
```

实际输出：

```
 Test Files  4 passed (4)
      Tests  31 passed (31)
```

- 期望：新工具 schema 合法（`additionalProperties` 铁律）、响应键对上契约扫描、分发与组合根装配不回归
- 实际：31/31 通过，退出码 0 —— 与期望一致

### 2.3 size-budget（如实记录：红，但非本卡目标、且无新增超标文件）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/size-budget.test.ts
```

实际输出：

```
 ❯ tests/size-budget.test.ts (5 tests | 1 failed)
   × src 下所有 .ts 单文件 ≤ 400 行（白名单见 WHITELIST，逐条带理由）
     → 超标文件（未在白名单内）：
index.ts = 442 行

 Test Files  1 failed (1)
      Tests  1 failed | 4 passed (5)
```

说明（**属基线缺口，不新增**）：
- `index.ts` 在 **HEAD 已是 433 行**（`git show HEAD:packages/web/dsh-pmboard/src/index.ts | wc -l` = 433），本卡 T-6 的接线（导入 + 注册 + `pendingConfirms` 装配）使其到 442 行；**该文件在改动前后都超限**，为分解计划已登记的基线缺口。
- 分解计划明定由 **T-12「组合根瘦身使尺寸门禁转绿」** 修绿（`decomposition.md` L92/L121/L188；T-6 验收行只要求「ask-confirm 两文件全绿」，L115），故本卡**不做** `index.ts` 拆分子（越界）。
- 白名单外**无新增**超标文件：`filter` 结果只有 `index.ts = 442` 一项，T-6 新增的 `PendingConfirmRegistry.ts`（88 行）、`ConfirmReceipt.ts`（122 行）、`pending-confirm.ts`（128 行）、`ConfirmReceiptTool.ts`（49 行）均远低于 400。

---

## 3. 联调结论

1. 接口 I-3（`reqboard_ask_confirm` 宽限赛跑/超宽限挂起）与 I-4（`reqboard_confirm_receipt(ticket)`）的**请求样例 → 期望响应 → 实际返回**三方一致，**7/7 例 MATCH**（含否定路径 C4 与未作答 C5）。
2. 非阻塞不判失败：超宽限返回 `success=true, pending=true, ticket=pc-…`，且台账未被改动（未落章）；作答后后台自动落章/推进并**唤醒窗口一次**（投递文案含取回执命令），回执以台账 `confirmedAt` 为准（`confirmed=true, advanced=true, brainstorming → design`）。
3. 兼容性矩阵成立：**宽限内作答 = 旧阻塞语义**（返回体无 `pending`/`ticket`，字段与改造前一致）；未装配 `pendingConfirms` 时退回旧阻塞路径（`ask-confirm-pending.test.ts`「未装配注册表」例）。
4. 拒绝护栏不降级：未知/跨窗口/过期 ticket 一律 `REQBOARD_UNKNOWN_TICKET`，文案引导改读 `reqboard_status.design_docs[].confirmed`（**不猜、不伪造**）。
5. 组合根装配到位：`src/index.ts` 导入并 `register(defineConfirmReceiptTool(useCaseDeps))`，`PendingConfirmRegistry` 注入 `useCaseDeps.pendingConfirms`；工具 schema 合法（`tools-schema` 绿）。
6. 目标命令 `npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts` **22/22 绿**；接口层回归 31/31 绿。`size-budget` 仍红且**仅**因基线 `index.ts`（433 → 442），由 T-12 修绿，非本卡范围、无新增超标文件。
7. 本卡为 integrate 阶段，只执行上述命令与临时探针并落本记录；**未修改任何实现或测试源码**。临时探针 `tests/__probe-t74ab2d.test.ts` 与一次性 dump 探针 `tests/__dump-t74ab2d.test.ts` 已在本轮内删除（`rm -f`，复核 `No such file or directory`）。本轮新增产物仅本文件。
