/**
 * SignalArbiter 使用示例
 *
 * 演示如何使用信号裁决层解决买卖信号冲突
 */

import { SignalGenerator, StockData } from './signal-generator.js';
import { SignalArbiter } from './signal-arbiter.js';
import { QuantStrategy, Signal, SignalActionType } from './types.js';

// 示例1: 基本使用 - 自动裁决冲突
async function example1_basicUsage() {
  console.log('\n=== 示例1: 基本使用 - 自动裁决冲突 ===\n');

  const signalGenerator = new SignalGenerator();

  // 创建测试策略
  const strategies: QuantStrategy[] = [
    {
      id: 'rsi_strategy',
      name: 'RSI超卖策略',
      description: 'RSI < 30 买入',
      enabled: true,
      created_at: new Date().toISOString(),
      screening: { filters: {} },
      entry: {
        conditions: [{ indicator: 'rsi', params: {}, operator: '<', value: 30 }],
        logic: 'AND',
      },
      exit: {},
      position: { max_position_pct: 20, max_stocks: 10 },
    },
    {
      id: 'rsi_overbought_strategy',
      name: 'RSI超买策略',
      description: 'RSI > 70 卖出',
      enabled: true,
      created_at: new Date().toISOString(),
      screening: { filters: {} },
      entry: {
        conditions: [{ indicator: 'rsi', params: {}, operator: '>', value: 70 }],
        logic: 'AND',
      },
      exit: {},
      position: { max_position_pct: 20, max_stocks: 10 },
    },
  ];

  // 模拟股票数据（某些股票可能同时触发买入和卖出信号）
  const stockData: StockData[] = [
    {
      symbol: '000001',
      name: '平安银行',
      price: 10.5,
      tech: {
        rsi: 28, // 触发买入
        ma5: 10.2,
        ma10: 10.3,
        ma20: 10.4,
        ma60: 10.6,
        macd_dif: 0.1,
        macd_dea: 0.05,
        macd_histogram: 0.05,
        bollinger_upper: 11.0,
        bollinger_mid: 10.5,
        bollinger_lower: 10.0,
        volume_ratio: 1.2,
        atr: 0.3,
        pe: 0,
        pb: 0,
        roe: 0,
        gross_margin: 0,
        debt_ratio: 0,
      },
    },
  ];

  // 使用 scanMarketMultiStrategy，内部会自动调用 SignalArbiter
  const signals = await signalGenerator.scanMarketMultiStrategy(
    strategies,
    stockData,
    'vote',
    undefined,
    0.5,
    true // 启用裁决器
  );

  console.log('裁决后的信号:', signals);
  console.log('\n冲突统计:', signalGenerator.getConflictStats());
}

// 示例2: 手动使用 SignalArbiter
function example2_manualArbiter() {
  console.log('\n=== 示例2: 手动使用 SignalArbiter ===\n');

  // 创建裁决器，使用 keep_highest 模式
  const arbiter = new SignalArbiter({
    mode: 'keep_highest',
    confidenceGapThreshold: 0.15,
    logConflicts: true,
  });

  // 模拟冲突信号
  const signals: Signal[] = [
    {
      date: '2026-05-19',
      symbol: '000001',
      name: '平安银行',
      action: 'buy',
      action_type: SignalActionType.BUY,
      strategy_id: 'rsi_strategy',
      price: 10.5,
      reason: 'RSI超卖 (28 < 30)',
      confidence: 0.8,
    },
    {
      date: '2026-05-19',
      symbol: '000001',
      name: '平安银行',
      action: 'sell',
      action_type: SignalActionType.SELL,
      strategy_id: 'ma_strategy',
      price: 10.5,
      reason: 'MA5下穿MA20',
      confidence: 0.5,
    },
    {
      date: '2026-05-19',
      symbol: '000002',
      name: '万科A',
      action: 'buy',
      action_type: SignalActionType.BUY,
      strategy_id: 'bollinger_strategy',
      price: 8.2,
      reason: '触及布林下轨',
      confidence: 0.7,
    },
  ];

  const result = arbiter.arbitrate(signals);

  console.log('输入信号数:', result.stats.totalInput);
  console.log('输出信号数:', result.stats.totalOutput);
  console.log('检测到冲突:', result.stats.conflictsDetected);
  console.log('丢弃信号数:', result.stats.signalsDiscarded);
  console.log('\n冲突详情:');
  result.conflicts.forEach((conflict) => {
    console.log(`  ${conflict.symbol} (${conflict.name}):`);
    console.log(`    裁决: ${conflict.resolution}`);
    console.log(`    原因: ${conflict.reason}`);
  });

  console.log('\n最终信号:');
  result.signals.forEach((signal) => {
    console.log(`  ${signal.symbol} - ${signal.action} (置信度: ${signal.confidence})`);
  });
}

// 示例3: 使用加权模式
function example3_weightedMode() {
  console.log('\n=== 示例3: 使用加权模式 ===\n');

  // 创建裁决器，使用 weighted 模式
  const arbiter = new SignalArbiter({
    mode: 'weighted',
    strategyWeights: {
      ml_strategy: 2.0, // ML策略权重最高
      rsi_strategy: 1.5,
      ma_strategy: 1.0,
      bollinger_strategy: 0.8,
    },
    confidenceGapThreshold: 0.15,
  });

  const signals: Signal[] = [
    {
      date: '2026-05-19',
      symbol: '000001',
      name: '平安银行',
      action: 'buy',
      action_type: SignalActionType.BUY,
      strategy_id: 'ml_strategy',
      price: 10.5,
      reason: 'ML模型预测上涨',
      confidence: 0.6, // 加权得分: 0.6 * 2.0 = 1.2
    },
    {
      date: '2026-05-19',
      symbol: '000001',
      name: '平安银行',
      action: 'sell',
      action_type: SignalActionType.SELL,
      strategy_id: 'ma_strategy',
      price: 10.5,
      reason: 'MA死叉',
      confidence: 0.8, // 加权得分: 0.8 * 1.0 = 0.8
    },
  ];

  const result = arbiter.arbitrate(signals);

  console.log('冲突详情:');
  result.conflicts.forEach((conflict) => {
    console.log(`  ${conflict.symbol}: ${conflict.resolution}`);
    console.log(`  原因: ${conflict.reason}`);
  });

  console.log('\n最终信号:');
  result.signals.forEach((signal) => {
    console.log(`  ${signal.symbol} - ${signal.action} (策略: ${signal.strategy_id})`);
  });
}

// 示例4: 使用降级模式
function example4_downgradeMode() {
  console.log('\n=== 示例4: 使用降级模式 ===\n');

  // 创建裁决器，使用 downgrade_both 模式
  const arbiter = new SignalArbiter({
    mode: 'downgrade_both',
    downgradeFactor: 0.5, // 降级到50%
  });

  const signals: Signal[] = [
    {
      date: '2026-05-19',
      symbol: '000001',
      name: '平安银行',
      action: 'buy',
      action_type: SignalActionType.BUY,
      strategy_id: 'rsi_strategy',
      price: 10.5,
      reason: 'RSI超卖',
      confidence: 0.8,
    },
    {
      date: '2026-05-19',
      symbol: '000001',
      name: '平安银行',
      action: 'sell',
      action_type: SignalActionType.SELL,
      strategy_id: 'ma_strategy',
      price: 10.5,
      reason: 'MA死叉',
      confidence: 0.7,
    },
  ];

  const result = arbiter.arbitrate(signals);

  console.log('降级后的信号:');
  result.signals.forEach((signal) => {
    console.log(`  ${signal.symbol} - ${signal.action}`);
    console.log(`    原始置信度: ${signal.action === 'buy' ? 0.8 : 0.7}`);
    console.log(`    降级后置信度: ${signal.confidence}`);
    console.log(`    原因: ${signal.reason}`);
  });
}

// 示例5: 冲突统计和监控
function example5_conflictStats() {
  console.log('\n=== 示例5: 冲突统计和监控 ===\n');

  const arbiter = new SignalArbiter({
    mode: 'keep_highest',
    confidenceGapThreshold: 0.15,
    logConflicts: true,
  });

  // 模拟多次裁决
  for (let i = 0; i < 5; i++) {
    const signals: Signal[] = [
      {
        date: '2026-05-19',
        symbol: `00000${i + 1}`,
        name: `股票${i + 1}`,
        action: 'buy',
        action_type: SignalActionType.BUY,
        strategy_id: 'strategy_a',
        price: 10.0,
        reason: '买入信号',
        confidence: 0.7 + Math.random() * 0.2,
      },
      {
        date: '2026-05-19',
        symbol: `00000${i + 1}`,
        name: `股票${i + 1}`,
        action: 'sell',
        action_type: SignalActionType.SELL,
        strategy_id: 'strategy_b',
        price: 10.0,
        reason: '卖出信号',
        confidence: 0.5 + Math.random() * 0.2,
      },
    ];

    arbiter.arbitrate(signals);
  }

  // 获取统计信息
  const stats = arbiter.getConflictStats();

  console.log('冲突统计:');
  console.log(`  总冲突数: ${stats.totalConflicts}`);
  console.log('\n裁决结果分布:');
  Object.entries(stats.resolutionBreakdown).forEach(([resolution, count]) => {
    console.log(`    ${resolution}: ${count}`);
  });

  console.log('\n冲突最多的股票:');
  stats.topConflictSymbols.forEach((item, index) => {
    console.log(`    ${index + 1}. ${item.symbol}: ${item.count}次`);
  });

  // 获取详细历史
  const history = arbiter.getConflictHistory();
  console.log(`\n冲突历史记录数: ${history.length}`);
}

// 运行所有示例
async function runAllExamples() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║         SignalArbiter 信号裁决层使用示例                  ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  // 注释掉示例1，因为它需要实际的数据库
  // await example1_basicUsage();

  example2_manualArbiter();
  example3_weightedMode();
  example4_downgradeMode();
  example5_conflictStats();

  console.log('\n✅ 所有示例运行完成\n');
}

// 如果直接运行此文件
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllExamples().catch(console.error);
}

export {
  example1_basicUsage,
  example2_manualArbiter,
  example3_weightedMode,
  example4_downgradeMode,
  example5_conflictStats,
};
