# 测试用例设计（REQ-260927100007-b8ba）

> 每个用例标注 `serves: FR-x`（章节标签门禁要求）与 `validates: FR-x`（模板约定）。
> 形态对齐本仓既有 `tests/transition-guard.test.ts`（表驱动 + 拒绝时断言状态不变）。

## 功能测试用例 <!-- serves: FR-1,FR-2,FR-3 -->

### TC-1: 批准计划即落库（同一调用内） <!-- serves: FR-1 validates: FR-1 -->

**测试目标**：批准带任务表的计划后，**同一调用返回时**台账该需求任务数 = 计划卡数。

**测试步骤**：构造 decomposing 需求 + 已提交计划（3 张卡）→ 调 `reqboard_ask_confirm(target=plan)` 肯定项。

**预期结果**：返回 `advanced=true`；`ledger.tasks` 中该需求任务数 = 3；需求状态 = `implementing`；`autoRun=true`。
**实际文件**：tests/confirm-settle-plan-persist.test.ts

### TC-2: 落库失败不推进且响亮 <!-- serves: FR-2 validates: FR-2 -->

**测试步骤**：让落库步骤抛错（注入失败）→ 调批准路径。
**预期结果**：需求状态**仍是 `decomposing`**；`advance.pausedReason` 非空；
系统评论含原因与恢复命令；`deps.alert` 被调用 1 次。
**实际文件**：tests/confirm-settle-plan-persist.test.ts

### TC-3: 阶段推进的任务完整性守卫 <!-- serves: FR-3 validates: FR-3 -->

**测试步骤**：构造 `plan.tasks.length = 14` 而台账 0 任务 → 推进 `decomposing → implementing`。
**预期结果**：被拒，错误码 `REQBOARD_TASK_INCOMPLETE`，消息含"计划 14 张 / 台账 0 张"与修复命令；
状态不变。反例：`plan.tasks.length = 0` → 放行。
**实际文件**：tests/advance-task-completeness-guard.test.ts

## 数据契约测试用例 <!-- serves: FR-4,FR-5,FR-10 -->

### TC-4: 条款门禁失败提示与实际可用路径一致 <!-- serves: FR-4 validates: FR-4 -->

**测试步骤**：已批准计划、无任何 FR 对照 → 调 `reqboard_decompose`。
**预期结果**：拒绝码 `requirement_uncovered`；`how` 同时给出
① `decomposition.md` 覆盖对照表 ② 显式 `tasks` + `requirement_refs` 两条路径与参数示例；
**不含**"给任务卡加 requirement_refs"这类恢复时刻不可执行的说法。
**实际文件**：tests/clause-coverage-gate.test.ts

### TC-5: reqboard_decompose 返回体契约合法 <!-- serves: FR-5 validates: FR-5 -->

**测试步骤**：成功落库后按工具 output schema 校验返回值。
**预期结果**：`task_coverage` 为数组且 item 字段齐全；`coverage_check` 为对象；schema 校验零错误。
**实际文件**：tests/tools-schema.test.ts、tests/decompose-tools.test.ts

### TC-6: reqboard_status 返回体 lossless <!-- serves: FR-10 validates: FR-10 -->

**测试步骤**：已绑定窗口调 `reqboard_status`（无 RTM 失败记录）。
**预期结果**：返回体递归扫描**无 `undefined` 值属性**；`success=true`（当前必然抛 not lossless JSON）。
**实际文件**：tests/status-lossless.test.ts

## 集成测试用例 <!-- serves: FR-6,FR-7,FR-8,FR-9,FR-11,FR-12,FR-13 -->

### TC-7: RTM 刷新集合随任务变更 <!-- serves: FR-6 validates: FR-6 -->

**测试步骤**：先批准计划生成 RTM，再调一次任务状态变更；对比 `rtm-decomposing.yml` 的 mtime 与覆盖度读数。
**预期结果**：`filesForTrigger('task:status')` 含 `rtm-decomposing.yml`；实施覆盖度随任务变化。
**实际文件**：packages/tools/reqboard/tests/rtm/triggers.test.ts

### TC-8: agent 侧任务流转工具注册并可用 <!-- serves: FR-7 validates: FR-7 -->

**测试步骤**：`apply()` 后枚举工具名；用 `reqboard_task_move` 把 todo 卡推到 in_progress。
**预期结果**：期望集合 = 实际 **17** 个（含 `reqboard_move` / `reqboard_task_move` / `clear_pause` / `run_status`）；
转移成功且 `executions` 开段。同时修好该测试的装配 stub（当前因 `ReqboardDiveManager extends Service` 抛错而未断言）。
**实际文件**：tests/apply-wiring.test.ts

### TC-9: transitionTask 拦截非法流转 <!-- serves: FR-8 validates: FR-8 -->

**测试步骤**：表驱动遍历合法/非法/人工门/越权四类。
**预期结果**：非法转移抛 `invalid_transition`、人工门对 agent/system 抛 `human_gate`、
`system` 白名单外抛 `system_gate`；**拒绝时 `status/version/updatedAt` 全部不变**；
`allowIllegalTransition: true` 可跳过（迁移用）。
**实际文件**：tests/task-transition-guard.test.ts

### TC-10: 四处写入点统一经收敛点 <!-- serves: FR-8 validates: FR-8 -->

**测试步骤**：静态扫描业务路径。
**预期结果**：`ExecuteTask` / `AdvanceChain` / `failure-handling` / `http/routers/tasks` 中
**无**直接 `status = ` 赋值（收敛点自身与迁移脚本除外）。
**实际文件**：tests/task-transition-guard.test.ts

### TC-11: 挂起确认期间写路径被拒 <!-- serves: FR-9 validates: FR-9 -->

**测试步骤**：`ask_confirm` 超宽限返回 pending → 同窗口调 `reqboard_submit`。
**预期结果**：拒绝码 `REQBOARD_CONFIRM_PENDING`、消息含 `reqboard_confirm_receipt(ticket=…)`；
**不写盘**；`reqboard_status` / `reqboard_confirm_receipt` 仍可用。
**实际文件**：tests/confirm-pending-guard.test.ts

### TC-12: 采集半零投递（Dive 与设计一致） <!-- serves: FR-11 validates: FR-11 -->

**测试步骤**：同一阶段连续两条直接人类消息 → 观察 `onStagePrompt` / `agent.followup` 调用次数。
**预期结果**：`onStagePrompt` **0 次**（纪律只经 system prompt）；`agent.followup` 不产生额外轮次；
非 armed 时里程碑催办只写 comment、不投递；armed+active 时 round 半投递且 `source.kind='dive'`。
**实际文件**：tests/dive-manager-alignment.test.ts、tests/dive-round-driver.test.ts

### TC-13: 窗口绑定投影可更新且有消费者 <!-- serves: FR-12 validates: FR-12 -->

**测试步骤**：先建需求 → 再用 bind 绑定窗口 → 读 `rtm-lifecycle.yml`。
**预期结果**：绑定后 `requirement.source_session` 随之更新（`bind` 触发点）；
`grep` 该字段的**读取方非空**（或类型层如实声明无消费者）；靠窗口侧锚点绑定的需求也能表示。
**实际文件**：packages/tools/reqboard/tests/rtm/triggers.test.ts

### TC-14: 文字证据确认后同一调用内推进 <!-- serves: FR-13 validates: FR-13 -->

**测试步骤**：`reqboard_ask_confirm(evidence="开始推进到设计吧")`（命中真实用户消息）。
**预期结果**：落章 + **需求状态 brainstorming → design**（同一调用内）；
若因守卫/人工门不推进 → `advanced:false` + 明确原因 + 可执行命令（不得沉默）。
**实际文件**：tests/confirm-evidence-advance.test.ts

### TC-15: Dive 在人工门主动弹框（有边界重弹） <!-- serves: FR-14 validates: FR-14 -->

**测试步骤**：构造绑定需求处于 brainstorming 且 requirement 产物**已确认但状态未推进** → 触发 agent idle。
**预期结果**：Dive 经 `GatePromptPort` 弹「推进确认」框（`kind='plan'` 语义的推进确认）；
人点肯定 → 状态推进 + 门后置链照常；同一次等待内**只弹 1 次**；
再触发 idle 2 次（跨回合）→ 冷却内不弹、超冷却后最多再弹 1 次（上限 2）；
到顶后写台账 comment 并停手；`GatePromptPort` 未装配 → 行为与改动前逐字一致（只投提醒消息）。
**实际文件**：tests/dive-gate-prompt.test.ts

## 覆盖度统计 <!-- serves: FR-1,FR-2,FR-3,FR-4,FR-5,FR-6,FR-7,FR-8,FR-9,FR-10,FR-11,FR-12,FR-13,FR-14 -->

| 需求条款 | 测试用例 | 覆盖状态 |
|---|---|---|
| FR-1 | TC-1 | 已覆盖 |
| FR-2 | TC-2 | 已覆盖 |
| FR-3 | TC-3 | 已覆盖 |
| FR-4 | TC-4 | 已覆盖 |
| FR-5 | TC-5 | 已覆盖 |
| FR-6 | TC-7 | 已覆盖 |
| FR-7 | TC-8 | 已覆盖 |
| FR-8 | TC-9, TC-10 | 已覆盖 |
| FR-9 | TC-11 | 已覆盖 |
| FR-10 | TC-6 | 已覆盖 |
| FR-11 | TC-12 | 已覆盖 |
| FR-12 | TC-13 | 已覆盖 |
| FR-13 | TC-14 | 已覆盖 |
| FR-14 | TC-15 | 已覆盖 |
