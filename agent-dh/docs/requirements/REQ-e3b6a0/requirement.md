---
req_id: REQ-e3b6a0
title: pmboard 闸门确认后置链：压缩上下文 + 注入阶段提示词 + 自动推进（切面/责任链）
category: feature
status: brainstorming
owner: w-878da638
created: 2026-09-20
business_value: 人工闸门是流水线唯一的人机交界。"人点一下、机器自己走完剩下"意味着确认之后必须原子地做三件事——压缩上下文、注入新阶段纪律、唤醒续跑；散在三处做必然漏一处，人就得点一次再催一次。
risk_level: high
---

# REQ-e3b6a0 闸门确认后置链（切面 / 责任链）

> 用户原话（本窗口 w-878da638）：
> - 首轮：「我发现 pm 插件里 ask_user_question 继续能力没有把下阶段的要求提示词注入，这个需要设计一下补充进去」
> - 升级轮：「现在我们弹框确认要实现一个切面功能或者责任链模式具体你设计，三问弹框作答 → 已过、REQ 已创建、窗口已绑定，确认后 → 调用创建立项 → 绑定窗口 → 压缩上下文 → 注入该阶段提示词让 agent 自动推进（用户不用注入提示词和继续推进），其他的人工闸门你帮我梳理流程」
>
> 三问确认：feature / 提示词难度 expert。
> **标题沿用了立项时的窄标题**（reqboard 无改题工具，见 §12 D6）；范围已按用户升级为准。
> 本文档只回答「做什么 + 链条契约」；实现形状（类/端口/文件）在 design 阶段。

---

## 1. 一句话目标

在 pmboard 的**每一道人工闸门**被作答之后，由一条**统一切面织入的后置责任链**自动完成
「状态推进 → 压缩上下文 → 注入作答后阶段纪律提示词 → 唤醒续跑」，
使人**答一次弹框即可**，不需要再手动输入「继续」，也不需要人替 agent 搬提示词。

**可证伪判定（总）**：在 :13080 上真实走一次 G1（确认需求文档），弹框点肯定项后**不再输入任何消息**，
agent 能自动带着 design 阶段纪律继续产出 `design/*.md`；且 `<dshHome>/state/node-isolation-log.json`
与 `prompt-injection-log.json` 各出现一条对应记录。

---

## 2. 产品定义

### 2.1 这道切面切的是什么

reqboard 有 5 道**人工闸门**（G0 立项门 + 4 道产物确认门）。它们分散在不同用例里
（`CreateRequirement` / `AskConfirm` / `AcceptSheet`），此前**没有任何统一的"确认之后"位置**：
每个用例只管自己那份落库，之后就结束了。这导致「确认后该发生什么」被各写各的、或被漏掉。

**切面（Aspect）**：把 join point 定在「**人工闸门被作答，且裁决已落库**」这一个点上，
所有门在这点上被统一织入同一条后置链。新增一道门 = 在闸门表登记一行，不新增一段"确认后逻辑"。

**责任链（Chain of Responsibility）**：后置动作拆成有序 handler，逐个执行、可短路、可降级：

```
GatePostChain (有序，H1..H5)
  │
  ├─ H1 advance   状态推进 / 绑定窗口（幂等：裁决用例已完成时只做校验）
  ├─ H2 compact   压缩上下文（条件 handler：输入包自足 且 agent 空闲）
  ├─ H3 inject    注入「作答后所处阶段」纪律提示词（唯一取词入口 INV-1）
  ├─ H4 resume    唤醒 agent 自动推进（不等人再敲"继续"）
  └─ H5 audit     留痕（injection-log + isolation-trace + decision_audit）
```

链的**契约**（这是本需求要的"做什么"）：

| 性质 | 要求 |
|---|---|
| 有序 | H1..H5 固定顺序；H2 依赖 H1 已落库（先落盘再遗弃） |
| 可短路 | H2 条件不满足 → skip 并继续 H3（不阻断链条） |
| 可降级 | 任一 handler 失败只记 warn + 留痕，**不回滚 H1 已落库的裁决**、不抛给调用方 |
| 幂等 | 同一次作答只跑一轮；重复信号按 (windowKey, gate, decidedAt) 去重 |
| 时序正确 | H2/H3 取词必须发生在 H1 落库**之后**（作答前取词 = 注入旧阶段纪律） |
| 可观测 | 每个 handler 各落一条留痕（跑没跑、为什么跳过） |

### 2.2 为什么必须两相（本需求最关键的结构判断）

弹框作答发生在 **agent 正在执行工具的回合内**；而压缩上下文的框架契约要求
`idle() === true`（轮次边界），且 `session append` 拒绝"发布中重入"（D-17 实测原文：
`session append cannot reenter while another append is being published`）。
因此链条天然分成两相：

```
Phase A · 内联相（工具调用栈内，agent 忙）
    H1 advance  ← 裁决用例本来就做（落章 + 状态迁移）
    登记 PendingGate（按窗口去重）

    ↓ 回合结束 turn/end（agent 空闲）

Phase B · 边界相（异步边界 setImmediate，绝不在事件派发内）
    H2 compact → H3 inject → H4 resume → H5 audit
```

两相之间是「**人已经确认、机器还没开始走**」的窗口——这正是用户观察到的"停在那里等人敲继续"。

---

## 3. 用户与角色

| 角色 | 诉求 | 现状痛点 |
|---|---|---|
| 人（唯一人工闸门持有者） | 点一次弹框，剩下机器自己走 | 答完 agent 停住；要手动敲"继续"；有时还得提醒它去读下一阶段规则 |
| 窗口 agent | 续跑时上下文干净（不被上一阶段的长对话拖累）+ 自带新阶段纪律 | 上下文越滚越长；新阶段提示词靠 systemPrompt 时机侥幸拿到，常拿不到 |
| 看板 / 审计 | 能回答"这次确认之后到底做了什么" | 注入留痕从未被这条路径写过；隔离留痕文件根本不存在 |
| 后续窗口 / 接手人 | 压缩后仍能凭"输入包"续跑 | 输入包能力已实现但默认关，从未产出过 |

---

## 4. 流程图

> ASCII 框图（看板文档预览走 marked，不渲染 mermaid，本仓仅 1 处 mermaid 用例）。

### 图 1 · 五道人工闸门与统一切面织入点

```
 draft ─▶ brainstorming ─▶ design ─▶ decomposing ─▶ implementing ─▶ accepting ─▶ archived
            ▲                 ▲            ▲                            ▲
            │G0 立项门         │G1           │G2                          │G3            │G4
            │pm 专有三问弹框     │确认需求文档  │批准拆分计划                  │确认拆分清单    │验收通过即归档
            │(create+bind)     │(requirement) │(plan)                      │(decomposition)│(verification)
            └──────────────────┴─────────────┴────────────────────────────┴──────────────┘
                                        │
                        ★ 统一切面织入点（唯一 join point）
                「人工闸门被作答，且裁决已落库」                  ← 新增门＝只加一行闸门表配置
                                        │
                              GatePostChain（H1..H5）

 不进链的情形：① 用户未作答（取消/暂离）② 弹框通道不可用（fallback=board）
              ③ 非肯定项（需要修改/需补充/暂停）→ 只跑 H3+H4（不推进、不压缩）
              ④ 取消需求（*>canceled）——人工闸门但不是"确认"
```

### 图 2 · 责任链两相时序

```
   人        弹框      裁决用例        台账     PendingGate    边界(turn/end)   Session/Agent
   │           │           │            │            │               │              │
   │──作答────▶│           │            │            │               │              │
   │           │──answers─▶│            │            │               │              │
   │           │           │─H1 落章+迁移▶│            │               │              │
   │           │           │─登记────────┼───────────▶│               │              │
   │           │◀─工具返回（本回合继续/结束）───────────────────────────────────────│
   │           │           │            │            │◀─turn/end─────│              │
   │           │           │            │            │─setImmediate─▶│              │
   │           │           │            │            │               │─H2 压缩──────▶│ surface replace
   │           │           │            │            │               │─H3 注入       │
   │           │           │            │            │               │─H4 唤醒──────▶│ 开新回合
   │           │           │            │            │               │─H5 留痕       │
   │◀─────────── 不必再敲"继续"：agent 带着压缩后的上下文 + 新阶段纪律继续 ──────────────│
```

### 图 3 · H2 压缩上下文：做什么 / 三条纪律 / 降级链

```
  压缩 = 在轮次边界把模型可见的 surface 整段替换成「节点输入包」：

    替换前 surface: [系统段][历史①][历史②]...[历史N]   ← 越滚越长，含着上一阶段的全部对话
    替换后 surface: [系统段][节点输入包]                 ← 只有两段

  节点输入包内容（INV-9：不读会话历史，因此压缩后仍能续跑）：
    ┌────────────────────────────────────────────────────────┐
    │ # 节点输入包 · REQ-xxxxxx · <阶段>                        │
    │ ## 当前节点        <阶段>（difficulty/category）           │
    │ ## 上游结论        已确认产物清单                          │
    │ ## 未决问题        未确认产物 + 阻塞 + 文档待同步            │
    │ ## 下一步          阶段链声明                              │
    │ ## 证据指针        产物路径                                │
    │ ## 路由提示词      resolveStagePrompt 的结果（= H3 的内容）  │
    │ ## 需求文档        docs/requirements/<REQ>/requirement.md  │
    └────────────────────────────────────────────────────────┘

  三条纪律（缺一不可，均为已实测的框架契约）：
   ① 先落盘再遗弃：产物写入完成（拿到事件 seq）才允许替换
   ② 边界必须配对平衡：tool 调用/结果必须成对，不平衡 → 拒绝替换 + 结构化错误
   ③ 只在轮次边界：agent 忙碌 → 不替换、留痕、不抛（等下一个边界）

  降级链（三条路径都不静默）：
   ① 触达得到 Session → 整段替换（replaced）
   ② 触达不到 → fallback：产出「请开新窗口 + 粘贴输入包」的文字指引
   ③ 兜底：输入包文本仍然完整返回（调用方可在同窗口重注入）
```

### 图 4 · 现状：三条断链 + 一条"有实现但从未跑过"

```
 (1) 状态转移注入（CaptureHook.onStagePrompt）
     收到用户消息 ─▶ 解析出阶段提示词(OK) ─▶ agents.followup(id, msg)
                                                └─▶ ✗ AgentRegistry 无此方法，守卫恒 false → 静默 no-op

 (2) 弹框自动继续（UserQuestionsAdapter.autoContinue）
     弹框作答 ─▶ onAnswered ?  ─▶ ✗ 组合根未注入第二参；且无调用方传 autoContinue → 零触发

 (3) 续跑消息内容：调用方给的静态串 ─▶ ✗ 不经 resolveStagePrompt → 无阶段提示词

 (4) 压缩上下文（IsolateNodeContext）**实现完整、但从未执行过**：
     开关 NODE_ISOLATION 未设 / profile 未配 nodeIsolation → 执行 0 次；
     触发点只有「绑定窗口收到用户消息」一条，盖不住"弹框作答"这条路径；
     留痕文件 <dshHome>/state/node-isolation-log.json 不存在（实测）。
```

---

## 5. 现状：已有能力盘点（能复用的很多，缺的是"接线 + 时机"）

本需求**不是从零造压缩能力**——压缩与留痕的地基已经存在，缺的是接线与触发时机。盘点如下：

| 能力 | 实现处（实测） | 现状 | 本需求处置 |
|---|---|---|---|
| 阶段提示词唯一取词入口 | `src/domain/prompt/index.ts:64 resolveStagePrompt`（INV-1） | 可用 | 复用为 H3 |
| 注入留痕 | `src/application/internal/injection-log.ts`（ring 500） | 可用 | 复用为 H5 |
| **压缩上下文** | `src/application/use-cases/IsolateNodeContext.ts`：轮次边界把 surface 整段替换成输入包 | **实现完整，但默认关、从未跑过** | 接入链成为 H2 |
| 节点输入包构造 | `src/application/internal/node-input-package.ts`（INV-9 不读会话历史） | 可用 | 直接复用 |
| 边界时机 / 失败隔离 | `src/application/internal/node-settlement.ts`（异步边界 setImmediate，永不抛） | 可用，但只接"绑定窗口收到用户消息"一个触发点 | 扩为**链执行器**的唯一异步边界 |
| 隔离留痕 | `src/application/internal/isolation-trace.ts`（ring 200） | 可用；文件尚不存在（从未写过） | 复用为 H5 |
| 弹框通道 | `src/application/ports.ts UserQuestionPort`；`adapters/UserQuestionsAdapter.ts` | 通道可用；`autoContinue` 桩**未接线** | 改造为链入口 |
| 会话投递 | `ctx.agents.get(id)?.followup(createUserMessage({...}))`，全仓 6 处范例 | 可用 | H4 按正确形状使用 |
| 立项三问弹框 | 文案由 CaptureHook 注入、执行靠 **DSH 宿主工具 `ask_user_question`** | **发起侧在 pmboard 手里**（是提示词注入，不是宿主黑盒） | 改文案指向 **pm 专有弹框**（D2 已定，见 FR-7） |

---

## 6. 设计骨架：切面 + 责任链（具体设计在 design 阶段展开）

### 6.1 Join point（切面织入点，唯一定义）

> **人工闸门被作答 且 裁决已落库**。

这是**唯一**允许产生"后置链信号"的位置。任何新增的确认型交互都必须汇到这一点，禁止在用例里再各写一段
"确认完之后做点什么"。

### 6.2 ConfirmContext（链的输入契约）

```
ConfirmContext {
  windowKey      string    // 作答窗口（agent id）
  gate           GateId    // G0 | G1 | G2 | G3 | G4
  from, to       Stage     // 作答前后所处阶段（H2/H3 取词依据 to）
  requirementId  string?   // G0 时由 H1 产出；其余为既有需求
  verdict        Affirmative | Negative   // 肯定项 / 非肯定项（决定 H1/H2 是否执行）
  answers        Answer[]  // 用户作答原文（进留痕与续跑摘要）
  decidedAt      number    // 幂等键的一半
}
```

### 6.3 五个 handler 的职责契约

| Handler | 职责 | 执行相 | 前置条件 | 失败处置 |
|---|---|---|---|---|
| **H1 advance** | 落章 + 状态迁移 + 绑定窗口（G0 时创建需求并绑定） | Phase A（内联） | — | 抛错（裁决本身失败必须响亮） |
| **H2 compact** | 调 `isolateNodeContext`：构造输入包 → 判时机/边界 → 先落盘 → surface 整段替换 | Phase B（边界） | 肯定项 且 输入包**自足** 且 `idle()` 且 边界配对平衡 | 结构化 skip/reject/fallback，**只 warn**，继续 H3 |
| **H3 inject** | 取「作答后所处阶段」纪律提示词（`resolveStagePrompt`）并注入会话 | Phase B | `isPromptStage(to)` 且 `stageEnabledFor(category,to)` | 取词失败 → 记 warn，H4 仍发中性续跑消息 |
| **H4 resume** | 唤醒 agent 自动推进（`agents.get(id).followup(createUserMessage(...))`） | Phase B | agent 在线且具备 followup | 只 warn，不改工具返回值 |
| **H5 audit** | 注入留痕 + 隔离留痕 + 决策审计 | Phase B（最后） | — | 留痕失败不得中断链 |

**H2 与 H3 的关系**：输入包的 `## 路由提示词` 段就是 H3 的内容（同一取词入口）。
H3 独立成 handler 的理由是**降级路径**：H2 跳过时（不可达 / agent 忙 / 文档未落盘），
H3 仍要把提示词随续跑消息送进去。二者共用取词入口，不产生第二份文案。

### 6.4 输入包"自足"的判定（H2 的核心前置条件）

压缩的前提是**压缩后仍能续跑**。输入包的自足性 = 路由提示词可用 **且** 需求文档已落盘
（`requirementDocPath` 可读到非空文本）。任一不满足 → H2 跳过（留下痕迹与原因），只跑 H3+H4。

这条判定直接决定了 **G0 立项门不压缩**：立项那一刻需求文档还不存在（brainstorming 才产出它），
若压缩，agent 会丢掉"用户为什么提这个需求"的全部上下文，反而写不出 `requirement.md`。

### 6.5 幂等与去重

- 幂等键 = `(windowKey, gate, decidedAt)`；同一次作答只跑一轮链。
- 同一窗口的 PendingGate 只保留最新一条（重复信号覆盖，不排队）。
- H2 同窗口同阶段只结算一次（已有 `settledNodes` 语义沿用）。

### 6.6 待验证的框架契约（V1，**不得假设**）

`surface replace` 内部是 `append("user/message", 输入包, {surfaceOp: replace})`。
而 DSH 的 Agent 有三档输入语义（读 `dsh-agent/lib/types/runtime-types.d.ts` 实证）：
`send(msg, target, wakeup)` / `followup(msg)`（**唤醒**新回合）/ `steer` / `inject(msg)`（**不唤醒**）。

**待验证**：`replace` 的 append 是否唤醒 driver。

- 若**会**唤醒 → H4 只需补摘要（或省略），链序 H2→H3→H4 成立；
- 若**不**唤醒（更像 `inject`）→ 必须 H4 显式 `followup` 唤醒，且要处理"输入包已被 append 一次、续跑消息又来一次"的重复；
  候选：把输入包文本作为 `followup` 的 message 内容，替换动作随后在下一个轮次边界完成；或新增端口方法 `replaceAndWake`。

**处置**：design 阶段第一个任务就是**契约实测**（在 :13080 上用真实窗口跑一次 replace，观察是否开新回合），
结论写进 `design/interfaces.md`；未实测前不得把任一种假设写进实现。

**V2 待实测契约（本需求不采用；仅当将来要"连非 pmboard 发起的弹框也纳入切面"时才需要）**：pmboard 根 ctx 注册 `user-questions/request` waterfall 中间件后，
是否真能收到**宿主工具**发起的请求（scope 过滤是否把非 agent 作用域的监听器排除）。
验证方式：注册一个只记日志的中间件 → 手动触发一次 `ask_user_question` → 看日志有没有命中；
命中则 A 成立；未命中则退回路线 B（迁弹框）。**不命中不得静默降级成"以为覆盖了 G0"。**

---

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已完成（有证据） | t-63a402、t-9f24a5、t-3270ae |
| FR-2 | ✅ 已完成（有证据） | t-9f24a5 |
| FR-3 | ✅ 已完成（有证据） | t-44ae54 |
| FR-4 | ✅ 已完成（有证据） | t-3f82e9 |
| FR-5 | ✅ 已完成（有证据） | t-f118db、t-db8f9c |
| FR-6 | ✅ 已完成（有证据） | t-9f24a5 |
| FR-7 | ✅ 已完成（有证据） | t-f33035 |
| FR-8 | ✅ 已完成（有证据） | t-3e11bf |
| FR-9 | ✅ 已完成（有证据） | t-dd6c5c |
| FR-10 | ✅ 已完成（有证据） | t-63a402、t-3270ae |

> 无未接收条款（10 条全部有落点）。

<!-- reqboard:marks:end -->

## 7. 人工闸门全景与逐门链路（"其他人工闸门"梳理）

### 7.1 闸门表（代码事实源）

`src/domain/artifact/ArtifactSpec.ts:38 ARTIFACT_CONFIRM_GATES`：

| 门 | from > to | 须确认产物 | 交互通道 | 确认后新阶段 |
|---|---|---|---|---|
| **G0** | (unbound) > draft | —（创建即立项） | **pm 专有三问弹框**（本次改造后；此前为宿主 `ask_user_question`） | brainstorming |
| **G1** | brainstorming > design | requirement | `reqboard_ask_confirm(target=artifact, kind=requirement)` | design |
| **G2** | design > decomposing | plan | `reqboard_ask_confirm(target=plan)` | decomposing |
| **G3** | decomposing > implementing | decomposition | `reqboard_ask_confirm(target=artifact, kind=decomposition)` | implementing |
| **G4** | accepting > archived | verification | `reqboard_accept_sheet`（逐项裁决 + 最终归档确认） | archived |
| —（非确认） | * > canceled | — | 看板人工操作（agent 调用被代码级拒绝） | canceled |

### 7.2 逐门链路（确认后 H1..H4 各做什么）

```
G0 立项门（三问弹框：需求名称 / 类型 / 难度）
  H1  reqboard_create（创建即立项）+ 绑定本窗口         → 需求进 draft → 自动进 brainstorming
  H2  ✗ 跳过（需求文档尚不存在 → 输入包不自足）
  H3  注入 brainstorming 阶段纪律提示词（heavy/light 按 §NFR-4 对齐后的档位）
  H4  followup 续跑 → agent 立刻开始写 docs/requirements/<REQ>/requirement.md
  期望：用户三问作答后不再输入任何消息，agent 自行产出需求文档并登记产物

G1 确认需求文档（requirement）
  H1  落章（confirmedAt/By/Via=session）+ brainstorming → design
  H2  ✓ 压缩：输入包 = design 路由提示词 + requirement.md + 台账投影（此时文档已落盘，自足）
  H3  design 阶段纪律（挂进输入包；降级时随续跑消息单独送）
  H4  followup 续跑 → agent 开始写 design/*.md 与 plan.md

G2 批准拆分计划（plan）
  H1  plan 落章（approvedAt/By/Via）+ design → decomposing
  H2  ✓ 压缩：输入包 = decomposing 路由提示词 + requirement.md + 台账投影（plan 已批准，列进"上游结论"）
  H3  decomposing 阶段纪律
  H4  followup 续跑 → agent 调 reqboard_decompose 落库任务卡

G3 确认拆分清单（decomposition）
  H1  落章 + decomposing → implementing
  H2  ✓ 压缩：输入包 = implementing 路由提示词 + requirement.md + 台账投影（**含任务卡清单**，implementing 阶段要按卡干）
  H3  implementing 阶段纪律（含「照卡执行、不二次创作」「每卡完工必须 task_report」等本仓覆盖条）
  H4  followup 续跑 → agent 开工第一张卡

G4 验收通过即归档（verification）
  H1  验收单逐项裁决落库；最终确认 → accepting → archived
  H2  ✓ 压缩：输入包 = archived 路由提示词 + requirement.md + 台账投影（含返工/覆盖记录）
  H3  archived **是可注入阶段**（ALL_STAGE_PROMPT_KEYS 含 archived，有 fragments/archived/*）→ 注入「补归档材料」收尾纪律
  H4  followup 续跑 → agent 调 reqboard_submit(kind=archive) 补材料

非肯定项（需要修改 / 需要补充 / 暂停）—— 进链但只跑半条：
  H1  ✗ 不推进（节点停在原处）；仅落"用户意见"评论
  H2  ✗ 不压缩（阶段没变，没必要遗弃上下文）
  H3  ✓ 注入**当前**阶段提示词
  H4  ✓ followup 续跑，消息带用户意见 → agent 按意见修订后再重新发起确认

取消需求（*>canceled）：不进链。它不是"确认"，且 agent 无权发起；看板侧操作后由既有机制留痕。
```

### 7.3 G0 的发起侧在 pmboard 自己手里（这是最关键的一处框正）

**框正**：G0 的弹框**不是"宿主工具发起的"**，它的发起链完整地落在 pmboard 内：

```
  session/event · user/message
        │  CaptureHook（adapters/CaptureHook.ts:205-287）
        │  判定：窗口 unbound && 无遗留 pending → 登记 pendingCapture（内存 Map，不进台账）
        ▼
  systemPrompt 组装时求值 reqboard:capture 段（src/index.ts:279-295）
        │  命中 pending → captureSectionText() → capturePromptForMessage(windowKey, text)
        ▼
  注入的文案（application/internal/capture-section.ts:211-238）
        │  「调用 ask_user_question 一次发两个问题向客户确认……」  ← 问题就在这一句
        ▼
  LLM 照文案去调宿主 ask_user_question 工具 → 弹框 → 用户作答 → LLM 调 reqboard_create
```

也就是说：**"让弹框启动"的开关是一段由 pmboard 注入的提示词**，不是不可触达的宿主黑盒。
因此 G0 的织入点应当选在**发起侧**（改文案 + 让文案指向 pmboard 自己的弹框工具），
而不是去拦宿主的 `user-questions/request` 接缝。

**发起侧改造（✅ 已定 · 2026-09-20 用户指令：「创建立项的 ask_user_question 要改成 pm 专有弹框」）**：

1. 注入文案由"调 `ask_user_question`"改为"调 **pmboard 的立项弹框工具**"（新工具，如 `reqboard_capture`）；
2. 该工具经既有 `UserQuestionPort` 弹**同一个 UI**（`userQuestions` 服务不变，视觉与交互不分叉）；
3. 拿到三问答案后在**同一个调用里**完成 H1（`reqboard_create` + 绑定窗口），并登记 G0 的 PendingGate；
4. 回合结束（turn/end）后进 Phase B：H2 **跳过**（需求文档尚未落盘）→ H3 注入 brainstorming 纪律 → H4 续跑 → H5 留痕。

为什么首选它而不是拦接缝：

| 维度 | 发起侧改造（首选） | 拦宿主 waterfall 接缝（备选） |
|---|---|---|
| 性质 | **主动定义**：谁发起弹框、答案怎么用、链怎么跑，全在 pmboard 里 | **被动观测**：只能看到"有个请求、有个答案"，要靠猜问题形状来判定是不是立项门 |
| 与 join point 对齐 | 天然对齐：G0 的"裁决已落库"就是 create+bind 完成那一刻 | 需额外建立"这次答案算不算裁决"的判据 |
| 覆盖范围 | 只覆盖 pmboard 发起的弹框（本需求要的正是这个） | 覆盖所有弹框（含 `exit_plan_mode` 等非立项弹框）——对本需求是过剩 |
| 风险 | 低：复用 `UserQuestionPort`，UI 不变；改的是一段文案 + 一个工具壳 | 中：依赖 scope 过滤行为（V2 待实测） |

**备选补充（非必需）**：若要连"非 pmboard 发起的弹框"也纳入切面，再叠加宿主 `user-questions/request` 的 waterfall 中间件
（`dsh-user-questions/lib/index.js`：`ask()` = `ctx.waterfall(scopeTarget(agent, agent), "user-questions/request", …, noAnswerer)`，
类型注释原文 **Return an answer to claim the request or call next() to delegate**；可达性见 §6.6 V2）。

### 7.3.1 顺带发现：同一门的三处口径自相矛盾（应一并修正）

| 出处 | 说的是几问 | 与工具 schema 是否一致 |
|---|---|---|
| `application/internal/capture-section.ts:220-221, 249`（注入文案） | **两问**（只有名称 + 类型） | ✗ —— `reqboard_create` 有 `prompt_difficulty` 参数 |
| `tools/CreateTool/prompt.ts`（工具契约 description） | **三问**（含提示词难度） | ✓ |
| `application/query/QueryState.ts:63`（`reqboard_status` 的 note） | **两问** | ✗ |

三处指向同一个"立项门"却说法不一，会导致 LLM 有时问两问、有时问三问，难度字段随机缺失（本需求实测自己那次是问了三问）。
本需求按**三问**统一（工具 schema 是事实源），一并修正三处文案。

> ⚠️ **撞车预警**：`capture-section.ts` 与 `QueryState.ts` 正是 **REQ-99f5fe（w-b5b8ab06 在途）** 的改动面。
> 本需求动同一处必须与其协调，避免第二个"基线归一"。处置见 §12 D7。

### 7.3.2 立项"何时弹"的缺口与硬化（2026-09-20 t-3e11bf E2E 走查返工）

**走查实测（窗口 session-361c2879，15:18–15:30，转录逐条核对）**：链路本身是通的——
`CaptureHook` 登记 ✓、`pendingCapture` 命中 ✓、`capturePromptForMessage` 注入 ✓
（turn 2/3/4 的 system/message 均含「检测到用户新输入」针对性段）。但该窗口 17 次
`tool/call`（PTC 展开为 35 次子调用：read 28 / grep 7）**零次 `reqboard_capture`**；
其中 15:23:57 那条「修复 FR-6 任务状态机 …」是明确工作意图，模型仍判为"对当前审查的追问"、
直接作答不弹框。

**根因（设计缺口，不是文案缺失）**：FR-7 只解决了"立项框走 pm 通道"，**没解决"什么时候必须弹"**——
原提示词是「请先判断**可能**包含值得立项的新工作意图 / 只是闲聊则正常回复」式的二元自由裁量，
且不弹框**零后果**（无拒绝、无留痕、无重试）→ 模型在忙于回答技术问题时默认选"先答完再说"。

**本次硬化（t-3e11bf）**：`capturePromptForMessage` / `captureGuidanceText` 改为
①**必须显式裁定**（判不准按"值得立项"处理）②值得立项时**本回合第一个工具调用**即
`reqboard_capture` ③不立项时必须在回复**首行**写明「本条不立项：<理由>」——把沉默变成
可审计表态。配套：`CaptureHook` 的 `turn/end` 增加消费留痕（PTC 下无法从 toolTrace 判定
是否调过工具，故只记消费、不做误判）；单测 `capture.test.ts` 锁定硬化语，防再被改软。

**仍不在本次范围**：代码侧"绕过模型直接发起弹框"的强制机制（例：登记 pending 后由组合根
主动投递催办 / 把 join point 从"闸门被作答后"扩到"待确认产物产生时"）——需人工拍板后另立范围。

### 7.4 顺带更正的两处文档漂移（不改代码）

| # | 漂移 | 证据 |
|---|---|---|
| 1 | `docs/guides/reqboard-workflow.md:17` 把「批准拆分计划」的边写成 `decomposing → implementing`（实际 `design → decomposing`），且**漏了 G3**；同文件第 31-33 行流程表却与代码一致 | ✅ **已更正（2026-09-20 t10）**：该行重写为「四道产物确认门 + 取消」，并显式引用事实源 `GateCatalog.ts` / `HUMAN_ONLY_REQ_TRANSITIONS` |
| 2 | `ArtifactSpec.ts:34` 注释写「五道人工确认门」，`ARTIFACT_CONFIRM_GATES` 只有 4 条（REQ-9f4a44 合并"验收通过/归档"后注释未同步） | ✅ **已消解（t2）**：门表迁入 `GateCatalog.ts` 时旧注释一并重写，现该文件只剩再导出说明（2026-09-20 复核） |

---

## 7.5 人工闸门标准流程（两条确认通道 · 本次梳理）

以 G1「确认需求文档」为例，一道门的完整流程（其余门同形，仅产物与提示词不同）：

```
① 备产（agent 侧）
   agent 写 docs/requirements/<REQ>/requirement.md
     └─ reqboard_submit(kind=requirement, path, summary)
          ├─ 内容门禁：功能编号 / 必填节 / 句法（不合格直接拒）
          └─ 登记 artifact{kind, path, stage}（幂等）→ 卡面出现「待确认」

② 上门（请人确认的三条路）
   ②a 首选：agent 主动调 reqboard_ask_confirm(target=artifact, kind=requirement)
   ②b 催办：产物登记 >30min 未确认 → milestoneReminderFor() 生成催办文案 → 投递提醒 agent 弹框
         ⚠️ 现状：投递经 onStagePrompt → agents.followup(id,msg) → **死调用，从未提醒过**（同根因第 3 个受害者）
   ②c 兜底：agent 硬推 reqboard_move(to=design) → 被拒
         REQBOARD_HUMAN_GATE / REQBOARD_ARTIFACT_NOT_CONFIRMED，拒绝消息里带【问题卡】
         gateQuestionCard() 直接给出可粘贴的 reqboard_ask_confirm(...) 调用

③ 弹框（pm 专有弹框；G0 立项门本次也改为走这条）
   UserQuestionPort.ask(questions, {agent, signal})   ← 底层 ctx.userQuestions 服务
   选项 5 项：确认推进 / 需要修改 / 需要补充 / 需要澄清 / 暂停（DEFAULT_CONFIRM_OPTIONS）

④ 作答分流 —— **两条通道不对称（本次要补的缺口）**
   通道 A · 会话弹框（artifact.confirmedVia = "session"）
       落章 + **原子推进**（ADVANCE_MAP 白名单 3 条：brainstorming>design / design>decomposing /
       decomposing>implementing）+ 评论「[确认弹框] 用户确认…」
       ✔ 有 agent 回合 → 可在 turn/end 触发 Phase B 后置链
   通道 B · 看板一键（artifact.confirmedVia = "board"）
       POST /req/artifact/confirm → **只落章**（confirmedAt/By）+ 评论「[产物确认] 人已确认产物…」
       推进要另点看板「→ 下一阶段」（POST /req/move，human actor）
       ✘ 没有 agent 回合 → 后置链无处触发；且人要**点两次**

⑤ 门放行判定（agent 侧与看板侧同源）
   ARTIFACT_CONFIRM_GATES[from>to] 要求的 kind 已 confirmedAt 非空 → 放行（不再受 human_gate 限制）
   否则拒绝；另经 assertArtifactGates 校验「产物存在 + 已确认」

⑥ 【本需求】后置链
   Phase A（内联）：登记 PendingGate(windowKey, gate, from, to, verdict)
       └─ turn/end（agent 空闲）→ setImmediate 异步边界
   Phase B：H2 压缩 → H3 注入 → H4 唤醒 → H5 留痕

⑦ 例外分支
   非肯定项（需要修改 / 补充 / 澄清 / 暂停）→ 不落章不推进 + 写"用户意见"评论 → 半链（H3 + H4）
   弹框通道不可用 → fallback=board（提示用户走看板，**不伪造确认**）
   取消需求（*>canceled）→ 人工专属，不进链
   subagent / 非活窗口 → DELEGATED_CALLER / CALLER_NOT_LIVE，不弹框
```

### 7.5.1 流程里暴露的三个缺口（本需求负责补前两个）

| # | 缺口 | 证据 | 处置 |
|---|---|---|---|
| 1 | **通道 B 只落章、不推进、无回合** | `http/routers/requirements.ts:151-175` 只写 `confirmedAt/By/Via`；`confirmedVia="board"` 不触发 ADVANCE_MAP；HTTP 请求没有 agent 回合，故 Phase B 无处挂 | 本需求 FR-9：看板确认后由链侧主动推进 + 投递（需给 HTTP handler 注入 agents 投递能力） |
| 2 | **30 分钟催办从未投递** | `CaptureHook.ts:273-277` 的 `milestoneReminderFor` 文案经 `onStagePrompt` → `index.ts:246-249` 的 `agents.followup(id,msg)` → `AgentRegistry` 无此方法 → 恒不执行（与 `onStagePrompt` 同根因） | 本需求 FR-1 修投递形状后自然恢复；补一条测试锁死 |
| 3 | 产物登记后没有"请人确认"的即时通知 | 只有 30min 后的催办（而它也死了）；人若不看会话就看不出有待确认产物 | 本需求范围外（属通知面），登记为线索 |

### 7.5.2 通道 A / B 能力对照

| 能力 | 通道 A 会话弹框 | 通道 B 看板一键 |
|---|---|---|
| 落章（confirmedAt/By/Via） | ✔ session | ✔ board |
| 状态推进 | ✔ 原子（同一次调用） | ✘ 需另点一次 |
| 触发后置链（Phase B） | ✔ 有回合，turn/end 可挂 | ✘ 无回合，需链侧主动投递 |
| 人要点几次 | 1 次 | 2 次（确认 + 推进） |
| 非肯定项语义 | ✔ 有（5 选项 + 用户意见） | ✘ 只有"确认"一个动作 |

---

## 7.6 确认后要做的事：公共骨架 + 逐门功能清单（对齐用户写立项的粒度）

### (A) 公共骨架：**任一**人工闸门「确认后」都要做的 10 件

| # | 做什么 | 承载 | 新增 / 已有 |
|---|---|---|---|
| 1 | **落章**：`artifact.confirmedAt/By/Via` + 台账评论 | 裁决用例（A）/ HTTP 确认端点（B） | 已有 |
| 2 | **状态推进**：`from → to`（白名单转移） | `ADVANCE_MAP` | A 已有 / **B 需补**（FR-9） |
| 3 | **绑定窗口**：窗口 ↔ 需求 | G0 由 create 完成；其余已绑定 | G0 已有 |
| 4 | **登记后置链信号** `PendingGate(windowKey, gate, from, to, verdict, decidedAt)` | 切面织入点 | **新增** |
| 5 | **压缩上下文**（条件：肯定项 ∧ 输入包自足 ∧ agent 空闲 ∧ 边界配对平衡） | H2 = `isolateNodeContext` | **接线**（能力已有、从未跑过） |
| 6 | **注入作答后阶段纪律提示词**（唯一取词入口 + 闸门） | H3 = `resolveStagePrompt` | **新增接线** |
| 7 | **唤醒 agent 自动续跑** | H4 = `agents.get(id).followup(createUserMessage)` | **修复形状** |
| 8 | **留痕**：注入留痕 + 隔离留痕 + 决策审计 | H5 | **新增接线** |
| 9 | **幂等**：按 `(windowKey, gate, decidedAt)` 去重 | 链执行器 | **新增** |
| 10 | **降级**：任一失败只 warn，**不回滚**落章与推进 | 链执行器 | **新增** |

### (B) 逐门功能清单（确认后按序执行，可逐条验收）

```
G0 立项门（三问弹框：需求名称 / 类型 / 难度）
  输入：三问作答
  ① 创建需求      reqboard_create(title, category, prompt_difficulty, summary, reason)
  ② 绑定窗口      sourceSessionId = 本窗口（需求进 draft）
  ③ 自动推进      draft → brainstorming
  ④ 压缩上下文    跳过（需求文档尚未落盘 → 输入包不自足）
  ⑤ 注入纪律      brainstorming 阶段提示词（档位由 prompt_difficulty 映射 light/heavy）
  ⑥ 唤醒续跑      agent 自行产出并登记 docs/requirements/<REQ>/requirement.md
  ⑦ 留痕          注入留痕 + 决策审计
  人不做：不再敲"继续"、不再替 agent 搬提示词

G1 确认需求文档（kind=requirement）
  ① 落章          confirmedVia=session（或 board）
  ② 推进          brainstorming → design
  ③ 压缩上下文    输入包 = design 路由提示词 + requirement.md + 台账投影
                  三条纪律：先落盘再遗弃 / 边界 tool 配对平衡 / 只在轮次边界
  ④ 注入纪律      design 阶段提示词
  ⑤ 唤醒续跑      agent 开始写 design/*.md 与 plan.md
  ⑥ 留痕          注入留痕（十字段）+ 隔离留痕（含被替换区间 range）

G2 批准拆分计划（target=plan）
  ① 落章          plan.approvedAt/By/Via
  ② 推进          design → decomposing
  ③ 压缩上下文    输入包 = decomposing 提示词 + requirement.md + 台账（plan 列入"上游结论"）
  ④ 注入纪律      decomposing 阶段提示词
  ⑤ 唤醒续跑      agent 调 reqboard_decompose 落库任务卡
  ⑥ 留痕

G3 确认拆分清单（kind=decomposition）
  ① 落章
  ② 推进          decomposing → implementing
  ③ 压缩上下文    输入包 = implementing 提示词 + requirement.md + 台账（**含任务卡清单**）
  ④ 注入纪律      implementing 阶段提示词（照卡执行 / 每卡必 task_report / 构建新鲜度门）
  ⑤ 唤醒续跑      agent 开工第一张卡
  ⑥ 留痕

G4 验收通过即归档（kind=verification）
  ① 裁决落库      验收单逐项裁决；最终确认 → verification 落章
  ② 推进          accepting → archived
  ③ 压缩上下文    输入包 = archived 提示词 + requirement.md + 台账（含返工/覆盖记录）
  ④ 注入纪律      archived 阶段提示词（补归档材料：目录 / 清单 / 合并去向 / 索引 / 说明书更新点）
  ⑤ 唤醒续跑      agent 调 reqboard_submit(kind=archive)
  ⑥ 留痕

非肯定项（需要修改 / 需要补充 / 需要澄清 / 暂停）
  ① 不落章、不推进
  ② 写"用户意见"评论
  ③ 不压缩（阶段没变，没必要遗弃上下文）
  ④ 注入当前阶段纪律（不是"下一阶段"）
  ⑤ 唤醒续跑，消息带用户意见 → agent 修订后重新发起确认

取消需求（*>canceled）
  不进链：它不是"确认"动作，且 agent 无权发起；看板侧操作，走既有留痕
```

### (C) 本次要交付的功能清单（新增 / 修复 / 改造）

| 类别 | 功能 | 落点 |
|---|---|---|
| **新增** | 切面织入点 + 责任链执行器（Phase A 登记 / Phase B 异步边界） | FR-1、FR-2 |
| **新增** | H2 压缩接线（含独立开关与"输入包自足"判定） | FR-3 |
| **新增** | H3 注入器（含 `promptDifficulty → light/heavy` 映射） | FR-4、NFR-4 |
| **新增** | H5 留痕接线（注入留痕 + 隔离留痕 + 决策审计） | FR-6 |
| **新增** | pm 专有立项弹框工具 `reqboard_capture`（三问 + 原子 create+bind） | FR-7 |
| **新增** | 看板通道 B 的"确认即推进 + 链侧投递"（HTTP 侧需注入 agents 投递能力） | FR-9 |
| **修复** | H4 投递形状（`agents.get(id).followup(createUserMessage)`）——同时救活**状态转移注入**与**30 分钟催办** | FR-1、FR-5 |
| **修复** | 三处"两问 / 三问"口径统一为三问 | FR-7 |
| **改造** | CaptureHook 注入文案改指 pm 弹框工具（不再点名宿主 `ask_user_question`） | FR-7 |

---

## 7.7 弹框入口清点 + 「人工闸门域」的分与合（2026-09-20 用户提问）

### 7.7.1 现有弹框入口清点（全部）

| # | 入口 | 形态 | 答案语义 | 对应门 |
|---|---|---|---|---|
| 1 | 宿主 `ask_user_question` | 宿主工具（`dsh-tool-ask-user` → `ctx.userQuestions`） | `selected[]` / `custom` 自由 | 无（通用征询） |
| 2 | **立项三问**（现状＝文案驱动宿主工具；本次改造） | 文案 → 宿主工具 → 目标改为 pm 工具 | 表单语义：名称 / 类型 / 难度 | **G0** |
| 3 | `reqboard_ask_confirm(target=artifact)` | pm 工具 → `UserQuestionPort` | 单选语义：5 选项（肯定 / 修改 / 补充 / 澄清 / 暂停）+ 自定义 | **G1 / G3** |
| 4 | `reqboard_ask_confirm(target=plan)` | 同上 | 单选语义（同 3） | **G2** |
| 5 | `reqboard_accept_sheet`（逐项裁决） | 同上 | **多项裁决语义**：N 问，每问 passed / failed + opinion | **G4 逐项** |
| 6 | `reqboard_accept_sheet`（最终归档拍板） | 同上 | 单选语义（二选一） | **G4 最终** |
| 7 | `exit_plan_mode`（`dsh-plan-mode`） | 宿主工具 | `intent: plan-review`（approve 标签） | 无（宿主自己的门） |

结论：现有 **三种答案语义族**（单选型 / 多项裁决型 / 表单取值型）分布在 **4 处 pm 调用点**（`AskConfirm.ts:76`、`AcceptSheet.ts:62`、`AcceptSheet.ts:149`，加本次新增的立项）与 **2 处宿主工具**。

### 7.7.2 分与合：**入口分开 / 通道合并 / 链统一**

| 层 | 结论 | 理由 |
|---|---|---|
| **入口（工具面）** | **分开**，且必须分 | ① 三种答案语义族的入参与返回值形状本就不同；② 合并成"带 mode 的巨工具"会把路由决策推给模型，而**门是安全边界**，模型选错 mode = 静默走错门；③ 门的必填产物 kind 分开时是常量、合并后变运行期字符串；④ 既有测试与阶段提示词都按入口写（`stage-prompts.test.ts:141` 断言「落章型确认纪律均指向 reqboard_ask_confirm」） |
| **通道（端口面）** | **合并**，保持一个 | `UserQuestionPort` 已是唯一出口，三个入口都走它。只需**补一条能力**：`opts.gate` 声明——这是切面识别 join point 的唯一信息源 |
| **链（能力面）** | **统一成一条**，用**装饰器**让所有入口自动获得 | 见 7.7.3。新增入口 **零成本**获得"确认后压缩 / 注入 / 续跑" |

一句话：**三个入口、一个通道、一条链。**

**特别说明：立项三问不要塞进 `reqboard_ask_confirm`**（不做成 `target=create`）。因为 ask_confirm 的语义是"确认**已有**产物 / 批准**已有**计划"，落章对象是 `artifact.confirmedAt`；而立项三问是"表单取值 + 创建"，**根本没有产物可落章**。硬塞会让 target 枚举爆炸、且 G0 的落章语义不成立。正确做法：新工具 `reqboard_capture`，但**共用同一个通道与同一条链**。

### 7.7.3 能力怎么"通过接口"给到所有 pm 弹框（装饰器织入）

```ts
// adapters/GateAwareQuestions.ts —— 包在 UserQuestionPort 外层的装饰器
class GateAwareQuestions implements UserQuestionPort {
  constructor(private inner: UserQuestionPort, private chain: GatePostChainPort, private clock: Clock) {}

  ask(questions, opts) {
    return this.inner.ask(questions, opts).then((answers) => {
      // ① 委托真实 UI：行为与返回协议零变化
      // ② 只"登记"PendingGate，不执行链（链在 turn/end 的 Phase B 跑）
      if (opts.gate !== undefined) this.chain.enqueue({
        windowKey: windowKeyOf(opts.agent), gate: opts.gate,
        answers, decidedAt: this.clock.now(),
      })
      // ③ 原样返回答案
      return answers
    })
  }
}
```

为什么是装饰器而不是在每个用例里写链调用：

- **新入口零成本**：任何走 `UserQuestionPort` 且声明 `opts.gate` 的弹框（现在与将来）自动获得能力，不需要改链；
- **用例层只声明意图**：用例只说"这次弹框属于哪个门"，不碰链的细节（保持 application 用例薄）；
- **时序仍然正确**：装饰器只 `enqueue`；**落章与推进（H1）仍由用例随后完成**；Phase B 在 turn/end 才执行 H2..H5——天然满足"先落盘再遗弃"。

### 7.7.4 「人工闸门域」目录与边界

```
domain/gate/            闸门领域（纯规则，零 I/O、零 import）
  GateSpec              单个闸门：gateId / from / to / requiredKind / verdictShape / advanceWhitelist
  GateCatalog           唯一事实源：四道产物门 + 立项门（替代散落多处的常量表）

application/gate/       后置链编排（只依赖端口）
  GatePostChain         Handler 契约 + 有序执行 + 短路 / 降级 / 幂等
  handlers/             H1 advance · H2 compact · H3 inject · H4 resume · H5 audit

adapters/               通道与投递（唯一碰会话与 fs 的地方）
  GateAwareQuestions    UserQuestionPort 装饰器（所有 pm 弹框自动获得能力）
  AgentDeliverer        agents.get(id).followup(createUserMessage) 的唯一投递实现
```

边界纪律（沿用既有机械门禁 `tests/layer-boundary.test.ts`）：
`domain/**` 零 import `node:` / `@deepseek-ai/*`；`application/**` 只依赖端口；会话与 fs 只在 `adapters/**` 与组合根。

### 7.7.5 这些地方**确实该合并**（现状是多份真相）

| 应合并项 | 现状散落处 | 合并去处 |
|---|---|---|
| 状态推进白名单 | `AskConfirm.ts:26-30` 私有的 `ADVANCE_MAP` | `GateCatalog` |
| 产物确认门表 | `ArtifactSpec.ts:38 ARTIFACT_CONFIRM_GATES` | `GateCatalog`（唯一事实源） |
| 人工专属转移集合 | `HUMAN_ONLY_REQ_TRANSITIONS` | `GateCatalog` |
| 门的问题卡文案 | `support.ts:158-170 gateQuestionCard` 的问题表 | `GateCatalog`（或由 GateSpec 派生） |
| 窗口投递实现 | pmboard 一处写错 + lifecycle / solve-kit / genome 各一份 | 单一 `AgentDeliverer`（本需求只落 pmboard 侧，跨包收敛另立需求） |

---

## 8. 功能点

### FR-1: 统一切面织入点

定义唯一 join point「人工闸门被作答，且裁决已落库」；所有门的后置动作统一从这里出发；新增一道门只加配置、不改用例代码。

### FR-2: 后置责任链框架

实现 H1..H5 有序 handler 链：可短路（H2 条件不满足则继续 H3）、可降级（失败只 warn + 留痕）、幂等（同一次作答只跑一轮）、每 handler 留痕。链定义单点，禁止用例再各写后置逻辑。

### FR-3: H2 压缩上下文

复用既有 `isolateNodeContext`：条件执行（肯定项 + 输入包自足 + agent 空闲 + 边界配对平衡），三条纪律（先落盘再遗弃 / 边界平衡 / 只在轮次边界）与 D-12 降级链原样遵守。

### FR-4: H3 注入作答后阶段纪律提示词

只走唯一取词入口 `resolveStagePrompt`（INV-1）；取词时序必须在 H1 落库之后；先过 `isPromptStage` 与 `stageEnabledFor` 闸门；非肯定项注入**当前**阶段提示词。

### FR-5: H4 唤醒自动推进

用正确投递形状 `ctx.agents.get(id)?.followup(createUserMessage({ ... }))`；投递失败只 warn，不改工具返回值。同时修复现状 `agents.followup(id, msg)` 的死调用。

### FR-6: H5 留痕

注入留痕（十字段）+ 隔离留痕（status/reason/range）+ 决策审计；「跑没跑、为什么跳过」必须可查。

### FR-7: 立项三问改为 pm 专有弹框（已定，2026-09-20 用户指令）

**指令原文**：「创建立项的 ask_user_question 要改成 pm 专有弹框」。

具体要求：

1. **发起侧换手**：CaptureHook 注入的立项引导文案，由"调宿主 `ask_user_question`"改为"调 **pmboard 立项弹框工具**"（暂名 `reqboard_capture`，最终命名在 design 定）；
2. **pm 专有弹框**：该工具经 pmboard 既有的 `UserQuestionPort` 弹框（底层仍是 `ctx.userQuestions` 服务，**UI 与交互不分叉**，只是调用方从宿主工具变成 pmboard 工具）；
3. **一次调用一把梭**：三问作答后在**同一个工具调用内**完成——答案映射 → `reqboard_create`（创建即立项）→ 绑定本窗口 → 登记 G0 的 PendingGate；避免"先弹框、再另调 create"的两段式（那样答案与创建之间会断链）；
4. **答案映射契约**（三问 → 创建参数）：
   - 问题一「需求名称」→ `title`：优先取 `custom`（用户自定义），否则取 `selected[0]`；
   - 问题二「需求类型」→ `category`：取 `selected[0]`（六个枚举之一）；
   - 问题三「提示词难度」→ `prompt_difficulty`：取 `selected[0]`（simple/standard/advanced/expert）；
   - 任一缺失 → 回落到既有默认并**在回执里说明**（不静默猜）；
5. **弹框通道不可用时**：与 `reqboard_ask_confirm` 同语义——返回 `fallback=board`，提示用户到看板立项，**不伪造立项**；
6. **Phase B 照常**：H2 **跳过**（需求文档未落盘、输入包不自足）→ H3 注入 brainstorming 纪律 → H4 续跑 → H5 留痕；
7. **口径统一**：把"两问 / 三问"三处矛盾统一为**三问**（工具 schema 为事实源）——见 §7.3.1。
8. **触发时机硬化**（2026-09-20 t-3e11bf E2E 走查返工）：判据从"请自行判断**可能**值得立项"
   改为**必须显式裁定**——判不准按"值得立项"处理；值得立项时**本回合第一个工具调用**即
   `reqboard_capture`；不立项时必须在回复首行写明「本条不立项：<理由>」。理由与实测见 §7.3.2。

### FR-8: 逐门链路落地

§7.2 的五道门链路 + 非肯定项半链 + 取消不进链，全部用同一框架表达并落地。

### FR-9: 看板一键确认通道纳入切面

通道 B（`POST /req/artifact/confirm`）落章后，由切面在链侧补齐两件事：**确认即推进**、**触发后置链**。

- 需要给 HTTP 路由注入 agent 投递能力（`agents.get(sessionId)?.followup(createUserMessage(...))`），
  按需求的 `sourceSessionId` 定位绑定窗口；
- **窗口不在线 → 只落章、不推进、不伪造**，并在响应里如实说明"窗口不在线，请回会话推进"；
- 幂等：与通道 A 同键去重（`windowKey, gate, decidedAt`），避免"看板点一次 + 会话又跑一轮"；
- 两通道对**人**的语义必须一致：确认一次 = 门开 + 自动往下走。

### FR-10: 人工闸门统一领域 + 能力经接口给到所有 pm 弹框

建立 `domain/gate/`（`GateSpec` + `GateCatalog`，纯规则零 I/O）作为「人工闸门」的唯一事实源，
并把现存四处重复定义（推进白名单 / 产物门表 / 人工专属转移 / 问题卡文案）收敛进去；
在 `UserQuestionPort` 外层以**装饰器**（`GateAwareQuestions`）织入能力：任何走该端口且声明 `opts.gate` 的弹框
**零额外代码**即获得"确认后压缩 / 注入 / 续跑"；用例层只声明"这次弹框属于哪个门"。

## 9. 非功能需求

| 编号 | 要求 |
|---|---|
| **NFR-1** | **不动宿主通用工具**：`ask_user_question` 的通用行为零改动（用户已裁定「不能有这个能力，会混乱的」）。G0 是**把 pmboard 自己的立项弹框**搬到 pmboard 通道，不是给宿主工具加能力 |
| **NFR-2** | **降级不阻塞**：H2/H3/H4/H5 任一失败只 warn + 留痕，不回滚 H1 已落库的裁决、不改变工具返回值、不向调用方抛错 |
| **NFR-3** | **异步边界纪律**：Phase B 绝不在 session/event 派发内同步执行（D-17 实测：`session append cannot reenter...`）；统一经 setImmediate 类异步边界 |
| **NFR-4** | **提示词难度取词对齐**：`promptDifficulty`（simple/standard/advanced/expert）接进取词档位映射（`simple/standard → light`、`advanced/expert → heavy`）；与文本推断冲突时取重不取轻 |
| **NFR-5** | **分层边界不破**：`application/**` 不 import `node:` / `@deepseek-ai/*`（`tests/layer-boundary.test.ts` 机械门禁）；`domain/**` 保持纯函数；会话与 fs 只在 `adapters/**` 与组合根 |
| **NFR-6** | **可回滚**：压缩与续跑默认走开关（既有 `NODE_ISOLATION` 语义扩展为"链开关"），关闭时链退化为"H1 + H3 + H4"，行为不小于现状 |

---

## 10. 边界

**做**（三组，每组一条主线）：

1. **建切面 + 责任链框架**：唯一定义 join point「闸门被作答且裁决已落库」，实现 H1..H5 有序链（可短路 / 可降级 / 幂等 / 每 handler 留痕），五道人工闸门统一织入；G0 立项三问弹框改走 pmboard 弹框通道以纳入切面；
2. **把既有压缩能力接进链（H2）**：`isolateNodeContext` 条件执行 + 三条纪律 + 降级链原样遵守，使"确认之后"的上下文收敛为节点输入包（含需求文档与台账投影）；
3. **修好两个让链空转的根因**：投递形状（`agents.get(id).followup(createUserMessage(...))`）与提示词难度档位对齐（`promptDifficulty` 接进取词），使 H3/H4 真正生效。

**不做**（明确排除，写进边界即本次不做）：

1. **不动宿主通用工具** `ask_user_question` 的行为（用户已裁定）；G0 只搬 pmboard 自己的弹框，不给宿主工具加能力；
2. **不做任务级并行 / workflow 的自动推进**——实施阶段"任务依赖链自动连跑、并行 workflow"是另一条线（粒度、状态机、失败语义都不同），本需求只管"闸门确认后"；
3. **不改任何阶段提示词正文**（`fragments/**` 文案不在本次范围），本次只解决"注没注、注的是不是那一档、注的时机对不对"；
4. **不做摘要式压缩**——压缩 = 既有"整段替换成输入包"实现，不引入 LLM 摘要（那是另一条技术路线，风险与成本都不同）。

---

## 11. 判定标准（可证伪：跑什么、看到什么算完成）

| 编号 | 判定 | 怎么验（命令 / 观察） |
|---|---|---|
| AC-1.1 | 切面是唯一织入点 | 单测：只新增一行 gate 配置（不改任何用例代码）→ 该门作答后链被触发 |
| AC-1.2 | 幂等 | 单测：同 `(windowKey, gate, decidedAt)` 重复信号 → handler 各只被调用一次 |
| AC-2.1 | 链序与短路 | 单测（注入 fake handler）：断言 H1→H2(skip)→H3→H4→H5 顺序；H2 skip **不阻断** H3 |
| AC-2.2 | 可降级 | 单测：H2/H4 抛错 → H1 落库结果不变、工具返回值不变、仅多 warn |
| AC-3.1 | 压缩真发生 | 单测：断言 `isolateNodeContext` 被调用且 `status=replaced`，`range` 自首个非 system 节点到 surface 末尾 |
| AC-3.2 | 压缩条件 | 单测：需求文档不存在 → skip（带 code）；`idle()=false` → skip；触达不到 → fallback 且返回输入包文本 |
| AC-3.3 | 三条纪律 | 单测：断言 `artifactSeq < replacementSeq`（先落盘再遗弃）；边界不平衡 → rejected；注入替身 scheduler 断言"派发内不同步执行" |
| AC-4.1 | H3 时序正确 | 单测：用 fake 台账在 H1 前后取 `revision`，断言取词发生在落库之后；断言 G1 消息含 design 档片段 id、不含 brainstorming 档 |
| AC-4.2 | 非肯定项半链 | 单测：选「需要修改」→ 断言节点未推进、H2 未执行、消息含当前阶段提示词与 `user_feedback` |
| AC-5.1 | 投递形状修正 | 单测：断言经 `agents.get(id).followup` 且消息为 `createUserMessage` 形状；`grep -rn "agents\.followup(" packages/pages/dsh-pmboard/src` → **0 命中** |
| AC-5.2 | 投递降级 | 单测：agent 离线/无 followup/抛错 → 只 warn，工具返回值与成功路径一致 |
| AC-6.1 | 留痕齐全 | 单测 + 运行观察：`prompt-injection-log.json` 与 `node-isolation-log.json` 各出现对应条目，含状态与原因 |
| AC-7.1 | G0 端到端 | 真实走一次立项三问弹框 → 作答后**不再输入任何消息**，agent 自动产出并登记 `docs/requirements/<REQ>/requirement.md` |
| AC-7.2 | 立项弹框走 pm 通道 | 单测：注入 fake `UserQuestionPort` → 断言 `ask()` 被调用（三问同一批次）；且断言 create + 绑定窗口在同一次工具调用内完成（台账里需求已存在且 `sourceSessionId` = 本窗口） |
| AC-7.3 | 不再点名宿主工具 | `grep -n "ask_user_question" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts` → **0 命中**；三处"两问/三问"口径一致为三问 |
| AC-7.4 | 答案映射契约 | 单测：名称取 `custom` 优先、类型/难度取 `selected[0]`；任一缺失走默认且在回执里显式说明（不静默猜） |
| AC-8.1 | 难度对齐 | 单测：`promptDifficulty=expert` → `resolveStagePrompt` 的 `routeKey` 含 `heavy`；`simple` → `light`；未声明 → 仍按文本推断（向后兼容） |
| AC-9.1 | 看板确认即推进 + 触发链 | 单测：调 `POST /req/artifact/confirm`（注入 fake 投递端口）→ 断言 ① 落章 `confirmedVia=board` ② 状态已推进 ③ 投递端口被调用一次 |
| AC-9.2 | 窗口离线不伪造 | 单测：`agents.get` 返回 undefined → 断言只落章、状态未推进、响应含"窗口不在线"说明 |
| AC-9.3 | 两通道幂等 | 单测：先走看板 B 再走会话 A（同 gate）→ 断言链只跑一轮、状态只推进一次 |
| AC-10.1 | 闸门定义单点 | 单测：新增一道门只改 `GateCatalog`；`grep -rn "ADVANCE_MAP\|ARTIFACT_CONFIRM_GATES" packages/pages/dsh-pmboard/src` → 只剩领域内一处定义 |
| AC-10.2 | 新弹框零成本获得能力 | 单测：新增一个走 `UserQuestionPort` 且带 `opts.gate` 的假用例 → 断言链被登记（**不改装饰器与链代码**） |
| AC-10.3 | 分层边界不破 | `tests/layer-boundary.test.ts` 通过；`domain/gate/**` 零 import `node:`/`@deepseek-ai/*` |
| AC-11.1 | 门禁 | `cd packages/pages/dsh-pmboard && npx vitest run` 全绿；`npx tsc --noEmit -p tsconfig.json` 无新增错误 |
| AC-11.2 | 线上可观察（总验收） | 重启 :13080 后真实走一次 G1：点肯定项后**不再输入任何消息**，agent 自动开始 design 阶段；两个留痕文件各新增一条 |
| AC-11.3 | 文档漂移已同步 | `docs/guides/reqboard-workflow.md` 闸门表与 `ArtifactSpec.ts:38` 逐条一致；`ArtifactSpec.ts` 注释条数 = map 条数（4） |

---

## 12. 决策记录（2026-09-20 用户裁定 · 全部已定）

> 用户原话：「给我弹框 我来确认，**其他的听你的**」——即 D7 选 ②，D8/D9 及其余一律按推荐值执行。

| ID | 决策 | 结论 | 依据 / 备注 |
|---|---|---|---|
| D1 | 压缩（H2）默认开还是关 | ✅ **分两步上**：链默认开（H1/H3/H4/H5 立即生效），H2 沿用独立开关、默认关 | V1 唤醒契约实测通过后再开压缩 |
| D2 | G0 怎么织入 | ✅ **立项三问改为 pm 专有弹框**（发起侧换手） | 用户指令原文 |
| D3 | 压缩粒度 | ✅ **整段替换**（复用既有 `IsolateNodeContext`） | 摘要式压缩已在边界中排除 |
| D4 | `promptDifficulty` 接取词 | ✅ **接入**：`simple/standard→light`、`advanced/expert→heavy`，冲突取重 | 对应 NFR-4 |
| D5 | H4 续跑消息粒度 | ✅ **按 H2 结果分流** | H2 成功→只发摘要；H2 跳过/降级→摘要+提示词全文 |
| D6 | REQ 标题更新 | ✅ **保留现标题**，范围以本 PRD 首屏声明为准（看板改题可选） | 看板无 agent 改题工具 |
| D7 | 与 REQ-99f5fe 撞车 | ✅ **② 并入本需求**：REQ-99f5fe 停手，`capture-section.ts` / `QueryState.ts` 的文案改造归 REQ-e3b6a0 | ⚠️ 让它停手只需**取消需求**（`*>canceled` 属代码级仅人，agent 无权调用）。**没有独立的「归档」门**——`accepting>archived` 即「验收通过」这道门的落地动作（通过即自动归档），其后补归档材料（`reqboard_submit(kind=archive)`）由 agent 自主完成、无需人再点；且 `brainstorming → archived` 不是合法边，故归档路径对 REQ-99f5fe 不适用 |
| D8 | 看板一键确认是否"确认即推进 + 触发链" | ✅ **是** | 对应 FR-9；代价：HTTP 路由需注入 agents 投递能力 |
| D9 | 弹框入口合并还是分开 | ✅ **入口分开 / 通道合并 / 链统一** | 对应 FR-10；被否方案：带 mode 的单一弹框工具 |

---

---

## 13. 依据与引用

- 用户原话：本窗口 2026-09-20 首轮 + 升级轮 + 「给我弹框 我来确认，其他的听你的」（见文首引文与 §12）；三问确认值 feature / expert。
- 闸门事实源：`src/domain/artifact/ArtifactSpec.ts:38 ARTIFACT_CONFIRM_GATES`、`:24 STAGE_ARTIFACT_REQUIREMENTS`。
- 压缩实现：`src/application/use-cases/IsolateNodeContext.ts`（三条纪律 / D-12 降级链 / D-15 系统段不可遮蔽）、
  `src/adapters/NodeIsolationAdapter.ts`（surface 原语 + tool 配对边界检查，等价移植 dsh-compaction）、
  `src/application/internal/node-input-package.ts`（INV-9 不读会话历史）、`src/application/internal/isolation-trace.ts`。
- 边界时机与失败隔离：`src/application/internal/node-settlement.ts`（开关默认关、setImmediate 异步边界、永不抛）。
- 取词与留痕：`src/domain/prompt/index.ts:64`（INV-1）、`src/application/internal/injection-log.ts`（INV-6）。
- 投递范式（正确形状）：`packages/lifecycle/src/index.ts:257`、`packages/solve-kit/src/target.ts:24`、`packages/pages/genome/src/routes/genome-routes.ts:161`。
- 看板确认通道：`src/http/routers/requirements.ts:151-175`（`POST /req/artifact/confirm`，只落章）；
  `src/application/use-cases/MoveRequirement.ts:50-92`（门放行判定 + 拒绝时带问题卡）；`src/application/internal/support.ts:158-170`（`gateQuestionCard`）。
- DSH 侧事实：`.dsh-data/profiles/node_modules/@deepseek-ai/dsh-agent/lib/types/index.d.ts`（`AgentRegistry` 无 `followup`）、
  `.../dsh-agent/lib/types/runtime-types.d.ts`（`Agent.followup/send/steer/inject` 四档语义）、
  `.../dsh-tool-ask-user/lib/index.js`（宿主工具直接调 `ctx.userQuestions.ask`）、
  `.../dsh-user-questions/lib/index.js`（`ask()` = `ctx.waterfall(scopeTarget(agent,agent), "user-questions/request", …, noAnswerer)`，
  类型注释明写 **Return an answer to claim the request or call next() to delegate**）、
  `.../dsh-user-questions/lib/types/types.d.ts`（事件声明 `user-questions/request(this: Scoped<Agent>, …)`）、
  `.../dsh-plan-mode/lib/index.js`（`exit_plan_mode` 走同一接缝，intent=plan-review）。
- 根 ctx 监听 Agent 作用域事件的先例：`packages/lifecycle/src/index.ts:424`（`agent/created`）、
  `packages/pages/dsh-pmboard/src/index.ts:267`（`session/event` 全局监听后自行过滤）。
- **G0 发起链（在 pmboard 内）**：`src/adapters/CaptureHook.ts:205-287`（`user/message` → 窗口 unbound 且无 pending → 登记 `pendingCapture`；`:273-277` 的 30min 催办）、
  `src/index.ts:279-295`（`reqboard:capture` 段按窗口求值）、`src/application/internal/capture-section.ts:211-238`（注入文案）、
  `src/application/query/QueryState.ts:63`、`src/tools/CreateTool/prompt.ts`（两问/三问口径不一致的三处）。
- 需求文档 gate 口径（本次踩到）：`reqboard_submit(kind=requirement)` 要求功能编号以 `### FR-1: 名称` 或行首 `- **FR-1: 名称**` 出现
  （`application/internal/doc-parse.ts:52 DEF_LINE_RE=/^\s*(?:[-*+]\s+)?\*\*((?:FR|BUG|RF|SP|DOC|CH)-\d+)\b/`）——表格单元 `| **FR-1** |` 不算。
- 前置能力（作为输入而非重做）：REQ-31e11f（状态转移注入，声明已交付但实为死代码）、REQ-422af1（分片路由 + 节点隔离设计，本需求接手其 t10 开关）、
  REQ-47939a（分层重构）、REQ-9f4a44（验收通过即归档，合并两道门）、REQ-99f5fe（文案改造，按 D7② 并入本需求）。

---

**状态**：brainstorming（待人工确认需求文档 → design）。
**架构风险等级 high**：涉及会话 surface 整段替换与唤醒语义（§6.6 V1），design 阶段第一个任务即为契约实测。
