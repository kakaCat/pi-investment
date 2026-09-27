# REQ-260927100007-b8ba: 拆分流程缺陷修复 D1–D8

> 本需求把「拆分（decompose）节点流程缺陷」清单（docs/work-logs/2026-09/reqboard-decompose-flow-defects.md）
> 逐条修掉。共同根因：**落库被排到批准之后、并委托给一个可能不存在的监听者**，
> 于是需求能在「台账 0 任务」的情况下静默走到验收，且没有任何一处会报错。

## 边界

### 做什么

1. **批准计划即落库（D1）**：批准拆分计划的同一次调用内同步把已批准的任务表落成任务卡 DAG，返回时台账已有卡；落库失败则**不推进**到 implementing，并写失败留痕。
2. **静默停滞响亮化（D2）**：推进到实施后若仍无任务，写 `advance.pausedReason` + 发告警 + 系统评论；不允许"委托了但没人接"这种情况零留痕。
3. **阶段推进的任务完整性守卫（D3）**：目标态为 implementing 时，若「计划有任务、台账该需求 0 个未取消任务」→ **拒绝推进**，错误信息含可用的修复指引。
4. **恢复路径真的可用（D4）**：条款覆盖门禁承认"已批准计划的 RTM/任务表"作为 FR 接收来源；错误提示给出的恢复命令必须实际可执行。
5. **返回体契约修正（D5）**：`reqboard_decompose` 的 `task_coverage` 返回数组时不再触发 schema 校验错误（工具声明与用例返回值对齐）。
6. **RTM 刷新集合补全（D6）**：`task:status` / `task:report` 触发时一并刷新 `rtm-decomposing.yml`，使实施覆盖度随任务变化更新。
7. **补齐 agent 侧任务流转工具（D7 · 方案 A）**：注册 `reqboard_task_move` 与 `reqboard_move`，复用既有 HTTP 层校验逻辑，使 agent/Dive 能自主推进任务与需求状态。
8. **任务级收敛点（D8）**：新增 `transitionTask(task, to, opts)`，内部调 `assertTaskTransition` + 记状态事件；把 ExecuteTask / AdvanceChain / failure-handling / HTTP 路由四处直接写 `task.status` 的地方统一改为经它流转（与需求级 `transitionRequirement` 对称）。

### 不做什么

1. **不改需求级状态机与五道人工门的语义**——`transitionRequirement` 已在本轮之前交付，本次只做任务侧的对称件。
2. **不做 D7 的 B 方案**（删提示词里的 task_move 指引、放弃 agent 自主推进与 Dive 自动模式）——2026-09-27 已裁定选 A；B 是产品方向反转，33 文件连锁，不在本需求。
3. **不改台账 schemaVersion、不做数据迁移**——本需求不新增台账字段，无数据形态变更。
4. **不重构 Dive 编排器**——Dive 仍是"编排者/驱动 agent"，不自己改状态（实测确认它只注入指令、结算节点，不调 transition）。

### 边界理由

- 前三条是同一个根因的三张脸（D1 不落库 / D2 不报警 / D3 不拦截），必须一起修，否则修一条仍会被另两条掩盖。
- 第 4–6 条是同一批"数据契约/数据流"问题，改动面小、可独立验证，先修能立刻改善可观测性。
- 第 7 条是能力建设（agent 能不能自己推进任务链），第 8 条是根治（状态机必须有唯一自校验收敛点）；二者互补：没有收敛点，新增的工具会复制出第 5 个无校验写入点。

## 产品定义

### 一句话目标

让需求流水线的"拆分 → 实施"这一段**要么真的落库、要么响亮地失败**，不再出现"批准了 14 张卡、台账 0 张卡、零告警、静默数日"。

### 核心价值

1. **可交付性**：批准计划后，同一请求返回时任务卡已在台账里，DAG/泳道/实施覆盖度不再为空。
2. **可观测性**：任何"推进了但任务侧没跟上"都变成一条可查的失败留痕 + 告警，而不是沉默。
3. **可自治性**：agent/Dive 能自己把任务从 todo 推到 done（D7），且所有流转都过同一个会自校验的收敛点（D8），非法流转被拒而不是被写出。

### 与现状的区别

现状：批准动作只推进状态（`createdCount = 0`），落库"委托给 Dive"，而该需求 `dive = null`、全仓也没人开过 armed → 委托从未被触发；同时 `decomposing → implementing` 不校验任务是否落库。本需求把落库移进批准动作、给推进加守卫、给任务侧补收敛点。

## 用户与角色

| 角色 | 谁 | 在本需求里做什么 |
|---|---|---|
| 需求提出者（人） | 使用看板的用户 | 提交/批准拆分计划；看到"批准后卡没落库"时得到明确报错与修复指引 |
| 窗口 agent | 运行 reqboard 工具的会话窗口 | 调 `reqboard_decompose` 落库、调 `reqboard_task_move` 推进任务、调 `reqboard_move` 推进需求 |
| Dive 编排器 | `application/dive` | 注入阶段纪律并驱动 agent；**不**替代 agent 改状态 |
| 维护者 | 改 dsh-pmboard 的开发者 | 依赖唯一收敛点，新增写入路径时不必各自记得校验 |

## 功能点

- **FR-1: 批准计划时同步落库任务卡**

批准拆分计划的这一次调用内，把已批准计划的任务表落成台账任务卡（含 depends_on、任务卡文档、decomposition.md、产物登记），**返回时** `reqboard_status`/台账即可查到该需求的任务数 = 计划卡数；落库失败时**不推进**到 implementing，且写失败评论 + `advance.pausedReason` + 告警。

- **FR-2: 静默停滞响亮化**

当"承诺要落库/开跑"的路径没有真正产生任务时，必须留下可查痕迹：系统评论含原因与恢复指引、`advance.pausedReason` 被写入、`deps.alert` 发出一条告警。禁止只有"成功推进"而没有"任务侧空"的任何检测与留痕。

- **FR-3: 阶段推进的任务完整性守卫**

需求状态从 decomposing 推进到 implementing 时，若该需求已批准计划里有任务（`plan.tasks.length > 0`）而台账里该需求 0 个未取消任务 → 拒绝推进，抛出的错误信息必须含可执行的修复指引（调 `reqboard_decompose` 或看板「拆分」按钮）。

- **FR-4: 条款覆盖门禁的失败提示与实际可用路径一致**

已批准的计划（`PlanTask`）**不携带** FR 对照字段，因此"批准后未落库"时，门禁拒绝信息的 `how` 必须给出两条**真的能用**的路径并附参数示例：① 在计划文档 `decomposition.md` 的覆盖对照表补「FR-N ↔ 计划 key」行（这是门禁的双源之一，1518 的恢复即走此法）；② 显式调 `reqboard_decompose(requirement_id=..., tasks=[{key,title,implementation,acceptance,requirement_refs:["FR-1",...]}, ...])`，key 必须与已批准计划一致。禁止给出"给对应任务卡加 requirement_refs"这类**在恢复时刻并不可执行**的操作。另：`reqboard_submit(kind=plan)` 在需求文档有根编号、而计划文档缺 FR 对照表时，返回 `warning` 指路（不硬拦，避免锁死存量计划）。

- **FR-5: reqboard_decompose 返回体契约合法**

`reqboard_decompose` 成功返回时，其返回体必须与工具声明的 output schema 相符——`task_coverage` 为对象数组（`type: 'array'`，items 含 task_id/task_key/task_title/covers_frs/covers_acceptance）；调用方不再收到 `returned invalid output` 校验错误。

- **FR-6: rtm-decomposing.yml 随任务变更刷新**

`task:status` 与 `task:report` 两个触发点除刷新 `rtm-implementing.yml` 外，还要重新生成 `rtm-decomposing.yml`（实施覆盖度），使任务落库/状态变化后实施覆盖度读数随之变化。

- **FR-7: 补齐 agent 侧任务流转与需求流转工具**

注册 `reqboard_task_move`（todo→in_progress→…→done，复用 `assertTaskTransition` 与执行段结算逻辑）与 `reqboard_move`（需求级推进，复用 `assertReqTransition`/`transitionRequirement`）。

**实测现状（2026-09-27 取证，已更正 D7 的原始证据）**：`grep -rn "name: 'reqboard_" src/tools/` 枚举出**实际注册 15 个**：
accept_sheet / ask_confirm / capture / **clear_pause** / confirm_receipt / create / decompose /
note_interruption / **run_status** / status / submit / task_execute / task_report / task_run / task_status。
即：`reqboard_move` 与 `reqboard_task_move` **确实缺失**（D7 成立）；但测试期望表**同时过期**——
它列了这两个不存在的名字，却漏了实际存在的 `reqboard_clear_pause` / `reqboard_run_status`。

**更正**：`tests/apply-wiring.test.ts` 当前 4/4 红**不是因为缺工具**——它在 `apply()` 装配阶段就抛
`TypeError: Cannot read properties of undefined (reading 'provide')`
（`application/dive/ReqboardDiveManager.ts:27`：`ReqboardDiveManager extends Service`，
`static inject = ['agents','reqboard']`，而测试的 stub ctx 没有 `reqboard` 服务），
**根本执行不到工具集合断言**。因此"4/4 失败 = 缺口的直接证据"这一说法不成立。
FR-7 的交付必须同时：(a) 补两个工具；(b) 修该测试的装配 stub（或改用真实 ctx）；
(c) 把期望集合对齐为实际 17 个名字。

- **FR-8: 任务级状态收敛点并统一四处写入点**

新增 `transitionTask(task, to, opts)`（application 层），内部调用 `assertTaskTransition(from, to, actor, role)`、维护 version/updatedAt/updatedBy、记录状态事件，并保留 `allowIllegalTransition` 逃生舱。ExecuteTask、AdvanceChain、failure-handling、HTTP tasks 路由四处对 `task.status` 的赋值全部改为经它流转；新增单测锁定"非法流转被拒且状态不变"。

- **FR-9: 确认门挂起（pending）时同窗口不得继续产出下游产物**

`reqboard_ask_confirm` 超宽限返回 `{pending:true, ticket}` 后，该窗口若再调 `reqboard_submit` /
`reqboard_decompose` / `reqboard_move` / `reqboard_task_move` 等**写路径**工具，必须被代码级拒绝，
错误码 `REQBOARD_CONFIRM_PENDING`，错误信息含取回执的两条可用路径（`reqboard_confirm_receipt(ticket="…")`
或看板确认）；`reqboard_status` 与 `reqboard_confirm_receipt` 保持可用（否则人无法解除挂起）。
工具返回体的 `note` 必须显式写明"收到作答前不得产出下游产物"。

**背景（实测事故）**：确认门走"非阻塞投递"（30s 宽限超时即返回 pending，见
`domain/limits.ts: confirmInlineGraceMs` 与 `internal/pending-confirm.ts`），**弹框不拦 agent loop**。
这是为修「弹框超时把回合打死」而刻意设计的；但它没有配套的"停手"守卫，
于是窗口在等作答期间继续产出下游产物，"未获批准的下一步"照样发生。


- **FR-10: reqboard_status 返回体必须是 lossless JSON（不得含 undefined 属性）**

`application/internal/rtm-health.ts` 的 `checkRTMHealth` 在**无失败记录**时返回
`last_failure: undefined`（own property，而非省略该键）。它经 `QueryState` 的 `rtm_health`
进入 `reqboard_status` 返回体，被 PTC 绑定层判为
`tool "reqboard_status" returned invalid output: value is not lossless JSON`。

**影响（实测）**：窗口一旦绑定需求（`open.length > 0`，`rtm_health` 才会被展开），
`reqboard_status` **必然失败**；未绑定时不展开该键，故此前一直未被发现。
这条直接违反本需求 FR-9 的"status 必须保持可用"。

**复现证据（2026-09-27 实测）**：直接调 `checkRTMHealth(...)` 得到
`keys = [healthy, missing_files, last_failure, retry_available]`、
`hasOwn(last_failure) = true`、`last_failure = undefined`；
递归扫描 `undefined` 值属性 = `["rtm_health.last_failure"]`；
而 `JSON.stringify` 会**静默丢弃**该键（`includes('last_failure') === false`）——
这正解释了它为何一直没在 JSON 往返里暴露，却会被 PTC 的 lossless 校验拦下。

**修法**：无记录时**省略该键**（条件展开），并为 `rtm_health` / `queryState` 加回归测试，
断言返回体可被 lossless 序列化（递归扫描无 `undefined` 值属性）。

- **FR-11: 采集半不得直投会话——凡"进会话"的投递必须走 round 半且带 source.kind='dive'（与 Dive 设计一致）**

**实测（2026-09-27，本窗口 session-52f725ef）**：Dive 在 `agent/status === 'idle'` 跑批时，只要"本回合有直接人类消息"
（`session-driver.ts:206` 的 `human !== undefined`）就把当前阶段的纪律提示词经
`onStagePrompt` → `AgentDeliverer.deliver` → **`agent.followup()`** 投递进会话，
而 `agent.followup` 会**新起一轮 agent loop**。去重只覆盖"节点结算"（`settledNodes` 集合），
**纪律投递没有任何按阶段去重** → 同一条人类消息会额外产生一轮"只有纪律、没有提问"的 agent 轮次，
这就是"loop 没有停止"的机制来源。

**与注释声明的意图不一致**：`wiring/pm-capture-root.ts:128` 写的是
「**状态转移**纪律与产物催办文案向绑定会话投递」，但实现条件是本回合**有**人类消息，
与"阶段是否变化"无关。

**证据链**：
1. `application/dive/session-driver.ts:206-237`（注入条件 = `human !== undefined`；去重集合只喂给节点结算）；
2. `wiring/pm-capture-root.ts:132-139`（`onStagePrompt` → `deliverer.deliver` → `agent.followup` = 新轮次）；
3. 运行时 `prompt-injection-log.json` 本窗口的 `brainstorming/light/feature` 记录，
   其 `fragmentIds` = [brainstorming/light/feature, brainstorming/light, brainstorming/feature, common/iron-rules]，
   与**实际到达模型的 user 消息文本逐字一致** → 证明该纪律确实被"投递"进会话（而非只进系统提示词）；
4. `node-isolation-log.json` 本窗口仅 1 条：`status=skipped`, `code=agent_busy`,
   `reason="agent 忙碌（活动轮次），跳过替换"` → 证明投递已把 agent 置为活动轮次。

**与您的 Dive 设计对照（契约来源 `docs/architecture/reqboard-dive-mode.md` §140-160 + `RequirementDive`）**：设计规定
① 驱动点 = 整 agent 空闲，且**只有 `armed + active` 才起轮**（`round-state.ts:126 isDrivableRequirement`；`round-driver.ts:201/251` 两处复核）；
② 事件**不直接投递**，只置标志 + `requestDrive`（`round-driver.ts:286-294`）；
③ 回合消息必须带 `source:{kind:'dive',requirementId,revision,round}`，走**预留 → deliverMessage → 准入（user/message 身份匹配）→ roundsInStage 落库**（`round-driver.ts:209-220`）。

**实现偏差（3 条）**：

| # | 设计 | 实现 | 位置 |
|---|---|---|---|
| G1 | 进会话只能走 round 半、带 `kind:'dive'` | `onStagePrompt` 走**通用 plugin 投递**（`kind:'plugin'`），不预留、不计数、不校验 | `session-driver.ts:219` → `pm-capture-root.ts:133` → `AgentDeliverer.deliver`（`AgentDeliverer.ts:53-60`） |
| G2 | 起轮条件 = `armed + active` | 触发条件是"本回合有直接人类消息"，与 armed/active/**阶段是否变化**全无关 | `session-driver.ts:206` |
| G3 | 采集半不投递 | 采集半在 idle 直接投递两条：阶段纪律（`:219`）与里程碑催办（`:243`） | `session-driver.ts:219/243` |

**修法（与设计一致）**：

- **A. 采集半只采集/簿记/记录，不再投递**——删除 `driveIdle` 中 `:219` 的纪律投递（纪律本就在每次请求的 system prompt 里，见 `capture-section.ts:140-163`，属纯冗余）；保留 `injectionLog.record` 与 R1 `onBoundWindowActivity`。
- **B. 里程碑催办改走 round 半**——`:243` 不再直投，改为登记"待催办"并 `requestDrive`，由 round 半在 `armed + active + idle + 无竞争` 时作为回合消息投递；非 armed 时只写台账 comment（不静默）。
- **C. 投递白名单**——`deliver()` 的通用 plugin 路径只保留"人点头后的收尾/交接/唤醒"（pending-confirm `wake`、闸门链 H4、失败告警），并在代码注释与架构文档里列成白名单；其余一律经 round 半的 `createRoundMessage`。
- **D. 补文档缺口**——`reqboard-dive-mode.md` 从未规定"阶段纪律注入 / 里程碑催办"的归属，这正是设计缺口；按 A/B 写清归属并新增「投递白名单」一节。
- 注：`onNodeSettled`（`:226`）走"只发信号 + 异步边界 `append`"，与设计②同型，保留；但其 `append('user/message', 输入包)` 需在文档里显式归类（建议归"人点头后的记录"豁免项）。

**活体复现（2026-09-27 02:06–02:08，本窗口）**——按时间线可复核：
- `02:06:56.860` `NODE-2 user/message ARRIVED` + `02:06:56.862 NODE-3 roundHuman SET (text.length=12)`
  → 这是**真人类**消息（"我感觉到是dive的问题"）；
- 该轮由我作答，跑到 `02:08:44` 才结束（agent 从 busy 回到 idle）；
- `02:08:44.091` 又一条 `NODE-2 user/message ARRIVED`，但**没有 NODE-3**
  （在 `session-driver.ts` 的 `source.kind !== 'user'` 过滤处被拦下）→ 即**非人类来源**，
  内容正是阶段纪律全文 → **这就是 agent 紧接着收到的"用户消息"，也是新一轮 loop 的起点**。
- 同型事件 `02:05:43.242` 亦无 NODE-3；对应的 `node-isolation-log` 记录为
  `02:05:43.213 status=skipped code=agent_busy` —— 证明**投递当场就把 agent 置为活动轮次**。

**净效果**：一条人类消息 = **两轮** agent loop（第一轮答人，第二轮只有纪律、没有提问）。
`roundHuman` 用后即删，故该循环会在无新人类消息时自然排空。

**验收**：① 同阶段连续两条直接人类消息 → 采集半**零投递**（`agent.followup` 不被调用、不产生额外轮次）；
② 需求 `armed + active` 时 `requestDrive` 才投递，且消息 `source.kind === 'dive'`、`roundsInStage` 递增；
③ 非 armed（全仓现状）时里程碑催办只写 comment、不投递。

- **FR-12: 窗口绑定的 RTM 投影必须"可更新且有消费者"**

**现状实测（2026-09-27）**：`rtm-lifecycle.yml` 的 `requirement.source_session` **确实有值**
（本需求第 6 行 = `session-52f725ef-…`；全量对账「台账 sourceSessionId ↔ RTM source_session」**4/4 一致、0 缺失、0 不一致**），
但它有**三条结构缺口**：

1. **写了没人读**：`source_session` 由 `lifecycle-generator.ts:85` 写入，但全仓**无任何生产代码读取**它
   （`grep -rn 'source_session' packages/ --include=*.ts` 仅命中写入方、类型声明、注释与测试夹具）。
   Dive 真正的投递目标取自**台账**（`round-driver.ts:287`：`requirementById(id)?.sourceSessionId`），
   而 `rtm-yaml.ts:68` 的注释「Dive 唤醒要按它投递」**与实现不符**。
2. **"绑定"不是触发点**：`filesForTrigger` 只有 8 个 trigger
   （create / submit:requirement / confirm:artifact / submit:design / confirm:plan / task:status / task:report / submit:verification），
   **没有 bind** → 先建后绑、或绑定关系变更后，`rtm-lifecycle.yml` 的窗口字段要等下一个触发点才刷新（**可能长期陈旧**）。
3. **窗口侧锚点不投影**：绑定有两个来源（`window.ts:24-41`）——需求侧 `sourceSessionId`（已投影）
   与窗口侧 triage 锚点（`bind_req`/`create_req` 的 `resultRequirementId`，**未投影**）
   → 靠「绑定」接手的窗口在 RTM 里**完全看不到窗口**（实测今天 0 例，属潜在缺口而非现行故障）。
   另：74 个存量需求没有 RTM 文件（RTM 基础设施 2026-09-26 才上线，未回填），这也是"看不到窗口信息"的表面原因。

**修法（需人裁决，三选一或组合）**：

- **A（最小，只治"话不实"）**：删除 `rtm-yaml.ts:68` 的误导注释，在 `types.ts` 注明"当前无消费者，仅供人查"。
- **B（对齐注释，推荐）**：让 Dive 的投递目标**优先读 RTM**，并新增 `bind` trigger —— 绑定发生时刷新 `rtm-lifecycle.yml`。
- **C（完整）**：RTM 增加窗口侧锚点投影（如 `bound_windows: [sessionId]`），由台账 triage 计算，`bind` 触发刷新。

**验收**：① `source_session` 的**读取方**非空（B/C）或注释与实现一致（A）；
② 构造"先建需求 → 再用 bind 绑定窗口"→ 绑定后 `rtm-lifecycle.yml` 的窗口字段随之更新（B/C）；
③ RTM 能表示**窗口侧锚点绑定**的窗口（C）。

- **FR-13: 文字证据路径确认后必须能推进（不得留下"已落章但推不动"的死锁）**

**实测（2026-09-27 02:52–02:55）**：用户在对话里说「开始推进到设计吧」，agent 按铁律走
`reqboard_ask_confirm(evidence="开始推进到设计吧")` → `confirmArtifact` **落章成功**
（`confirmedVia=session`、`evidence_verified=true`），**但需求状态仍是 `brainstorming`**，
且此后**无任何 agent 可达的推进路径**：

- 证据路径（`ConfirmArtifact.ts:107-160`）**只落章**，不调 `transitionRequirement`；
  其返回 note 指向 `reqboard_move`——而该工具**未注册**（D7）；
- 弹框路径（`AskConfirm.ts:87-112`）因"产物已确认"**早返回 `advanced:false`、不弹框**
  （实测返回 `note='产物 requirement 已确认，未重复弹框'`）→ 同样不推进；
- 看板路由（`http/routers/requirements.ts:294`）是**人**的通道。

→ 结果：**门放行了、节点却永远停在 brainstorming**，且只有一句"已确认，未重复弹框"、零修复指引。
这正是 D1/D2「落章与推进不是一个原子动作」在**需求级**的同一形态。
→ 同时**证伪** d7 决策记录 §9.4 的自我更正（"需求阶段可纯靠弹框推进"）：弹框只在**未落章**时推进；
一旦先走证据路径落章，就既推不动、又不能再弹框 = **静默死锁**。

**修法**：① `ConfirmArtifact` 落章后调用与 `confirm-settle` **同一推进块**
（`advanceTargetFor` + 人工门 `transitionRequirement`），不依赖外部工具；② 补 `reqboard_move`（FR-7）作兜底通道。

**验收**：`reqboard_ask_confirm(evidence=...)` 成功后需求状态**在同一调用内** brainstorming → design；
若确实不推进，必须返回明确原因 + 可执行命令，不得沉默。

## 接口设计

### 收敛点接口（FR-8）

```ts
// src/application/internal/task-transition.ts
export interface TaskTransitionOpts {
  at: number
  actor: ActorRef
  reason?: string
  /** 任务角色（parent/subtask/legacy）——决定用哪张转移表 */
  role?: TaskRole
  /** 逃生舱：仅迁移/回填可用，业务路径禁止 */
  allowIllegalTransition?: boolean
}
export function transitionTask(task: TaskRecord, to: TaskStatus, opts: TaskTransitionOpts): void
```

约定：成功 = 就地改 task.status/version/updatedAt/updatedBy + 追加 statusHistory；失败 = 抛错且**不改动任何字段**（半迁移态禁止）。

### 工具接口（FR-7）

| 工具 | 输入 | 输出 | 错误语义 |
|---|---|---|---|
| `reqboard_task_move` | `task_id`、`to`、`reason?` | `{success, task_id, from, to, status}` | 非法转移 → `invalid_transition`；人工门越权 → `human_gate`；任务不属于本窗口绑定需求 → `REQBOARD_NOT_BOUND_TO_WINDOW` |
| `reqboard_move` | `requirement_id?`、`to`、`reason?` | `{success, requirement_id, from, to, status}` | 非法转移 → `invalid_transition`；人工门越权 → `human_gate` |

### 返回体契约（FR-5）

`reqboard_decompose` 的 `task_coverage` 类型从 `object` 改为 `array`（item 为对象）；`coverage_check` 保持对象。

## 验收标准

### 可执行判定命令

```bash
# FR-5：返回体契约（schema 与实际值一致）
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/tools-schema.test.ts
# 预期：passed

# FR-7：工具集合对齐（含修装配 stub；当前 4/4 红是 Service 装配抛错，非断言失败）
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/apply-wiring.test.ts
# 预期：4/4 通过；期望集合 = 实际 17 个（含 reqboard_move / reqboard_task_move / clear_pause / run_status）

# FR-8：任务级收敛点拦截非法流转
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-transition-guard.test.ts
# 预期：passed，且断言"拒绝时 task.status/version/updatedAt 不变"

# FR-1/FR-2/FR-3：批准落库 + 守卫 + 响亮化
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-settle-plan-persist.test.ts
# 预期：批准后台账任务数 = 计划卡数；dive=null 且落库失败时不推进且写 pausedReason

# FR-6：RTM 刷新集合
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts
# 预期：task:status 触发的 files 集合含 rtm-decomposing.yml
```

```bash
# FR-9：挂起确认期间的停手守卫
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts
# 预期：pending 存在时同窗口调 reqboard_submit → 被拒（REQBOARD_CONFIRM_PENDING）且不写盘；
#       reqboard_confirm_receipt / reqboard_status 仍可调用
```

```bash
# FR-10：status 返回体 lossless（已绑定窗口）
# 在任一已绑定窗口调 reqboard_status → 必须 success（当前必然报 returned invalid output: ... not lossless JSON）
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/status-lossless.test.ts
# 预期：passed（递归断言返回体无 undefined 属性）
```

### 判定标准

1. 上述命令全绿；
2. `reqboard_decompose` 成功返回不再出现 `returned invalid output`；
3. 构造"计划有卡 / 台账 0 卡"的推进路径 → **被拒**且报错含修复指引；
4. 四处任务写入点全部经 `transitionTask`（`grep -n 'task.status = \|t.status = \|parent.status = ' src` 在业务路径上零命中，除去收敛点自身与迁移脚本）。

## 参考

- 流水线节点流程图（RTM 生成点 · 人工门 · Dive 参与点）：docs/architecture/reqboard-pipeline-flow.md
- Dive 契约与投递白名单：docs/architecture/reqboard-dive-mode.md
- 缺陷清单原始证据：docs/work-logs/2026-09/reqboard-decompose-flow-defects.md、docs/work-logs/2026-09/d7-task-move-tool-decision.md

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |
| FR-7 | 🔴 **未被接收** | — |
| FR-8 | 🔴 **未被接收** | — |
| FR-9 | 🔴 **未被接收** | — |
| FR-10 | 🔴 **未被接收** | — |
| FR-11 | 🔴 **未被接收** | — |
| FR-12 | 🔴 **未被接收** | — |
| FR-13 | 🔴 **未被接收** | — |

> 🔴 **未被接收（13 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7、FR-8、FR-9、FR-10、FR-11、FR-12、FR-13

<!-- reqboard:marks:end -->
