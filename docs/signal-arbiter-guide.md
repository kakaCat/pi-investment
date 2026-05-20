# SignalArbiter 信号裁决层

## 概述

SignalArbiter 是一个信号裁决层，用于解决量化交易系统中同一股票同时产生买入和卖出信号的冲突问题。

## 问题背景

在多策略量化系统中，不同策略可能对同一只股票产生相反的信号：
- 策略A（RSI超卖）：发出买入信号
- 策略B（均线死叉）：发出卖出信号

这种冲突会导致系统无法决策，需要一个裁决机制来解决。

## 核心功能

### 1. 冲突检测
自动检测同一股票在同一时间点的买入/卖出信号冲突。

### 2. 四种裁决模式

#### keep_highest（保留最高置信度）
- 比较买入和卖出信号的置信度
- 保留置信度更高的一方
- 如果置信度差距小于阈值，则丢弃所有信号

```typescript
const arbiter = new SignalArbiter({
  mode: 'keep_highest',
  confidenceGapThreshold: 0.15  // 置信度差距阈值
});
```

#### downgrade_both（降级所有信号）
- 保留所有冲突信号，但降低其置信度
- 适用于希望保留所有信息但标记风险的场景

```typescript
const arbiter = new SignalArbiter({
  mode: 'downgrade_both',
  downgradeFactor: 0.5  // 降级到50%
});
```

#### discard_both（丢弃所有信号）
- 检测到冲突时，丢弃所有相关信号
- 最保守的策略，避免在不确定情况下交易

```typescript
const arbiter = new SignalArbiter({
  mode: 'discard_both'
});
```

#### weighted（加权裁决）
- 根据策略权重计算加权得分
- 保留加权得分更高的一方
- 适用于有明确策略优先级的场景

```typescript
const arbiter = new SignalArbiter({
  mode: 'weighted',
  strategyWeights: {
    'ml_strategy': 2.0,      // ML策略权重最高
    'rsi_strategy': 1.5,
    'ma_strategy': 1.0,
    'bollinger_strategy': 0.8
  }
});
```

### 3. 冲突记录和统计

SignalArbiter 会记录所有冲突情况，提供统计分析：

```typescript
const stats = arbiter.getConflictStats();
// {
//   totalConflicts: 10,
//   resolutionBreakdown: {
//     kept_buy: 6,
//     kept_sell: 2,
//     discarded_both: 2
//   },
//   topConflictSymbols: [
//     { symbol: '000001', count: 3 },
//     { symbol: '000002', count: 2 }
//   ]
// }
```

## 使用方式

### 方式1: 集成到 SignalGenerator（推荐）

SignalGenerator 已经内置了 SignalArbiter，在多策略扫描时自动调用：

```typescript
const signalGenerator = new SignalGenerator(
  '.pi-invest/quant/signals',
  factorLib,
  true,
  '.pi-invest/stock-db/stocks.db',
  {
    mode: 'keep_highest',
    confidenceGapThreshold: 0.15
  }
);

// 多策略扫描，自动裁决冲突
const signals = await signalGenerator.scanMarketMultiStrategy(
  strategies,
  stockData,
  'vote',
  undefined,
  0.5,
  true  // 启用裁决器
);

// 查看冲突统计
const stats = signalGenerator.getConflictStats();
```

### 方式2: 独立使用

也可以单独使用 SignalArbiter 处理信号列表：

```typescript
import { SignalArbiter } from './signal-arbiter.js';

const arbiter = new SignalArbiter({
  mode: 'keep_highest',
  confidenceGapThreshold: 0.15,
  logConflicts: true
});

const result = arbiter.arbitrate(signals);

console.log('输入信号:', result.stats.totalInput);
console.log('输出信号:', result.stats.totalOutput);
console.log('冲突数:', result.stats.conflictsDetected);
console.log('丢弃信号:', result.stats.signalsDiscarded);

// 查看冲突详情
result.conflicts.forEach(conflict => {
  console.log(`${conflict.symbol}: ${conflict.resolution} - ${conflict.reason}`);
});
```

## 配置参数

### ArbiterConfig

```typescript
interface ArbiterConfig {
  // 裁决模式
  mode: 'keep_highest' | 'downgrade_both' | 'discard_both' | 'weighted';
  
  // 置信度差距阈值（用于 keep_highest 和 weighted 模式）
  confidenceGapThreshold: number;  // 默认: 0.15
  
  // 降级因子（用于 downgrade_both 模式）
  downgradeFactor: number;  // 默认: 0.5
  
  // 策略权重（用于 weighted 模式）
  strategyWeights?: Record<string, number>;
  
  // 是否记录冲突日志
  logConflicts: boolean;  // 默认: true
}
```

## 裁决结果

### ArbiterResult

```typescript
interface ArbiterResult {
  // 裁决后的信号列表
  signals: Signal[];
  
  // 冲突记录
  conflicts: ConflictRecord[];
  
  // 统计信息
  stats: {
    totalInput: number;        // 输入信号数
    totalOutput: number;       // 输出信号数
    conflictsDetected: number; // 检测到的冲突数
    signalsDiscarded: number;  // 丢弃的信号数
    signalsDowngraded: number; // 降级的信号数
  };
}
```

### ConflictRecord

```typescript
interface ConflictRecord {
  symbol: string;
  name: string;
  date: string;
  buySignals: Signal[];
  sellSignals: Signal[];
  resolution: 'kept_buy' | 'kept_sell' | 'downgraded_both' | 'discarded_both';
  reason: string;
}
```

## 实际应用场景

### 场景1: 日常信号生成

```typescript
// 每日扫描市场，自动裁决冲突
const signals = await signalGenerator.scanMarketMultiStrategy(
  enabledStrategies,
  allStocks,
  'vote',
  strategyWeights,
  0.5,
  true  // 启用裁决
);

// 保存裁决后的信号
await signalGenerator.saveSignals(today, signals);
```

### 场景2: 回测验证

```typescript
// 在回测中使用裁决器，评估不同裁决策略的效果
const arbiterConfigs = [
  { mode: 'keep_highest' },
  { mode: 'downgrade_both' },
  { mode: 'weighted', strategyWeights: weights }
];

for (const config of arbiterConfigs) {
  const arbiter = new SignalArbiter(config);
  const result = arbiter.arbitrate(historicalSignals);
  
  // 评估裁决效果
  const performance = await backtest(result.signals);
  console.log(`${config.mode}: 收益率 ${performance.return}%`);
}
```

### 场景3: 监控和分析

```typescript
// 定期分析冲突情况
const stats = arbiter.getConflictStats();

if (stats.totalConflicts > 100) {
  console.warn('⚠️  冲突率过高，建议检查策略配置');
}

// 找出冲突最多的股票
stats.topConflictSymbols.forEach(item => {
  console.log(`${item.symbol}: ${item.count}次冲突`);
  // 可能需要单独分析这些股票
});
```

## 最佳实践

### 1. 选择合适的裁决模式

- **保守型**：使用 `discard_both`，避免在不确定情况下交易
- **平衡型**：使用 `keep_highest`，保留高置信度信号
- **激进型**：使用 `downgrade_both`，保留所有信息但降低风险
- **策略优先型**：使用 `weighted`，根据策略历史表现分配权重

### 2. 调整置信度阈值

```typescript
// 根据市场环境调整阈值
const arbiter = new SignalArbiter({
  mode: 'keep_highest',
  confidenceGapThreshold: volatileMarket ? 0.20 : 0.15
});
```

### 3. 定期审查冲突统计

```typescript
// 每周审查冲突情况
const weeklyStats = arbiter.getConflictStats();

// 如果某个策略经常产生冲突信号，可能需要调整
if (weeklyStats.resolutionBreakdown.discarded_both > 50) {
  console.log('建议审查策略参数，减少冲突');
}
```

### 4. 结合策略权重

```typescript
// 根据策略历史表现动态调整权重
const strategyPerformance = await analyzeStrategyPerformance();

const weights = {
  'strategy_a': strategyPerformance.strategy_a.winRate,
  'strategy_b': strategyPerformance.strategy_b.winRate,
  'strategy_c': strategyPerformance.strategy_c.winRate
};

const arbiter = new SignalArbiter({
  mode: 'weighted',
  strategyWeights: weights
});
```

## 测试

运行单元测试：

```bash
npx vitest run src/services/quant/signal-arbiter.test.ts
```

运行示例：

```bash
npx tsx src/services/quant/signal-arbiter-example.ts
```

## 文件位置

- **实现**: `/Users/mac/Documents/ai/pi-investment/src/services/quant/signal-arbiter.ts`
- **测试**: `/Users/mac/Documents/ai/pi-investment/src/services/quant/signal-arbiter.test.ts`
- **示例**: `/Users/mac/Documents/ai/pi-investment/src/services/quant/signal-arbiter-example.ts`
- **集成**: `/Users/mac/Documents/ai/pi-investment/src/services/quant/signal-generator.ts`

## 性能考虑

- SignalArbiter 的时间复杂度为 O(n)，其中 n 是信号数量
- 内存占用取决于冲突历史记录，可以定期调用 `clearConflictHistory()` 清理
- 对于大规模信号处理（>10000个信号），建议分批处理

## 未来扩展

可能的扩展方向：

1. **动态权重调整**：根据策略实时表现自动调整权重
2. **时间序列分析**：考虑信号的时间序列特征
3. **市场环境适配**：根据市场波动率自动调整裁决策略
4. **机器学习裁决**：使用ML模型学习最优裁决策略

## 总结

SignalArbiter 提供了一个灵活、可配置的信号冲突解决方案，支持多种裁决模式，能够有效处理多策略系统中的信号冲突问题，提高交易决策的可靠性。
