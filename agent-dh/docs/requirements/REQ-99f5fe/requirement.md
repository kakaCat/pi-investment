---
req_id: REQ-99f5fe
title: 修复 CaptureHook 注入提示词不触发立项弹框
category: refactor
status: brainstorming
owner: w-b5b8ab06
created: 2026-09-20
business_value: 恢复流水线入口（立项门）可用；并把 pm 插件**业务的 hook 机制**（宿主事件 → 业务行为）统一封装成一个可审计的领域，让"行为散在多文件、删不干净、问不出为什么"这类静默故障机械可查
risk_level: medium
---

# REQ-99f5fe 修复 CaptureHook 注入提示词不触发立项弹框（业务 hook 机制聚合成一个领域）

| 项 | 值 |
|----|-----|
| 类型 | refactor |
| 提出 | 用户 |
| 分析 | investor / w-b5b8ab06 |
| 触发实证 | ① 用户原话「CaptureHook 注入的提示词有问题，导致没有让llm 触发创建立项的弹框」；② 用户裁定范围「**业务的 hook 机制统一封装成一个领域**」（不是全量挂载点）；③ 本窗口在已产出多份实施方案的情况下连续多轮讨论**零弹框、零 REQ** |
| 复核时点 | **2026-09-20 七次复核**：①对齐 e3b6a0；②B2–B5 剔除出 hook；③改名 SessionEventIntake；④补流程图；⑤澄清时点订阅 vs 嗅探推断；⑥按入库代码逐行核对补 §1.4 现状逐段解剖（用户：hook 使用比较乱，需仔细梳理）：①对齐 e3b6a0；②B2–B5 剔除出 hook；③改名 SessionEventIntake；④补 §1.3 流程图；⑤按用户问答澄清"闸门为何还有一处 hook"（时点订阅合法 vs 嗅探推断错放），新增 B11 与 timing.turn-end 规则：①对齐 e3b6a0 已上线内容；②B2–B5 剔除出 hook 回归程序路径；③改名（CaptureHook → SessionEventIntake）；④补 §1.3 流程图（事件流 / 七节点矩阵 / 目标架构与闸门链接缝）：①按入库状态（972b2262）对齐 e3b6a0 已上线内容；②按用户裁定把 B2/B3/B4/B5 从 hook 剔除回归程序路径；③按用户裁定改名（CaptureHook → SessionEventIntake，名随职责）：①按入库状态（972b2262）对齐 e3b6a0 已上线内容；②按用户裁定把 B2/B3/B4/B5 从 hook 剔除回归程序路径（CaptureHook 只处理立项）：本文档已按当前入库状态（`972b2262`）重写——写作期间 REQ-e3b6a0 的闸门链与文案硬化**已上线**，旧版中"三处硬伤/半接线/进行中"等描述已过期 |

> **本文档只回答「做什么、为什么」。** 分层、模块接口、迁移工序属「怎么做」，在 design 阶段的
> `design/*.md` 产出（refactor 类型要求 `architecture.md` + `migration.md`）。

> **范围裁定（2026-09-20，用户）**：本需求只收**业务的 hook 机制**——宿主事件到达后**触发业务行为**
> 的那一层；**不收注册型 plumbing**（工具 / 路由 / 服务注入 / 客户端槽位等"注册挂载机制"本身）。

> **与他需求的边界（2026-09-20 二次复核）**：`REQ-e3b6a0`（窗口 w-878da638）的闸门确认后置链
> **已上线并入库**：`domain/gate/GateCatalog`（五道门唯一事实源）+ `application/gate/GatePostChain`
> （H1 校验→H2 压缩→H3 注入→H4 唤醒→H5 审计）+ `adapters/GateAwareQuestions` 装饰器 +
> `CaptureRequirement`（pm 专有立项弹框）+ `AgentDeliverer`（修复了 `agents.followup` 投递形状错误——
> 阶段提示与里程碑催办自诞生起从未投递的根因）。本会话早前误加的 autoContinue 桩已被其删除。
> 本需求**不重复实现**该链，只在边界上对齐核验（见 RF-5）。

---

## 1. 产品定义

**产品**：pmboard 的**业务 hook 领域**——一句话：
**把"宿主事件到达 → 触发业务行为"的判定与动作收成一个领域：判定纯函数化、动作单点化、过程可查、接线可门禁。**

**为什么现在做（实证触发，不是"应该做"）**：
① 用户报告注入文案失效（本窗口 15+ 轮方案讨论零弹框）；② 业务 hook 的**判定与动作仍分处两个文件**
（`CaptureHook.ts` 判定 + `index.ts` 闭包动作），且闸门链上线后闭包增至 6 处；③ 本会话出现过
悬空接线（5 个 tsc 错误）与半接线（测试绿但运行时永不触发）两类静默故障，**目前均无门禁防复发**；
④ "hook 到底会做哪些事"没有任何一处可答。

### 1.1 "业务的 hook 机制"清单（本需求的范围；2026-09-20 二次复核后的现状）

业务的 hook = 宿主事件到达后**触发业务行为**的那一层：

**A 类 · 真正需要 hook 的（没有程序点，事件驱动是本
质）**：

| # | 业务行为 | 触发事件 | 为什么必须是 hook |
|---|---------|---------|------------------|
| B1 | 立项捕获登记 | `user/message`（未绑定窗口） | 用户对窗口说话但还没调任何工具——这个时机只有事件监听能拿到 |
| B6 | 待捕获清除 | `turn/end` | B1 的配套簿记 |
| B7 | 工具痕迹跟踪（done 凭证门） | `tool/call`（非忽略会话） | 工具调用由宿主发起，插件内没有程序点 |
| B8 | 近期用户消息缓冲（证据核验） | `user/message`（清洗后非空） | 证据核验需要消息流，事件驱动 |
| B9 | 捕获引导段注入 | systemPrompt 组装 | 渲染时机点，本就是注入钩子 |
| B11 | **回合收尾时机订阅**（结算分发 + 闸门链 runPending） | `turn/end` | **订阅框架的确定生命周期时点**——Phase B 必须等本回合台账写入落定才能跑（作答与推进隔着用例后半段；作答可能来自看板无调用栈；D-17 禁监听器内会话写）。无语义推断，与 B 类错放有本质区别 |

**B 类 · 错放进 hook 的（有明确业务程序点，应回归程序路径）**：

| # | 业务行为 | 正确的程序点 | 现状与证据 |
|---|---------|-------------|-----------|
| B2 | 承接推进（draft → brainstorming） | 创建/迁移时推进 | **程序路径已存在**：`CaptureRequirement` 创建时 inline 推进（`advanceDraftToBrainstorming`）；hook 嗅探只剩遗留 draft 兜底 |
| B3 | 阶段纪律提示词注入 | 迁移发生处注入 | **闸门路径已由链 H3 覆盖**（时序正确）；而 `reqboard_move` / rollup / 验收打回三条迁移路径实测**全不注入**（grep `resolveStagePrompt\|deliver` 0 命中），只能靠 hook 嗅探兜底 |
| B4 | 里程碑超时提醒 | 定时检查 / 闸门链 handler | 仍在 CaptureHook 借消息时机顺带检查（`milestoneReminderFor`），未进闸门链 |
| B5 | 节点结算 → 上下文隔离 | 随 B3 的迁移路径 | 登记挂在 B3 的 hook 路径上；闸门路径的压缩已由链 H2 覆盖 |
| B10 | 闸门确认后置链 | 弹框作答（程序点已就位） | **REQ-e3b6a0 已上线**（`application/gate/`），本需求只对齐核验（RF-5），不重建 |

> B 类的存在证明了一个比"散落两处"更深的病：**每次要加"状态变化后该做的事"，都图省事挂到消息嗅探上，
> 而不是在业务程序点上做**。CaptureHook 名字是"立项捕获"，实际已长成推进/注入/催办/隔离的杂物筐。

**明确不收（注册型 plumbing，不是业务 hook，本轮一律不动）**：

- 工具注册（`tools.register`）、HTTP 路由注册（`webServer.register`）、服务惰性注入（`ctx.inject`）；
- systemPrompt 段的**注册机制**本身（B9 收的是"注入什么内容"的判定，不是"怎么注册段"）；
- 手工 `disposers.push`、SSE 推送通道、工具 `render` 展示回调；
- 客户端全部挂载（slots / 自定义事件 / 定时器 / 样式注入 / `window.__*` / sessionStorage / page-kit 壳）；
- 台账订阅管道（`repo.subscribe`）的机制本身。

> 理由：这些是"怎么向宿主注册"的基础设施，不是"事件到了做什么业务动作"。混进来会让领域变成
> "插件全量重构"，范围失控。若以后要治理注册面，另立需求。

### 1.2 交付物清单

| # | 交付物 | 是什么 | 谁消费 |
|---|--------|--------|--------|
| 1 | 注入文案**剩余缺口补齐** | 在 e3b6a0 已硬化的文案上，补"已产出方案后追问 = 立项信号"缺口，并 E2E 验证触发率 | 窗口 agent（LLM） |
| 2 | **业务 hook 领域** | 规则类型 / 规则表（A 类 B1/B6/B7/B8/B9 判定集中）/ 跑批器 / 单一动作出口；另含 B 类四条程序行为回归程序路径（RF-9） | 维护者；窗口 agent（间接受益） |
| 3 | hook 决策留痕 + 只读查询 | 每条规则命中/跳过及原因、动作、耗时；有界 ring buffer + 只读入口 | 排障的人；看板 |
| 4 | 业务 hook 门禁 | 规则声明与注册一致 / 禁止项不可复活 / 假绿可判红 | CI 与回归 |

### 1.3 流程图：hook 在哪些节点起什么作用

**图 1 · 一次会话回合内的事件流与 hook 作用点（目标态）**

```
user/message 事件到达
  │
  ▼
门闩（纯函数，共用）：忽略会话？ 非直接人类？ 清洗后为空？ —— 任一命中即丢弃
  │
  ├─ B8 证据缓冲：记录真实用户消息（供文字确认核验，防 agent 伪造"用户同意了"）
  │
  ├─ 窗口未绑定？──是──► B1 立项捕获登记（pendingCapture）
  │                         └─► 下回合 systemPrompt 组装时 B9 注入立项引导
  │                               └─► LLM 显式裁定 → 值得立项 → 本回合首个工具调用
  │                                     reqboard_capture（pm 弹框，程序路径接管）
  │
  │   窗口已绑定？──是──► 【B2/B3/B4 已移出 hook，回归程序路径（RF-9）】
  │                         B2 承接推进 → 程序点：CaptureRequirement 创建时 inline 推进
  │                         B3 阶段注入 → 程序点：迁移用例 / 闸门链 H3（闸门路径已覆盖）
  │                         B4 超时催办 → 程序点：定时检查或链 handler（design 定案）
  │
  └─ 并行：tool/call 事件 ──► B7 工具痕迹跟踪（done 凭证门判定"开工以来有无干活"）

turn/end 事件到达
  ├─ B6 清除待捕获登记（防跨回合重复 nag）
  ├─ 【B5 节点结算：随 B3 移出 hook（RF-9）；闸门路径压缩已由链 H2 覆盖】
  └─ 闸门链 runPending（REQ-e3b6a0，B10，本需求不重建）
```

**图 2 · 流水线七节点 × hook 作用矩阵（目标态）**

```
 立项       需求分析        设计          拆分           实施           验收           归档
 draft → brainstorming → design → decomposing → implementing → accepting → archived
   │            │            │           │             │             │             │
 B1+B9       闸门 G1       闸门 G2     闸门 G3       B7 工具痕迹     闸门 G4        —
 hook 检测    确认需求文档   批准拆分计划  确认拆分清单   （done 凭证门）  逐项裁决        （无 hook）
 意图→弹框    │            │           │             │             + 归档拍板
              ▼            ▼           ▼             ▼             ▼
              └────── 闸门链（e3b6a0 · B10 · 程序路径，本需求不重建）──────┘
                     H1 推进 → H2 压缩 → H3 注入 → H4 唤醒 → H5 审计

 全程贯穿：B8 证据缓冲（hook · user/message）
```

| 流水线节点 | hook 做什么 | 载体 |
|-----------|------------|------|
| 立项（draft） | 检测工作意图 → 注入引导 → 弹三问 | B1+B9（hook）→ `reqboard_capture`（程序） |
| 需求分析（brainstorming） | 确认需求文档（G1）后的推进/压缩/注入/唤醒/审计 | 闸门链（程序） |
| 设计（design） | 批准拆分计划（G2）后的同上 | 闸门链（程序） |
| 拆分（decomposing） | 确认拆分清单（G3）后的同上 | 闸门链（程序） |
| 实施（implementing） | 工具痕迹跟踪（支撑 done 凭证门） | B7（hook · tool/call） |
| 验收（accepting） | 逐项裁决 + 归档拍板（G4）；多批续跑核验 | 闸门链 + AcceptSheet（程序） |
| 归档（archived） | 无 | — |
| 全程 | 用户消息证据缓冲（文字确认防伪造） | B8（hook · user/message） |

**图 3 · 目标架构：统一入口 + 规则路由 + 单一出口（与闸门链的接缝）**

```
session/event ──► SessionEventIntake（薄：采集 + 规范化为 HookEvent）
                      │
                      ▼
              runner 跑批 HOOK_RULES（路由表，5 条，每条 = 一行）
                ├─ capture.pending-register   user/message · 未绑定
                ├─ capture.clear              turn/end · 恒真
                ├─ evidence.buffer            user/message · 有文本
                ├─ trace.tool-call            tool/call · 非忽略会话
                ├─ prompt.capture-section     systemPrompt 组装
                └─ timing.turn-end            turn/end · 恒真 → 结算分发 + 闸门链收尾
                      │ 每条命中产出 HookAction[]（意图，非副作用）
                      ▼
              applyActions（单一动作出口：台账写 / 投递 / 调度 / 留痕）
                      │
                      ▼ 每条规则落 hook_decisions（命中/跳过/原因/耗时）

闸门作答 ──► GateAwareQuestions（e3b6a0 装饰器，声明 gate=G#）
                      │
                      ▼
              GatePostChain（H1→H5 责任链，已上线，本需求不重建）
              —— 与 hook 领域的接缝：弹框作答事件由装饰器登记进链，
                 路由表不重复承载（RF-2 AC2 锁死规则表长度 = 5）
```

> 模式定位：**本领域是 Dispatcher**（一个事件来了，哪些行为要响应——并行、独立、可多中）；
> **闸门链是责任链**（一件确认完成后，按序做后续——串行、有序、有依赖）。两者互补不重叠。

> **问：闸门既是程序路径，为何还挂着一处 hook（turn/end → runPending）？**
> 答：闸门的业务动作不靠 hook（作答 → 用例内联落章推进）。但链的 Phase B（压缩/注入/唤醒）
> 必须等"本回合台账写入落定"后才能跑（H1 要校验推进结果；作答可能来自看板无调用栈；D-17 禁
> 监听器内会话写）——这个**执行时机**由 turn/end 时点订阅提供。这是 hook 的合法用法：
> **订阅框架的确定时点来调度程序模块**，与 B2–B4 的错放（用 user/message **推断**业务事件）有
> 本质区别。路由化后它是路由表里的 `timing.turn-end` 规则（match 恒真，act = 结算分发 +
> 链收尾的意图，执行层再映射到闸门链）。

### 1.4 现状逐段解剖（按事件源，2026-09-20 按入库代码逐行核对）

**事件源 ① `session/event` · `user/message`**（CaptureHook.ts:224-307）

| 顺序 | 路径 | 判定位置 | 动作位置 | 分类 | 证据 |
|------|------|---------|---------|------|------|
| 1 | 门闩：忽略会话 / 非 direct human / 清洗后为空 | CaptureHook.ts:227-246 | —（丢弃） | 合法·共用门闩 | L228 / L235 / L243 |
| 2 | B8 证据缓冲 | CaptureHook.ts:250-252 | `SessionProbeAdapter.recordRecentUserMsg` | 合法·事件驱动 | 消费方：ConfirmArtifact.ts:41（防伪造核验） |
| 3 | B1 立项捕获登记（unbound） | CaptureHook.ts:303-307 | `pendingCapture` Map → capture-section 注入 | 合法·事件驱动（无更早程序点） | capture-section.ts |
| 4 | B2 承接推进（bound） | CaptureHook.ts:259-260 | `index.ts:275-284` 闭包 → `applyPickupAdvance` | **错放** | 程序点已存在：CaptureRequirement.ts:57 inline 推进 |
| 5 | B3 阶段提示注入（bound） | CaptureHook.ts:266-275 | `index.ts:289-296` 闭包 → `AgentDeliverer` | **错放** | 链 H3 已覆盖闸门路径；move/rollup/verdicts 三路径 0 注入 |
| 6 | B3' 节点结算登记（**藏在 B3 分支内**） | CaptureHook.ts:280-287 | `pendingSettlements` Map | **错放·耦合** | 不注入就不登记——两个目的耦在一个 if 里 |
| 7 | B4 里程碑催办（bound） | CaptureHook.ts:293-298 | 同 B3 闭包 → `AgentDeliverer` | **错放** | 触发是"时间到了"，借消息时机顺带检查 |

**事件源 ② `session/event` · `tool/call`**（CaptureHook.ts:186-192）

| 路径 | 判定位置 | 动作位置 | 分类 | 证据 |
|------|---------|---------|------|------|
| B7 工具痕迹跟踪 | CaptureHook.ts:186-191 | `SessionProbeAdapter.recordToolTrace` | 合法·事件驱动（工具调用由宿主发起，插件内无程序点） | 消费方：support.ts:102 done 凭证门 |

**事件源 ③ `session/event` · `turn/end`**（CaptureHook.ts:196-221）

| 路径 | 判定位置 | 动作位置 | 分类 | 证据 |
|------|---------|---------|------|------|
| B6 清待捕获 + 存活留痕 | CaptureHook.ts:201-208 | `pending` Map | 合法（B1 簿记配套） | e3b6a0 t-3e11bf 加的存活时长留痕 |
| B5 结算分发 | CaptureHook.ts:211-217 | `onNodeSettled` → node-settlement 异步隔离 | 时点订阅合法；**但登记来源是错放的 B3'（联动错放）** | D-17：监听器内禁会话写 |
| 闸门链收尾 | CaptureHook.ts:220 | `onTurnEnd` → `setImmediate` → `gateChain.runPending` | 合法·时点订阅 | e3b6a0 t7 |

**事件源 ④ systemPrompt 组装**（`index.ts` 段注册）

| 路径 | 判定位置 | 动作位置 | 分类 |
|------|---------|---------|------|
| B9 捕获引导段（unbound）/ 推进纪律段（bound） | capture-section.ts（窗口状态判定） | 渲染返回值 | 合法·渲染钩子 |

**事件源 ⑤ 弹框作答返回**（`UserQuestionPort.ask`）

| 路径 | 判定位置 | 动作位置 | 分类 |
|------|---------|---------|------|
| B10 闸门登记 → Phase B（推进/压缩/注入/唤醒/审计） | GateAwareQuestions（装饰器） | GatePostChain.enqueue → 责任链 | 合法·程序点（REQ-e3b6a0 已上线） |

**数据管道（不是业务 hook，本轮不收）**：`repo.subscribe` → SSE（stages.ts:65-72）→ `EventSource`（client/api.ts:212）→ 看板刷新。

**"乱"的七处具体表现（每条有行号证据）**：

1. **一名多职**：CaptureHook 名为立项捕获，实际装 8 种行为（B1–B8）；
2. **判定与动作分居**：判定在 `CaptureHook.ts`，动作在 `index.ts` 闭包（5 个回调 + gateChain 装配块）；
3. **合法与错放混居**：B1/B7/B8 是 hook 本职，B2/B3/B4 是程序行为错放——同一函数里两类语义；
4. **同一目的三条路径**：阶段纪律提示词有三条触发路径——B9（每回合组装）/ B3（hook 嗅探）/ 链 H3（闸门后），口径各自演化，随时漂移；
5. **时序耦合**：B5 结算登记藏在 B3 注入分支里（CaptureHook.ts:280-287——不注入就不登记）；
6. **投递链曾整体静默死**：`agents.followup` 形状错误致阶段提示与催办从未投递（e3b6a0 已修 `AgentDeliverer`）；
7. **无决策留痕**：每条消息走了哪些分支、为什么跳过，无处可查。

---

## 2. 用户与角色

| 角色 | 是谁 | 他要什么 | 今天被什么卡住 |
|------|------|----------|---------------|
| **用户（需求方 / 验收人）** | 提出工作意图的人 | 说出"要做什么"后**立刻**被弹框确认立项 | 硬化前的文案被判为"继续之前话题" → 全程无弹框（实测 15+ 轮 0 次）；硬化后的效果尚未 E2E 验证 |
| **执行窗口（agent）** | 承接需求的 agent 窗口 | 在正确时点得到**明确指令** | 旧文案建议句 + 豁免过宽 + 「两问 vs 三问」矛盾（已被 e3b6a0 修复大部）；但"方案讨论期的追问"仍被列为不立项示例 |
| **接手窗口 / 未来的自己** | 中途接手或半年后回看 | 一眼看清"hook 会做哪些事、这次为什么没触发" | 判定在 `CaptureHook.ts`、动作散在 `index.ts` 6 处闭包/装配块；无决策日志 → 只能读代码倒推 |
| **维护者（改 hook 的人）** | 后续改 hook 的窗口 | 加/删一条业务 hook 只改**一处** | 加一条要同时改两个文件；删一条删不干净（本会话实测残留致 tsc 5 错，已清但**无门禁防复发**） |

---

## 3. 目标与度量（今天值 = 2026-09-20 二次复核实测）

| 目标 | 度量口径 | 今天（实测） | 目标值 |
|------|---------|-------------|--------|
| **立项门触发率** | 进入"已产出方案或含改动意图"的会话中，弹出立项确认框的比例 | **硬化前 0%**（本窗口 15+ 轮 0 次）；硬化后未经 E2E 验证 | **100%（E2E 实测）** |
| **判定收敛度** | 事件型 hook 判定代码所在文件数 | **2**（`CaptureHook.ts` + `index.ts`） | **1**（单一领域目录） |
| **动作收敛度** | `index.ts` 中承载 hook 动作的闭包/装配块数 | **6**（4 个 CaptureHookDeps 闭包 + gateChain 装配 + onTurnEnd） | **1**（单一动作出口） |
| **错放程序行为数** | 在消息嗅探 hook 里的程序行为数（§1.1 B 类） | **4**（B2/B3/B4/B5） | **0**（全部回归程序路径） |
| **行为可见度** | 能由一份规则表回答"hook 会做什么"的事件型行为比例 | **0/6**（无表，要通读代码） | **6/6**（B1/B6/B7/B8/B9/B11 全部登记） |
| **悬空接线** | hook 相关的 `tsc` 报错数 | **0**（本会话已清），但**无门禁防复发** | **0 + 门禁固化** |
| **可观测率** | 能由决策日志回答"为什么没触发"的 hook 决策占比 | **0%** | **100%** |
| **回归不变** | 既有 hook 回归通过用例数 | **50**（capture 系列，e3b6a0 硬化后实测） | **≥50** |

---

## 4. 要解决的问题

### P1 注入文案的剩余缺口（主体已被 REQ-e3b6a0 修复，本节只列剩余）

**已修复（e3b6a0，已入库，勿重复做）**：
- 文案已指令化：「**本回合你必须先做一次显式裁定、再回答用户**——沉默跳过等于本回合未完成（会被留痕，走查时按失败计）」；
- 判不准 → 按值得立项处理（="拿不准默认弹框"原则）；
- 立项动作指向 pm 专有弹框 `reqboard_capture`（一次调用完成三问 + 创建 + 绑定 + 推进）；
- 「两问 vs 三问」矛盾已消除（统一为三问）。

**剩余缺口（本需求负责）**：
- **现象**：现文案仍把「继续之前话题」列为**不立项**示例（`capture-section.ts`）。
- **证据**：本窗口的零弹框恰恰发生在"方案讨论期的追问"场景——agent 已产出实施方案，用户追问方案细节/让 agent 继续，**这正是"继续之前话题"**，但此时恰恰该立项。硬化前的 15+ 轮讨论即属此类。
- **根因**："继续之前话题"这个豁免把"纯闲聊式继续"与"方案收敛后的推进意图"混为一谈，缺一个正向锚点：**已产出方案后，用户对方案的任何回应都是立项信号**。
- **影响**：硬化后仍可能在该场景漏弹；且无人验证硬化后触发率是否达标（无 E2E 证据）。

### P2 程序行为被错放进消息嗅探 hook（比"散落两处"更深一层）

**现象**：B2（承接推进）、B3（阶段提示注入）、B4（超时提醒）、B5（节点隔离）四条**有明确业务程序点**的行为，
被放进 CaptureHook 靠嗅探 `user/message` 触发；且判定在 `CaptureHook.ts`、动作在 `index.ts` 闭包
（闸门链上线后动作面增至 6 处：4 个 CaptureHookDeps 闭包 + gateChain 装配块 + onTurnEnd）。
**证据**：
- B2：`CaptureRequirement` 已 inline 推进（`advanceDraftToBrainstorming`），hook 路径只兜遗留 draft；
- B3：闸门链 H3 已按正确时序注入；而 `reqboard_move` / rollup / verdicts 三条路径实测不注入
  （grep `resolveStagePrompt\|deliver` 0 命中）；
- B4：`CaptureHook.ts:296` 仍在消息事件里顺带检查超时；
- B5：登记挂在 B3 的 hook 路径（`CaptureHook.ts:280` 附近）。
**根因**：每次要加"状态变化后该做的事"，都挂到消息嗅探上，而不是在业务程序点上做。
**影响**：时机错位（消息不来就不触发/晚触发）、语义错位（CaptureHook 名不副实）、行为发散加速
（新面还在向组合根堆闭包）。逐段解剖与行号证据见 §1.4。

### P3 悬空接线已清但无门禁防复发

**现象**：本会话曾发现 `index.ts` 残留 `onAskUserQuestionAnswered`（`CaptureHookDeps` 未声明），
`tsc` 报 5 个错误，且该残留正是用户明令禁止的能力。
**现状**：残留已删（本会话），tsc 当前 0 错误。
**根因（未解决）**：没有"声明—注册"一致性门禁；这次是靠类型错误**碰巧**暴露（若字段可选则完全静默）。
**影响**：同类残留随时会再出现；需要门禁而非运气。

### P4 半接线已被删除，教训需门禁固化

**现象**：本会话早前误加的"自动继续"桩曾半接线（端口声明与适配器实现存在、用例与组合根未接线，
运行时永不触发，而单测 6/6 绿）。
**现状**：该桩已被 REQ-e3b6a0 t7 删除并替换为 gate 链（`GateAwareQuestions` 装饰器织入）。
**根因（未解决）**：单测直接 `new` 适配器注入回调、**绕过组合根**，造成"源码级测试绿 ≠ 线上生效"。
**影响**：没有门禁的话，下一处"声明了没人接"还会出现。

### P5 不可观测

**现象**：被问"为什么没触发"时，系统内没有任何地方能回答。
**证据**：本次排查只能靠"读代码 + 在自身系统提示词里碰巧看到注入文本"倒推，耗时整个会话。
**根因**：hook 执行过程无留痕（对比：阶段提示词注入有 `injection_log`，闸门链有 H5 审计留痕，
但"每次宿主事件 → 哪些规则命中/跳过/为什么"没有对应物）。
**影响**：每次排查从零开始；硬化后触发率是否提升无法回归验证。

---

## 5. 用户场景

| 场景 | 要写清楚的内容 |
|------|---------------|
| **正常流程** | 用户发出工作意图 → hook 登记待捕获 → 注入文案指向该消息 → LLM **本回合先显式裁定** → 值得立项则第一个工具调用 `reqboard_capture` → 用户作答即创建+绑定+推进 → 闸门链 Phase B 接管（压缩/注入/唤醒/审计） |
| **今天翻车的地方** | ① "方案讨论期的追问"被判为"继续之前话题" → 不弹框（P1 剩余缺口）；② 想知道"hook 会做哪些事"只能通读两个文件（P2）；③ 排障问"为什么没触发"无人能答（P5）；④ 删一条 hook 删不干净且无门禁（P3/P4） |
| **验收** | 验收人：① 发一条"方案就这么做"类追问，观察是否**本回合弹立项框**（E2E）；② 查 hook 决策日志能回答触发与否及原因；③ 查规则表能列出 B1–B9 全部行为；④ 故意造悬空接线，确认门禁变红 |
| **复盘 / 换人接手** | 半年后或换窗口：① 本文档 + `design/*.md` 给出"为什么这样聚合"；② **规则表一行一条行为**，一眼看清 hook 全貌；③ 决策日志可回放某次事件命中了哪些规则 |

---

## 6. 重构条款（RF-#）

### RF-1: 注入文案剩余缺口补齐与硬化验证（本需求唯一显式行为变更）

在 REQ-e3b6a0 已硬化的文案（显式裁定 / 判不准按值得立项 / 指向 `reqboard_capture` / 三问统一）之上，
补齐最后一个语义缺口并验证效果。**不与已硬化部分冲突，不重写已修内容。**

- AC1：现状断言（防回退）：`capture-section.ts` 渲染结果**包含**「必须」「显式裁定」「reqboard_capture」，
  **不包含**「两问」；`npx vitest run tests/capture.test.ts` 通过。
- AC2：缺口补齐：文案含「已产出方案后，用户对方案的任何回应（追问/确认/继续）都是立项信号」分句，
  且「继续之前话题」**不再**作为不立项示例出现（改为"纯闲聊式继续"之类不覆盖方案场景的表述）。
- AC3：E2E 真机：在已产出方案的窗口发"方案就这么做/这个方案再改改"类追问 → **本回合弹出立项框**
  （留真机证据：截图或决策日志）。
- AC4：不破坏既有回归：`capture.test.ts` / `capture-hook.test.ts` 全绿，既有断言逐条不改。

### RF-2: 事件型业务 hook 聚合成单一领域（含重命名）

B1/B6/B7/B8/B9 五条**真正事件驱动**的行为（无程序点，见 §1.1 A 类）收进**一个领域目录**：
规则类型、规则表、跑批器、单一动作出口；`index.ts` 不再持有散落闭包。

**重命名（用户裁定：名字必须符合设计）**——`CaptureHook` 早已不只是"立项捕获"，
名实错位正是 P2 的表征。命名随职责走：

| 现状 | 新名 | 职责 |
|------|------|------|
| `adapters/CaptureHook.ts` | `adapters/SessionEventIntake.ts` | **唯一入口**：接收 `session/event` → 规范化 HookEvent → 调跑批器 → 执行动作意图 |
| `createSessionEventCaptureHook` / `CaptureHookDeps` | `createSessionEventIntake` / `SessionEventIntakeDeps` | 同上 |
| （无） | `application/internal/hook/`（领域目录） | `types.ts`（HookEvent / HookRule / HookAction / HookDecision）+ `rules.ts`（一行为一条规则）+ `registry.ts`（HOOK_RULES 唯一事实源 / 路由表）+ `runner.ts`（跑批器） |
| 规则命名空间 | `capture.*` / `evidence.*` / `trace.*` | "立项捕获"只是规则表里的一个命名空间，不再占据整个模块名 |
| 日志 tag `reqboard-capture` | `reqboard-hook` | 同步 |

**保留不改名的**：`capture-section.ts`（它真的只做立项捕获引导，名实相符）。

- AC1：组合根清零：`grep -rn "onBoundWindowActivity\|onStagePrompt\|onNodeSettled\|onTurnEnd" src/index.ts` **无命中**。
- AC2：改名完成：`grep -rn "CaptureHook" src/ tests/` **无命中**（`capture-section.ts` 与 `capture.*` 规则命名空间除外——名实相符者保留）。
- AC3：规则表长度 = 5（B1/B6/B7/B8/B9 全部登记），且每条规则 id 带命名空间前缀。
- AC4：`grep -rln "shouldCaptureWindow" src/adapters/SessionEventIntake.ts` **无命中**（判定已迁入领域）。
- AC5：每条规则的判定是纯函数：可单独单测，不依赖 `ctx` / 网络 / fs。
- AC6：改名与搬迁不夹带行为变化：capture 系列回归既有断言逐条不动（测试文件只允许 import 行跟随改名）。

### RF-3: 新增 hook 不改组合根

新增一条业务 hook 只允许改"规则表 + 测试"两处；`src/index.ts` 不因新增行为而改动。

- AC1：一次演示提交中 `git diff --stat src/index.ts` 对该新增**为空**，而规则表文件有改动。
- AC2：新增条目后相应单测通过（证明无需额外接线）。

### RF-4: 悬空接线与禁止项门禁固化

- AC1：`npx tsc --noEmit -p tsconfig.json` 对 hook 相关代码保持 **0 错误**，且新增门禁使其不可回潮。
- AC2：往组合根故意加回一个未声明的回调字段 → 门禁测试**失败**。
- AC3：禁止项断言：任何 hook/续跑机制的白名单**不包含** `ask_user_question`（用户裁定）。

### RF-5: 闸门作答后置核验（对齐 REQ-e3b6a0，不重建）

核验已上线的 `GatePostChain` 覆盖"弹框作答后该做的全部事项"，本需求只补缺口、不另建机制。

- AC1：`grep -rn "autoContinue\|onAnswered" src/` **无命中**（旧桩不得复活）。
- AC2：核验 `reqboard_accept_sheet` 多批续跑：验收项数 > `batch_size` 时，作答后由链唤醒并
  自动发起下一批直至 `pending = 0`；若不覆盖，**在链上补 handler**（不绕开链另造机制）。
- AC3：反向证明：对 `reqboard_ask_confirm`（范式①内联完成）作答后，断言**没有**注入多余"继续"
  消息（防双重推进；`grep -c "autoContinue" src/application/use-cases/AskConfirm.ts` = 0 恒成立）。

### RF-6: hook 决策留痕与只读查询

每次宿主事件经领域跑批后留下决策记录（规则 id / 事件 / 窗口 / verdict / 原因 / 动作 / 耗时），
提供有界 ring buffer（容量上限常量）与只读查询入口。

- AC1：跑一次规则，决策记录含 `ruleId` / `verdict` / `event` / `windowKey` 四字段。
- AC2：写入超过容量上限后，记录条数 **= 容量上限**（有界）。
- AC3：只读查询能按窗口过滤，返回命中与跳过记录。
- AC4：与既有 `injection_log` / 闸门链 H5 审计**不重复**：决策日志记录的是"规则是否命中"，
  而非"注入了什么内容"或"闸门推进结果"。

### RF-7: 接线门禁 G1–G5 落地且可故障注入

- AC1：门禁测试含 G1–G5 五组断言，`npx vitest run` 全绿。
- AC2：故障注入：临时注入悬空接线 → G1 红；临时让规则表与注册不一致 → G2 红；
  临时把 `ask_user_question` 加入续跑白名单 → G5 红（逐一验证后还原）。

### RF-8: 既有 hook 行为不变式

- AC1：`npx vitest run tests/capture.test.ts tests/capture-hook.test.ts tests/isolate-node-context.test.ts`
  **全绿**（当前 50 条基线），且这三个文件的既有断言**逐条未被修改**（`git diff` 对它们为空；
  新业务行为差异只允许以新增测试的形式出现）。
- AC2：领域目录内无 `node:` / `@deepseek-ai/*` / `fs` 导入（`layer-boundary` 门禁通过）。
- AC3：判定函数不调用 `Date.now()`（`grep` 无命中），时间一律经参数注入。

---

### RF-9: 错放进 hook 的程序行为回归程序路径

B2/B3/B4/B5 从消息嗅探中取出，挂到各自的业务程序点（用户裁定：CaptureHook 只处理立项）：

- **B2 承接推进**：以 `CaptureRequirement` 的 inline 推进为准；其余创建路径统一走同一推进点；
  hook 兜底删除或降级为一次性迁移。
- **B3 阶段提示注入**：`reqboard_move` / rollup / 验收打回三条迁移路径在用例内直接触发注入
  （或登记进闸门链），不再靠 hook 嗅探兜底。
- **B4 里程碑提醒**：改为定时检查或闸门链 handler，不再借消息时机顺带检查。
- **B5 节点隔离**：结算的**判定与登记**随 B3 回归程序路径；`turn/end` 的**分发时机**保留为领域的
  `timing.turn-end` 规则（B11，时点订阅合法）；闸门路径已由链 H2 覆盖的部分不重复。

- AC1：`grep -c "milestoneReminderFor" src/adapters/CaptureHook.ts` = 0（催办迁出）。
- AC2：`grep -c "onBoundWindowActivity" src/adapters/CaptureHook.ts` = 0（承接推进迁出）。
- AC3：三条非闸门迁移路径（reqboard_move / rollup / verdicts）迁移后**都有**阶段提示注入证据
  （每路径 grep `resolveStagePrompt\|injectionLog\|chain` ≥1 命中）。
- AC4：回归不变：capture 系列 + rollup/verdicts 相关测试全绿（新行为以新测试承载，不改既有断言）。

---

## 7. 行为不变式（refactor 必填）

| # | 不变式 | 判定方式 |
|---|--------|---------|
| INV-1 | 既有 hook 行为的可观测结果不变 | capture 系列回归（当前 50 条基线）逐条不变且全绿 |
| INV-2 | 判定层纯函数：禁 `node:` / `@deepseek-ai/*` / `fs`，禁 `Date.now()` | `layer-boundary` 门禁 + 规则单测（注入 now） |
| INV-3 | 监听器内不做会话写操作（D-17） | 动作用途经异步边界；沿用 `node-settlement` 与闸门链的可注入 `schedule` |
| INV-4 | 失败隔离：任一规则抛错只告警，不打断其他规则与流水线 | 故障注入单测 |
| INV-5 | `ask_user_question` 永不进入任何续跑/自动继续白名单 | 门禁 G5 |
| INV-6 | 搬迁不夹带改行为 | 纯搬迁步的回归逐条不变 |
| INV-7 | **不叠加续跑**：范式①（同步内联完成）的弹框不得叠加异步注入续跑 | 门禁：`AskConfirm.ts` 的 `autoContinue` 命中数恒为 0；端到端断言无多余 followup |
| INV-8 | **不重写已硬化内容**：REQ-e3b6a0 已上线的闸门链与文案硬化不被本需求重写 | 迁移期间 `git diff` 对 `domain/gate/` `application/gate/` `GateAwareQuestions.ts` 为空（对齐修改除外，且须注明） |

---

## 8. 非功能需求

| 项 | 要求 |
|----|------|
| 向后兼容 | 迁移期间不改变 hook 对外可观测行为；`CaptureHookDeps` 既有字段在迁移步内保持可用 |
| 不改动什么 | 不改需求状态机与人工闸门语义；不改 token / 提示词分片口径；不改 `userQuestions` 服务本身；**客户端一行不动**；**不重写 REQ-e3b6a0 已上线的闸门链** |
| 可回滚 | 分步迁移，每步独立 revert；任一步回归变红即停并回退该步 |
| 规模 / 性能 | hook 全程同步无网络；判定复杂度 O(规则数 × 台账规模)；决策日志 ring buffer 有界 |

---

## 9. 边界（本轮不做）

- ❌ **注册型 plumbing 一律不动**：工具注册 / HTTP 路由注册 / 服务惰性注入 / systemPrompt 段注册机制 /
  `disposers` 清理机制 / SSE 通道 / 工具 render 回调 / 台账订阅管道（见 §1.1 不收清单）；
- ❌ **客户端一行不动**（slots / 事件 / 定时器 / 样式 / 全局挂载 / 持久化 / page-kit 壳）；
- ❌ 不重建闸门后置链（REQ-e3b6a0 已上线，本需求只核验对齐）；
- ❌ 不重写注入文案的已硬化部分（显式裁定 / 三问 / reqboard_capture 指向，e3b6a0 已做）；
- ❌ 不引入任务依赖调度器 / DAG（另立需求）；
- ❌ 不回填、不伪造历史台账数据；
- ❌ 不把"验证文档存在"当作"功能已接线"。

---

## 10. 优先级与版本切分

| 版本 | 内容 | 理由 |
|------|------|------|
| **MVP（必须先上）** | RF-1（文案剩余缺口 + E2E 验证）+ **RF-9（错放行为回归程序路径）** + RF-2/RF-3（领域聚合与单点出口）+ RF-8（不变式） | 没有 RF-1，硬化后的立项门在"方案追问"场景仍会漏；RF-9 是用户裁定的正确边界（CaptureHook 只处理立项）；RF-2/3 在 RF-9 收敛后才有稳定地基 |
| V2 | RF-5（闸门链核验）+ RF-6（决策留痕） | 依赖 MVP 的单一动作出口；留痕是"可回归证明触发率"的前提 |
| V3 | RF-4 + RF-7（门禁） | 门禁在行为稳定后固化，否则会锁死错误的形状 |

**实施前置**：拆分计划**经人工批准**；`design/architecture.md` 与 `design/migration.md` 已产出；
§14 的 [TBD] 清零。

---

## 11. 测试策略

| 层级 | 用例数 | 覆盖路径 | 不覆盖（显式） |
|------|--------|----------|----------------|
| 单元 | ≥10 | 每条规则的命中 / 不命中 / 异常隔离；文案渲染断言；决策日志边界 | 不测真实会话与网络 |
| 集成 | ≥6 | 规则表 + 跑批器 + 单一动作出口（注入替身端口） | 不测跨进程/跨服务 |
| E2E | ≥3 | ① "方案追问"消息 → 本回合弹立项框（真机）；② `user/message` → 决策日志出现预期 verdict；③ 故障注入使 G1/G2/G5 变红 | 不测 DSH 框架本身与弹框 UI 渲染细节 |

**要求**：必须有 E2E（真实触发链）；每层写明"不覆盖什么"。

---

## 12. 迁移与回滚（refactor 必填）

- **分步迁移**，每步独立可验证、独立可回滚（单步 revert 不牵连其他步）；
- 顺序：RF-1 文案剩余缺口（小步先行，E2E 验证）→ **RF-9 错放行为回归程序路径（先收窄 CaptureHook 职责）** →
  **改名 CaptureHook → SessionEventIntake**（职责收窄后名实相符再动结构，测试 import 跟随）→
  抽规则表（纯搬迁 A 类 5 条进 `application/internal/hook/`）→ 加决策留痕 → 闸门链核验（RF-5）→ 门禁固化（RF-4/RF-7）；
- **双向校验**：规则表建立期，用"现有行为集合 vs 规则表集合"的差集证明无遗漏（差集为空才进下一步）；
- **回滚点**：任一步回归变红即停止并回退该步，不带病推进；
- **与他需求的时序**：REQ-e3b6a0 已上线；本需求的领域聚合若与其闸门链接线（`index.ts` 装配块）冲突，
  以"领域承接其装配输入"为准，不回退其功能。

---

## 13. 性能基线（refactor 必填）

- 现状基线：单次 `user/message` 处理为纯内存判定（规则数 × 台账规模），无网络、无 fs；
- 目标：迁移后**判定耗时 P95 不劣于现状**；由决策日志 `ms` 字段采集并回归对比；
- 决策日志写入不得阻塞事件派发（同步入内存 ring buffer，落盘异步/有界）。

---

## 14. [TBD] 待确认清单

- [TBD] 领域目录的物理位置（`application/internal/hook/` vs `domain/hook/`）—— 原因：取决于 `window.ts`
  等判定的分层归属，需在 design 阶段定案。
- [TBD] 与 REQ-e3b6a0 的运行时边界：其 `GateAwareQuestions` 装饰器 / `onTurnEnd` 闭包与本领域的跑批器
  是否共享事件规范化入口 —— 原因：两侧都在消化 `user/message` 与弹框作答，需在 design 阶段与对方窗口
  对齐，避免双份判定。
- [TBD] B4 里程碑提醒的程序点形式（定时器 vs 闸门链 handler）—— 原因：取决于插件是否有合适的调度点，design 阶段定案。
- [TBD] hook 决策日志的只读查询入口形式（HTTP 路由路径 / 看板面板字段）—— 原因：需与现有
  `/dashboard/api/reqboard/*` 路由命名对齐。
- [TBD] **需求标题与范围不匹配**：标题为"修复 CaptureHook 注入提示词不触发立项弹框"，但该修复的主体已由
  REQ-e3b6a0 上线，本需求实际剩"文案缺口补齐 + 业务 hook 领域聚合"。是否改名 —— 原因：改名影响看板与
  历史引用，需用户裁定。