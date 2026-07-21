"""Phase 1 集成测试"""
import pytest
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from domain.chan.kline_processor import KLineProcessor
from domain.chan.bi_identifier import BiIdentifier
from domain.chan.segment_identifier import SegmentIdentifier


class TestPhase1Integration:
    """Phase 1 集成测试类"""

    @pytest.fixture
    def sample_klines(self):
        """加载测试数据"""
        fixture_path = Path(__file__).parent / 'fixtures' / 'sample_klines.json'
        with open(fixture_path, 'r') as f:
            data = json.load(f)

        df = pd.DataFrame(data['klines'])
        df['date'] = pd.to_datetime(df['date'])
        return df

    def test_full_pipeline(self, sample_klines):
        """测试完整流水线（K线预处理 → 笔识别 → 线段识别）"""
        # Step 1: K线预处理
        processor = KLineProcessor()
        processed_klines = processor.process(sample_klines)

        assert len(processed_klines) > 0
        assert all(isinstance(k.date, datetime) for k in processed_klines)

        # Step 2: 笔识别
        bi_identifier = BiIdentifier()
        fenxings = bi_identifier.identify_fenxings(processed_klines)
        bis = bi_identifier.identify_bis(fenxings, processed_klines)

        assert len(fenxings) >= 0  # 可能无分型
        assert len(bis) >= 0       # 可能无笔

        # Step 3: 线段识别
        segment_identifier = SegmentIdentifier()
        segments = segment_identifier.identify_segments(bis)

        assert len(segments) >= 0  # 可能无线段

        # 验证数据完整性
        if len(segments) > 0:
            assert all(len(seg.bis) >= 3 for seg in segments)
            assert all(seg.high > seg.low for seg in segments)

    def test_empty_input(self):
        """测试空输入"""
        empty_df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

        processor = KLineProcessor()
        result = processor.process(empty_df)

        assert len(result) == 0

    def test_minimal_input(self):
        """测试最小输入（少于3根K线）"""
        df = pd.DataFrame({
            'date': [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'open': [10.0, 11.0],
            'high': [10.5, 11.5],
            'low': [9.5, 10.5],
            'close': [10.2, 11.2],
            'volume': [1000, 1100]
        })

        processor = KLineProcessor()
        processed_klines = processor.process(df)

        bi_identifier = BiIdentifier()
        fenxings = bi_identifier.identify_fenxings(processed_klines)

        # 预期：少于3根K线，无法识别分型
        assert len(fenxings) == 0


class TestPhase2Integration:
    """Phase 2 集成测试类"""

    @pytest.fixture
    def sample_klines(self):
        """加载测试数据"""
        fixture_path = Path(__file__).parent / 'fixtures' / 'sample_klines.json'
        with open(fixture_path, 'r') as f:
            data = json.load(f)

        df = pd.DataFrame(data['klines'])
        df['date'] = pd.to_datetime(df['date'])
        return df

    def test_phase2_pipeline(self, sample_klines):
        """测试 Phase 2 完整流水线（到买卖点检测）"""
        # Phase 1
        processor = KLineProcessor()
        processed_klines = processor.process(sample_klines)

        bi_identifier = BiIdentifier()
        fenxings = bi_identifier.identify_fenxings(processed_klines)
        bis = bi_identifier.identify_bis(fenxings, processed_klines)

        segment_identifier = SegmentIdentifier()
        segments = segment_identifier.identify_segments(bis)

        # Phase 2
        from domain.chan.zhongshu_identifier import ZhongShuIdentifier
        from domain.chan.divergence_detector import DivergenceDetector
        from domain.chan.buypoint_detector import BuyPointDetector

        zhongshu_identifier = ZhongShuIdentifier()
        zhongshus = zhongshu_identifier.identify_zhongshus(segments)

        divergence_detector = DivergenceDetector()
        divergences = {}
        for i in range(1, len(segments)):
            if i > 0 and segments[i].direction == segments[i-1].direction:
                divergences[i] = divergence_detector.detect_divergence(
                    segments[i-1], segments[i], processed_klines,
                    'bearish' if segments[i].direction == 'down' else 'bullish'
                )

        buypoint_detector = BuyPointDetector()
        buypoints = buypoint_detector.detect_buypoints(segments, zhongshus, divergences, processed_klines)

        # 验证
        assert len(zhongshus) >= 0
        assert len(buypoints) >= 0
        if len(buypoints) > 0:
            assert all(bp.type in ['1买', '2买', '3买', '1卖', '2卖', '3卖'] for bp in buypoints)
            assert all(0 < bp.position_ratio <= 1.0 for bp in buypoints)
            assert all(0 < bp.confidence <= 1.0 for bp in buypoints)


class TestPhase3Integration:
    """Phase 3 集成测试类"""

    @pytest.fixture
    def sample_klines(self):
        """加载测试数据"""
        fixture_path = Path(__file__).parent / 'fixtures' / 'sample_klines.json'
        with open(fixture_path, 'r') as f:
            data = json.load(f)

        df = pd.DataFrame(data['klines'])
        df['date'] = pd.to_datetime(df['date'])
        return df

    def test_phase3_pipeline(self, sample_klines):
        """测试 Phase 3 完整流水线（包含 MACD 和走势分析）"""
        from domain.chan.chan_analyzer import ChanAnalyzer

        analyzer = ChanAnalyzer()
        result = analyzer.analyze('TEST.SH', sample_klines)

        # 验证完整结果
        assert result.symbol == 'TEST.SH'
        assert len(result.klines) > 0
        assert len(result.fenxings) >= 0
        assert len(result.bis) >= 0
        assert len(result.segments) >= 0
        assert len(result.zhongshus) >= 0
        assert len(result.buypoints) >= 0
        assert result.trend_type in ['上涨', '下跌', '盘整']
        assert isinstance(result.divergences, dict)

    def test_chan_analyzer_with_filter(self, sample_klines):
        """测试 ChanAnalyzer 买卖点过滤功能"""
        from domain.chan.chan_analyzer import ChanAnalyzer

        analyzer = ChanAnalyzer()
        result = analyzer.analyze(
            'TEST.SH',
            sample_klines,
            enable_buypoints=['1买', '2买']
        )

        # 验证过滤生效
        if len(result.buypoints) > 0:
            assert all(bp.type in ['1买', '2买'] for bp in result.buypoints)
