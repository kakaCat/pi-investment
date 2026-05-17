# 量化系统使用指南

## 概述

量化系统提供了完整的量化交易策略管理、信号生成和股票评分功能，支持机器学习增强的信号预测。

## 核心组件

### 1. QuantService - 策略管理服务

管理量化策略的完整生命周期。

```typescript
import { QuantService } from './services/quant/quant-service.js';

const quantService = new QuantService();

// 创建策略
const strategy = await quantService.createStrategy({
  name: 'RSI超卖策略',
  description: '当RSI低于30且MA5上穿MA10时买入',
  enabled: true,
  screening: {
    market: 'A',
    filters: {
      pe_range: [0, 30],
      market_cap_range: [1000000000, null]
    }
  },
  entry: {
    conditions: [
      { indicator: 'rsi', operator: '<', value: 30, params: {} },
      { indicator: 'ma_cross', operator: 'cross_above', value: 0, params: {} }
    ],
    logic: 'AND'
  },
  exit: {
    stop_loss: 0.05,
    take_profit: 0.15,
    trailing_stop: 0.03
  },
  position: {
    max_position_pct: 0.2,
    max_stocks: 10,
    rebalance_freq: 'weekly'
  }
});

// 查询策略
const allStrategies = await quantService.listStrategies();
const activeStrategies = await quantService.listStrategies(true);
const myStrategy = await quantService.getStrategy(strategy.id);

// 更新策略
await quantService.updateStrategy(strategy.id, {
  description: '更新后的描述',
  exit: { stop_loss: 0.08, take_profit: 0.20 }
});

// 启用/禁用策略
await quantService.disableStrategy(strategy.id);
await quantService.enableStrategy(strategy.id);

// 删除策略
await quantService.deleteStrategy(strategy.id);
```

### 2. SignalGenerator - 信号生成器

基于策略和技术指标生成交易信号，支持ML增强。

```typescript
import { SignalGenerator } from './services/quant/signal-generator.js';

const signalGenerator = new SignalGenerator(
  '.pi-invest/quant/signals',
  undefined,
  true  // 启用ML预测
);

// 准备技术指标数据
const technicals = {
  rsi: 28.5,
  ma5: 10.5,
  ma10: 10.3,
  ma20: 10.0,
  ma60: 9.8,
  macd_dif: 0.15,
  macd_dea: 0.10,
  macd_histogram: 0.05,
  bollinger_upper: 11.0,
  bollinger_mid: 10.2,
  bollinger_lower: 9.4,
  volume_ratio: 2.3,
  atr: 0.25
};

// 生成信号
const signal = await signalGenerator.generateSignal(
  '000001',
  '平安银行',
  strategy,
  technicals,
  10.25  // 当前价格
);

if (signal) {
  console.log(`信号: ${signal.action}`);
  console.log(`置信度: ${signal.confidence}`);
  console.log(`原因: ${signal.reason}`);
}

// 查询历史信号
const recentSignals = await signalGenerator.getRecentSignals(7);
const stockSignals = await signalGenerator.getSignalsBySymbol('000001');
```

### 3. FactorLibrary - 因子库

计算技术指标和股票评分。

```typescript
import { FactorLibrary } from './services/quant/factor-library.js';

const factorLib = new FactorLibrary();

// 计算技术指标
const closes = [10.0, 10.1, 10.2, 10.15, 10.3, ...];

const rsi = factorLib.calculateRSI(closes, 14);
const ma20 = factorLib.calculateMA(closes, 20);
const macd = factorLib.calculateMACD(closes);
const bollinger = factorLib.calculateBollinger(closes, 20, 2);

// 股票评分
const score = factorLib.scoreStock(technicals, 10.25);
console.log(`总分: ${score.total_score}`);
console.log(`推荐: ${score.recommendation}`);
console.log(`因子得分:`, score.factors);
```

## Agent工具

量化系统提供6个Agent工具，可在对话中使用：

### 1. manage_quant_strategy - 策略管理

```typescript
// 创建策略
manage_quant_strategy({
  action: 'create',
  strategy: { /* 策略配置 */ }
})

// 列出策略
manage_quant_strategy({ action: 'list' })

// 更新策略
manage_quant_strategy({
  action: 'update',
  strategy_id: 'xxx',
  updates: { /* 更新字段 */ }
})

// 删除策略
manage_quant_strategy({
  action: 'delete',
  strategy_id: 'xxx'
})
```

### 2. generate_signals - 生成交易信号

```typescript
generate_signals({
  strategy_id: 'xxx',
  symbols: ['000001', '600519'],
  use_ml: true  // 可选，默认true
})
```

### 3. score_stock - 股票评分

```typescript
score_stock({
  symbol: '000001',
  technicals: { /* 技术指标 */ },
  current_price: 10.25
})
```

### 4. train_signal_model - 训练ML模型

```typescript
train_signal_model({
  training_data: [
    {
      technicals: { /* 技术指标 */ },
      label: 1  // 1=买入信号有效, 0=无效
    },
    // 更多训练样本...
  ]
})
```

### 5. run_backtest - 回测策略（可选）

```typescript
run_backtest({
  strategy_id: 'xxx',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
  commission: 0.0003
})
```

### 6. get_strategy_performance - 获取策略表现

```typescript
get_strategy_performance({
  strategy_id: 'xxx',
  period_days: 30  // 可选，默认30天
})
```

## 机器学习功能

### 特征提取

系统自动从技术指标中提取8维特征向量：

1. RSI归一化值
2. MA5/MA20比率
3. MA10/MA20比率
4. MA20/MA60比率
5. MACD柱状图
6. 布林带位置
7. 成交量比率
8. ATR归一化值

### 模型训练

```python
# Python端训练（通过Agent工具调用）
from ml.signal_trainer import SignalTrainer

trainer = SignalTrainer()
result = trainer.train(training_data)
# 模型保存到 .pi-invest/quant/models/signal_model.json
```

### ML预测

```python
# Python端预测（SignalGenerator自动调用）
from ml.signal_predictor import SignalPredictor

predictor = SignalPredictor()
result = predictor.predict(technicals)
# 返回 {"confidence": 0.75, "model": "xgboost"}
```

## 数据存储

### 目录结构

```
.pi-invest/quant/
├── strategies/          # 策略JSON文件
│   └── {strategy_id}.json
├── signals/            # 信号JSON文件
│   └── {date}/
│       └── {symbol}_{timestamp}.json
└── models/             # ML模型文件
    └── signal_model.json
```

### 策略文件格式

```json
{
  "id": "uuid",
  "name": "策略名称",
  "description": "策略描述",
  "enabled": true,
  "created_at": "2024-01-01T00:00:00Z",
  "screening": { /* 筛选条件 */ },
  "entry": { /* 入场条件 */ },
  "exit": { /* 出场条件 */ },
  "position": { /* 仓位管理 */ }
}
```

### 信号文件格式

```json
{
  "date": "2024-01-01T10:30:00Z",
  "symbol": "000001",
  "name": "平安银行",
  "action": "buy",
  "strategy_id": "uuid",
  "price": 10.25,
  "reason": "RSI超卖且MA金叉",
  "confidence": 0.85,
  "indicators": { /* 技术指标快照 */ }
}
```

## 最佳实践

### 1. 策略设计

- **明确目标**：定义清晰的入场和出场条件
- **风险控制**：设置合理的止损和止盈
- **仓位管理**：限制单只股票和总仓位比例
- **回测验证**：使用历史数据验证策略有效性

### 2. 信号生成

- **启用ML**：对于复杂市场环境，启用ML预测提高准确率
- **置信度过滤**：只执行高置信度信号（如 > 0.7）
- **多策略组合**：使用多个策略分散风险

### 3. 模型训练

- **数据质量**：使用足够多的高质量训练样本（建议 > 1000）
- **标签准确**：确保训练标签反映真实信号有效性
- **定期重训**：市场环境变化时重新训练模型

### 4. 性能监控

- **跟踪信号**：记录所有生成的信号
- **评估准确率**：定期评估信号的实际表现
- **策略调优**：根据表现调整策略参数

## 示例：完整工作流

```typescript
// 1. 创建策略
const strategy = await quantService.createStrategy({
  name: 'MACD金叉策略',
  description: 'MACD金叉且RSI不超买时买入',
  enabled: true,
  screening: {
    market: 'A',
    filters: { pe_range: [0, 50] }
  },
  entry: {
    conditions: [
      { indicator: 'macd', operator: 'cross_above', value: 0, params: {} },
      { indicator: 'rsi', operator: '<', value: 70, params: {} }
    ],
    logic: 'AND'
  },
  exit: {
    stop_loss: 0.05,
    take_profit: 0.15
  },
  position: {
    max_position_pct: 0.15,
    max_stocks: 15
  }
});

// 2. 获取股票列表和技术指标
const stocks = await getStockList('A');
const signals = [];

for (const stock of stocks) {
  const klines = await getKlines(stock.symbol, '1d', 100);
  const closes = klines.map(k => k.close);
  
  // 计算技术指标
  const technicals = {
    rsi: factorLib.calculateRSI(closes, 14),
    ma5: factorLib.calculateMA(closes, 5),
    ma10: factorLib.calculateMA(closes, 10),
    ma20: factorLib.calculateMA(closes, 20),
    ma60: factorLib.calculateMA(closes, 60),
    ...factorLib.calculateMACD(closes),
    ...factorLib.calculateBollinger(closes, 20, 2),
    volume_ratio: klines[klines.length - 1].volume / avgVolume,
    atr: calculateATR(klines, 14)
  };
  
  // 生成信号
  const signal = await signalGenerator.generateSignal(
    stock.symbol,
    stock.name,
    strategy,
    technicals,
    closes[closes.length - 1]
  );
  
  if (signal && signal.confidence > 0.7) {
    signals.push(signal);
  }
}

// 3. 按置信度排序并选择前10个
signals.sort((a, b) => b.confidence - a.confidence);
const topSignals = signals.slice(0, 10);

console.log('今日推荐买入:', topSignals);
```

## 故障排除

### ML预测失败

如果ML预测返回null，检查：
1. 模型是否已训练（`.pi-invest/quant/models/signal_model.json`存在）
2. Python环境是否正确配置
3. 技术指标数据是否完整

解决方案：
- 运行`train_signal_model`工具训练模型
- 或禁用ML：`new SignalGenerator(dir, undefined, false)`

### 策略不生成信号

检查：
1. 策略是否启用（`enabled: true`）
2. 入场条件是否过于严格
3. 技术指标数据是否准确

### 性能问题

优化建议：
1. 限制并发信号生成数量
2. 缓存技术指标计算结果
3. 使用数据库存储历史信号而非文件系统

## 技术架构

```
┌─────────────────────────────────────────┐
│           Agent Tools Layer             │
│  (quant-tools.ts - 6 tools)            │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Service Layer                   │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │ QuantService │  │ SignalGenerator │ │
│  └──────────────┘  └─────────────────┘ │
│  ┌──────────────────────────────────┐  │
│  │      FactorLibrary               │  │
│  └──────────────────────────────────┘  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Python ML Layer                 │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │FeatureExtract│  │ SignalPredictor │ │
│  └──────────────┘  └─────────────────┘ │
│  ┌──────────────────────────────────┐  │
│  │      SignalTrainer               │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## 相关文档

- [量化系统设计文档](./superpowers/specs/2026-05-17-quant-system-design.md)
- [量化系统实现计划](./superpowers/plans/2026-05-17-quant-system-implementation.md)
- [API文档](../src/services/quant/README.md)
