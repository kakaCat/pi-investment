"""缠论完整分析器 - 一站式分析接口（笔中枢版流水线，2026-08-05 重构）"""
from typing import List
import pandas as pd
from dataclasses import dataclass, field
from .types import KLine, FenXing, Bi, Segment, BiZhongShu, BuyPoint
from .kline_processor import KLineProcessor
from .bi_identifier import BiIdentifier
from .bi_zhongshu_identifier import BiZhongShuIdentifier
from .buypoint_detector import BuyPointDetector
from .bi_trend_analyzer import BiTrendAnalyzer


@dataclass
class ChanAnalysisResult:
    """缠论分析结果"""
    symbol: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]          # 契约保留，恒为空（线段层已弃用）
    zhongshus: List[BiZhongShu]
    buypoints: List[BuyPoint]
    trend_type: str
    divergences: dict = field(default_factory=dict)


class ChanAnalyzer:
    """缠论完整分析器（笔中枢版）"""

    def __init__(self):
        self.kline_processor = KLineProcessor()
        self.bi_identifier = BiIdentifier()
        self.zhongshu_identifier = BiZhongShuIdentifier()
        self.buypoint_detector = BuyPointDetector()
        self.trend_analyzer = BiTrendAnalyzer()

    def analyze(
        self,
        symbol: str,
        klines_df: pd.DataFrame,
        enable_buypoints: List[str] = None,
    ) -> ChanAnalysisResult:
        if enable_buypoints is None:
            enable_buypoints = ['1买', '2买', '3买', '1卖', '2卖', '3卖']

        processed_klines = self.kline_processor.process(klines_df)
        fenxings = self.bi_identifier.identify_fenxings(processed_klines)
        bis = self.bi_identifier.identify_bis(fenxings, processed_klines)

        zhongshus = self.zhongshu_identifier.identify(bis)
        buypoints = self.buypoint_detector.detect(
            bis, zhongshus, processed_klines, enable_types=enable_buypoints)
        trend_type = self.trend_analyzer.analyze(bis, zhongshus)

        return ChanAnalysisResult(
            symbol=symbol,
            klines=processed_klines,
            fenxings=fenxings,
            bis=bis,
            segments=[],               # 线段层已弃用（2026-08-05，原算法退化）
            zhongshus=zhongshus,
            buypoints=buypoints,
            trend_type=trend_type,
            divergences={},
        )
