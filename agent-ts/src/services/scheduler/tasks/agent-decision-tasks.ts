/**
 * Agent AI 决策任务定义
 *
 * 这些任务使用 agent_turn 类型，让 Agent AI 自主执行决策
 */
import type { SchedulerTask } from '../scheduler-service.js';
import { WEEKLY_MEMORY_DISTILL_PROMPT } from './memory-distill-task.js';

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
第零步：查询历史经验
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**决策前先查询类似场景的历史案例与教训！**
- 使用 query_experience 或 memory_search 查询相关经验
- 关键词：当前市场情况、持仓状态、技术形态等
- 参考历史成功/失败案例，避免重复错误

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
   - 注意T+1：仅今日买入的部分明天才能卖；之前持有的随时可卖，以 portfolio_status 的 shares_available 为准

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
- 记住T+1：仅今天买入的部分明天才能卖；之前持有的随时可卖（以 shares_available 为准）
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
- 记住T+1：仅今日买入的部分无法当日卖出；之前持有的可卖（以 shares_available 为准）

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
第零步：查询历史经验
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**复盘前先查询类似场景的历史案例与教训！**
- 使用 query_experience 或 memory_search 查询相关经验
- 关键词：今日交易类型、市场情况、盈亏情况等
- 对比历史案例，总结成功/失败模式

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
    // A2-T2：从「直接调用 runWeeklyEvolution」迁移为 evolution Agent 的 agent_turn——
    // 由 evolution Agent 用 evolution_run / evolution_leaderboard 产出提案，
    // 只提案不落地（不自动执行任何变更），提案写入 evolution 域供人工/Claude 评审。
    {
      name: 'weekly_evolution',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 20 * * 0',  // 每周日 20:00
      payload: {
        kind: 'agent_turn',
        agentKind: 'evolution',
        message: `
🔄 每周进化分析 - 策略绩效归因与优化提案

**目标：分析本周进化指标，产出优化提案（仅提案，不落地）。**

你是 evolution 域的 Agent。你的职责是评估策略/行为适应度、生成优化建议，
**不直接修改代码或交易系统**——所有产出都是提案，供人工/Claude 评审后落地。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：运行进化分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 使用 evolution_run 运行本周进化分析：
   - 读取本周的适应度数据、绩效归因、经验沉淀
   - 生成优化建议与提案文件（落盘到 .pi-invest/evolution/）

2. 使用 evolution_leaderboard 查看全账户适应度排行：
   - 各策略/行为在哪一侧失分？下跌捕获 vs 上涨捕获？
   - 哪些策略值得保留、哪些需要优化、哪些该下线？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：产出提案（写入 evolution 域）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基于分析结果，把优化提案写进 evolution 域（evolution_run 落盘到
.pi-invest/evolution/）。提案应包含：
- 建议变更的策略/行为及理由
- 预期收益与风险
- 优先级排序

⚠️ **硬约束：不自动执行任何变更。** 提案产出后由人工/Claude 评审，
确认后再落地。你只负责「发现 + 提案」，不负责「执行」。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
完成标准
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- evolution_run 已运行，本周进化分析完成
- 提案已写入 evolution 域（.pi-invest/evolution/）
- 代码库零改动（未执行任何代码/交易变更）

现在开始本周进化分析。
        `
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
    },

    // 6. 每周记忆蒸馏 - 从本周经验提炼可复用规则
    {
      name: 'weekly_memory_distill',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 21 * * 0',  // 每周日 21:00（进化任务后）
      payload: {
        kind: 'agent_turn',
        message: WEEKLY_MEMORY_DISTILL_PROMPT
      },
      compensationEnabled: false,
      compensationCheckAfter: undefined,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    },

    // 7. 每日召回审计 - 记忆 Agent 质量监控
    // A1-T2：记忆 Agent 每日审计召回日志，标注相关性，识别系统性问题
    {
      name: 'daily_recall_audit',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 19 * * *',  // 每天 19:00
      payload: {
        kind: 'agent_turn',
        agentKind: 'memory',
        message: `
📊 每日召回审计 - 记忆质量监控与优化

**目标：审计过去 24 小时的记忆召回质量，标注相关性，识别系统性问题。**

你是 memory 域的 Agent。你的职责是监控记忆召回系统的健康度，
标注召回内容的相关性，发现并报告质量问题。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：拉取过去 24 小时召回审计统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用 recall_audit 工具拉取统计数据：

1. 获取昨日统计：
   recall_audit({
     action: 'stats',
     date_from: '<昨日日期 YYYY-MM-DD>',
     date_to: '<今日日期 YYYY-MM-DD>'
   })

2. 关注关键指标（stats 响应的真实字段名）：
   - 总召回次数 (total)、注入数 (injected)、抑制数 (suppressed)
   - 注入率 (injection_rate) - 低于 60% 需要警惕
   - 分流统计 (by_flow) - 各渠道（scheduled-task/wake-event/interactive-chat/skill-invocation）的注入/抑制分布
   - 抑制原因 (suppress_reasons) - 哪些原因导致抑制？
   - 评分直方图 (score_histogram) - 低分注入是否过多？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：逐条初步标注（仅标注 agent feedback）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用 recall_audit 查询近期召回记录：

1. 查询昨日召回事件（重点关注注入的记录）：
   recall_audit({
     action: 'list',
     date_from: '<昨日日期>',
     date_to: '<今日日期>',
     gate_result: 'passed',  // passed=已注入放行, suppressed=已抑制
     page_size: 50
   })

2. 逐条评估相关性：
   - 记忆内容是否与用户查询/上下文相关？
   - 如果明显离题 → 标注 irrelevant
   - 如果有助于理解或决策 → 标注 relevant
   - 如果不确定 → 跳过，稍后标记需要人工审查

3. 标注反馈（仅限 agent feedback，绝不覆盖 human feedback）：
   recall_audit({
     action: 'feedback',
     audit_id: <审计记录ID>,
     memory_id: <记忆ID>,
     feedback: 'relevant' 或 'irrelevant'
   })

⚠️ **重要约束**：
- 只标注没有 human feedback 的记录（human feedback 优先级最高）
- 保守标注：只在明确离题时标 irrelevant，有疑问就不标
- 每日标注量适度（建议 20-50 条），不要一次性处理太多

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：低置信条目标记需要人工审查
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

识别需要人工审查的情况：

1. 边界情况：
   - 注入分数在临界区间（0.6-0.7）的记录
   - 内容相关但时效性存疑的记录
   - 技术类记忆用于非技术场景（或反之）

2. 系统性问题：
   - 某个 memory 被频繁召回但相关性不高
   - 某类查询总是召回不相关内容
   - 高分记录被错误抑制

3. 记录需审查清单：
   使用 memory_write 将需要人工审查的条目记录到记忆：
   memory_write({
     content: '[需人工审查] audit_id=<审计记录ID> memory_id=<记忆ID>：<为什么需要人工审查>',
     category: 'recall-audit-review'
   })
   （memory_write 仅接受 content/category 两个参数；不要传 action/scope/metadata，
     这些参数不存在会被静默忽略）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第四步：写日报到记忆
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用 memory_write 记录今日审计结果：

1. 日报内容应包括：
   - 昨日召回统计摘要（总数、注入率、抑制率）
   - 标注反馈数量（relevant 几条、irrelevant 几条）
   - 发现的关键问题（如果有）：
     * 注入率过低（<60%）或抑制率过高（>40%）
     * 低分注入过多（score < 0.6 但仍注入）
     * 某类查询的召回质量系统性偏低
   - 优化建议（如果有）：
     * 需要调整召回阈值？
     * 需要优化某些记忆的元数据？
     * 需要增加/删除某类记忆？

2. 写入参数（memory_write 仅接受 content/category，其余参数不存在）：
   memory_write({
     content: '每日召回审计日报 <审计日期>：总数<X>，注入率<Y>%，标注 relevant<A>条/irrelevant<B>条。关键发现：…。建议：…',
     category: 'daily-recall-audit'
   })
   （日期、统计数据直接写进 content 文本；category 固定用 'daily-recall-audit' 便于后续检索）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
完成标准
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- recall_audit stats 已拉取，关键指标已分析
- 已标注部分召回记录（agent feedback，未覆盖 human feedback）
- 边界情况已标记需要人工审查（如有）
- 日报已写入记忆（category: daily-recall-audit）

现在开始今日召回审计。
        `
      },
      compensationEnabled: false,
      compensationCheckAfter: undefined,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    }
  ];
}
