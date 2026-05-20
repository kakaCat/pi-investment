# 回测引擎

事件驱动的回测引擎，用于验证量化策略。

## 核心特性

- ✅ **事件驱动架构**: 逐日遍历历史数据
- ✅ **涨跌停限制**: 无法买入涨停股/卖出跌停股
- ✅ **停牌处理**: 自动跳过停牌日
- ✅ **滑点模型**: 固定滑点 + 冲击成本
- ✅ **交易成本**: 佣金(万三) + 印花税(千一)
- ✅ **权益曲线**: 每日权益记录
- ✅ **绩效分析**: 收益率/夏普/回撤/胜率

## 快速开始

```python
from backtest import BacktestEngine
from strategies import MACrossStrategy

# 创建回测引擎
engine = BacktestEngine(
    initial_capital=1000000,
    commission_rate=0.0003,  # 佣金 0.03%
    stamp_tax_rate=0.001,    # 印花税 0.1%
    slippage_rate=0.001      # 滑点 0.1%
)

# 创建策略
strategy = MACrossStrategy(fast=5, slow=20)

# 运行回测
result = engine.run(
    strategy=strategy,
    data=historical_data,
    start_date='2020-01-01',
    end_date='2025-12-31'
)

# 查看结果
print(f"总收益率: {result['total_return']*100:.2f}%")
print(f"年化收益率: {result['annual_return']*100:.2f}%")
print(f"最大回撤: {result['max_drawdown']*100:.2f}%")
print(f"夏普比率: {result['sharpe_ratio']:.2f}")
print(f"胜率: {result['win_rate']*100:.2f}%")
```

## 模块说明

### BacktestEngine (engine.py)
核心回测引擎，负责:
- 逐日遍历数据
- 处理订单执行
- 更新持仓和权益
- 生成回测报告

### SimulatedBroker (broker.py)
模拟券商，负责:
- 计算交易成本 (佣金+印花税)
- 验证订单合法性
- 检查购买力

### SlippageModel (slippage.py)
滑点模型，负责:
- 固定滑点计算
- 冲击成本计算 (大单影响)

### Portfolio (portfolio.py)
持仓管理，负责:
- 持仓跟踪
- 资金管理
- 风险监控

## 回测结果

```python
{
    'strategy_id': 'ma_cross',
    'start_date': '2020-01-01',
    'end_date': '2025-12-31',
    'initial_capital': 1000000,
    'final_capital': 1250000,
    'total_return': 0.25,           # 25%
    'annual_return': 0.045,         # 4.5%
    'max_drawdown': -0.12,          # -12%
    'sharpe_ratio': 1.45,
    'total_trades': 120,
    'winning_trades': 75,
    'losing_trades': 45,
    'win_rate': 0.625,              # 62.5%
    'profit_loss_ratio': 1.8,
    'avg_holding_days': 15,
    'trades': [...],                # 交易记录
    'daily_equity': [...]           # 权益曲线
}
```

## 策略接口

策略需要实现 `calculate_signals` 方法:

```python
class MyStrategy:
    def calculate_signals(self, date: str, data: pd.DataFrame) -> List[Dict]:
        """
        计算交易信号
        
        Returns:
            [
                {
                    'symbol': '000001',
                    'action': 'buy',  # or 'sell'
                    'reason': '金叉买入'
                },
                ...
            ]
        """
        signals = []
        # 策略逻辑...
        return signals
```

## 注意事项

1. **数据格式**: 需要包含 symbol, date, open, high, low, close, volume
2. **涨跌停**: 自动处理，无法买入涨停股/卖出跌停股
3. **停牌**: 需要提供停牌数据，否则会尝试交易停牌股
4. **滑点**: 默认0.1%，可根据实际情况调整
5. **交易成本**: 佣金万三+印花税千一，符合A股实际

## 性能要求

- 回测10年日线数据 < 30秒
- 支持1000+股票池
- 内存占用 < 2GB

## 下一步

1. 实现策略层 (strategies/)
2. 集成因子库 (factors/)
3. 添加风控系统 (risk/)
4. 实现参数优化
