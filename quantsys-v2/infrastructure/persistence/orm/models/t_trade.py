from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base


class TTradeCycle(Base):
    __tablename__ = "t_trade_cycles"
    __table_args__ = (
        CheckConstraint("upper_price > lower_price", name="chk_t_trade_cycles_range"),
        CheckConstraint("shares > 0 AND shares % 100 = 0", name="chk_t_trade_cycles_shares"),
        CheckConstraint(
            "mode IN ('remind_only','auto_sim')", name="chk_t_trade_cycles_mode"
        ),
        CheckConstraint(
            "status IN ('waiting_sell','waiting_buyback','completed','cancelled')",
            name="chk_t_trade_cycles_status",
        ),
        Index("idx_t_trade_cycles_account_status", "account", "status"),
        Index("idx_t_trade_cycles_symbol", "symbol"),
        Index(
            "uq_t_trade_cycles_active_symbol",
            "account",
            "symbol",
            unique=True,
            postgresql_where=text("status IN ('waiting_sell','waiting_buyback')"),
        ),
        {"schema": "quant"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(String(60), nullable=False)
    symbol = Column(String(20), nullable=False)
    mode = Column(String(20), nullable=False)
    status = Column(String(24), nullable=False, default="waiting_sell")
    upper_price = Column(Numeric(15, 4), nullable=False)
    lower_price = Column(Numeric(15, 4), nullable=False)
    shares = Column(Integer, nullable=False)
    available_shares_at_creation = Column(Integer, nullable=False)
    slippage_bps = Column(Numeric(8, 2), nullable=False, default=10)
    expected_gross_pnl = Column(Numeric(15, 2), nullable=False)
    expected_fees = Column(Numeric(15, 2), nullable=False)
    expected_slippage_cost = Column(Numeric(15, 2), nullable=False)
    expected_net_pnl = Column(Numeric(15, 2), nullable=False)
    reason = Column(String(500), nullable=False)
    invalidation = Column(Text, nullable=True)
    sell_trade_id = Column(Integer, nullable=True, unique=True)
    sell_price = Column(Numeric(15, 4), nullable=True)
    sell_commission = Column(Numeric(15, 2), nullable=True)
    sell_stamp_duty = Column(Numeric(15, 2), nullable=True)
    sell_transfer_fee = Column(Numeric(15, 2), nullable=True)
    sell_filled_at = Column(DateTime(timezone=False), nullable=True)
    buyback_trade_id = Column(Integer, nullable=True, unique=True)
    buyback_price = Column(Numeric(15, 4), nullable=True)
    buyback_commission = Column(Numeric(15, 2), nullable=True)
    buyback_stamp_duty = Column(Numeric(15, 2), nullable=True)
    buyback_transfer_fee = Column(Numeric(15, 2), nullable=True)
    buyback_filled_at = Column(DateTime(timezone=False), nullable=True)
    gross_pnl = Column(Numeric(15, 2), nullable=True)
    total_fees = Column(Numeric(15, 2), nullable=True)
    net_pnl = Column(Numeric(15, 2), nullable=True)
    sell_rule_id = Column(Integer, nullable=True)
    buyback_rule_id = Column(Integer, nullable=True)
    cancel_reason = Column(Text, nullable=True)
    rule_sync = Column(JSONB, nullable=True)
    lock_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime(timezone=False), nullable=True)
    cancelled_at = Column(DateTime(timezone=False), nullable=True)

    def to_dict(self):
        def number(value):
            return float(value) if value is not None else None

        def timestamp(value):
            return value.isoformat() if value is not None else None

        return {
            "id": self.id,
            "t_trade_id": self.id,
            "account": self.account,
            "symbol": self.symbol,
            "mode": self.mode,
            "status": self.status,
            "current_leg": (
                "sell" if self.status == "waiting_sell"
                else "buyback" if self.status == "waiting_buyback"
                else None
            ),
            "upper_price": number(self.upper_price),
            "lower_price": number(self.lower_price),
            "shares": self.shares,
            "available_shares_at_creation": self.available_shares_at_creation,
            "slippage_bps": number(self.slippage_bps),
            "expected_gross_pnl": number(self.expected_gross_pnl),
            "expected_fees": number(self.expected_fees),
            "expected_slippage_cost": number(self.expected_slippage_cost),
            "expected_net_pnl": number(self.expected_net_pnl),
            "reason": self.reason,
            "invalidation": self.invalidation,
            "sell_trade_id": self.sell_trade_id,
            "sell_price": number(self.sell_price),
            "sell_filled_at": timestamp(self.sell_filled_at),
            "buyback_trade_id": self.buyback_trade_id,
            "buyback_price": number(self.buyback_price),
            "buyback_filled_at": timestamp(self.buyback_filled_at),
            "gross_pnl": number(self.gross_pnl),
            "total_fees": number(self.total_fees),
            "net_pnl": number(self.net_pnl),
            "sell_rule_id": self.sell_rule_id,
            "buyback_rule_id": self.buyback_rule_id,
            "cancel_reason": self.cancel_reason,
            "rule_sync": self.rule_sync,
            "lock_version": self.lock_version,
            "created_at": timestamp(self.created_at),
            "updated_at": timestamp(self.updated_at),
            "completed_at": timestamp(self.completed_at),
            "cancelled_at": timestamp(self.cancelled_at),
        }
