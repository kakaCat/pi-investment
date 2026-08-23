# Backtest Domain - 策略回测引擎

**领域职责**: 策略回测、数据管道、性能分析

---

## 概述

Backtest 领域提供完整的策略回测基础设施，包括 52 个内置策略、多阶段数据管道、指标计算、ML 集成等功能。

**核心能力**:
- ✅ 52 个内置策略（趋势、突破、反转、网格、配对等）
- ✅ 多阶段回测数据管道（获取、清洗、因子计算、存储）
- ✅ 技术指标管理器（支持 TA-Lib、pandas-ta、自定义指标）
- ✅ 因子/指标/ML 混入（Mixin）支持
- ✅ BackTrader 框架集成
- ✅ 回测报告生成（收益率、夏普比率、最大回撤等）

---

## 目录结构

```
backtest/
├── __init__.py                    # 领域入口
├── engine/                  (52)  # 回测引擎
│   ├── __init__.py                # 导出所有策略和组件
│   ├── strategy_base.py           # 策略基类
│   ├── enhanced_strategy_base.py  # 增强策略基类（支持 Mixin）
│   ├── commission.py              # 佣金模型
│   ├── slippage.py                # 滑点模型
│   ├── position_sizing.py         # 仓位管理
│   ├── risk_rules.py              # 风险规则
│   ├── backtest_report.py         # 回测报告生成器
│   ├── strategy_factory.py        # 策略工厂
│   ├── strategy_runner.py         # 策略运行器
│   ├── strategy_combiner.py       # 策略组合器
│   ├── smart_backtest_engine.py   # 智能回测引擎
│   ├── code_validator.py          # 代码验证器
│   ├── param_parser.py            # 参数解析器
│   ├── factor_cache.py            # 因子缓存
│   ├── stress_test.py             # 压力测试
│   │
│   ├── indicators/                # 技术指标
│   │   ├── base.py                # 指标基类
│   │   ├── indicator_manager.py   # 指标管理器
│   │   ├── talib_adapter.py       # TA-Lib 适配器
│   │   ├── pandasta_adapter.py    # pandas-ta 适配器
│   │   └── custom_adapter.py      # 自定义指标适配器
│   │
│   ├── mixins/                    # 混入
│   │   ├── factor_mixin.py        # 因子混入
│   │   ├── indicator_mixin.py     # 指标混入
│   │   └── ml_mixin.py            # ML 混入
│   │
│   ├── backtrader/                # BackTrader 集成
│   │   ├── backtrader_engine.py   # BackTrader 引擎
│   │   ├── data_feed.py           # 数据源适配
│   │   └── strategy_adapter.py    # 策略适配器
│   │
│   └── [52 个策略实现]
│       ├── adx_trend_strategy.py          # ADX 趋势策略
│       ├── bollinger_breakout.py          # 布林带突破
│       ├── breakout_strategy.py           # 突破策略
│       ├── cci_reversal_strategy.py       # CCI 反转策略
│       ├── donchian_channel_strategy.py   # 唐奇安通道
│       ├── grid_trading_strategy.py       # 网格交易
│       ├── ma_cross.py                    # 均线交叉
│       ├── mean_reversion_strategy.py     # 均值回归
│       ├── momentum_strategy.py           # 动量策略
│       ├── multi_factor_strategy.py       # 多因子策略
│       ├── pairs_correlation_strategy.py  # 配对交易
│       ├── rsi_reversal.py                # RSI 反转
│       ├── turtle_strategy.py             # 海龟策略
│       ├── volatility_breakout_strategy.py # 波动率突破
│       ├── ml_prediction_strategy.py      # ML 预测策略
│       ├── config_driven_strategy.py      # 配置驱动策略
│       └── ... (其他 38 个策略)
│
├── stages/                  (14)  # 回测阶段
│   ├── __init__.py
│   ├── backtest_stage.py          # 回测阶段基类
│   ├── factor_stage.py            # 因子计算阶段
│   ├── model_stage.py             # 模型训练阶段
│   ├── risk_stage.py              # 风险评估阶段
│   │
│   └── data_pipeline/             # 数据管道
│       ├── data_fetch_stage.py           # 数据获取
│       ├── deduplication_stage.py        # 去重
│       ├── time_alignment_stage.py       # 时间对齐
│       ├── imputation_stage.py           # 缺失值填充
│       ├── anomaly_detection_stage.py    # 异常检测
│       ├── conflict_resolution_stage.py  # 冲突解决
│       ├── factor_compute_stage.py       # 因子计算
│       └── storage_stage.py              # 数据存储
│
├── pipeline/                 (3)  # 管道监控
│   ├── monitor.py                 # 监控器
│   └── error_handler.py           # 错误处理
│
└── core/                     (2)  # 核心工具
    ├── market_impact.py           # 市场影响模型
    └── walk_forward.py            # Walk-Forward 优化
```

---

## 快速开始

### 1. 使用内置策略

```python
from domain.backtest.engine import BreakoutStrategy, StrategyRunner

# 创建策略实例
strategy = BreakoutStrategy(
    lookback=20,       # 突破周期
    entry_threshold=1.02,  # 入场阈值
    stop_loss=0.05     # 止损比例
)

# 运行回测
runner = StrategyRunner()
result = runner.run(
    strategy=strategy,
    symbol='000001.SZ',
    start_date='2023-01-01',
    end_date='2023-12-31',
    initial_cash=1000000
)

# 查看结果
print(f"总收益率: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
```

### 2. 创建自定义策略

```python
from domain.backtest.engine import EnhancedStrategyBase

class MyStrategy(EnhancedStrategyBase):
    """自定义策略"""
    
    def __init__(self, param1=10, param2=0.02):
        super().__init__()
        self.param1 = param1
        self.param2 = param2
    
    def generate_signals(self, data):
        """生成交易信号"""
        signals = []
        
        # 你的策略逻辑
        for i in range(len(data)):
            if self._should_buy(data, i):
                signals.append({
                    'date': data.index[i],
                    'action': 'buy',
                    'price': data['close'].iloc[i]
                })
            elif self._should_sell(data, i):
                signals.append({
                    'date': data.index[i],
                    'action': 'sell',
                    'price': data['close'].iloc[i]
                })
        
        return signals
    
    def _should_buy(self, data, i):
        """买入条件"""
        # 实现你的买入逻辑
        pass
    
    def _should_sell(self, data, i):
        """卖出条件"""
        # 实现你的卖出逻辑
        pass
```

### 3. 使用 Mixin 扩展策略

```python
from domain.backtest.engine import EnhancedStrategyBase
from domain.backtest.engine.mixins import FactorMixin, IndicatorMixin

class MultiFactorStrategy(EnhancedStrategyBase, FactorMixin, IndicatorMixin):
    """多因子策略（支持因子和指标）"""
    
    def generate_signals(self, data):
        # 使用因子
        momentum = self.get_factor('momentum', data)
        value = self.get_factor('value', data)
        
        # 使用指标
        rsi = self.get_indicator('rsi', data, period=14)
        macd = self.get_indicator('macd', data)
        
        # 组合信号
        signals = self._combine_signals(momentum, value, rsi, macd)
        return signals
```

### 4. 使用数据管道

```python
from domain.backtest.stages.data_pipeline import (
    DataFetchStage,
    DeduplicationStage,
    FactorComputeStage,
    StorageStage
)

# 构建数据管道
pipeline = [
    DataFetchStage(sources=['akshare', 'tushare']),
    DeduplicationStage(),
    FactorComputeStage(factors=['momentum', 'value', 'quality']),
    StorageStage(target='postgresql')
]

# 执行管道
for stage in pipeline:
    data = stage.execute(data)
```

---

## 核心概念

### 策略生命周期

```
初始化 → 数据加载 → 信号生成 → 仓位管理 → 风险控制 → 绩效分析
  ↓          ↓          ↓          ↓          ↓          ↓
__init__  load_data  generate   position   risk_    generate
                    _signals    _sizing    rules    _report
```

### 回测流程

```
1. 数据准备
   ├── 获取历史数据
   ├── 数据清洗
   ├── 特征工程
   └── 因子计算

2. 策略执行
   ├── 遍历每个时间点
   ├── 生成交易信号
   ├── 执行买卖操作
   └── 更新持仓

3. 绩效分析
   ├── 计算收益率
   ├── 计算风险指标
   ├── 生成回测报告
   └── 可视化结果
```

### 佣金和滑点

```python
from domain.backtest.engine import AShareCommission, Slippage

# 使用 A 股佣金模型
commission = AShareCommission(
    rate=0.0003,        # 万三佣金
    min_commission=5.0  # 最低 5 元
)

# 滑点模型
slippage = Slippage(
    fixed_slippage=0.001,  # 固定滑点 0.1%
    volume_impact=0.1      # 成交量影响
)
```

---

## 内置策略列表

### 趋势策略
- **ADXTrendStrategy** - ADX 趋势强度
- **MACrossStrategy** - 均线交叉
- **MomentumStrategy** - 动量策略
- **TurtleStrategy** - 海龟策略

### 突破策略
- **BreakoutStrategy** - 价格突破
- **BollingerBreakout** - 布林带突破
- **DonchianChannelStrategy** - 唐奇安通道
- **VolatilityBreakoutStrategy** - 波动率突破

### 反转策略
- **RSIReversalStrategy** - RSI 超买超卖
- **CCIReversalStrategy** - CCI 反转
- **MeanReversionStrategy** - 均值回归

### 多因子策略
- **MultiFactorStrategy** - 多因子组合
- **PEMomentumMA60Strategy** - PE + 动量 + 均线

### 特殊策略
- **GridTradingStrategy** - 网格交易
- **PairsCorrelationStrategy** - 配对交易
- **MLPredictionStrategy** - 机器学习预测
- **ConfigDrivenStrategy** - 配置驱动策略

---

## 架构设计

### 分层架构

```
应用层 (application/)
    ↓ 调用
领域层 (domain/backtest/)
    ↓ 使用
基础设施层 (infrastructure/)
```

### 依赖关系

```python
# ✅ 正确：domain 层不依赖 infrastructure
from domain.backtest.engine import BreakoutStrategy

# ⚠️  遗留问题：2 处依赖 application 层
# - backtest_report.py → application.services.risk_metrics_service
# - ml_mixin.py → application.services.ml_pipeline.predictor
# 待修复：通过依赖注入解耦
```

---

## 性能优化

### 因子缓存

```python
from domain.backtest.engine import factor_cache

# 使用缓存避免重复计算
@factor_cache(ttl=3600)
def compute_expensive_factor(data):
    # 昂贵的因子计算
    return result
```

### 并行回测

```python
from domain.backtest.engine import StrategyRunner

runner = StrategyRunner(parallel=True, n_jobs=4)
results = runner.run_multiple(strategies, symbols)
```

---

## 测试

```bash
# 运行回测领域测试
pytest tests/domain/backtest/ -v

# 运行特定策略测试
pytest tests/domain/backtest/test_breakout_strategy.py -v
```

---

## 相关文档

- [策略参数指南](engine/STRATEGY_PARAMS_GUIDE.py)
- [实现总结](engine/IMPLEMENTATION_SUMMARY.py)
- [QuantLib 技术计算库](../quantlib/README.md)
- [因子领域](../factors/README.md)
- [风险领域](../risk/README.md)

---

## 贡献指南

### 添加新策略

1. 继承 `EnhancedStrategyBase`
2. 实现 `generate_signals()` 方法
3. 在 `engine/__init__.py` 中导出
4. 添加单元测试
5. 更新本文档

### 添加新指标

1. 在 `indicators/custom_adapter.py` 中实现
2. 注册到 `IndicatorManager`
3. 添加测试用例

---

**维护者**: QuantSys V2 Team  
**最后更新**: 2026-08-23  
**版本**: v2.0 (quantlib 重构后)
