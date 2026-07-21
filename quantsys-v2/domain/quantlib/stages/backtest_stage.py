"""
Backtest Stage

Event-driven backtesting engine as a PipelineStage.
Accepts klines + signals, runs strategy simulation, produces performance metrics.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
import numpy as np
import pandas as pd

from domain.quantlib.core.pipeline import PipelineStage

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    cost: float
    entry_reason: str = ""
    highest_price: float = 0.0


@dataclass
class Trade:
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    profit: float
    profit_pct: float
    holding_days: int
    entry_reason: str = ""
    exit_reason: str = ""


@dataclass
class DailyEquity:
    date: str
    cash: float
    position_value: float
    total_equity: float
    return_pct: float
    drawdown: float


class BacktestStage(PipelineStage):
    """
    Event-driven backtest stage.

    Input:
    - symbol: stock code
    - klines: K-line data (list of dict with ohlcv + date)
    - signals: trading signals (list of {date, action, symbol, reason, confidence})
    - initial_capital: starting capital (optional, default 1,000,000)
    - commission_rate: commission rate (optional, default 0.0003)
    - stamp_tax_rate: stamp tax rate, sell only (optional, default 0.001)
    - slippage_rate: slippage (optional, default 0.001)

    Output:
    - backtest: {metrics, equity_curve, trades}
    """

    def __init__(
        self,
        name: str = "backtest",
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        slippage_rate: float = 0.001,
    ):
        super().__init__(name)
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.slippage_rate = slippage_rate

    def validate_input(self, data: Dict[str, Any]) -> bool:
        if "symbol" not in data:
            raise ValueError("Missing required field: symbol")
        if "klines" not in data:
            raise ValueError("Missing required field: klines")
        if not isinstance(data["klines"], list) or len(data["klines"]) < 2:
            raise ValueError("klines must be a list with at least 2 entries")
        return True

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = data["symbol"]
        klines = data["klines"]
        signals = data.get("signals", [])

        capital = data.get("initial_capital", self.initial_capital)
        commission = data.get("commission_rate", self.commission_rate)
        stamp = data.get("stamp_tax_rate", self.stamp_tax_rate)
        slippage = data.get("slippage_rate", self.slippage_rate)

        logger.info(f"Running backtest for {symbol}, {len(klines)} klines, {len(signals)} signals")

        result = self._run_backtest(
            symbol, klines, signals,
            initial_capital=capital,
            commission_rate=commission,
            stamp_tax_rate=stamp,
            slippage_rate=slippage,
        )

        output = data.copy()
        output["backtest"] = result
        logger.info(
            f"Backtest complete: return={result['metrics']['total_return']:.2%}, "
            f"sharpe={result['metrics']['sharpe_ratio']:.2f}"
        )
        return output

    def _run_backtest(
        self,
        symbol: str,
        klines: List[Dict],
        signals: List[Dict],
        initial_capital: float,
        commission_rate: float,
        stamp_tax_rate: float,
        slippage_rate: float,
    ) -> Dict:
        df = self._prepare_klines_df(klines)

        cash = initial_capital
        positions: Dict[str, Position] = {}
        trades: List[Trade] = []
        equity_curve: List[DailyEquity] = []

        signals_by_date: Dict[str, List[Dict]] = {}
        for s in signals:
            d = s.get("date", "")
            signals_by_date.setdefault(d, []).append(s)

        trading_dates = sorted(df["date"].unique())

        for date in trading_dates:
            day_data = df[df["date"] == date]
            if day_data.empty:
                continue

            current_price = float(day_data.iloc[0]["close"])

            # Update position highest prices
            for pos in positions.values():
                if current_price > pos.highest_price:
                    pos.highest_price = current_price

            # Process signals for this date
            day_signals = signals_by_date.get(date, [])
            for sig in day_signals:
                action = sig.get("action", "hold")

                if action == "buy" and symbol not in positions:
                    available = cash * 0.95
                    fill_price = current_price * (1 + slippage_rate)
                    shares = int(available / fill_price / 100) * 100

                    if shares >= 100:
                        amount = fill_price * shares
                        comm = max(amount * commission_rate, 5)
                        total_cost = amount + comm

                        if total_cost <= cash:
                            cash -= total_cost
                            positions[symbol] = Position(
                                symbol=symbol,
                                entry_date=date,
                                entry_price=fill_price,
                                shares=shares,
                                cost=total_cost,
                                entry_reason=sig.get("reason", ""),
                                highest_price=fill_price,
                            )

                elif action == "sell" and symbol in positions:
                    pos = positions.pop(symbol)
                    fill_price = current_price * (1 - slippage_rate)

                    amount = fill_price * pos.shares
                    comm = max(amount * commission_rate, 5)
                    tax = amount * stamp_tax_rate
                    proceeds = amount - comm - tax

                    profit = proceeds - pos.cost
                    profit_pct = profit / pos.cost if pos.cost > 0 else 0

                    entry_dt = datetime.strptime(pos.entry_date, "%Y-%m-%d")
                    exit_dt = datetime.strptime(date, "%Y-%m-%d")
                    holding_days = (exit_dt - entry_dt).days

                    cash += proceeds
                    trades.append(Trade(
                        symbol=symbol,
                        entry_date=pos.entry_date,
                        entry_price=pos.entry_price,
                        exit_date=date,
                        exit_price=fill_price,
                        shares=pos.shares,
                        profit=profit,
                        profit_pct=profit_pct,
                        holding_days=holding_days,
                        entry_reason=pos.entry_reason,
                        exit_reason=sig.get("reason", ""),
                    ))

            # Record daily equity
            position_value = 0.0
            for pos in positions.values():
                position_value += current_price * pos.shares

            total_equity = cash + position_value
            return_pct = (total_equity - initial_capital) / initial_capital

            if equity_curve:
                peak = max(e.total_equity for e in equity_curve)
                drawdown = (total_equity - peak) / peak if peak > 0 else 0.0
            else:
                drawdown = 0.0

            equity_curve.append(DailyEquity(
                date=date,
                cash=cash,
                position_value=position_value,
                total_equity=total_equity,
                return_pct=return_pct,
                drawdown=drawdown,
            ))

        # Close any remaining positions on last day
        if positions and trading_dates:
            last_date = trading_dates[-1]
            last_price = float(df[df["date"] == last_date].iloc[0]["close"])
            for sym, pos in list(positions.items()):
                fill_price = last_price * (1 - slippage_rate)
                amount = fill_price * pos.shares
                comm = max(amount * commission_rate, 5)
                tax = amount * stamp_tax_rate
                proceeds = amount - comm - tax
                profit = proceeds - pos.cost
                profit_pct = profit / pos.cost if pos.cost > 0 else 0
                cash += proceeds

                entry_dt = datetime.strptime(pos.entry_date, "%Y-%m-%d")
                exit_dt = datetime.strptime(last_date, "%Y-%m-%d")
                trades.append(Trade(
                    symbol=sym,
                    entry_date=pos.entry_date,
                    entry_price=pos.entry_price,
                    exit_date=last_date,
                    exit_price=fill_price,
                    shares=pos.shares,
                    profit=profit,
                    profit_pct=profit_pct,
                    holding_days=(exit_dt - entry_dt).days,
                    entry_reason=pos.entry_reason,
                    exit_reason="end_of_period",
                ))
                del positions[sym]

        metrics = self._calculate_metrics(
            equity_curve, trades, initial_capital,
            trading_dates[0] if trading_dates else "",
            trading_dates[-1] if trading_dates else "",
        )

        return {
            "metrics": metrics,
            "equity_curve": [asdict(e) for e in equity_curve],
            "trades": [asdict(t) for t in trades],
        }

    @staticmethod
    def _prepare_klines_df(klines: List[Dict]) -> pd.DataFrame:
        df = pd.DataFrame(klines)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _calculate_metrics(
        equity_curve: List[DailyEquity],
        trades: List[Trade],
        initial_capital: float,
        start_date: str,
        end_date: str,
    ) -> Dict:
        if not equity_curve:
            return {
                "total_return": 0.0,
                "annual_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_loss_ratio": 0.0,
                "avg_holding_days": 0.0,
            }

        final_equity = equity_curve[-1].total_equity
        total_return = (final_equity - initial_capital) / initial_capital

        if start_date and end_date:
            days = (datetime.strptime(end_date, "%Y-%m-%d") -
                    datetime.strptime(start_date, "%Y-%m-%d")).days
            years = max(days / 365, 1 / 365)
            annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0
        else:
            annual_return = 0.0

        max_drawdown = min((e.drawdown for e in equity_curve), default=0.0)

        daily_returns = [e.return_pct for e in equity_curve]
        daily_diffs = np.diff(daily_returns) if len(daily_returns) > 2 else [0.0]
        sharpe = (
            float(np.mean(daily_diffs) / np.std(daily_diffs) * np.sqrt(252))
            if len(daily_diffs) > 1 and np.std(daily_diffs) > 0
            else 0.0
        )

        winning = [t for t in trades if t.profit > 0]
        losing = [t for t in trades if t.profit <= 0]
        win_rate = len(winning) / len(trades) if trades else 0.0
        avg_win = sum(t.profit for t in winning) / len(winning) if winning else 0.0
        avg_loss = sum(t.profit for t in losing) / len(losing) if losing else 0.0
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        avg_holding = (
            sum(t.holding_days for t in trades) / len(trades) if trades else 0.0
        )

        return {
            "initial_capital": initial_capital,
            "final_capital": round(final_equity, 2),
            "total_return": round(total_return, 6),
            "annual_return": round(annual_return, 6),
            "max_drawdown": round(max_drawdown, 6),
            "sharpe_ratio": round(sharpe, 4),
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 4),
            "profit_loss_ratio": round(profit_loss_ratio, 4),
            "avg_holding_days": round(avg_holding, 1),
        }
