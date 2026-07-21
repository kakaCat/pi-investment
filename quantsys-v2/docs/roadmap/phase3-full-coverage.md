# Phase 3: 全面完善 (4-5个月)

**目标**: 从95分提升到100分 (+5分)  
**时间**: 4-5个月  
**重点**: 补齐所有短板，达到世界级水平

---

## 任务清单

### 1. 回测系统完善 (+5分)

#### 1.1 市场冲击成本模型 (3周)

**目标**: 实现Almgren-Chriss市场冲击模型

**技术方案**:
```python
# quant/backtest/market_impact.py

import numpy as np
from typing import Dict

class AlmgrenChrissModel:
    """
    Almgren-Chriss市场冲击模型
    
    论文: Optimal execution of portfolio transactions (2001)
    """
    
    def __init__(self, 
                 permanent_impact_coef: float = 0.1,
                 temporary_impact_coef: float = 0.01,
                 volatility: float = 0.02):
        """
        Args:
            permanent_impact_coef: 永久冲击系数 (γ)
            temporary_impact_coef: 临时冲击系数 (η)
            volatility: 价格波动率 (σ)
        """
        self.gamma = permanent_impact_coef
        self.eta = temporary_impact_coef
        self.sigma = volatility
    
    def calculate_impact(self, 
                        order_size: float,
                        adv: float,  # Average Daily Volume
                        price: float,
                        execution_time: float = 1.0) -> Dict[str, float]:
        """
        计算市场冲击成本
        
        Args:
            order_size: 订单大小（股数）
            adv: 日均成交量
            price: 当前价格
            execution_time: 执行时间（天）
        
        Returns:
            {
                'permanent_impact': 永久冲击成本,
                'temporary_impact': 临时冲击成本,
                'total_impact': 总冲击成本,
                'impact_bps': 冲击成本（基点）
            }
        """
        # 参与率 (participation rate)
        participation_rate = order_size / (adv * execution_time)
        
        # 永久冲击: γ * σ * (order_size / ADV)^0.5
        permanent_impact = (
            self.gamma * self.sigma * price * 
            np.sqrt(order_size / adv)
        )
        
        # 临时冲击: η * σ * (order_size / (ADV * T))
        temporary_impact = (
            self.eta * self.sigma * price * 
            (order_size / (adv * execution_time))
        )
        
        total_impact = permanent_impact + temporary_impact
        
        # 转换为基点 (bps)
        impact_bps = (total_impact / price) * 10000
        
        return {
            'permanent_impact': permanent_impact,
            'temporary_impact': temporary_impact,
            'total_impact': total_impact,
            'impact_bps': impact_bps,
            'participation_rate': participation_rate
        }
    
    def optimal_execution_schedule(self,
                                   total_shares: int,
                                   total_time: float,
                                   risk_aversion: float = 1e-6) -> np.ndarray:
        """
        计算最优执行策略
        
        Args:
            total_shares: 总股数
            total_time: 总时间（天）
            risk_aversion: 风险厌恶系数 (λ)
        
        Returns:
            每个时间段的交易量
        """
        n_periods = int(total_time * 390)  # 每天390分钟
        
        # Almgren-Chriss最优策略
        kappa = np.sqrt(risk_aversion * self.sigma**2 / self.eta)
        tau = total_time / n_periods
        
        # 计算每个时间段的交易量
        schedule = np.zeros(n_periods)
        remaining = total_shares
        
        for t in range(n_periods):
            time_left = (n_periods - t) * tau
            trade_rate = (
                remaining * 
                np.sinh(kappa * tau) / 
                np.sinh(kappa * time_left)
            )
            schedule[t] = trade_rate
            remaining -= trade_rate
        
        return schedule

# 集成到回测引擎
class BacktestStage(PipelineStage):
    def __init__(self, use_market_impact: bool = True):
        super().__init__()
        self.use_market_impact = use_market_impact
        if use_market_impact:
            self.impact_model = AlmgrenChrissModel()
    
    def _execute_trade(self, symbol: str, shares: int, price: float, 
                      adv: float) -> float:
        """执行交易并计算成本"""
        base_cost = shares * price
        
        if self.use_market_impact:
            impact = self.impact_model.calculate_impact(
                order_size=shares,
                adv=adv,
                price=price
            )
            total_cost = base_cost + impact['total_impact']
            
            logger.info(
                f"Market impact: {impact['impact_bps']:.2f} bps, "
                f"participation rate: {impact['participation_rate']:.2%}"
            )
        else:
            total_cost = base_cost
        
        return total_cost
```

**验收标准**:
- [ ] Almgren-Chriss模型实现
- [ ] 最优执行策略计算
- [ ] 集成到回测引擎
- [ ] 与实际交易数据对比验证

---

#### 1.2 多资产组合回测 (3周)

**目标**: 支持多股票组合回测

**技术方案**:
```python
# quant/backtest/portfolio_backtest.py

class PortfolioBacktestEngine:
    """多资产组合回测引擎"""
    
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.positions = {}  # {symbol: Position}
        self.cash = initial_capital
        self.equity_curve = []
    
    def run(self, 
            symbols: List[str],
            klines_dict: Dict[str, pd.DataFrame],
            signals_dict: Dict[str, List[Dict]],
            rebalance_frequency: str = 'daily') -> Dict:
        """
        运行组合回测
        
        Args:
            symbols: 股票列表
            klines_dict: K线数据字典 {symbol: klines}
            signals_dict: 信号字典 {symbol: signals}
            rebalance_frequency: 再平衡频率
        """
        # 获取所有日期
        all_dates = self._get_all_dates(klines_dict)
        
        for date in all_dates:
            # 更新持仓市值
            self._update_positions_value(date, klines_dict)
            
            # 检查是否需要再平衡
            if self._should_rebalance(date, rebalance_frequency):
                self._rebalance_portfolio(date, symbols, signals_dict, klines_dict)
            
            # 记录权益曲线
            total_equity = self.cash + sum(
                pos.shares * self._get_price(pos.symbol, date, klines_dict)
                for pos in self.positions.values()
            )
            self.equity_curve.append({
                'date': date,
                'equity': total_equity,
                'cash': self.cash,
                'positions_value': total_equity - self.cash
            })
        
        # 计算组合指标
        return self._calculate_portfolio_metrics()
    
    def _rebalance_portfolio(self, date, symbols, signals_dict, klines_dict):
        """组合再平衡"""
        # 获取当前信号
        current_signals = {}
        for symbol in symbols:
            signals = signals_dict.get(symbol, [])
            signal = self._get_signal_at_date(signals, date)
            if signal:
                current_signals[symbol] = signal
        
        # 计算目标权重
        target_weights = self._calculate_target_weights(current_signals)
        
        # 执行调仓
        total_equity = self.cash + sum(
            pos.shares * self._get_price(pos.symbol, date, klines_dict)
            for pos in self.positions.values()
        )
        
        for symbol, target_weight in target_weights.items():
            target_value = total_equity * target_weight
            current_value = self._get_position_value(symbol, date, klines_dict)
            
            if abs(target_value - current_value) > 100:  # 最小调仓金额
                self._adjust_position(symbol, target_value, date, klines_dict)
    
    def _calculate_target_weights(self, signals: Dict) -> Dict[str, float]:
        """
        计算目标权重
        
        策略:
        1. 等权重
        2. 风险平价
        3. 最大夏普比率
        4. 最小方差
        """
        # 简单实现: 等权重
        n_signals = len(signals)
        if n_signals == 0:
            return {}
        
        return {symbol: 1.0 / n_signals for symbol in signals.keys()}
    
    def _calculate_portfolio_metrics(self) -> Dict:
        """计算组合指标"""
        equity_series = pd.Series([e['equity'] for e in self.equity_curve])
        returns = equity_series.pct_change().dropna()
        
        return {
            'total_return': (equity_series.iloc[-1] / self.initial_capital - 1),
            'annual_return': self._annualized_return(returns),
            'sharpe_ratio': self._sharpe_ratio(returns),
            'max_drawdown': self._max_drawdown(equity_series),
            'calmar_ratio': self._calmar_ratio(returns, equity_series),
            'win_rate': (returns > 0).sum() / len(returns),
            'equity_curve': self.equity_curve
        }

# 使用示例
engine = PortfolioBacktestEngine(initial_capital=1_000_000)

results = engine.run(
    symbols=['600000', '000858', '600036'],
    klines_dict={
        '600000': klines_600000,
        '000858': klines_000858,
        '600036': klines_600036
    },
    signals_dict={
        '600000': signals_600000,
        '000858': signals_000858,
        '600036': signals_600036
    },
    rebalance_frequency='weekly'
)

print(f"组合年化收益: {results['annual_return']:.2%}")
print(f"夏普比率: {results['sharpe_ratio']:.2f}")
print(f"最大回撤: {results['max_drawdown']:.2%}")
```

**验收标准**:
- [ ] 多资产回测引擎
- [ ] 组合再平衡功能
- [ ] 多种权重分配策略
- [ ] 组合优化算法

---

#### 1.3 Walk-Forward分析 (2周)

**目标**: 滚动窗口回测，避免过拟合

**技术方案**:
```python
# quant/backtest/walk_forward.py

class WalkForwardAnalysis:
    """Walk-Forward分析"""
    
    def __init__(self, 
                 train_period: int = 252,  # 训练期（天）
                 test_period: int = 63,    # 测试期（天）
                 step_size: int = 21):     # 步长（天）
        self.train_period = train_period
        self.test_period = test_period
        self.step_size = step_size
    
    def run(self, 
            data: pd.DataFrame,
            strategy_class,
            param_grid: Dict) -> Dict:
        """
        运行Walk-Forward分析
        
        Args:
            data: 历史数据
            strategy_class: 策略类
            param_grid: 参数网格
        
        Returns:
            分析结果
        """
        results = []
        
        # 滚动窗口
        start_idx = 0
        while start_idx + self.train_period + self.test_period <= len(data):
            # 训练集
            train_data = data.iloc[start_idx:start_idx + self.train_period]
            
            # 测试集
            test_data = data.iloc[
                start_idx + self.train_period:
                start_idx + self.train_period + self.test_period
            ]
            
            # 在训练集上优化参数
            best_params = self._optimize_params(
                train_data, strategy_class, param_grid
            )
            
            # 在测试集上验证
            test_result = self._backtest_with_params(
                test_data, strategy_class, best_params
            )
            
            results.append({
                'train_start': train_data.index[0],
                'train_end': train_data.index[-1],
                'test_start': test_data.index[0],
                'test_end': test_data.index[-1],
                'best_params': best_params,
                'test_return': test_result['return'],
                'test_sharpe': test_result['sharpe']
            })
            
            # 移动窗口
            start_idx += self.step_size
        
        # 汇总结果
        return self._aggregate_results(results)
    
    def _optimize_params(self, train_data, strategy_class, param_grid):
        """在训练集上优化参数"""
        from sklearn.model_selection import ParameterGrid
        
        best_sharpe = -np.inf
        best_params = None
        
        for params in ParameterGrid(param_grid):
            result = self._backtest_with_params(
                train_data, strategy_class, params
            )
            
            if result['sharpe'] > best_sharpe:
                best_sharpe = result['sharpe']
                best_params = params
        
        return best_params
    
    def _aggregate_results(self, results: List[Dict]) -> Dict:
        """汇总结果"""
        test_returns = [r['test_return'] for r in results]
        test_sharpes = [r['test_sharpe'] for r in results]
        
        return {
            'n_periods': len(results),
            'avg_return': np.mean(test_returns),
            'std_return': np.std(test_returns),
            'avg_sharpe': np.mean(test_sharpes),
            'win_rate': sum(1 for r in test_returns if r > 0) / len(test_returns),
            'periods': results,
            'stability': self._calculate_stability(results)
        }
    
    def _calculate_stability(self, results: List[Dict]) -> float:
        """
        计算策略稳定性
        
        稳定性 = 正收益期数 / 总期数
        """
        positive_periods = sum(1 for r in results if r['test_return'] > 0)
        return positive_periods / len(results)

# 使用示例
wfa = WalkForwardAnalysis(
    train_period=252,  # 1年训练
    test_period=63,    # 3个月测试
    step_size=21       # 每月滚动
)

param_grid = {
    'ma_short': [5, 10, 20],
    'ma_long': [20, 60, 120],
    'rsi_period': [6, 14, 24]
}

results = wfa.run(
    data=historical_data,
    strategy_class=MACrossStrategy,
    param_grid=param_grid
)

print(f"平均收益: {results['avg_return']:.2%}")
print(f"平均夏普: {results['avg_sharpe']:.2f}")
print(f"策略稳定性: {results['stability']:.2%}")
```

**验收标准**:
- [ ] Walk-Forward框架实现
- [ ] 参数优化功能
- [ ] 稳定性分析
- [ ] 过拟合检测

---

#### 1.4 参数敏感性分析 (1周)

**技术方案**:
```python
# quant/backtest/sensitivity_analysis.py

class SensitivityAnalysis:
    """参数敏感性分析"""
    
    def analyze(self, 
                data: pd.DataFrame,
                strategy_class,
                param_name: str,
                param_range: List,
                fixed_params: Dict) -> pd.DataFrame:
        """
        分析单个参数的敏感性
        
        Args:
            data: 历史数据
            strategy_class: 策略类
            param_name: 参数名
            param_range: 参数范围
            fixed_params: 固定参数
        """
        results = []
        
        for param_value in param_range:
            params = fixed_params.copy()
            params[param_name] = param_value
            
            # 回测
            backtest_result = self._backtest(data, strategy_class, params)
            
            results.append({
                param_name: param_value,
                'return': backtest_result['return'],
                'sharpe': backtest_result['sharpe'],
                'max_drawdown': backtest_result['max_drawdown']
            })
        
        return pd.DataFrame(results)
    
    def heatmap_analysis(self,
                        data: pd.DataFrame,
                        strategy_class,
                        param1_name: str,
                        param1_range: List,
                        param2_name: str,
                        param2_range: List,
                        fixed_params: Dict) -> np.ndarray:
        """
        双参数热力图分析
        """
        results = np.zeros((len(param1_range), len(param2_range)))
        
        for i, param1_value in enumerate(param1_range):
            for j, param2_value in enumerate(param2_range):
                params = fixed_params.copy()
                params[param1_name] = param1_value
                params[param2_name] = param2_value
                
                backtest_result = self._backtest(data, strategy_class, params)
                results[i, j] = backtest_result['sharpe']
        
        return results
```

**验收标准**:
- [ ] 单参数敏感性分析
- [ ] 双参数热力图
- [ ] 参数稳定区间识别

---

### 2. 衍生品支持 (+4分)

#### 2.1 期货支持 (4周)

**技术方案**:
```python
# quant/futures/futures_pricing.py

class FuturesPricing:
    """期货定价"""
    
    def fair_value(self, 
                   spot_price: float,
                   risk_free_rate: float,
                   dividend_yield: float,
                   time_to_maturity: float) -> float:
        """
        期货理论价格
        
        F = S * e^((r-q)*T)
        """
        return spot_price * np.exp(
            (risk_free_rate - dividend_yield) * time_to_maturity
        )
    
    def basis(self, futures_price: float, spot_price: float) -> float:
        """基差 = 期货价格 - 现货价格"""
        return futures_price - spot_price
    
    def cost_of_carry(self, 
                     futures_price: float,
                     spot_price: float,
                     time_to_maturity: float) -> float:
        """持有成本"""
        return (futures_price / spot_price - 1) / time_to_maturity

# quant/futures/futures_strategies.py

class CalendarSpreadStrategy:
    """跨期套利策略"""
    
    def generate_signals(self,
                        near_contract: pd.DataFrame,
                        far_contract: pd.DataFrame) -> List[Dict]:
        """
        生成跨期套利信号
        
        当近月合约相对远月合约被低估时，买近卖远
        """
        signals = []
        
        # 计算价差
        spread = far_contract['close'] - near_contract['close']
        spread_ma = spread.rolling(20).mean()
        spread_std = spread.rolling(20).std()
        
        # Z-score
        z_score = (spread - spread_ma) / spread_std
        
        for i in range(len(z_score)):
            if z_score.iloc[i] > 2:  # 价差过大
                signals.append({
                    'date': near_contract.index[i],
                    'action': 'buy_near_sell_far',
                    'z_score': z_score.iloc[i]
                })
            elif z_score.iloc[i] < -2:  # 价差过小
                signals.append({
                    'date': near_contract.index[i],
                    'action': 'sell_near_buy_far',
                    'z_score': z_score.iloc[i]
                })
        
        return signals
```

**验收标准**:
- [ ] 期货定价模型
- [ ] 跨期套利策略
- [ ] 期现套利策略
- [ ] 期货回测引擎

---

#### 2.2 隐含波动率曲面 (3周)

**技术方案**:
```python
# quant/options/volatility_surface.py

from scipy.interpolate import griddata
from scipy.optimize import minimize

class VolatilitySurface:
    """隐含波动率曲面"""
    
    def __init__(self):
        self.surface_data = None
    
    def build_surface(self, 
                     options_data: pd.DataFrame) -> np.ndarray:
        """
        构建波动率曲面
        
        Args:
            options_data: 期权数据，包含 strike, maturity, market_price, iv
        """
        # 提取数据
        strikes = options_data['strike'].values
        maturities = options_data['maturity'].values
        ivs = options_data['iv'].values
        
        # 创建网格
        strike_grid = np.linspace(strikes.min(), strikes.max(), 50)
        maturity_grid = np.linspace(maturities.min(), maturities.max(), 50)
        
        strike_mesh, maturity_mesh = np.meshgrid(strike_grid, maturity_grid)
        
        # 插值
        iv_surface = griddata(
            (strikes, maturities),
            ivs,
            (strike_mesh, maturity_mesh),
            method='cubic'
        )
        
        self.surface_data = {
            'strikes': strike_grid,
            'maturities': maturity_grid,
            'iv_surface': iv_surface
        }
        
        return iv_surface
    
    def get_iv(self, strike: float, maturity: float) -> float:
        """获取指定行权价和到期日的隐含波动率"""
        if self.surface_data is None:
            raise ValueError("Surface not built yet")
        
        # 双线性插值
        from scipy.interpolate import interp2d
        
        f = interp2d(
            self.surface_data['strikes'],
            self.surface_data['maturities'],
            self.surface_data['iv_surface']
        )
        
        return float(f(strike, maturity))
    
    def calibrate_svi(self, options_data: pd.DataFrame) -> Dict:
        """
        校准SVI模型
        
        SVI: w(k) = a + b * (ρ * (k - m) + sqrt((k - m)^2 + σ^2))
        """
        def svi_formula(k, a, b, rho, m, sigma):
            return a + b * (rho * (k - m) + np.sqrt((k - m)**2 + sigma**2))
        
        def objective(params):
            a, b, rho, m, sigma = params
            predicted = svi_formula(
                options_data['log_moneyness'], a, b, rho, m, sigma
            )
            return np.sum((predicted - options_data['total_variance'])**2)
        
        # 优化
        result = minimize(
            objective,
            x0=[0.04, 0.4, -0.4, 0, 0.1],
            bounds=[
                (0, None),      # a >= 0
                (0, None),      # b >= 0
                (-1, 1),        # -1 <= rho <= 1
                (None, None),   # m
                (0, None)       # sigma >= 0
            ]
        )
        
        return {
            'a': result.x[0],
            'b': result.x[1],
            'rho': result.x[2],
            'm': result.x[3],
            'sigma': result.x[4],
            'success': result.success
        }
```

**验收标准**:
- [ ] 波动率曲面构建
- [ ] SVI模型校准
- [ ] 波动率微笑可视化
- [ ] 套利机会检测

---

### 3. 因子工程完善 (+3分)

#### 3.1 因子有效性监控 (2周)

**技术方案**:
```python
# quant/factor_analysis/factor_monitor.py

class FactorMonitor:
    """因子有效性监控"""
    
    def calculate_ic(self, 
                    factor_values: pd.Series,
                    forward_returns: pd.Series) -> float:
        """计算信息系数 (IC)"""
        return factor_values.corr(forward_returns)
    
    def calculate_ic_ir(self,
                       factor_values: pd.DataFrame,
                       forward_returns: pd.DataFrame) -> Dict:
        """
        计算IC和IR (Information Ratio)
        
        IR = mean(IC) / std(IC)
        """
        ic_series = []
        
        for date in factor_values.index:
            ic = self.calculate_ic(
                factor_values.loc[date],
                forward_returns.loc[date]
            )
            ic_series.append(ic)
        
        ic_series = pd.Series(ic_series)
        
        return {
            'mean_ic': ic_series.mean(),
            'std_ic': ic_series.std(),
            'ir': ic_series.mean() / ic_series.std(),
            'ic_series': ic_series
        }
    
    def monitor_factor_decay(self,
                            factor_name: str,
                            lookback_periods: int = 60) -> Dict:
        """监控因子衰减"""
        # 获取历史IC
        historical_ic = self._get_historical_ic(factor_name, lookback_periods)
        
        # 计算趋势
        from scipy.stats import linregress
        x = np.arange(len(historical_ic))
        slope, intercept, r_value, p_value, std_err = linregress(x, historical_ic)
        
        return {
            'factor_name': factor_name,
            'slope': slope,
            'r_squared': r_value**2,
            'p_value': p_value,
            'is_decaying': slope < -0.001 and p_value < 0.05
        }
```

**验收标准**:
- [ ] IC/IR计算
- [ ] 因子衰减检测
- [ ] 因子有效性报告
- [ ] 自动告警

---

## 时间表

| 月份 | 任务 | 状态 |
|------|------|------|
| M1 | 市场冲击 + 多资产回测 | 🔲 |
| M2 | Walk-Forward + 期货支持 | 🔲 |
| M3 | 波动率曲面 + 因子监控 | 🔲 |
| M4 | 架构优化 + 策略增强 | 🔲 |
| M5 | 全面测试 + 文档完善 | 🔲 |

---

## 最终验收标准

### 功能完整性
- [ ] 所有10个维度得分 ≥ 18/20
- [ ] 核心功能100%可用
- [ ] 无P0/P1级别bug

### 性能指标
- [ ] 回测速度 > 1000 trades/s
- [ ] API响应时间 < 100ms
- [ ] 系统可用性 > 99.9%

### 质量指标
- [ ] 代码覆盖率 > 90%
- [ ] 文档完整度 100%
- [ ] pylint评分 > 9.5

### 对标验证
- [ ] 与Backtrader对比测试
- [ ] 与Zipline对比测试
- [ ] 与商业系统对比

---

## 🎉 达到100分后

### 持续改进
1. 性能优化 (C++/Rust重写核心模块)
2. 分布式计算 (Dask/Ray)
3. 实时交易支持
4. 云原生部署

### 商业化
1. SaaS服务
2. 企业版
3. API服务
4. 培训咨询

---

**恭喜！完成Phase 3后，QuantSys-V2将成为世界级量化系统！**
