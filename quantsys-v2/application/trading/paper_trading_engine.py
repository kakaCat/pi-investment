"""
通用模拟交易引擎 (Paper Trading Engine)

将信号转化为模拟交易，管理持仓和盈亏。
与 V13 专用 SimulationTrader 不同，本引擎支持任意策略组合。
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import structlog

from live_trading.simulation_broker import SimulationBroker
from adapters.outbound.repositories import SimulationORMRepository
from domain.trading.models.signal import Signal
from domain.trading.models.trade_result import TradeResult
from qs_trading.application.ports.fill_listener import (
    FillEvent,
    IFillListener,
    get_fill_listener,
    notify_fill,
    register_fill_listener,
    unregister_fill_listener,
)

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


# ── 成交回调端口（RFC 017 §2.1.4 / REQ-261021194640-69b8 IF-1、IF-2）─────────
#
# 端口本体已迁到**交易包中立侧**，本文件只保留同名导出做兼容转发（旧 import 不破）：
#   `qs_trading.application.ports.fill_listener` —— FillEvent / IFillListener /
#   register/get/unregister / notify_fill 的唯一实现处。
#
# 依赖方向不可倒：`qs_watch → qs_trading` 是已声明的单向依赖，反向不存在。
# 所以 trading 侧只提供薄端口 + 模块级注册位，绝不 import watch。
# 唯一填报点仍是成交**落库之后**（`_notify_fill`，被 `_execute_buy/_execute_sell`
# 各调一行）：现在改调 `notify_fill`——它自吞监听者异常、未注册返回 False，
# **失败只记日志，绝不影响成交落库**。
#
# 转发清单（`from application.trading.paper_trading_engine import X` 全部等价）：
#   FillEvent · IFillListener · register_fill_listener · get_fill_listener ·
#   unregister_fill_listener
# 本模块不设 __all__：改造前就没有，保持模块命名空间与旧行为逐字一致。


class PaperTradingEngine:
    """通用模拟交易引擎"""

    def __init__(
        self,
        account_name: str = 'rotation_main',
        initial_capital: float = 1_000_000,
        risk_config: Optional[Dict] = None,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.001,
        fill_listener: Optional[IFillListener] = None,
    ):
        self.account_name = account_name
        self.initial_capital = initial_capital
        self.risk_config = {**DEFAULT_RISK_CONFIG, **(risk_config or {})}
        self.broker = SimulationBroker(commission_rate, slippage_rate)
        self.repo = SimulationORMRepository()
        #: 成交回调（可选注入；缺省跟随组合根注册的模块级监听器，见 `_notify_fill`）
        self._fill_listener = fill_listener
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

    def _notify_fill(self, *, signal: Signal, action: str, shares: int,
                     filled_price: float, trade_id: Optional[int],
                     order_id: Optional[int] = None) -> None:
        """成交落库后的**单行回调**（RFC 017 §2.1.4 / IF-2）。

        派发本身交给中立侧端口 `notify_fill`（唯一出口）；本方法只负责
        「把成交事实投影成 FillEvent」这一件事。

        纪律（逐条对应验收「回调失败不影响成交落库」）：
          · 只在 `trade_id` 非空时回调——没有落库的成交不是事实，绝不虚报；
          · 监听器缺失 = no-op（未装配时成交路径与改造前逐字一致）；
          · 任何异常只记日志，**绝不向上抛**（成交已经提交，回执是旁路增益）——
            由 `notify_fill` 统一兜住，本方法不再自建 try/except；
          · 以成交来源（signal.strategy_name）作 `source`：watch 指令 / 盘中止损 /
            人工……**任何来源**的成交都同一条事实，消费侧一视同仁地收敛。
        """
        if trade_id is None:
            return
        event = FillEvent(
            account_name=self.account_name,
            symbol=str(getattr(signal, 'symbol', '') or ''),
            action=str(action or '').lower(),
            shares=int(shares),
            price=float(filled_price),
            trade_id=trade_id,
            order_id=order_id,
            filled_at=datetime.now(),
            source=str(getattr(signal, 'strategy_name', None) or 'paper_trading'),
            reason=getattr(signal, 'reason', None),
        )
        # 实例级监听器优先，缺省回落模块级注册位（口径与改造前一致）
        notify_fill(event, listener=getattr(self, '_fill_listener', None))

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
        # 2026-10-20 修复批量执行下风控失效的三处：
        # ① 先按强度排序再过滤，限额给最强信号（原来是过滤完才排序）；
        # ② 每日买入笔数上限计入本批已批准数（原只查 _daily_buy_count，
        #    执行在过滤后才递增，同批信号全部穿透，实测一批 8 笔/上限 3）；
        # ③ 现金与总仓位预算在批内逐笔扣减（原每条信号都看到全额预算，
        #    批总量可数倍于预算）。
        signals = sorted(signals, key=lambda s: s.strength or 0, reverse=True)
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

            if self._daily_buy_count + len(approved) >= self.risk_config['max_daily_buys']:
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

            if max_shares * price > cash:
                max_shares = int(cash / price / 100) * 100
                if max_shares < 100:
                    logger.info(f"Signal rejected (insufficient cash): {signal.symbol}")
                    continue

            # 风控批下来的股数上限随信号下达执行层（_execute_buy 必须遵守）
            signal.approved_shares = max_shares
            approved.append(signal)
            # 批内预占：后续信号看到扣减后的现金与预算
            reserved = max_shares * price
            cash -= reserved
            remaining_position_budget -= reserved

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
        # 执行层遵守风控批下来的股数上限（_filter_buy_signals 写入；
        # 无该属性 = 未经过滤层直连调用，保持原行为）
        approved_cap = getattr(signal, 'approved_shares', None)
        if approved_cap is not None:
            shares = min(shares, int(approved_cap))
        if shares < 100:
            return TradeResult(signal=signal, success=False, error="Shares too small")

        try:
            trade = self.broker.buy(signal.symbol, shares, price)
        except Exception as e:
            return TradeResult(signal=signal, success=False, error=str(e))

        filled_price = trade['filled_price']
        commission = trade['commission']
        total_cost = trade['total_cost']

        trade_id = self.repo.add_trade(
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
        # 2026-10-20 修复：买入后 total_value/position_value 必须计入新仓市值。
        # 旧实现 total_value = new_cash + 旧 position_value，买入瞬间净值凭空
        # 缩水 ~total_cost，直到下次 update_position_prices 才自愈（盘中读数偏低）。
        old_position_value = float(account.position_value or 0) if account else 0.0
        new_position_value = old_position_value + filled_price * shares
        self.repo.update_account(
            account_name=self.account_name,
            cash_available=new_cash,
            total_value=new_cash + new_position_value,
            peak_value=float(account.peak_value or self.initial_capital) if account else self.initial_capital,
            cumulative_return=float(account.cumulative_return or 0) if account else 0,
            max_drawdown=float(account.max_drawdown or 0) if account else 0,
            position_value=new_position_value,
        )

        self._daily_buy_count += 1

        # 成交落库后的单行回执（RFC 017 §2.1.4）：trading → watch 的唯一单向回调
        self._notify_fill(signal=signal, action='buy', shares=shares,
                          filled_price=filled_price, trade_id=trade_id)

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

        trade_id = self.repo.add_trade(
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

        # 成交落库后的单行回执（RFC 017 §2.1.4）：清仓/部分成交由消费侧按持仓真值判定，
        # trading 只如实上报「卖了什么、成交多少」——不在交易侧推断 watch 的收敛结果。
        self._notify_fill(signal=signal, action='sell', shares=shares,
                          filled_price=filled_price, trade_id=trade_id)

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

    def _stop_loss_threshold(self, symbol: str) -> float:
        """止损阈值（负数口径）：risk_config['stop_loss_pct_fn']（按标的分级，
        如宪法口径创业板/科创板 -10%、其余 -8%，函数返回正数幅度）优先；
        缺省回落到标量 risk_config['stop_loss_pct']（行为不变，全市场 -8%）"""
        stop_loss_fn = self.risk_config.get('stop_loss_pct_fn')
        if callable(stop_loss_fn):
            return -abs(float(stop_loss_fn(symbol)))
        return self.risk_config.get('stop_loss_pct', -0.08)

    def evaluate_stop_loss(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """只评估止损/止盈触发，**绝不下单**（alert-only 账户用，如 user_main_simulation：
        处置权在用户，系统自动卖单 = 越权，只能产出告警请用户裁定）。

        Returns:
            [{'symbol', 'type': 'stop_loss'|'take_profit', 'pnl_pct', 'threshold',
              'avg_cost', 'current_price', 'shares_available'}]
        """
        triggers = []
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

            stop_loss_threshold = self._stop_loss_threshold(symbol)
            if pnl_pct <= stop_loss_threshold:
                triggers.append({
                    'symbol': symbol,
                    'type': 'stop_loss',
                    'pnl_pct': round(pnl_pct, 4),
                    'threshold': stop_loss_threshold,
                    'avg_cost': avg_cost,
                    'current_price': current_price,
                    'shares_available': int(position.shares_available),
                })
                continue

            take_profit_threshold = self.risk_config.get('take_profit_pct', 0.15)
            if pnl_pct >= take_profit_threshold:
                triggers.append({
                    'symbol': symbol,
                    'type': 'take_profit',
                    'pnl_pct': round(pnl_pct, 4),
                    'threshold': take_profit_threshold,
                    'avg_cost': avg_cost,
                    'current_price': current_price,
                    'shares_available': int(position.shares_available),
                })

        return triggers

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

            stop_loss_threshold = self._stop_loss_threshold(symbol)
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

        # 日收益率不再在此自算（2026-09-11, w-8f2c4cc5）：旧实现取「最近一条快照」当基准，而该条
        # 可能是当日自己 09:31 的早盘快照（估值残缺），2026-07-27 因此写出 +24.08% 假日收益
        # （真实 +0.72%），污染 sharpe/vol/max_drawdown 与 M4 熔断。现统一交给
        # repo.upsert_equity_snapshot 按上一交易日有效快照计算，再用返回值回填本方法的输出。

        peak = float(account.peak_value or initial)
        if total_value > peak:
            peak = total_value
        # 当日回撤统一为负号口径（旧实现取正号 peak-total，与快照/risk_metrics 的负号峰谷口径相反）
        day_drawdown = (total_value / peak - 1.0) if peak > 0 else 0.0

        snap = self.repo.upsert_equity_snapshot(
            account_name=self.account_name,
            cash=cash,
            position_value=position_value,
            total_value=total_value,
            cumulative_return=cumulative_return,
            drawdown=day_drawdown,
        )
        daily_return = (
            float(snap.daily_return)
            if snap is not None and getattr(snap, 'daily_return', None) is not None
            else None
        )

        # 账户表写「峰谷最大回撤」（唯一真源=净值序列），不再写当日回撤——
        # 旧实现在此写当日回撤且取正号，导致 simulation_account.max_drawdown = +0.0043
        # 与 risk_metrics 的 -1.83% 符号语义全不一致（2026-09-11, w-8f2c4cc5）。
        max_drawdown = self.repo.recompute_account_max_drawdown(self.account_name)
        if max_drawdown is None:
            max_drawdown = min(day_drawdown, float(account.max_drawdown or 0))

        self.repo.update_account(
            account_name=self.account_name,
            cash_available=cash,
            total_value=total_value,
            peak_value=peak,
            cumulative_return=cumulative_return,
            max_drawdown=max_drawdown,
            position_value=position_value,
        )

        logger.info("daily_snapshot_taken", account=self.account_name, nav=round(total_value / initial, 4) if initial > 0 else 1.0, total_value=round(total_value, 2), daily_return=(f"{daily_return:.4%}" if daily_return is not None else None))

        return {
            'date': date.today().isoformat(),
            'nav': round(total_value / initial, 4) if initial > 0 else 1.0,
            'total_value': round(total_value, 2),
            'daily_return': round(daily_return, 6) if daily_return is not None else None,
            'drawdown': round(day_drawdown, 4),          # 当日回撤（负号）
            'max_drawdown': round(max_drawdown, 4),      # 峰谷最大回撤（负号，与 risk_metrics 同口径）
        }

    def set_market_style(self, style: str):
        valid_styles = ['bull', 'bear', 'oscillation', 'default']
        if style not in valid_styles:
            style = 'default'
        self.market_style = style
        logger.info("market_style_updated", style=style)
