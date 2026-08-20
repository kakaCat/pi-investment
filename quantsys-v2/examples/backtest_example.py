"""
Backtest Example

Demonstrates the complete backtest framework with:
- Slippage models
- Commission models
- Position sizing strategies
- Report generation
"""
import sys
from pathlib import Path

# Add parent directory to path

from domain.quantlib.engine.slippage import create_slippage_model
from domain.quantlib.engine.commission import create_commission_model
from domain.quantlib.engine.position_sizing import create_position_sizer
from domain.quantlib.engine.backtest_report import BacktestReportGenerator
from datetime import datetime, timedelta
import random


def generate_sample_klines(symbol: str, days: int = 252) -> list:
    """Generate sample K-line data for testing"""
    klines = []
    base_price = 10.0
    current_price = base_price
    start_date = datetime(2024, 1, 1)

    for i in range(days):
        date = start_date + timedelta(days=i)
        if date.weekday() >= 5:  # Skip weekends
            continue

        # Random walk
        change = random.uniform(-0.03, 0.03)
        current_price *= (1 + change)

        klines.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': round(current_price * 0.99, 2),
            'high': round(current_price * 1.02, 2),
            'low': round(current_price * 0.98, 2),
            'close': round(current_price, 2),
            'volume': random.randint(1000000, 5000000)
        })

    return klines


def generate_sample_signals(klines: list, symbol: str) -> list:
    """Generate sample trading signals"""
    signals = []

    # Simple moving average crossover strategy
    for i in range(20, len(klines), 30):
        # Buy signal
        signals.append({
            'date': klines[i]['date'],
            'action': 'buy',
            'symbol': symbol,
            'reason': 'MA crossover',
            'confidence': random.uniform(0.6, 0.9)
        })

        # Sell signal (10-20 days later)
        exit_idx = min(i + random.randint(10, 20), len(klines) - 1)
        signals.append({
            'date': klines[exit_idx]['date'],
            'action': 'sell',
            'symbol': symbol,
            'reason': 'Take profit',
            'confidence': random.uniform(0.6, 0.9)
        })

    return signals


def run_simple_backtest(
    klines: list,
    signals: list,
    slippage_model,
    commission_model,
    position_sizer,
    initial_capital: float = 1000000
):
    """
    Run a simple backtest with the new engine components.

    This is a simplified version demonstrating the components.
    For production, use the integrated BacktestStage.
    """
    cash = initial_capital
    position = None
    trades = []
    equity_curve = []

    # Create price lookup
    price_by_date = {k['date']: k for k in klines}

    # Group signals by date
    signals_by_date = {}
    for sig in signals:
        signals_by_date.setdefault(sig['date'], []).append(sig)

    # Process each trading day
    for kline in klines:
        date = kline['date']
        price = kline['close']
        volume = kline['volume']

        # Process signals for this date
        day_signals = signals_by_date.get(date, [])

        for signal in day_signals:
            if signal['action'] == 'buy' and position is None:
                # Calculate position size
                total_equity = cash
                shares = position_sizer.calculate_position_size(
                    price=price,
                    available_capital=cash,
                    total_equity=total_equity,
                    signal_data={'confidence': signal.get('confidence', 1.0)}
                )

                if shares >= 100:
                    # Apply slippage
                    market_data = {'volume': volume}
                    fill_price = slippage_model.apply_slippage(
                        price, shares, 'buy', market_data
                    )

                    # Calculate commission
                    fees = commission_model.calculate_commission(
                        fill_price, shares, 'buy'
                    )

                    total_cost = fill_price * shares + fees['total']

                    if total_cost <= cash:
                        cash -= total_cost
                        position = {
                            'symbol': signal['symbol'],
                            'entry_date': date,
                            'entry_price': fill_price,
                            'shares': shares,
                            'cost': total_cost,
                            'entry_reason': signal['reason']
                        }

            elif signal['action'] == 'sell' and position is not None:
                # Apply slippage
                market_data = {'volume': volume}
                fill_price = slippage_model.apply_slippage(
                    price, position['shares'], 'sell', market_data
                )

                # Calculate commission
                fees = commission_model.calculate_commission(
                    fill_price, position['shares'], 'sell'
                )

                proceeds = fill_price * position['shares'] - fees['total']
                profit = proceeds - position['cost']
                profit_pct = profit / position['cost']

                entry_date = datetime.strptime(position['entry_date'], '%Y-%m-%d')
                exit_date = datetime.strptime(date, '%Y-%m-%d')
                holding_days = (exit_date - entry_date).days

                cash += proceeds

                trades.append({
                    'symbol': position['symbol'],
                    'entry_date': position['entry_date'],
                    'entry_price': position['entry_price'],
                    'exit_date': date,
                    'exit_price': fill_price,
                    'shares': position['shares'],
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'holding_days': holding_days,
                    'entry_reason': position['entry_reason'],
                    'exit_reason': signal['reason']
                })

                position = None

        # Record daily equity
        position_value = 0.0
        if position:
            position_value = price * position['shares']

        total_equity = cash + position_value
        return_pct = (total_equity - initial_capital) / initial_capital

        equity_curve.append({
            'date': date,
            'cash': cash,
            'position_value': position_value,
            'total_equity': total_equity,
            'return_pct': return_pct,
            'drawdown': 0.0  # Will be calculated in report
        })

    return equity_curve, trades


def main():
    """Run backtest examples"""
    print("=" * 70)
    print("Backtest Framework Example")
    print("=" * 70)
    print()

    # Generate sample data
    symbol = '000001'
    print(f"Generating sample data for {symbol}...")
    klines = generate_sample_klines(symbol, days=252)
    signals = generate_sample_signals(klines, symbol)
    print(f"Generated {len(klines)} klines and {len(signals)} signals")
    print()

    # ==================== Example 1: Conservative Setup ====================
    print("Example 1: Conservative Setup")
    print("-" * 70)

    slippage = create_slippage_model('fixed', slippage_pct=0.001)
    commission = create_commission_model('ashare')
    sizer = create_position_sizer('percent', percent=0.1)

    print(f"Slippage: Fixed 0.1%")
    print(f"Commission: A-share standard")
    print(f"Position sizing: Fixed 10% of equity")
    print()

    equity_curve, trades = run_simple_backtest(
        klines, signals, slippage, commission, sizer
    )

    # Generate report
    report_gen = BacktestReportGenerator(risk_free_rate=0.03)
    report = report_gen.generate_report(
        equity_curve=equity_curve,
        trades=trades,
        initial_capital=1000000,
        start_date=klines[0]['date'],
        end_date=klines[-1]['date'],
        strategy_name='Conservative MA Crossover',
        parameters={
            'slippage': 'fixed_0.1%',
            'commission': 'ashare',
            'position_sizing': 'fixed_10%'
        }
    )

    print(report['summary'])
    print()

    # ==================== Example 2: Aggressive Setup ====================
    print("\n" + "=" * 70)
    print("Example 2: Aggressive Setup (Kelly Criterion)")
    print("-" * 70)

    slippage = create_slippage_model('market_impact', impact_coefficient=0.05)
    commission = create_commission_model('ashare')
    sizer = create_position_sizer(
        'kelly',
        win_rate=0.6,
        profit_loss_ratio=2.0,
        kelly_fraction=0.5
    )

    print(f"Slippage: Market impact model")
    print(f"Commission: A-share standard")
    print(f"Position sizing: Half Kelly (win_rate=60%, P/L ratio=2.0)")
    print()

    equity_curve, trades = run_simple_backtest(
        klines, signals, slippage, commission, sizer
    )

    report = report_gen.generate_report(
        equity_curve=equity_curve,
        trades=trades,
        initial_capital=1000000,
        start_date=klines[0]['date'],
        end_date=klines[-1]['date'],
        strategy_name='Aggressive MA Crossover',
        parameters={
            'slippage': 'market_impact',
            'commission': 'ashare',
            'position_sizing': 'half_kelly'
        }
    )

    print(report['summary'])
    print()

    # ==================== Example 3: Risk Parity Setup ====================
    print("\n" + "=" * 70)
    print("Example 3: Risk Parity Setup")
    print("-" * 70)

    slippage = create_slippage_model('proportional', volume_factor=0.1)
    commission = create_commission_model('tiered')
    sizer = create_position_sizer('risk_parity', target_risk_percent=0.02)

    print(f"Slippage: Proportional to volume")
    print(f"Commission: Tiered (volume-based)")
    print(f"Position sizing: Risk parity (2% target risk)")
    print()

    equity_curve, trades = run_simple_backtest(
        klines, signals, slippage, commission, sizer
    )

    report = report_gen.generate_report(
        equity_curve=equity_curve,
        trades=trades,
        initial_capital=1000000,
        start_date=klines[0]['date'],
        end_date=klines[-1]['date'],
        strategy_name='Risk Parity MA Crossover',
        parameters={
            'slippage': 'proportional',
            'commission': 'tiered',
            'position_sizing': 'risk_parity_2%'
        }
    )

    print(report['summary'])
    print()

    # ==================== Export Reports ====================
    print("\n" + "=" * 70)
    print("Exporting Reports")
    print("-" * 70)

    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)

    # Export JSON
    json_path = output_dir / 'backtest_report.json'
    report_gen.export_to_json(report, str(json_path))
    print(f"JSON report exported to: {json_path}")

    # Export Markdown
    md_path = output_dir / 'backtest_report.md'
    report_gen.export_to_markdown(report, str(md_path))
    print(f"Markdown report exported to: {md_path}")

    print()
    print("=" * 70)
    print("Backtest examples completed!")
    print("=" * 70)


if __name__ == '__main__':
    main()
