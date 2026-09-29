---
id: reqboard-pipeline-flow
title: 需求流水线节点流程图（RTM 生成点 · 人工门 · Dive 参与点）
summary: draft→archived 七节点的实际动作、RTM 产出文件、五道人工门与 Dive 两半参与点的 ASCII 流程图；附投递白名单与缺陷落点 D1–D13（含修复状态）。
type: architecture
status: living
updated: 2026-09-27
owners: [session-52f725ef]
tags: [reqboard, dive, rtm, pipeline, flow]
---

# 需求流水线节点流程图（RTM 生成点 · 人工门 · Dive 参与点）

> **这一页解决什么**：把「需求走到哪一步 → 系统实际做了什么 → 落了哪个 RTM 文件 → 哪一步必须人点头
> → Dive 在哪一拍介入」画在一张图里，供排障与改动前对照。
>
> **与相邻文档的分工**：[pmboard 代码流程](pmboard-code-flow.md) 讲代码分层与调用链；
> [Dive 模式架构](reqboard-dive-mode.md) 讲 Dive 的契约；[RTM 使用指南](../guides/rtm-usage.md) 讲 RTM 文件格式。
> 本页只讲**运行时节点流程**。
>
> **口径（重要）**：本图按 `packages/web/dsh-pmboard/src` 与 `packages/tools/reqboard/src` 的**实际实现**绘制，
> **不画未实现的设计意图**；凡"设计说 A、实现是 B"的地方直接标 ⚠ 并给缺陷号。
> 图例：`[阶段N]` = 节点内动作顺序；`→ RTM` = 本次动作落地的 RTM 文件；`【门】` = 人工确认门（代码级仅人）；
> `◆Dive` = Dive 参与点；`⚠Dn` = 缺陷落点（REQ-260927100007-b8ba）。

```
┌───────────────────────────────────────────────────────────────────────────┐
│          需求流水线各节点流程 - RTM 数据生成与 Dive 模式决策                 │
│   (draft → brainstorming → design → decomposing → implementing → accepting) │
└───────────────────────────────────────────────────────────────────────────┘


节点零：draft（立项）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 立项（reqboard_create）
      │
      ├─→ 创建需求记录：id / title / category / status=draft
      │      绑定本窗口：sourceSessionId = 本窗口 key（openRequirementsFor 之后才认它）
      │
      ├─→ → RTM: rtm-lifecycle.yml（trigger='create'；骨架 current_stage=draft）
      │
      └─→ 完成标志：
             • reqboard_create 成功
             • rtm-lifecycle.yml 已生成到 docs/requirements/<REQ>/
             • 看板 draft 泳道可见

   ◆Dive 采集半（session-driver，**不受 armed 门控**，见文末不变量）
      └─→ 窗口 unbound → bound；此后本窗口的**直接人类消息**进 roundHuman 采集

   ⚠ 立项后即可被"接手推进"：绑定窗口一发言，R1（onBoundWindowActivity）自动把 draft → brainstorming
      —— 这一次转移不需要人点（设计如此，非缺陷）。


节点一：brainstorming（需求分析）
<!-- serves: FR-5 / FR-6（REQ-260927123256-196b t6：等待语义与停手守卫已同步到本文档） -->
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 写需求文档
      │
      ├─→ 写 requirement.md（必填节：边界 / 产品定义 / 用户与角色 / 功能点；条款行 `- **FR-N: 名称**`）
      │
      └─→ 提交：reqboard_submit(kind=requirement)
             门禁：G2 文档集完整性 + 编号连续性 + 唯一性 + 可打开性
             • 通过 → 登记产物（artifacts[] = {stage: brainstorming, kind: requirement}）
             • 不过 → 拒绝提交，返回结构化缺口（不推进）

   [阶段2] 生成 RTM
      │
      └─→ → RTM: rtm-brainstorming.yml（+ rtm-lifecycle.yml）
             trigger='submit:requirement'；解析 requirement.md 提取 FR 列表

   [阶段3] 【门】G1 = requirement 产物确认
      │
      ├─→ 发起：reqboard_ask_confirm(target=artifact, kind=requirement)
      │      ⚠ 缺省**阻塞等待**：人不作答，agent 就停在这一步（与原生 ask_user_question 一致），
      │         等到作答 / 取消 / 中止才返回；返回体不再出现 pending/ticket
      │         （REQ-260927123256-196b FR-1；原「30s 宽限到点自动放行」已删除）
      │      ⚠ 仅当调用方**显式**传正数 inline_grace_ms 才走非阻塞逃生舱：超宽限返回 pending+ticket，
      │         弹框留着、后台落章并唤醒窗口——这是"主动放弃阻塞"，后果自负（FR-3）
      │      ⚠ 阻塞期间本窗口写路径被停手守卫拦住（REQBOARD_CONFIRM_PENDING），
      │         且 reqboard_status.pending_confirms 可见"在等谁 / 是否被中止"（FR-2 / FR-4）
      │
      ├─→ 肯定 → 落章 + transitionRequirement(brainstorming → design)
      ├─→ 否定/需修改 → 只留痕（recordDeclinedConfirmation），不推进、不注入下一节纪律
      │      反馈循环：读 user_feedback → 改 requirement.md → 重新 submit → 重新确认
      └─→ → RTM: rtm-brainstorming.yml + rtm-design.yml + rtm-lifecycle.yml（trigger='confirm:artifact'）

```

```
节点二：design（设计）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 写设计文档（feature 必交 5 份，见 `templates/design/`）
      │      architecture.md / data-model.md / interfaces.md / test-cases.md / use-cases.md
      │      每个 `##` / `###` 标题**必须**带 `<!-- serves: FR-x -->`，否则 design_orphan 硬拦
      │      禁止混入任务表（design_contains_decomposition 硬拦）
      │
      └─→ 登记：reqboard_submit(kind=design)（幂等；逐份登记态 design_docs[]）

   [阶段2] 生成 RTM
      └─→ → RTM: rtm-design.yml（+ rtm-lifecycle.yml）；trigger='submit:design'

   [阶段3] 【门】G2 = design 产物确认
      │
      ├─→ reqboard_ask_confirm(target=artifact, kind=design)
      │      等待语义同 G1：缺省阻塞到作答/取消/中止；显式 inline_grace_ms 才非阻塞（FR-1 / FR-3）
      │      闸门：checkDesignCompletenessGate（① 文档集交齐 ② 每份 design/*.md 都有确认章）
      ├─→ 肯定 → 落章 + transitionRequirement(design → decomposing)
      └─→ → RTM: rtm-design.yml + rtm-brainstorming.yml + rtm-lifecycle.yml（trigger='confirm:artifact'）
```

```
节点三：decomposing（拆分）★ 本需求主要修点
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 写拆分计划
      │
      ├─→ 写 decomposition.md（含 §1 RTM 覆盖对照表：根编号 ↔ 计划 key）
      ├─→ 提交：reqboard_submit(kind=plan)（任务表：key/title/phase/side/depends_on/acceptance/implementation）
      │      ⚠F4 计划文件（PlanTask）**不含** FR 对照字段 → 门禁的唯一 FR 来源是
      │         ① 显式传入的 tasks ② decomposition.md 覆盖对照表；失败提示必须给这两条可用路径
      │
      └─→ 计划状态：pending_approval（未批准不得落库）

   [阶段2] 【门】G3 = 批准拆分计划（★ 唯一需要人点头的"计划"闸门）
      │
      ├─→ reqboard_ask_confirm(target=plan)（或看板「批准计划」）
      ├─→ 落章：plan.approvedAt + decomposition 产物 confirmedAt
      │
      ├─→ 设计意图：**落章 → 同步落库任务卡 → 进 implementing + autoRun=true**
      │      ✗ 实现（事故）：@confirm-settle `const createdCount = 0`——落库那步没写，
      │        改为"委托 Dive 续跑时创建"        ⚠D1（批准计划不落库）
      │        且该需求 dive = null、全仓 0 需求开过 armed → 委托**从无监听者**
      │        → 台账 0 任务，DAG/泳道/实施覆盖度全空，**零告警**  ⚠D2（静默停滞）
      │
      ├─→ 落库后：transitionRequirement(decomposing → implementing)
      │      ✗ 实现：该转移**不校验**"计划有卡而台账 0 卡"      ⚠D3（任务完整性守卫缺失）
      │
      └─→ → RTM: rtm-decomposing.yml + rtm-implementing.yml + rtm-lifecycle.yml（trigger='confirm:plan'）

   [阶段3] 落库任务卡（reqboard_decompose）
      │
      ├─→ 产 TaskRecord[]（status=todo、dependsOn 解析成真实 id、requirementRefs[]）
      ├─→ 写 decomposition.md + tasks/<t-id>.md 骨架
      ├─→ 登记产物：decomposition + 每任务 task_detail
      ├─→ → RTM: 随 confirm:plan 一次性刷新
      │      ⚠D6 此后任务状态变更**不再**刷新 rtm-decomposing.yml → 实施覆盖度停在 0%
      │
      └─→ 返回体：{success, created, task_coverage, coverage_check}
             ⚠D5 声明 task_coverage: object，实际返回 **array** → 绑定层报
                "returned invalid output: value.task_coverage must be an object"
                → agent 误判失败并重试（有幂等守卫兜住）
```

```
节点四：implementing（实施）★ 任务级状态机在这里
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 任务流转
      │
      ├─→ 目标：reqboard_task_move(task_id, to, reason)
      │      ✗ 实现：`reqboard_task_move` 与 `reqboard_move` **未注册**（实际 15 个工具里没有）
      │        → agent 无法推进任何任务；看板 HTTP 路由仍可用（"人点得动"掩盖"agent 调不动"）
      │        ⚠D7（agent 侧任务流转工具缺失 —— 已裁定走方案 A：补齐工具）
      │
      ├─→ 任务状态机：todo → in_progress → integrating → testing → in_review → done（+canceled）
      │      role=subtask/parent 用收紧表（无 integrating/testing/in_review 出边）
      │      人工门（仅人）：各态→canceled、canceled→todo、done→in_progress/canceled
      │
      ├─→ 收敛点：需求侧有 transitionRequirement（会自校验）；
      │      任务侧 **无等价收敛点**，状态被四处直接赋值：
      │        ExecuteTask.ts:225/260 · AdvanceChain.ts:138/171 ·
      │        failure-handling.ts:44 · http/routers/tasks.ts:81（唯一校验点，看板按钮）
      │        ⚠D8（校验强度与执行者错配 → 子卡链/父卡链能造非法流转且零报错）
      │
      └─→ → RTM: rtm-implementing.yml + rtm-implementing/<task>.yml
             （trigger='task:status' / 'task:report'）  ⚠D6 同 rtm-decomposing.yml 不刷新

   [阶段2] 任务汇报与收尾
      ├─→ reqboard_task_report(task_id, summary, completed, files_changed, next_step) → 追加 tasks/<t>.md
      ├─→ 子卡全部 done/canceled → 父卡 finalize（assertDoneEvidence 凭证门）
      └─→ 全部任务 done → applyTaskRollup → transitionRequirement(implementing → accepting)

   [阶段3] 失败路径（响亮化）
      └─→ 子卡执行失败 → rollbackSubtask（in_progress → todo、attempt+1、revisions(rollback)）
             → pauseRequirement(autoRun=false, pausedReason) + deps.alert 高优告警
```

```
节点五：accepting（验收）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 提交验收材料
      └─→ reqboard_submit(kind=verification, summary, evidence[])
             证据必须含可核验锚点（命令/路径/数据）；引用路径必须真实存在
             → → RTM: rtm-accepting.yml + rtm-lifecycle.yml（trigger='submit:verification'）

   [阶段2] 【门】G4 = 人工验收（★ 只有人能点）
      └─→ reqboard_accept_sheet 逐项弹框（通过/改进/其他）；或看板勾选
             全通过 → archived；有 failed → 生成返工卡，回 implementing

节点六：archived / done（归档）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 准备归档材料：reqboard_submit(kind=archive, dir, docs[], merged_into[], index_entry)
             （feature/refactor/spike 必填 manual_updates；bug/doc/chore 写 manual_note）
   [阶段2] 【门】G5 = 人工归档（仅人）
```

## 横切 A · Dive 两半的实际时序（这是"loop 没有停止"的来源）

```
  人发言 ──► session/event 'user/message'（source.kind='user'）
                │
                ├─ 采集/簿记半（driveIdle 之前只登记，不动作）
                │     └─ roundHuman.set(windowKey, {text})        ← 仅直接人类消息
                │
  agent 变空闲 ──► agent/status === 'idle'
                │
                └─ round.onIdle(agent, tick)
                      ├─ 1) captureTick() = driveIdle(windowKey, session)
                      │      ├─ unbound → 登记立项候选（pending）
                      │      └─ bound   → human 存在时：
                      │           ├─ R1: onBoundWindowActivity → draft→brainstorming
                      │           ├─ ✔ 阶段纪律投递：onStagePrompt(resolved.text)
                      │           │     └─► AgentDeliverer.deliver → agent.followup()
                      │           │          ★ 这**新起一轮 agent loop**（消息 source.kind='plugin'）
                      │           │          ⚠F11 采集半**直投会话**，绕开 round 半的
                      │           │             armed+active / 预留 / 准入计数 / 来源标识
                      │           │             且纪律本就在每次 system prompt 里（纯冗余）
                      │           └─ 节点结算信号 onNodeSettled（→ 异步边界 append 输入包）
                      │                 （本例实测：status=skipped code=agent_busy）
                      │
                      └─ 2) requestDrive(state) = round 半
                            └─ 仅当 **armed + active + idle + 无竞争输入** 才起轮
                                 ├─ 预留 round = roundsInStage+1（登记 messageId/revision/content）
                                 ├─ createRoundMessage → source.kind='dive'
                                 ├─ deliverMessage → agent.followup()
                                 └─ 准入：user/message 身份匹配 → roundsInStage 落库
                                       reject/discarded/cancelled 不计数；达上限 → paused/round-limit

  ⚠F11 净效果：一条人类消息 = **两轮** loop（第一轮答人；第二轮只有纪律、没有提问）。
      实测时间线（2026-09-27）：02:06:56 人类消息(NODE-3, 12 字符)
        → 02:08:44 NODE-2 无 NODE-3 = Dive 投递 → 我又答了一轮；
        02:34:33 人类消息(NODE-3, 17 字符) → 02:35:46 NODE-2 无 NODE-3 = 又一次投递。
```

## 横切 B · 闸门后置链（人点完弹框后机器自动做什么）

```
  turn/end ──► onTurnEnd(windowKey, session) ──► setImmediate ──► gateChain.runPending()
                两相：Phase A 入队（作答发生时，只登记不执行）
                      Phase B 边界执行（agent 空闲后）H1 → H2 → H3 → H4 → H5
                      幂等键 = (windowKey, gate, decidedAt)
                        H1 advance   推进落库
                        H2 compact   压缩上下文（要求 idle）
                        H3 inject    注入阶段纪律（**非肯定答复不注入**，FR-10）
                        H4 resume    ★ 向窗口投递唤醒消息（【闸门确认】/【闸门待改进】+ 意见）
                                     → agent.followup() → 新起一轮
                        H5 audit     链级审计写台账 comment
  ⚠ 说明：H4 投递是**设计内的唤醒**（把裁决与意见交给 agent），与 ⚠F11 的"多余重投"不同类；
     但它同样以 user 消息形态到达，容易被 agent 误当人指令 —— 靠纪律而非代码区分。
     实测：02:09:32 台账 comment "[闸门后置链] G1：h1-advance=skip(not_advanced)；…；h4-resume=ok"
```

## 横切 C · 投递白名单（FR-11 的目标状态）

| 投递方 | 现状 | 目标（与 Dive 设计一致） |
|---|---|---|
| round 半续跑 | `createRoundMessage` + source.kind='dive' + 预留/准入 | **保持**（唯一合法的"起轮"通道） |
| 阶段纪律（采集半 idle） | `deliver()` → kind='plugin'，**每次人类发言**都投 | **删除投递**（纪律已在每次 system prompt；保留 injectionLog 留痕与 R1 接手推进） |
| 里程碑催办（采集半 idle） | `deliver()` → kind='plugin'，时间型直投 | 改为"登记待催办 + requestDrive"，由 round 半在 armed+active 时投递；非 armed 只写 comment |
| pending-confirm wake | `deliver()` → kind='plugin' | **保留**（人作答后的交接） |
| 闸门链 H4 resume | `deliver()` → kind='plugin' | **保留**（人点头后的唤醒） |
| 失败告警 FailureAlert | `deliver()` → kind='plugin' | **保留**（响亮化） |

> **不变量（不得违反）**：采集/簿记与"人点头后的必要收尾/交接/记录"**不得**加 `if(!armed) return`
> —— 全仓至今 0 个需求开过 armed，一旦被门控，流水线立刻停摆（源码注释原文）。

## 横切 D · 确认门（弹框）全链路：现状 → FR-14 目标

> 图例：【门】人工确认门；通道①②③ 三条确认通道；⚠ 实测断点。

```
┌───────────────────────────────────────────────────────────────────────────┐
│              确认门（弹框）全链路 - 三通道 / Dive 兜底 / 断点位置            │
└───────────────────────────────────────────────────────────────────────────┘


[阶段1] 产物登记（reqboard_submit）
   │
   └─→ artifacts[] 追加一条 { stage, kind, path, registeredAt }，confirmedAt 为空
          ⚠ 自动发现还会补 notes（过程产物兜底），它不是门禁产物


[阶段2] 等人点头（三条通道，任一即可）
   │
   ├─ 通道① 弹框：agent 调 reqboard_ask_confirm(target=artifact, kind=…)
   │     ├─ 该 kind 产物**已确认**？ → 早返回「已确认，未重复弹框」，**不弹、不推进**
   │     │        ⚠D12  ← 这一条让"门已满足但状态没动"永远救不回来
   │     └─ 未确认 → 弹框 → 人点肯定项 → 落章 + 推进（atomic）
   │
   ├─ 通道② 文字证据：agent 调 reqboard_ask_confirm(evidence="…")
   │     ├─ 核验命中 60min 内真实用户消息 → 落章（confirmedVia=session）
   │     │        ⚠D12/FR-13  修复前：只落章、**不推进**，note 指向未注册的 reqboard_move
   │     └─ 未命中/编造 → REQBOARD_EVIDENCE_FAKE（拒）
   │
   └─ 通道③ 看板一键确认（人点）→ 落章 + 该门 autoAdvance 推进 + 投递闸门后置链


[阶段3] 门后置链（Phase B，turn/end 时）
   │
   └─→ H1 推进 → H2 压缩 → H3 注入阶段纪律 → H4 唤醒 agent（agent.followup）→ H5 审计
          ⚠ H3 在"非肯定答复"时跳过（FR-10）；H4 仍会唤醒 → 新起一轮


[阶段4] Dive 的自动兜底（**唯一**的"再提醒"来源）
   │
   └─→ agent idle → driveIdle(windowKey, session)
          │
          ├─ 里程碑提醒（时间型，30min）：当前阶段存在"已登记未确认且超时"的产物
          │     └─→ 投递消息「请**立即**调 reqboard_ask_confirm（target=artifact, kind=…）弹框请人确认」
          │           → AgentDeliverer.deliver → agent.followup → **新起一轮** → agent 收到后才可能去弹框
          │           ⚠ 每产物只提醒一次（内存 remindedAt，重启清零）
          │           ⚠D13 候选不过滤 kind → 会选中 notes（笔记文件），命令不可执行
          │
          └─ 阶段纪律投递（⚠F11：采集半直投，绕开 round 半）


[阶段5] 断点汇总（现状为什么"人看不到框"）
   │
   ├─ ⚠D12  产物已确认 → 弹框路径永久早返回；若无人点看板，节点**永远停在原地**（静默）
   ├─ ⚠规则冲突  Dive 说「**立即**调 ask_confirm」，铁律说「弹框超时/中断**不自动重弹**」
   │              → 提醒被纪律吃掉 → 没人保证人会看到框
   └─ ⚠D13  产物确认后候选退化成 notes → 提醒变成"确认一个笔记文件"
```

### FR-14 目标流程（A + 有边界重弹）

```
┌───────────────────────────────────────────────────────────────────────────┐
│        FR-14 目标：Dive 在人工门**主动弹框**（不再依赖 agent 记得去弹）      │
└───────────────────────────────────────────────────────────────────────────┘

[触发] agent idle → driveIdle(windowKey, session)
   │
   └─→ 计算该绑定需求的**门状态** gateFromStage(status)
          │
          ├─ (a) 门要求的产物【未确认】
          │        └─→ 弹「确认产物」框（结论 + 链接 + 推进目标）
          │
          └─ (b) 门要求的产物【已确认】但状态【未推进】
                   └─→ 弹「推进确认」框（肯定项 = 执行该 human-only 转移）
                          ★ 这条正是 D12 的根治：门满足却没人推进时，兜底问人
   │
   ├─ 幂等：同 (需求, 门, 产物指纹) 在**一次等待内**只弹一次（不刷屏）
   ├─ 跨回合可再弹：冷却 ≥ X 分钟、上限 N 次（建议 2），到顶则写台账 comment 停手
   └─ 弹出走**受信内部入口**（只允许 Dive 调用；绕过 idle 期的 live-driver 认证，
      因为 requireLiveDriver 要求 agent.status==='running' 且 currentInitiator()===agent）
          │
          └─→ 人点肯定 → 落章（如需）+ transitionRequirement(actor=human) → 门后置链照常（H1..H5）

[不变量，仍然保留]
   • 「同一产物不重复弹框」对**同一次等待**继续生效（不打扰）
   • 五道人工门仍**只能由人**发起（代码级 human_gate；Dive 只"请人点头"，不代替人做决定）
```

## 缺陷落点索引（REQ-260927100007-b8ba）

> **修复状态列**读法：✅ = 本需求已修并有回归测试锁住；⏳ = 计划内但本页尚未核实；— = 无对应 FR（未纳入本需求）。
> ⚠ 标记的历史实现描述**保留原样**（本页口径：记"当时实测是什么"，便于日后对照），
> 是否已修只看最右列。

| 缺陷 | 节点 | 一句话 | 对应 FR | 修复状态 |
|---|---|---|---|---|
| D1 | decomposing | 批准计划不落库（createdCount=0） | FR-1 | ✅ 批准动作内同步落库 |
| D2 | decomposing | 委托 Dive 但无人监听 → 静默停滞零告警 | FR-2 | ✅ pausedReason + 告警 + 系统评论 |
| D3 | decomposing→implementing | 阶段推进不校验任务完整性 | FR-3 | ✅ 拒绝推进并给修复命令 |
| D4 | decomposing | 条款门禁失败提示给出的恢复命令不可用 | FR-4 | ✅ 提示两条真的能用的路径 |
| D5 | decomposing | reqboard_decompose 返回体不合契约（array vs object） | FR-5 | ✅ 声明与取值对齐（array） |
| D6 | decomposing/implementing | rtm-decomposing.yml 不随任务变更刷新 | FR-6 | ✅ task:status/task:report 补刷新 |
| D7 | implementing | reqboard_task_move / reqboard_move 未注册 | FR-7 | ✅ 两工具已注册（17 个） |
| D8 | implementing | 任务级无收敛点，四处直接写 status | FR-8 | ✅ transitionTask 收敛点 |
| D9 | brainstorming | 确认门挂起期间窗口继续产出下游产物（缺停手守卫） | FR-9 | ✅ REQBOARD_CONFIRM_PENDING |
| D10 | brainstorming | reqboard_status 返回体含 undefined → 绑定窗口必然失败 | FR-10 | ✅ 无记录时省略该键 |
| D11 | 横切（Dive） | 采集半直投会话 → 一条人类消息两轮 loop | FR-11 | ✅ 采集半零投递 + 投递白名单 |
| D12 | brainstorming（确认门） | **文字证据路径只落章不推进**；弹框路径"产物已确认"即早返回 → 门放行但节点**永远停在原地**，agent 无路可走且零指引；证伪 d7 §9.4「需求阶段可纯靠弹框推进」 | FR-13 | ✅ 落章同调用内推进 + reqboard_move 兜底 |

> **D12 详情（2026-09-27 实测）**：用户说「开始推进到设计吧」→ `reqboard_ask_confirm(evidence=…)`
> 落章成功（`confirmedVia=session`、`evidence_verified=true`），状态仍 `brainstorming`；
> 再调弹框路径 → 早返回 `advanced:false`、`note='产物 requirement 已确认，未重复弹框'`（不弹框、不推进）；
> `reqboard_move` 未注册（D7）；看板路由是人通道。**结论：agent 无法推进需求阶段。**

---

| D13 | 横切（里程碑催办） | **提醒把过程产物当门禁产物**：`findStaleUnconfirmedArtifact` 不过滤 kind → 选中 `notes`，文案硬写 `ask_confirm(kind=notes)`；而 `notes` 不在任何门的 `requiredKind`（`ARTIFACT_CONFIRM_GATES` 由五道门的 `requiredKind` 生成）→ 命令与门不匹配 | 待定（无 FR） | — 未纳入本需求，保持嫌疑属实 |

> **D13 详情（2026-09-27 实测）**：连收两条【里程碑提醒】，第 2 条指向
> `kind=notes`（`rtm-brainstorming.yml`，登记 53 分钟未确认），要求调
> `reqboard_ask_confirm(target=artifact, kind=notes)`。
> `MilestoneSpec.findStaleUnconfirmedArtifact` 的判据只有"同阶段 + 未确认 + 超时"，
> **没有"是不是门禁产物"**；而 `notes` 是"过程产物兜底"（自动发现的笔记/原型），
> 不属于任何门的 `requiredKind`。
> ⚠ **未验证的嫌疑**：`confirm-settle` 的推进只看 `advanceTargetFor(from)`、
> 不校验被确认的 kind 是否等于该门的 requiredKind → 照这条命令做
> **可能用一个笔记文件把节点推进**。**我没有执行验证**——因为执行即等于用错误命令推进节点。

## 事件链的两处「崩溃不丢链」补强（2026-09-28，REQ-260928222643-4d34）

一次实机 quick_restart 暴露了两处会在**进程被杀**后把链永久卡死的缺陷，均已修复并加回归测试
（`tests/advance-parent-evidence.test.ts`、`tests/advance-stale-lock.test.ts`，各含正例与反例）：

1. **残留锁回收**：`driveChain` 正常收尾会清 `advance.lockAt/runId`，但进程被杀时 `finally` 不执行，`runId` 会**永久**留下；
   而投递前置检查只看「runId 是否存在」就判「已有 run 在跑」——该需求此后再也无法投递
   （实测恒返回 `REQBOARD_ADVANCE_LOCKED`），连启动恢复扫描 `scanAndResume` 也被同一判断挡下。
   修法：`lockAt` 缺省或已过期即视为残留，显式回收后继续投递（新鲜锁照旧挡并发）。
2. **父卡收尾凭证基准**：done 凭证门的子卡路径早已用「不可变出身」（需求/父卡/子卡 `createdAt` 最小值），
   父卡路径却仍用 `claimedAt`。轻档手工交付（先干活、后认领）时 `claimedAt` 晚于交付文件 mtime，
   父卡在 `FINALIZE_PARENT` 恒被判 `REQBOARD_NO_EVIDENCE`。修法：父子两条证据路径共用 `chainBaselineOf()`
   （不可变出身，窗口单调不后退）。

**另一条实操约束**：重启后的子卡派发需要 **agent 句柄**——启动恢复扫描无 `exec`，子卡会以
「派发缺少 agent 句柄：绑定窗口 <session>」失败并暂停；需由**绑定窗口**再调一次 `reqboard_task_run`
带上 `exec` 才能续跑。

**同源观测**：链懒展开只建 TaskRecord、不落 `tasks/<id>.md` 卡文档；验收门 AC-7.5 要求每卡一份，
需回填。自动展开的子卡验收标准是模板话术（无可执行锚点），会被 `REQBOARD_ACCEPTANCE_NOT_EXECUTABLE` 拦下，
需用 `reqboard_task_move(task_id, acceptance=...)` 改成可复核命令。
## 参考

- 缺陷清单与实测证据：docs/work-logs/2026-09/reqboard-decompose-flow-defects.md、d7-task-move-tool-decision.md
- Dive 契约：[reqboard-dive-mode.md](reqboard-dive-mode.md)
- 代码流程与调用链：[pmboard-code-flow.md](pmboard-code-flow.md)
- RTM 文件格式：[rtm-usage.md](../guides/rtm-usage.md)
