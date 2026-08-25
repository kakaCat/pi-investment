"""账户交易服务 —— 手工/代管交易的单事务执行

事务流: 校验 → 委托单 → 成交+费用 → 资金流水(add_trade自动) → 持仓 → 账户 → 快照
"""
import structlog
from datetime import date, datetime, time as dt_time
from typing import Dict, Optional

from domain.ports import ISimulationRepository

logger = structlog.get_logger(__name__)


class TradingError(Exception):
    def __init__(self, message: str, status_code: int = 422, details: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class AccountTradingService:
    COMMISSION_RATE = 0.00025      # 佣金万2.5
    COMMISSION_MIN = 5.0           # 最低5元
    STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
    TRANSFER_FEE_RATE = 0.00001    # 过户费
    MAX_SINGLE_POSITION_RATIO = 0.30
    MAX_TOTAL_POSITION_RATIO = 0.80
    MAX_DAILY_BUY_COUNT = 5              # 单日买入笔数上限
    MAX_DAILY_BUY_AMOUNT_RATIO = 0.50    # 单日买入金额占总资产上限
    # A股交易时段（交易日才允许成交）
    TRADING_SESSIONS = (
        (dt_time(9, 30), dt_time(11, 30)),
        (dt_time(13, 0), dt_time(15, 0)),
    )

    def __init__(self, repo: Optional[ISimulationRepository] = None, calendar=None,
                 now_fn=None):
        self.repo = repo
        if calendar is None:
            from application.services.trading_calendar_service import TradingCalendarService
            calendar = TradingCalendarService()
        self.calendar = calendar
        # 时间源可注入（测试用固定时间）；默认真实时钟
        self.now_fn = now_fn or datetime.now

    def _get_price(self, symbol: str) -> float:
        from application.services.realtime_quote_service import RealtimeQuoteService
        quote = RealtimeQuoteService().get_realtime_quote(symbol)
        if not quote or not quote.price or quote.price <= 0:
            raise TradingError(f'无法获取 {symbol} 实时价格', 502)
        return float(quote.price)

    def _check_trading_window(self, now: datetime) -> None:
        """A股交易时段护栏：只有交易日的 9:30-11:30 / 13:00-15:00 才能成交。

        非交易日或非交易时段抛 TradingError（422），
        拒绝原因返回给调用方（agent 记录后应等下一交易时段）。
        """
        day_str = now.date().isoformat()
        if not self.calendar.is_trading_day(day_str):
            raise TradingError(f'非交易日（{day_str}），A股不开市，委托拒绝', 422)
        t = now.time()
        if not any(start <= t <= end for start, end in self.TRADING_SESSIONS):
            raise TradingError(
                f'非交易时段（{t.strftime("%H:%M")}），'
                f'A股交易时段为 9:30-11:30 / 13:00-15:00，委托拒绝', 422)

    def _is_in_trading_window(self, now: datetime) -> bool:
        """复用 _check_trading_window 的判定逻辑，返回布尔而不抛异常"""
        try:
            self._check_trading_window(now)
            return True
        except TradingError:
            return False

    def _check_daily_buy_limits(
        self, account_name: str, trade_amount: float, total_value: float
    ) -> None:
        """账户级日买入限额（服务端硬护栏，防 LLM 失控）。

        超限抛 TradingError，拒绝原因会返回给调用方（agent 记录后不再重试）。
        """
        today = date.today().isoformat()
        trades = self.repo.get_trades_by_account(
            account_name, start_date=today, end_date=today)
        buys = [t for t in trades if t.action == 'BUY']  # action 大写契约（08-13 统一）
        if len(buys) >= self.MAX_DAILY_BUY_COUNT:
            raise TradingError(
                f'单日买入笔数超限: 今日已买 {len(buys)} 笔，'
                f'上限 {self.MAX_DAILY_BUY_COUNT} 笔', 422)
        bought_amount = sum(float(t.amount or 0) for t in buys)
        if (bought_amount + trade_amount) / total_value > self.MAX_DAILY_BUY_AMOUNT_RATIO:
            raise TradingError(
                f'单日买入金额超限: 今日已买 ¥{bought_amount:,.0f}，'
                f'本次 ¥{trade_amount:,.0f}，'
                f'超过总资产 {self.MAX_DAILY_BUY_AMOUNT_RATIO:.0%}', 422)

    def execute_trade(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: Optional[int] = None,
        amount: Optional[float] = None,
        price_limit: Optional[float] = None,
        reason: Optional[str] = None,
        max_positions: int = 10,
        price: Optional[float] = None,
        allow_off_hours: bool = False,
        execute_at: Optional[str] = None,
    ) -> Dict:
        # ---- 校验 ----
        if not reason or len(reason.strip()) < 10:
            raise TradingError('必须提供详细的交易理由（至少10字）', 400)
        # action 统一大写契约（2026-08-13）：入口规范化，非法值包成 400
        from infrastructure.persistence.orm.models.action_norm import normalize_action
        try:
            action = normalize_action(action)
        except ValueError:
            raise TradingError("action 必须是 'buy' 或 'sell'", 400)
        if execute_at is not None and execute_at != 'market_open':
            raise TradingError("execute_at 仅支持 'market_open'", 400)

        now = self.now_fn()
        in_window = self._is_in_trading_window(now)

        # 条件委托：非交易时段 + execute_at='market_open' → 挂单，开盘后 9:31 起撮合。
        # 仍校验账户存在且 active，但不查行情/资金/持仓——这些护栏在撮合时复核。
        if execute_at == 'market_open' and not in_window:
            account = self.repo.get_account(account_name)
            if not account:
                raise TradingError(f'账户不存在: {account_name}', 404)
            if account.status != 'active':
                raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)
            pending = self.repo.create_pending_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, amount=amount, price_limit=price_limit,
                reason=reason, execute_at='market_open')
            logger.info("pending_order_placed",
                        account=account_name, action=action, symbol=symbol,
                        pending_order_id=pending.id)
            return {
                'status': 'pending',
                'pending_order_id': pending.id,
                'message': '已挂单，开盘后 9:31 起自动撮合',
            }

        if not allow_off_hours and not in_window:
            self._check_trading_window(now)  # 抛出带具体原因的 422
        account = self.repo.get_account(account_name)
        if not account:
            raise TradingError(f'账户不存在: {account_name}', 404)
        if account.status != 'active':
            raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)

        # T+1 结转由每日任务（settle_t1）负责，不在交易路径内做——
        # 可用数由交易事务自身维护（买入当日 +0，卖出即时扣减）

        px = price if price is not None else self._get_price(symbol)
        if price_limit is not None:
            if action == 'BUY' and px > price_limit:
                raise TradingError(f'现价 {px} 高于限价 {price_limit}，委托拒绝', 422)
            if action == 'SELL' and px < price_limit:
                raise TradingError(f'现价 {px} 低于限价 {price_limit}，委托拒绝', 422)

        if shares is None:
            if not amount:
                raise TradingError('shares 与 amount 必须提供一个', 400)
            shares = int(amount // (px * 100)) * 100
            if shares <= 0:
                raise TradingError('金额不足一手（100股）', 422)
        if shares % 100 != 0:
            raise TradingError('股数必须为 100 的整数倍', 422)

        trade_amount = round(px * shares, 2)
        commission = max(round(trade_amount * self.COMMISSION_RATE, 2), self.COMMISSION_MIN)
        stamp_duty = round(trade_amount * self.STAMP_DUTY_RATE, 2) if action == 'SELL' else 0.0
        transfer_fee = round(trade_amount * self.TRANSFER_FEE_RATE, 2)

        positions = self.repo.get_all_positions(account_name)
        pos = next((p for p in positions if p.symbol == symbol), None)
        position_value = sum(
            float(p.market_value or 0) or float(p.shares_total) * float(p.current_price or p.avg_cost)
            for p in positions
        )
        total_value = float(account.cash_available) + float(account.cash_frozen) + position_value
        if total_value <= 0:
            total_value = float(account.total_value or account.initial_capital or 1)

        realized_pnl = None
        realized_pnl_rate = None
        if action == 'BUY':
            self._check_daily_buy_limits(account_name, trade_amount, total_value)
            total_cost = trade_amount + commission + transfer_fee
            if total_cost > float(account.cash_available):
                raise TradingError(
                    f'可用资金不足: 需要 ¥{total_cost:,.2f}，可用 ¥{float(account.cash_available):,.2f}', 422)
            new_mv = trade_amount + (
                (float(pos.market_value or 0) or float(pos.shares_total) * px) if pos else 0)
            if new_mv / total_value > self.MAX_SINGLE_POSITION_RATIO:
                raise TradingError(
                    f'单票仓位超限: 买入后 {symbol} 市值占比 {new_mv / total_value:.1%} > 30%', 422)
            if pos is None and len(positions) >= max_positions:
                raise TradingError(f'持仓数量超限: 已持有 {len(positions)} 只，上限 {max_positions}', 422)
            if (position_value + trade_amount) / total_value > self.MAX_TOTAL_POSITION_RATIO:
                raise TradingError('总仓位超限: 买入后超过总资产 80%', 422)
        else:
            if pos is None or pos.shares_total <= 0:
                raise TradingError(f'无 {symbol} 持仓，无法卖出', 422)
            if shares > pos.shares_available:
                raise TradingError(
                    f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                    details={'sellable_shares': pos.shares_available, 'symbol': symbol})
            cost_basis = shares * float(pos.avg_cost)
            realized_pnl = round(trade_amount - cost_basis - commission - stamp_duty - transfer_fee, 2)
            realized_pnl_rate = round(realized_pnl / cost_basis, 4) if cost_basis else 0.0

        # ---- 单事务执行 ----
        try:
            # 行级锁串行化同账户并发交易，防 lost update：
            # 锁定后 account 被刷新为数据库最新值，资金类校验必须在锁内复核
            locked_account = self.repo.get_account_for_update(account_name)
            if not locked_account:
                raise TradingError(f'账户不存在: {account_name}', 404)
            account = locked_account
            if action == 'BUY':
                total_cost_locked = trade_amount + commission + transfer_fee
                if total_cost_locked > float(account.cash_available):
                    raise TradingError(
                        f'可用资金不足(锁内复核): 需要 ¥{total_cost_locked:,.2f}'
                        f'，可用 ¥{float(account.cash_available):,.2f}', 422)

            # 锁内重读持仓：之前读取的 pos/positions 可能是并发事务提交前的旧值
            self.repo.session.expire_all()
            positions = self.repo.get_all_positions(account_name)
            pos = next((p for p in positions if p.symbol == symbol), None)
            if action == 'SELL':
                if pos is None or pos.shares_total <= 0:
                    raise TradingError(f'无 {symbol} 持仓，无法卖出', 422)
                if shares > pos.shares_available:
                    raise TradingError(
                        f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                        details={'sellable_shares': pos.shares_available, 'symbol': symbol})

            order = self.repo.create_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, price_limit=price_limit, reason=reason,
                commit=False)
            order.status = 'filled'
            order.filled_shares = shares
            order.avg_filled_price = px

            trade_id = self.repo.add_trade(
                account_name=account_name, symbol=symbol, action=action,
                shares=shares, price=px, filled_price=px, amount=trade_amount,
                commission=commission, stamp_duty=stamp_duty, transfer_fee=transfer_fee,
                total_cost=trade_amount + commission + transfer_fee if action == 'BUY' else None,
                total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'SELL' else None,
                order_id=order.id, realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

            if action == 'BUY':
                old_total = pos.shares_total if pos else 0
                old_cost = float(pos.avg_cost) * old_total if pos else 0.0
                new_total = old_total + shares
                new_avg = round((old_cost + trade_amount + commission + transfer_fee) / new_total, 4)
                self.repo.upsert_position(
                    account_name, symbol, shares_total=new_total, avg_cost=new_avg,
                    shares_available=pos.shares_available if pos else 0,  # 当日买入不可卖
                    current_price=px, commit=False)
                account.cash_available = float(account.cash_available) - (
                    trade_amount + commission + transfer_fee)
            else:
                remaining = pos.shares_total - shares
                if remaining == 0:
                    self.repo.delete_position(account_name, symbol, commit=False)
                else:
                    self.repo.upsert_position(
                        account_name, symbol, shares_total=remaining,
                        avg_cost=float(pos.avg_cost),
                        shares_available=pos.shares_available - shares,
                        current_price=px, commit=False)
                account.cash_available = float(account.cash_available) + (
                    trade_amount - commission - stamp_duty - transfer_fee)

            account.position_value = position_value + (
                trade_amount if action == 'BUY' else -trade_amount)
            account.total_value = (
                float(account.cash_available) + float(account.cash_frozen)
                + float(account.position_value))
            if account.initial_capital:
                account.cumulative_return = (
                    float(account.total_value) / float(account.initial_capital) - 1)
            if account.peak_value and float(account.total_value) > float(account.peak_value):
                account.peak_value = account.total_value

            self.repo.upsert_equity_snapshot(
                account_name,
                cash=float(account.cash_available) + float(account.cash_frozen),
                position_value=float(account.position_value),
                total_value=float(account.total_value),
                cumulative_return=float(account.cumulative_return or 0),
                drawdown=(float(account.total_value) / float(account.peak_value) - 1)
                if account.peak_value else 0.0,
                commit=False)

            self.repo.session.commit()
        except TradingError:
            self.repo.session.rollback()
            raise
        except Exception as e:
            self.repo.session.rollback()
            logger.error("trade_transaction_failed_rollback", error=str(e), exc_info=True)
            raise TradingError(f'交易执行失败: {e}', 500)

        # 成交后自动写决策审计记录：簿记下沉服务端，不再依赖 LLM 自觉调 decision_record
        self._auto_record_decision(
            account_name=account_name, action=action, symbol=symbol,
            shares=shares, price=px, amount=trade_amount,
            reason=reason, realized_pnl=realized_pnl)

        return {
            'order_id': order.id,
            'order_status': 'filled',
            'trade_id': trade_id,
            'symbol': symbol,
            'action': action.lower(),  # 对外 API 保持小写（库内大写契约不影响消费方）
            'shares': shares,
            'price': px,
            'amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'realized_pnl': realized_pnl,
            'realized_pnl_rate': realized_pnl_rate,
        }

    # ==================== 条件委托（挂单） ====================

    def _auto_record_decision(
        self, account_name: str, action: str, symbol: str,
        shares: int, price: float, amount: float,
        reason: Optional[str], realized_pnl: Optional[float],
    ) -> None:
        """成交后自动写 agent_decisions 审计记录。

        失败只记日志不影响交易结果（审计不能拖垮主链路）。
        Agent 只需在"放弃信号/不交易"时显式 decision_record——
        成交类记录由本方法保证。
        """
        try:
            from application.services.decision_service import DecisionService
            DecisionService().record_decision({
                'decision_type': f'trade_{action.lower()}',  # decision_type 小写契约（evolution 打分消费）
                'reasoning': reason or '',
                'context': {'account': account_name, 'auto_recorded': True},
                'parameters': {
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'amount': amount,
                    'realized_pnl': realized_pnl,
                },
                'related_entity_type': 'stock',
                'related_entity_id': symbol,
            })
        except Exception as e:
            logger.warning(f"auto_record_decision_failed（不影响成交）: {e}")

    def execute_pending_orders(self, now: Optional[datetime] = None) -> Dict:
        """撮合所有 pending 挂单（由 orchestrator 在开盘后 9:31 起调用）。

        每个挂单走完整 execute_trade 护栏（不带 execute_at）：
        - 成功 → status='executed' + executed_trade_id
        - 护栏拒绝（TradingError）→ status='failed' + fail_reason
        幂等：已处理的订单不再是 pending，重复调用无副作用。
        """
        now = now or self.now_fn()
        pending = self.repo.get_pending_orders(status='pending')
        executed = 0
        failed = 0
        details = []
        for po in pending:
            try:
                result = self.execute_trade(
                    account_name=po.account_name,
                    action=po.action,
                    symbol=po.symbol,
                    shares=po.shares,
                    amount=float(po.amount) if po.amount is not None else None,
                    price_limit=float(po.price_limit) if po.price_limit is not None else None,
                    reason=po.reason,
                )
                self.repo.update_pending_order_status(
                    po.id, 'executed', executed_trade_id=result['trade_id'])
                executed += 1
                details.append({
                    'pending_order_id': po.id,
                    'status': 'executed',
                    'trade_id': result['trade_id'],
                })
            except TradingError as e:
                self.repo.update_pending_order_status(
                    po.id, 'failed', fail_reason=str(e))
                failed += 1
                details.append({
                    'pending_order_id': po.id,
                    'status': 'failed',
                    'fail_reason': str(e),
                })
        if executed or failed:
            logger.info("pending_orders_matched",
                        executed=executed, failed=failed, at=now.isoformat())
        return {'executed': executed, 'failed': failed, 'details': details}

    def cancel_pending_order(self, account_name: str, order_id: int) -> Dict:
        """取消挂单（仅 pending 状态可取消）"""
        order = self.repo.get_pending_order(order_id)
        if not order or order.account_name != account_name:
            raise TradingError(f'挂单不存在: {order_id}', 404)
        if order.status != 'pending':
            raise TradingError(
                f'仅 pending 状态可取消，当前状态: {order.status}', 409)
        self.repo.update_pending_order_status(order_id, 'cancelled')
        logger.info("pending_order_cancelled",
                    account=account_name, pending_order_id=order_id)
        return {'status': 'cancelled', 'pending_order_id': order_id}
