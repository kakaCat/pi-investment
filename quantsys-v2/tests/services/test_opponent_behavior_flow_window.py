"""OpponentBehaviorService 资金窗口、当日数据和文案契约测试。"""
from datetime import datetime

from qs_intel.application.services.opponent_behavior_service import OpponentBehaviorService


NOW = datetime(2026, 11, 18, 10, 0, 0)


def _row(trade_date, main=0.0, small=0.0, medium=0.0, large=0.0, big=0.0):
    return {
        'trade_date': trade_date,
        'total_main_flow': main,
        'total_small_flow': small,
        'total_medium_flow': medium,
        'total_large_flow': large,
        'total_big_flow': big,
    }


class FakeFundFlowRepo:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def get_market_aggregate_flow(self, start_date, end_date):
        self.calls.append((start_date, end_date))
        return [
            dict(row) for row in self.rows
            if start_date <= str(row['trade_date'])[:10] <= end_date
        ]

    def get_latest_trade_date(self):
        return max((str(row['trade_date'])[:10] for row in self.rows), default=None)

    def get_industry_aggregate_flow(self, trade_date):
        return []


def _service(rows):
    repo = FakeFundFlowRepo(rows)
    return OpponentBehaviorService(fund_flow_repo=repo, now_fn=lambda: NOW), repo


def test_window_metadata_is_cumulative_and_reads_repository_once():
    service, repo = _service([
        _row('2026-11-14', main=-500000, small=250000, medium=100000),
        _row('2026-11-17', main=-300000, small=100000, medium=50000),
    ])

    result = service.analyze_current_behavior()

    assert repo.calls == [('2026-11-14', '2026-11-18')]
    assert result['window'] == 'trailing_5d_cumulative'
    assert result['window_unit'] == 'calendar_days'
    assert result['start'] == '2026-11-14'
    assert result['end'] == '2026-11-18'
    assert result['as_of'] == '2026-11-17'
    assert result['source_rows'] == 2
    assert result['source_row_kind'] == 'daily_market_aggregate'
    assert result['has_current_day_data'] is False
    assert result['degraded'] is False

    retail = result['retail']
    institution = result['institution']
    assert retail['net_flow'] == 500000 * 10000
    assert institution['net_flow'] == -800000 * 10000
    assert retail['net_flow_scope'] == 'window_cumulative'
    assert institution['net_flow_scope'] == 'window_cumulative'
    assert retail['current_day_net_flow'] is None
    assert institution['current_day_net_flow'] is None
    assert retail['source_rows'] == 2
    assert institution['as_of'] == '2026-11-17'
    assert '正在' not in retail['description']
    assert '正在' not in institution['description']

    # 保留兼容枚举，但明确它只是资金组合，不允许直接推导价格位置/清仓动作。
    assert result['market_phase'] == 'distribution'
    assert result['market_phase_basis'] == 'fund_flow_combination_only'
    assert result['market_phase_requires_price_confirmation'] is True
    opportunity = result['opportunity_map']['avoid_institution'][0]
    text = opportunity['reason'] + opportunity['action']
    assert all(word not in text for word in ('顶部', '高位接盘', '清仓'))


def test_current_day_flow_is_separate_from_window_cumulative():
    service, _ = _service([
        _row('2026-11-17', main=10000, small=10000, medium=10000),
        _row('2026-11-18', main=-600000, small=-100000, medium=-50000),
    ])

    result = service.analyze_current_behavior()

    assert result['as_of'] == '2026-11-18'
    assert result['source_rows'] == 2
    assert result['current_day_source_rows'] == 1
    assert result['has_current_day_data'] is True
    assert result['institution']['net_flow'] == -590000 * 10000
    assert result['institution']['current_day_net_flow'] == -600000 * 10000
    assert result['retail']['current_day_net_flow'] == -150000 * 10000


def test_current_day_institution_flow_uses_same_main_fallback_as_window():
    service, _ = _service([
        _row('2026-11-18', main=0, large=-300000, big=-400000),
    ])

    result = service.analyze_current_behavior()

    assert result['institution']['net_flow'] == -700000 * 10000
    assert result['institution']['current_day_net_flow'] == -700000 * 10000


def test_no_flow_data_is_explicitly_degraded_with_window_metadata():
    service, repo = _service([])

    result = service.analyze_current_behavior()

    assert len(repo.calls) == 1
    assert result['degraded'] is True
    assert result['market_phase'] == 'unknown'
    assert result['source_rows'] == 0
    assert result['as_of'] is None
    assert result['has_current_day_data'] is False
    assert result['retail']['behavior'] == 'unknown'
    assert result['retail']['net_flow'] is None
    assert result['retail']['emotion_index'] is None
    assert result['institution']['net_flow'] is None
