/**
 * Agent AI 决策任务定义
 *
 * 这些任务使用 agent_turn 类型，让 Agent AI 自主执行决策
 */
import type { SchedulerTask } from '../scheduler-service.js';

export function createAgentDecisionTasks(): Omit<SchedulerTask, 'id' | 'createdAt' | 'updatedAt'>[] {
  return [
    // 1. 早盘分析 - Agent AI 决策
    {
      name: 'morning_ai_analysis',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 9 * * 1-5',  // 工作日 9:00
      payload: {
        kind: 'agent_turn',
        message: `
🌅 早盘分析时间！请执行以下任务：

**背景**：
现在是交易日早上 9:00，市场即将开盘。你需要分析市场情况，制定今日交易策略。

**可用工具**：
- opponent_behavior - 分析对手行为（散户/机构/游资）
- alert_check - 检查博弈预警
- pool_list - 获取所有池子
- pool_battlefield - 评估池子战场
- manipulation_detect - 检测操纵风险
- knowledge_query - 查询知识库
- decision_record - 记录决策

**任务流程**：

1. **分析市场对手行为**
   使用 opponent_behavior 工具分析：
   - 散户情绪如何？是恐慌还是贪婪？
   - 机构在做什么？吸筹还是派发？
   - 游资是否活跃？

2. **检查预警信号**
   使用 alert_check 工具检查：
   - 有哪些紧急预警？
   - 风险等级如何？

3. **评估现有池子**
   使用 pool_list 获取所有池子，对每个池子：
   - 使用 pool_battlefield 评估战场情况
   - 判断：是否需要调整或关闭？

4. **寻找新机会**
   基于对手行为分析：
   - 有哪些潜在机会？
   - 使用 manipulation_detect 检查风险
   - 使用 knowledge_query 查询相关知识
   - 决策：是否创建新池子？

5. **制定今日策略**
   综合以上信息：
   - 今日重点关注什么？
   - 需要采取什么行动？
   - 风险控制措施是什么？

6. **记录决策**
   使用 decision_record 记录你的决策和理由

**输出要求**：
- 给出明确的操作建议
- 说明你的分析逻辑
- 标注置信度
- 如果发现重大机会或风险，使用通知服务发送飞书通知

请开始执行早盘分析。
        `
      },
      compensationEnabled: true,
      compensationCheckAfter: '09:30',
      compensationMaxAttempts: 2,
      deleteAfterRun: false
    },

    // 2. 实时监控（简化版 - 快速检查）
    {
      name: 'realtime_quick_check',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '*/30 9-14 * * 1-5',  // 工作日 9:00-14:55，每30分钟
      payload: {
        kind: 'agent_turn',
        message: `
⚡ 盘中快速检查！

**任务**：
快速检查当前市场状态，发现异常立即处理。

**检查项**：
1. 使用 alert_check 查看是否有新的紧急预警
2. 如果有 critical 级别预警，立即分析并决策
3. 快速浏览池子状态（不需要详细分析）

**输出**：
- 如有紧急情况，说明并采取行动
- 如无异常，简单确认即可

保持简短，这是快速检查。
        `
      },
      compensationEnabled: false,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    },

    // 3. 每日复盘 - Agent AI 学习
    {
      name: 'daily_ai_review',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 18 * * *',  // 每天 18:00
      payload: {
        kind: 'agent_turn',
        message: `
📚 每日复盘时间！请进行今日的学习和总结：

**背景**：
交易日已结束，现在是复盘时间。你需要评估今日决策，提取经验教训。

**可用数据**：
- quantsys-v2 后台已完成今日数据处理
- 调用 GET http://localhost:5001/api/scheduler/runs 查看今日任务执行
- 调用 GET http://localhost:5001/api/signals/today 查看今日信号（如果有API）

**任务流程**：

1. **查看今日决策**
   - 今天做了哪些决策？
   - 创建了哪些池子？
   - 调整了哪些仓位？

2. **评估决策效果**
   - 今天的信号准确率如何？
   - 哪些决策是对的？哪些是错的？
   - 为什么会出现这些结果？

3. **分析成功案例**
   - 成功的决策有什么共同特征？
   - 什么因素导致了成功？
   - 可以提取什么模式？

4. **分析失败案例**
   - 失败的决策错在哪里？
   - 如何避免类似错误？
   - 有什么教训？

5. **知识提取**
   使用 knowledge_record（如有）记录：
   - 今日发现的新模式
   - 需要注意的风险
   - 值得复用的策略

6. **明日改进方向**
   - 明天需要注意什么？
   - 哪些策略需要调整？
   - 风控是否需要优化？

**输出要求**：
- 给出详细的复盘报告
- 标注关键经验教训
- 提出明确的改进建议
- 使用通知服务发送每日报告到飞书

请开始每日复盘。
        `
      },
      compensationEnabled: true,
      compensationCheckAfter: '19:00',
      compensationMaxAttempts: 1,
      deleteAfterRun: false
    }
  ];
}
