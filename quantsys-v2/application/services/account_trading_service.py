"""账户交易服务 —— 手工/代管交易的单事务执行

事务流: 校验 → 委托单 → 成交+费用 → 资金流水(add_trade自动) → 持仓 → 账户 → 快照
"""
import structlog
from typing import Dict, Optional

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

logger = structlog.get_logger(__name__)


class TradingError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class AccountTradingService:
    COMMISSION_RATE = 0.00025      # 佣金万2.5
    COMMISSION_MIN = 5.0           # 最低5元
    STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
    TRANSFER_FEE_RATE = 0.00001    # 过户费
    MAX_SINGLE_POSITION_RATIO = 0.30
    MAX_TOTAL_POSITION_RATIO = 0.80

    def __init__(self, repo: Optional[SimulationORMRepository] = None):
        self.repo = repo or SimulationORMRepository()

    def _get_price(self, symbol: str) -> float:
        from application.services.realtime_quote_service import RealtimeQuoteService
        quote = RealtimeQuoteService().get_realtime_quote(symbol)
        if not quote or not quote.price or quote.price <= 0:
            raise TradingError(f'无法获取 {symbol} 实时价格', 502)
        return float(quote.price)

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
    ) -> Dict:
        # ---- 校验 ----
        if not reason or len(reason.strip()) < 10:
            raise TradingError('必须提供详细的交易理由（至少10字）', 400)
        action = (action or '').lower()
        if action not in ('buy', 'sell'):
            raise TradingError("action 必须是 'buy' 或 'sell'", 400)
        account = self.repo.get_account(account_name)
        if not account:
            raise TradingError(f'账户不存在: {account_name}', 404)
        if account.status != 'active':
            raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)

        # T+1 结转由每日任务（settle_t1）负责，不在交易路径内做——
        # 可用数由交易事务自身维护（买入当日 +0，卖出即时扣减）

        px = price if price is not None else self._get_price(symbol)
        if price_limit is not None:
            if action == 'buy' and px > price_limit:
                raise TradingError(f'现价 {px} 高于限价 {price_limit}，委托拒绝', 422)
            if action == 'sell' and px < price_limit:
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
        stamp_duty = round(trade_amount * self.STAMP_DUTY_RATE, 2) if action == 'sell' else 0.0
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
        if action == 'buy':
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
                    f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422)
            cost_basis = shares * float(pos.avg_cost)
            realized_pnl = round(trade_amount - cost_basis - commission - stamp_duty - transfer_fee, 2)
            realized_pnl_rate = round(realized_pnl / cost_basis, 4) if cost_basis else 0.0

        # ---- 单事务执行 ----
        try:
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
                total_cost=trade_amount + commission + transfer_fee if action == 'buy' else None,
                total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'sell' else None,
                order_id=order.id, realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

            if action == 'buy':
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
                trade_amount if action == 'buy' else -trade_amount)
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

        return {
            'order_id': order.id,
            'order_status': 'filled',
            'trade_id': trade_id,
            'symbol': symbol,
            'action': action,
            'shares': shares,
            'price': px,
            'amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'realized_pnl': realized_pnl,
            'realized_pnl_rate': realized_pnl_rate,
        }
