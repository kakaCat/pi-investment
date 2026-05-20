# 风控系统 (Risk Management System)

量化交易的风险管理模块，包含预交易风控、仓位管理、止损机制等核心功能。

## 📁 模块结构

```
risk/
├── __init__.py              # 模块入口
├── pre_trade.py             # 预交易风控
├── position_manager.py      # 仓位管理
└── stop_loss.py             # 止损机制
```

---

## 🛡️ 1. 预交易风控 (Pre-Trade Risk Check)

在订单执行前进行风险检查，防止违规交易。

### 检查项

1. **黑名单检查** - 禁止交易特定股票
2. **ST股票检查** - 可配置是否允许ST股票
3. **单股仓位限制** - 默认不超过10%
4. **行业集中度限制** - 默认不超过30%
5. **最大回撤限制** - 默认不超过20%
6. **单日交易次数限制** - 默认不超过10次
7. **流动性检查** - 确保有足够的流动性

### 使用示例

```python
from risk import PreTradeRiskCheck, RiskConfig

# 创建风控配置
config = RiskConfig(
    max_position_pct=0.10,      # 单股最大10%
    max_sector_pct=0.30,        # 单行业最大30%
    max_drawdown=0.20,          # 最大回撤20%
    max_daily_trades=10,        # 单日最多10笔
    blacklist=['000001'],       # 黑名单
    allow_st_stocks=False       # 不允许ST股票
)

# 创建风控检查器
risk_check = PreTradeRiskCheck(config)

# 检查订单
is_valid, error_msg = risk_check.check(order, portfolio, market_data)

if not is_valid:
    print(f"订单被拒绝: {error_msg}")
else:
    # 执行订单
    execute_order(order)

# 获取风控统计
stats = risk_check.get_statistics()
print(f"总拒绝订单数: {stats['total_rejected']}")
print(f"拒绝原因分布: {stats['rejected_by_reason']}")
```

---

## 📊 2. 仓位管理 (Position Management)

动态调整仓位大小，基于风险和市场条件。

### 仓位策略

1. **固定仓位** - 每次固定比例
2. **Kelly公式** - 基于胜率和盈亏比
3. **波动率调整** - 根据股票波动率调整
4. **ATR仓位** - 基于ATR止损计算
5. **风险平价** - 相关性调整

### 使用示例

```python
from risk import PositionManager, PositionSizeConfig

# 创建仓位管理配置
config = PositionSizeConfig(
    method='kelly',             # 使用Kelly公式
    kelly_fraction=0.25,        # 保守系数25%
    max_position_pct=0.20,      # 最大20%
    min_position_pct=0.02       # 最小2%
)

# 创建仓位管理器
pos_mgr = PositionManager(config)

# 计算仓位大小
market_data = {
    'win_rate': 0.6,
    'profit_loss_ratio': 2.0,
    'volatility': 0.25
}

shares = pos_mgr.calculate_position_size(
    symbol='000001',
    price=10.0,
    total_equity=1000000,
    signal_strength=0.8,        # 信号强度80%
    market_data=market_data
)

print(f"建议买入: {shares}股")

# 计算再平衡交易
target_positions = {
    '000001': 0.10,
    '000002': 0.15,
    '000003': 0.08
}

trades = pos_mgr.calculate_rebalance_trades(
    target_positions,
    current_positions,
    total_equity,
    threshold=0.05  # 5%偏差才调仓
)

for symbol, shares in trades.items():
    if shares > 0:
        print(f"买入 {symbol}: {shares}股")
    else:
        print(f"卖出 {symbol}: {-shares}股")
```

---

## 🛑 3. 止损机制 (Stop Loss Management)

多种止损策略，保护资金安全。

### 止损类型

1. **固定止损** - 固定百分比止损 (如5%)
2. **ATR止损** - 基于ATR的动态止损
3. **移动止损** - 跟随最高价移动 (如10%)
4. **时间止损** - 超过最大持仓天数
5. **组合止损** - 结合多种策略 (推荐)

### 使用示例

```python
from risk import StopLossManager, StopLossConfig

# 创建止损配置
config = StopLossConfig(
    method='combined',          # 组合止损
    fixed_pct=0.05,            # 固定止损5%
    trailing_pct=0.10,         # 移动止损10%
    max_holding_days=60,       # 最大持仓60天
    profit_protect_pct=0.15,   # 盈利15%后启用保护
    profit_protect_stop=0.05   # 保护止损5%
)

# 创建止损管理器
stop_mgr = StopLossManager(config)

# 检查是否应该止损
should_stop, reason = stop_mgr.should_stop_loss(
    symbol='000001',
    entry_price=10.0,
    current_price=9.2,
    highest_price=11.5,
    entry_date='2024-01-01',
    current_date='2024-02-15',
    market_data={'atr': 0.5}
)

if should_stop:
    print(f"触发止损: {reason}")
    # 执行止损卖出
    sell_position(symbol)

# 批量检查止损
positions = {
    '000001': {
        'entry_price': 10.0,
        'entry_date': '2024-01-01',
        'highest_price': 11.5,
        'shares': 1000
    },
    '000002': {
        'entry_price': 20.0,
        'entry_date': '2024-01-01',
        'highest_price': 22.0,
        'shares': 500
    }
}

current_prices = {
    '000001': 9.2,
    '000002': 21.5
}

stops = stop_mgr.batch_check_stops(
    positions, current_prices, '2024-02-15'
)

for stop in stops:
    print(f"止损: {stop['symbol']} - {stop['reason']}")
    print(f"  入场价: {stop['entry_price']:.2f}")
    print(f"  当前价: {stop['current_price']:.2f}")
    print(f"  亏损: {stop['loss_pct']*100:.2f}%")
```

---

## 🔄 完整使用流程

```python
from risk import PreTradeRiskCheck, PositionManager, StopLossManager

# 1. 初始化风控系统
risk_check = PreTradeRiskCheck()
pos_mgr = PositionManager()
stop_mgr = StopLossManager()

# 2. 策略生成信号
signal = strategy.generate_signal('000001', data)

if signal == 'buy':
    # 3. 计算仓位
    shares = pos_mgr.calculate_position_size(
        symbol='000001',
        price=current_price,
        total_equity=portfolio.total_equity,
        signal_strength=signal_strength
    )
    
    # 4. 创建订单
    order = Order(
        symbol='000001',
        action='buy',
        price=current_price,
        shares=shares,
        date=current_date
    )
    
    # 5. 预交易风控检查
    is_valid, error = risk_check.check(order, portfolio)
    
    if is_valid:
        # 6. 执行订单
        execute_order(order)
    else:
        print(f"订单被拒绝: {error}")

# 7. 每日检查止损
for symbol, position in portfolio.positions.items():
    should_stop, reason = stop_mgr.should_stop_loss(
        symbol=symbol,
        entry_price=position.entry_price,
        current_price=get_current_price(symbol),
        highest_price=position.highest_price,
        entry_date=position.entry_date,
        current_date=current_date
    )
    
    if should_stop:
        print(f"触发止损: {symbol} - {reason}")
        sell_position(symbol)
```

---

## 📈 性能指标

- **预交易风控**: < 1ms/订单
- **仓位计算**: < 1ms/股票
- **止损检查**: < 1ms/持仓

---

## 🧪 测试

运行测试套件:

```bash
# 运行所有风控测试
PYTHONPATH=. python -m unittest python/tests/test_risk.py -v

# 运行特定测试
PYTHONPATH=. python -m unittest python/tests/test_risk.py::TestPreTradeRiskCheck -v
```

测试覆盖:
- ✅ 预交易风控: 6个测试
- ✅ 止损机制: 5个测试
- ✅ 仓位管理: 7个测试
- **总计: 18个测试用例**

---

## 🎯 最佳实践

### 1. 预交易风控

- ✅ 始终启用黑名单检查
- ✅ 根据策略类型调整仓位限制
- ✅ 定期审查被拒绝的订单
- ✅ 在回测中也使用风控

### 2. 仓位管理

- ✅ 使用Kelly公式的保守版本 (1/4 Kelly)
- ✅ 根据信号强度调整仓位
- ✅ 考虑相关性，避免过度集中
- ✅ 设置合理的最大/最小仓位

### 3. 止损机制

- ✅ 推荐使用组合止损策略
- ✅ 盈利后启用移动止损
- ✅ 设置时间止损避免长期套牢
- ✅ 根据市场波动率调整止损幅度

---

## 📝 配置建议

### 保守型策略

```python
RiskConfig(
    max_position_pct=0.05,      # 单股5%
    max_sector_pct=0.20,        # 单行业20%
    max_drawdown=0.15,          # 最大回撤15%
    allow_st_stocks=False
)

StopLossConfig(
    method='combined',
    fixed_pct=0.03,             # 固定止损3%
    trailing_pct=0.08,          # 移动止损8%
    max_holding_days=30
)
```

### 激进型策略

```python
RiskConfig(
    max_position_pct=0.20,      # 单股20%
    max_sector_pct=0.40,        # 单行业40%
    max_drawdown=0.25,          # 最大回撤25%
    allow_st_stocks=True
)

StopLossConfig(
    method='combined',
    fixed_pct=0.08,             # 固定止损8%
    trailing_pct=0.15,          # 移动止损15%
    max_holding_days=90
)
```

---

## 🔗 相关模块

- [回测引擎](../backtest/README.md) - 集成风控系统
- [策略层](../python/strategies/README.md) - 使用风控检查
- [因子库](../python/factors/README.md) - 提供市场数据

---

## 📚 参考资料

- Kelly Criterion: https://en.wikipedia.org/wiki/Kelly_criterion
- Risk Parity: https://en.wikipedia.org/wiki/Risk_parity
- ATR Stop Loss: https://www.investopedia.com/articles/trading/08/average-true-range.asp
