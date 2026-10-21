# Backtest Engine Documentation

## Overview

The quantsys-v2 backtest engine provides a production-grade framework for realistic strategy backtesting with:

- **Slippage Models**: Simulate realistic execution prices
- **Commission Models**: Accurate fee calculations for different markets
- **Position Sizing**: Multiple strategies for capital allocation
- **Report Generation**: Comprehensive performance metrics and risk analysis

## Architecture

```
quant/engine/
├── slippage.py           # Slippage models
├── commission.py         # Commission/fee models
├── position_sizing.py    # Position sizing strategies
└── backtest_report.py    # Report generation
```

## Components

### 1. Slippage Models

Slippage represents the difference between expected and actual execution prices.

#### Available Models

**FixedSlippage**
- Constant percentage slippage
- Simple but unrealistic for large orders
```python
from quant.engine import FixedSlippage

slippage = FixedSlippage(slippage_pct=0.001)  # 0.1%
fill_price = slippage.apply_slippage(100.0, 1000, 'buy')
# buy: 100.1, sell: 99.9
```

**ProportionalSlippage**
- Scales with order size relative to volume
- More realistic for varying order sizes
```python
from quant.engine import ProportionalSlippage

slippage = ProportionalSlippage(
    base_slippage_pct=0.0005,
    volume_factor=0.1
)
market_data = {'volume': 10000}
fill_price = slippage.apply_slippage(100.0, 1000, 'buy', market_data)
```

**MarketImpactSlippage**
- Models price impact based on order size, liquidity, and volatility
- Uses square-root model: impact ∝ sqrt(order_size / volume)
- Most realistic but requires market data
```python
from quant.engine import MarketImpactSlippage

slippage = MarketImpactSlippage(
    base_slippage_pct=0.0003,
    impact_coefficient=0.05,
    volatility_factor=0.5
)
market_data = {'volume': 10000, 'volatility': 1.2}
fill_price = slippage.apply_slippage(100.0, 1000, 'buy', market_data)
```

**NoSlippage**
- Zero slippage for testing or optimistic scenarios

#### Factory Function
```python
from quant.engine import create_slippage_model

model = create_slippage_model('fixed', slippage_pct=0.001)
model = create_slippage_model('proportional', volume_factor=0.1)
model = create_slippage_model('market_impact', impact_coefficient=0.05)
model = create_slippage_model('none')
```

### 2. Commission Models

Accurate fee calculations for different markets.

#### Available Models

**AShareCommission**
- A-share (China mainland) fee structure
- Commission: 0.03% (both sides, minimum 5 RMB)
- Stamp tax: 0.1% (sell only)
- Transfer fee: 0.001% (both sides)
```python
from quant.engine import AShareCommission

commission = AShareCommission()
fees = commission.calculate_commission(10.0, 10000, 'buy')
# {'commission': 30.0, 'stamp_tax': 0.0, 'transfer_fee': 1.0, 'total': 31.0}

fees = commission.calculate_commission(10.0, 10000, 'sell')
# {'commission': 30.0, 'stamp_tax': 100.0, 'transfer_fee': 1.0, 'total': 131.0}
```

**HKStockCommission**
- Hong Kong stock fee structure
- Commission: 0.25% (minimum 100 HKD)
- Trading fee: 0.00565%
- Transaction levy: 0.0027%
- Stamp duty: 0.13% (minimum 1 HKD)
```python
from quant.engine import HKStockCommission

commission = HKStockCommission()
fees = commission.calculate_commission(100.0, 1000, 'buy')
```

**FixedCommission**
- Simple fixed percentage commission
- Useful for US stocks or simplified backtesting
```python
from quant.engine import FixedCommission

commission = FixedCommission(
    commission_rate=0.001,
    min_commission=5.0,
    per_share_fee=0.0
)
```

**TieredCommission**
- Commission rate decreases with trade size
- Common for institutional traders
```python
from quant.engine import TieredCommission

tiers = [
    (0, 0.0003),        # 0-100k: 0.03%
    (100000, 0.0002),   # 100k-1M: 0.02%
    (1000000, 0.0001)   # 1M+: 0.01%
]
commission = TieredCommission(tiers=tiers, min_commission=5.0)
```

**ZeroCommission**
- Zero commission for testing

#### Factory Function
```python
from quant.engine import create_commission_model

model = create_commission_model('ashare')
model = create_commission_model('hkstock')
model = create_commission_model('fixed', commission_rate=0.001)
model = create_commission_model('tiered', tiers=[(0, 0.0003)])
model = create_commission_model('zero')
```

### 3. Position Sizing Strategies

Controls how much capital to allocate to each trade.

#### Available Strategies

**FixedPositionSizer**
- Allocates fixed dollar amount per trade
- Simple but doesn't scale with portfolio
```python
from quant.engine import FixedPositionSizer

sizer = FixedPositionSizer(fixed_amount=100000, lot_size=100)
shares = sizer.calculate_position_size(
    price=10.0,
    available_capital=500000,
    total_equity=1000000
)
# Returns: 10000 shares
```

**FixedPercentSizer**
- Allocates fixed percentage of equity
- Scales with portfolio size
```python
from quant.engine import FixedPercentSizer

sizer = FixedPercentSizer(
    percent=0.1,        # 10% of equity
    max_percent=0.3     # Cap at 30%
)
shares = sizer.calculate_position_size(
    price=10.0,
    available_capital=500000,
    total_equity=1000000
)
# Returns: 10000 shares (10% of 1M = 100k)
```

**KellyPositionSizer**
- Optimal sizing based on Kelly Criterion
- Formula: f = (p * b - q) / b
  - p = win probability
  - b = profit/loss ratio
  - q = 1 - p
- Uses fractional Kelly to reduce risk
```python
from quant.engine import KellyPositionSizer

sizer = KellyPositionSizer(
    win_rate=0.6,
    profit_loss_ratio=2.0,
    kelly_fraction=0.25  # Quarter Kelly for safety
)

# Can scale by signal confidence
signal_data = {'confidence': 0.8}
shares = sizer.calculate_position_size(
    price=10.0,
    available_capital=500000,
    total_equity=1000000,
    signal_data=signal_data
)
```

**RiskParitySizer**
- Sizes positions to equalize risk contribution
- Position size ∝ 1 / volatility
```python
from quant.engine import RiskParitySizer

sizer = RiskParitySizer(
    target_risk_percent=0.02,  # 2% risk per position
    default_volatility=0.02
)

signal_data = {'volatility': 0.03}  # Asset volatility
shares = sizer.calculate_position_size(
    price=10.0,
    available_capital=500000,
    total_equity=1000000,
    signal_data=signal_data
)
```

**VolatilityTargetSizer**
- Maintains constant portfolio volatility
- Position weight = target_volatility / asset_volatility
```python
from quant.engine import VolatilityTargetSizer

sizer = VolatilityTargetSizer(
    target_volatility=0.15,  # 15% annual volatility
    default_volatility=0.02
)
```

#### Factory Function
```python
from quant.engine import create_position_sizer

sizer = create_position_sizer('fixed', fixed_amount=100000)
sizer = create_position_sizer('percent', percent=0.1)
sizer = create_position_sizer('kelly', win_rate=0.6, profit_loss_ratio=2.0)
sizer = create_position_sizer('risk_parity', target_risk_percent=0.02)
sizer = create_position_sizer('volatility_target', target_volatility=0.15)
```

### 4. Report Generation

Comprehensive performance metrics and risk analysis.

#### BacktestReportGenerator

```python
from quant.engine import BacktestReportGenerator

generator = BacktestReportGenerator(risk_free_rate=0.03)

report = generator.generate_report(
    equity_curve=equity_curve,
    trades=trades,
    initial_capital=1000000,
    start_date='2024-01-01',
    end_date='2024-12-31',
    strategy_name='My Strategy',
    parameters={'param1': 'value1'}
)
```

#### Metrics Calculated

**Returns**
- Total return
- Annual return
- Monthly returns

**Risk-Adjusted Returns**
- Sharpe ratio
- Sortino ratio
- Calmar ratio

**Risk Metrics**
- Maximum drawdown
- Maximum drawdown duration
- Volatility (annualized)
- Downside deviation

**Trade Statistics**
- Total trades
- Win rate
- Profit/loss ratio
- Average win/loss
- Average holding days
- Max consecutive wins/losses

**Capital Metrics**
- Initial/final/peak capital

#### Export Formats

**JSON Export**
```python
generator.export_to_json(report, 'backtest_report.json')
```

**Markdown Export**
```python
generator.export_to_markdown(report, 'backtest_report.md')
```

## Complete Example

```python
from quant.engine import (
    create_slippage_model,
    create_commission_model,
    create_position_sizer,
    BacktestReportGenerator
)

# Configure backtest components
slippage = create_slippage_model('market_impact', impact_coefficient=0.05)
commission = create_commission_model('ashare')
sizer = create_position_sizer('kelly', win_rate=0.6, profit_loss_ratio=2.0)

# Run backtest (simplified example)
cash = 1000000
position = None
trades = []
equity_curve = []

for kline in klines:
    price = kline['close']
    
    # Process signals
    for signal in signals_for_date(kline['date']):
        if signal['action'] == 'buy' and position is None:
            # Calculate position size
            shares = sizer.calculate_position_size(
                price=price,
                available_capital=cash,
                total_equity=cash,
                signal_data={'confidence': signal['confidence']}
            )
            
            # Apply slippage
            fill_price = slippage.apply_slippage(
                price, shares, 'buy', {'volume': kline['volume']}
            )
            
            # Calculate commission
            fees = commission.calculate_commission(fill_price, shares, 'buy')
            
            # Execute trade
            total_cost = fill_price * shares + fees['total']
            if total_cost <= cash:
                cash -= total_cost
                position = {
                    'entry_price': fill_price,
                    'shares': shares,
                    'cost': total_cost
                }
        
        elif signal['action'] == 'sell' and position is not None:
            # Similar logic for selling
            pass
    
    # Record equity
    position_value = position['shares'] * price if position else 0
    equity_curve.append({
        'date': kline['date'],
        'cash': cash,
        'position_value': position_value,
        'total_equity': cash + position_value,
        'return_pct': (cash + position_value - 1000000) / 1000000,
        'drawdown': 0.0
    })

# Generate report
generator = BacktestReportGenerator(risk_free_rate=0.03)
report = generator.generate_report(
    equity_curve=equity_curve,
    trades=trades,
    initial_capital=1000000,
    start_date=klines[0]['date'],
    end_date=klines[-1]['date'],
    strategy_name='My Strategy'
)

print(report['summary'])
generator.export_to_json(report, 'report.json')
generator.export_to_markdown(report, 'report.md')
```

## Integration with BacktestStage

The existing `BacktestStage` can be enhanced to use these components:

```python
from quant.stages.backtest_stage import BacktestStage
from quant.engine import (
    create_slippage_model,
    create_commission_model,
    create_position_sizer
)

# Create enhanced backtest stage
stage = BacktestStage(
    name='backtest',
    initial_capital=1000000,
    slippage_model=create_slippage_model('market_impact'),
    commission_model=create_commission_model('ashare'),
    position_sizer=create_position_sizer('kelly', win_rate=0.6)
)

# Run backtest
result = stage.process({
    'symbol': '000001',
    'klines': klines,
    'signals': signals
})

print(result['backtest']['metrics'])
```

## Testing

All components have comprehensive unit tests:

```bash
pytest tests/test_backtest_engine.py -v
```

Test coverage:
- Slippage models: 5 tests
- Commission models: 8 tests
- Position sizers: 10 tests
- Report generator: 4 tests

## Performance Considerations

1. **Slippage Models**
   - `FixedSlippage`: Fastest, O(1)
   - `ProportionalSlippage`: Fast, O(1)
   - `MarketImpactSlippage`: Moderate, requires market data

2. **Commission Models**
   - All models: O(1) calculation
   - `TieredCommission`: O(log n) for tier lookup

3. **Position Sizers**
   - `FixedPositionSizer`: O(1)
   - `FixedPercentSizer`: O(1)
   - `KellyPositionSizer`: O(1)
   - `RiskParitySizer`: O(1)
   - `VolatilityTargetSizer`: O(1)

4. **Report Generation**
   - O(n) where n = number of equity curve points
   - Efficient numpy-based calculations

## Best Practices

1. **Slippage Selection**
   - Use `FixedSlippage` for quick tests
   - Use `MarketImpactSlippage` for realistic backtests
   - Calibrate parameters based on historical execution data

2. **Commission Models**
   - Always use market-specific models (AShare, HKStock)
   - Include all fees (stamp tax, transfer fees)
   - Verify minimum commission thresholds

3. **Position Sizing**
   - Start with `FixedPercentSizer` (10-20%)
   - Use `KellyPositionSizer` with fractional Kelly (0.25-0.5)
   - Update Kelly parameters based on rolling performance
   - Consider `RiskParitySizer` for multi-asset portfolios

4. **Report Analysis**
   - Focus on risk-adjusted returns (Sharpe, Sortino)
   - Monitor maximum drawdown and duration
   - Analyze trade statistics (win rate, P/L ratio)
   - Compare against benchmark

## Future Enhancements

Potential additions:
- Dynamic position sizing based on market regime
- Multi-asset portfolio backtesting
- Transaction cost analysis (TCA)
- Benchmark comparison
- Monte Carlo simulation
- Walk-forward optimization
- Real-time performance tracking
