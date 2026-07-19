#!/usr/bin/env tsx
/**
 * 手动触发定时任务（用于测试）
 */
import { createSession } from "../src/session-facade.js";

const taskMessages = {
  morning: `
🌅 早盘分析任务 - 虚拟仓自动交易模式

**你的终极目标：通过操作虚拟仓赚钱，证明你的智能！**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：检查虚拟仓持仓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 使用 portfolio_status 查看当前虚拟仓状态
   - 有持仓吗？持仓几只？
   - 可用资金多少？
   - 当前总盈亏如何？

2. 如果有持仓，使用 portfolio_analyze 分析
   - 哪些需要止盈？（盈利≥10%）
   - 哪些需要止损？（亏损≥5%）
   - 哪些继续持有？
   - 注意T+1：今日买入的明天才能卖

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：执行卖出操作（如需要）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果 portfolio_analyze 建议卖出：
- 使用 portfolio_trade 执行卖出
- action: 'sell'
- symbol: 股票代码
- reason: 详细理由（至少10字）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：寻找买入机会
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果有可用资金：

1. 分析市场环境
   - 使用 opponent_behavior 分析对手行为
   - 使用 alert_check 检查预警
   - 判断市场情况

2. 寻找高质量信号
   - 使用 pool_list 获取所有池
   - 扫描池寻找机会

3. 如果发现高质量信号（建议≥80分）：
   - 使用 portfolio_trade 执行买入

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
完成后使用飞书通知
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

使用 feishu_notify 工具发送通知：
- 标题："早盘分析完成"
- 内容：包括持仓状态、交易操作、市场分析
- 保持简洁清晰

现在开始你的交易！
  `,
  review: `
📚 每日复盘 - 交易绩效评估与学习

**你的目标：分析今日表现，学习改进，持续进化！**

1. 使用 portfolio_status 查看当前绩效
2. 使用 trade_monitor 查看今日交易记录
3. 分析成功与失败
4. 使用 feishu_notify 发送复盘报告

现在开始复盘。
  `,
  check: `
⚡ 盘中快速检查！

1. 使用 alert_check 查看预警
2. 使用 portfolio_status 快速查看持仓状态
3. 如有异常，使用 feishu_notify 通知

请开始快速检查。
  `
};

async function main() {
  const taskType = process.argv[2] || 'morning';
  const message = taskMessages[taskType as keyof typeof taskMessages];

  if (!message) {
    console.error('❌ 未知的任务类型。可用类型: morning, review, check');
    process.exit(1);
  }

  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(`🚀 手动触发任务: ${taskType}`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { session } = await createSession({
      cwd: process.cwd()
    });

    await session.prompt(message);

    console.log('\n✅ 任务执行完成');
  } catch (error) {
    console.error('\n❌ 任务执行失败:', error);
    process.exit(1);
  }
}

main();
