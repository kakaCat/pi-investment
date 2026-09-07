"""
ORM Models模块

包含所有数据库表的SQLAlchemy Model定义

核心Model：
- Stock: 股票基础信息
- DailyKline: 日K线数据
- MinuteKline: 分钟K线数据
- Signal: 交易信号
- SignalExecution: 信号执行记录
- SimulationAccount: 模拟账户
- SimulationPosition: 模拟持仓
- SimulationTrade: 模拟交易记录

使用示例：
    from infrastructure.persistence.orm.models import Stock, DailyKline
    from infrastructure.persistence.orm import get_session

    session = get_session()
    stock = session.query(Stock).filter_by(symbol='000001').first()
    klines = session.query(DailyKline).filter_by(symbol='000001').limit(10).all()
"""

from .stock import Stock, DailyKline
from .kline import MinuteKline
from .signal import Signal, SignalExecution
from .simulation import (
    SimulationAccount, SimulationPosition, SimulationTrade,
    SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
    SimulationPendingOrder,
)
from .portfolio import PortfolioHolding
from .trade import Trade
from .factor import FactorValue
from .backtest import BacktestResult
from .scheduler import SchedulerTaskConfig, SchedulerRun
from .condition_rule import ConditionRule, ConditionResult
from .index_constituent import IndexConstituent
from .orchestrator import DailyOrchestratorState
from .market_perception import MarketRegime, MarketSentimentDaily, MarketTheme

__all__ = [
    # 股票相关
    'Stock',
    'DailyKline',
    'MinuteKline',
    'IndexConstituent',

    # 信号相关
    'Signal',
    'SignalExecution',

    # 模拟交易相关
    'SimulationAccount',
    'SimulationOrder',
    'SimulationCashFlow',
    'SimulationEquitySnapshot',
    'SimulationPosition',
    'SimulationTrade',
    'SimulationPendingOrder',

    # 持仓相关
    'PortfolioHolding',

    # 交易记录相关
    'Trade',

    # 因子相关
    'FactorValue',

    # 回测相关
    'BacktestResult',

    # 调度器相关
    'SchedulerTaskConfig',
    'SchedulerRun',

    # 条件监控相关
    'ConditionRule',
    'ConditionResult',

    # 编排器相关
    'DailyOrchestratorState',

    # M1 市场感知相关（RFC 007）
    'MarketRegime',
    'MarketSentimentDaily',
    'MarketTheme',
]
