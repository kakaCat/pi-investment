import { InvestmentAgentLoop } from '@pi-investment/investment-agent-loop';
import { AgentDHClient } from '@pi-investment/agent-dh-client';
import { Context } from '@deepseek-ai/cordis';

/**
 * 示例 4: 完整的交易 Agent
 * 
 * 这个示例展示一个完整的交易 Agent，包括：
 * 1. Agent 注册和启动
 * 2. 查询市场数据
 * 3. 执行策略回测
 * 4. 生成交易信号
 * 5. 监控和报告
 */

async function main() {
  console.log('=== 完整交易 Agent 示例 ===\n');

  // 1. 初始化
  console.log('[1] 初始化 Agent...\n');

  const ctx = new Context();
  const client = AgentDHClient.createDefault();

  const agentLoop = new InvestmentAgentLoop(ctx, {
    osClient: client.agentOS,
    agentType: 'trading',
    capabilities: ['market-data', 'backtest', 'signal-generation'],
  });

  const agent = await agentLoop.create('trading-agent-session', {
    agentId: 'trading-agent-001',
    type: 'trading',
    capabilities: ['market-data', 'backtest', 'signal-generation'],
  });

  console.log('    ✓ Trading Agent 已启动');
  console.log(`      Agent ID: ${agent.agentId}\n`);

  // 2. 查询市场数据
  console.log('[2] 获取市场数据...\n');

  const symbols = ['600000.SH', '600519.SH', '600036.SH'];
  const marketData = [];

  for (const symbol of symbols) {
    try {
      const quote = await client.quantsysV2.getQuote(symbol);
      marketData.push(quote);
      console.log(`    ${symbol}:`);
      console.log(`      价格: ¥${quote.price}`);
      console.log(`      涨跌幅: ${quote.change_pct > 0 ? '+' : ''}${quote.change_pct.toFixed(2)}%`);
      console.log(`      成交量: ${(quote.volume / 10000).toFixed(0)} 万股\n`);
    } catch (error) {
      console.log(`    ${symbol}: 数据获取失败\n`);
    }
  }

  // 3. 获取市场风格
  console.log('[3] 分析市场风格...\n');

  try {
    const marketStyle = await client.quantsysV2.getMarketStyle();
    console.log(`    当前市场风格: ${marketStyle.style}`);
    console.log(`    置信度: ${(marketStyle.confidence * 100).toFixed(1)}%`);
    console.log(`    描述: ${marketStyle.description}`);
    console.log(`    更新时间: ${new Date(marketStyle.updated_at).toLocaleString()}\n`);
  } catch (error) {
    console.log('    市场风格数据暂不可用\n');
  }

  // 4. 选择并回测策略
  console.log('[4] 执行策略回测...\n');

  const strategies = await client.quantsysV2.listStrategies({
    source: 'builtin',
  });

  if (strategies.length > 0) {
    const strategy = strategies[0];
    console.log(`    使用策略: ${strategy.name}\n`);

    const backtestResults = [];

    for (const symbol of symbols.slice(0, 2)) {
      console.log(`    回测 ${symbol}...`);
      
      try {
        const result = await client.quantsysV2.backtestStrategy({
          strategy_id: strategy.id,
          symbol,
          start_date: '2024-01-01',
          end_date: '2024-12-31',
          initial_capital: 100000,
        });

        backtestResults.push({ symbol, result });
        
        console.log(`      收益率: ${result.total_return.toFixed(2)}%`);
        console.log(`      夏普比率: ${result.sharpe_ratio.toFixed(2)}`);
        console.log(`      最大回撤: ${result.max_drawdown.toFixed(2)}%\n`);
      } catch (error) {
        console.log(`      回测失败\n`);
      }
    }

    // 5. 生成交易信号
    console.log('[5] 生成交易信号...\n');

    if (backtestResults.length > 0) {
      // 选择表现最好的股票
      const bestResult = backtestResults.reduce((best, current) => {
        return current.result.sharpe_ratio > best.result.sharpe_ratio ? current : best;
      });

      console.log(`    最佳标的: ${bestResult.symbol}`);
      console.log(`    夏普比率: ${bestResult.result.sharpe_ratio.toFixed(2)}`);
      console.log(`    总收益率: ${bestResult.result.total_return.toFixed(2)}%\n`);

      try {
        const signals = await client.quantsysV2.generateSignals({
          strategy_id: strategy.id,
          symbols: [bestResult.symbol],
          date: new Date().toISOString().split('T')[0],
        });

        if (signals.length > 0) {
          console.log(`    生成 ${signals.length} 个信号:\n`);
          signals.forEach((signal, index) => {
            console.log(`    ${index + 1}. ${signal.signal_type.toUpperCase()} ${signal.symbol}`);
            console.log(`       价格: ¥${signal.price}`);
            console.log(`       置信度: ${((signal.confidence || 0) * 100).toFixed(1)}%`);
            console.log(`       时间: ${new Date(signal.generated_at).toLocaleString()}\n`);
          });
        } else {
          console.log('    当前无信号\n');
        }
      } catch (error) {
        console.log('    信号生成失败\n');
      }
    }
  }

  // 6. 监控报告
  console.log('[6] 生成监控报告...\n');

  const report = {
    agent_id: agent.agentId,
    timestamp: new Date().toISOString(),
    market_data_count: marketData.length,
    strategies_tested: strategies.length,
    symbols_analyzed: symbols.length,
    status: 'active',
  };

  console.log('    Agent 状态报告:');
  console.log('    ┌─────────────────────────────────────┐');
  console.log(`    │ Agent ID: ${report.agent_id}`);
  console.log(`    │ 状态: ${report.status}`);
  console.log(`    │ 市场数据: ${report.market_data_count} 条`);
  console.log(`    │ 策略测试: ${report.strategies_tested} 个`);
  console.log(`    │ 分析标的: ${report.symbols_analyzed} 个`);
  console.log(`    │ 时间: ${new Date(report.timestamp).toLocaleString()}`);
  console.log('    └─────────────────────────────────────┘\n');

  // 7. 优雅关闭
  console.log('[7] 关闭 Agent...\n');

  await agentLoop.stopAll();
  console.log('    ✓ Trading Agent 已停止\n');

  console.log('=== 示例完成 ===');
  console.log('\n💡 提示: 这个 Agent 可以定时运行，实现自动化交易分析。');
}

// 运行示例
main().catch((error) => {
  console.error('❌ 错误:', error);
  process.exit(1);
});
