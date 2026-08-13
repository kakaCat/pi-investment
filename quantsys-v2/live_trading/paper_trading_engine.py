"""
通用模拟交易引擎 (Paper Trading Engine)

将信号转化为模拟交易，管理持仓和盈亏。
与 V13 专用 SimulationTrader 不同，本引擎支持任意策略组合。

核心职责：
1. 信号 → 风控过滤 → 仓位计算 → 模拟成交
2. 持仓管理（止损/止盈/更新市值）
3. 盈亏结算（写入 strategy_performance）
4. 多策略子账户隔离

使用方式：
    engine = PaperTradingEngine(account_name="rotation_main", initial_capital=1_000_000)
    trades = engine.execute_signals(signals)
    engine.check_stop_loss(current_prices)
    report = engine.get_performance_report()
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import structlog

from live_trading.simulation_broker import SimulationBroker
from adapters.outbound.repositories import SimulationORMRepository

logger = structlog.get_logger(__name__)


# ============================================================
# 数据结构
# ============================================================

class Signal:
    """交易信号"""

    def __init__(
        self,
        symbol: str,
        action: str,  # 'buy' | 'sell'
        strategy_id: Optional[int] = None,
        strategy_name: str = '',
        strength: float = 1.0,  # 信号强度 0-1
        price: Optional[float] = None,  # 参考价格（None则用市价）
        stop_loss_pct: float = -0.08,  # 止损比例
        take_profit_pct: float = 0.15,  # 止盈比例
        reason: str = '',
        signal_id: Optional[str] = None,
    ):
        self.symbol = symbol
        self.action = action
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.strength = strength
        self.price = price
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.reason = reason
        self.signal_id = signal_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'action': self.action,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'strength': self.strength,
            'price': self.price,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'reason': self.reason,
            'signal_id': self.signal_id,
        }


class TradeResult:
    """交易结果"""

    def __init__(
        self,
        signal: Signal,
        success: bool,
        shares: int = 0,
        filled_price: float = 0.0,
        amount: float = 0.0,
        commission: float = 0.0,
        pnl: float = 0.0,  # 卖出时的盈亏
        pnl_pct: float = 0.0,
        error: str = '',
    ):
        self.signal = signal
        self.success = success
        self.shares = shares
        self.filled_price = filled_price
        self.amount = amount
        self.commission = commission
        self.pnl = pnl
        self.pnl_pct = pnl_pct
        self.error = error
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.signal.symbol,
            'action': self.signal.action,
            'strategy_name': self.signal.strategy_name,
            'success': self.success,
            'shares': self.shares,
            'filled_price': self.filled_price,
            'amount': self.amount,
            'commission': self.commission,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'error': self.error,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# 风控配置
# ============================================================

DEFAULT_RISK_CONFIG = {
    'max_single_position_pct': 0.20,   # 单票最大仓位 20%
    'max_daily_buys': 3,               # 每日最多买入 3 只
    'max_total_position_pct': {        # 总仓位上限（按市场风格）
        'bull': 0.80,
        'bear': 0.30,
        'oscillation': 0.50,
        'default': 0.60,
    },
    'min_trade_amount': 5000,          # 最小交易金额
    'blacklist': [],                   # 黑名单
}


# ============================================================
# 核心引擎
# ============================================================

class PaperTradingEngine:
    """通用模拟交易引擎

    支持：
    - 任意策略信号执行
    - 多策略子账户隔离
    - 自动止损/止盈
    - 每日净值快照
    - 绩效报告生成
    """

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
        self.market_style = 'default'  # 当前市场风格
        self._daily_buy_count = 0
        self._daily_buy_date = None

        # 确保账户存在
        self._ensure_account()

        logger.info(
            "paper_trading_engine_initialized",
            account=account_name,
            capital=initial_capital,
        )

    # ==================== 账户管理 ====================

    def _ensure_account(self):
        """确保账户存在，不存在则创建"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            self.repo.create_account(
                account_name=self.account_name,
                initial_capital=self.initial_capital,
                display_name=f"轮转主账户",
            )
            logger.info(f"Created account: {self.account_name}")

    def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}
        return account.to_dict()

    def get_cash_available(self) -> float:
        """获取可用资金"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            return 0.0
        return float(account.cash_available or 0)

    # ==================== 信号执行 ====================

    def execute_signals(
        self,
        signals: List[Signal],
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[TradeResult]:
        """执行一批交易信号

        Args:
            signals: 信号列表
            current_prices: 当前价格 {symbol: price}，None则使用信号中的价格

        Returns:
            交易结果列表
        """
        results = []

        # 重置每日买入计数
        today = date.today()
        if self._daily_buy_date != today:
            self._daily_buy_date = today
            self._daily_buy_count = 0

        # 分离买卖信号
        buy_signals = [s for s in signals if s.action == 'BUY']  # signals 大写契约（08-13 统一）
        sell_signals = [s for s in signals if s.action == 'SELL']

        # 先执行卖出（释放资金）
        for signal in sell_signals:
            price = (current_prices or {}).get(signal.symbol) or signal.price
            result = self._execute_sell(signal, price)
            results.append(result)

        # 再执行买入（风控过滤后）
        approved_buys = self._filter_buy_signals(buy_signals, current_prices)
        for signal in approved_buys:
            price = (current_prices or {}).get(signal.symbol) or signal.price
            result = self._execute_buy(signal, price)
            results.append(result)

        # 更新账户市值
        if current_prices:
            self._update_position_values(current_prices)

        executed = sum(1 for r in results if r.success)
        logger.info(
            "signals_executed",
            total=len(signals),
            executed=executed,
            failed=len(signals) - executed,
        )

        return results

    def _filter_buy_signals(
        self,
        signals: List[Signal],
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[Signal]:
        """风控过滤买入信号"""
        approved = []
        cash = self.get_cash_available()
        account = self.repo.get_account(self.account_name)
        total_value = float(account.total_value or self.initial_capital) if account else self.initial_capital

        # 获取当前持仓
        positions = self.repo.get_all_positions(self.account_name)
        held_symbols = {p.symbol for p in positions if p.shares_total > 0}

        # 总仓位上限
        max_position_pct = self.risk_config['max_total_position_pct'].get(
            self.market_style,
            self.risk_config['max_total_position_pct']['default']
        )
        current_position_value = sum(
            float(p.market_value or 0) for p in positions
        )
        remaining_position_budget = total_value * max_position_pct - current_position_value

        for signal in signals:
            # 黑名单检查
            if signal.symbol in self.risk_config['blacklist']:
                logger.info(f"Signal rejected (blacklist): {signal.symbol}")
                continue

            # 已持仓检查（不重复买入）
            if signal.symbol in held_symbols:
                logger.info(f"Signal rejected (already held): {signal.symbol}")
                continue

            # 每日买入数量限制
            if self._daily_buy_count >= self.risk_config['max_daily_buys']:
                logger.info(f"Signal rejected (daily buy limit): {signal.symbol}")
                continue

            # 单票仓位限制
            price = (current_prices or {}).get(signal.symbol) or signal.price or 0
            if price <= 0:
                continue
            max_shares = int(total_value * self.risk_config['max_single_position_pct'] / price / 100) * 100
            if max_shares < 100:
                logger.info(f"Signal rejected (position too small): {signal.symbol}")
                continue

            # 总仓位预算检查
            estimated_cost = max_shares * price
            if estimated_cost > remaining_position_budget:
                max_shares = int(remaining_position_budget / price / 100) * 100
                if max_shares < 100:
                    logger.info(f"Signal rejected (position budget exceeded): {signal.symbol}")
                    continue

            # 可用资金检查
            if estimated_cost > cash:
                max_shares = int(cash / price / 100) * 100
                if max_shares < 100:
                    logger.info(f"Signal rejected (insufficient cash): {signal.symbol}")
                    continue

            approved.append(signal)

        # 按信号强度排序，优先执行强信号
        approved.sort(key=lambda s: s.strength, reverse=True)
        return approved

    def _execute_buy(self, signal: Signal, price: Optional[float]) -> TradeResult:
        """执行买入"""
        if price is None or price <= 0:
            return TradeResult(signal=signal, success=False, error="No valid price")

        cash = self.get_cash_available()
        account = self.repo.get_account(self.account_name)
        total_value = float(account.total_value or self.initial_capital) if account else self.initial_capital

        # 计算买入股数
        # 按信号强度调整仓位：强信号用满仓位，弱信号减半
        max_amount = total_value * self.risk_config['max_single_position_pct']
        target_amount = max_amount * signal.strength
        target_amount = min(target_amount, cash * 0.95)  # 留5%余量

        shares = int(target_amount / price / 100) * 100
        if shares < 100:
            return TradeResult(signal=signal, success=False, error="Shares too small")

        # 通过 Broker 模拟成交
        try:
            trade = self.broker.buy(signal.symbol, shares, price)
        except Exception as e:
            return TradeResult(signal=signal, success=False, error=str(e))

        filled_price = trade['filled_price']
        commission = trade['commission']
        total_cost = trade['total_cost']

        # 写入交易记录（自动写资金流水）
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

        # 更新持仓（新建或加仓）
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
                shares_available=old_shares,  # T+1: 今日买入不可卖
                current_price=filled_price,
            )
        else:
            self.repo.upsert_position(
                account_name=self.account_name,
                symbol=signal.symbol,
                shares_total=shares,
                avg_cost=filled_price,
                shares_available=0,  # T+1: 今日买入不可卖
                current_price=filled_price,
            )

        # 更新账户现金
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

        logger.info(
            "buy_executed",
            symbol=signal.symbol,
            shares=shares,
            price=filled_price,
            strategy=signal.strategy_name,
        )

        return TradeResult(
            signal=signal,
            success=True,
            shares=shares,
            filled_price=filled_price,
            amount=trade['amount'],
            commission=commission,
        )

    def _execute_sell(self, signal: Signal, price: Optional[float]) -> TradeResult:
        """执行卖出"""
        # 查找持仓
        position = self.repo.get_position(self.account_name, signal.symbol)

        if position is None or position.shares_available <= 0:
            return TradeResult(
                signal=signal, success=False,
                error=f"No available position for {signal.symbol}"
            )

        shares = position.shares_available
        avg_cost = float(position.avg_cost or 0)

        if price is None or price <= 0:
            price = float(position.current_price or avg_cost)

        # 通过 Broker 模拟成交
        try:
            trade = self.broker.sell(signal.symbol, shares, price)
        except Exception as e:
            return TradeResult(signal=signal, success=False, error=str(e))

        filled_price = trade['filled_price']
        commission = trade['commission']
        stamp_duty = trade.get('stamp_duty', 0)
        total_revenue = trade['total_revenue']

        # 计算盈亏
        pnl = (filled_price - avg_cost) * shares - commission - stamp_duty
        pnl_pct = (filled_price - avg_cost) / avg_cost if avg_cost > 0 else 0

        # 写入交易记录
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

        # 更新持仓（减仓或清仓）
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

        # 更新账户现金
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

        logger.info(
            "sell_executed",
            symbol=signal.symbol,
            shares=shares,
            price=filled_price,
            pnl=round(pnl, 2),
            pnl_pct=f"{pnl_pct:.2%}",
        )

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

    # ==================== 持仓管理 ====================

    def check_stop_loss(self, current_prices: Dict[str, float]) -> List[TradeResult]:
        """检查止损/止盈，自动触发卖出

        Args:
            current_prices: 当前价格 {symbol: price}

        Returns:
            触发的卖出交易结果
        """
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

            # 止损检查（默认 -8%）
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

            # 止盈检查（默认 +15%）
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
        """更新所有持仓的市值（批量）"""
        # 使用 repo 的批量更新方法（自动刷新账户总资产）
        self.repo.update_position_prices(self.account_name, current_prices)

    def get_current_positions(self) -> List[Dict[str, Any]]:
        """获取当前所有持仓"""
        positions = self.repo.get_all_positions(self.account_name)
        return [p.to_dict() for p in positions if p.shares_total > 0]

    # ==================== 绩效报告 ====================

    def get_performance_report(self) -> Dict[str, Any]:
        """生成绩效报告"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}

        total_value = float(account.total_value or 0)
        initial = float(account.initial_capital or self.initial_capital)
        cumulative_return = (total_value - initial) / initial if initial > 0 else 0

        positions = self.get_current_positions()
        position_value = sum(p.get('market_value', 0) for p in positions)

        # 计算今日交易
        today_str = date.today().isoformat()
        today_trades = self.repo.get_trades_by_account(
            account_name=self.account_name,
            start_date=today_str,
            end_date=today_str,
        )
        today_sells = [t for t in today_trades if t.action == 'SELL']  # action 大写契约（08-13 统一）
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
        """拍摄每日净值快照"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}

        total_value = float(account.total_value or 0)
        cash = float(account.cash_available or 0)
        position_value = float(account.position_value or 0)
        initial = float(account.initial_capital or self.initial_capital)
        cumulative_return = (total_value - initial) / initial if initial > 0 else 0

        # 计算日收益率（对比昨日快照）
        snapshots = self.repo.get_equity_snapshots(self.account_name, limit=1)
        if snapshots:
            prev_value = float(snapshots[0].total_value or 0)
            daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0
        else:
            daily_return = cumulative_return

        # 更新峰值和最大回撤
        peak = float(account.peak_value or initial)
        if total_value > peak:
            peak = total_value
        drawdown = (peak - total_value) / peak if peak > 0 else 0

        # 写入快照
        self.repo.upsert_equity_snapshot(
            account_name=self.account_name,
            cash=cash,
            position_value=position_value,
            total_value=total_value,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            drawdown=drawdown,
        )

        # 更新账户峰值和回撤
        self.repo.update_account(
            account_name=self.account_name,
            cash_available=cash,
            total_value=total_value,
            peak_value=peak,
            cumulative_return=cumulative_return,
            max_drawdown=drawdown,
            position_value=position_value,
        )

        logger.info(
            "daily_snapshot_taken",
            account=self.account_name,
            nav=round(total_value / initial, 4) if initial > 0 else 1.0,
            total_value=round(total_value, 2),
            daily_return=f"{daily_return:.4%}",
        )

        return {
            'date': date.today().isoformat(),
            'nav': round(total_value / initial, 4) if initial > 0 else 1.0,
            'total_value': round(total_value, 2),
            'daily_return': round(daily_return, 6),
            'drawdown': round(drawdown, 4),
        }

    # ==================== 市场风格 ====================

    def set_market_style(self, style: str):
        """设置当前市场风格（影响仓位上限）"""
        valid_styles = ['bull', 'bear', 'oscillation', 'default']
        if style not in valid_styles:
            style = 'default'
        self.market_style = style
        logger.info("market_style_updated", style=style)
