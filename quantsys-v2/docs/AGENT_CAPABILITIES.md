# QuantSys V2 - AI Agent 能力指南

**面向**: AI Agent / 智能助手  
**版本**: v2.3.0  
**更新日期**: 2026-05-25

---

## 📖 文档目的

本文档专为 AI Agent 设计，帮助你理解：
1. **QuantSys V2 现在能做什么** - 已实现的完整功能
2. **你可以用什么工具** - 可调用的 API、服务和函数
3. **系统的潜力** - 可扩展的方向和未来可能性
4. **如何完成量化任务** - 实际工作流程和最佳实践

---

## 🎯 核心定位

QuantSys V2 是一个**企业级量化投资系统**，为 AI Agent 提供：

### 你现在可以做的事情

✅ **数据获取与分析**
- 获取 A 股、港股的实时行情和历史数据
- 查询财务报表、估值指标、资金流向
- 访问市场概览、板块数据、指数行情

✅ **技术分析**
- 计算 66+ 技术指标（MA、RSI、MACD、布林带等）
- 执行趋势分析、波动率分析、动量分析
- 生成买卖信号和交易建议

✅ **量化研究**
- 运行回测验证策略有效性
- 计算风险指标（夏普比率、最大回撤、VaR）
- 进行统计分析和假设检验

✅ **机器学习**
- 自动特征工程（技术指标、价格特征、时间特征）
- 训练预测模型（XGBoost、LightGBM、随机森林）
- 模型评估和特征重要性分析

✅ **交易执行**
- 创建和管理订单
- 跟踪持仓和盈亏
- 执行风险检查和止损策略

✅ **实时监控**
- WebSocket 实时行情推送
- 事件驱动的信号通知
- 风险告警和异常检测

### 系统的潜力

🚀 **可扩展方向**
- 深度学习模型（LSTM、Transformer）
- 高频交易策略
- 多资产组合优化
- 情绪分析和新闻挖掘
- 自动化报告生成

---

## 🛠️ Agent 工具箱

### 1. HTTP API 工具 (端口 5001)

这是你的主要工作接口，所有功能都通过 RESTful API 暴露。

#### 1.1 数据获取工具

**股票搜索与查询**
```http
GET /api/stocks/search?q=浦发银行
GET /api/stocks/<symbol>
GET /api/stocks/list?market=A&limit=100
```

**用途**: 
- 根据关键词搜索股票
- 获取股票基本信息（名称、代码、行业、市值）
- 批量获取股票列表

**实际场景**:
```
用户: "帮我分析浦发银行"
Agent: 
1. 调用 /api/stocks/search?q=浦发银行 找到代码 600000.SH
2. 调用 /api/stocks/600000.SH 获取基本信息
3. 继续后续分析...
```

**K线数据获取**
```http
GET /api/stock/<symbol>/klines?period=daily&limit=100
GET /api/stock/<symbol>/history?start_date=2024-01-01&end_date=2024-12-31
```

**用途**:
- 获取日线、周线、月线、分钟线数据
- 支持指定时间范围
- 返回 OHLCV（开高低收量）数据

**实际场景**:
```
用户: "浦发银行最近一个月的走势如何？"
Agent:
1. 调用 /api/stock/600000.SH/klines?period=daily&limit=30
2. 分析价格趋势、涨跌幅、成交量变化
3. 生成走势描述
```

**实时行情**
```http
GET /api/stock/<symbol>/quote
POST /api/stocks/batch-quotes (批量获取)
```

**用途**:
- 获取实时价格、涨跌幅、成交量
- 支持批量查询多只股票
- 包含盘口数据（买卖五档）

**财务数据**
```http
GET /api/stock/<symbol>/financials
GET /api/stock/<symbol>/valuation
```

**用途**:
- 获取利润表、资产负债表、现金流量表
- 获取估值指标（PE、PB、ROE、毛利率等）
- 支持多期财务数据对比

**市场数据**
```http
GET /api/market/overview
GET /api/market/sectors
GET /api/market/concepts
```

**用途**:
- 获取市场整体情况（涨跌家数、成交额）
- 获取板块表现和热点概念
- 发现市场机会

#### 1.2 技术分析工具

**因子计算**
```http
GET /api/stock/<symbol>/factors
POST /api/indicators/calculate
```

**可用因子** (66+):
- **移动平均**: ma5, ma10, ma20, ma60, ema5, ema10
- **动量指标**: rsi6, rsi14, macd, macd_signal, roc
- **波动率**: bollinger_upper/middle/lower, atr14, volatility20
- **成交量**: obv, mfi14, vwap, volume_ratio, turnover_rate
- **趋势**: adx14, cci20, aroon_up25, sar
- **其他**: wr14, bias, psy, ar26, br26, dma, trix

**用途**:
- 一次性计算多个技术指标
- 获取指标的元数据（超买超卖信号、金叉死叉等）
- 支持自定义参数

**实际场景**:
```
用户: "浦发银行的技术指标怎么样？"
Agent:
1. 调用 /api/stock/600000.SH/factors
2. 分析 RSI（是否超买超卖）
3. 分析 MACD（是否金叉死叉）
4. 分析布林带（是否突破上下轨）
5. 综合判断技术面强弱
```

**价格行为分析**
```http
GET /api/stock/<symbol>/price-action
GET /api/stock/<symbol>/technical
```

**用途**:
- 识别价格形态（头肩顶、双底、三角形等）
- 判断支撑位和阻力位
- 分析趋势强度

**买入区间计算**
```http
GET /api/stock/<symbol>/buy-range
```

**用途**:
- 基于技术指标计算合理买入价格区间
- 包含 Kelly 准则的仓位建议
- 提供风险收益比分析

#### 1.3 信号生成工具

**机会扫描**
```http
POST /api/signals/scan
```

**请求示例**:
```json
{
  "stocks": ["600000.SH", "000858.SZ"],  // 可选：指定股票
  "minScore": 60,                         // 最低综合评分
  "maxRiskLevel": "medium",               // 最大风险等级
  "technical": ["rsi_oversold", "macd_golden_cross"],
  "fundamental": ["low_pe", "high_roe"]
}
```

**响应示例**:
```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "600000.SH",
      "name": "浦发银行",
      "score": 85,                    // 综合评分 (0-100)
      "technical_score": 90,          // 技术面评分
      "fundamental_score": 80,        // 基本面评分
      "capital_score": 75,            // 资金面评分
      "confidence": 0.85,             // 置信度
      "risk_level": "low",            // 风险等级
      "signal_type": "buy",           // 信号类型
      "reasons": [                    // 推荐理由
        "RSI 超卖反弹",
        "MACD 金叉",
        "主力资金流入"
      ]
    }
  ],
  "total": 1,
  "scanned": 400
}
```

**用途**:
- 从 400+ 热门股票中快速筛选机会
- 多维度评分（技术、基本面、资金）
- 0.2 秒扫描完成

**实际场景**:
```
用户: "现在有什么好的买入机会？"
Agent:
1. 调用 /api/signals/scan (minScore=70, maxRiskLevel=medium)
2. 获取高分股票列表
3. 逐个分析推荐理由
4. 按评分排序展示给用户
```

**信号历史**
```http
GET /api/signals/history
GET /api/signals/<signal_id>
```

**用途**:
- 查看历史信号表现
- 跟踪信号执行情况
- 评估信号准确率

#### 1.4 回测工具

**运行回测**
```http
POST /api/backtest/run
```

**请求示例**:
```json
{
  "symbol": "600000.SH",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 100000,
  "strategy": {
    "type": "ma_crossover",
    "params": {
      "fast_period": 5,
      "slow_period": 20
    }
  }
}
```

**响应示例**:
```json
{
  "success": true,
  "backtest_id": "bt_20260525_001",
  "results": {
    "total_return": 0.35,           // 总收益率 35%
    "annual_return": 0.175,         // 年化收益率 17.5%
    "max_drawdown": -0.12,          // 最大回撤 -12%
    "sharpe_ratio": 1.8,            // 夏普比率
    "win_rate": 0.65,               // 胜率 65%
    "total_trades": 45,             // 总交易次数
    "profit_factor": 2.3,           // 盈亏比
    "trades": [...]                 // 详细交易记录
  }
}
```

**用途**:
- 验证策略有效性
- 评估风险收益特征
- 优化策略参数

**实际场景**:
```
用户: "帮我测试一下 5 日均线和 20 日均线交叉策略"
Agent:
1. 调用 /api/backtest/run (ma_crossover 策略)
2. 分析回测结果（收益率、回撤、胜率）
3. 评估策略是否可行
4. 给出优化建议
```

#### 1.5 机器学习工具

**模型训练**
```http
POST /api/training/start
```

**请求示例**:
```json
{
  "symbols": ["600000.SH", "000858.SZ"],
  "features": ["ma5", "rsi14", "macd", "volume_ratio"],
  "target": "next_day_return",
  "model_type": "xgboost",
  "train_start": "2020-01-01",
  "train_end": "2023-12-31",
  "test_start": "2024-01-01",
  "test_end": "2024-12-31"
}
```

**响应示例**:
```json
{
  "success": true,
  "training_id": "train_20260525_001",
  "status": "completed",
  "metrics": {
    "train_auc": 0.82,
    "test_auc": 0.78,
    "train_accuracy": 0.75,
    "test_accuracy": 0.72,
    "feature_importance": {
      "rsi14": 0.25,
      "macd": 0.20,
      "ma5": 0.18,
      "volume_ratio": 0.15
    }
  },
  "model_path": "models/xgb_20260525_001.pkl"
}
```

**用途**:
- 自动特征工程
- 训练预测模型
- 评估模型性能
- 获取特征重要性

**实际场景**:
```
用户: "能用机器学习预测股票涨跌吗？"
Agent:
1. 调用 /api/training/start 训练模型
2. 等待训练完成
3. 分析模型性能（AUC、准确率）
4. 解释特征重要性
5. 给出预测结果
```

#### 1.6 风险管理工具

**风险检查**
```http
POST /api/risk/check
POST /api/stock/<symbol>/risk/trade-check
```

**请求示例**:
```json
{
  "symbol": "600000.SH",
  "action": "BUY",
  "quantity": 100,
  "price": 1800.0
}
```

**响应示例**:
```json
{
  "passed": true,
  "checks": {
    "position_limit": {"passed": true, "message": "持仓比例 5% < 限制 10%"},
    "single_order_limit": {"passed": true, "message": "订单金额 18万 < 限制 50万"},
    "daily_trade_limit": {"passed": true, "message": "今日交易 3次 < 限制 10次"},
    "max_drawdown": {"passed": true, "message": "当前回撤 -3% < 限制 -15%"}
  },
  "warnings": [
    "该股票波动率较高，建议降低仓位"
  ]
}
```

**用途**:
- 交易前风险检查
- 防止过度交易
- 控制持仓集中度
- 监控回撤风险

**仓位计算**
```http
POST /api/stock/<symbol>/risk/position-size
```

**请求示例**:
```json
{
  "capital": 100000,
  "risk_per_trade": 0.02,      // 单笔风险 2%
  "stop_loss_pct": 0.05        // 止损 5%
}
```

**响应示例**:
```json
{
  "position_size": 400,          // 建议买入 400 股
  "position_value": 72000,       // 持仓市值 7.2 万
  "position_pct": 0.72,          // 占总资金 72%
  "risk_amount": 2000,           // 风险金额 2000 元
  "stop_loss_price": 171.0       // 止损价 171 元
}
```

**用途**:
- 科学计算仓位大小
- 基于风险承受能力
- 包含 Kelly 准则优化

#### 1.7 订单与持仓工具

**订单管理**
```http
POST /api/orders/create
GET /api/orders/list
PUT /api/orders/<order_id>/cancel
```

**持仓查询**
```http
GET /api/portfolio/positions
GET /api/portfolio/summary
GET /api/portfolio/history
```

**用途**:
- 创建买卖订单
- 跟踪订单状态
- 查看持仓和盈亏
- 分析持仓分布

#### 1.8 市场情绪工具

**资金流向**
```http
GET /api/stock/<symbol>/fund-flow
GET /api/market/north-flow
GET /api/market/sector-flow
```

**用途**:
- 查看主力资金流向
- 北向资金动向
- 板块资金轮动

**龙虎榜**
```http
GET /api/stock/<symbol>/lhb
```

**用途**:
- 查看机构和游资动向
- 识别主力操作

**融资融券**
```http
GET /api/stock/<symbol>/margin
GET /api/market/margin
```

**用途**:
- 查看融资融券余额
- 判断市场情绪

### 2. WebSocket 实时工具 (端口 5003)

用于实时数据推送和事件通知。

**连接方式**:
```javascript
const socket = io('http://127.0.0.1:5003');

// 连接成功
socket.on('connected', (data) => {
    console.log('Session ID:', data.session_id);
});

// 订阅股票
socket.emit('subscribe', {symbol: '600000.SH'});

// 接收实时行情
socket.on('quote_update', (data) => {
    // data: {symbol, price, volume, change, change_pct}
});

// 接收信号通知
socket.on('signal_generated', (data) => {
    // data: {symbol, signal, strategy, confidence, reason}
});

// 接收风险告警
socket.on('risk_alert', (data) => {
    // data: {symbol, risk_type, level, message}
});
```

**支持的事件**:
- `quote_update` - 行情更新（3-5秒/次）
- `signal_generated` - 信号生成
- `risk_alert` - 风险告警
- `trade_executed` - 交易执行
- `backtest_completed` - 回测完成
- `data_updated` - 数据更新

**用途**:
- 实时监控股票价格变化
- 及时接收交易信号
- 实时风险监控
- 异步任务完成通知

### 3. Python 服务层工具

如果你是 Python Agent，可以直接调用服务层。

**数据服务**
```python
from services.data_service import DataService

ds = DataService()

# 获取股票及K线
stock_data = ds.get_stock_with_klines('600000.SH', days=100)

# 获取市场概览
overview = ds.get_market_overview()

# 批量更新K线
ds.batch_update_klines(['600000.SH', '000858.SZ'])
```

**因子计算**
```python
from quant.adapters import get_factor_adapter

adapter = get_factor_adapter()

# 计算单个因子
ma5 = adapter.calculate('ma5', klines)

# 批量计算
factors = adapter.calculate_batch(['ma5', 'rsi14', 'macd'], klines)

# 获取元数据
result = adapter.calculate_with_metadata('rsi14', klines)
# 返回: {value, method, parameters, metadata, timestamp}
```

**机会扫描**
```python
from services.opportunity_scoring_service_v2 import OpportunityScoringServiceV2

scorer = OpportunityScoringServiceV2()

# 扫描机会
opportunities = scorer.scan_opportunities(
    symbols=['600000.SH', '000858.SZ'],
    min_score=60,
    max_risk_level='medium'
)

# 单只股票评分
score = scorer.score_stock('600000.SH')
```

**风险管理**
```python
from services.risk_service import RiskService

risk_service = RiskService()

# 风险检查
check = risk_service.pre_trade_check(
    symbol='600000.SH',
    action='BUY',
    quantity=100,
    price=1800.0
)

# 计算风险指标
metrics = risk_service.calculate_risk_metrics(
    returns=portfolio_returns,
    benchmark_returns=benchmark_returns
)
```

**回测引擎**
```python
from quantlib.backtest import BacktestEngine

engine = BacktestEngine()

# 运行回测
result = engine.run(
    symbol='600000.SH',
    strategy=ma_crossover_strategy,
    start_date='2023-01-01',
    end_date='2024-12-31',
    initial_capital=100000
)

# 分析结果
print(f"总收益: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
```

### 4. 量化分析库 (QuantLib)

**衍生品定价**
```python
from quant.derivatives.pricing import DerivativesPricer

pricer = DerivativesPricer()

# Black-Scholes 期权定价
option_price = pricer.black_scholes_price(
    S=100, K=105, T=0.25, r=0.05, sigma=0.2, option_type='call'
)

# Greeks 计算
greeks = pricer.calculate_greeks(S=100, K=105, T=0.25, r=0.05, sigma=0.2)
# 返回: {delta, gamma, theta, vega, rho}

# 隐含波动率
iv = pricer.calculate_implied_volatility(
    S=100, K=105, T=0.25, r=0.05, market_price=3.5
)
```

**时间序列分析**
```python
from quant.timeseries import TimeSeriesAnalyzer

analyzer = TimeSeriesAnalyzer()

# 趋势分析
trend = analyzer.analyze_trend(prices, trend_type='linear')
# 返回: {slope, intercept, r_squared, trend_strength}

# 平稳性检验
stationarity = analyzer.test_stationarity(returns, test_type='both')
# 返回: {adf_statistic, adf_p_value, kpss_statistic, is_stationary}

# 自相关分析
acf = analyzer.calculate_autocorrelation(returns, max_lag=20)
# 返回: {acf_values, pacf_values, significant_lags}
```

**统计分析**
```python
from quant.statistics import StatisticalAnalyzer

analyzer = StatisticalAnalyzer()

# Bootstrap 重采样
bootstrap = analyzer.bootstrap_resample(
    returns,
    statistic='sharpe',
    n_iterations=10000,
    confidence_level=0.95
)
# 返回: {statistic, confidence_interval, std_error}

# t 检验
t_test = analyzer.t_test(strategy_a_returns, strategy_b_returns)
# 返回: {t_statistic, p_value, is_significant, effect_size}

# 正态性检验
normality = analyzer.shapiro_test(returns)
# 返回: {statistic, p_value, is_normal}
```

---

## 💡 实际工作流程

### 场景 1: 股票分析

**用户请求**: "帮我分析一下浦发银行，现在能买吗？"

**Agent 工作流程**:

```python
# 步骤 1: 搜索股票
response = requests.get('http://127.0.0.1:5001/api/stocks/search?q=浦发银行')
symbol = response.json()['stocks'][0]['symbol']  # 600000.SH

# 步骤 2: 获取基本信息
stock_info = requests.get(f'http://127.0.0.1:5001/api/stocks/{symbol}').json()
# 分析: 行业、市值、PE、PB

# 步骤 3: 获取实时行情
quote = requests.get(f'http://127.0.0.1:5001/api/stock/{symbol}/quote').json()
# 分析: 当前价格、涨跌幅、成交量

# 步骤 4: 获取技术指标
factors = requests.get(f'http://127.0.0.1:5001/api/stock/{symbol}/factors').json()
# 分析: RSI（是否超买超卖）、MACD（金叉死叉）、布林带（突破情况）

# 步骤 5: 获取资金流向
fund_flow = requests.get(f'http://127.0.0.1:5001/api/stock/{symbol}/fund-flow').json()
# 分析: 主力资金流入流出

# 步骤 6: 计算买入区间
buy_range = requests.get(f'http://127.0.0.1:5001/api/stock/{symbol}/buy-range').json()
# 获取: 建议买入价格区间、仓位建议

# 步骤 7: 综合分析
# 基本面: PE 估值水平、ROE 盈利能力
# 技术面: 趋势方向、超买超卖、支撑阻力
# 资金面: 主力动向、北向资金
# 风险: 波动率、回撤风险

# 步骤 8: 生成建议
recommendation = {
    "action": "BUY" | "HOLD" | "SELL",
    "confidence": 0.75,
    "entry_price": 1750.0,
    "stop_loss": 1650.0,
    "target_price": 1900.0,
    "position_size": "建议仓位 5-10%",
    "reasons": [
        "技术面: RSI 超卖反弹，MACD 金叉",
        "基本面: PE 处于历史低位",
        "资金面: 主力资金连续流入"
    ],
    "risks": [
        "短期波动较大",
        "行业政策风险"
    ]
}
```

### 场景 2: 机会挖掘

**用户请求**: "现在市场上有什么好的投资机会？"

**Agent 工作流程**:

```python
# 步骤 1: 扫描市场机会
response = requests.post('http://127.0.0.1:5001/api/signals/scan', json={
    "minScore": 70,
    "maxRiskLevel": "medium",
    "technical": ["rsi_oversold", "macd_golden_cross"],
    "fundamental": ["low_pe", "high_roe"]
})

opportunities = response.json()['opportunities']
# 获取: 高分股票列表（按评分排序）

# 步骤 2: 逐个分析
for opp in opportunities[:5]:  # 取前 5 个
    symbol = opp['symbol']
    
    # 获取详细信息
    stock_info = requests.get(f'http://127.0.0.1:5001/api/stocks/{symbol}').json()
    klines = requests.get(f'http://127.0.0.1:5001/api/stock/{symbol}/klines?limit=30').json()
    
    # 分析推荐理由
    reasons = opp['reasons']
    
    # 计算买入区间
    buy_range = requests.get(f'http://127.0.0.1:5001/api/stock/{symbol}/buy-range').json()

# 步骤 3: 生成报告
report = {
    "total_opportunities": len(opportunities),
    "top_picks": [
        {
            "symbol": "600000.SH",
            "name": "浦发银行",
            "score": 85,
            "reasons": ["RSI 超卖", "MACD 金叉", "主力流入"],
            "entry_price": 1750.0,
            "target_price": 1900.0
        },
        # ... 更多
    ],
    "market_sentiment": "偏多",
    "hot_sectors": ["白酒", "新能源", "半导体"]
}
```

### 场景 3: 策略回测

**用户请求**: "帮我测试一下双均线策略的效果"

**Agent 工作流程**:

```python
# 步骤 1: 定义策略参数
strategy_params = {
    "type": "ma_crossover",
    "params": {
        "fast_period": 5,
        "slow_period": 20
    }
}

# 步骤 2: 选择测试股票
test_symbols = ["600000.SH", "000858.SZ", "600036.SH"]

# 步骤 3: 批量回测
results = []
for symbol in test_symbols:
    response = requests.post('http://127.0.0.1:5001/api/backtest/run', json={
        "symbol": symbol,
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000,
        "strategy": strategy_params
    })
    results.append(response.json())

# 步骤 4: 分析结果
summary = {
    "average_return": np.mean([r['results']['total_return'] for r in results]),
    "average_sharpe": np.mean([r['results']['sharpe_ratio'] for r in results]),
    "average_win_rate": np.mean([r['results']['win_rate'] for r in results]),
    "best_performer": max(results, key=lambda x: x['results']['total_return']),
    "worst_performer": min(results, key=lambda x: x['results']['total_return'])
}

# 步骤 5: 参数优化建议
# 如果夏普比率 < 1.0，建议调整参数
# 如果胜率 < 50%，建议改变策略逻辑
# 如果最大回撤 > 20%，建议增加止损
```

### 场景 4: 实时监控

**用户请求**: "帮我监控浦发银行，有重要信号时通知我"

**Agent 工作流程**:

```python
import socketio

# 步骤 1: 建立 WebSocket 连接
sio = socketio.Client()

@sio.on('connected')
def on_connect(data):
    print(f"Connected: {data['session_id']}")
    # 订阅股票
    sio.emit('subscribe', {'symbol': '600000.SH'})

@sio.on('quote_update')
def on_quote(data):
    # 实时行情更新
    price = data['price']
    change_pct = data['change_pct']
    
    # 检查是否触发条件
    if abs(change_pct) > 0.03:  # 涨跌超过 3%
        notify_user(f"浦发银行价格异动: {change_pct:.2%}")

@sio.on('signal_generated')
def on_signal(data):
    # 收到交易信号
    if data['symbol'] == '600000.SH':
        notify_user(f"浦发银行信号: {data['signal']} (置信度: {data['confidence']:.0%})")

@sio.on('risk_alert')
def on_risk(data):
    # 收到风险告警
    if data['symbol'] == '600000.SH':
        notify_user(f"浦发银行风险告警: {data['message']}")

# 步骤 2: 连接服务器
sio.connect('http://127.0.0.1:5003')

# 步骤 3: 保持连接
sio.wait()
```

### 场景 5: 机器学习预测

**用户请求**: "能用机器学习预测明天的涨跌吗？"

**Agent 工作流程**:

```python
# 步骤 1: 准备训练数据
symbols = ["600000.SH", "000858.SZ", "600036.SH"]  # 多只股票
features = ["ma5", "ma10", "rsi14", "macd", "volume_ratio", "atr14"]

# 步骤 2: 启动训练
response = requests.post('http://127.0.0.1:5001/api/training/start', json={
    "symbols": symbols,
    "features": features,
    "target": "next_day_return",
    "model_type": "xgboost",
    "train_start": "2020-01-01",
    "train_end": "2023-12-31",
    "test_start": "2024-01-01",
    "test_end": "2024-12-31"
})

training_id = response.json()['training_id']

# 步骤 3: 等待训练完成（或通过 WebSocket 接收通知）
import time
while True:
    status = requests.get(f'http://127.0.0.1:5001/api/training/{training_id}').json()
    if status['status'] == 'completed':
        break
    time.sleep(5)

# 步骤 4: 分析模型性能
metrics = status['metrics']
print(f"测试集 AUC: {metrics['test_auc']:.3f}")
print(f"测试集准确率: {metrics['test_accuracy']:.2%}")

# 步骤 5: 特征重要性分析
importance = metrics['feature_importance']
top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
print("最重要的特征:")
for feature, score in top_features[:5]:
    print(f"  {feature}: {score:.3f}")

# 步骤 6: 使用模型预测
# 获取最新数据
latest_klines = requests.get('http://127.0.0.1:5001/api/stock/600000.SH/klines?limit=100').json()
latest_factors = requests.get('http://127.0.0.1:5001/api/stock/600000.SH/factors').json()

# 调用预测接口（假设已实现）
prediction = requests.post('http://127.0.0.1:5001/api/ml/predict', json={
    "model_id": training_id,
    "features": latest_factors
}).json()

print(f"预测明天: {prediction['label']} (概率: {prediction['probability']:.2%})")
```

---

## 🚀 系统潜力与扩展方向

### 1. 已实现的强大能力

✅ **完整的量化工作流**
- 数据获取 → 因子计算 → 信号生成 → 回测验证 → 风险管理 → 交易执行
- 全流程自动化，无需人工干预

✅ **高性能计算**
- 66+ 技术因子，单只股票 < 50ms
- 400 只股票机会扫描 < 0.2s
- 批量查询优化，减少数据库访问

✅ **实时能力**
- WebSocket 实时推送
- 事件驱动架构
- 异步处理支持

✅ **企业级架构**
- 双层防腐层设计
- Pipeline 模式
- 微服务就绪
- 完整的测试覆盖（96%通过率）

### 2. 可扩展的方向

🚀 **深度学习模型**
- LSTM 时间序列预测
- Transformer 注意力机制
- GAN 生成对抗网络
- 强化学习交易策略

**实现路径**:
```python
# 已有基础: 特征工程、数据管道、模型训练框架
# 需要添加: 深度学习模型类

from services.ml_pipeline.trainer import ModelTrainer

trainer = ModelTrainer(model_type='lstm')  # 新增 LSTM 支持
result = trainer.train(X_train, y_train, X_val, y_val)
```

🚀 **高频交易**
- 分钟级、秒级策略
- 订单簿分析
- 微观结构研究

**实现路径**:
```python
# 已有基础: 实时数据推送、快速因子计算
# 需要添加: 高频数据接口、低延迟执行

# 订阅 tick 数据
sio.emit('subscribe_tick', {'symbol': '600000.SH'})

@sio.on('tick_update')
def on_tick(data):
    # 毫秒级处理
    pass
```

🚀 **多资产组合优化**
- 马科维茨均值方差模型
- Black-Litterman 模型
- 风险平价策略

**实现路径**:
```python
# 已有基础: 风险指标计算、相关性分析
# 需要添加: 优化求解器

from quantlib.portfolio import PortfolioOptimizer

optimizer = PortfolioOptimizer()
weights = optimizer.optimize(
    returns=expected_returns,
    cov_matrix=covariance_matrix,
    method='mean_variance'
)
```

🚀 **情绪分析**
- 新闻文本挖掘
- 社交媒体情绪
- 财报情绪分析

**实现路径**:
```python
# 已有基础: 新闻数据接口
# 需要添加: NLP 模型

from services.sentiment_analyzer import SentimentAnalyzer

analyzer = SentimentAnalyzer()
sentiment = analyzer.analyze_news(symbol='600000.SH', days=7)
# 返回: {sentiment_score, positive_ratio, key_topics}
```

🚀 **自动化报告**
- 每日市场分析报告
- 持仓诊断报告
- 策略表现报告

**实现路径**:
```python
# 已有基础: 所有数据和分析能力
# 需要添加: 报告生成器

from services.report_generator import ReportGenerator

generator = ReportGenerator()
report = generator.generate_daily_report(date='2026-05-25')
# 生成 PDF/HTML 报告
```

### 3. Agent 可以做的创新

💡 **智能投顾**
- 根据用户风险偏好推荐股票
- 动态调整投资组合
- 个性化投资建议

💡 **策略挖掘**
- 自动发现有效因子
- 遗传算法优化策略参数
- 策略组合优化

💡 **风险预警**
- 实时监控持仓风险
- 预测市场拐点
- 黑天鹅事件预警

💡 **交易助手**
- 自动执行交易计划
- 智能止盈止损
- 订单拆分优化

💡 **研究助手**
- 自动生成研究报告
- 行业对比分析
- 事件驱动研究

---

## 📊 性能指标

### API 性能
- 平均响应时间: < 100ms
- P95 响应时间: < 200ms
- P99 响应时间: < 500ms
- 并发支持: 1000+ QPS

### 计算性能
- 单只股票因子计算: < 50ms
- 批量因子计算（100只）: < 2s
- 机会扫描（400只）: < 0.2s
- 回测（1年数据）: < 5s

### 数据性能
- 数据库查询: < 10ms（有索引）
- 缓存命中: < 2ms
- WebSocket 延迟: < 50ms

---

## 🎓 最佳实践

### 1. 数据获取
- 优先使用批量接口减少请求次数
- 利用缓存避免重复查询
- 使用 WebSocket 获取实时数据

### 2. 因子计算
- 批量计算多个因子（一次调用）
- 使用 `calculate_with_metadata` 获取信号
- 缓存计算结果

### 3. 回测验证
- 使用足够长的历史数据（至少 2 年）
- 包含不同市场环境（牛市、熊市、震荡）
- 考虑交易成本和滑点

### 4. 风险管理
- 交易前必须调用风险检查
- 设置合理的止损止盈
- 控制单只股票仓位

### 5. 实时监控
- 使用 WebSocket 而非轮询
- 设置合理的告警阈值
- 及时响应风险事件

---

## 📚 相关文档

- [CAPABILITIES.md](CAPABILITIES.md) - 完整功能列表
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构
- [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) - API 集成指南
- [WEBSOCKET_GUIDE.md](WEBSOCKET_GUIDE.md) - WebSocket 使用指南
- [QUICKSTART.md](QUICKSTART.md) - 快速入门

---

## 🎯 总结

QuantSys V2 为 AI Agent 提供了完整的量化投资工具箱：

✅ **数据完整** - A股、港股全覆盖，实时+历史数据  
✅ **分析全面** - 66+因子、机器学习、统计分析  
✅ **执行可靠** - 订单管理、风险控制、实时监控  
✅ **性能优异** - 毫秒级响应、批量优化、异步处理  
✅ **易于扩展** - 模块化设计、插件系统、API 友好  

**你现在就可以**:
- 分析任何 A 股、港股
- 生成交易信号和建议
- 运行回测验证策略
- 训练机器学习模型
- 执行交易和风险管理
- 实时监控市场变化

**未来可以做到**:
- 深度学习预测
- 高频交易策略
- 多资产组合优化
- 情绪分析和新闻挖掘
- 自动化投资决策

开始使用 QuantSys V2，让量化投资更智能！

