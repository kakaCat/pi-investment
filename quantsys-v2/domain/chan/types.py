"""
缠论核心数据结构定义

所有数据类使用 @dataclass 装饰器，默认不可变（frozen=False，但业务逻辑不修改）
"""
from dataclasses import dataclass, field
from typing import List, Literal, Optional
from datetime import datetime


@dataclass
class KLine:
    """K线（处理包含关系后）"""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    original_indices: List[int] = field(default_factory=list)  # 原始K线索引（用于回溯）


@dataclass
class FenXing:
    """分型（顶分型/底分型）"""
    type: Literal['top', 'bottom']
    index: int              # 在处理后K线中的索引
    price: float            # 顶/底价格
    date: datetime
    klines: List[KLine] = field(default_factory=list)     # 构成分型的3根K线


@dataclass
class Bi:
    """笔"""
    direction: Literal['up', 'down']
    start_fenxing: FenXing
    end_fenxing: FenXing
    high: float
    low: float
    length: int             # 包含的K线数量
    price_change: float     # 涨跌幅


@dataclass
class Segment:
    """线段"""
    direction: Literal['up', 'down']
    bis: List[Bi] = field(default_factory=list)           # 构成线段的笔
    start_index: int = 0
    end_index: int = 0
    high: float = 0.0
    low: float = 0.0


@dataclass
class ZhongShu:
    """中枢（Phase 2 实现）"""
    segments: List[Segment] = field(default_factory=list)
    high: float = 0.0
    low: float = 0.0
    start_index: int = 0
    end_index: int = 0
    type: Literal['震荡', '扩展', '移动'] = '震荡'


@dataclass
class Trend:
    """走势类型（Phase 2 实现）"""
    type: Literal['上涨', '下跌', '盘整'] = '盘整'
    segments: List[Segment] = field(default_factory=list)
    zhongshus: List[ZhongShu] = field(default_factory=list)
    start_index: int = 0
    end_index: int = 0


@dataclass
class BuyPoint:
    """买卖点（Phase 2 实现）"""
    type: Literal['1买', '2买', '3买', '1卖', '2卖', '3卖'] = '1买'
    index: int = 0
    price: float = 0.0
    date: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    reason: str = ''
    stop_loss: float = 0.0
    stop_profit: float = 0.0
    position_ratio: float = 0.0


@dataclass
class ChanAnalysisResult:
    """完整分析结果"""
    symbol: str
    klines: List[KLine] = field(default_factory=list)
    fenxings: List[FenXing] = field(default_factory=list)
    bis: List[Bi] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    zhongshus: List[ZhongShu] = field(default_factory=list)
    trends: List[Trend] = field(default_factory=list)
    buypoints: List[BuyPoint] = field(default_factory=list)
    current_trend: Optional[Trend] = None
    latest_signal: Optional[BuyPoint] = None
