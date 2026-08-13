"""
模拟交易ORM Repository

使用SQLAlchemy ORM的模拟交易数据访问层

支持：
1. 账户管理（开户/发现/归档）
2. 持仓管理（T+1 可用/总量分离）
3. 交易记录（自动写资金流水，维持不变式 Σ流水 == cash_available + cash_frozen）
4. 委托单
5. 资金流水
6. 净值快照
7. 统计查询
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, date
import structlog

from sqlalchemy import func, and_, desc
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import (
    SimulationAccount,
    SimulationPosition,
    SimulationTrade,
    SimulationOrder,
    SimulationCashFlow,
    SimulationEquitySnapshot,
    SimulationPendingOrder,
)
from domain.ports import ISimulationRepository

logger = structlog.get_logger(__name__)

__all__ = ['SimulationORMRepository', 'normalize_action']


def normalize_action(action: str) -> str:
    """交易方向归一化为大写 'BUY'/'SELL'（2026-08-12）。

    背景：simulation_trades.action 曾有两套写入约定（大写 vs 小写），
    读取侧 SQL 只匹配大写 → 小写卖出被无视 → 幽灵持仓注水估值。
    所有写入必须经过此函数；读取侧同步用 UPPER(action) 兼容历史脏数据。
    """
    normalized = (action or '').strip().upper()
    if normalized not in ('BUY', 'SELL'):
        raise ValueError(f"非法交易方向: {action!r}（期望 buy/sell）")
    return normalized


class SimulationORMRepository(BaseORMRepository[SimulationAccount], ISimulationRepository):
    """模拟交易ORM Repository

    示例用法：
        repo = SimulationORMRepository()

        # 获取账户
        account = repo.get_account('v14_simulation')

        # 获取所有持仓
        positions = repo.get_all_positions('v14_simulation')

        # 添加交易记录（自动写资金流水）
        trade_id = repo.add_trade(
            account_name='v14_simulation',
            symbol='000001',
            action='buy',
            shares=100,
            price=10.0,
            filled_price=10.05
        )
    """

    model = SimulationAccount

    # ==================== ISimulationRepository接口实现 ====================

    def save_simulation_result(self, result: Dict[str, Any]) -> int:
        """保存模拟交易结果（ISimulationRepository接口实现）

        Args:
            result: 模拟交易结果数据（必须包含 account_name）

        Returns:
            记录ID
        """
        try:
            trade = SimulationTrade(
                account_name=result['account_name'],
                symbol=result.get('symbol'),
                action=result.get('action'),
                shares=result.get('shares'),
                price=result.get('price'),
                filled_price=result.get('filled_price'),
                commission=result.get('commission', 0.0),
                trade_date=result.get('trade_date'),
            )
            self.session.add(trade)
            self.session.commit()
            return trade.id if trade.id else 0

        except Exception as e:
            logger.error(f"Error saving simulation result: {e}")
            self.session.rollback()
            return 0

    # ==================== 账户管理 ====================

    def get_account(self, account_name: str) -> Optional[SimulationAccount]:
        """获取账户信息

        Args:
            account_name: 账户名称

        Returns:
            SimulationAccount对象
        """
        try:
            return self.session.query(SimulationAccount).filter_by(
                account_name=account_name
            ).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting account {account_name}: {e}")
            return None

    def get_account_for_update(self, account_name: str) -> Optional[SimulationAccount]:
        """获取账户并加行级锁（SELECT ... FOR UPDATE）。

        用于交易事务：防止并发请求读到相同的 cash_available 后互相覆盖
        （lost update——2026-07-28 agent_virtual 曾因此虚增现金 ¥23,346）。
        锁持有者提交前，同账户的其他事务阻塞等待，从而实现串行化。
        populate_existing 强制以数据库最新值刷新会话中已缓存的实体。
        """
        try:
            return (
                self.session.query(SimulationAccount)
                .filter_by(account_name=account_name)
                .populate_existing()
                .with_for_update()
                .first()
            )
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error locking account {account_name}: {e}")
            return None

    def create_account(
        self,
        account_name: str,
        initial_capital: float,
        display_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
        commit: bool = True
    ) -> Optional[SimulationAccount]:
        """开户（写 deposit 资金流水，建立流水链起点）

        Args:
            account_name: 账户名称
            initial_capital: 初始资金
            display_name: 显示名
            strategy_name: 绑定策略名（可空）
            commit: 是否立即提交

        Returns:
            SimulationAccount对象
        """
        try:
            existing = self.get_account(account_name)
            if existing:
                logger.warning(f"Account {account_name} already exists")
                return existing
            account = SimulationAccount(
                account_name=account_name,
                display_name=display_name or account_name,
                strategy_name=strategy_name,
                initial_capital=initial_capital,
                cash_available=initial_capital,
                cash_frozen=0,
                total_value=initial_capital,
                peak_value=initial_capital,
                status='active',
            )
            self.session.add(account)
            flow = SimulationCashFlow(
                account_name=account_name,
                flow_type='deposit',
                amount=initial_capital,
                balance_after=initial_capital,
            )
            self.session.add(flow)
            if commit:
                self.session.commit()
                self.session.refresh(account)
            logger.info(f"开户成功: {account_name}, 初始资金 ¥{initial_capital:,.2f}")
            return account
        except Exception as e:
            logger.error(f"Error creating account {account_name}: {e}")
            self.session.rollback()
            return None

    def list_accounts(self, status: str = 'active') -> List[SimulationAccount]:
        """按状态列出账户"""
        return self.session.query(SimulationAccount).filter_by(status=status).all()

    def list_account_summaries(self, status: str = 'active') -> List[Dict]:
        """账户发现：所有账户 + 摘要（含持仓数）"""
        accounts = self.list_accounts(status)
        counts = dict(
            self.session.query(
                SimulationPosition.account_name, func.count()
            ).group_by(SimulationPosition.account_name).all()
        )
        return [{
            'account_name': a.account_name,
            'display_name': a.display_name,
            'strategy_name': a.strategy_name,
            'status': a.status,
            'cash_available': float(a.cash_available or 0),
            'cash_frozen': float(a.cash_frozen or 0),
            'position_value': float(a.position_value or 0),
            'total_value': float(a.total_value or 0),
            'cumulative_return': float(a.cumulative_return or 0),
            'positions_count': int(counts.get(a.account_name, 0)),
        } for a in accounts]

    def archive_account(self, account_name: str) -> bool:
        """归档账户（只读）"""
        account = self.get_account(account_name)
        if not account:
            return False
        account.status = 'archived'
        self.session.commit()
        return True

    def set_account_status(self, account_name: str, status: str) -> bool:
        """设置账户状态（active/frozen/archived）。

        frozen 账户被 execute_trade 拒绝写操作（status != 'active' 检查），
        用于退役旧账本但保留历史数据。
        """
        try:
            account = self.get_account(account_name)
            if not account:
                logger.warning(f"Account {account_name} not found")
                return False
            account.status = status
            self.session.commit()
            logger.info(f"账户状态变更: {account_name} → {status}")
            return True
        except Exception as e:
            logger.error(f"Error setting status for {account_name}: {e}")
            self.session.rollback()
            return False

    def update_account(
        self,
        account_name: str,
        cash_available: float,
        total_value: float,
        peak_value: float,
        cumulative_return: float,
        max_drawdown: float,
        position_value: Optional[float] = None,
        last_rebalance_date: Optional[str] = None
    ) -> bool:
        """更新账户信息

        Args:
            account_name: 账户名称
            cash_available: 可用资金
            total_value: 总资产
            peak_value: 历史峰值
            cumulative_return: 累计收益率
            max_drawdown: 最大回撤
            position_value: 持仓市值（None 则不更新）
            last_rebalance_date: 最后调仓日期

        Returns:
            成功返回True
        """
        try:
            account = self.get_account(account_name)
            if not account:
                logger.warning(f"Account {account_name} not found")
                return False

            account.cash_available = cash_available
            account.total_value = total_value
            account.peak_value = peak_value
            account.cumulative_return = cumulative_return
            account.max_drawdown = max_drawdown
            if position_value is not None:
                account.position_value = position_value
            if last_rebalance_date:
                account.last_rebalance_date = last_rebalance_date

            self.session.commit()
            logger.info(f"账户更新: {account_name} 可用资金¥{cash_available:,.2f}, 总资产¥{total_value:,.2f}")
            return True

        except Exception as e:
            logger.error(f"Error updating account {account_name}: {e}")
            self.session.rollback()
            return False

    def update_last_rebalance_date(self, account_name: str, date: str) -> bool:
        """更新账户最后调仓日期"""
        try:
            account = self.get_account(account_name)
            if not account:
                logger.warning(f"Account {account_name} not found")
                return False

            account.last_rebalance_date = date
            self.session.commit()
            logger.info(f"Updated last_rebalance_date for {account_name}: {date}")
            return True

        except Exception as e:
            logger.error(f"Error updating last_rebalance_date for {account_name}: {e}")
            self.session.rollback()
            return False

    # ==================== 资金流水 ====================

    def add_cash_flow(
        self,
        account_name: str,
        flow_type: str,
        amount: float,
        balance_after: float,
        ref_order_id: Optional[int] = None,
        ref_trade_id: Optional[int] = None,
        commit: bool = True
    ) -> Optional[SimulationCashFlow]:
        """写入资金流水（所有资金变动必须经过此方法）"""
        flow = SimulationCashFlow(
            account_name=account_name,
            flow_type=flow_type,
            amount=amount,
            balance_after=balance_after,
            ref_order_id=ref_order_id,
            ref_trade_id=ref_trade_id,
        )
        self.session.add(flow)
        if commit:
            self.session.commit()
        return flow

    def get_cash_flows(self, account_name: str, limit: int = 500) -> List[SimulationCashFlow]:
        """按时间顺序获取资金流水"""
        return self.session.query(SimulationCashFlow).filter_by(
            account_name=account_name
        ).order_by(SimulationCashFlow.id).limit(limit).all()

    def get_last_flow_balance(self, account_name: str) -> Optional[float]:
        """获取最后一条流水的余额"""
        flow = self.session.query(SimulationCashFlow).filter_by(
            account_name=account_name
        ).order_by(SimulationCashFlow.id.desc()).first()
        return float(flow.balance_after) if flow else None

    def verify_cash_flow_invariant(self, account_name: str) -> Dict:
        """校验不变式（双重）：
        1. 末条流水余额 == cash_available + cash_frozen
        2. 全部流水 amount 之和 == cash_available + cash_frozen
           （强不变式：能检出并发 lost update 造成的链条断裂，
           此类问题中末条余额可能恰好与现金一致，单看 1 无法发现）
        """
        account = self.get_account(account_name)
        flows = self.get_cash_flows(account_name, limit=100000)
        flow_balance = float(flows[-1].balance_after) if flows else 0.0
        flow_sum = sum(float(f.amount or 0) for f in flows)
        cash = (float(account.cash_available or 0) + float(account.cash_frozen or 0)) if account else 0.0
        return {
            'account_name': account_name,
            'flow_balance': flow_balance,
            'flow_sum': round(flow_sum, 2),
            'account_cash': cash,
            'flow_count': len(flows),
            'invariant_ok': abs(flow_balance - cash) < 0.01,
            'sum_invariant_ok': abs(flow_sum - cash) < 0.01,
        }

    # ==================== 委托单 ====================

    def create_order(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: int,
        order_type: str = 'market',
        price_limit: Optional[float] = None,
        reason: Optional[str] = None,
        strategy_name: Optional[str] = None,
        signal_id: Optional[str] = None,
        commit: bool = True
    ) -> SimulationOrder:
        """创建委托单"""
        order = SimulationOrder(
            account_name=account_name,
            action=action,
            order_type=order_type,
            symbol=symbol,
            shares=shares,
            price_limit=price_limit,
            status='submitted',
            filled_shares=0,
            reason=reason,
            strategy_name=strategy_name,
            signal_id=signal_id,
        )
        self.session.add(order)
        if commit:
            self.session.commit()
            self.session.refresh(order)
        else:
            self.session.flush()  # 拿到 order.id
        return order

    # ==================== 条件委托（挂单） ====================

    def create_pending_order(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: Optional[int] = None,
        amount: Optional[float] = None,
        price_limit: Optional[float] = None,
        reason: Optional[str] = None,
        execute_at: str = 'market_open',
        commit: bool = True
    ) -> SimulationPendingOrder:
        """创建条件委托（挂单），初始状态 pending"""
        order = SimulationPendingOrder(
            account_name=account_name,
            action=action,
            symbol=symbol,
            shares=shares,
            amount=amount,
            price_limit=price_limit,
            reason=reason,
            execute_at=execute_at,
            status='pending',
        )
        self.session.add(order)
        if commit:
            self.session.commit()
            self.session.refresh(order)
        else:
            self.session.flush()
        return order

    def get_pending_order(self, order_id: int) -> Optional[SimulationPendingOrder]:
        """按 id 取单个挂单"""
        return self.session.query(SimulationPendingOrder).filter_by(id=order_id).first()

    def get_pending_orders(
        self,
        account_name: Optional[str] = None,
        status: Optional[str] = 'pending'
    ) -> List[SimulationPendingOrder]:
        """查询挂单（默认只取 pending，按 id 升序保证撮合顺序）"""
        query = self.session.query(SimulationPendingOrder)
        if account_name:
            query = query.filter_by(account_name=account_name)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(SimulationPendingOrder.id).all()

    def update_pending_order_status(
        self,
        order_id: int,
        status: str,
        fail_reason: Optional[str] = None,
        executed_trade_id: Optional[int] = None,
        commit: bool = True
    ) -> bool:
        """更新挂单状态（executed/failed/cancelled）"""
        order = self.get_pending_order(order_id)
        if not order:
            return False
        order.status = status
        if fail_reason is not None:
            order.fail_reason = fail_reason
        if executed_trade_id is not None:
            order.executed_trade_id = executed_trade_id
        order.updated_at = datetime.now()
        if commit:
            self.session.commit()
        return True

    # ==================== 净值快照 ====================

    def upsert_equity_snapshot(
        self,
        account_name: str,
        cash: float,
        position_value: float,
        total_value: float,
        daily_return: float = 0.0,
        cumulative_return: float = 0.0,
        drawdown: float = 0.0,
        snapshot_date: Optional[date] = None,
        commit: bool = True
    ) -> SimulationEquitySnapshot:
        """写入/更新当日净值快照"""
        day = snapshot_date or datetime.now().date()
        snap = self.session.query(SimulationEquitySnapshot).filter_by(
            account_name=account_name, snapshot_date=day
        ).first()
        if snap:
            snap.cash = cash
            snap.position_value = position_value
            snap.total_value = total_value
            snap.daily_return = daily_return
            snap.cumulative_return = cumulative_return
            snap.drawdown = drawdown
        else:
            snap = SimulationEquitySnapshot(
                account_name=account_name,
                snapshot_date=day,
                cash=cash,
                position_value=position_value,
                total_value=total_value,
                daily_return=daily_return,
                cumulative_return=cumulative_return,
                drawdown=drawdown,
            )
            self.session.add(snap)
        if commit:
            self.session.commit()
        return snap

    def get_equity_snapshots(self, account_name: str, limit: int = 90) -> List[SimulationEquitySnapshot]:
        """获取净值快照（按日期倒序）"""
        return self.session.query(SimulationEquitySnapshot).filter_by(
            account_name=account_name
        ).order_by(SimulationEquitySnapshot.snapshot_date.desc()).limit(limit).all()

    # ==================== 持仓管理 ====================

    def get_all_positions(
        self,
        account_name: str,
        only_nonzero: bool = True
    ) -> List[SimulationPosition]:
        """获取所有持仓"""
        try:
            query = self.session.query(SimulationPosition).filter_by(
                account_name=account_name
            )

            if only_nonzero:
                query = query.filter(SimulationPosition.shares_total > 0)

            return query.order_by(SimulationPosition.symbol).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting positions for {account_name}: {e}")
            return []

    def get_position(
        self,
        account_name: str,
        symbol: str
    ) -> Optional[SimulationPosition]:
        """获取单个持仓"""
        try:
            return self.session.query(SimulationPosition).filter_by(
                account_name=account_name,
                symbol=symbol
            ).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting position {symbol}: {e}")
            return None

    def upsert_position(
        self,
        account_name: str,
        symbol: str,
        shares_total: int,
        avg_cost: float,
        shares_available: Optional[int] = None,
        current_price: Optional[float] = None,
        commit: bool = True
    ) -> bool:
        """插入或更新持仓

        Args:
            account_name: 账户名称
            symbol: 股票代码
            shares_total: 持仓总量
            avg_cost: 移动加权成本价
            shares_available: 可用数量（None 时 = shares_total）
            current_price: 当前价格
            commit: 是否立即提交

        Returns:
            成功返回True
        """
        try:
            available = shares_available if shares_available is not None else shares_total
            price = current_price or avg_cost
            market_value = shares_total * price
            cost = shares_total * avg_cost
            profit = market_value - cost
            profit_rate = profit / cost if cost > 0 else 0

            position = self.get_position(account_name, symbol)

            if position:
                position.shares_total = shares_total
                position.shares_available = available
                position.avg_cost = avg_cost
                position.current_price = current_price
                position.market_value = market_value
                position.cost = cost
                position.profit_total = profit
                position.profit_total_rate = profit_rate
            else:
                position = SimulationPosition(
                    account_name=account_name,
                    symbol=symbol,
                    shares_total=shares_total,
                    shares_available=available,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    market_value=market_value,
                    cost=cost,
                    profit_total=profit,
                    profit_total_rate=profit_rate
                )
                self.session.add(position)

            if commit:
                self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error upserting position {symbol}: {e}")
            self.session.rollback()
            return False

    def delete_position(self, account_name: str, symbol: str, commit: bool = True) -> bool:
        """删除持仓"""
        try:
            position = self.get_position(account_name, symbol)
            if position:
                self.session.delete(position)
                if commit:
                    self.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting position {symbol}: {e}")
            self.session.rollback()
            return False

    def clear_all_positions(self, account_name: str) -> bool:
        """清空账户所有持仓"""
        try:
            deleted = self.session.query(SimulationPosition).filter_by(
                account_name=account_name
            ).delete()
            self.session.commit()
            logger.info(f"Cleared {deleted} positions for account {account_name}")
            return True
        except Exception as e:
            logger.error(f"Error clearing positions for {account_name}: {e}")
            self.session.rollback()
            return False

    def settle_t1(self, account_name: str, today: Optional[date] = None) -> int:
        """T+1 结转：可用数 = 总量 − 当日买入量（幂等自校正，无需状态标记）

        Args:
            account_name: 账户名称
            today: 参照日期（默认今天；测试/回放可注入未来日期模拟次日）

        Returns:
            更新行数
        """
        day = today or datetime.now().date()
        bought_today = dict(
            self.session.query(
                SimulationTrade.symbol, func.sum(SimulationTrade.shares)
            ).filter_by(account_name=account_name, action='buy')
             .filter(SimulationTrade.trade_date == day)
             .group_by(SimulationTrade.symbol).all()
        )
        positions = self.session.query(SimulationPosition).filter_by(
            account_name=account_name).all()
        for p in positions:
            p.shares_available = max(
                p.shares_total - int(bought_today.get(p.symbol, 0)), 0)
        self.session.commit()
        return len(positions)

    def update_position_prices(
        self,
        account_name: str,
        prices: Dict[str, float]
    ) -> bool:
        """批量更新持仓当前价格，并刷新账户总资产/累计收益率"""
        try:
            for symbol, price in prices.items():
                position = self.get_position(account_name, symbol)
                if position:
                    position.current_price = price
                    position.market_value = position.shares_total * price
                    position.profit_total = float(position.market_value) - float(position.cost or 0)
                    if float(position.cost or 0) > 0:
                        position.profit_total_rate = position.profit_total / float(position.cost)

            account = self.get_account(account_name)
            if account:
                positions = self.get_all_positions(account_name)
                total_market_value = sum(float(p.market_value) for p in positions if p.market_value)
                account.position_value = total_market_value
                account.total_value = (
                    float(account.cash_available or 0)
                    + float(account.cash_frozen or 0)
                    + total_market_value
                )
                initial_capital = float(account.initial_capital or 0)
                if initial_capital > 0:
                    account.cumulative_return = (account.total_value - initial_capital) / initial_capital

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating position prices: {e}")
            self.session.rollback()
            return False

    # ==================== 交易记录 ====================

    def add_trade(
        self,
        account_name: str,
        symbol: str,
        action: str,
        shares: int,
        price: float,
        filled_price: float,
        amount: Optional[float] = None,
        commission: float = 0,
        stamp_duty: float = 0,
        transfer_fee: float = 0,
        total_cost: Optional[float] = None,
        total_revenue: Optional[float] = None,
        trade_date: Optional[str] = None,
        order_type: str = 'market',
        order_id: Optional[int] = None,
        realized_pnl: Optional[float] = None,
        realized_pnl_rate: Optional[float] = None,
        reason: Optional[str] = None,
        write_flow: bool = True,
        commit: bool = True
    ) -> Optional[int]:
        """添加交易记录（自动写资金流水，维持流水链不变式）

        Args:
            account_name: 账户名称
            symbol: 股票代码
            action: 操作类型 (buy/sell)
            shares: 交易数量
            price: 委托价格
            filled_price: 成交价格
            amount: 交易金额（默认 shares × filled_price）
            commission: 佣金
            stamp_duty: 印花税
            transfer_fee: 过户费
            total_cost: 总成本（买入）
            total_revenue: 总收入（卖出）
            trade_date: 交易日期
            order_type: 订单类型
            order_id: 关联委托单
            realized_pnl: 已实现盈亏（卖出）
            realized_pnl_rate: 已实现盈亏率
            reason: 交易理由
            write_flow: 是否自动写资金流水（默认 True）
            commit: 是否立即提交

        Returns:
            交易ID
        """
        try:
            if amount is None:
                amount = shares * filled_price

            if trade_date is None:
                trade_date = datetime.now().date()

            trade = SimulationTrade(
                account_name=account_name,
                symbol=symbol,
                action=normalize_action(action),
                shares=shares,
                price=price,
                filled_price=filled_price,
                amount=amount,
                commission=commission,
                stamp_duty=stamp_duty,
                transfer_fee=transfer_fee,
                total_cost=total_cost,
                total_revenue=total_revenue,
                trade_date=trade_date,
                order_type=order_type,
                order_id=order_id,
                realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate,
                reason=reason,
            )
            self.session.add(trade)
            self.session.flush()

            if write_flow:
                fees = float(commission or 0) + float(stamp_duty or 0) + float(transfer_fee or 0)
                if action.lower() == 'buy':
                    net = -(float(amount) + fees)
                    flow_type = 'buy_debit'
                else:
                    net = float(amount) - fees
                    flow_type = 'sell_credit'
                last = self.get_last_flow_balance(account_name)
                if last is None:
                    account = self.get_account(account_name)
                    last = float(account.cash_available or 0) if account else 0.0
                self.add_cash_flow(
                    account_name=account_name,
                    flow_type=flow_type,
                    amount=net,
                    balance_after=last + net,
                    ref_order_id=order_id,
                    ref_trade_id=trade.id,
                    commit=False)

            if commit:
                self.session.commit()
            logger.info(f"交易记录: {account_name} {action} {symbol} {shares}股 @ ¥{filled_price:.2f}")
            return trade.id

        except Exception as e:
            logger.error(f"Error adding trade: {e}")
            self.session.rollback()
            return None

    def get_trades(
        self,
        account_name: str,
        limit: int = 100
    ) -> List[SimulationTrade]:
        """获取交易记录"""
        try:
            return self.session.query(SimulationTrade).filter_by(
                account_name=account_name
            ).order_by(SimulationTrade.trade_time.desc()).limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trades: {e}")
            return []

    def get_trades_by_account(
        self,
        account_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[SimulationTrade]:
        """获取账户的所有交易记录"""
        try:
            query = self.session.query(SimulationTrade).filter_by(
                account_name=account_name
            )

            if start_date:
                query = query.filter(SimulationTrade.trade_date >= start_date)
            if end_date:
                query = query.filter(SimulationTrade.trade_date <= end_date)

            return query.order_by(SimulationTrade.trade_date.desc()).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trades for account {account_name}: {e}")
            return []

    def get_trades_by_symbol(
        self,
        account_name: str,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[SimulationTrade]:
        """获取指定股票的交易记录"""
        try:
            query = self.session.query(SimulationTrade).filter_by(
                account_name=account_name,
                symbol=symbol
            )

            if start_date:
                query = query.filter(SimulationTrade.trade_date >= start_date)
            if end_date:
                query = query.filter(SimulationTrade.trade_date <= end_date)

            return query.order_by(SimulationTrade.trade_date.desc()).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trades for {symbol}: {e}")
            return []

    def get_trade_count(
        self,
        account_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> int:
        """获取交易次数"""
        try:
            query = self.session.query(SimulationTrade).filter_by(
                account_name=account_name
            )

            if start_date and end_date:
                query = query.filter(
                    SimulationTrade.trade_date >= start_date,
                    SimulationTrade.trade_date <= end_date
                )

            return query.count()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error counting trades: {e}")
            return 0

    def get_total_commission(self, account_name: str) -> float:
        """获取总手续费（佣金+印花税+过户费）"""
        try:
            result = self.session.query(
                func.coalesce(func.sum(SimulationTrade.commission), 0) +
                func.coalesce(func.sum(SimulationTrade.stamp_duty), 0) +
                func.coalesce(func.sum(SimulationTrade.transfer_fee), 0)
            ).filter_by(account_name=account_name).scalar()

            return float(result or 0)

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting total commission: {e}")
            return 0.0

    # ==================== 统计查询 ====================

    def get_position_summary(self, account_name: str) -> Dict:
        """获取持仓汇总"""
        try:
            positions = self.get_all_positions(account_name, only_nonzero=True)

            total_cost = sum(float(p.cost or 0) for p in positions)
            total_market_value = sum(float(p.market_value or 0) for p in positions)
            total_profit = sum(float(p.profit_total or 0) for p in positions)

            return {
                'count': len(positions),
                'total_cost': total_cost,
                'total_market_value': total_market_value,
                'total_profit': total_profit,
                'profit_rate': total_profit / total_cost if total_cost > 0 else 0
            }

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting position summary: {e}")
            return {}

    def get_trade_stats(
        self,
        account_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """获取交易统计"""
        try:
            query = self.session.query(SimulationTrade).filter_by(
                account_name=account_name
            )

            if start_date and end_date:
                query = query.filter(
                    SimulationTrade.trade_date >= start_date,
                    SimulationTrade.trade_date <= end_date
                )

            trades = query.all()

            buy_count = sum(1 for t in trades if t.action.lower() == 'buy')
            sell_count = sum(1 for t in trades if t.action.lower() == 'sell')
            total_commission = sum(
                float(t.commission or 0) + float(t.stamp_duty or 0) + float(t.transfer_fee or 0)
                for t in trades
            )

            return {
                'total': len(trades),
                'buy': buy_count,
                'sell': sell_count,
                'commission': total_commission
            }

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trade stats: {e}")
            return {}
