# 因子库 (Factor Library)

量化投资因子计算框架，支持技术因子和基本面因子的高效计算。

## 功能特性

- **丰富的因子库**: 30+ 技术因子和基本面因子
- **高性能计算**: 支持并行计算，单因子计算 < 1秒
- **灵活的架构**: 基于面向对象设计，易于扩展
- **缓存机制**: 支持因子结果缓存，提升重复计算效率
- **完整测试**: 测试覆盖率 > 80%

## 已实现因子

### 技术因子 (Technical Factors)

#### 趋势类 (Trend)
- **MA** - 简单移动平均线 (5/10/20/60日)
- **EMA** - 指数移动平均线 (12/26日)
- **MACD** - 平滑异同移动平均线 (DIF, DEA, Histogram)
- **ADX** - 平均趋向指标
- **WMA** - 加权移动平均线

#### 动量类 (Momentum)
- **RSI** - 相对强弱指标
- **KDJ** - 随机指标 (K, D, J)
- **CCI** - 商品通道指标
- **ROC** - 变动率指标
- **Williams %R** - 威廉指标
- **MOM** - 动量指标
- **STOCH** - 随机振荡器

#### 波动类 (Volatility)
- **ATR** - 平均真实波幅
- **Bollinger Bands** - 布林带 (上轨/中轨/下轨/宽度/位置百分比)
- **Keltner Channel** - 肯特纳通道
- **Standard Deviation** - 标准差
- **Historical Volatility** - 历史波动率
- **Donchian Channel** - 唐奇安通道

#### 成交量类 (Volume)
- **OBV** - 能量潮指标
- **MFI** - 资金流量指标
- **VWAP** - 成交量加权平均价
- **Volume Ratio** - 量比
- **A/D Line** - 累积/派发线
- **CMF** - 蔡金资金流量
- **EMV** - 简易波动指标
- **Force Index** - 力度指标

### 基本面因子 (Fundamental Factors)

#### 估值类 (Valuation)
- **PE** - 市盈率
- **PB** - 市净率
- **PS** - 市销率
- **PCF** - 市现率
- **Dividend Yield** - 股息率
- **EV/EBITDA** - 企业价值倍数

#### 盈利能力 (Profitability)
- **ROE** - 净资产收益率
- **ROA** - 总资产收益率
- **Gross Margin** - 毛利率
- **Net Margin** - 净利率
- **ROIC** - 投入资本回报率
- **Operating Margin** - 营业利润率

#### 成长性 (Growth)
- **Revenue Growth** - 营收增长率 (同比/环比)
- **Profit Growth** - 净利润增长率 (同比/环比)
- **EPS Growth** - 每股收益增长率 (同比/环比)
- **PEG** - 市盈率相对盈利增长比率
- **Asset Growth** - 总资产增长率

#### 质量 (Quality)
- **Debt-to-Asset** - 资产负债率
- **Current Ratio** - 流动比率
- **Quick Ratio** - 速动比率
- **Cash Ratio** - 现金比率
- **Debt-to-Equity** - 产权比率
- **Interest Coverage** - 利息保障倍数
- **Asset Turnover** - 总资产周转率
- **Inventory Turnover** - 存货周转率

## 快速开始

### 1. 计算单个因子

```python
from factors.technical.trend import MA
import pandas as pd

# 准备OHLCV数据
data = pd.DataFrame({
    'date': [...],
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})

# 计算MA5
ma5 = MA(period=5)
result = ma5.calculate(data)
print(result)
```

### 2. 批量计算多个因子

```python
from factors.calculator import FactorCalculator
from factors.technical import MA, EMA, RSI, ATR

# 创建计算器
calculator = FactorCalculator(max_workers=4)

# 注册因子
factors = [
    MA(period=5),
    MA(period=20),
    EMA(period=12),
    RSI(period=14),
    ATR(period=14)
]
calculator.register_batch(factors)

# 批量计算
results = calculator.calculate_all(data)
print(results)
```

### 3. 使用缓存

```python
from factors.cache import FactorCache

cache = FactorCache(cache_dir=".pi-invest/factor-cache", ttl_hours=24)

# 尝试从缓存获取
cached_result = cache.get("MA5", "000001", "2024-01-01", "2024-12-31")

if cached_result is None:
    # 缓存未命中，计算因子
    result = ma5.calculate(data)
    # 保存到缓存
    cache.set("MA5", "000001", "2024-01-01", "2024-12-31", result)
else:
    result = cached_result
```

## 架构设计

```
factors/
├── base.py                     # 因子基类
├── calculator.py               # 因子计算引擎
├── cache.py                    # 因子缓存
├── technical/                  # 技术因子
│   ├── trend.py               # 趋势类
│   ├── momentum.py            # 动量类
│   ├── volatility.py          # 波动类
│   └── volume.py              # 成交量类
└── fundamental/               # 基本面因子
    ├── valuation.py           # 估值类
    ├── profitability.py       # 盈利能力
    ├── growth.py              # 成长性
    └── quality.py             # 质量类
```

## 性能指标

- **单因子计算时间**: < 1秒/股票 (252个交易日数据)
- **并行计算加速**: 支持多线程并行计算
- **测试覆盖率**: > 80%
- **因子数量**: 30+ 个

## 测试

运行所有测试:

```bash
PYTHONPATH=python python -m unittest discover python/tests/factors -v
```

运行特定测试:

```bash
PYTHONPATH=python python -m unittest python.tests.factors.test_trend -v
PYTHONPATH=python python -m unittest python.tests.factors.test_momentum -v
PYTHONPATH=python python -m unittest python.tests.factors.test_calculator -v
PYTHONPATH=python python -m unittest python.tests.factors.test_cache -v
```

## 示例

查看完整示例:

```bash
PYTHONPATH=python python python/factors/examples.py
```

示例包括:
1. 计算单个因子
2. 批量计算多个因子
3. 计算MACD和KDJ
4. 计算布林带
5. 使用缓存
6. 性能测试
7. 基本面因子计算

## 扩展因子库

### 添加新的技术因子

```python
from factors.base import TechnicalFactor
import pandas as pd

class MyFactor(TechnicalFactor):
    def __init__(self, period: int = 20):
        super().__init__(
            name=f"MyFactor{period}",
            description=f"{period}日自定义因子",
            period=period
        )
    
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        # 实现因子计算逻辑
        result = ...  # 你的计算逻辑
        return result
```

### 添加新的基本面因子

```python
from factors.base import FundamentalFactor
import pandas as pd

class MyFundamentalFactor(FundamentalFactor):
    def __init__(self):
        super().__init__(
            name="MyFundamentalFactor",
            description="自定义基本面因子"
        )
    
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        # 实现因子计算逻辑
        result = ...  # 你的计算逻辑
        return result
```

## 注意事项

1. **数据格式**: 技术因子需要OHLCV格式的DataFrame，列名必须为: `open`, `high`, `low`, `close`, `volume`
2. **基本面因子**: 需要财务数据，具体列名参考各因子的文档字符串
3. **NaN处理**: 因子计算会自动处理NaN值，但建议在使用前检查数据质量
4. **性能优化**: 对于大量股票的批量计算，建议使用并行计算和缓存机制

## 版本

当前版本: 0.1.0

## 作者

量化开发B - 因子库基础设施开发
