"""多数据源 K 线链路「无数据 vs 数据源故障」语义测试 — 2026-09-11 w-8f2c4cc5

背景：board 事件 7e66acac——GET /api/stock/600519/klines?start_date=2026-09-06&end_date=2026-09-06
（周日）触发链路 LocalDB 空 + Sina 过滤后空 + AKShare 网络异常，旧实现一律按 ERROR 上报
「❌ 所有数据源均失败」，于是「查非交易日」这种正常空结果变成看板错误事件。
"""
import pytest

from adapters.outbound.datasources.multi_source_data_fetcher import (
    MultiSourceDataFetcher,
    classify_chain_outcome,
    contains_weekday,
)


@pytest.mark.parametrize('start,end,want', [
    ('2026-09-06', '2026-09-06', False),   # 周日单日
    ('2026-09-05', '2026-09-06', False),   # 周六~周日
    ('2026-09-05', '2026-09-07', True),    # 跨到周一
    ('2026-09-09', '2026-09-10', True),    # 交易日
    ('bad-date', '2026-09-06', True),      # 格式异常不拦截
])
def test_contains_weekday(start, end, want):
    assert contains_weekday(start, end) is want


def test_weekend_only_range_skips_external_sources():
    """仅含周末的区间直接返回 None，不触碰外部源（否则必然空/异常并被误判为故障）。"""

    class _Boom:
        name = 'Boom'

        def fetch_klines(self, symbol, start_date, end_date):
            raise AssertionError('仅含周末的区间不应查询任何数据源')

    fetcher = MultiSourceDataFetcher()
    fetcher.sources = [_Boom()]
    assert fetcher.fetch_klines('600519', '2026-09-06', '2026-09-06') is None


def test_empty_but_healthy_sources_is_warning_not_error():
    level, message = classify_chain_outcome(
        '600519', '2026-09-06', '2026-09-06',
        empty_sources=['LocalDB', 'Sina'],
        errors=[('AKShare', RuntimeError('RemoteDisconnected'))],
    )
    assert level == 'warning', '有源正常返回但区间为空时不得按 ERROR 上报'
    assert '无K线数据' in message and 'LocalDB' in message


def test_all_sources_error_is_error():
    level, message = classify_chain_outcome(
        '600519', '2026-09-09', '2026-09-10',
        empty_sources=[],
        errors=[('LocalDB', RuntimeError('db down')), ('Sina', RuntimeError('timeout'))],
    )
    assert level == 'error'
    assert '所有数据源均失败' in message and 'db down' in message


def test_real_empty_business_day_still_warning():
    """真实交易日但无数据（停牌/新上市）同样属「无数据」，不应升级为故障事件。"""
    level, _ = classify_chain_outcome(
        '600519', '2026-09-09', '2026-09-10', empty_sources=['LocalDB', 'Sina', 'AKShare'], errors=[])
    assert level == 'warning'
