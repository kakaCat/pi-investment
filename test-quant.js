#!/usr/bin/env node
/**
 * 量化模块测试脚本
 *
 * 用法:
 *   npm run quant:test
 */

import { QuantService } from './dist/services/quant/quant-service.js';
import { BacktestEngine } from './dist/services/quant/backtest-engine.js';
import { SignalGenerator } from './dist/services/quant/signal-generator.js';

async function main() {
  console.log('🧪 量化模块测试\n');

  const quantService = new QuantService();
  const backtestEngine = new BacktestEngine();
  const signalGenerator = new SignalGenerator();

  // 1. 创建测试策略
  console.log('1️⃣ 创建测试策略...');
  const strategy = await quantService.createStrategy({
    name: '低估值反转策略',
    description: 'PE<15, RSI<30时买入，止损8%，止盈20%',
    enabled: true,
    screening: {
      market: 'A',
      filters: {
        pe_range: [0, 15],
        pb_range: [0, 2],
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
      stop_loss: 0.08,
      take_profit: 0.20,
    },
    position: {
      max_position_pct: 0.2,
      max_stocks: 5,
    },
  });
  console.log(`✅ 策略创建成功: ${strategy.id}\n`);

  // 2. 列出所有策略
  console.log('2️⃣ 列出所有策略...');
  const strategies = await quantService.listStrategies();
  console.log(`✅ 共有 ${strategies.length} 个策略\n`);

  // 3. 运行回测（简化版，仅测试框架）
  console.log('3️⃣ 运行回测...');
  try {
    const backtest = await backtestEngine.run(strategy, {
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      commission: 0.0003,
    });
    console.log(`✅ 回测完成: ${backtest.id}`);
    console.log(`   总收益: ${(backtest.performance.total_return * 100).toFixed(2)}%`);
    console.log(`   胜率: ${(backtest.performance.win_rate * 100).toFixed(2)}%`);
    console.log(`   交易次数: ${backtest.performance.total_trades}\n`);
  } catch (err) {
    console.log(`⚠️  回测失败（预期，因为信号检查未完整实现）: ${err.message}\n`);
  }

  // 4. 生成信号（简化版）
  console.log('4️⃣ 生成交易信号...');
  try {
    const signals = await signalGenerator.scan(strategy);
    console.log(`✅ 发现 ${signals.length} 个交易信号\n`);
  } catch (err) {
    console.log(`⚠️  信号生成失败（预期，因为需要实时数据）: ${err.message}\n`);
  }

  console.log('✅ 量化模块基础框架测试完成！');
  console.log('\n📝 下一步:');
  console.log('   1. 完善 BacktestEngine 的信号检查逻辑');
  console.log('   2. 完善 SignalGenerator 的股票池筛选');
  console.log('   3. 添加更多技术指标支持');
  console.log('   4. 集成到 CRON 定时任务');
}

main().catch(console.error);
