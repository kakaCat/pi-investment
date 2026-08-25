"""
M1 市场感知服务单元测试（RFC 007）

测试覆盖：
- Regime 判定规则（10 条：5 档 regime + 5 边界条件）
- 数据源容错（3 条）
- 边界条件（3 条）

总计：16 条单元测试
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from application.services.market_perception_service import (
    MarketPerceptionService,
    PANIC_SENTIMENT,
    PANIC_INDEX_5D_PCT,
    EUPHORIA_SENTIMENT,
    EUPHORIA_VOLUME_RATIO,
    EUPHORIA_UP_PCT,
    TREND_5D_THRESHOLD_PCT,
    COVERAGE_MIN,
    THEME_MIN_LIMIT_UP,
)


# ==============================================================================
# Phase 1: Regime 判定规则测试（10 条）
# ==============================================================================

class TestRegimeClassification:
    """测试 regime 判定规则（RFC 007 §3）"""

    def test_classify_regime_panic(self):
        """测试 panic 判定：情绪≤20, 量能<1.0, 指数5日<-3.0"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=15,           # ≤20
            volume_ratio=0.8,       # <1.0
            up_pct=20,              # 不影响
            chg5d=-4.5,             # <-3.0
            close=3000,
            ma20=3100,
            ma60=3200
        )
        assert regime == 'panic', "情绪15 + 量能0.8 + 5日跌4.5% 应判定为 panic"

    def test_classify_regime_euphoria(self):
        """测试 euphoria 判定：情绪≥80, 量能>2.0, 涨家占比>70%"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=85,           # ≥80
            volume_ratio=2.5,       # >2.0
            up_pct=75,              # >70%
            chg5d=1.0,              # 不影响
            close=3100,
            ma20=3050,
            ma60=3000
        )
        assert regime == 'euphoria', "情绪85 + 量能2.5 + 涨家75% 应判定为 euphoria"

    def test_classify_regime_trend_up(self):
        """测试 trend_up：close>MA20>MA60, 5日>1.0%"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=60,           # 中性
            volume_ratio=1.2,
            up_pct=55,
            chg5d=1.5,              # >1.0
            close=3200,             # >MA20
            ma20=3100,              # >MA60
            ma60=3000
        )
        assert regime == 'trend_up', "close>MA20>MA60 + 5日涨1.5% 应判定为 trend_up"

    def test_classify_regime_trend_down(self):
        """测试 trend_down：close<MA20<MA60, 5日<-1.0%"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=40,           # 中性
            volume_ratio=0.9,
            up_pct=40,
            chg5d=-1.5,             # <-1.0
            close=3000,             # <MA20
            ma20=3100,              # <MA60
            ma60=3200
        )
        assert regime == 'trend_down', "close<MA20<MA60 + 5日跌1.5% 应判定为 trend_down"

    def test_classify_regime_range_fallback(self):
        """测试 range 兜底：不满足任何明确条件"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=50,           # 中性
            volume_ratio=1.0,       # 正常
            up_pct=50,              # 中性
            chg5d=0.5,              # 小幅波动
            close=3100,             # ≈MA20
            ma20=3100,              # ≈MA60
            ma60=3100
        )
        assert regime == 'range', "指标全部中性应兜底判定为 range"


class TestRegimeBoundaryConditions:
    """测试 regime 判定边界条件（5 条）"""

    def test_classify_regime_panic_boundary(self):
        """测试 panic 边界：情绪=20（刚好触线）"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=20,           # =20（边界值，<=20 触发）
            volume_ratio=0.99,      # <1.0
            up_pct=25,
            chg5d=-3.1,             # <-3.0（需要严格小于）
            close=3000,
            ma20=3100,
            ma60=3200
        )
        assert regime == 'panic', "情绪20（边界）+ 量能0.99 + 5日跌3.1% 应判定为 panic"

    def test_classify_regime_euphoria_boundary(self):
        """测试 euphoria 边界：情绪=80, 量能=2.0, 涨家占比=70%"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=80,           # =80（边界值）
            volume_ratio=2.0,       # =2.0（边界值）
            up_pct=70,              # =70%（边界值）
            chg5d=0.5,
            close=3100,
            ma20=3050,
            ma60=3000
        )
        # 注意：>2.0 才触发，=2.0 不触发 euphoria，应降级到其他判定
        # 根据条件：close>ma20>ma60 + chg5d=0.5<1.0 → 不满足 trend_up → range
        assert regime == 'range', "量能=2.0（边界不触发）应降级到 range"

    def test_classify_regime_trend_up_boundary(self):
        """测试 trend_up 边界：5日涨幅=1.0%（边界不触发）"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=60,
            volume_ratio=1.2,
            up_pct=55,
            chg5d=1.0,              # =1.0%（边界值，>1.0 才触发）
            close=3200,             # >MA20
            ma20=3100,              # >MA60
            ma60=3000
        )
        assert regime == 'range', "5日涨1.0%（边界不触发）应降级到 range"

    def test_classify_regime_trend_down_boundary(self):
        """测试 trend_down 边界：5日跌幅=-1.0%（边界不触发）"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=40,
            volume_ratio=0.9,
            up_pct=40,
            chg5d=-1.0,             # =-1.0%（边界值，<-1.0 才触发）
            close=3000,             # <MA20
            ma20=3100,              # <MA60
            ma60=3200
        )
        assert regime == 'range', "5日跌1.0%（边界不触发）应降级到 range"

    def test_classify_regime_priority_panic_over_trend_down(self):
        """测试优先级：panic > trend_down（同时满足时 panic 优先）"""
        regime = MarketPerceptionService._classify_regime(
            sentiment=15,           # panic 条件
            volume_ratio=0.7,       # panic 条件
            up_pct=30,
            chg5d=-4.0,             # 同时满足 panic 和 trend_down
            close=2900,             # trend_down 条件
            ma20=3100,              # trend_down 条件
            ma60=3200
        )
        assert regime == 'panic', "同时满足 panic 和 trend_down 时，panic 优先"


# ==============================================================================
# Phase 2: 数据源容错测试（3 条）
# ==============================================================================

class TestDataSourceResilience:
    """测试数据源容错机制"""

    @patch('adapters.outbound.datasources.manager.get_data_provider_manager')
    def test_index_trend_provider_failure(self, mock_mgr):
        """测试指数数据源返回失败"""
        # Mock 数据源返回失败
        mock_provider = Mock()
        mock_provider.get_index_daily.return_value = {'success': False}
        mock_mgr.return_value = mock_provider

        svc = MarketPerceptionService()
        result = svc._index_trend('2026-08-25')

        assert result is None, "数据源失败应返回 None"
        mock_provider.get_index_daily.assert_called_once()

    @patch('adapters.outbound.datasources.manager.get_data_provider_manager')
    def test_index_trend_insufficient_history(self, mock_mgr):
        """测试指数历史不足 60 日"""
        # Mock 返回少于 60 条记录
        mock_provider = Mock()
        mock_data = Mock()
        mock_data.data = {'records': [{'close': 3000, 'date': f'2026-08-{i:02d}'} for i in range(1, 51)]}
        mock_provider.get_index_daily.return_value = {
            'success': True,
            'data': mock_data
        }
        mock_mgr.return_value = mock_provider

        svc = MarketPerceptionService()
        result = svc._index_trend('2026-08-25')

        assert result is None, "历史不足 60 日应返回 None"

    def test_snapshot_sentiment_service_error(self):
        """测试情绪计算服务异常"""
        # Mock DataService
        mock_ds = Mock()

        svc = MarketPerceptionService(ds=mock_ds)

        # Mock MarketSentimentService 异常
        with patch('application.services.market_sentiment_service.MarketSentimentService') as mock_sentiment_cls:
            mock_sentiment = Mock()
            mock_sentiment.analyze_market_sentiment.side_effect = Exception("计算失败")
            mock_sentiment_cls.return_value = mock_sentiment

            result = svc._snapshot_sentiment('2026-08-25')

            assert result['stored'] is False, "服务异常应返回 stored=False"
            assert 'error' in result, "应包含 error 字段"


# ==============================================================================
# Phase 3: 边界条件测试（3 条）
# ==============================================================================

class TestBoundaryConditions:
    """测试边界条件"""

    def test_coverage_partial_threshold(self):
        """测试 coverage=4000 边界（刚好不 partial）"""
        # Mock MarketSentimentService 返回 coverage=4000
        mock_ds = Mock()
        svc = MarketPerceptionService(ds=mock_ds)

        with patch('application.services.market_sentiment_service.MarketSentimentService') as mock_sentiment_cls:
            mock_sentiment = Mock()
            mock_sentiment.analyze_market_sentiment.return_value = {
                'fear_greed_index': 50,
                'indicators': {
                    'advance_decline': {
                        'up_count': 2000,
                        'down_count': 1500,
                        'flat_count': 500,
                        'ratio': 1.33,
                        'data_date': '2026-08-25',
                    },
                    'new_high_low': {
                        'new_high_count': 100,
                        'new_low_count': 80,
                    },
                    'volume': {
                        'volume_ratio': 1.2,
                        'recent_avg_volume': 500000000,
                    },
                    'volatility': {
                        'volatility': 0.015,
                    },
                }
            }
            mock_sentiment_cls.return_value = mock_sentiment

            # Mock Repository
            svc.sentiment_repo = Mock()
            svc.sentiment_repo.upsert.return_value = True

            result = svc._snapshot_sentiment('2026-08-25')

            assert result.get('stored') is True, "coverage=4000 应成功落库"
            assert result.get('partial') is False, "coverage≥4000 应 partial=False"

    def test_coverage_partial_below_threshold(self):
        """测试 coverage=3999（刚好 partial）"""
        mock_ds = Mock()
        svc = MarketPerceptionService(ds=mock_ds)

        with patch('application.services.market_sentiment_service.MarketSentimentService') as mock_sentiment_cls:
            mock_sentiment = Mock()
            mock_sentiment.analyze_market_sentiment.return_value = {
                'fear_greed_index': 50,
                'indicators': {
                    'advance_decline': {
                        'up_count': 2000,
                        'down_count': 1500,
                        'flat_count': 499,  # 总和 3999
                        'ratio': 1.33,
                        'data_date': '2026-08-25',
                    },
                    'new_high_low': {
                        'new_high_count': 100,
                        'new_low_count': 80,
                    },
                    'volume': {
                        'volume_ratio': 1.2,
                        'recent_avg_volume': 500000000,
                    },
                    'volatility': {
                        'volatility': 0.015,
                    },
                }
            }
            mock_sentiment_cls.return_value = mock_sentiment

            # Mock Repository
            svc.sentiment_repo = Mock()
            svc.sentiment_repo.upsert.return_value = True

            result = svc._snapshot_sentiment('2026-08-25')

            assert result.get('stored') is True, "coverage 不影响落库"
            assert result.get('partial') is True, "coverage<4000 应 partial=True"

    def test_themes_min_limit_up_boundary(self):
        """测试 ≥3 只涨停成团边界"""
        # Mock 涨停池：行业A 2只（不成团）、行业B 3只（刚好成团）
        records = [
            # 行业A：2只（不成团）
            {'代码': '600000', '名称': 'A1', '所属行业': '行业A', '涨跌幅': 10.0, '封板资金': 5000},
            {'代码': '600001', '名称': 'A2', '所属行业': '行业A', '涨跌幅': 10.0, '封板资金': 4000},
            # 行业B：3只（刚好成团）
            {'代码': '600010', '名称': 'B1', '所属行业': '行业B', '涨跌幅': 10.0, '封板资金': 6000},
            {'代码': '600011', '名称': 'B2', '所属行业': '行业B', '涨跌幅': 10.0, '封板资金': 5500},
            {'代码': '600012', '名称': 'B3', '所属行业': '行业B', '涨跌幅': 10.0, '封板资金': 5000},
        ]

        top = MarketPerceptionService._cluster_top_themes(records, top_n=3)

        assert len(top) == 1, f"只有行业B成团，应返回1个主题，实际返回{len(top)}个"
        assert top[0][0] == '行业B', "应该是行业B"
        assert len(top[0][1]) == 3, "行业B应该有3只股票"


# ==============================================================================
# Phase 4: 集成测试辅助（可选，用于后续扩展）
# ==============================================================================

class TestIntegrationHelpers:
    """集成测试辅助方法（可用于后续端到端测试）"""

    def test_build_reason_format(self):
        """测试 reason 字段格式"""
        reason = MarketPerceptionService._build_reason(
            sentiment=65,
            volume_ratio=1.35,
            up_pct=58.5,
            chg5d=1.8,
            close=3200,
            ma20=3150,
            ma60=3100,
            regime='trend_up',
            prefix='[测试] '
        )

        assert '[测试] 情绪65' in reason, "应包含情绪值"
        assert '量能1.35' in reason, "应包含量能比"
        assert '涨家占比58.5%' in reason, "应包含涨家占比"
        assert '指数5日+1.8%' in reason, "应包含5日涨跌幅"
        assert 'close>MA20' in reason, "应包含均线关系"
        assert 'MA20>MA60' in reason, "应包含均线关系"
        assert 'trend_up' in reason, "应包含判定结果"

    def test_cluster_top_themes_sorting(self):
        """测试主线排序逻辑（涨停数 > 封板资金）"""
        records = [
            # 行业A：5只，封板资金少
            *[{'代码': f'60000{i}', '名称': f'A{i}', '所属行业': '行业A',
               '涨跌幅': 10.0, '封板资金': 3000} for i in range(5)],
            # 行业B：4只，封板资金多
            *[{'代码': f'60001{i}', '名称': f'B{i}', '所属行业': '行业B',
               '涨跌幅': 10.0, '封板资金': 10000} for i in range(4)],
        ]

        top = MarketPerceptionService._cluster_top_themes(records, top_n=2)

        assert len(top) == 2, "应返回2个主题"
        assert top[0][0] == '行业A', "涨停数多的行业应排第一（5 > 4）"
        assert len(top[0][1]) == 5, "行业A应该有5只"
        assert top[1][0] == '行业B', "行业B应排第二"


# ==============================================================================
# 运行测试
# ==============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
