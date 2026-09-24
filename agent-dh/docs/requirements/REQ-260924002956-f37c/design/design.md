---
req_id: "REQ-260924002956-f37c"
title: "立项拒绝路径应终端化：拒绝即收尾，不追问、不发闸门未通过"
category: bug
requirement_refs: "BUG-1, BUG-2"
---

# 设计（REQ-260924002956-f37c）· 立项拒绝路径终端化

> 类型：bug ｜ 窗口 session-4799e386 ｜ 读者：执行 agent ｜ 语言：技术为主
> 一句话：把「✖️ 不需要立项」从"第 1 问的一个选项"提升为**请求级终止信号**——拒绝即收框、即返回、不登记闸门；顺带堵掉 H4 对无 `from` 闸门编造现状的分支。

## 复现与证据 serves: BUG-1, BUG-2

**最小重现（BUG-1）**：unbound 窗口 → 触发 `reqboard_capture` → 第 1 问选「✖️ 不需要立项」→ 观测 `questions.ask` 之后的 UI：继续出示「需求类型」。

**最小重现（BUG-2）**：同上拒绝后等 `turn/end` → 观测投递：`【闸门待改进】G0 未通过，节点仍在 brainstorming。\n选择「✖️ 不需要立项」`。

**证据（可复核）**：

| 证据 | 位置/内容 | 说明 |
|---|---|---|
| 拒绝回执 | `success:false`、`requirement_id:''`、`defaults_used:[category,difficulty,doc_location]` | 未答的三问被当"默认"回收 ⇒ 四问被一次性下发（BUG-1） |
| 拒绝留痕 | `<dshHome>/state/capture-rejections.json`，`at=1790180755608`（2026-09-24 00:25:55 CST，windowKey=session-4799e386-…） | 证明拒绝已发生且留痕（FR-5 保留） |
| 注入留痕 | `<dshHome>/state/reqboard-capture-diag.log` 本窗口 NODE-4/NODE-5 连续 `DYNAMIC PROMPT` | 触发端按设计工作，缺陷不在 hook |
| 告警原文 | 用户转述的系统投递（见需求文档「背景与动机」第二段） | BUG-2 的现场 |

## 根因定位步骤与判定依据 serves: BUG-1, BUG-2

定位按"从弹框到后置链"单向推，每一步都有**代码级判据**，不靠推测：

1. **判据 A（拒绝为何不是终止信号）**：读 `application/internal/capture-mapping.ts:75-128` —— `buildCaptureQuestions()` 返回 4 问数组，`✖️ 不需要立项` 只是第 1 问的 option label（`:77-89`）。宿主 `dsh-user-questions` 的 `AskUserQuestionIntent` 只有 `plan-review`，**没有"选项即终止"表达能力**，UI 只能把 4 问走完 ⇒ 判定：短路必须由调用方做。
2. **判据 B（为何问完才判拒绝）**：读 `application/use-cases/CaptureRequirement.ts:127-158` —— 单次 `ask(4问)` 返回后才 `mapCaptureAnswers` → `mapped.rejected` ⇒ 判定：判定点晚于弹框，改判定点无用，必须改**发起方式**。
3. **判据 C（拒绝为何变成"闸门失败"）**：读 `adapters/GateAwareQuestions.ts:52-68` —— 只要 `answers.length > 0` 就 `enqueue(G0)`；再看 `application/gate/handlers/h1-advance.ts:30-40` 找不到需求 → `verdict=negative`、`skip:no_requirement` ⇒ 判定：链把"没需求"当失败处理。
4. **判据 D（"节点仍在 brainstorming"从哪来）**：读 `application/gate/handlers/h4-resume.ts:40-42` 输出 `{from ?? to}`，再看 `domain/gate/GateCatalog.ts:22-28` G0 **无 `from`** ⇒ 判定：文案回落到 `to='brainstorming'`，把目标态印成现状。
5. **反证（排除触发端）**：诊断日志显示 hook 登记与注入均正常（判据见上表第 3 行）⇒ 判定：触发端不动。

## 修复方案 serves: BUG-1, BUG-2

三处改动，全在 `packages/web/dsh-pmboard` 内；不改协议、不改工具 schema。

### 改动 1 · 题目拆两段（BUG-1） serves: BUG-1

文件：`src/application/internal/capture-mapping.ts`

- 由 `buildCaptureQuestions()`（4 问）拆为：
  - `buildCaptureIntentQuestions(titleOptions)` → 只含第 1 问「需求名称（含 ✖️ 不需要立项）」；
  - `buildCaptureDetailQuestions()` → 类型 / 难度 / 文档位置 3 问；
- 保留 `buildCaptureQuestions()` 作为两段拼接的兼容导出（既有调用点与测试无需改口径），或直接改调用点为两段——以不破坏既有 `capture.test.ts` 断言语义为准。
- 拒绝前缀常量 `REJECT_PREFIX`、`pickAnswer`、`mapCaptureAnswers` 语义不变（映射层只多一次"分批合并"）。

### 改动 2 · 用例编排短路（BUG-1 + BUG-2） serves: BUG-1, BUG-2

文件：`src/application/use-cases/CaptureRequirement.ts`

伪码（真实实现按现状风格书写）：

```text
第一段 = await questions.ask(buildCaptureIntentQuestions(titleOptions))   // 不带 gate：拒绝不该登记闸门
mapped1 = mapCaptureAnswers(第一段)
if (mapped1.rejected) {
  rejections.record({windowKey, at: now})      // 留痕不变（FR-5）
  return notCreated(mapped1, {note: '用户选择不立项：本次未创建需求（已留痕…）'})   // 不再发起第二段
}
第二段 = await questions.ask(buildCaptureDetailQuestions(), {gate: 'G0'})      // 肯定分支：G0 登记在这里
mapped = mapCaptureAnswers([...第一段, ...第二段])
…后续创建/推进 draft→brainstorming 不变…
```

- **不变量**：肯定分支的最终 4 问内容、默认值、创建与推进语义与改动前一致（防"修反"）；
- **G0 归属**：闸门登记从"第 1 段"挪到"第 2 段"，这样 H1 在 `turn/end` 看到的是**真实推进后的 brainstorming** = `affirmative`，从根上消除 BUG-2；
- **拒绝回执**：`defaults_used` 只反映真实作答（拒绝路径不再出现 `category/difficulty/doc_location`）。

### 改动 3 · H4 对无 `from` 的闸门不编现状（BUG-2 防御） serves: BUG-2

文件：`src/application/gate/handlers/h4-resume.ts`

- 负分支文案由 `未通过，节点仍在 {from ?? to}` 改为：有 `from` 才写"节点仍在 {from}"；无 `from` 时只写 `{gate} 未通过`（G0 本就没有"当前节点"可言）；
- 不改肯定分支文案（`【闸门确认】…已确认，节点推进到 {to}`），不改投递通道与失败降级语义。

## 数据契约与接口 serves: BUG-1, BUG-2

| 契约 | 现状 | 改动后 |
|---|---|---|
| `AskQuestion`（`application/ports.ts:147-152`） | `{id, header, question, options}` | **不变** |
| `AskAnswer` | `{id?, selected?, custom?}` | **不变** |
| `CaptureMapping`（`capture-mapping.ts:131-144`） | `{title, category, difficulty, docLocation, rejected, answers, defaultsUsed}` | **不变**（仅 `defaultsUsed` 在拒绝路径下语义更准） |
| `reqboard_capture` 工具出参 | `success/requirement_id/status/answers/defaults_used/note/…` | **不变** |
| `capture-rejections.json` | `[{windowKey, at, title?}]`，cap 50，TTL 30min | **不变** |
| 宿主 `user-questions` 协议 | — | **不动**（放弃"选项即终止"的宿主方案，见「不做的事」） |

## 回归测试落点 serves: BUG-1, BUG-2

| 用例 | 文件 | 断言（可证伪） |
|---|---|---|
| 拒绝只发一段 | `tests/capture-tool.test.ts` | 拒绝路径 `ask` 调用次数 = 1；第二段问题（id=category/difficulty/doc_location）从未出现在任何一次 `ask` 入参 |
| 拒绝不入闸门 | `tests/gate-aware-questions.test.ts` | 拒绝路径 `enqueue` 计数 = 0；肯定路径 = 1 |
| 拒绝无告警 | `tests/capture-tool.test.ts`（或 gate-handlers） | 拒绝路径 `deliver` 计数 = 0；投递文本不含「闸门待改进」 |
| 无 from 不编现状 | `tests/gate-handlers.test.ts` | G0 负分支输出不含子串 `节点仍在`；有 from 的闸门仍含 `节点仍在 {from}` |
| 肯定路径不变 | `tests/capture-tool.test.ts` + `tests/capture.test.ts` | 两段合计 4 问、创建成功、状态 brainstorming、`defaults_used` 语义不变 |
| 全量回归 | — | `npx vitest run packages/web/dsh-pmboard` 全绿 |
| 真机 | — | 重启后走一次拒绝路径：弹框立即收、无追问、无投递 |

## 不做的事 serves: BUG-1, BUG-2

- **不改宿主**：不给 `dsh-user-questions` 加"终止选项" intent（影响所有弹框、跨仓改动，收益不抵风险）。
- **不改工具 schema / 不改 FR-5 粘滞**：`reqboard_capture` 入参出参与 30 分钟粘滞原样保留。
- **不顺手重构**：`CaptureRequirement` 的其它分支（绑定检查、弹框不可用、缺名称、创建推进）不动一行。
- **越界观察（另单）**：`MoveRequirement.ts:56` 用全局 `ARTIFACT_CONFIRM_GATES` 而非 `confirmGateKindFor(category,…)`，使 `CATEGORY_FLOW_PROFILES.bug` 的 confirmGates 在推进时不生效（本单立项时已撞上）。不在本设计范围内修改。
