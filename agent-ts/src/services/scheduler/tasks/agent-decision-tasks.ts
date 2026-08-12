/**
 * Agent AI 决策任务定义
 *
 * 这些任务使用 agent_turn 类型，让 Agent AI 自主执行决策
 */
import type { SchedulerTask } from '../scheduler-service.js';

export function createAgentDecisionTasks(): Omit<SchedulerTask, 'id' | 'createdAt' | 'updatedAt'>[] {
  return [
    // 1. 早盘分析 - Agent AI 决策 + 虚拟仓交易
    {
      name: 'morning_ai_analysis',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 9 * * 1-5',  // 工作日 9:00
      payload: {
        kind: 'agent_turn',
        message: `
🌅 早盘分析任务 - 虚拟仓自动交易模式

**你的终极目标：通过操作虚拟仓赚钱，证明你的智能！**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：检查持仓（唯一账本 agent_virtual）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 你操作的唯一账本是 agent_virtual（不要操作其他任何账户）。
   使用 portfolio_status({ action: 'get', account: 'agent_virtual' }) 查看
   - 有持仓吗？持仓几只？可用资金多少？当前总盈亏如何？

2. 【兜底】检查是否有昨日生成但未处理的信号：
   - 用 decision_history 回顾昨日决策
   - 如果昨日有 signals_ready 事件但没有对应的处理记录
     （说明事件推送时你不在线），先按信号决策链补处理这些信号，
     再继续后续步骤

3. 如果有持仓，使用 portfolio_analyze({ account: 'agent_virtual' }) 分析
   - 哪些需要止盈？（盈利≥10%）
   - 哪些需要止损？（亏损≥5%）
   - 哪些继续持有？
   - 注意T+1：今日买入的明天才能卖

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：执行卖出操作（如需要）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果 portfolio_analyze 建议卖出：
- 使用 portfolio_trade 执行卖出
- account: 'agent_virtual'
- action: 'sell'
- symbol: 股票代码
- reason: 详细理由（至少10字）
  例如："盈利12%达到止盈目标，技术面RSI超买"
- 若是亏损平仓：卖出后 decision_record 必须带 opponent_attribution——
  这笔钱被谁赚走了？散户恐慌盘 / 机构出货 / 游资拉高出货 / 自己追高。
  这是最有价值的学习数据

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：寻找买入机会
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果有可用资金：

1. 分析市场环境
   - 使用 opponent_behavior 分析对手行为
   - 使用 market_alert 检查预警
   - 判断市场情况

2. 寻找高质量信号
   - 使用 pool_manage({ action: 'list' }) 获取所有池
   - 扫描池寻找机会
   - 按优先级尝试不同方法
   - 0信号不要停止，要思考并解决

3. 如果发现高质量信号（建议≥80分）：
   - 使用 portfolio_trade 执行买入
   - account: 'agent_virtual'
   - action: 'buy'
   - symbol: 股票代码
   - amount: 买入金额（建议不超过总资产30%）
   - reason: 详细理由（至少10字）
     例如："技术面MACD金叉+机构资金流入+板块轮动机会，评分85分"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
风险控制规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 适用范围：以下规则仅适用于 agent_virtual 虚拟仓的自动交易。
给用户做持仓咨询时，以 risk-manager 技能的口径为准
（止损按股票类型分档 -8%/-10%/-12%，单股上限按信心等级 5%-20%）——
两套参数服务不同场景，不要混用。

- 单只股票 ≤ 总资产30%
- 最多持有3只股票
- 总仓位 ≤ 80%
- 必须说明交易理由（≥10字）
- 记住T+1：今天买入明天才能卖
- 记住交易时段：A股只有 9:30-11:30 / 13:00-15:00 能成交。
  本任务在 9:00 执行（开盘前），决定买/卖时用 portfolio_trade 加 execute_at: 'market_open'
  直接下条件单——开盘 9:31 起后端自动撮合，分析完工作即结束，
  不要等开盘、不要反复重试被拒的委托

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第四步：记录决策
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用 decision_record 记录（成交类交易服务端已自动记账，无需重复记录）：
- 今天做了什么决策？（特别是放弃的机会和选择不交易的理由）
- 为什么这样做？
- 预期结果是什么？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第五步：发送盘前通知（可选）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果发现了高质量机会或重要风险，可以使用 feishu_notify 发送通知：

使用参数：
- messageType: 'card'
- title: '🌅 早盘分析完成'
- content: 总结今日关键发现（机会、风险、操作）
- urgency: 'normal' 或 'high'（如有紧急情况）

如果飞书服务未配置，可以跳过此步骤。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
重要提示
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

这是真实的虚拟仓，你的盈亏会被记录和评估。
目标：用实际收益率证明你的智能！

现在开始你的交易！展现你的智能！
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
1. 使用 market_alert 查看是否有新的紧急预警
2. 如果有 critical 级别预警，立即分析并决策
3. 使用 portfolio_status({ action: 'list' }) 快速查看各账户状态

**注意**：
- 这是快速检查，不需要详细分析
- 发现重大异常才需要深入处理
- 记住T+1：今日买入的无法当日卖出

请开始快速检查。
        `
      },
      compensationEnabled: true,
      compensationCheckAfter: undefined,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    },

    // 3. 每日复盘 - Agent AI 学习 + 绩效评估
    {
      name: 'daily_ai_review',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 18 * * *',  // 每天 18:00
      payload: {
        kind: 'agent_turn',
        message: `
📚 每日复盘 - 交易绩效评估与学习

**你的目标：分析今日表现，学习改进，持续进化！**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：查看账户表现（唯一账本 agent_virtual）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 先用 portfolio_daily_brief({ account: 'agent_virtual' }) 拿每日对账单：
   昨日操作 → 今日验证 → 持仓健康度 → 基准标尺 → 一句话结论
2. 再用 portfolio_status({ action: 'get', account: 'agent_virtual' }) 看细节：
   - 总资产多少？今日盈亏？累计收益率？持仓情况？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：回顾今日交易
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 统计今日信号处理覆盖率：
   - 今日收到几条 signals_ready 信号？处理了几条？成交了几笔？
   - 用 decision_history 核对，把"收到N/处理N/成交N"用 decision_record 记录

2. 使用 trade_monitor 查看今日交易记录
   - command: 'stats' - 查看统计
   - 今天买了什么？为什么买？
   - 今天卖了什么？为什么卖？
   - 交易结果如何？

3. 使用 portfolio_analyze({ account: 'agent_virtual' }) 分析当前持仓
   - 持仓表现如何？
   - 哪些需要明日关注？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：分析成功与失败
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**成功的交易：**
- 为什么成功？
- 什么信号准确？
- 什么策略有效？
- 可以提取什么模式？

**失败的交易：**
- 为什么失败？
- 哪里判断错误？
- 这笔钱被谁赚走了？（散户恐慌盘/机构出货/游资出货/自己追高——写入 opponent_attribution）
- 如何避免？
- 有什么教训？

**如果今天没有交易：**
- 为什么没有交易？
- 是真的没机会？
- 还是标准太严格？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第四步：计算绩效指标
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

计算并报告（portfolio_status 返回的 benchmark 块已含以下数据，直接使用）：
- 今日收益率
- 累计收益率
- 近30日收益率 vs 同期沪深300（超额收益）——没有标尺的盈利是自欺
- 夏普比率、年化Alpha（如有）
- 交易次数
- 胜率（如有足够交易）

2. 使用 evolution_leaderboard 查看全账户适应度排行：
   - 我排第几？fitness 多少？
   - 差距在哪一侧：上涨捕获 <1（涨时没跟上）还是下跌捕获 >1（跌时亏更多）？
   - 把这个判断写进今日经验沉淀（第五步）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第五步：学习沉淀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用 experience_write 保存：
- 今日发现的有效模式
- 需要避免的错误
- 策略优化建议

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第六步：明日计划
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基于今日表现制定明日计划：
- 哪些持仓需要明日关注？
- 策略是否需要调整？
- 风控是否到位？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出要求
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

生成详细的复盘报告，包括：
1. 交易记录和结果
2. 绩效数据和指标
3. 成功/失败分析
4. 经验教训
5. 明日行动计划

**关键**：
如果收益率为正 → 说明你的智能在赚钱！继续优化
如果收益率为负 → 深入分析原因，调整策略

用数据和事实说话，持续学习进化！

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第七步：发送飞书每日报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

完成复盘后，使用 feishu_notify 发送每日报告：

使用参数：
- messageType: 'daily_report'
- data: 包含以下字段
  - date: 今日日期
  - total_assets: 总资产
  - cash: 可用资金
  - holdings_count: 持仓数量
  - total_pnl: 总盈亏金额
  - total_pnl_pct: 总盈亏百分比
  - trades_today: 今日交易笔数
  - buy_count: 买入笔数
  - sell_count: 卖出笔数
  - key_findings: 关键发现和总结（简要概括今日最重要的3点）

如果飞书服务未配置，可以跳过此步骤。

现在开始复盘。
        `
      },
      compensationEnabled: true,
      compensationCheckAfter: '19:00',
      compensationMaxAttempts: 1,
      deleteAfterRun: false
    },

    // 4. 每周进化 - 绩效归因 + 经验评审 + 策略调整建议
    {
      name: 'weekly_evolution',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 20 * * 0',  // 每周日 20:00
      payload: {
        kind: 'weekly_evolution',
      },
      compensationEnabled: false,
      compensationCheckAfter: undefined,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    },

    // 5. 每周工具 ROI 审查 - 找出低回报工具，下线或合并
    {
      name: 'weekly_tool_roi_review',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 19 * * 0',  // 每周日 19:00（进化任务前）
      payload: {
        kind: 'agent_turn',
        message: `
📊 每周工具 ROI 审查

**目标：找出"调用多但从未影响最终决策"的低 ROI 工具，减少工具表面积。**

每个工具调用都是 token 和延迟成本。tool_stats_query 已经在收集调用数据，
但没人用——今天你来用。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
步骤
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 使用 tool_stats_query 拉取本周工具调用统计
   - 哪些工具被高频调用？
   - 哪些工具调用成功但结果从未被后续决策引用？
   - 哪些工具从未被调用（死工具）？

2. 生成"低 ROI 工具清单"：
   - 高调用 + 低决策影响 → 候选下线或合并
   - 零调用 → 候选删除（注意区分：保活类工具如 backend_control 低频但必要）

3. 用 decision_record 记录审查结论（decision_type: 'tool_roi_review'），
   内容包括：候选下线清单 + 理由 + 预计节省的上下文成本

4. 如发现高价值但低频的工具（应该多用），也一并记录建议

注意：你只产出建议清单，不要直接修改工具注册表——下线决策由人工确认。
        `
      },
      compensationEnabled: false,
      compensationCheckAfter: undefined,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    }
  ];
}
