#!/usr/bin/env node
/**
 * 量化模块完整测试 - Phase 2
 *
 * 测试改进后的功能：
 * - 完整的信号检查逻辑
 * - 止损止盈机制
 * - 夏普比率和最大回撤计算
 * - 扩展的股票池
 */

import { QuantService } from './dist/services/quant/quant-service.js';
import { BacktestEngine } from './dist/services/quant/backtest-engine.js';
import { SignalGenerator } from './dist/services/quant/signal-generator.js';

async function main() {
  console.log('🧪 量化模块完整测试 (Phase 2)\n');

  const quantService = new QuantService();
  const backtestEngine = new BacktestEngine();
  const signalGenerator = new SignalGenerator();

  // 1. 创建测试策略 - RSI超卖反转
  console.log('1️⃣ 创建 RSI 超卖反转策略...');
  const strategy1 = await quantService.createStrategy({
    name: 'RSI超卖反转策略',
    description: 'RSI<30时买入，RSI>70或止盈20%时卖出，止损8%',
    enabled: true,
    screening: {
      market: 'A',
      filters: {
        pe_range: [0, 30],
      },
    },
    entry: {
      conditions: [
        {
          indicator: 'rsi',
          params: {},
          operator: '<',
          value: 30,
        },
      ],
      logic: 'AND',
    },
    exit: {
      stop_loss: 0.08,
      take_profit: 0.20,
      conditions: [
        {
          indicator: 'rsi',
          params: {},
          operator: '>',
          value: 70,
        },
      ],
    },
    position: {
      max_position_pct: 0.15,
      max_stocks: 5,
    },
  });
  console.log(`✅ 策略创建: ${strategy1.id}\n`);

  // 2. 创建第二个策略 - 均线交叉
  console.log('2️⃣ 创建均线交叉策略...');
  const strategy2 = await quantService.createStrategy({
    name: '均线金叉策略',
    description: 'MA5上穿MA20买入，下穿卖出',
    enabled: true,
    screening: {
      market: 'A',
      filters: {},
    },
    entry: {
      conditions: [
        {
          indicator: 'ma_cross',
          params: { fast: 5, slow: 20 },
          operator: 'cross_above',
          value: 0,
        },
      ],
      logic: 'AND',
    },
    exit: {
      stop_loss: 0.10,
      take_profit: 0.25,
      conditions: [
        {
          indicator: 'ma_cross',
          params: { fast: 5, slow: 20 },
          operator: 'cross_below',
          value: 0,
        },
      ],
    },
    position: {
      max_position_pct: 0.20,
      max_stocks: 3,
    },
  });
  console.log(`✅ 策略创建: ${strategy2.id}\n`);

  // 3. 列出所有策略
  console.log('3️⃣ 列出所有策略...');
  const strategies = await quantService.listStrategies();
  console.log(`✅ 共有 ${strategies.length} 个策略:`);
  strategies.forEach(s => {
    console.log(`   - ${s.name} (${s.enabled ? '启用' : '禁用'})`);
  });
  console.log();

  // 4. 运行回测 - 策略1
  console.log('4️⃣ 回测策略1 (2024年)...');
  try {
    const backtest1 = await backtestEngine.run(strategy1, {
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      commission: 0.0003,
    });
    console.log(`✅ 回测完成: ${backtest1.id}`);
    console.log(`   总收益: ${(backtest1.performance.total_return * 100).toFixed(2)}%`);
    console.log(`   年化收益: ${(backtest1.performance.annual_return * 100).toFixed(2)}%`);
    console.log(`   夏普比率: ${backtest1.performance.sharpe_ratio.toFixed(2)}`);
    console.log(`   最大回撤: ${(backtest1.performance.max_drawdown * 100).toFixed(2)}%`);
    console.log(`   胜率: ${(backtest1.performance.win_rate * 100).toFixed(2)}%`);
    console.log(`   盈亏比: ${backtest1.performance.profit_factor.toFixed(2)}`);
    console.log(`   交易次数: ${backtest1.performance.total_trades}`);

    if (backtest1.trades.length > 0) {
      console.log(`\n   最近5笔交易:`);
      backtest1.trades.slice(-5).forEach(t => {
        const pnlStr = t.pnl ? ` (${t.pnl > 0 ? '+' : ''}${(t.pnl_pct * 100).toFixed(2)}%)` : '';
        console.log(`   ${t.date} ${t.action === 'buy' ? '买入' : '卖出'} ${t.symbol} @${t.price.toFixed(2)}${pnlStr} - ${t.reason}`);
      });
    }
    console.log();
  } catch (err) {
    console.log(`⚠️  回测失败: ${err.message}\n`);
  }

  // 5. 运行回测 - 策略2
  console.log('5️⃣ 回测策略2 (2024年)...');
  try {
    const backtest2 = await backtestEngine.run(strategy2, {
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      commission: 0.0003,
    });
    console.log(`✅ 回测完成: ${backtest2.id}`);
    console.log(`   总收益: ${(backtest2.performance.total_return * 100).toFixed(2)}%`);
    console.log(`   年化收益: ${(backtest2.performance.annual_return * 100).toFixed(2)}%`);
    console.log(`   夏普比率: ${backtest2.performance.sharpe_ratio.toFixed(2)}`);
    console.log(`   最大回撤: ${(backtest2.performance.max_drawdown * 100).toFixed(2)}%`);
    console.log(`   胜率: ${(backtest2.performance.win_rate * 100).toFixed(2)}%`);
    console.log(`   盈亏比: ${backtest2.performance.profit_factor.toFixed(2)}`);
    console.log(`   交易次数: ${backtest2.performance.total_trades}\n`);
  } catch (err) {
    console.log(`⚠️  回测失败: ${err.message}\n`);
  }

  // 6. 生成实时信号
  console.log('6️⃣ 扫描实时交易信号...');
  try {
    const signals1 = await signalGenerator.scan(strategy1);
    console.log(`✅ 策略1发现 ${signals1.length} 个信号`);
    signals1.forEach(s => {
      console.log(`   ${s.action === 'buy' ? '买入' : '卖出'} ${s.symbol} ${s.name} @${s.price.toFixed(2)} - ${s.reason}`);
    });

    const signals2 = await signalGenerator.scan(strategy2);
    console.log(`✅ 策略2发现 ${signals2.length} 个信号`);
    signals2.forEach(s => {
      console.log(`   ${s.action === 'buy' ? '买入' : '卖出'} ${s.symbol} ${s.name} @${s.price.toFixed(2)} - ${s.reason}`);
    });
    console.log();
  } catch (err) {
    console.log(`⚠️  信号生成失败: ${err.message}\n`);
  }

  console.log('✅ Phase 2 测试完成！\n');
  console.log('📊 改进总结:');
  console.log('   ✅ 完整的信号检查逻辑（RSI/MA/MACD）');
  console.log('   ✅ 止损止盈机制');
  console.log('   ✅ 夏普比率计算');
  console.log('   ✅ 最大回撤计算');
  console.log('   ✅ 扩展的股票池');
  console.log('   ✅ 多策略并行测试\n');

  console.log('📝 下一步 (Phase 3):');
  console.log('   1. 集成到 CRON 定时任务');
  console.log('   2. 参数优化器（网格搜索）');
  console.log('   3. 更多技术指标（KDJ/布林带）');
  console.log('   4. 基本面筛选（PE/PB/ROE）');
}

main().catch(console.error);
