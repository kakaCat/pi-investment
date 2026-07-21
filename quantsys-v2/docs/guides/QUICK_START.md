# Quantsys-v2 快速入门指南

## 简介

Quantsys-v2 是一个功能强大的量化交易框架，提供了从因子工程到策略回测的完整工具链。本指南将帮助您在5分钟内快速上手核心功能。

## 安装依赖

```bash
cd quantsys-v2
pip install -r requirements.txt

# 如果需要GPU加速（可选）
pip install cupy-cuda11x  # 根据CUDA版本选择
```

## 核心功能概览

Quantsys-v2 提供以下5大核心框架：

1. **因子工程框架** - IC/IR分析、因子正交化、分层回测、另类数据因子
2. **期权策略框架** - Greeks计算、Delta中性、波动率套利
3. **GPU加速框架** - 因子计算加速、机器学习加速
4. **高频策略框架** - 做市策略、统计套利、事件驱动
5. **跨品种策略框架** - 股指期货对冲、商品期货CTA

## 5分钟快速体验

### 1. 因子IC分析（2分钟）

```python
from quantsys_v2.quant.factor_analysis.ic_analyzer import ICAnalyzer
import numpy as np
import pandas as pd

# 创建分析器
analyzer = ICAnalyzer()

# 准备模拟数据
dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
symbols = [f'stock_{i}' for i in range(100)]

# 因子数据（日期 × 股票）
factor_data = pd.DataFrame(
    np.random.randn(len(dates), len(symbols)),
    index=dates,
    columns=symbols
)

# 收益数据
return_data = pd.DataFrame(
    np.random.randn(len(dates), len(symbols)) * 0.02,
    index=dates,
    columns=symbols
)

# 计算IC时间序列
ic_series = analyzer.calculate_ic_series(
    factor_data,
    return_data,
    periods=[1, 5, 10, 20]  # 1日、5日、10日、20日预测期
)

# 计算IC统计指标
ic_stats = analyzer.calculate_ic_statistics()
print("IC统计指标:")
print(ic_stats)

# 因子质量评分
quality_scores = analyzer.get_factor_quality_score()
for period, scores in quality_scores.items():
    print(f"{period}: {scores['quality']} (评分: {scores['total_score']:.2f})")
```

**输出示例：**
```
IC统计指标:
              IC_mean    IC_std    IC_IR  IC_positive_rate  ICIR_annual
IC_1D         0.0234    0.1456    0.161              0.523         2.56
IC_5D         0.0412    0.1234    0.334              0.587         5.30
IC_10D        0.0389    0.1189    0.327              0.578         5.19
IC_20D        0.0356    0.1123    0.317              0.564         5.03

IC_1D: 一般 (评分: 6.40)
IC_5D: 良好 (评分: 7.80)
IC_10D: 良好 (评分: 7.60)
IC_20D: 良好 (评分: 7.20)
```

### 2. 期权Greeks计算（1分钟）

```python
from quantsys_v2.quant.options.greeks_calculator import GreeksCalculator

# 创建计算器
calculator = GreeksCalculator()

# 计算期权Greeks
greeks = calculator.calculate_greeks(
    S=100,      # 标的价格
    K=100,      # 行权价
    T=0.25,     # 到期时间（年）
    r=0.03,     # 无风险利率
    sigma=0.2,  # 波动率
    option_type='call'
)

print("期权Greeks:")
for key, value in greeks.items():
    print(f"  {key}: {value:.4f}")
```

**输出示例：**
```
期权Greeks:
  price: 3.9876
  delta: 0.5596
  gamma: 0.0398
  theta: -0.0109
  vega: 0.1990
  rho: 0.1349
```

### 3. GPU加速因子计算（1分钟）

```python
from quantsys_v2.quant.gpu_acceleration.gpu_factors import GPUFactorCalculator
import numpy as np
import pandas as pd

# 创建计算器（自动检测GPU）
calculator = GPUFactorCalculator(use_gpu=True)

# 准备OHLC数据
n = 1000
df = pd.DataFrame({
    'close': 100 + np.cumsum(np.random.randn(n) * 0.5),
    'high': 100 + np.cumsum(np.random.randn(n) * 0.5) + 1,
    'low': 100 + np.cumsum(np.random.randn(n) * 0.5) - 1,
    'volume': np.random.randint(1000, 10000, n)
})

# 批量计算因子
factors = ['sma_20', 'ema_12', 'rsi_14', 'macd', 'bollinger', 'atr_14']
result = calculator.batch_calculate_factors(df, factors)

print("计算完成！因子列:")
print(result.columns.tolist())
print("\n最新数据:")
print(result.tail())
```

### 4. 股指期货对冲（1分钟）

```python
from quantsys_v2.quant.cross_asset_strategies.index_futures_hedge import IndexFuturesHedgeStrategy
import numpy as np

# 创建对冲策略
strategy = IndexFuturesHedgeStrategy(
    portfolio_value=10_000_000,  # 1000万组合
    futures_multiplier=300,       # 期货合约乘数
    hedge_ratio=1.0,              # 完全对冲
    rebalance_threshold=0.1       # 10%再平衡阈值
)

# 模拟组合和指数收益
portfolio_returns = np.random.randn(100) * 0.015
index_returns = np.random.randn(100) * 0.012

# 更新Beta
strategy.update_beta(portfolio_returns, index_returns)
print(f"组合Beta: {strategy.current_beta:.4f}")

# 生成再平衡信号
signal = strategy.generate_rebalance_signal(
    portfolio_value=10_000_000,
    futures_price=4000
)

if signal:
    print("\n再平衡信号:")
    print(f"  当前持仓: {signal['current_position']} 手")
    print(f"  目标持仓: {signal['target_position']} 手")
    print(f"  调整数量: {signal['adjustment']} 手")
```

## 下一步

恭喜！您已经完成了快速入门。接下来可以：

1. 查看 [完整示例](../examples/) - 每个模块的详细使用示例
2. 阅读 [API参考文档](../api/) - 详细的类和方法说明
3. 学习 [最佳实践](BEST_PRACTICES.md) - 因子开发和策略优化技巧
4. 探索 [高级功能](#高级功能) - 更多强大特性

## 高级功能预览

### 因子正交化

消除因子间的相关性，提高因子独立性：

```python
from quantsys_v2.quant.factor_analysis.orthogonalizer import FactorOrthogonalizer

orthogonalizer = FactorOrthogonalizer()

# Schmidt正交化
orthogonal_factors = orthogonalizer.schmidt_orthogonalization(
    factor_data,
    base_factors=['market_cap', 'industry']
)

# PCA正交化
pc_factors, variance_ratio = orthogonalizer.pca_orthogonalization(
    factor_data,
    variance_threshold=0.95
)
```

### 做市策略

高频交易做市策略：

```python
from quantsys_v2.quant.hft_strategies.market_making import MarketMakingStrategy

strategy = MarketMakingStrategy(
    symbol='BTC/USDT',
    min_spread=0.0002,
    target_spread=0.0005,
    max_inventory=1000
)

# 更新订单簿
strategy.order_book.update(bids, asks)

# 生成做市订单
orders = strategy.generate_orders()
```

### 另类数据因子

新闻情绪、社交媒体热度等另类数据因子：

```python
from quantsys_v2.quant.alternative_factors.sentiment_factors import NewsSentimentFactor

news_factor = NewsSentimentFactor()

# 计算新闻情绪因子
factors = news_factor.calculate(
    symbol='000001',
    date=datetime.now(),
    lookback_days=7
)

print(f"新闻情绪: {factors['news_sentiment']:.4f}")
print(f"情绪变化: {factors['sentiment_change']:.4f}")
print(f"新闻强度: {factors['news_intensity']:.4f}")
```

## 常见问题

### Q1: GPU加速需要什么硬件？

A: 需要NVIDIA GPU和CUDA 11.x或更高版本。如果没有GPU，框架会自动回退到CPU计算。

### Q2: 如何获取真实市场数据？

A: 可以使用AkShare、Tushare等数据源。参考 `examples/data_preparation.py`。

### Q3: 因子IC多少算好？

A: 
- IC_mean > 0.05: 优秀
- IC_mean > 0.03: 良好
- IC_mean > 0.01: 一般
- IC_IR > 1.5: 优秀稳定性

### Q4: 如何选择对冲比率？

A: 
- hedge_ratio=1.0: 完全对冲Beta风险
- hedge_ratio=0.5: 部分对冲
- 使用 `MinimumVarianceHedgeStrategy` 自动优化

### Q5: 做市策略适合什么市场？

A: 适合流动性好、价差稳定的市场，如主流加密货币、股指期货等。

## 获取帮助

- 查看示例代码: `docs/examples/`
- API文档: `docs/api/`
- 提交Issue: GitHub Issues
- 技术交流: 项目讨论区

## 许可证

本项目采用 MIT 许可证。
