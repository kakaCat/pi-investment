# 用例设计

**需求**: REQ-260925234037-1503  
**版本**: 1.0  
**更新**: 2026-09-25



### UC-1: Agent 创建需求（Dive Armed 唯一模式） `serves: FR-2`

**角色**：Agent

**前置条件**：
- Agent 识别到新工作意图
- 值得立项

**主流程**：

1. Agent 调用 `reqboard_create` 或 `reqboard_capture`
   ```typescript
   const result = await tools.reqboard_create({
     title: '实现新功能',
     category: 'feature',
     summary: '功能描述...'
     // 不再有 dive_mode 参数
   })
   ```

2. 系统创建需求，固定设置 `dive.activation = 'armed'`

3. 系统返回需求信息
   ```typescript
   {
     success: true,
     requirement_id: 'REQ-...',
     status: 'brainstorming',
     // dive 固定为 armed
   }
   ```

4. Agent 继续需求分析工作

**后置条件**：
- ✅ 需求已创建，状态为 brainstorming
- ✅ dive.activation = 'armed'
- ✅ DiveManager 将自动续跑此需求

**异常流程**：
- 无（固定为 armed，无参数选择）

---



### UC-2: Agent 执行任务（只用 task_run） `serves: FR-1, FR-2`

**角色**：Agent

**前置条件**：
- 需求处于 implementing 阶段
- 有 ready 状态的父卡

**主流程**：

1. Agent 检查任务状态
   ```typescript
   const status = await tools.reqboard_status({})
   // 查看任务列表，找到 ready 的父卡
   ```

2. Agent 调用 `reqboard_task_run` 执行父卡
   ```typescript
   const result = await tools.reqboard_task_run({
     task_id: 't-abc123'  // 父卡 ID
   })
   ```

3. 系统自动执行父卡下的子卡链
   - 按 depends_on 顺序执行
   - 一次执行一个 ready 的子卡
   - 子卡完成后自动推进到下一个

4. 所有子卡完成后，父卡自动汇总收尾

5. 所有父卡完成后，需求自动推进到 accepting

**后置条件**：
- ✅ 任务执行完成
- ✅ 无需调用 task_move（已删除）
- ✅ 需求自动推进

**异常流程**：

A. **子卡执行失败**
   1. Dive 流程暂停（phase = paused）
   2. Agent 收到暂停通知
   3. Agent 分析失败原因
   4. Agent 修复问题
   5. Agent 调用 `clear_pause` 恢复
   6. 继续执行

---



### UC-3: Agent 紧急干预（break glass） `serves: FR-1, FR-2`

**角色**：Agent

**前置条件**：
- Dive 流程异常（phase = paused）
- 或需要人工干预

**主流程**：

1. Agent 发现流程暂停
   ```typescript
   const status = await tools.reqboard_status({})
   const req = status.open_requirements[0]
   
   if (req.dive.phase === 'paused') {
     console.log('流程已暂停:', req.dive.pausedReason)
   }
   ```

2. Agent 分析暂停原因
   - 达到 maxRounds 限制
   - 任务执行失败
   - 其他异常

3. Agent 采取修复措施
   - 修改代码
   - 调整配置
   - 清理错误状态

4. Agent 调用 `clear_pause` 恢复流程
   ```typescript
   const result = await tools.reqboard_clear_pause({
     requirement_id: 'REQ-...',
     reason: '已修复任务执行错误，恢复流程'
   })
   ```

5. 系统恢复 Dive 流程
   - phase: paused → idle
   - roundsInStage 重置为 0
   - DiveManager 继续续跑

**后置条件**：
- ✅ 流程已恢复
- ✅ DiveManager 继续自动续跑

**使用频率**：低频（仅在异常时使用）

---



### UC-4: Agent 尝试调用已删除工具（错误引导） `serves: FR-4`

**角色**：Agent

**前置条件**：
- Agent 尝试调用已删除的工具
- 可能是旧习惯或系统提示词未更新

**主流程**：

1. Agent 尝试调用 `reqboard_decompose`
   ```typescript
   try {
     await tools.reqboard_decompose({
       requirement_id: 'REQ-...'
     })
   } catch (error) {
     // 捕获错误
   }
   ```

2. 系统返回友好错误
   ```json
   {
     "error": "unknown tool: reqboard_decompose",
     "message": "工具 reqboard_decompose 已删除。\n建议使用 reqboard_task_run 替代。\nDive Armed 模式下会自动拆分需求。"
   }
   ```

3. Agent 理解错误消息

4. Agent 改用正确工具
   ```typescript
   // 改用 task_run
   await tools.reqboard_task_run({ task_id: '...' })
   ```

**后置条件**：
- ✅ Agent 学会使用正确工具
- ✅ 系统提示词可能需要更新

**异常流程**：
- 如果 Agent 持续调用已删除工具，需要更新系统提示词

---



### UC-5: 用户查看 Dive 文档（Dive-first 方案） `serves: FR-5`

**角色**：人工用户

**前置条件**：
- 用户想了解 REQ 流水线工作方式

**主流程**：

1. 用户打开 `docs/guides/dive-mode-usage.md`

2. 用户看到 Dive-first 方案
   - 只介绍 Dive Armed 模式
   - 不提及 disarmed 或手动模式
   - 强调自动化工作流程

3. 用户了解工具使用频率
   - **高频**：reqboard_status, reqboard_task_run
   - **中频**：reqboard_submit, reqboard_ask_confirm
   - **低频**：reqboard_clear_pause（仅异常时）

4. 用户了解完整流程
   - brainstorming → design → decomposing → implementing → accepting → archived
   - 每个阶段的人工决策点
   - 自动推进的条件

**后置条件**：
- ✅ 用户理解 Dive Armed 工作方式
- ✅ 用户知道何时需要干预

**不再提供的信息**：
- ❌ 如何创建 disarmed 需求
- ❌ armed vs disarmed 对比
- ❌ 手动工具使用说明

---



### UC-6: 验收通过自动归档 `serves: FR-1, FR-2`

**角色**：Agent + DiveManager

**前置条件**：
- 需求处于 accepting 阶段
- 所有验收项已通过

**主流程**：

1. Agent 提交验收材料
   ```typescript
   await tools.reqboard_submit({
     kind: 'verification',
     summary: '交付完成，所有测试通过',
     evidence: [
       '单元测试：全部通过',
       'E2E 测试：全部通过',
       '文档已更新'
     ]
   })
   ```

2. 人工验收通过（在看板上勾选全部通过）

3. 系统检测到验收通过
   - accepting.autoExecute = true
   - 所有验收项 status = passed

4. **DiveManager 自动推进到 archived**
   - 无需 Agent 调用 `reqboard_move`
   - 无需人工点击推进按钮

5. 需求完成，状态变为 archived

**后置条件**：
- ✅ 需求已归档
- ✅ Dive 流程完整闭环
- ✅ 无需手动推进

**对比旧流程**：

**旧流程**（accepting.autoExecute = false）：
```
验收通过 → Agent 手动调用 reqboard_move → archived
```

**新流程**（accepting.autoExecute = true）：
```
验收通过 → 自动归档 → archived
```

---



### UC-7: 完整 Dive Armed 工作流程 `serves: FR-2`

**角色**：Agent + 人工用户

**前置条件**：
- 识别到新工作意图

**完整流程图**：

```
┌─────────────────────────────────────────────────────────┐
│  1. 立项（Agent）                                        │
│     reqboard_create / reqboard_capture                  │
│     → dive.activation = 'armed' (固定)                  │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  2. 需求分析（Agent）                                    │
│     编写 requirement.md                                  │
│     reqboard_submit(kind='requirement')                 │
│     reqboard_ask_confirm(kind='requirement')            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼ (人工确认)
┌─────────────────────────────────────────────────────────┐
│  3. 设计（Agent）                                        │
│     编写设计文档（5份）                                  │
│     reqboard_submit(kind='design')                      │
│     reqboard_ask_confirm(kind='design')                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼ (人工确认)
┌─────────────────────────────────────────────────────────┐
│  4. 拆分（Agent）                                        │
│     编写 decomposition.md + 任务表                       │
│     reqboard_submit(kind='plan')                        │
│     reqboard_ask_confirm(target='plan')                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼ (人工批准)
┌─────────────────────────────────────────────────────────┐
│  5. 自动拆分落库（DiveManager）                          │
│     jobs.start 后台拆分                                  │
│     任务写入数据库                                        │
│     需求推进到 implementing                              │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  6. 实施（Agent，只用 task_run）                         │
│     reqboard_task_run(父卡) → 自动执行子卡链            │
│     不调用 decompose / move / task_move (已删除)        │
│     任务完成 → 自动推进到 accepting                      │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  7. 验收（Agent + 人工）                                 │
│     reqboard_submit(kind='verification')                │
│     人工验收通过                                          │
│     accepting.autoExecute=true → 自动归档 (FR-6)        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  8. 完成（archived）                                     │
│     需求已归档，Dive 流程完整闭环                        │
└─────────────────────────────────────────────────────────┘
```

**人工决策点**（5个）：
1. 需求分析确认（requirement.md）
2. 设计确认（design/*.md）
3. 拆分计划批准（decomposition.md + 任务表）
4. 验收（勾选验收项）
5. 归档材料审批（可选）

**自动推进点**（4个）：
1. 需求确认 → design
2. 设计确认 → decomposing
3. 计划批准 → implementing（自动拆分落库）
4. 验收通过 → archived（FR-6 新增）

**关键变化**：
- ✅ 全流程无需调用已删除工具
- ✅ 只用 task_run 完成任务执行
- ✅ 验收通过自动归档

---

## 工具使用频率表 <!-- serves: FR-5 -->

| 工具 | 频率 | 用途 | 备注 |
|------|------|------|------|
| `reqboard_create` | 低频 | 创建需求 | 每个需求一次 |
| `reqboard_capture` | 低频 | 立项弹框 | 每个需求一次 |
| `reqboard_status` | 高频 | 查看状态 | 每个阶段多次 |
| `reqboard_submit` | 中频 | 提交产物 | 每个阶段一次 |
| `reqboard_ask_confirm` | 中频 | 请求确认 | 每个阶段一次 |
| `reqboard_task_run` | 高频 | 执行任务 | 实施阶段核心工具 |
| `reqboard_task_report` | 中频 | 任务汇报 | 任务完成时 |
| `reqboard_clear_pause` | 低频 | 紧急干预 | 仅异常时 |
| `reqboard_accept_sheet` | 低频 | 逐项验收 | 验收阶段 |
| ~~`reqboard_decompose`~~ | ❌ 已删除 | - | 用 task_run 替代 |
| ~~`reqboard_move`~~ | ❌ 已删除 | - | 自动推进 |
| ~~`reqboard_task_move`~~ | ❌ 已删除 | - | 自动执行 |

---

## 用例优先级 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->


### P0（必须实现） `serves: FR-1, FR-2`
- UC-1: Agent 创建需求（Dive Armed 唯一模式）
- UC-2: Agent 执行任务（只用 task_run）
- UC-6: 验收通过自动归档
- UC-7: 完整 Dive Armed 工作流程


### P1（重要） `serves: FR-1, FR-2`
- UC-3: Agent 紧急干预（break glass）
- UC-4: Agent 尝试调用已删除工具（错误引导）


### P2（文档） `serves: FR-5`
- UC-5: 用户查看 Dive 文档（Dive-first 方案）