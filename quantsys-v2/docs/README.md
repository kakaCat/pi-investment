# Quantsys-v2 文档中心

欢迎使用Quantsys-v2量化交易框架！本文档中心提供完整的使用指南、示例代码和API参考。

## 📚 文档导航

### 快速开始
- **[快速入门指南](guides/QUICK_START.md)** - 5分钟快速体验核心功能
- **[最佳实践指南](guides/BEST_PRACTICES.md)** - 因子开发和策略优化技巧

### 使用示例
所有示例代码位于 `examples/` 目录，可直接运行：

#### 因子工程框架
- **[example_ic_analysis.py](examples/example_ic_analysis.py)** - IC/IR分析完整示例
  - IC时间序列计算
  - IC统计指标
  - 因子质量评分
  - 多因子对比

- **[example_orthogonalization.py](examples/example_orthogonalization.py)** - 因子正交化示例
  - Schmidt正交化
  - PCA正交化
  - 对称正交化
  - 方法对比

#### 期权策略框架
- **[example_greeks_calculator.py](examples/example_greeks_calculator.py)** - 期权Greeks计算
  - Black-Scholes定价
  - Delta/Gamma/Theta/Vega/Rho
  - 隐含波动率
  - 期权策略Greeks

#### GPU加速框架
- **[example_gpu_factors.py](examples/example_gpu_factors.py)** - GPU加速因子计算
  - GPU环境检测
  - CPU vs GPU性能对比
  - 批量因子计算
  - 大规模数据处理

#### 跨品种策略框架
- **[example_index_hedge.py](examples/example_index_hedge.py)** - 股指期货对冲
  - Beta计算
  - 静态对冲策略
  - 动态对冲策略
  - 最小方差对冲
  - 对冲效果评估

#### 高频策略框架
- **[example_market_making.py](examples/example_market_making.py)** - 做市策略
  - 订单簿管理
  - 做市报价计算
  - 库存控制
  - 统计套利

### API参考
详细的类和方法文档（即将添加）

## 🚀 快速运行示例

### 运行单个示例
```bash
# IC分析示例
python docs/examples/example_ic_analysis.py

# 期权Greeks计算
python docs/examples/example_greeks_calculator.py

# GPU加速（需要GPU）
python docs/examples/example_gpu_factors.py

# 股指对冲
python docs/examples/example_index_hedge.py

# 做市策略
python docs/examples/example_market_making.py
```

### 运行所有示例
```bash
# 使用提供的测试脚本
python docs/examples/run_all_examples.py
```

## 📖 学习路径

### 初学者路径
1. 阅读 [快速入门指南](guides/QUICK_START.md)
2. 运行 `example_ic_analysis.py` 了解因子评估
3. 运行 `example_greeks_calculator.py` 了解期权定价
4. 阅读 [最佳实践指南](guides/BEST_PRACTICES.md)

### 进阶路径
1. 学习因子正交化 (`example_orthogonalization.py`)
2. 探索GPU加速 (`example_gpu_factors.py`)
3. 研究对冲策略 (`example_index_hedge.py`)
4. 实现高频策略 (`example_market_making.py`)

### 实战路径
1. 使用真实数据替换示例中的模拟数据
2. 根据最佳实践开发自己的因子
3. 构建多因子选股模型
4. 实现完整的回测系统
5. 进行样本外验证

## 🔧 核心功能

### 1. 因子工程框架
```python
from quant.factor_analysis.ic_analyzer import ICAnalyzer
from quant.factor_analysis.orthogonalizer import FactorOrthogonalizer

# IC分析
analyzer = ICAnalyzer()
ic_series = analyzer.calculate_ic_series(factor_data, return_data)
ic_stats = analyzer.calculate_ic_statistics()

# 因子正交化
orthogonalizer = FactorOrthogonalizer()
orthogonal_factors = orthogonalizer.schmidt_orthogonalization(
    factor_data, base_factors=['market_cap']
)
```

### 2. 期权策略框架
```python
from quant.options.greeks_calculator import GreeksCalculator

calculator = GreeksCalculator()
greeks = calculator.calculate_greeks(
    S=100, K=100, T=0.25, r=0.03, sigma=0.2, option_type='call'
)
```

### 3. GPU加速框架
```python
from quant.gpu_acceleration.gpu_factors import GPUFactorCalculator

calculator = GPUFactorCalculator(use_gpu=True)
result = calculator.batch_calculate_factors(
    df, factors=['sma_20', 'rsi_14', 'macd']
)
```

### 4. 跨品种策略框架
```python
from quant.cross_asset_strategies.index_futures_hedge import IndexFuturesHedgeStrategy

strategy = IndexFuturesHedgeStrategy(
    portfolio_value=10_000_000,
    futures_multiplier=300,
    hedge_ratio=1.0
)
strategy.update_beta(portfolio_returns, index_returns)
signal = strategy.generate_rebalance_signal(portfolio_value, futures_price)
```

### 5. 高频策略框架
```python
from quant.hft_strategies.market_making import MarketMakingStrategy

strategy = MarketMakingStrategy(
    symbol='BTC/USDT',
    min_spread=0.0002,
    max_inventory=1000
)
orders = strategy.generate_orders()
```

## 📊 性能指标

### 因子评估标准
- **IC_mean > 0.05**: 优秀
- **IC_mean > 0.03**: 良好
- **IC_IR > 1.5**: 优秀稳定性
- **IC_positive_rate > 0.6**: 高胜率

### GPU加速效果
- 小数据集 (<1000): CPU更快
- 中等数据集 (1000-10000): 2-5x加速
- 大数据集 (>10000): 10-100x加速

## 🛠️ 依赖要求

### 基础依赖
```bash
numpy>=1.20.0
pandas>=1.3.0
scipy>=1.7.0
scikit-learn>=0.24.0
```

### 可选依赖
```bash
# GPU加速
cupy-cuda11x  # CUDA 11.x
cupy-cuda12x  # CUDA 12.x

# 可视化
matplotlib>=3.3.0
seaborn>=0.11.0

# 性能优化
numba>=0.53.0
```

## 📝 代码质量

所有示例代码遵循以下标准：
- ✅ 完整的文档字符串
- ✅ 清晰的变量命名
- ✅ 详细的注释说明
- ✅ 可直接运行
- ✅ 包含结果解读

## 🤝 贡献指南

欢迎贡献新的示例和文档！

### 添加新示例
1. 在 `examples/` 目录创建新文件
2. 遵循现有示例的结构
3. 包含完整的文档和注释
4. 确保代码可以独立运行
5. 更新本README

### 改进文档
1. 修正错误或不清晰的描述
2. 添加更多使用场景
3. 补充最佳实践
4. 提供反馈和建议

## 📞 获取帮助

- 查看 [常见问题](guides/QUICK_START.md#常见问题)
- 阅读 [最佳实践指南](guides/BEST_PRACTICES.md)
- 运行示例代码学习
- 查看源代码注释

## 📄 许可证

本项目采用 MIT 许可证。

---

**最后更新**: 2026-05-22

**版本**: 2.0.0

**维护者**: Quantsys-v2 Team
