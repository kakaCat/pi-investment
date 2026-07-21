# Quantsys-v2 最佳实践指南

本指南总结了因子开发、策略开发和系统优化的最佳实践，帮助您构建稳健高效的量化交易系统。

## 目录

1. [因子开发最佳实践](#因子开发最佳实践)
2. [策略开发最佳实践](#策略开发最佳实践)
3. [性能优化建议](#性能优化建议)
4. [常见陷阱和解决方案](#常见陷阱和解决方案)
5. [代码质量标准](#代码质量标准)

---

## 因子开发最佳实践

### 1. 因子设计原则

#### 经济逻辑优先
```python
# ✓ 好的做法：有明确经济逻辑
def momentum_factor(prices, window=20):
    """
    动量因子：基于价格趋势延续的经济逻辑
    研究表明：过去表现好的股票短期内倾向于继续表现好
    """
    return prices.pct_change(window)

# ✗ 避免：纯数据挖掘，没有经济逻辑
def random_combination_factor(data):
    """随机组合多个指标，没有理论支撑"""
    return data['a'] * 0.37 + data['b'] ** 1.23 - data['c'] / 2.71
```

#### 因子稳定性
```python
# ✓ 好的做法：使用稳健的统计方法
def robust_zscore(data, window=60):
    """使用中位数和MAD，对异常值不敏感"""
    median = data.rolling(window).median()
    mad = (data - median).abs().rolling(window).median()
    return (data - median) / (mad * 1.4826)

# ✗ 避免：对异常值敏感
def simple_zscore(data, window=60):
    """均值和标准差容易受异常值影响"""
    return (data - data.rolling(window).mean()) / data.rolling(window).std()
```

### 2. 因子评估流程

#### 完整的评估体系
```python
from quant.factor_analysis.ic_analyzer import ICAnalyzer
from quant.factor_analysis.orthogonalizer import FactorOrthogonalizer

def evaluate_factor(factor_data, return_data):
    """完整的因子评估流程"""
    
    # 1. IC分析
    analyzer = ICAnalyzer()
    ic_series = analyzer.calculate_ic_series(factor_data, return_data, periods=[1, 5, 10, 20])
    ic_stats = analyzer.calculate_ic_statistics()
    
    # 评估标准
    if ic_stats.loc['IC_5D', 'IC_mean'] < 0.02:
        print("警告: IC均值过低")
    if ic_stats.loc['IC_5D', 'IC_IR'] < 0.5:
        print("警告: IC_IR过低，因子不稳定")
    if ic_stats.loc['IC_5D', 'IC_positive_rate'] < 0.52:
        print("警告: IC正比率过低")
    
    # 2. 因子相关性检查
    orthogonalizer = FactorOrthogonalizer()
    corr_matrix = orthogonalizer.calculate_correlation_matrix(factor_data)
    high_corr = orthogonalizer.find_highly_correlated_pairs(threshold=0.7)
    
    if len(high_corr) > 0:
        print(f"警告: 发现{len(high_corr)}对高度相关的因子")
    
    # 3. 分层回测
    # ... 实现分层回测逻辑
    
    # 4. 时间稳定性检查
    # 滚动窗口IC
    # ...
    
    return {
        'ic_stats': ic_stats,
        'correlation': corr_matrix,
        'high_corr_pairs': high_corr
    }
```

### 3. 因子正交化

#### 何时需要正交化
- 多因子模型中存在高度相关的因子
- 因子间相关性 > 0.7
- 需要提取独立的风险因子

#### 选择正交化方法
```python
# 场景1: 有明确的基础因子（如市值、行业）
orthogonalizer = FactorOrthogonalizer()
orthogonal_factors = orthogonalizer.schmidt_orthogonalization(
    factor_data,
    base_factors=['market_cap', 'industry']
)

# 场景2: 需要降维
orthogonal_pca, variance = orthogonalizer.pca_orthogonalization(
    factor_data,
    variance_threshold=0.95
)

# 场景3: 所有因子地位平等
orthogonal_symmetric = orthogonalizer.symmetric_orthogonalization(factor_data)
```

### 4. 因子组合

#### 因子加权方法
```python
def combine_factors(factors_dict, weights=None, method='equal'):
    """
    因子组合
    
    Args:
        factors_dict: {因子名: 因子值DataFrame}
        weights: 权重字典
        method: 'equal', 'ic_weighted', 'ir_weighted'
    """
    if method == 'equal':
        # 等权
        weights = {k: 1.0/len(factors_dict) for k in factors_dict}
    
    elif method == 'ic_weighted':
        # IC加权
        ic_values = {}
        for name, factor in factors_dict.items():
            analyzer = ICAnalyzer()
            ic_series = analyzer.calculate_ic_series(factor, return_data, periods=[5])
            ic_values[name] = ic_series['IC_5D'].mean()
        
        total_ic = sum(abs(v) for v in ic_values.values())
        weights = {k: abs(v)/total_ic for k, v in ic_values.items()}
    
    elif method == 'ir_weighted':
        # IC_IR加权（考虑稳定性）
        ir_values = {}
        for name, factor in factors_dict.items():
            analyzer = ICAnalyzer()
            ic_series = analyzer.calculate_ic_series(factor, return_data, periods=[5])
            ic_stats = analyzer.calculate_ic_statistics()
            ir_values[name] = ic_stats.loc['IC_5D', 'IC_IR']
        
        total_ir = sum(max(v, 0) for v in ir_values.values())
        weights = {k: max(v, 0)/total_ir for k, v in ir_values.items()}
    
    # 组合因子
    combined = None
    for name, factor in factors_dict.items():
        if combined is None:
            combined = factor * weights[name]
        else:
            combined += factor * weights[name]
    
    return combined, weights
```

---

## 策略开发最佳实践

### 1. 策略设计原则

#### 简单优于复杂
```python
# ✓ 好的做法：逻辑清晰，易于理解和维护
class SimpleMovingAverageCrossStrategy:
    def __init__(self, fast_period=10, slow_period=20):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def generate_signal(self, prices):
        fast_ma = prices.rolling(self.fast_period).mean()
        slow_ma = prices.rolling(self.slow_period).mean()
        
        signal = 0
        if fast_ma.iloc[-1] > slow_ma.iloc[-1]:
            signal = 1  # 买入
        elif fast_ma.iloc[-1] < slow_ma.iloc[-1]:
            signal = -1  # 卖出
        
        return signal

# ✗ 避免：过度复杂，难以理解和调试
class OverComplexStrategy:
    def generate_signal(self, data):
        # 组合10+个指标，多层嵌套逻辑
        # 难以理解每个部分的作用
        # 难以调试和优化
        pass
```

### 2. 风险管理

#### 仓位管理
```python
class PositionSizer:
    """仓位管理器"""
    
    def __init__(self, max_position=1.0, max_leverage=1.0):
        self.max_position = max_position
        self.max_leverage = max_leverage
    
    def calculate_position(self, signal, volatility, capital):
        """
        根据信号强度和波动率计算仓位
        
        Args:
            signal: 信号强度 [-1, 1]
            volatility: 波动率
            capital: 总资金
        """
        # 基础仓位
        base_position = signal * self.max_position
        
        # 波动率调整：波动率越高，仓位越小
        vol_adjustment = 0.15 / max(volatility, 0.05)  # 目标波动率15%
        adjusted_position = base_position * vol_adjustment
        
        # 限制在最大仓位内
        final_position = np.clip(adjusted_position, -self.max_position, self.max_position)
        
        return final_position
```

#### 止损止盈
```python
class RiskManager:
    """风险管理器"""
    
    def __init__(self, stop_loss=0.05, take_profit=0.15, trailing_stop=0.03):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop = trailing_stop
        self.highest_price = None
    
    def check_exit(self, entry_price, current_price, position):
        """检查是否需要退出"""
        if position == 0:
            return False, None
        
        pnl_pct = (current_price - entry_price) / entry_price * np.sign(position)
        
        # 止损
        if pnl_pct < -self.stop_loss:
            return True, 'stop_loss'
        
        # 止盈
        if pnl_pct > self.take_profit:
            return True, 'take_profit'
        
        # 移动止损
        if self.highest_price is None:
            self.highest_price = current_price
        else:
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            drawdown = (self.highest_price - current_price) / self.highest_price
            if drawdown > self.trailing_stop:
                return True, 'trailing_stop'
        
        return False, None
```

### 3. 回测框架

#### 完整的回测流程
```python
class Backtester:
    """回测引擎"""
    
    def __init__(self, strategy, initial_capital=1000000):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
    
    def run(self, data):
        """运行回测"""
        for date, row in data.iterrows():
            # 1. 更新持仓市值
            self.update_positions(row)
            
            # 2. 生成信号
            signal = self.strategy.generate_signal(data.loc[:date])
            
            # 3. 执行交易
            if signal != 0:
                self.execute_trade(date, row, signal)
            
            # 4. 记录权益
            equity = self.calculate_equity(row)
            self.equity_curve.append({
                'date': date,
                'equity': equity,
                'positions': self.positions.copy()
            })
        
        # 5. 计算绩效指标
        return self.calculate_performance()
    
    def calculate_performance(self):
        """计算绩效指标"""
        equity_series = pd.Series([e['equity'] for e in self.equity_curve])
        returns = equity_series.pct_change().dropna()
        
        total_return = (equity_series.iloc[-1] - self.initial_capital) / self.initial_capital
        annual_return = (1 + total_return) ** (252 / len(equity_series)) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        max_drawdown = drawdown.min()
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'total_trades': len(self.trades)
        }
```

### 4. 参数优化

#### 避免过拟合
```python
# ✓ 好的做法：样本外测试
def optimize_parameters(data, param_grid):
    """参数优化with样本外测试"""
    
    # 分割数据
    train_size = int(len(data) * 0.6)
    val_size = int(len(data) * 0.2)
    
    train_data = data[:train_size]
    val_data = data[train_size:train_size+val_size]
    test_data = data[train_size+val_size:]
    
    best_params = None
    best_val_sharpe = -np.inf
    
    # 在训练集上搜索参数
    for params in param_grid:
        strategy = Strategy(**params)
        backtester = Backtester(strategy)
        
        # 训练集表现
        train_perf = backtester.run(train_data)
        
        # 验证集表现
        val_perf = backtester.run(val_data)
        
        if val_perf['sharpe_ratio'] > best_val_sharpe:
            best_val_sharpe = val_perf['sharpe_ratio']
            best_params = params
    
    # 在测试集上评估
    final_strategy = Strategy(**best_params)
    final_backtester = Backtester(final_strategy)
    test_perf = final_backtester.run(test_data)
    
    print(f"验证集Sharpe: {best_val_sharpe:.2f}")
    print(f"测试集Sharpe: {test_perf['sharpe_ratio']:.2f}")
    
    return best_params, test_perf
```

---

## 性能优化建议

### 1. 数据处理优化

#### 使用向量化操作
```python
# ✓ 好的做法：向量化
def calculate_returns_vectorized(prices):
    """使用NumPy向量化操作"""
    return np.diff(prices) / prices[:-1]

# ✗ 避免：循环
def calculate_returns_loop(prices):
    """使用Python循环，慢100倍"""
    returns = []
    for i in range(1, len(prices)):
        ret = (prices[i] - prices[i-1]) / prices[i-1]
        returns.append(ret)
    return returns
```

#### 使用GPU加速
```python
from quant.gpu_acceleration.gpu_factors import GPUFactorCalculator

# 大数据集使用GPU
if len(data) > 10000:
    calculator = GPUFactorCalculator(use_gpu=True)
else:
    calculator = GPUFactorCalculator(use_gpu=False)

result = calculator.batch_calculate_factors(data, factors)
```

### 2. 内存优化

#### 数据类型优化
```python
# ✓ 好的做法：使用合适的数据类型
df['price'] = df['price'].astype('float32')  # 而不是float64
df['volume'] = df['volume'].astype('int32')  # 而不是int64
df['symbol'] = df['symbol'].astype('category')  # 分类数据

# 节省内存
print(f"优化前: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
# 优化后可能节省50%+内存
```

### 3. 并行计算

#### 多进程处理
```python
from multiprocessing import Pool

def calculate_factor_for_symbol(symbol):
    """计算单个股票的因子"""
    data = load_data(symbol)
    factors = calculate_factors(data)
    return symbol, factors

# 并行计算100只股票
symbols = [f'stock_{i}' for i in range(100)]

with Pool(processes=8) as pool:
    results = pool.map(calculate_factor_for_symbol, symbols)

# 合并结果
all_factors = dict(results)
```

---

## 常见陷阱和解决方案

### 1. 前视偏差 (Look-Ahead Bias)

```python
# ✗ 错误：使用了未来数据
def calculate_signal_wrong(data, date):
    """在date时刻使用了date之后的数据"""
    future_data = data[data.index > date]  # 错误！
    return future_data.mean()

# ✓ 正确：只使用历史数据
def calculate_signal_correct(data, date):
    """只使用date之前的数据"""
    historical_data = data[data.index <= date]
    return historical_data.mean()
```

### 2. 幸存者偏差 (Survivorship Bias)

```python
# ✗ 错误：只使用当前存在的股票
current_stocks = get_current_stock_list()  # 只包含未退市的股票
backtest_data = load_data(current_stocks)  # 偏差！

# ✓ 正确：使用历史时点的股票池
def get_stock_universe(date):
    """获取指定日期的股票池，包括后来退市的股票"""
    return get_stocks_existed_at_date(date)
```

### 3. 过拟合

```python
# ✗ 错误：过度优化参数
# 在同一数据集上测试100+个参数组合
# 选择表现最好的参数
# → 样本外表现差

# ✓ 正确：交叉验证
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(data):
    train_data = data.iloc[train_idx]
    test_data = data.iloc[test_idx]
    # 在train上训练，在test上验证
```

### 4. 数据泄露

```python
# ✗ 错误：标准化使用了全部数据
scaler = StandardScaler()
data_scaled = scaler.fit_transform(data)  # 使用了未来数据！

# ✓ 正确：滚动标准化
def rolling_standardize(data, window=60):
    """使用滚动窗口标准化"""
    mean = data.rolling(window).mean()
    std = data.rolling(window).std()
    return (data - mean) / std
```

---

## 代码质量标准

### 1. 文档和注释

```python
def calculate_ic(factor_values: np.ndarray, forward_returns: np.ndarray) -> float:
    """
    计算因子IC（Information Coefficient）
    
    IC是因子值与未来收益的Spearman相关系数，用于衡量因子的预测能力。
    
    Args:
        factor_values: 因子值数组，形状为(N,)，N为股票数量
        forward_returns: 未来收益数组，形状为(N,)
    
    Returns:
        IC值，范围[-1, 1]。正值表示因子与收益正相关。
        
    Example:
        >>> factor = np.array([0.1, 0.2, 0.3, 0.4])
        >>> returns = np.array([0.01, 0.02, 0.015, 0.025])
        >>> ic = calculate_ic(factor, returns)
        >>> print(f"IC: {ic:.4f}")
    
    Note:
        - 使用Spearman相关系数而非Pearson，对异常值更稳健
        - IC > 0.03 通常认为是有效因子
        - 需要至少10个样本才能计算有意义的IC
    """
    # 实现...
```

### 2. 单元测试

```python
import unittest

class TestICAnalyzer(unittest.TestCase):
    """IC分析器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.analyzer = ICAnalyzer()
        self.factor_data = pd.DataFrame(...)
        self.return_data = pd.DataFrame(...)
    
    def test_calculate_ic_basic(self):
        """测试基础IC计算"""
        ic = self.analyzer.calculate_ic(
            np.array([1, 2, 3, 4]),
            np.array([0.01, 0.02, 0.03, 0.04])
        )
        self.assertGreater(ic, 0.9)  # 完全正相关
    
    def test_calculate_ic_with_nan(self):
        """测试包含NaN的情况"""
        ic = self.analyzer.calculate_ic(
            np.array([1, 2, np.nan, 4]),
            np.array([0.01, 0.02, 0.03, 0.04])
        )
        self.assertFalse(np.isnan(ic))  # 应该正确处理NaN
    
    def test_calculate_ic_insufficient_samples(self):
        """测试样本不足的情况"""
        ic = self.analyzer.calculate_ic(
            np.array([1, 2]),
            np.array([0.01, 0.02])
        )
        self.assertTrue(np.isnan(ic))  # 样本太少应返回NaN
```

### 3. 日志记录

```python
import logging

logger = logging.getLogger(__name__)

def run_backtest(strategy, data):
    """运行回测"""
    logger.info(f"开始回测: {strategy.name}")
    logger.info(f"数据范围: {data.index[0]} 到 {data.index[-1]}")
    
    try:
        results = strategy.backtest(data)
        logger.info(f"回测完成: Sharpe={results['sharpe']:.2f}")
        return results
    except Exception as e:
        logger.error(f"回测失败: {e}", exc_info=True)
        raise
```

---

## 总结

### 核心原则

1. **简单性**: 简单的策略更容易理解、调试和维护
2. **稳健性**: 使用稳健的统计方法，对异常值不敏感
3. **可重复性**: 代码和结果应该可重复
4. **样本外测试**: 始终在样本外数据上验证
5. **风险管理**: 风险管理比收益预测更重要

### 开发流程

1. 提出假设（基于经济逻辑）
2. 数据准备和清洗
3. 因子计算和评估
4. 策略构建和回测
5. 样本外验证
6. 实盘前的压力测试
7. 小规模实盘验证
8. 逐步扩大规模

### 持续改进

- 定期评估策略表现
- 监控市场环境变化
- 及时调整参数和逻辑
- 学习新的方法和技术
- 记录经验教训

---

## 参考资源

- [快速入门指南](QUICK_START.md)
- [API参考文档](../api/)
- [示例代码](../examples/)
- 学术论文和研究报告
- 量化社区和论坛
