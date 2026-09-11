"""交易状态仓储契约测试（fake session，不连库、不写库）

锁住的契约：
  只提供事实（is_st/is_suspended/is_delisted + 昨收），不做判定
  symbol 归一（600519.SH → 600519）；不在 stocks 表返回 None（调用方据此 fail-loud）
  昨收查询失败不致命（策略回退行情 prev_close），但必须回滚防线程毒化
  prev_close_date 必须一并返回（调用方要能识别 DB 陈旧）
"""
from types import SimpleNamespace

import pytest

import infrastructure.persistence.orm.base_repository as base_repo
from adapters.outbound.repositories.trading_status_repository import TradingStatusRepository


class FakeQuery:
    def __init__(self, first_result=None, error=None, log=None, label=''):
        self._first = first_result
        self._error = error
        self._log = log
        self._label = label
        self.filters = []
        self.orders = []

    def filter(self, *args):
        self.filters.append(args)
        return self

    def order_by(self, *args):
        self.orders.append(args)
        return self

    def first(self):
        if self._log is not None:
            self._log.append(self._label)
        if self._error:
            raise self._error
        return self._first


class FakeSession:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []
        self.rolled_back = 0

    def query(self, model):
        label = model.__name__
        self.calls.append(label)
        return self.mapping[label]

    def rollback(self):
        self.rolled_back += 1


@pytest.fixture
def patch_session(monkeypatch):
    def _apply(session):
        monkeypatch.setattr(base_repo, 'get_session', lambda: session)
        return session
    return _apply


def _stock(**overrides):
    data = {'symbol': '600519', 'name': '贵州茅台', 'market': 'SH', 'industry': '白酒',
            'is_st': False, 'is_suspended': False, 'is_delisted': False}
    data.update(overrides)
    return SimpleNamespace(**data)


def _kline(close=1688.0, trade_date='2026-09-10'):
    from datetime import date
    return SimpleNamespace(close=close,
                           trade_date=date.fromisoformat(trade_date) if trade_date else None)


def test_返回静态状态与昨收(patch_session):
    session = patch_session(FakeSession({
        'Stock': FakeQuery(_stock()),
        'DailyKline': FakeQuery(_kline()),
    }))
    status = TradingStatusRepository().get_stock_status('600519.SH')
    assert status['symbol'] == '600519', '库内统一无后缀'
    assert status['is_st'] is False and status['is_suspended'] is False
    assert status['prev_close'] == pytest.approx(1688.0)
    assert status['prev_close_date'] == '2026-09-10'
    assert status['source'] == 'stocks_table'


def test_股票不存在返回None(patch_session):
    patch_session(FakeSession({'Stock': FakeQuery(None), 'DailyKline': FakeQuery(None)}))
    assert TradingStatusRepository().get_stock_status('600519') is None


def test_空代码不打库(patch_session):
    session = patch_session(FakeSession({'Stock': FakeQuery(None), 'DailyKline': FakeQuery(None)}))
    assert TradingStatusRepository().get_stock_status('') is None
    assert session.calls == []


def test_ST与停牌标记原样透出不做判定(patch_session):
    patch_session(FakeSession({
        'Stock': FakeQuery(_stock(is_st=True, is_suspended=True, is_delisted=True)),
        'DailyKline': FakeQuery(None),
    }))
    status = TradingStatusRepository().get_stock_status('600519')
    assert (status['is_st'], status['is_suspended'], status['is_delisted']) == (True, True, True)
    assert status['prev_close'] is None and status['prev_close_date'] is None


def test_昨收缺失不致命但必须回滚(patch_session):
    session = patch_session(FakeSession({
        'Stock': FakeQuery(_stock()),
        'DailyKline': FakeQuery(error=RuntimeError('daily_klines 停更/连接异常')),
    }))
    status = TradingStatusRepository().get_stock_status('600519')
    assert status is not None and status['prev_close'] is None
    assert session.rolled_back == 1, '不回滚会毒化同线程后续查询'


def test_股票表查询异常向上抛且先回滚(patch_session):
    session = patch_session(FakeSession({
        'Stock': FakeQuery(error=RuntimeError('pg down')),
        'DailyKline': FakeQuery(None),
    }))
    with pytest.raises(RuntimeError):
        TradingStatusRepository().get_stock_status('600519')
    assert session.rolled_back == 1


def test_昨收为空值时返回None而不是0(patch_session):
    patch_session(FakeSession({
        'Stock': FakeQuery(_stock()),
        'DailyKline': FakeQuery(SimpleNamespace(close=None, trade_date=None)),
    }))
    status = TradingStatusRepository().get_stock_status('600519')
    assert status['prev_close'] is None and status['prev_close_date'] is None
