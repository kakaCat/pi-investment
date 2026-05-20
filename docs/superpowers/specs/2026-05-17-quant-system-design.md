# 量化系统完整实现 - 设计文档

**日期**: 2026-05-17  
**任务**: 恢复并增强量化交易系统  
**状态**: 设计完成，待实施

## 目录

1. [背景](#背景)
2. [目标](#目标)
3. [架构设计](#架构设计)
4. [服务层设计](#服务层设计)
5. [Python ML 层设计](#python-ml-层设计)
6. [Agent 工具层设计](#agent-工具层设计)
7. [定时任务设计](#定时任务设计)
8. [错误处理与降级策略](#错误处理与降级策略)
9. [数据流设计](#数据流设计)
10. [文件结构](#文件结构)
11. [实施计划](#实施计划)

---

## 背景

### 问题现状

1. **SOUL.md 要求使用量化工具**：Phase 4B 强制要求使用 `generate_signals`、`score_stock`、`query_experience` 三个工具
2. **工具未实现**：`generate_signals` 和 `score_stock` 不存在，只有 `query_experience` 可用
3. **历史实现被删除**：2026-05-14 删除了完整的量化系统（commit `1daf5d4`）

### 删除原因

- 项目从 Python ML 方案转向纯 TypeScript 方案
- ML 相关代码已被禁用但仍存在，造成维护负担
- 但删除时误将纯 TS 的量化系统也一起删了

### 历史实现

- **commit `edff27c`** (2026-03-29) - 完整的纯 TS 量化系统
- **commit `3137c6e`** (2026-03-30) - 添加了 XGBoost ML 增强
- **commit `1daf5d4`** (2026-05-14) - 删除 ML 残骸时连同量化系统一起删除

---

## 目标

### 功能目标

1. **恢复完整量化系统**：策略管理、信号生成、回测引擎、因子库
2. **集成 Python ML**：XGBoost 信号置信度预测，带降级策略
3. **实现 Agent 工具**：`generate_signals`、`score_stock`、`manage_quant_strategy`、`run_backtest`、`train_signal_model`
4. **定时任务**：每日信号扫描、每周模型重训练、绩效报告、策略健康检查

### 技术目标

1. **适配当前架构**：使用新的 Python caller（`callPythonResilient`）、新缓存系统
2. **错误处理完善**：多级降级、超时保护、快速失败
3. **可维护性**：清晰的分层设计、完整的测试覆盖

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Scheduled Tasks (CRON)                    │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ Daily Signal   │  │ Model Retrain  │  │ Performance  │  │
│  │ Scan (15:05)   │  │ (Weekly)       │  │ Report (Daily)│  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      Agent Tools Layer                       │
│  generate_signals | score_stock | manage_quant_strategy     │
│  run_backtest | train_signal_model | get_strategy_performance│
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                   Service Layer (TS)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │QuantService  │  │SignalGenerator│  │BacktestEngine│     │
│  │(策略CRUD)    │  │(信号生成)     │  │(回测引擎)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────────────────────────────────────────┐      │
│  │         FactorLibrary (因子计算)                  │      │
│  └──────────────────────────────────────────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌──▼──────┐ ┌──▼────────────────┐
│ AkShare-TS   │ │Pipeline │ │Python ML (XGBoost)│
│(实时数据)    │ │SQLite   │ │signal_predictor   │
│              │ │(历史K线)│ │signal_trainer     │
└──────────────┘ └─────────┘ └───────────────────┘
```

### 分层职责

| 层级 | 职责 | 技术栈 |
|------|------|--------|
| **定时任务层** | 自动化执行周期性任务 | CRON + TS scripts |
| **工具层** | Agent 可调用的函数接口 | TypeScript |
| **服务层** | 业务逻辑实现 | TypeScript |
| **数据层** | 数据获取和存储 | AkShare-TS + SQLite |
| **ML 层** | 机器学习增强 | Python + XGBoost |

---

## 服务层设计

### 1. QuantService（策略管理）

**文件路径**: `src/services/quant/quant-service.ts`

**职责**: 策略的增删改查，文件存储

**核心方法**:

```typescript
class QuantService {
  private strategiesDir = '.pi-invest/quant/strategies';
  
  // 策略 CRUD
  async createStrategy(strategy: Omit<QuantStrategy, 'id' | 'created_at'>): Promise<QuantStrategy>
  async listStrategies(): Promise<QuantStrategy[]>
  async getStrategy(id: string): Promise<QuantStrategy | null>
  async updateStrategy(id: string, updates: Partial<QuantStrategy>): Promise<QuantStrategy | null>
  async deleteStrategy(id: string): Promise<boolean>
  
  // 策略启用/禁用
  async enableStrategy(id: string): Promise<QuantStrategy | null>
  async disableStrategy(id: string): Promise<QuantStrategy | null>
}
```

**存储格式**: JSON 文件，存储在 `.pi-invest/quant/strategies/strategy_<timestamp>.json`

---

### 2. SignalGenerator（信号生成）

**文件路径**: `src/services/quant/signal-generator.ts`

**职责**: 根据策略生成买卖信号

**核心方法**:

```typescript
class SignalGenerator {
  private signalsDir = '.pi-invest/quant/signals';
  private stockDB: StockDBService;
  private factorLib: FactorLibrary;
  
  // 核心方法
  async scan(strategy: QuantStrategy): Promise<Signal[]>
  
  // 内部方法
  private async getStockPool(strategy: QuantStrategy): Promise<string[]>
  private async checkStock(symbol: string, strategy: QuantStrategy): Promise<Signal | null>
  private matchConditions(indicators: any, conditions: EntryCondition[], logic: 'AND' | 'OR'): boolean
  private async predictConfidence(signal: Signal): Promise<number>  // 调用 Python ML
  private async saveSignals(date: string, signals: Signal[]): Promise<void>
}
```

**信号生成流程**:

```typescript
async scan(strategy: QuantStrategy): Promise<Signal[]> {
  // 1. 获取股票池（根据策略筛选条件）
  const symbols = await this.getStockPool(strategy);
  
  // 2. 分批并行检查（每批 20 只，带超时保护）
  const batchSize = 20;
  const batches = this.chunk(symbols, batchSize);
  const allSignals: Signal[] = [];
  
  for (const batch of batches) {
    const signals = await Promise.all(
      batch.map(symbol => this.checkStock(symbol, strategy))
    );
    allSignals.push(...signals.filter(s => s !== null));
  }
  
  // 3. 调用 ML 预测置信度（带降级）
  for (const signal of allSignals) {
    signal.confidence = await this.predictConfidence(signal);
  }
  
  // 4. 保存信号
  await this.saveSignals(today, allSignals);
  
  return allSignals;
}
```

**存储格式**: JSON 文件，存储在 `.pi-invest/quant/signals/YYYY-MM-DD.json`

---

### 3. BacktestEngine（回测引擎）

**文件路径**: `src/services/quant/backtest-engine.ts`

**职责**: 在历史数据上模拟交易，计算策略表现

**核心方法**:

```typescript
class BacktestEngine {
  private backtestsDir = '.pi-invest/quant/backtests';
  private stockDB: StockDBService;
  private factorLib: FactorLibrary;
  
  // 核心方法
  async run(options: BacktestOptions): Promise<BacktestResult>
  
  // 内部方法
  private async getHistoricalData(symbol: string, startDate: string, endDate: string): Promise<KlineBar[]>
  private checkSignal(bar: KlineBar, indicators: any, conditions: EntryCondition[]): boolean
  private simulateTrade(portfolio: Portfolio, signal: Signal, bar: KlineBar): void
  private calculatePerformance(trades: Trade[]): PerformanceMetrics
  private async saveBacktest(result: BacktestResult): Promise<void>
}
```

**回测流程**:

```typescript
async run(options: BacktestOptions): Promise<BacktestResult> {
  // 前置检查（快速失败）
  const strategy = await quantService.getStrategy(options.strategy_id);
  if (!strategy || !strategy.enabled) throw new Error('策略不可用');
  
  const symbols = await this.getStockPool(strategy);
  let portfolio = { cash: options.initial_capital, positions: [] };
  const trades: Trade[] = [];
  
  // 逐日模拟
  for (let date = startDate; date <= endDate; date = nextDay(date)) {
    for (const symbol of symbols) {
      const bar = await this.getBar(symbol, date);
      const indicators = await factorLib.calculate(symbol, date);
      
      // 检查买入信号
      if (this.checkSignal(bar, indicators, strategy.entry.conditions)) {
        this.openPosition(portfolio, symbol, bar, strategy);
        trades.push({ action: 'buy', date, symbol, price: bar.close, ... });
      }
      
      // 检查卖出信号/止损/止盈
      if (this.shouldExit(portfolio, symbol, bar, indicators, strategy)) {
        this.closePosition(portfolio, symbol, bar);
        trades.push({ action: 'sell', date, symbol, price: bar.close, ... });
      }
    }
  }
  
  // 计算绩效
  const performance = this.calculatePerformance(trades);
  const result = { strategy_id, period, performance, trades, equity_curve, ... };
  
  await this.saveBacktest(result);
  return result;
}
```

**绩效指标**:
- 总收益率、年化收益率
- 夏普比率、最大回撤
- 胜率、盈亏比
- 交易次数、平均持仓天数

**存储格式**: JSON 文件，存储在 `.pi-invest/quant/backtests/backtest_<timestamp>.json`

---

### 4. FactorLibrary（因子计算）

**文件路径**: `src/services/quant/factor-library.ts`

**职责**: 计算技术指标和多因子评分

**核心方法**:

```typescript
class FactorLibrary {
  private stockDB: StockDBService;
  
  // 技术指标计算
  async calculate(symbol: string, date: string): Promise<TechnicalIndicators>
  
  // 单个指标
  async calculateRSI(bars: KlineBar[], period: number): Promise<number>
  async calculateMA(bars: KlineBar[], period: number): Promise<number>
  async calculateMACD(bars: KlineBar[]): Promise<{ dif: number; dea: number; histogram: number }>
  async calculateBollinger(bars: KlineBar[], period: number): Promise<{ upper: number; mid: number; lower: number }>
  
  // 因子评分
  async scoreStock(symbol: string): Promise<StockScore>
}
```

**多因子评分逻辑**:

```typescript
async scoreStock(symbol: string): Promise<StockScore> {
  const indicators = await this.calculate(symbol, today);
  const fundamentals = await getFundamentals(symbol);
  
  // 技术面评分（0-100）
  const technicalScore = 
    (indicators.rsi < 30 ? 30 : 0) +              // 超卖 +30
    (indicators.ma5 > indicators.ma20 ? 20 : 0) + // 金叉 +20
    (indicators.macd_histogram > 0 ? 20 : 0) +    // MACD 多头 +20
    (indicators.volume_ratio > 1.5 ? 15 : 0) +    // 放量 +15
    (indicators.bb_position < 0.2 ? 15 : 0);      // 布林下轨 +15
  
  // 基本面评分（0-100）
  const fundamentalScore =
    (fundamentals.pe_percentile < 40 ? 30 : 0) +  // 低估 +30
    (fundamentals.roe > 12 ? 25 : 0) +             // 高 ROE +25
    (fundamentals.debt_ratio < 60 ? 20 : 0) +      // 低负债 +20
    (fundamentals.quality_score > 65 ? 25 : 0);    // 高质量 +25
  
  // 综合评分（加权平均）
  const totalScore = technicalScore * 0.6 + fundamentalScore * 0.4;
  
  return {
    symbol,
    total_score: totalScore,
    technical_score: technicalScore,
    fundamental_score: fundamentalScore,
    recommendation: totalScore > 70 ? 'buy' : totalScore > 50 ? 'hold' : 'avoid'
  };
}
```

---

## Python ML 层设计

### 模块结构

```
python/ml/
├── __init__.py
├── signal_trainer.py      # XGBoost 模型训练
├── signal_predictor.py    # 信号置信度预测
└── feature_extractor.py   # 特征提取（新增）
```

---

### 1. signal_trainer.py（模型训练）

**功能**: 从历史信号中学习，训练 XGBoost 分类器

**训练流程**:

```python
def train_model(days: int = 30, min_samples: int = 50) -> dict:
    # 1. 加载历史信号
    signals = load_signals_from_dir('.pi-invest/quant/signals/')
    
    # 2. 计算每个信号的实际收益率（5日后）
    labeled_data = []
    for signal in signals:
        future_return = get_future_return(signal.symbol, signal.date, days=5)
        label = 1 if future_return > 0.02 else 0  # 收益>2%为正样本
        features = extract_features(signal)
        labeled_data.append((features, label))
    
    # 3. 检查样本数
    if len(labeled_data) < min_samples:
        return {"error": f"样本不足，需要至少 {min_samples} 条"}
    
    # 4. 训练 XGBoost
    X, y = split_features_labels(labeled_data)
    model = xgboost.XGBClassifier(max_depth=5, n_estimators=100)
    model.fit(X, y)
    
    # 5. 保存模型
    save_model(model, '.pi-invest/quant/models/signal_confidence.pkl')
    
    # 6. 返回训练报告
    return {
        "samples": len(labeled_data),
        "accuracy": model.score(X, y),
        "feature_importance": model.feature_importances_.tolist()
    }
```

**特征列表**:
- `rsi` - RSI 指标
- `ma5_ma20_ratio` - 短期均线/长期均线
- `ma20_ma60_ratio` - 中期均线/长期均线
- `macd_histogram` - MACD 柱状图
- `bb_position` - 布林带位置（0-1）
- `volume_ratio` - 成交量比率
- `conditions_matched_ratio` - 策略条件匹配度
- `action` - 买入(0) 或 卖出(1)

---

### 2. signal_predictor.py（置信度预测）

**功能**: 预测信号的成功概率

```python
def predict_confidence(features: dict) -> dict:
    model_path = '.pi-invest/quant/models/signal_confidence.pkl'
    
    # 模型不存在时降级
    if not os.path.exists(model_path):
        return {"confidence": None, "model": "none"}
    
    try:
        model = load_model(model_path)
        
        # 特征向量（顺序必须与训练时一致）
        X = np.array([[
            features['rsi'],
            features['ma5_ma20_ratio'],
            features['ma20_ma60_ratio'],
            features['macd_histogram'],
            features['bb_position'],
            features['volume_ratio'],
            features['conditions_matched_ratio'],
            features['action']
        ]])
        
        # 预测概率
        proba = model.predict_proba(X)[0][1]  # 正类概率
        
        return {
            "confidence": float(proba),
            "model": "xgboost"
        }
    except Exception as e:
        return {
            "confidence": None,
            "model": "none",
            "error": str(e)
        }
```

---

### 3. feature_extractor.py（特征提取）

**功能**: 从信号对象中提取标准化特征

```python
def extract_features(signal: dict) -> dict:
    """从信号中提取 ML 特征"""
    indicators = signal.get('indicators', {})
    
    # 安全获取指标值
    rsi = indicators.get('rsi', 50)
    ma5 = indicators.get('ma5', 0)
    ma20 = indicators.get('ma20', 1)
    ma60 = indicators.get('ma60', 1)
    macd_hist = indicators.get('macd_histogram', 0)
    bb_upper = indicators.get('bollinger', {}).get('upper', 0)
    bb_lower = indicators.get('bollinger', {}).get('lower', 0)
    current_price = indicators.get('current_price', 0)
    volume_ratio = indicators.get('volume_ratio', 1)
    
    # 计算衍生特征
    ma5_ma20_ratio = ma5 / ma20 if ma20 > 0 else 1
    ma20_ma60_ratio = ma20 / ma60 if ma60 > 0 else 1
    bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5
    
    # 策略条件匹配度
    conditions_matched = len(signal.get('reason', '').split(','))
    conditions_matched_ratio = min(conditions_matched / 3, 1.0)
    
    return {
        'rsi': rsi,
        'ma5_ma20_ratio': ma5_ma20_ratio,
        'ma20_ma60_ratio': ma20_ma60_ratio,
        'macd_histogram': macd_hist,
        'bb_position': bb_position,
        'volume_ratio': volume_ratio,
        'conditions_matched_ratio': conditions_matched_ratio,
        'action': 0 if signal.get('action') == 'buy' else 1
    }
```

---

### 4. 在 akshare_bridge.py 中注册

```python
# 在 akshare_bridge.py 末尾添加

def predict_signal_confidence(args: dict) -> dict:
    """预测信号置信度（调用 ML 模块）"""
    from ml.signal_predictor import predict_confidence
    return predict_confidence(args.get('features', {}))

def train_signal_model(args: dict) -> dict:
    """训练信号置信度模型"""
    from ml.signal_trainer import train_model
    days = args.get('days', 30)
    min_samples = args.get('min_samples', 50)
    return train_model(days, min_samples)
```

---

### 5. TypeScript 调用 Python ML

```typescript
// 在 SignalGenerator 中
private async predictConfidence(signal: Signal, retries: number = 2): Promise<number> {
  // Level 1: 尝试 XGBoost ML 模型
  for (let i = 0; i < retries; i++) {
    try {
      const features = this.extractFeatures(signal);
      const result = await callPython('predict_signal_confidence', { features });
      const data = JSON.parse(result);
      
      if (data.confidence !== null && data.confidence !== undefined) {
        return data.confidence;
      }
    } catch (error) {
      if (i === retries - 1) {
        console.warn('ML 预测失败，降级到规则引擎');
        return this.ruleBasedConfidence(signal);
      }
      await this.sleep(1000 * (i + 1));
    }
  }
  
  // Level 2: 规则引擎（基于技术指标）
  return this.ruleBasedConfidence(signal);
}

private ruleBasedConfidence(signal: Signal): number {
  const ind = signal.indicators;
  let score = 0.5;  // 基础分
  
  // RSI 超卖/超买
  if (signal.action === 'buy' && ind.rsi < 30) score += 0.2;
  if (signal.action === 'sell' && ind.rsi > 70) score += 0.2;
  
  // 均线多头/空头排列
  if (ind.ma5 > ind.ma20 && ind.ma20 > ind.ma60) score += 0.15;
  
  // MACD 金叉/死叉
  if (ind.macd_histogram > 0) score += 0.1;
  
  // 成交量放大
  if (ind.volume_ratio > 1.5) score += 0.05;
  
  return Math.max(0.1, Math.min(0.9, score));
}
```

---

## Agent 工具层设计

### 工具列表

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `generate_signals` | 生成买卖信号 | action, strategy_id, symbol |
| `score_stock` | 多因子评分 | symbol |
| `manage_quant_strategy` | 策略管理 | action, strategy_id, strategy |
| `run_backtest` | 运行回测 | strategy_id, start_date, end_date, initial_capital |
| `train_signal_model` | 训练 ML 模型 | days, min_samples |
| `get_strategy_performance` | 策略表现统计 | strategy_id, days |

---

### 1. generate_signals

```typescript
{
  name: 'generate_signals',
  description: `扫描市场生成买卖信号。
  
  使用场景：
  - 扫描所有启用的策略，生成今日信号
  - 为特定策略生成信号
  - 为单只股票生成信号`,
  
  parameters: {
    action: 'scan' | 'check',
    strategy_id?: string,
    symbol?: string
  }
}
```

---

### 2. score_stock

```typescript
{
  name: 'score_stock',
  description: `对股票进行多因子综合评分（0-100分）。
  
  评分维度：
  - 技术面：RSI、均线、MACD、成交量、布林带
  - 基本面：PE分位、ROE、负债率、质量评分`,
  
  parameters: {
    symbol: string
  }
}
```

---

### 3. manage_quant_strategy

```typescript
{
  name: 'manage_quant_strategy',
  description: '管理量化策略：创建、列出、查看、删除、启用/禁用',
  
  parameters: {
    action: 'create' | 'list' | 'get' | 'delete' | 'enable' | 'disable',
    strategy_id?: string,
    strategy?: QuantStrategy
  }
}
```

---

### 4. run_backtest

```typescript
{
  name: 'run_backtest',
  description: `在历史数据上回测策略表现。
  
  返回：总收益率、年化收益率、夏普比率、最大回撤、胜率、盈亏比`,
  
  parameters: {
    strategy_id: string,
    start_date: string,
    end_date: string,
    initial_capital: number,
    commission: number
  }
}
```

---

### 5. train_signal_model

```typescript
{
  name: 'train_signal_model',
  description: `使用历史信号数据训练 XGBoost 模型。
  
  要求：至少 50 条历史信号`,
  
  parameters: {
    days: number,
    min_samples: number
  }
}
```

---

### 6. get_strategy_performance

```typescript
{
  name: 'get_strategy_performance',
  description: '统计策略的历史信号表现',
  
  parameters: {
    strategy_id: string,
    days: number
  }
}
```

---

## 定时任务设计

### 新增的 CRON 任务

**1. 每日量化信号扫描**

```json
{
  "id": "quant-daily-scan",
  "name": "量化信号每日扫描",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "5 15 * * 1-5"
  },
  "payload": {
    "kind": "agent_turn",
    "message": "扫描所有启用的量化策略，生成今日买卖信号"
  }
}
```

**执行模式**: Agent 驱动（智能分析）

---

**2. 每周模型重训练**

```json
{
  "id": "quant-retrain-model",
  "name": "量化模型重训练",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 20 * * 0"
  },
  "payload": {
    "kind": "system_event",
    "message": "retrain_signal_model"
  }
}
```

**执行模式**: 纯自动化（确定性任务）

---

**3. 每日绩效报告**

```json
{
  "id": "quant-daily-report",
  "name": "量化策略绩效报告",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 16 * * 1-5"
  },
  "payload": {
    "kind": "agent_turn",
    "message": "生成量化策略今日绩效报告，分析信号质量"
  }
}
```

**执行模式**: Agent 驱动（需要分析和洞察）

---

**4. 每月策略健康检查**

```json
{
  "id": "quant-health-check",
  "name": "量化策略健康检查",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 9 1 * *"
  },
  "payload": {
    "kind": "agent_turn",
    "message": "检查所有量化策略的健康状态，自动禁用表现差的策略"
  }
}
```

**执行模式**: Agent 驱动（需要判断）

---

### 定时任务执行流程

```
16:00 - Pipeline 更新（已有）
  ↓ 更新股票列表和 K 线数据到 SQLite
  
15:05 - 量化信号扫描（新增）
  ↓ 使用最新数据生成信号
  
16:00 - 量化绩效报告（新增）
  ↓ 分析今日信号质量
  
周日 20:00 - 模型重训练（新增）
  ↓ 使用历史信号重新训练 XGBoost
```

---

## 错误处理与降级策略

### 1. ML 层降级（多级 Fallback）

```
Level 1: XGBoost ML 模型
  ↓ 失败
Level 2: 规则引擎（基于技术指标）
  ↓ 返回默认置信度
```

### 2. 错误分类与处理

| 错误类型 | 处理策略 | 示例 |
|---------|---------|------|
| **数据缺失** | 跳过该股票，继续处理 | K 线数据不存在 |
| **网络超时** | 重试 2 次，失败则降级 | Python 调用超时 |
| **模型不存在** | 降级到规则引擎 | XGBoost 模型文件缺失 |
| **参数错误** | 快速失败，抛出异常 | 日期格式错误 |
| **系统错误** | 记录日志，发送告警 | 磁盘满、内存不足 |

### 3. 超时保护

- **信号扫描**: 分批处理（每批 20 只），单批超时跳过
- **Python 调用**: 使用 `callPythonResilient`（10s/30s/60s 分级超时）
- **回测引擎**: 前置检查，最多回测 730 天

### 4. 定时任务错误处理

```typescript
// 单个策略失败不中断整个任务
for (const strategy of enabled) {
  try {
    const signals = await generator.scan(strategy);
    results.push({ strategy: strategy.name, signals: signals.length, success: true });
  } catch (error) {
    console.error(`策略 ${strategy.name} 扫描失败:`, error);
    results.push({ strategy: strategy.name, error: error.message, success: false });
    // 继续下一个策略
  }
}

// 如果全部失败，发送告警
if (summary.success_count === 0) {
  await sendAlert('量化信号扫描全部失败，请检查系统');
}
```

---

## 数据流设计

### 信号生成流程

```
1. Agent 调用 generate_signals(symbol)
   ↓
2. SignalGenerator 获取股票池
   ↓
3. 对每只股票：
   a. 从 AkShare-TS 获取实时价格
   b. 从 Pipeline SQLite 获取历史 K 线
   c. FactorLibrary 计算技术指标
   d. 匹配策略条件（RSI、MA、MACD 等）
   e. 调用 Python ML 预测置信度（可选）
   ↓
4. 返回信号列表，保存到 .pi-invest/quant/signals/
```

### 回测流程

```
1. Agent 调用 run_backtest(strategy_id, start_date, end_date)
   ↓
2. BacktestEngine 加载策略定义
   ↓
3. 从 Pipeline SQLite 获取历史数据
   ↓
4. 逐日模拟交易：
   a. 检查买入信号 → 开仓
   b. 检查卖出信号/止损/止盈 → 平仓
   c. 记录交易明细
   ↓
5. 计算绩效指标（收益率、夏普、最大回撤）
   ↓
6. 返回回测报告，保存到 .pi-invest/quant/backtests/
```

---

## 文件结构

### 新增文件

```
src/services/quant/
├── types.ts                    # 类型定义（已存在）
├── quant-service.ts            # 策略管理服务（恢复）
├── signal-generator.ts         # 信号生成器（恢复）
├── backtest-engine.ts          # 回测引擎（恢复）
├── factor-library.ts           # 因子库（恢复）
├── performance-analyzer.ts     # 绩效分析器（新增）
├── quant-service.test.ts       # 单元测试
├── signal-generator.test.ts    # 单元测试
└── backtest-engine.test.ts     # 单元测试

src/infrastructure/tools/
└── quant-tools.ts              # 量化工具定义（恢复）

python/ml/
├── __init__.py
├── signal_trainer.py           # 模型训练（恢复）
├── signal_predictor.py         # 置信度预测（恢复）
└── feature_extractor.py        # 特征提取（新增）

src/scripts/
├── quant-daily-scan.ts         # 每日信号扫描脚本（新增）
├── quant-retrain-model.ts      # 模型重训练脚本（新增）
└── quant-health-check.ts       # 策略健康检查脚本（新增）

.pi-invest/quant/
├── strategies/                 # 策略定义（已存在）
├── signals/                    # 信号记录（已存在）
├── backtests/                  # 回测结果（已存在）
├── models/                     # ML 模型（新增）
│   └── signal_confidence.pkl
└── reports/                    # 绩效报告（新增）
    └── YYYY-MM-DD.md
```

---

## 实施计划

### Phase 1: 服务层恢复（优先级：P0）

**目标**: 恢复核心服务类，实现基础功能

**任务**:

1. **恢复 QuantService**
   - 从 `edff27c` 恢复 `quant-service.ts`
   - 适配当前项目结构
   - 编写单元测试
   - **预计时间**: 2 小时

2. **恢复 SignalGenerator**
   - 从 `edff27c` 恢复 `signal-generator.ts`
   - 集成 `callPythonResilient`
   - 实现降级策略（规则引擎）
   - 添加超时保护和分批处理
   - 编写单元测试
   - **预计时间**: 4 小时

3. **恢复 BacktestEngine**
   - 从 `edff27c` 恢复 `backtest-engine.ts`
   - 优化性能（分批加载数据）
   - 添加前置检查（快速失败）
   - 编写单元测试
   - **预计时间**: 4 小时

4. **恢复 FactorLibrary**
   - 从 `edff27c` 恢复 `factor-library.ts`
   - 实现 `scoreStock` 多因子评分
   - 复用现有的 `analyze_technical` 工具
   - 编写单元测试
   - **预计时间**: 3 小时

**验收标准**:
- ✅ 所有服务类单元测试通过
- ✅ 可以创建策略、生成信号、运行回测
- ✅ TypeScript 编译无错误

**总计时间**: 13 小时（约 2 天）

---

### Phase 2: 工具层实现（优先级：P0）

**目标**: 实现 Agent 工具，满足 SOUL.md Phase 4B 要求

**任务**:

1. **实现 quant-tools.ts**
   - 从 `edff27c` 恢复工具定义
   - 实现 6 个工具：
     - `generate_signals`
     - `score_stock`
     - `manage_quant_strategy`
     - `run_backtest`
     - `train_signal_model`
     - `get_strategy_performance`
   - **预计时间**: 4 小时

2. **注册工具到 index.ts**
   - 在 `src/infrastructure/tools/index.ts` 中添加 `quantTools`
   - 验证工具可被 Agent 调用
   - **预计时间**: 1 小时

3. **集成测试**
   - 手动测试每个工具
   - 验证与 Agent 的集成
   - **预计时间**: 2 小时

**验收标准**:
- ✅ Agent 可以调用所有 6 个量化工具
- ✅ SOUL.md Phase 4B 要求的工具全部可用
- ✅ 工具返回格式正确

**总计时间**: 7 小时（约 1 天）

---

### Phase 3: Python ML 层实现（优先级：P1）

**目标**: 恢复 ML 增强功能

**任务**:

1. **恢复 Python ML 模块**
   - 从 `3137c6e` 恢复 `python/ml/` 目录
   - 新增 `feature_extractor.py`
   - **预计时间**: 2 小时

2. **在 akshare_bridge.py 中注册函数**
   - 注册 `predict_signal_confidence`
   - 注册 `train_signal_model`
   - 测试 Python 调用
   - **预计时间**: 1 小时

3. **集成到 SignalGenerator**
   - 实现 `predictConfidence` 方法
   - 实现 `ruleBasedConfidence` 降级
   - 添加重试逻辑
   - **预计时间**: 2 小时

4. **训练初始模型**
   - 收集历史信号数据（如果有）
   - 训练第一个 XGBoost 模型
   - 验证预测功能
   - **预计时间**: 2 小时

**验收标准**:
- ✅ Python ML 模块可以被 TS 调用
- ✅ 模型不存在时自动降级到规则引擎
- ✅ 训练功能正常工作

**总计时间**: 7 小时（约 1 天）

---

### Phase 4: 定时任务实现（优先级：P1）

**目标**: 实现自动化任务

**任务**:

1. **实现定时任务脚本**
   - `quant-daily-scan.ts` - 每日信号扫描
   - `quant-retrain-model.ts` - 模型重训练
   - `quant-health-check.ts` - 策略健康检查
   - **预计时间**: 4 小时

2. **添加 CRON 配置**
   - 在 `.pi-invest/CRON.json` 中添加 4 个任务
   - 测试定时触发
   - **预计时间**: 1 小时

3. **扩展 CronService**
   - 添加对 `system_event: "retrain_signal_model"` 的处理
   - **预计时间**: 1 小时

4. **实现 PerformanceAnalyzer**
   - 新增 `performance-analyzer.ts`
   - 实现策略表现统计
   - **预计时间**: 3 小时

**验收标准**:
- ✅ 定时任务可以自动执行
- ✅ 任务失败不影响其他任务
- ✅ 绩效报告生成正常

**总计时间**: 9 小时（约 1.5 天）

---

### Phase 5: 测试与优化（优先级：P2）

**目标**: 完善测试覆盖，优化性能

**任务**:

1. **单元测试补充**
   - 所有服务类达到 80% 覆盖率
   - **预计时间**: 4 小时

2. **集成测试**
   - 端到端测试（创建策略 → 回测 → 生成信号）
   - **预计时间**: 3 小时

3. **性能优化**
   - 回测引擎性能优化（批量加载数据）
   - 信号扫描并发优化
   - **预计时间**: 3 小时

4. **文档完善**
   - 更新 README
   - 编写使用示例
   - **预计时间**: 2 小时

**验收标准**:
- ✅ 测试覆盖率 > 80%
- ✅ 回测 100 只股票 1 年数据 < 30 秒
- ✅ 文档完整

**总计时间**: 12 小时（约 2 天）

---

## 总体时间估算

| Phase | 任务 | 时间 |
|-------|------|------|
| Phase 1 | 服务层恢复 | 2 天 |
| Phase 2 | 工具层实现 | 1 天 |
| Phase 3 | Python ML 层 | 1 天 |
| Phase 4 | 定时任务 | 1.5 天 |
| Phase 5 | 测试与优化 | 2 天 |
| **总计** | | **7.5 天** |

---

## 风险与缓解

### 风险 1: 历史代码与当前架构不兼容

**概率**: 中  
**影响**: 高  
**缓解**: 
- 先恢复一个服务类，验证兼容性
- 如有大量冲突，考虑重写而非恢复

### 风险 2: ML 模型训练数据不足

**概率**: 高  
**影响**: 中  
**缓解**:
- 实现规则引擎降级，ML 不是必需的
- 可以先运行一段时间积累信号数据

### 风险 3: 回测性能问题

**概率**: 中  
**影响**: 中  
**缓解**:
- 限制回测周期（最多 2 年）
- 分批加载数据，避免内存溢出
- 添加进度提示

### 风险 4: 定时任务执行失败

**概率**: 低  
**影响**: 中  
**缓解**:
- 单个任务失败不影响其他任务
- 添加告警机制
- CronService 自动禁用连续失败 5 次的任务

---

## 验收标准

### 功能验收

- ✅ Agent 可以创建量化策略
- ✅ Agent 可以运行回测，获得绩效报告
- ✅ Agent 可以生成今日买卖信号
- ✅ Agent 可以对股票进行多因子评分
- ✅ 定时任务自动执行（每日信号扫描、每周模型重训练）
- ✅ ML 模型可以预测信号置信度（或降级到规则引擎）

### 质量验收

- ✅ 单元测试覆盖率 > 80%
- ✅ 所有 TypeScript 编译无错误
- ✅ 所有测试通过
- ✅ 无明显性能问题（回测 100 只股票 1 年 < 30 秒）

### 文档验收

- ✅ 设计文档完整
- ✅ 实施计划清晰
- ✅ 使用示例完善
- ✅ SOUL.md 更新（如需要）

---

## 后续优化方向

1. **策略优化器**: 自动调整策略参数，寻找最优组合
2. **多因子模型**: 扩展因子库，支持更多技术指标和基本面因子
3. **实盘跟踪**: 记录实际交易结果，与回测对比
4. **策略市场**: 分享和导入其他用户的策略
5. **可视化**: 回测结果可视化（权益曲线、交易分布）

---

## 总结

本设计文档详细描述了量化系统的完整实现方案，包括：

1. **架构设计**: 清晰的分层架构（定时任务层、工具层、服务层、数据层、ML 层）
2. **服务层**: 4 个核心服务类（QuantService、SignalGenerator、BacktestEngine、FactorLibrary）
3. **Python ML 层**: XGBoost 信号置信度预测，带多级降级策略
4. **Agent 工具层**: 6 个工具满足 SOUL.md Phase 4B 要求
5. **定时任务**: 4 个自动化任务（信号扫描、模型重训练、绩效报告、健康检查）
6. **错误处理**: 完善的降级策略、超时保护、快速失败机制
7. **实施计划**: 5 个 Phase，总计 7.5 天

该方案基于历史实现（commit `edff27c` 和 `3137c6e`），适配当前架构，平衡了功能完整性和实施复杂度。

