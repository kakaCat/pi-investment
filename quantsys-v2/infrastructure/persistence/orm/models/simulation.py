"""
模拟交易相关Model

包含：
1. SimulationAccount - 模拟账户
2. SimulationPosition - 模拟持仓
3. SimulationTrade - 模拟交易记录
"""
from sqlalchemy import (
    Column, String, Integer, Date, DateTime, Numeric, Text,
    Index, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from datetime import datetime

from ..base import Base
from .action_norm import normalize_action

__all__ = [
    'SimulationAccount', 'SimulationPosition', 'SimulationTrade',
    'SimulationOrder', 'SimulationCashFlow', 'SimulationEquitySnapshot',
    'SimulationPendingOrder',
]


class SimulationAccount(Base):
    """模拟账户表

    对应数据库表：quant.simulation_account
    主键：id
    唯一约束：account_name
    """
    __tablename__ = 'simulation_account'
    __table_args__ = (
        # 唯一约束
        Index('simulation_account_account_name_key', 'account_name', unique=True),
        # Schema
        {'schema': 'quant'}
    )

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='账户ID')

    # 账户信息
    account_name = Column(
        String(50),
        nullable=False,
        default='default',
        comment='账户名称'
    )

    # 资金信息
    cash_available = Column(Numeric(15, 2), nullable=False, default=0, comment='可用资金')
    cash_frozen = Column(Numeric(15, 2), nullable=False, default=0, comment='冻结资金')
    position_value = Column(Numeric(15, 2), nullable=False, default=0, comment='持仓市值')
    total_value = Column(Numeric(15, 2), nullable=False, default=0, comment='总资产')
    peak_value = Column(Numeric(15, 2), nullable=False, default=0, comment='历史峰值')
    initial_capital = Column(Numeric(15, 2), nullable=False, default=0, comment='初始资金')

    # 账户元数据
    display_name = Column(String(100), comment='显示名')
    strategy_name = Column(String(50), comment='绑定策略名')
    status = Column(String(20), nullable=False, default='active', comment='active/archived')

    # 绩效指标
    cumulative_return = Column(Numeric(10, 4), default=0, comment='累计收益率')
    max_drawdown = Column(Numeric(10, 4), default=0, comment='最大回撤')

    # 最后操作日期
    last_rebalance_date = Column(Date, comment='最后调仓日期')

    # 时间戳
    created_at = Column(
        DateTime(timezone=False),
        default=datetime.now,
        comment='创建时间'
    )
    updated_at = Column(
        DateTime(timezone=False),
        default=datetime.now,
        onupdate=datetime.now,
        comment='更新时间'
    )

    # 关系映射
    positions = relationship(
        'SimulationPosition',
        back_populates='account',
        foreign_keys='SimulationPosition.account_name',
        primaryjoin='SimulationAccount.account_name==SimulationPosition.account_name',
        lazy='dynamic'
    )
    trades = relationship(
        'SimulationTrade',
        back_populates='account',
        foreign_keys='SimulationTrade.account_name',
        primaryjoin='SimulationAccount.account_name==SimulationTrade.account_name',
        lazy='dynamic'
    )

    def __repr__(self):
        return (
            f"<SimulationAccount(id={self.id}, name='{self.account_name}', "
            f"cash_available={self.cash_available}, total_value={self.total_value})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'account_name': self.account_name,
            'cash_available': float(self.cash_available) if self.cash_available else 0,
            'cash_frozen': float(self.cash_frozen) if self.cash_frozen else 0,
            'position_value': float(self.position_value) if self.position_value else 0,
            'total_value': float(self.total_value) if self.total_value else 0,
            'peak_value': float(self.peak_value) if self.peak_value else 0,
            'initial_capital': float(self.initial_capital) if self.initial_capital else 0,
            'display_name': self.display_name,
            'strategy_name': self.strategy_name,
            'status': self.status,
            'cumulative_return': float(self.cumulative_return) if self.cumulative_return else 0,
            'max_drawdown': float(self.max_drawdown) if self.max_drawdown else 0,
            'last_rebalance_date': self.last_rebalance_date.isoformat() if self.last_rebalance_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SimulationPosition(Base):
    """模拟持仓表

    对应数据库表：quant.simulation_positions
    主键：id
    唯一约束：(account_name, symbol)
    """
    __tablename__ = 'simulation_positions'
    __table_args__ = (
        # 唯一约束
        Index('simulation_positions_account_name_symbol_key', 'account_name', 'symbol', unique=True),
        # Schema
        {'schema': 'quant'}
    )

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='持仓ID')

    # 账户关联
    account_name = Column(
        String(50),
        nullable=False,
        default='default',
        comment='账户名称'
    )

    # 持仓信息
    symbol = Column(String(20), nullable=False, comment='股票代码')
    shares_total = Column(Integer, nullable=False, default=0, comment='持仓总量')
    shares_available = Column(Integer, nullable=False, default=0, comment='可用数量(T+1)')
    avg_cost = Column(Numeric(10, 2), nullable=False, comment='移动加权成本价')

    # 市值信息
    current_price = Column(Numeric(10, 2), comment='当前价格')
    market_value = Column(Numeric(15, 2), comment='市值')
    cost = Column(Numeric(15, 2), comment='成本')

    # 盈亏信息
    profit_total = Column(Numeric(15, 2), comment='持仓盈亏(浮动)')
    profit_total_rate = Column(Numeric(10, 4), comment='持仓盈亏比例')
    profit_today = Column(Numeric(15, 2), comment='当日盈亏')

    # 时间戳
    created_at = Column(
        DateTime(timezone=False),
        default=datetime.now,
        comment='创建时间'
    )
    updated_at = Column(
        DateTime(timezone=False),
        default=datetime.now,
        onupdate=datetime.now,
        comment='更新时间'
    )

    # 关系映射
    account = relationship(
        'SimulationAccount',
        back_populates='positions',
        foreign_keys=[account_name],
        primaryjoin='SimulationPosition.account_name==SimulationAccount.account_name'
    )

    def __repr__(self):
        return (
            f"<SimulationPosition(id={self.id}, account='{self.account_name}', "
            f"symbol='{self.symbol}', shares_total={self.shares_total}, avg_cost={self.avg_cost})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'account_name': self.account_name,
            'symbol': self.symbol,
            'shares_total': self.shares_total,
            'shares_available': self.shares_available,
            'avg_cost': float(self.avg_cost) if self.avg_cost else 0,
            'current_price': float(self.current_price) if self.current_price else 0,
            'market_value': float(self.market_value) if self.market_value else 0,
            'cost': float(self.cost) if self.cost else 0,
            'profit_total': float(self.profit_total) if self.profit_total else 0,
            'profit_total_rate': float(self.profit_total_rate) if self.profit_total_rate else 0,
            'profit_today': float(self.profit_today) if self.profit_today else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SimulationTrade(Base):
    """模拟交易记录表

    对应数据库表：quant.simulation_trades
    主键：id
    """
    __tablename__ = 'simulation_trades'
    __table_args__ = (
        # 索引
        Index('idx_simulation_trades_account', 'account_name'),
        Index('idx_simulation_trades_symbol', 'symbol'),
        Index('idx_simulation_trades_date', 'trade_date'),
        # action 大写契约（2026-08-13 统一，见 models/action_norm.py）
        CheckConstraint("action IN ('BUY','SELL')", name='simulation_trades_action_check'),
        # Schema
        {'schema': 'quant'}
    )

    @validates('action')
    def _normalize_action(self, key, value):
        return normalize_action(value)

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='交易ID')

    # 账户关联
    account_name = Column(
        String(50),
        nullable=False,
        default='default',
        comment='账户名称'
    )

    # 交易信息
    symbol = Column(String(20), nullable=False, comment='股票代码')
    action = Column(String(10), nullable=False, comment='操作类型(BUY/SELL，大写契约)')
    shares = Column(Integer, nullable=False, comment='交易数量')

    # 价格信息
    price = Column(Numeric(10, 2), nullable=False, comment='委托价格')
    filled_price = Column(Numeric(10, 2), nullable=False, comment='成交价格')
    amount = Column(Numeric(15, 2), nullable=False, comment='交易金额')

    # 费用信息
    commission = Column(Numeric(10, 2), nullable=False, default=0, comment='佣金')
    stamp_duty = Column(Numeric(10, 2), default=0, comment='印花税')
    transfer_fee = Column(Numeric(10, 2), default=0, comment='过户费')
    total_cost = Column(Numeric(15, 2), comment='总成本（买入时）')
    total_revenue = Column(Numeric(15, 2), comment='总收入（卖出时）')

    # 关联与盈亏
    order_id = Column(Integer, comment='关联委托单ID')
    realized_pnl = Column(Numeric(15, 2), comment='已实现盈亏(卖出)')
    realized_pnl_rate = Column(Numeric(10, 4), comment='已实现盈亏率')
    reason = Column(String(500), comment='交易理由')

    # 订单类型
    order_type = Column(
        String(20),
        default='market',
        comment='订单类型(market/limit)'
    )

    # 时间信息
    trade_date = Column(Date, nullable=False, comment='交易日期')
    trade_time = Column(
        DateTime(timezone=False),
        default=datetime.now,
        comment='交易时间'
    )
    created_at = Column(
        DateTime(timezone=False),
        default=datetime.now,
        comment='创建时间'
    )

    # 关系映射
    account = relationship(
        'SimulationAccount',
        back_populates='trades',
        foreign_keys=[account_name],
        primaryjoin='SimulationTrade.account_name==SimulationAccount.account_name'
    )

    def __repr__(self):
        return (
            f"<SimulationTrade(id={self.id}, symbol='{self.symbol}', "
            f"action='{self.action}', shares={self.shares}, price={self.filled_price})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'account_name': self.account_name,
            'symbol': self.symbol,
            'action': self.action,
            'shares': self.shares,
            'price': float(self.price) if self.price else 0,
            'filled_price': float(self.filled_price) if self.filled_price else 0,
            'amount': float(self.amount) if self.amount else 0,
            'commission': float(self.commission) if self.commission else 0,
            'stamp_duty': float(self.stamp_duty) if self.stamp_duty else 0,
            'transfer_fee': float(self.transfer_fee) if self.transfer_fee else 0,
            'total_cost': float(self.total_cost) if self.total_cost else 0,
            'total_revenue': float(self.total_revenue) if self.total_revenue else 0,
            'order_id': self.order_id,
            'realized_pnl': float(self.realized_pnl) if self.realized_pnl is not None else None,
            'realized_pnl_rate': float(self.realized_pnl_rate) if self.realized_pnl_rate is not None else None,
            'reason': self.reason,
            'order_type': self.order_type,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'trade_time': self.trade_time.isoformat() if self.trade_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SimulationOrder(Base):
    """委托单表 quant.simulation_order"""
    __tablename__ = 'simulation_order'
    __table_args__ = (
        Index('idx_simulation_order_account', 'account_name'),
        Index('idx_simulation_order_symbol', 'symbol'),
        CheckConstraint("action IN ('BUY','SELL')", name='simulation_order_action_check'),
        {'schema': 'quant'}
    )

    @validates('action')
    def _normalize_action(self, key, value):
        return normalize_action(value)

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False, comment='账户名称')
    action = Column(String(10), nullable=False, comment='BUY/SELL（大写契约）')
    order_type = Column(String(20), nullable=False, default='market', comment='market/limit')
    symbol = Column(String(20), nullable=False, comment='股票代码')
    shares = Column(Integer, nullable=False, comment='委托数量')
    price_limit = Column(Numeric(10, 2), comment='限价')
    status = Column(String(20), nullable=False, default='submitted',
                    comment='submitted/filled/partially_filled/cancelled/rejected')
    filled_shares = Column(Integer, default=0, comment='已成交数量')
    avg_filled_price = Column(Numeric(10, 2), comment='平均成交价')
    reason = Column(String(500), comment='决策理由')
    strategy_name = Column(String(50), comment='来源策略')
    signal_id = Column(String(64), comment='来源信号')
    reject_reason = Column(String(500), comment='拒绝原因')
    created_at = Column(DateTime(timezone=False), default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime(timezone=False), default=datetime.now,
                        onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return (
            f"<SimulationOrder(id={self.id}, account='{self.account_name}', "
            f"{self.action} {self.symbol} x{self.shares}, status={self.status})>"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'account_name': self.account_name,
            'action': self.action,
            'order_type': self.order_type,
            'symbol': self.symbol,
            'shares': self.shares,
            'price_limit': float(self.price_limit) if self.price_limit else None,
            'status': self.status,
            'filled_shares': self.filled_shares,
            'avg_filled_price': float(self.avg_filled_price) if self.avg_filled_price else None,
            'reason': self.reason,
            'strategy_name': self.strategy_name,
            'signal_id': self.signal_id,
            'reject_reason': self.reject_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SimulationCashFlow(Base):
    """资金流水表 quant.simulation_cash_flow —— 所有资金变动必须经此表"""
    __tablename__ = 'simulation_cash_flow'
    __table_args__ = (
        Index('idx_simulation_cash_flow_account', 'account_name'),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False, comment='账户名称')
    flow_type = Column(String(20), nullable=False,
                       comment='deposit/buy_debit/sell_credit/fee/withdraw/dividend/adjustment')
    amount = Column(Numeric(15, 2), nullable=False, comment='有符号变动额')
    balance_after = Column(Numeric(15, 2), nullable=False, comment='变动后余额')
    ref_order_id = Column(Integer, comment='来源委托单')
    ref_trade_id = Column(Integer, comment='来源成交')
    created_at = Column(DateTime(timezone=False), default=datetime.now, comment='创建时间')

    def __repr__(self):
        return (
            f"<SimulationCashFlow(id={self.id}, account='{self.account_name}', "
            f"{self.flow_type} {self.amount}, balance={self.balance_after})>"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'account_name': self.account_name,
            'flow_type': self.flow_type,
            'amount': float(self.amount),
            'balance_after': float(self.balance_after),
            'ref_order_id': self.ref_order_id,
            'ref_trade_id': self.ref_trade_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SimulationEquitySnapshot(Base):
    """净值快照表 quant.simulation_equity_snapshot，(account_name, snapshot_date) 唯一"""
    __tablename__ = 'simulation_equity_snapshot'
    __table_args__ = (
        Index('simulation_equity_snapshot_account_date_key',
              'account_name', 'snapshot_date', unique=True),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False, comment='账户名称')
    snapshot_date = Column(Date, nullable=False, comment='快照日期')
    cash = Column(Numeric(15, 2), nullable=False, default=0, comment='现金')
    position_value = Column(Numeric(15, 2), nullable=False, default=0, comment='持仓市值')
    total_value = Column(Numeric(15, 2), nullable=False, default=0, comment='总资产')
    daily_return = Column(Numeric(10, 4), default=0, comment='日收益率')
    cumulative_return = Column(Numeric(10, 4), default=0, comment='累计收益率')
    drawdown = Column(Numeric(10, 4), default=0, comment='回撤')
    created_at = Column(DateTime(timezone=False), default=datetime.now, comment='创建时间')

    def __repr__(self):
        return (
            f"<SimulationEquitySnapshot(account='{self.account_name}', "
            f"date={self.snapshot_date}, total_value={self.total_value})>"
        )

    def to_dict(self):
        return {
            'account_name': self.account_name,
            'date': self.snapshot_date.isoformat() if self.snapshot_date else None,
            'cash': float(self.cash or 0),
            'position_value': float(self.position_value or 0),
            'total_value': float(self.total_value or 0),
            'daily_return': float(self.daily_return or 0),
            'cumulative_return': float(self.cumulative_return or 0),
            'drawdown': float(self.drawdown or 0),
        }


class SimulationPendingOrder(Base):
    """条件委托（挂单）表 quant.simulation_pending_orders

    非交易时段下的 execute_at='market_open' 挂单，
    开盘后 9:31 起由 daily_orchestrator MARKET_OPEN tick 自动撮合。
    """
    __tablename__ = 'simulation_pending_orders'
    __table_args__ = (
        Index('idx_simulation_pending_orders_account', 'account_name'),
        Index('idx_simulation_pending_orders_status', 'status'),
        CheckConstraint("action IN ('BUY','SELL')", name='simulation_pending_orders_action_check'),
        {'schema': 'quant'}
    )

    @validates('action')
    def _normalize_action(self, key, value):
        return normalize_action(value)

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False, comment='账户名称')
    symbol = Column(String(20), nullable=False, comment='股票代码')
    action = Column(String(10), nullable=False, comment='BUY/SELL（大写契约）')
    shares = Column(Integer, comment='委托数量（可空，与 amount 二选一）')
    amount = Column(Numeric(15, 2), comment='委托金额（可空，与 shares 二选一）')
    price_limit = Column(Numeric(10, 2), comment='限价')
    reason = Column(Text, comment='交易理由')
    execute_at = Column(String(20), nullable=False, default='market_open',
                        comment='撮合时机（market_open）')
    status = Column(String(20), nullable=False, default='pending',
                    comment='pending/executed/failed/cancelled')
    fail_reason = Column(Text, comment='撮合失败原因（护栏拒绝理由）')
    executed_trade_id = Column(Integer, comment='撮合成功后关联的 simulation_trades.id')
    created_at = Column(DateTime(timezone=False), default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime(timezone=False), default=datetime.now,
                        onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return (
            f"<SimulationPendingOrder(id={self.id}, account='{self.account_name}', "
            f"{self.action} {self.symbol}, status={self.status})>"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'account_name': self.account_name,
            'symbol': self.symbol,
            'action': self.action,
            'shares': self.shares,
            'amount': float(self.amount) if self.amount is not None else None,
            'price_limit': float(self.price_limit) if self.price_limit is not None else None,
            'reason': self.reason,
            'execute_at': self.execute_at,
            'status': self.status,
            'fail_reason': self.fail_reason,
            'executed_trade_id': self.executed_trade_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
