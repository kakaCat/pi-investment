---
req_id: "REQ-260924002956-f37c"
title: "立项拒绝路径应终端化：拒绝即收尾，不追问、不发闸门未通过"
status: brainstorming
owner: "session-4799e386"
category: bug
---

# 需求说明（REQ-260924002956-f37c）

> 状态：需求分析（brainstorming） · 窗口 session-4799e386 · 立据：2026-09-24
> 宣布路径：Bounded（缺陷修复，改动面 = dsh-pmboard 包内 3 个文件；不新增能力、不动协议）

## 背景与动机

用户在 2026-09-24 00:25 前后的两个回合里连续踩到同一条路径，原话：

> 「立项弹框出现了，我选不立项，弹框继续让我选类型。我选不立项应该直接关闭弹框继续完成对话」

> 「【闸门待改进】G0 未通过，节点仍在 brainstorming。选择「✖️ 不需要立项」」（这是系统投递给窗口的原文）

**问题**：立项弹框的「✖️ 不需要立项」被当成"第 1 问的一个选项"，而不是"本次弹框的终止信号"。后果有两层：

1. **弹框层**：用户以为已取消，弹框还在追问类型/难度/文档位置；
2. **链路层**：拒绝之后系统又发一条「闸门待改进 / 未通过 / 节点仍在 brainstorming」——把一个**被用户正确拒绝**的框报成"闸门失败"，还邀请 agent 去"改进"它；而且 G0 从未创建过任何节点，那句"节点仍在 brainstorming"是不存在的现状。

对一个"不想立项"的人来说，这条路径本该**一步收尾**，实际却要多点三下 + 收一条误导性告警。

## 目标

| 编号 | 目标 | 价值（解决什么问题/对谁的价值） | 衡量指标 | 目标值 |
|---|---|---|---|---|
| G1 | 拒绝即终止弹框 | 用户选「不需要立项」后不再被追问后续问题 | 该路径下 `questions.ask` 调用次数 | 1（现状为 1 次四问，UI 继续追问） |
| G2 | 拒绝不产生任何下游动作 | 不再投递「闸门未通过/待改进」，不再登记 G0 | 该路径下 G0 入队次数 / 未通过投递条数 | 0 / 0 |
| G3 | 肯定路径行为不变 | 正常立项不被这次改动影响 | 既有 capture/gate 测试 | 全绿，四问一次问完 + 同调用内建单 |

## 非目标

- N1 **不改 DSH 框架**：`dsh-user-questions` 的 `intent` 只支持 `plan-review`，没有"选项即终止"语义；本次在调用方（pmboard）实现短路，不动宿主协议。
- N2 **不改工具 schema**：`reqboard_capture` 的入参/出参契约不变（`CaptureTool.ts` 是薄壳，判定在用例/领域）。
- N3 **不动拒绝粘滞（FR-5）**：30 分钟同窗口不再弹框的既有机制保持原样。
- N4 **不顺手修无关缺陷**：本次仅记录一条观察（见「边界」最后一条），不在本单修。

## 边界（不做什么）

- 不把"拒绝"做成宿主层的通用能力（不引入新的 `intent`、不改 UI 组件）——那影响所有弹框，超出本单。
- 不改变肯定分支的四问内容与默认值（`docs/requirements/<REQ>/` 等默认一律不动）。
- 不覆盖"弹框被取消/超时"（`ask()` 抛错）的既有语义：仍返回未立项，不写拒绝留痕。
- **越界观察（登记不修）**：`MoveRequirement.ts:56` 用的是全局 `ARTIFACT_CONFIRM_GATES`，没有走 `confirmGateKindFor(category, from, to)`，因此 `CATEGORY_FLOW_PROFILES.bug` 声明的"免需求分析门 / confirmGates 只含 design>decomposing 等"在推进时**不生效**——本单立项时就撞上（bug 类型仍被 brainstorming→design 的 requirement 产物门拦住）。属"档案声明与执行不一致"，另单处理。

## 验收标准

- [ ] AC1（G1）：新增单测——第一段作答为「✖️ 不需要立项」时，`questions.ask` 只被调用 1 次，且第二段问题（类型/难度/文档位置）从未下发。
- [ ] AC2（G2）：同一场景下，`GatePostChainPort.enqueue` 调用次数为 0；无任何 `deliver` 投递（"闸门待改进"消息不存在）。
- [ ] AC3（G2）：拒绝路径返回值仍为 `success:false` / `requirement_id:''`，且 `state/capture-rejections.json` 新增一条本窗口记录（FR-5 粘滞保留）。
- [ ] AC4（G3）：肯定路径回归——四问一次问完（两段合计 4 问）、G0 恰好入队 1 次、需求创建并推进到 brainstorming，既有断言不变。
- [ ] AC5（防御）：无 `from` 的闸门（G0）在负分支不再输出"节点仍在 {状态}"文案——单测断言消息不含 `节点仍在`。
- [ ] AC6（回归）：`npx vitest run packages/web/dsh-pmboard` 全量绿。
- [ ] AC7（真机）：改后重启实例，实际走一次"选不立项"路径，弹框立即关闭、无后续追问、无"闸门待改进"投递。

## 改动位置

链路（缺陷环节用【】标出）：

`用户消息 → hook 登记 pending → 注入立项提示 → reqboard_capture → 【四问一次 ask：拒绝只是第 1 问的选项】 → 【答案全部回收后才判 rejected】 → 【GateAwareQuestions 有作答即登记 G0】 → 【H1 找不到需求→negative】 → 【H4 发"闸门未通过，节点仍在 brainstorming"】`

| 环节 | 本次是否改动 | 说明 |
|---|---|---|
| 上游：hook 登记 / 提示注入 | 否 | 行为不变 |
| 【弹框题目组装】`application/internal/capture-mapping.ts` | 是 | 拆成「立项意愿+名称」与「类型/难度/文档位置」两段 |
| 【用例编排】`application/use-cases/CaptureRequirement.ts` | 是 | 第一段命中拒绝 → 写留痕 + 立即返回，不发起第二段；G0 登记挪到第二段 |
| 【闸门后置链 H4】`application/gate/handlers/h4-resume.ts` | 是 | 无 `from` 的门不再编"节点仍在 X" |
| 下游：创建/推进/留痕 | 否 | 肯定分支语义不变 |

## 改动对比

| 项 | 修复前（缺陷行为） | 修复后（预期行为） | 说明 |
|---|---|---|---|
| 拒绝后弹框 | 继续追问类型/难度/文档位置 | 立即收框，不再追问 | 第二段根本不发起 |
| 拒绝后链路 | 登记 G0 → H1 negative → H4 投递「闸门待改进…节点仍在 brainstorming」 | 不登记 G0、不投递 | 拒绝不是"闸门失败" |
| 拒绝回执 | 带 `defaults_used: [category, difficulty, doc_location]`（未答的三问被当作走了默认） | 只反映真实作答 | 去噪，避免误读 |
| 肯定路径 | 四问一次问完 + 建单 | 不变（两段合计仍是四问） | 防"修反" |

## 复现步骤

环境：本机 DSH 实例 :13080（profile agent-dh），窗口 session-4799e386，2026-09-24 00:20 前后。

- **BUG-1（弹框不终止）**：在未绑定需求的窗口触发立项弹框 → 第 1 问选「✖️ 不需要立项」→ 预期弹框关闭并结束；实际弹框继续显示「需求类型」，需再答 2–3 问。
- **BUG-2（假告警）**：拒绝后等回合结束 → 预期无任何后续消息；实际窗口收到投递：`【闸门待改进】G0 未通过，节点仍在 brainstorming。\n选择「✖️ 不需要立项」`。

**证据附件**：

- `state/capture-rejections.json`（2026-09-24 00:25:55 CST，`at=1790180755608`，windowKey=session-4799e386-…）：证明拒绝确实发生且已留痕；
- 同次工具回执：`success:false`、`requirement_id:''`、`defaults_used:[category,difficulty,doc_location]`——证明未答的三问被当成"默认"回收（四问被一次性下发）；
- BUG-2 的原文投递（用户转述，见「背景与动机」第二段引文）；
- `state/reqboard-capture-diag.log` 中本窗口 NODE-4/NODE-5 连续 `DYNAMIC PROMPT`：证明注入按设计发生、缺陷不在触发端。

## 根因

1. **拒绝不是请求级语义，只是第 1 问的一个选项 label**：`application/internal/capture-mapping.ts:77-89`（`✖️ 不需要立项` 作为 `name` 问的 option），四问在 `:91-127` 一次性下发；宿主无"选此项终止"语义，UI 只能一路问完。
2. **rejected 判定发生在答案全部回收之后**：`application/use-cases/CaptureRequirement.ts:129-158` —— 弹框问完才轮到 `mapCaptureAnswers` 发现 `rejected=true`，已有心无力。
3. **拒绝被当作"闸门作答"登记**：`adapters/GateAwareQuestions.ts:52-68` 只要 `answers.length > 0` 就 `enqueue` G0，不区分肯定/拒绝。
4. **链上把"没需求"判成 negative 并发未通过文案**：`application/gate/handlers/h1-advance.ts:30-40`（找不到需求 → `verdict=negative`、`skip: no_requirement`）→ `application/gate/handlers/h4-resume.ts:40-42` 输出「未通过，节点仍在 {from ?? to}」；而 G0 在 `domain/gate/GateCatalog.ts:22-28` **没有 `from`**，于是回落到 `to='brainstorming'`，印出一个从未存在的节点状态。

## 回归

将来怎么证明修好了（必须覆盖上述两条复现路径，禁止顺手重构）：

- `packages/web/dsh-pmboard/tests/capture-tool.test.ts`：拒绝路径只发 1 段 ask、返回值与留痕不变；
- `packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts`：拒绝路径 G0 入队 0 次（肯定路径仍 1 次）；
- `packages/web/dsh-pmboard/tests/gate-handlers.test.ts`：无 `from` 闸门负分支不输出"节点仍在"；
- 真机：重启后走一次拒绝路径（AC7）。

## 修订记录

| 日期 | 修改内容 | 修改人 |
|---|---|---|
| 2026-09-24 | 初稿（用户两次现场反馈 + 代码级根因定位） | session-4799e386 |

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| BUG-1 | 🔴 **未被接收** | — |
| BUG-2 | 🔴 **未被接收** | — |

> 🔴 **未被接收（2 条）**：BUG-1、BUG-2

<!-- reqboard:marks:end -->
