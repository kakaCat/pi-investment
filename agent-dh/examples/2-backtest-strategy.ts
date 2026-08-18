import { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * 示例 2: 策略回测
 * 
 * 这个示例展示如何：
 * 1. 列出可用策略
 * 2. 选择策略进行回测
 * 3. 分析回测结果
 * 4. 进行参数优化
 */

async function main() {
  console.log('=== 策略回测示例 ===\n');

  // 创建客户端
  const client = AgentDHClient.createDefault();

  // 1. 列出可用策略
  console.log('[1] 查询可用策略...\n');
  
  const strategies = await client.quantsysV2.listStrategies({
    source: 'builtin',
  });

  console.log(`    找到 ${strategies.length} 个内置策略:`);
  strategies.slice(0, 5).forEach((strategy, index) => {
    console.log(`    ${index + 1}. ${strategy.name} (ID: ${strategy.id}, 类型: ${strategy.code_type})`);
  });
  console.log();

  // 2. 选择第一个策略进行回测
  if (strategies.length === 0) {
    console.log('❌ 没有可用的策略');
    return;
  }

  const selectedStrategy = strategies[0];
  console.log(`[2] 使用策略: ${selectedStrategy.name}\n`);

  // 3. 执行回测
  console.log('[3] 开始回测...');
  console.log(`    股票: 600000.SH (浦发银行)`);
  console.log(`    时间: 2024-01-01 至 2024-12-31`);
  console.log(`    初始资金: ¥100,000\n`);

  const backtestResult = await client.quantsysV2.backtestStrategy({
    strategy_id: selectedStrategy.id,
    symbol: '600000.SH',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 100000,
  });

  // 4. 展示回测结果
  console.log('[4] 回测结果:\n');
  console.log('    ┌─────────────────────────────────────┐');
  console.log(`    │ 总收益率:    ${backtestResult.total_return.toFixed(2)}%`);
  console.log(`    │ 年化收益率:  ${backtestResult.annual_return.toFixed(2)}%`);
  console.log(`    │ 夏普比率:    ${backtestResult.sharpe_ratio.toFixed(2)}`);
  console.log(`    │ 最大回撤:    ${backtestResult.max_drawdown.toFixed(2)}%`);
  console.log(`    │ 胜率:        ${backtestResult.win_rate.toFixed(2)}%`);
  console.log(`    │ 交易次数:    ${backtestResult.total_trades}`);
  console.log('    └─────────────────────────────────────┘\n');

  // 5. 评估结果
  console.log('[5] 策略评估:\n');

  const evaluation = evaluateStrategy(backtestResult);
  console.log(`    综合评分: ${evaluation.score}/100`);
  console.log(`    评级: ${evaluation.grade}`);
  console.log(`    建议: ${evaluation.recommendation}\n`);

  // 6. 参数优化（可选）
  console.log('[6] 参数优化（可选）\n');
  
  console.log('    提示: 如需进行参数优化，可使用以下代码:');
  console.log(`    
    const optimized = await client.quantsysV2.optimizeStrategy({
      strategy_id: ${selectedStrategy.id},
      symbol: '600000.SH',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      param_ranges: {
        fast_period: [5, 10, 20],
        slow_period: [20, 50, 60],
      },
    });
  `);

  console.log('=== 示例完成 ===');
}

/**
 * 评估策略表现
 */
function evaluateStrategy(result: any): {
  score: number;
  grade: string;
  recommendation: string;
} {
  let score = 0;

  // 收益率评分（40分）
  if (result.total_return > 50) score += 40;
  else if (result.total_return > 30) score += 30;
  else if (result.total_return > 10) score += 20;
  else if (result.total_return > 0) score += 10;

  // 夏普比率评分（30分）
  if (result.sharpe_ratio > 2) score += 30;
  else if (result.sharpe_ratio > 1.5) score += 25;
  else if (result.sharpe_ratio > 1) score += 20;
  else if (result.sharpe_ratio > 0.5) score += 10;

  // 最大回撤评分（20分）
  if (result.max_drawdown < 10) score += 20;
  else if (result.max_drawdown < 20) score += 15;
  else if (result.max_drawdown < 30) score += 10;
  else if (result.max_drawdown < 40) score += 5;

  // 胜率评分（10分）
  if (result.win_rate > 60) score += 10;
  else if (result.win_rate > 50) score += 8;
  else if (result.win_rate > 40) score += 5;

  // 评级
  let grade = 'D';
  if (score >= 90) grade = 'A+';
  else if (score >= 80) grade = 'A';
  else if (score >= 70) grade = 'B';
  else if (score >= 60) grade = 'C';

  // 建议
  let recommendation = '';
  if (score >= 80) {
    recommendation = '优秀的策略！建议实盘测试。';
  } else if (score >= 60) {
    recommendation = '表现尚可，建议进行参数优化。';
  } else {
    recommendation = '表现较差，需要重新设计策略。';
  }

  return { score, grade, recommendation };
}

// 运行示例
main().catch((error) => {
  console.error('❌ 错误:', error);
  process.exit(1);
});
