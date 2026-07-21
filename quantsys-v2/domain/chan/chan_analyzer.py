"""缠论完整分析器 - 一站式分析接口"""
from typing import List
import pandas as pd
from dataclasses import dataclass
from .types import KLine, FenXing, Bi, Segment, ZhongShu, BuyPoint
from .kline_processor import KLineProcessor
from .bi_identifier import BiIdentifier
from .segment_identifier import SegmentIdentifier
from .zhongshu_identifier import ZhongShuIdentifier
from .divergence_detector import DivergenceDetector
from .buypoint_detector import BuyPointDetector
from .trend_analyzer import TrendAnalyzer


@dataclass
class ChanAnalysisResult:
    """缠论分析结果"""
    symbol: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]
    zhongshus: List[ZhongShu]
    buypoints: List[BuyPoint]
    trend_type: str
    divergences: dict


class ChanAnalyzer:
    """
    缠论完整分析器

    封装 Phase 1 & 2 & 3 所有功能
    提供一站式分析接口
    """

    def __init__(self):
        self.kline_processor = KLineProcessor()
        self.bi_identifier = BiIdentifier()
        self.segment_identifier = SegmentIdentifier()
        self.zhongshu_identifier = ZhongShuIdentifier()
        self.divergence_detector = DivergenceDetector()
        self.buypoint_detector = BuyPointDetector()
        self.trend_analyzer = TrendAnalyzer()

    def analyze(
        self,
        symbol: str,
        klines_df: pd.DataFrame,
        enable_buypoints: List[str] = ['1买', '2买', '3买', '1卖', '2卖', '3卖']
    ) -> ChanAnalysisResult:
        """
        完整缠论分析流程

        Args:
            symbol: 股票代码
            klines_df: K线 DataFrame
            enable_buypoints: 启用的买卖点类型

        Returns:
            ChanAnalysisResult
        """
        # Phase 1: 基础结构识别
        processed_klines = self.kline_processor.process(klines_df)
        fenxings = self.bi_identifier.identify_fenxings(processed_klines)
        bis = self.bi_identifier.identify_bis(fenxings, processed_klines)
        segments = self.segment_identifier.identify_segments(bis)

        # Phase 2: 中枢和背驰
        zhongshus = self.zhongshu_identifier.identify_zhongshus(segments)

        divergences = {}
        for i in range(1, len(segments)):
            if i > 0 and segments[i].direction == segments[i-1].direction:
                divergences[i] = self.divergence_detector.detect_divergence(
                    segments[i-1], segments[i], processed_klines,
                    'bearish' if segments[i].direction == 'down' else 'bullish'
                )

        buypoints = self.buypoint_detector.detect_buypoints(
            segments, zhongshus, divergences, processed_klines
        )

        # 过滤买卖点
        buypoints = [bp for bp in buypoints if bp.type in enable_buypoints]

        # Phase 3: 走势类型分析
        trend_type = self.trend_analyzer.analyze(segments, zhongshus)

        return ChanAnalysisResult(
            symbol=symbol,
            klines=processed_klines,
            fenxings=fenxings,
            bis=bis,
            segments=segments,
            zhongshus=zhongshus,
            buypoints=buypoints,
            trend_type=trend_type,
            divergences=divergences
        )
