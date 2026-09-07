"""
回测相关Model

包含：
1. BacktestResult - 回测结果
"""
from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime, BigInteger,
    Index, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from ..base import Base

__all__ = ['BacktestResult']


class BacktestResult(Base):
    """回测结果表

    对应数据库表：quant.backtest_results
    主键：id
    """
    __tablename__ = 'backtest_results'
    __table_args__ = (
        # 索引
        Index('idx_backtest_results_strategy_name', 'strategy_name'),
        Index('idx_backtest_results_symbol', 'symbol'),
        Index('idx_backtest_results_sharpe_ratio', 'sharpe_ratio'),
        Index('idx_backtest_results_created_at_desc', 'created_at'),
        # Schema
        {'schema': 'quant'}
    )

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='回测ID')

    # 策略信息
    strategy_name = Column(Text, nullable=False, comment='策略名称')
    symbol = Column(Text, comment='股票代码（单股票策略）')
    parameters = Column(JSONB, comment='策略参数（JSON）')

    # 回测时间范围
    start_date = Column(Date, nullable=False, comment='开始日期')
    end_date = Column(Date, nullable=False, comment='结束日期')

    # 资金信息
    initial_capital = Column(Float, nullable=False, comment='初始资金')
    final_capital = Column(Float, nullable=False, comment='最终资金')

    # 收益指标
    total_return = Column(Float, comment='总收益率')
    annual_return = Column(Float, comment='年化收益率')

    # 风险指标
    sharpe_ratio = Column(Float, comment='夏普比率')
    max_drawdown = Column(Float, comment='最大回撤')

    # 交易统计
    total_trades = Column(Integer, comment='总交易次数')
    winning_trades = Column(Integer, comment='盈利交易次数')
    losing_trades = Column(Integer, comment='亏损交易次数')
    win_rate = Column(Float, comment='胜率')

    # 盈亏统计
    avg_win = Column(Float, comment='平均盈利')
    avg_loss = Column(Float, comment='平均亏损')
    profit_factor = Column(Float, comment='盈亏比')

    # 详细数据（JSON）
    equity_curve = Column(JSONB, comment='净值曲线（JSON）')
    trade_details = Column(JSONB, comment='交易明细（JSON）')

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        comment='创建时间'
    )

    def __repr__(self):
        return (
            f"<BacktestResult(id={self.id}, strategy='{self.strategy_name}', "
            f"return={self.total_return:.2%}, sharpe={self.sharpe_ratio:.2f})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'parameters': self.parameters,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'equity_curve': self.equity_curve,
            'trade_details': self.trade_details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
