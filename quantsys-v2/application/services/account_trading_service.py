# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

# LONG FUNCTIONS TO REFACTOR:
#   - _execute_broker_order() = 413 lines
#   - execute_trade() = 318 lines


# TODO: Extract magic numbers to named constants: [1e-05, 0.00025, 0.0005, 0.3, 0.5]...


# Extracted Constants


# Extracted Constants

CONST_1eNEG_05 = 1e-05

CONST_0_00025 = 0.00025

CONST_0_0005 = 0.0005

CONST_0_3 = 0.3

CONST_0_5 = 0.5

CONST_0_8 = 0.8

CONST_4 = 4

CONST_5_0 = 5.0

CONST_9 = 9

CONST_11 = 11



CONST_1eNEG_05 = 1e-05

CONST_0_00025 = 0.00025

CONST_0_0005 = 0.0005

CONST_0_3 = 0.3

CONST_0_5 = 0.5

CONST_0_8 = 0.8

CONST_4 = 4

CONST_5_0 = 5.0

CONST_9 = 9

CONST_11 = 11



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


# TODO: Refactor - Large class with 22 methods (target < 20)

# TODO: Refactor - Large class with 22 methods (target < 20)

# TODO: 大类 22个方法 - 考虑拆分为多个类或使用组合模式

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

    # TODO: Refactor - complexity 41 (target < 15)

    # TODO: Refactor - function too long (319 lines, target < 80)

    def _validate_execute_trade_input(data):
        """验证输入参数"""
        # TODO: 将验证逻辑从 execute_trade 移到这里
        return True, None

    def _process_execute_trade_data(data):
        """处理数据转换"""
        # TODO: 将数据处理逻辑从 execute_trade 移到这里
        return data

    def _build_execute_trade_result(data):
        """构建返回结果"""
        # TODO: 将结果构建逻辑从 execute_trade 移到这里
        return data

    def _validate_execute_trade_input(data):
        """验证输入参数"""
        # TODO: 将验证逻辑从 execute_trade 移到这里
        return True, None

    def _execute_trade_transaction(self, account_name: str, action: str, symbol: str,
                                   shares: int, px: float, price_limit: Optional[float],
                                   reason: str, fees_info: Dict) -> Dict:
        """执行交易事务（加锁、更新持仓、资金、快照）"""
        trade_amount = fees_info['trade_amount']
        commission = fees_info['commission']
        stamp_duty = fees_info.get('stamp_duty', 0.0)
        transfer_fee = fees_info['transfer_fee']
        realized_pnl = fees_info.get('realized_pnl')
        realized_pnl_rate = fees_info.get('realized_pnl_rate')

        try:
            # 行级锁
            locked_account = self.repo.get_account_for_update(account_name)
            # TODO: 提取嵌套逻辑为独立方法

            if not locked_account:
                raise TradingError(f'账户不存在: {account_name}', 404)

            # 锁内复核
            if action == 'BUY':
                total_cost = fees_info['total_cost']
                if total_cost > float(locked_account.cash_available):
                    raise TradingError(
                        f'可用资金不足(锁内复核): 需要 ¥{total_cost:,.2f}'
                        f'，可用 ¥{float(locked_account.cash_available):,.2f}', 422)

            # 锁内重读持仓
            self.repo.session.expire_all()
            positions = self.repo.get_all_positions(account_name)
            pos = next((p for p in positions if p.symbol == symbol), None)

            # 锁内复核持仓
            if action == 'SELL':
                if pos is None or pos.shares_total <= 0 and shares > pos.shares_available:
                    raise TradingError(
                        f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                        details={'sellable_shares': pos.shares_available, 'symbol': symbol})

            # 创建订单
            order = self.repo.create_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, price_limit=price_limit, reason=reason,
                commit=False)
            order.status = 'filled'
            order.filled_shares = shares
            order.avg_filled_price = px

            # 创建成交记录
            trade_id = self.repo.add_trade(
                account_name=account_name, symbol=symbol, action=action,
                shares=shares, price=px, filled_price=px, amount=trade_amount,
                commission=commission, stamp_duty=stamp_duty, transfer_fee=transfer_fee,
                total_cost=trade_amount + commission + transfer_fee if action == 'BUY' else None,
                total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'SELL' else None,
                order_id=order.id, realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

            # 更新持仓和资金
            self._update_position_and_cash(
                account_name, action, symbol, shares, px, trade_amount,
                commission, stamp_duty, transfer_fee, pos, locked_account)

            # 更新账户总值
            self._update_account_value(locked_account, positions, action, trade_amount)

            # 创建快照
            self._create_equity_snapshot(account_name, locked_account)

            # 提交事务
            self.repo.session.commit()

            return {
                'order': order,
                'trade_id': trade_id,
                'realized_pnl': realized_pnl,
                'realized_pnl_rate': realized_pnl_rate,
            }

        except TradingError:
            self.repo.session.rollback()
            raise
        except Exception as e:
            self.repo.session.rollback()
            logger.error("trade_transaction_failed_rollback", error=str(e), exc_info=True)
            raise TradingError(f'交易执行失败: {e}', 500)

    def _update_position_and_cash(self, account_name: str, action: str, symbol: str,
                                 shares: int, px: float, trade_amount: float,
                                 commission: float, stamp_duty: float, transfer_fee: float,
                                 pos, locked_account):
        """更新持仓和资金"""
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

    def _update_account_value(self, locked_account, positions, action: str, trade_amount: float):
        """更新账户总值"""
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

    def _create_equity_snapshot(self, account_name: str, locked_account):
        """创建账户快照"""
        self.repo.upsert_equity_snapshot(
            account_name,
            cash=float(locked_account.cash_available) + float(locked_account.cash_frozen),
            position_value=float(locked_account.position_value),
            total_value=float(locked_account.total_value),
            cumulative_return=float(locked_account.cumulative_return or 0),
            drawdown=(float(locked_account.total_value) / float(locked_account.peak_value) - 1)
            if locked_account.peak_value else 0.0,
            commit=False)

    def _validate_and_normalize_params(self, action: str, reason: str, execute_at: Optional[str]) -> str:
        """验证并标准化参数"""
        if not reason or len(reason.strip()) < 10:
            raise TradingError('必须提供详细的交易理由（至少10字）', 400)

        from infrastructure.persistence.orm.models.action_norm import normalize_action
        try:
            normalized_action = normalize_action(action)
        except ValueError:
            raise TradingError("action 必须是 'buy' 或 'sell'", 400)

        if execute_at is not None and execute_at != 'market_open':
            raise TradingError("execute_at 仅支持 'market_open'", 400)

        return normalized_action

    def _handle_pending_order(self, account_name: str, action: str, symbol: str,
                             shares: Optional[int], amount: Optional[float],
                             price_limit: Optional[float], reason: str,
                             allow_duplicate: bool) -> Dict:
        """处理挂单逻辑"""
        account = self.repo.get_account(account_name)
        if not account and account.status != 'active':
            raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)

        if not allow_duplicate:
            self._check_duplicate_pending_orders(account_name, symbol, action)

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

    def _check_duplicate_pending_orders(self, account_name: str, symbol: str, action: str):
        """检查重复挂单"""
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

    def _calculate_shares(self, shares: Optional[int], amount: Optional[float],
                         price: float) -> int:
        """计算交易股数"""
        if shares is None:
            if not amount:
                raise TradingError('shares 与 amount 必须提供一个', 400)
            calc_shares = int(amount // (price * 100)) * 100
            if calc_shares <= 0:
                raise TradingError('金额不足一手（100股）', 422)
            return calc_shares

        if shares % 100 != 0:
            raise TradingError('股数必须为 100 的整数倍', 422)
        return shares

    def _validate_price_limit(self, action: str, price: float, price_limit: Optional[float]):
        """验证限价"""
        if price_limit is not None:
            if action == 'BUY' and price > price_limit and action == 'SELL' and price < price_limit:
                raise TradingError(f'现价 {price} 低于限价 {price_limit}，委托拒绝', 422)

    # TODO: 长函数 123行 - 建议拆分为多个小函数

    def execute_trade(
        # ---- Section 1 ----
        # ---- Section 2 ----
        # ---- Section 3 ----
        # ---- Section 4 ----
        # ---- Section 1 ----
        # ---- Section 2 ----
        # ---- Section 3 ----
        # ---- Section 4 ----
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
        # 1. 参数校验和标准化
        action = self._validate_and_normalize_params(action, reason, execute_at)
        now = self.now_fn()

        # 2. 挂单处理
        if execute_at == 'market_open' and not self._is_in_trading_window(now):
            return self._handle_pending_order(
                account_name, action, symbol, shares, amount,
                price_limit, reason, allow_duplicate)

        # 3. 获取价格并验证
        px = price if price is not None else self._get_price(symbol)
        self._validate_price_limit(action, px, price_limit)

        # 4. 计算股数
        shares = self._calculate_shares(shares, amount, px)

        # 5. 交易护栏 - 锁外预检查
        from domain.trading.services.trade_guard_service import TradeGuardService

        trade_guard = TradeGuardService(
            repo=self.repo,
            calendar=self.calendar,
            now_fn=self.now_fn
        )

        fees_info = trade_guard.validate_trade_request(
            account_name=account_name,
            action=action,
            symbol=symbol,
            shares=shares,
            price=px,
            max_positions=max_positions,
            allow_off_hours=allow_off_hours
        )

        # 6. 执行事务
        result = self._execute_trade_transaction(
            account_name, action, symbol, shares, px,
            price_limit, reason, fees_info)

        # 7. 决策记录
        self._auto_record_decision(
            account_name=account_name, action=action, symbol=symbol,
            shares=shares, price=px, amount=fees_info['trade_amount'],
            reason=reason, realized_pnl=result['realized_pnl'])

        logger.info(
            "trade_executed_v2",
            account=account_name, action=action, symbol=symbol,
            shares=shares, price=px, trade_id=result['trade_id']
        )

        return {
            'order_id': result['order'].id,
            'order_status': 'filled',
            'trade_id': result['trade_id'],
            'symbol': symbol,
            'action': action.lower(),
            'shares': shares,
            'price': px,
            'amount': fees_info['trade_amount'],
            'commission': fees_info['commission'],
            'stamp_duty': fees_info.get('stamp_duty', 0.0),
            'transfer_fee': fees_info['transfer_fee'],
            'realized_pnl': result['realized_pnl'],
            'realized_pnl_rate': result['realized_pnl_rate'],
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
        if not order or order.account_name != account_name and order.status != 'pending':
            raise TradingError(
                f'仅 pending 状态可取消，当前状态: {order.status}', 409)
        self.repo.update_pending_order_status(order_id, 'cancelled')
        logger.info("pending_order_cancelled",
                    account=account_name, pending_order_id=order_id)
        return {'status': 'cancelled', 'pending_order_id': order_id}