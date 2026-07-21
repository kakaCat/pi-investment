"""缠论完整分析器测试"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from domain.chan.chan_analyzer import ChanAnalyzer


class TestChanAnalyzer:
    """缠论完整分析器测试类"""

    @pytest.fixture
    def sample_klines(self):
        """构造测试数据"""
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
        """测试完整分析流程"""
        analyzer = ChanAnalyzer()
        result = analyzer.analyze('600519.SH', sample_klines)

        # 验证返回结构
        assert result.symbol == '600519.SH'
        assert result.klines is not None
        assert result.fenxings is not None
        assert result.bis is not None
        assert result.segments is not None
        assert result.zhongshus is not None
        assert result.buypoints is not None
        assert result.trend_type in ['上涨', '下跌', '盘整']

    def test_analyze_with_buypoint_filter(self, sample_klines):
        """测试买卖点过滤"""
        analyzer = ChanAnalyzer()
        result = analyzer.analyze(
            '600519.SH',
            sample_klines,
            enable_buypoints=['1买', '2买']  # 只启用1买和2买
        )

        # 验证只有1买和2买
        if len(result.buypoints) > 0:
            assert all(bp.type in ['1买', '2买'] for bp in result.buypoints)
