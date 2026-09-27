# 用例设计（REQ-260927100007-b8ba）

> 每个场景标注 `serves: FR-x`。主流程 + 异常/边界各一条，覆盖 13 条 FR。

## UC-1: 人批准计划（含同步落库） <!-- serves: FR-1,FR-2,FR-3 -->

**谁**：需求提出者。**何时**：拆分计划已提交、待批准。**做什么**：看板点「批准计划」或弹框肯定项。

**期望**：同一调用内落章 → 落库任务卡 → 进 implementing + `autoRun=true`；
返回时台账任务数 = 计划卡数。**异常**：落库失败 → 停在 decomposing、写 `pausedReason`、发告警、给恢复命令。

## UC-2: 计划有卡而台账 0 卡时被拦 <!-- serves: FR-3 -->

**谁**：窗口 agent（或看板移动）。**何时**：历史事故后的脏状态。

**期望**：推进 `decomposing → implementing` **被拒**，报错含"计划 N 张 / 台账 0 张"与两条修复命令；状态不变。

## UC-3: 恢复路径真的可用 <!-- serves: FR-4,FR-5 -->

**谁**：窗口 agent。**何时**：批准后未落库、需要手动重试。

**期望**：`reqboard_decompose` 的拒绝提示给出两条**真的能用**的路径与参数示例；
成功时返回体与工具 schema 一致（不再 `returned invalid output`）。

## UC-4: agent 自主推进任务链 <!-- serves: FR-6,FR-7,FR-8 -->

**谁**：窗口 agent / Dive 驱动的 agent。**何时**：实施阶段。

**期望**：`reqboard_task_move` 把卡从 `todo` 推到 `in_progress`/…/`done`；
每次流转都经 `transitionTask`，非法/越权被拒且状态不变；
任务变化后 `rtm-decomposing.yml` 随 `rtm-implementing.yml` 一起刷新。

## UC-5: 确认门挂起期间不产出下游产物 <!-- serves: FR-9,FR-10 -->

**谁**：窗口 agent。**何时**：`ask_confirm` 超宽限返回 pending、人尚未作答。

**期望**：同窗口写路径工具被代码级拒绝并给出取回执命令；
`reqboard_status` 可用且返回体 lossless（否则 agent 连回执都读不到）。

## UC-6: Dive 按设计投递 <!-- serves: FR-11 -->

**谁**：Dive 采集半 / round 半。**何时**：agent 空闲。

**期望**：采集半只采集/簿记/记录，**零投递**（阶段纪律已在每次 system prompt）；
只有 `armed + active` 时 round 半才投递回合消息（`source.kind='dive'` + 预留 + 准入计数）；
里程碑催办非 armed 时只写 comment。

## UC-7: 绑定窗口后 RTM 随之更新 <!-- serves: FR-12 -->

**谁**：维护者 / Dive。**何时**：需求先建后绑、或绑定变更。

**期望**：绑定动作触发 `rtm-lifecycle.yml` 刷新，`requirement.source_session` 与新绑定一致；
该字段存在**真实读取方**（或如实声明无消费者，不再有"注释说 Dive 读它"的假话）。

## UC-8: 文字证据确认后立即推进 <!-- serves: FR-13 -->

**谁**：人在对话里说"确认/推进"。**何时**：任一阶段产物确认。

**期望**：`reqboard_ask_confirm(evidence=…)` 落章 + **同一调用内**推进；
若不推进，返回明确原因与可执行命令——不留"已落章但节点永远停在原地"的静默死锁。
