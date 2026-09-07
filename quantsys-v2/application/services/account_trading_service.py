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
        allow_duplicate: bool = False,
    ) -> Dict:
        """
        重构版交易执行（使用 TradeGuardService）

        重构说明（2026-09-01）:
            引入 TradeGuardService 进行锁外预检查，所有业务规则集中在领域层。
            保留应用层事务管理、行级锁和锁内复核（防 TOCTOU）。

            参考文档: docs/work-logs/2026-09/account-trading-service-refactor-final-report.md

        职责划分:
            - 领域层 (TradeGuardService): 所有业务规则校验
            - 应用层 (本方法): 事务管理、行级锁、锁内复核

        Args:
            account_name: 账户名
            action: 交易方向 ('buy'/'sell')
            symbol: 股票代码
            shares: 股数（与 amount 二选一）
            amount: 金额（与 shares 二选一）
            price_limit: 限价
            reason: 交易理由（必填，至少10字）
            max_positions: 持仓数量上限
            price: 指定价格（None 则获取实时价）
            allow_off_hours: 是否允许盘后交易
            execute_at: 执行时机 ('market_open' = 挂单)
            allow_duplicate: 重复挂单确认标记（2026-09-03）。默认 False：
                挂单时若已存在同标的同方向的 pending 单 → 409 拦截，
                调用方确认无误后设 True 重发才放行。

        Returns:
            交易结果字典
        """
        # ---- 1. 参数校验和标准化 ----
        if not reason or len(reason.strip()) < 10:
            raise TradingError('必须提供详细的交易理由（至少10字）', 400)

        from infrastructure.persistence.orm.models.action_norm import normalize_action
        try:
            action = normalize_action(action)
        except ValueError:
            raise TradingError("action 必须是 'buy' 或 'sell'", 400)

        if execute_at is not None and execute_at != 'market_open':
            raise TradingError("execute_at 仅支持 'market_open'", 400)

        now = self.now_fn()

        # ---- 2. 挂单处理 ----
        if execute_at == 'market_open' and not self._is_in_trading_window(now):
            account = self.repo.get_account(account_name)
            if not account:
                raise TradingError(f'账户不存在: {account_name}', 404)
            if account.status != 'active':
                raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)

            # ---- 2.1 重复挂单拦截（2026-09-03，防双重成交）----
            # 背景：002241 曾出现凌晨限价单+盘前市价单两笔相同 SELL 300 股 pending，
            # 若双双撮合 = 意外清仓。同标的同方向已有 pending 单时默认拦截，
            # 调用方（agent）确认后设 allow_duplicate=True 重发才放行。
            if not allow_duplicate:
                existing = self.repo.get_pending_orders(
                    account_name=account_name, status='pending') or []
                conflicts = [
                    o for o in existing
                    if getattr(o, 'symbol', None) == symbol
                    and str(getattr(o, 'action', '')).upper() == action
                ]
                if conflicts:
                    desc = '；'.join(
                        f"id={o.id} {o.action} {o.symbol} "
                        f"{o.shares if o.shares is not None else '-'}"
                        f"股{'/金额' + str(o.amount) if o.amount else ''}"
                        f"{'(限价' + str(o.price_limit) + ')' if o.price_limit is not None else '(市价)'}"
                        for o in conflicts)
                    raise TradingError(
                        f'检测到 {len(conflicts)} 笔同标的同方向 pending 挂单：{desc}。'
                        f'如确认仍要重复挂单，请设 allow_duplicate=true 重发；'
                        f'如要替换原单，请先调用 cancel 撤销后再挂。',
                        409,
                        details={
                            'conflicts': [
                                o.to_dict() if hasattr(o, 'to_dict') else {
                                    'id': getattr(o, 'id', None),
                                    'symbol': getattr(o, 'symbol', None),
                                    'action': getattr(o, 'action', None),
                                    'shares': getattr(o, 'shares', None),
                                    'price_limit': getattr(o, 'price_limit', None),
                                }
                                for o in conflicts
                            ],
                            'hint': 'allow_duplicate=true 放行；或先 cancel 原挂单再挂新单',
                        })

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

        # ---- 3. 获取价格 ----
        px = price if price is not None else self._get_price(symbol)

        # 价格限制校验
        if price_limit is not None:
            if action == 'BUY' and px > price_limit:
                raise TradingError(f'现价 {px} 高于限价 {price_limit}，委托拒绝', 422)
            if action == 'SELL' and px < price_limit:
                raise TradingError(f'现价 {px} 低于限价 {price_limit}，委托拒绝', 422)

        # 计算股数
        if shares is None:
            if not amount:
                raise TradingError('shares 与 amount 必须提供一个', 400)
            shares = int(amount // (px * 100)) * 100
            if shares <= 0:
                raise TradingError('金额不足一手（100股）', 422)

        if shares % 100 != 0:
            raise TradingError('股数必须为 100 的整数倍', 422)

        # ---- 4. 交易护栏 - 锁外预检查（领域层）----
        from domain.trading.services.trade_guard_service import TradeGuardService

        trade_guard = TradeGuardService(
            repo=self.repo,
            calendar=self.calendar,
            now_fn=self.now_fn
        )

        # 所有业务规则在这里校验：交易时段、限额、资金、持仓、仓位
        fees_info = trade_guard.validate_trade_request(
            account_name=account_name,
            action=action,
            symbol=symbol,
            shares=shares,
            price=px,
            max_positions=max_positions,
            allow_off_hours=allow_off_hours
        )

        # 提取费用信息
        trade_amount = fees_info['trade_amount']
        commission = fees_info['commission']
        stamp_duty = fees_info.get('stamp_duty', 0.0)
        transfer_fee = fees_info['transfer_fee']
        realized_pnl = fees_info.get('realized_pnl')
        realized_pnl_rate = fees_info.get('realized_pnl_rate')

        # ---- 5. 事务执行 ----
        try:
            # 行级锁串行化同账户并发交易，防 lost update
            locked_account = self.repo.get_account_for_update(account_name)
            if not locked_account:
                raise TradingError(f'账户不存在: {account_name}', 404)

            # 锁内复核资金（防 TOCTOU）
            if action == 'BUY':
                total_cost = fees_info['total_cost']
                if total_cost > float(locked_account.cash_available):
                    raise TradingError(
                        f'可用资金不足(锁内复核): 需要 ¥{total_cost:,.2f}'
                        f'，可用 ¥{float(locked_account.cash_available):,.2f}', 422)

            # 锁内重读持仓（防并发）
            self.repo.session.expire_all()
            positions = self.repo.get_all_positions(account_name)
            pos = next((p for p in positions if p.symbol == symbol), None)

            # 锁内复核持仓（防 TOCTOU）
            if action == 'SELL':
                if pos is None or pos.shares_total <= 0:
                    raise TradingError(f'无 {symbol} 持仓，无法卖出', 422)
                if shares > pos.shares_available:
                    raise TradingError(
                        f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                        details={'sellable_shares': pos.shares_available, 'symbol': symbol})

            # ---- 6. 创建订单并标记已成交 ----
            order = self.repo.create_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, price_limit=price_limit, reason=reason,
                commit=False)

            order.status = 'filled'
            order.filled_shares = shares
            order.avg_filled_price = px

            # ---- 7. 创建成交记录 ----
            trade_id = self.repo.add_trade(
                account_name=account_name, symbol=symbol, action=action,
                shares=shares, price=px, filled_price=px, amount=trade_amount,
                commission=commission, stamp_duty=stamp_duty, transfer_fee=transfer_fee,
                total_cost=trade_amount + commission + transfer_fee if action == 'BUY' else None,
                total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'SELL' else None,
                order_id=order.id, realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

            # ---- 8. 更新持仓 ----
            if action == 'BUY':
                old_total = pos.shares_total if pos else 0
                old_cost = float(pos.avg_cost) * old_total if pos else 0.0
                new_total = old_total + shares
                new_avg = round((old_cost + trade_amount + commission + transfer_fee) / new_total, 4)

                self.repo.upsert_position(
                    account_name, symbol, shares_total=new_total, avg_cost=new_avg,
                    shares_available=pos.shares_available if pos else 0,  # T+1
                    current_price=px, commit=False)

                # 扣减资金
                locked_account.cash_available = float(locked_account.cash_available) - (
                    trade_amount + commission + transfer_fee)
            else:  # SELL
                remaining = pos.shares_total - shares
                if remaining == 0:
                    self.repo.delete_position(account_name, symbol, commit=False)
                else:
                    self.repo.upsert_position(
                        account_name, symbol, shares_total=remaining,
                        avg_cost=float(pos.avg_cost),
                        shares_available=pos.shares_available - shares,
                        current_price=px, commit=False)

                # 增加资金
                locked_account.cash_available = float(locked_account.cash_available) + (
                    trade_amount - commission - stamp_duty - transfer_fee)

            # ---- 9. 更新账户总值 ----
            position_value = sum(
                float(p.market_value or 0) or float(p.shares_total) * float(p.current_price or p.avg_cost)
                for p in positions
            )

            locked_account.position_value = position_value + (
                trade_amount if action == 'BUY' else -trade_amount)
            locked_account.total_value = (
                float(locked_account.cash_available) + float(locked_account.cash_frozen)
                + float(locked_account.position_value))

            if locked_account.initial_capital:
                locked_account.cumulative_return = (
                    float(locked_account.total_value) / float(locked_account.initial_capital) - 1)

            if locked_account.peak_value and float(locked_account.total_value) > float(locked_account.peak_value):
                locked_account.peak_value = locked_account.total_value

            # ---- 10. 创建账户快照 ----
            self.repo.upsert_equity_snapshot(
                account_name,
                cash=float(locked_account.cash_available) + float(locked_account.cash_frozen),
                position_value=float(locked_account.position_value),
                total_value=float(locked_account.total_value),
                cumulative_return=float(locked_account.cumulative_return or 0),
                drawdown=(float(locked_account.total_value) / float(locked_account.peak_value) - 1)
                if locked_account.peak_value else 0.0,
                commit=False)

            # ---- 11. 提交事务 ----
            self.repo.session.commit()

        except TradingError:
            self.repo.session.rollback()
            raise
        except Exception as e:
            self.repo.session.rollback()
            logger.error("trade_transaction_failed_rollback", error=str(e), exc_info=True)
            raise TradingError(f'交易执行失败: {e}', 500)

        # ---- 12. 决策记录 ----
        self._auto_record_decision(
            account_name=account_name, action=action, symbol=symbol,
            shares=shares, price=px, amount=trade_amount,
            reason=reason, realized_pnl=realized_pnl)

        logger.info(
            "trade_executed_v2",
            account=account_name, action=action, symbol=symbol,
            shares=shares, price=px, trade_id=trade_id
        )

        return {
            'order_id': order.id,
            'order_status': 'filled',
            'trade_id': trade_id,
            'symbol': symbol,
            'action': action.lower(),
            'shares': shares,
            'price': px,
            'amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'realized_pnl': realized_pnl,
            'realized_pnl_rate': realized_pnl_rate,
        }

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
                'decision_type': f'trade_{action}',
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
