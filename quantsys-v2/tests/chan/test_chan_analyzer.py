"""缠论完整分析器测试（笔中枢版流水线）"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from domain.chan.chan_analyzer import ChanAnalyzer


class TestChanAnalyzer:
    @pytest.fixture
    def sample_klines(self):
        data = []
        for i in range(100):
            data.append({
                'date': datetime(2024, 1, 1) + timedelta(days=i),
                'open': 10.0 + i * 0.1,
                'high': 11.0 + i * 0.1,
                'low': 9.0 + i * 0.1,
                'close': 10.5 + i * 0.1,
                'volume': 1000
            })
        return pd.DataFrame(data)

    def test_analyze_full_pipeline(self, sample_klines):
        analyzer = ChanAnalyzer()
        result = analyzer.analyze('600519.SH', sample_klines)

        assert result.symbol == '600519.SH'
        assert result.klines is not None
        assert result.fenxings is not None
        assert result.bis is not None
        assert result.segments == []            # 线段层已弃用，契约返回空
        assert result.zhongshus is not None     # 笔中枢列表（BiZhongShu）
        assert result.buypoints is not None
        assert result.trend_type in ['上涨', '下跌', '盘整']

    def test_analyze_with_buypoint_filter(self, sample_klines):
        analyzer = ChanAnalyzer()
        result = analyzer.analyze('600519.SH', sample_klines,
                                  enable_buypoints=['1买', '2买'])
        if len(result.buypoints) > 0:
            assert all(bp.type in ['1买', '2买'] for bp in result.buypoints)
