---
id: gate-post-chain
title: 闸门确认后置链（切面 + 责任链）
summary: 人工闸门被作答之后机器自动做什么：唯一点 join point、两相执行 H1..H5、短路/降级/幂等不变量、新加一道门要改哪里。
type: architecture
status: living
updated: 2026-09-20
owners: [w-878da638]
tags: [reqboard, gate, chain, pmboard, l2]
---

# 闸门确认后置链（切面 + 责任链）

> **这页回答**：人在弹框上点了一下之后，机器自动做了哪几件事、按什么顺序、失败了怎么办、
> 新加一道人工门要改哪里。事实源是代码（`packages/pages/dsh-pmboard/src/application/gate/**`），
> 本页与代码不一致时以代码为准。

## 0. 一句话

reqboard 的**五道人工闸门**在「**闸门被作答 且 裁决已落库**」这一个点上，被同一条后置链
`GatePostChain`（H1..H5）统一织入：

    H1 advance（推进 / 绑定）→ H2 compact（压缩上下文）→ H3 inject（注入作答后阶段纪律）
      → H4 resume（唤醒续跑）→ H5 audit（留痕）

**新增一道门 = 在 `GateCatalog` 登记一行，不新增一段「确认后逻辑」。**（REQ-e3b6a0）

## 1. Join point：唯一定义

> **人工闸门被作答，且裁决已落库。**

这是**唯一**允许产生「后置链信号」的位置。任何新增的确认型交互都必须汇到这一点；
**禁止**在用例里再各写一段「确认完之后做点什么」——散在三处做必然漏一处。

## 2. 两相执行（为什么必须拆开）

弹框作答发生在 **agent 正在执行工具的回合内**；而压缩上下文的框架契约要求轮次边界
（`idle() === true`），且 `session append` 拒绝「发布中重入」
（实测原文：`session append cannot reenter while another append is being published`）。
因此链条天然分两相：

| 相 | 时机 | 做什么 |
|---|---|---|
| **Phase A · 内联相** | 工具调用栈内（agent 忙） | H1 落章 + 状态迁移 + 绑定窗口；登记 `PendingGate(windowKey, gate, from, to, verdict, decidedAt)`（按窗口去重，只留最新一条） |
| **Phase B · 边界相** | 回合结束 `turn/end` 后的 setImmediate（绝不在事件派发内同步执行） | H2 → H3 → H4 → H5 |

两相之间就是「**人已经确认、机器还没开始走**」的窗口——这正是不拆两相时
「答完弹框停在那里等人敲『继续』」的成因。

## 3. 五个 handler

| Handler | 职责 | 相 | 前置条件 | 失败处置 |
|---|---|---|---|---|
| **H1 advance** | 落章 + 状态迁移（白名单转移）+ 绑定窗口（G0 时创建需求并绑定） | A | — | 抛错（裁决本身失败必须响亮） |
| **H2 compact** | 构造节点输入包 → 判时机/边界 → 先落盘 → surface 整段替换 | B | 肯定项 ∧ 输入包**自足** ∧ `idle()` ∧ tool 调用/结果配对平衡 | 结构化 skip/reject/fallback，**只 warn**，继续 H3 |
| **H3 inject** | 取「作答后所处阶段」纪律提示词（`resolveStagePrompt`，INV-1 唯一取词入口）并注入 | B | `isPromptStage(to)` ∧ `stageEnabledFor(category,to)` | 只 warn；H4 仍发中性续跑消息 |
| **H4 resume** | 唤醒 agent 自动推进（`agents.get(id).followup(createUserMessage(...))`） | B | agent 在线且具备 followup | 只 warn，不改工具返回值 |
| **H5 audit** | 注入留痕 + 隔离留痕 + 需求时间线评论 | B（最后） | — | 留痕失败不得中断链 |

**H2 与 H3 的关系**：输入包的 `## 路由提示词` 段就是 H3 的内容（同一取词入口，不产生第二份文案）。
H3 独立成 handler 的理由是**降级路径**：H2 跳过时（不可达 / agent 忙 / 文档未落盘），
提示词仍要随续跑消息送进去。

**输入包「自足」判定（H2 的核心前置）**：路由提示词可用 **且** 需求文档已落盘。
任一不满足 → H2 跳过。这条直接决定了 **G0 立项门不压缩**：立项那一刻需求文档还不存在，
压缩会让 agent 丢掉「用户为什么提这个需求」的全部上下文。

## 4. 不变量（链的契约）

| 性质 | 要求 |
|---|---|
| 有序 | H1..H5 固定顺序；`HANDLER_ORDER` 是唯一顺序事实源（乱序传入会被纠正） |
| 可短路 | H2 条件不满足 → skip 并继续 H3，**不阻断**链条 |
| 可降级 | 任一 handler 失败只记 warn + 留痕，**不回滚 H1 已落库的裁决**、不抛给调用方、不改工具返回值 |
| 幂等 | 同一次作答只跑一轮；键 = `(windowKey, gate, decidedAt)`；同一窗口 PendingGate 只保留最新一条（覆盖不排队） |
| 时序正确 | H2/H3 取词必须发生在 H1 落库**之后**（作答前取词 = 注入旧阶段纪律） |
| 可观测 | 每个 handler 各落一条留痕（跑没跑、为什么跳过） |
| 可回滚 | 链默认开（H1/H3/H4/H5 生效）；**H2 沿用独立开关、默认关**——开关关闭时链退化为「H1 + H3 + H4」，行为不小于现状 |

## 5. 五道门与「作答后所处阶段」

闸门事实源 = `domain/gate/GateCatalog.ts`（旧分散常量表已收敛进来）：

| 门 | from > to | 须确认产物 | 交互通道 | 确认后新阶段 |
|---|---|---|---|---|
| **G0** | (unbound) > draft | —（创建即立项） | pm 专有立项弹框 `reqboard_capture`（三问） | brainstorming |
| **G1** | brainstorming > design | requirement | `reqboard_ask_confirm(target=artifact, kind=requirement)` | design |
| **G2** | design > decomposing | plan | `reqboard_ask_confirm(target=plan)` | decomposing |
| **G3** | decomposing > implementing | decomposition | `reqboard_ask_confirm(target=artifact, kind=decomposition)` | implementing |
| **G4** | accepting > archived | verification | `reqboard_accept_sheet`（逐项裁决 + 最终归档确认） | archived |

**非肯定项**（需要修改 / 需要补充 / 需要澄清 / 暂停）只跑半条链：H1 不推进、H2 不压缩（阶段没变，
没必要遗弃上下文）、H3 注入**当前**阶段纪律、H4 带用户意见续跑。
**取消需求**（`*>canceled`）不进链：它不是「确认」，且 agent 无权发起。

## 6. 两个入口

1. **pm 专有立项弹框 `reqboard_capture`（G0）**：一次调用弹出三问
   （需求名称 / 需求类型 / 提示词难度）→ 用户作答 → **同一次调用内**完成答案映射 → 创建需求 →
   绑定本窗口 → 登记 G0 的 PendingGate。避免「先弹框、再另调 create」两段式（答案与创建之间会断链）。
   通道不可用时返回 `fallback=board`，**不伪造立项**。
2. **`GateAwareQuestions` 装饰器（其余三处 pm 弹框）**：包在 `UserQuestionPort` 外层。
   用例只声明「这次弹框属于哪个门」（`opts.gate`），装饰器只 `enqueue` 不执行链——
   任何走该端口且声明 gate 的弹框（现在与将来）**零额外代码**获得后置链。

**看板通道（board 一键确认）**：HTTP 侧没有 agent 回合，故由链侧主动补齐两件事——
**确认即推进** + **触发后置链**（按需求 `sourceSessionId` 定位绑定窗口投递）。
**窗口不在线 → 只落章、不推进、不伪造**，并在响应里如实说明「窗口不在线，请回会话推进」；
两通道同键去重，避免「看板点一次 + 会话又跑一轮」。

## 7. 代码地图

    domain/gate/GateSpec.ts        单个闸门：gateId / from / to / requiredKind / verdictShape / advanceWhitelist
    domain/gate/GateCatalog.ts     唯一事实源：四道产物门 + 立项门（替代散落多处的常量表）
    application/gate/GatePostChain.ts   Handler 契约 + 有序执行 + 短路/降级/幂等 + ChainScratch
    application/gate/PendingGate.ts     Phase A 登记、Phase B 消费
    application/gate/handlers/          h1-advance / h2-compact / h3-inject / h4-resume / h5-audit / shared
    adapters/GateAwareQuestions.ts      UserQuestionPort 装饰器（所有 pm 弹框自动获得能力）
    adapters/AgentDeliverer.ts          agents.get(id).followup(createUserMessage) 的唯一投递实现

分层纪律（机械门禁 `tests/layer-boundary.test.ts`）：`domain/**` 零 import `node:`/`@deepseek-ai/*`；
`application/**` 只依赖端口；会话与 fs 只在 `adapters/**` 与组合根。

## 8. 留痕与自检（可复核）

| 文件 | 内容 | 容量 |
|---|---|---|
| `.dsh-data/state/prompt-injection-log.json` | 每次阶段提示词注入：windowKey / stage / difficulty / routeKey / hitLevel / fragmentIds / 字符数 | ring 500 |
| `.dsh-data/state/node-isolation-log.json` | 每次压缩结算：status（replaced/skipped/fallback）/ reason / range / artifactSeq / replacementSeq | ring 200 |

自检（打印最后一条）：

    python3 -c "import json;print(json.load(open('.dsh-data/state/node-isolation-log.json'))[-1])"

**实测样例（2026-09-20，window session-878da638）**：隔离留痕 3 条，均为 `status=replaced`，
且每条 `artifactSeq < replacementSeq`（如 1961 < 5725）——「先落盘再遗弃」在生产中成立；
注入留痕含 `routeKey=accepting/light/feature`、`fragmentIds=[... , common/iron-rules]`、`hitLevel=exact`。
判据：**两个文件各出现对应条目、含状态与原因**，才算这条链真的跑了。

## 9. 扩展一道新门（照做即可）

1. 在 `domain/gate/GateCatalog.ts` 登记一行（`gateId / from / to / requiredKind / verdictShape / advanceWhitelist`）；
2. 用例弹框时声明 `opts.gate`；
3. 若该门开启一个需要注入纪律的新阶段，在阶段提示词 fragments 登记同名阶段。

**不需要**改 `GatePostChain`、不需要改 `GateAwareQuestions`——链与装饰器都按声明工作。
（单测 `tests/gate-aware-questions.test.ts` 锁死这条：新增一个带 `opts.gate` 的假弹框用例后链被登记，
且装饰器与链的代码**未被修改**。）

## 10. 边界（明确不做）

- **不动宿主通用工具 `ask_user_question`** 的行为；G0 是 pmboard 自己的弹框，不是给宿主工具加能力；
- **不做摘要式压缩**：压缩 = 既有「整段替换成节点输入包」，不引入 LLM 摘要；
- **不改任何阶段提示词正文**（fragments 文案不在本链范围）；
- **不做任务级并行 / workflow 自动推进**——本链只管「闸门确认后」。

---

## 相关页面

- [需求归档规范](requirement-archive.md) —— 归档 = 存底 + 合并，材料与合并去向
- [需求看板实操（从立项到归档）](../guides/reqboard-workflow.md) —— 全流程表 + 各阶段硬要求 + 错误码处置
- [需求节点详情系统](reqboard-stage-detail.md) —— 节点点开看工作记录（L2，与链配合）
- [全站页面索引](../INDEX.md)
