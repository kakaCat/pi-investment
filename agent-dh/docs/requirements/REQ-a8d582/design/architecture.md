# REQ-a8d582 设计·架构与改动面

> requirement_refs: FR-1, FR-2, FR-3, FR-4
> 上游：[requirement.md](../requirement.md) · 同批：[interfaces.md](./interfaces.md)、[data-model.md](./data-model.md)、[test-cases.md](./test-cases.md)

## 1. 改动总览 serves: FR-1, FR-2, FR-3, FR-4

| 面 | 文件 | 改动 |
|---|---|---|
| 客户端·操作条 | `src/client/views/stage-detail.ts` | accepting 分支去掉"未交材料只给提示"，按钮只看阶段 |
| 客户端·交互 | `src/client/board-mount.ts` | `case 'verify-pass'` 加确认弹框 + 覆盖说明装配 |
| 客户端·契约 | `src/client/api.ts`、`src/client/types.ts` | `verifyPass` 增可选 `confirm_override`；verification 增可选 `override` |
| 服务端·裁决 | `src/http/routers/verdicts.ts`、`src/application/internal/verdicts.ts`、`src/application/use-cases/AcceptSheet.ts` | 裁决只记录，不再自动打回 |
| 服务端·返工 | `src/http/routers/verdicts.ts` | 返工任务改由"退回返工"动作生成 |
| 服务端·通过 | `src/http/routers/verdicts.ts` | pass 的覆盖语义（含有不合格项与无材料两种情形）+ 落痕 |
| 数据契约 | `src/shared/protocol.ts` | `VerificationRecord.override`（可选） |

## 2. 客户端：按钮显示条件与二次确认 serves: FR-1, FR-3

**显示条件（FR-3）**：`renderActionBar` 里 `if (req.status === 'accepting' && req.verification !== undefined)` 改为只判 `req.status === 'accepting'`；`case 'accepting'` 中"未提交验收材料…"的 hint 分支整体删除（该文案把"验收阶段"错写成"已交材料"，FR-3 明确要求移除）。

**确认弹框（FR-1）**：`case 'verify-pass'` 在发请求前做一次本地装配 + `window.confirm`：

1. 取当前需求：`state.requirements.find(r => r.id === reqId)`；
2. 统计 `verification?.sheet?.items` 的 passed/failed/pending；
3. 文案分三种：
   - 无 `verification`：`尚未提交验收材料（本次通过没有验收证据）。确认后直接归档，是否继续？`
   - 有 sheet 且 failed + pending = 0：`验收单 v{n}：{p} 项全部通过。验收通过即归档，是否继续？`
   - 有 failed 或 pending：`验收单 v{n}：通过 {p} / 不通过 {f} / 未裁决 {u}。{前 3 条不通过项摘要}。确认后按「覆盖通过」归档，是否继续？`
4. `window.confirm` 返回 false → 直接 return（不发任何请求）；返回 true → `api.verifyPass({ id, confirm_override: <装配出的说明> })`。

**为什么覆盖原因不让用户手填**：用户要的是"有不合格是否通过"的是/否确认；加输入框会把它变成写作文（同文件 `window.prompt` 只用于必须留意见的退回路径）。覆盖原因由计数与条目摘要自动装配，保证可审计、可复现。

## 3. 服务端：裁决只记录，返工由「退回返工」触发 serves: FR-2

**现状**：`/req/verdicts` 只要本批出现 `failed` 就立刻 `assertReqTransition(accepting → implementing)` 并批量建返工任务（verdicts.ts:130-167）；agent 弹框通道 `reqboard_accept_sheet` 走 `application/internal/verdicts.ts` 也是同一套自动打回。

**改为**：

- 裁决（`/req/verdicts` 与 `applyVerdicts`）**只写验收单、不改需求状态、不建任务**；返回 `note` 指引"有 N 项不通过，需求仍在验收态：由人点「退回返工」或「验收通过」"。
- 返工任务改为在**退回返工**动作里生成：`handleVerifyDecision(pass=false)` 按当前 sheet 的 `failed` 项批量建卡（沿用现有卡规格：title=`返工：{原标题/判据}`、`implementation` 带验收意见、`acceptance`=判据、scope/phase/side 承接原任务），再置 `implementing`。
- **幂等**：退回返工会把状态改成 `implementing`，按钮随之消失，同一版验收单不会被退回两次；为防直连接口重复调用，建卡前先判"仍在验收态"。

**已知行为变更（验收时要确认）**：agent 弹框通道 `reqboard_accept_sheet` 在有未过项时**不再自动打回**，只返回指引；后续动作交给人（看板按钮）。这是 FR-2 的直接后果，收益是两条通道语义单点、不再各自决定状态。

## 4. 服务端：pass 的覆盖语义 serves: FR-1, FR-4

`handleVerifyDecision(pass=true)` 现在只做三件事（状态 / 材料存在 / 产物已登记）。改为：

1. 取 sheet，统计 `failed` / `pending`；记录"是否有材料"；
2. **统一前置**：当 `failed + pending > 0` **或** 无 `verification` 时，要求请求体带非空 `confirm_override`；缺失 → 结构化错误，文案含计数与"缺少验收证据"字样；
3. 带覆盖时：跳过 `missing_artifact` 的 verification 产物检查（无材料时本就不可能有该产物），写入覆盖记录（见 data-model.md），状态照常 `accepting → archived`；
4. 无不合格且材料齐全时：行为与现状完全一致（不要求新参数）。

## 5. 分层与不变量 serves: FR-2, FR-4

- **状态字面量只在 domain 判定**：改状态的两处仍走 `domain/status/Predicates` 与既有转移断言，路由层不新增字面量比较（layer-boundary 门禁会拦）。
- **规则单点**：两条通道（看板 HTTP / agent 弹框）的"裁决不改状态"落在同一处（`application/internal/verdicts.ts`），不在路由里各写一份。
- **人工门不变量**：`accepting → archived` 与 `accepting → implementing` 仍只在人的动作里发生，agent 工具不得代办。
- **无新增弹框组件**：客户端沿用 `window.confirm`，不引入新依赖、不动构建链。

## 6. 风险与边界 serves: FR-2, FR-4

- 覆盖式通过会削弱"验收必须有证据"，兜底 = 弹框警示 + 必填覆盖原因 + 双处留痕。
- 取消自动打回后不合格项可能长期挂在验收态：看板对"验收态且验收单有 failed"加显式标记（本设计只要求标记可见）。
- 若日后需要"自动打回"回归，应作为新需求引入，不在本次偷偷加回。
