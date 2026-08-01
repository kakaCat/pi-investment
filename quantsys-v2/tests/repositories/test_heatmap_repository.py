"""HeatmapRepository 交易日/窗口收盘价查询测试（真实 quant_test DB）"""
from datetime import date

import pytest

from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
from infrastructure.persistence.orm.models.stock import DailyKline, Stock

# 用 2009 年的日期避免与 quant_test 中其他测试数据冲突
D0 = date(2009, 1, 5)   # 周一
D1 = date(2009, 1, 6)
D2 = date(2009, 1, 7)


@pytest.fixture
def seeded():
    repo = HeatmapRepository()
    s = repo.session
    s.add_all([
        Stock(symbol='TST001', name='测试一', industry='测试半导体', market='A', market_cap=100.0),
        Stock(symbol='TST002', name='测试二', industry='测试半导体', market='A', market_cap=50.0),
    ])
    for sym, c0, c1 in [('TST001', 10.0, 11.0), ('TST002', 20.0, 18.0)]:
        s.add_all([
            DailyKline(symbol=sym, trade_date=D0, open=c0, high=c0, low=c0, close=c0, volume=1, amount=1),
            DailyKline(symbol=sym, trade_date=D1, open=c1, high=c1, low=c1, close=c1, volume=1, amount=1),
        ])
    s.commit()
    yield repo
    for sym in ('TST001', 'TST002'):
        s.query(DailyKline).filter(DailyKline.symbol == sym).delete()
        s.query(Stock).filter(Stock.symbol == sym).delete()
    s.commit()


class TestTradeDates:
    def test_last_trade_date_on_or_before(self, seeded):
        assert seeded.get_last_trade_date_on_or_before(date(2009, 1, 6)) >= D1

    def test_trade_dates_from(self, seeded):
        dates = seeded.get_trade_dates_from(D0, 2)
        assert dates[0] == D0
        assert dates[1] == D1
        assert len(dates) == 2

    def test_trade_dates_partial_when_not_enough(self, seeded):
        # 只要 4 个交易日，但只播了 2 天（且更晚的日期若存在也属于其他数据，
        # 本用例只断言返回列表不为空且首日正确——partial 判定在 service 层）
        dates = seeded.get_trade_dates_from(D0, 4)
        assert dates[0] == D0


class TestWindowCloses:
    def test_window_closes(self, seeded):
        closes = seeded.get_window_closes(['TST001', 'TST002'], D0, D1)
        assert closes['TST001'] == {'close_d0': 10.0, 'close_dn': 11.0}
        assert closes['TST002'] == {'close_d0': 20.0, 'close_dn': 18.0}

    def test_window_closes_empty_symbols(self, seeded):
        assert seeded.get_window_closes([], D0, D1) == {}
