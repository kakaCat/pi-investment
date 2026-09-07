"""
资金流 Repository 与对手行为服务测试

覆盖 2026-07-28 修复的关键行为：
1. batch_upsert 幂等写入（symbol+trade_date 去重）
2. get_market_aggregate_flow 聚合口径（万元）与空表行为
3. OpponentBehaviorService 数据缺失时显式降级（degraded），
   不再静默返回 0.0 伪装「中性」
"""
import pytest
from datetime import datetime, timedelta

from adapters.outbound.repositories import FundFlowORMRepository
from adapters.outbound.repositories.fund_flow_repository import FundFlow
from application.services.opponent_behavior_service import OpponentBehaviorService


@pytest.fixture
def repo():
    return FundFlowORMRepository()


@pytest.fixture
def clean_table(repo):
    """每个测试前清空 stock_fund_flow（quant_test 库）"""
    repo.session.query(FundFlow).delete()
    repo.session.commit()
    yield
    repo.session.query(FundFlow).delete()
    repo.session.commit()


def _record(symbol='600519', trade_date='2026-07-27', main=100.0, small=-50.0):
    return {
        'symbol': symbol,
        'trade_date': trade_date,
        'close_price': 1300.0,
        'change_pct': 1.5,
        'main_net_inflow': main,
        'main_net_inflow_rate': 2.0,
        'large_net_inflow': main * 0.6 if main is not None else None,
        'large_net_inflow_rate': None,
        'big_net_inflow': main * 0.4 if main is not None else None,
        'big_net_inflow_rate': None,
        'medium_net_inflow': None,
        'medium_net_inflow_rate': None,
        'small_net_inflow': small,
        'small_net_inflow_rate': None,
        'source': 'test',
    }


class TestFundFlowRepository:
    """资金流仓储"""

    def test_batch_upsert_and_latest(self, repo, clean_table):
        """upsert 写入后 get_latest_fund_flow 可取回"""
        count = repo.batch_upsert([_record()])
        assert count == 1

        rows = repo.get_latest_fund_flow('600519', days=5)
        assert len(rows) == 1
        assert rows[0]['symbol'] == '600519'
        assert float(rows[0]['main_net_inflow']) == 100.0
        assert rows[0]['updated_at'] is not None

    def test_batch_upsert_idempotent(self, repo, clean_table):
        """同一 symbol+trade_date 重复 upsert 不重复插行，且值被更新"""
        repo.batch_upsert([_record(main=100.0)])
        repo.batch_upsert([_record(main=200.0)])

        rows = repo.get_latest_fund_flow('600519', days=5)
        assert len(rows) == 1
        assert float(rows[0]['main_net_inflow']) == 200.0

    def test_market_aggregate_flow(self, repo, clean_table):
        """市场聚合：按日分组求和，单位万元"""
        repo.batch_upsert([
            _record('600519', main=100.0, small=-40.0),
            _record('000001', main=200.0, small=-60.0),
        ])

        flows = repo.get_market_aggregate_flow('2026-07-27', '2026-07-27')
        assert len(flows) == 1
        assert flows[0]['total_main_flow'] == 300.0
        assert flows[0]['total_small_flow'] == -100.0

    def test_market_aggregate_empty(self, repo, clean_table):
        """空表返回空列表（调用方据此显式降级）"""
        assert repo.get_market_aggregate_flow('2026-07-27', '2026-07-28') == []

    def test_latest_trade_date(self, repo, clean_table):
        assert repo.get_latest_trade_date() is None
        repo.batch_upsert([_record()])
        assert repo.get_latest_trade_date() == '2026-07-27'


class TestOpponentBehaviorDegraded:
    """对手行为服务降级语义"""

    def test_degraded_when_no_data(self, clean_table):
        """无资金流数据时：behavior=unknown + degraded=True，
        绝不能返回 net_flow=0 伪装中性（2026-07-28 前的 bug）"""
        svc = OpponentBehaviorService()
        result = svc.analyze_current_behavior()

        assert result['degraded'] is True
        assert result['retail']['behavior'] == 'unknown'
        assert result['retail']['net_flow'] is None
        assert result['retail']['degraded'] is True
        assert result['institution']['behavior'] == 'unknown'
        assert result['institution']['net_flow'] is None
        assert result['market_phase'] == 'unknown'

    def test_real_analysis_with_data(self, repo, clean_table):
        """有数据时给出真实流向（万元→元换算正确）"""
        end = datetime.now()
        start = end - timedelta(days=5)
        repo.batch_upsert([
            _record(trade_date=start.strftime('%Y-%m-%d'), main=10000.0, small=-30000.0),
        ])

        svc = OpponentBehaviorService()
        result = svc.analyze_current_behavior()

        assert result['degraded'] is False
        # 机构（主力）= 10000万 = 1亿元
        assert result['institution']['net_flow'] == 10000.0 * 10000
        # 散户（小单+中单）= -30000万 = -3亿元
        assert result['retail']['net_flow'] == -30000.0 * 10000


class TestSentimentScoreGuard:
    """情绪评分边界（pos == total 在 0==0 时不得加分）"""

    def test_empty_index_performance_no_score(self):
        from application.services.market_sentiment_service import MarketSentimentService
        svc = MarketSentimentService(data_service=None)

        score_empty = svc._calculate_sentiment_score({
            'advance_decline': {'error': '无数据'},
            'volume': {'error': '无数据'},
            'index': {'indices': {}, 'positive_count': 0, 'total_count': 0},
            'volatility': {'error': '无数据'},
            'new_high_low': {'error': '无数据'},
        })
        # 全部维度失败时必须保持基准分 50，不因 0==0 误加 25 分
        assert score_empty == 50.0
