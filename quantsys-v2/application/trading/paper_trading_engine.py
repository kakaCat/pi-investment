"""
通用模拟交易引擎 (Paper Trading Engine)

将信号转化为模拟交易，管理持仓和盈亏。
与 V13 专用 SimulationTrader 不同，本引擎支持任意策略组合。
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import structlog

from live_trading.simulation_broker import SimulationBroker
from adapters.outbound.repositories import SimulationORMRepository
from domain.trading.models.signal import Signal
from domain.trading.models.trade_result import TradeResult

logger = structlog.get_logger(__name__)

DEFAULT_RISK_CONFIG = {
    'max_single_position_pct': 0.20,
    'max_daily_buys': 3,
    'max_total_position_pct': {
        'bull': 0.80,
        'bear': 0.30,
        'oscillation': 0.50,
        'default': 0.60,
    },
    'min_trade_amount': 5000,
    'blacklist': [],
}


class PaperTradingEngine:
    """通用模拟交易引擎"""

    def __init__(
        self,
        account_name: str = 'rotation_main',
        initial_capital: float = 1_000_000,
        risk_config: Optional[Dict] = None,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.001,
    ):
        self.account_name = account_name
        self.initial_capital = initial_capital
        self.risk_config = {**DEFAULT_RISK_CONFIG, **(risk_config or {})}
        self.broker = SimulationBroker(commission_rate, slippage_rate)
        self.repo = SimulationORMRepository()
        self.market_style = 'default'
        self._daily_buy_count = 0
        self._daily_buy_date = None
        self._ensure_account()
        logger.info("paper_trading_engine_initialized", account=account_name, capital=initial_capital)

    def _ensure_account(self):
        account = self.repo.get_account(self.account_name)
        if account is None:
            self.repo.create_account(
                account_name=self.account_name,
                initial_capital=self.initial_capital,
                display_name=f"轮转主账户",
            )
            logger.info(f"Created account: {self.account_name}")

    def get_account_info(self) -> Dict[str, Any]:
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}
        return account.to_dict()

    def get_cash_available(self) -> float:
        account = self.repo.get_account(self.account_name)
        if account is None:
            return 0.0
        return float(account.cash_available or 0)

    def execute_signals(
        self,
        signals: List[Signal],
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[TradeResult]:
        results = []
        today = date.today()
        if self._daily_buy_date != today:
            self._daily_buy_date = today
            self._daily_buy_count = 0

        buy_signals = [s for s in signals if s.action == 'BUY']
        sell_signals = [s for s in signals if s.action == 'SELL']

        for signal in sell_signals:
            price = (current_prices or {}).get(signal.symbol) or signal.price
            result = self._execute_sell(signal, price)
            results.append(result)

        approved_buys = self._filter_buy_signals(buy_signals, current_prices)
        for signal in approved_buys:
            price = (current_prices or {}).get(signal.symbol) or signal.price
            result = self._execute_buy(signal, price)
            results.append(result)

        if current_prices:
            self._update_position_values(current_prices)

        executed = sum(1 for r in results if r.success)
        logger.info("signals_executed", total=len(signals), executed=executed, failed=len(signals) - executed)
        return results

    def _filter_buy_signals(
        self,
        signals: List[Signal],
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[Signal]:
        approved = []
        cash = self.get_cash_available()
        account = self.repo.get_account(self.account_name)
        total_value = float(account.total_value or self.initial_capital) if account else self.initial_capital

        positions = self.repo.get_all_positions(self.account_name)
        held_symbols = {p.symbol for p in positions if p.shares_total > 0}

        max_position_pct = self.risk_config['max_total_position_pct'].get(
            self.market_style,
            self.risk_config['max_total_position_pct']['default']
        )
        current_position_value = sum(float(p.market_value or 0) for p in positions)
        remaining_position_budget = total_value * max_position_pct - current_position_value

        for signal in signals:
            if signal.symbol in self.risk_config['blacklist']:
                logger.info(f"Signal rejected (blacklist): {signal.symbol}")
                continue

            if signal.symbol in held_symbols:
                logger.info(f"Signal rejected (already held): {signal.symbol}")
                continue

            if self._daily_buy_count >= self.risk_config['max_daily_buys']:
                logger.info(f"Signal rejected (daily buy limit): {signal.symbol}")
                continue

            price = (current_prices or {}).get(signal.symbol) or signal.price or 0
            if price <= 0:
                continue
            max_shares = int(total_value * self.risk_config['max_single_position_pct'] / price / 100) * 100
            if max_shares < 100:
                logger.info(f"Signal rejected (position too small): {signal.symbol}")
                continue

            estimated_cost = max_shares * price
            if estimated_cost > remaining_position_budget:
                max_shares = int(remaining_position_budget / price / 100) * 100
                if max_shares < 100:
                    logger.info(f"Signal rejected (position budget exceeded): {signal.symbol}")
                    continue

            if estimated_cost > cash:
                max_shares = int(cash / price / 100) * 100
                if max_shares < 100:
                    logger.info(f"Signal rejected (insufficient cash): {signal.symbol}")
                    continue

            approved.append(signal)

        approved.sort(key=lambda s: s.strength, reverse=True)
        return approved

    def _execute_buy(self, signal: Signal, price: Optional[float]) -> TradeResult:
        if price is None or price <= 0:
            return TradeResult(signal=signal, success=False, error="No valid price")

        cash = self.get_cash_available()
        account = self.repo.get_account(self.account_name)
        total_value = float(account.total_value or self.initial_capital) if account else self.initial_capital

        max_amount = total_value * self.risk_config['max_single_position_pct']
        target_amount = max_amount * signal.strength
        target_amount = min(target_amount, cash * 0.95)

        shares = int(target_amount / price / 100) * 100
        if shares < 100:
            return TradeResult(signal=signal, success=False, error="Shares too small")

        try:
            trade = self.broker.buy(signal.symbol, shares, price)
        except Exception as e:
            return TradeResult(signal=signal, success=False, error=str(e))

        filled_price = trade['filled_price']
        commission = trade['commission']
        total_cost = trade['total_cost']

        self.repo.add_trade(
            account_name=self.account_name,
            symbol=signal.symbol,
            action='buy',
            shares=shares,
            price=price,
            filled_price=filled_price,
            amount=trade['amount'],
            commission=commission,
            total_cost=total_cost,
            reason=f"{signal.strategy_name}: {signal.reason}" if signal.reason else signal.strategy_name,
        )

        existing = self.repo.get_position(self.account_name, signal.symbol)
        if existing and existing.shares_total > 0:
            old_shares = existing.shares_total
            old_cost = float(existing.avg_cost or 0) * old_shares
            new_shares = old_shares + shares
            new_avg_cost = (old_cost + filled_price * shares) / new_shares
            self.repo.upsert_position(
                account_name=self.account_name,
                symbol=signal.symbol,
                shares_total=new_shares,
                avg_cost=new_avg_cost,
                shares_available=old_shares,
                current_price=filled_price,
            )
        else:
            self.repo.upsert_position(
                account_name=self.account_name,
                symbol=signal.symbol,
                shares_total=shares,
                avg_cost=filled_price,
                shares_available=0,
                current_price=filled_price,
            )

        new_cash = cash - total_cost
        self.repo.update_account(
            account_name=self.account_name,
            cash_available=new_cash,
            total_value=new_cash + float(account.position_value or 0) if account else new_cash,
            peak_value=float(account.peak_value or self.initial_capital) if account else self.initial_capital,
            cumulative_return=float(account.cumulative_return or 0) if account else 0,
            max_drawdown=float(account.max_drawdown or 0) if account else 0,
        )

        self._daily_buy_count += 1

        logger.info("buy_executed", symbol=signal.symbol, shares=shares, price=filled_price, strategy=signal.strategy_name)

        return TradeResult(
            signal=signal,
            success=True,
            shares=shares,
            filled_price=filled_price,
            amount=trade['amount'],
            commission=commission,
        )

    def _execute_sell(self, signal: Signal, price: Optional[float]) -> TradeResult:
        position = self.repo.get_position(self.account_name, signal.symbol)

        if position is None or position.shares_available <= 0:
            return TradeResult(signal=signal, success=False, error=f"No available position for {signal.symbol}")

        shares = position.shares_available
        avg_cost = float(position.avg_cost or 0)

        if price is None or price <= 0:
            price = float(position.current_price or avg_cost)

        try:
            trade = self.broker.sell(signal.symbol, shares, price)
        except Exception as e:
            return TradeResult(signal=signal, success=False, error=str(e))

        filled_price = trade['filled_price']
        commission = trade['commission']
        stamp_duty = trade.get('stamp_duty', 0)
        total_revenue = trade['total_revenue']

        pnl = (filled_price - avg_cost) * shares - commission - stamp_duty
        pnl_pct = (filled_price - avg_cost) / avg_cost if avg_cost > 0 else 0

        self.repo.add_trade(
            account_name=self.account_name,
            symbol=signal.symbol,
            action='sell',
            shares=shares,
            price=price,
            filled_price=filled_price,
            amount=trade['amount'],
            commission=commission,
            stamp_duty=stamp_duty,
            total_revenue=total_revenue,
            realized_pnl=pnl,
            realized_pnl_rate=pnl_pct,
            reason=f"{signal.strategy_name}: {signal.reason}" if signal.reason else signal.strategy_name,
        )

        remaining = position.shares_total - shares
        if remaining <= 0:
            self.repo.upsert_position(
                account_name=self.account_name,
                symbol=signal.symbol,
                shares_total=0,
                avg_cost=0,
                shares_available=0,
                current_price=filled_price,
            )
        else:
            self.repo.upsert_position(
                account_name=self.account_name,
                symbol=signal.symbol,
                shares_total=remaining,
                avg_cost=avg_cost,
                shares_available=remaining,
                current_price=filled_price,
            )

        account = self.repo.get_account(self.account_name)
        if account:
            new_cash = float(account.cash_available or 0) + total_revenue
            position_value = float(account.position_value or 0) - (shares * filled_price)
            position_value = max(position_value, 0)
            self.repo.update_account(
                account_name=self.account_name,
                cash_available=new_cash,
                total_value=new_cash + position_value,
                peak_value=float(account.peak_value or 0),
                cumulative_return=float(account.cumulative_return or 0),
                max_drawdown=float(account.max_drawdown or 0),
                position_value=position_value,
            )

        logger.info("sell_executed", symbol=signal.symbol, shares=shares, price=filled_price, pnl=round(pnl, 2), pnl_pct=f"{pnl_pct:.2%}")

        return TradeResult(
            signal=signal,
            success=True,
            shares=shares,
            filled_price=filled_price,
            amount=trade['amount'],
            commission=commission,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )

    def check_stop_loss(self, current_prices: Dict[str, float]) -> List[TradeResult]:
        results = []
        positions = self.repo.get_all_positions(self.account_name)

        for position in positions:
            if position.shares_available <= 0:
                continue

            symbol = position.symbol
            current_price = current_prices.get(symbol)
            if current_price is None:
                continue

            avg_cost = float(position.avg_cost or 0)
            if avg_cost <= 0:
                continue

            pnl_pct = (current_price - avg_cost) / avg_cost

            stop_loss_threshold = self.risk_config.get('stop_loss_pct', -0.08)
            if pnl_pct <= stop_loss_threshold:
                signal = Signal(
                    symbol=symbol,
                    action='sell',
                    strategy_name='stop_loss',
                    reason=f"止损触发: {pnl_pct:.2%} <= {stop_loss_threshold:.2%}",
                )
                result = self._execute_sell(signal, current_price)
                results.append(result)
                continue

            take_profit_threshold = self.risk_config.get('take_profit_pct', 0.15)
            if pnl_pct >= take_profit_threshold:
                signal = Signal(
                    symbol=symbol,
                    action='sell',
                    strategy_name='take_profit',
                    reason=f"止盈触发: {pnl_pct:.2%} >= {take_profit_threshold:.2%}",
                )
                result = self._execute_sell(signal, current_price)
                results.append(result)

        if results:
            logger.info("stop_loss_check", triggered=len(results))

        return results

    def _update_position_values(self, current_prices: Dict[str, float]):
        self.repo.update_position_prices(self.account_name, current_prices)

    def get_current_positions(self) -> List[Dict[str, Any]]:
        positions = self.repo.get_all_positions(self.account_name)
        return [p.to_dict() for p in positions if p.shares_total > 0]

    def get_performance_report(self) -> Dict[str, Any]:
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}

        total_value = float(account.total_value or 0)
        initial = float(account.initial_capital or self.initial_capital)
        cumulative_return = (total_value - initial) / initial if initial > 0 else 0

        positions = self.get_current_positions()
        position_value = sum(p.get('market_value', 0) for p in positions)

        today_str = date.today().isoformat()
        today_trades = self.repo.get_trades_by_account(
            account_name=self.account_name,
            start_date=today_str,
            end_date=today_str,
        )
        today_sells = [t for t in today_trades if t.action == 'SELL']
        today_pnl = sum(float(t.realized_pnl or 0) for t in today_sells)

        return {
            'account_name': self.account_name,
            'date': today_str,
            'initial_capital': initial,
            'total_value': total_value,
            'cash_available': float(account.cash_available or 0),
            'position_value': position_value,
            'cumulative_return': round(cumulative_return, 4),
            'cumulative_return_pct': f"{cumulative_return:.2%}",
            'max_drawdown': float(account.max_drawdown or 0),
            'today_pnl': round(today_pnl, 2),
            'today_trades': len(today_trades),
            'open_positions': len(positions),
            'positions': positions,
        }

    def take_daily_snapshot(self) -> Dict[str, Any]:
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}

        total_value = float(account.total_value or 0)
        cash = float(account.cash_available or 0)
        position_value = float(account.position_value or 0)
        initial = float(account.initial_capital or self.initial_capital)
        cumulative_return = (total_value - initial) / initial if initial > 0 else 0

        snapshots = self.repo.get_equity_snapshots(self.account_name, limit=1)
        if snapshots:
            prev_value = float(snapshots[0].total_value or 0)
            daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0
        else:
            daily_return = cumulative_return

        peak = float(account.peak_value or initial)
        if total_value > peak:
            peak = total_value
        drawdown = (peak - total_value) / peak if peak > 0 else 0

        self.repo.upsert_equity_snapshot(
            account_name=self.account_name,
            cash=cash,
            position_value=position_value,
            total_value=total_value,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            drawdown=drawdown,
        )

        self.repo.update_account(
            account_name=self.account_name,
            cash_available=cash,
            total_value=total_value,
            peak_value=peak,
            cumulative_return=cumulative_return,
            max_drawdown=drawdown,
            position_value=position_value,
        )

        logger.info("daily_snapshot_taken", account=self.account_name, nav=round(total_value / initial, 4) if initial > 0 else 1.0, total_value=round(total_value, 2), daily_return=f"{daily_return:.4%}")

        return {
            'date': date.today().isoformat(),
            'nav': round(total_value / initial, 4) if initial > 0 else 1.0,
            'total_value': round(total_value, 2),
            'daily_return': round(daily_return, 6),
            'drawdown': round(drawdown, 4),
        }

    def set_market_style(self, style: str):
        valid_styles = ['bull', 'bear', 'oscillation', 'default']
        if style not in valid_styles:
            style = 'default'
        self.market_style = style
        logger.info("market_style_updated", style=style)
