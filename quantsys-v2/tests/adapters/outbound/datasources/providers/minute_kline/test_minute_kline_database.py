"""本地 DB 分钟线 provider 契约测试（fake repository，不连库不写库）

锁住的契约：
  quant.minute_klines 无 period 列且**混存多粒度** → 粒度不一致必须拒绝返回（fail-loud），
  绝不把 1m 的 bar 当 5m 交给下游（"静默错误映射"事故类型）
  粒度推断不出时不用默认值伪装
  空缓存 / 窗口过滤后为空 → **空列表 + last_note**（健康无数据，见 base.py 三态契约，
  2026-09-11 P10 修复）；查询异常 / 粒度无法判定 → None + last_error（真故障）；
  latest_bar_datetime 如实透出
"""
from datetime import date, datetime, timedelta

import pytest

from adapters.outbound.datasources.providers.minute_kline.database import (
    DatabaseMinuteKlineProvider,
)
from domain.models.market_data import MinuteKline


class FakeMinuteRepo:
    def __init__(self, *, latest=None, rows=None, error=None):
        self.latest = latest
        self.rows = rows or []
        self.error = error
        self.calls = []

    def get_latest_minute_kline(self, symbol):
        self.calls.append(('latest', symbol))
        if self.error == 'latest':
            raise RuntimeError('pg down')
        return self.latest

    def get_minute_klines(self, symbol, start_dt, end_dt):
        self.calls.append(('range', symbol, start_dt, end_dt))
        if self.error == 'range':
            raise RuntimeError('pg down')
        return list(self.rows)


def _bars(day, times, period='5m', symbol='600150'):
    return [MinuteKline(symbol=symbol, trade_datetime=f'{day} {t}:00', open=10.0, high=10.5,
                        low=9.8, close=10.2, volume=100.0, amount=1020.0,
                        period=period, source='database_minute', timestamp='t')
            for t in times]


DAY = (date.today() - timedelta(days=100)).strftime('%Y-%m-%d')


def test_粒度不一致必须拒绝返回():
    """表内混存多粒度：请求 5m 但库内是 1m → 宁可不兜底也不能给错粒度。"""
    rows = _bars(DAY, ['09:31', '09:32', '09:33', '09:34'])
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(
        latest=type('L', (), {'trade_datetime': f'{DAY} 09:34:00'})(), rows=rows))
    assert provider.get_minute_klines('600150', '5m') is None
    assert '粒度' in provider.last_error and '1m' in provider.last_error


def test_粒度一致时返回并把period改写为推断值():
    rows = _bars(DAY, ['09:35', '09:40', '09:45', '09:50'])
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(rows=rows))
    bars = provider.get_minute_klines('600150', '5m', end_date=DAY)
    assert bars and all(b.period == '5m' for b in bars)
    assert provider.latest_bar_datetime == f'{DAY} 09:50:00'
    assert provider.granularity == '5m'


def test_粒度推断不出时不用默认值伪装():
    rows = _bars(DAY, ['09:35', '11:00'])   # 样本 <3，推断不出
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(rows=rows))
    assert provider.get_minute_klines('600150', '5m', end_date=DAY) is None
    assert '无法从数据推断粒度' in provider.last_error


def test_无缓存算健康无数据而不是故障():
    """P10：库内没有该标的的缓存是**正常**的（缓存本就只覆盖部分标的），
    不得写成 last_error —— 那会把这个兜底源计成故障直至熔断。"""
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(latest=None))
    assert provider.get_minute_klines('600150', '5m') == []
    assert provider.last_error is None, '无缓存不得写成 last_error（会触发熔断）'
    assert 'DB 无 600150 的分钟线缓存' in provider.last_note


def test_查询异常必须显式失败():
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(error='range'))
    assert provider.get_minute_klines('600150', '5m', end_date=DAY) is None
    assert 'pg down' in provider.last_error


def test_最新一根查询异常必须显式失败():
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(error='latest'))
    assert provider.get_minute_klines('600150', '5m') is None
    assert 'pg down' in provider.last_error


def test_非法周期不打库():
    repo = FakeMinuteRepo()
    provider = DatabaseMinuteKlineProvider(repo)
    assert provider.get_minute_klines('600150', '7m') is None
    assert repo.calls == []


def test_未给end_date时以库内最后一根为窗口右界():
    latest = type('L', (), {'trade_datetime': f'{DAY} 09:50:00'})()
    rows = _bars(DAY, ['09:35', '09:40', '09:45', '09:50'])
    repo = FakeMinuteRepo(latest=latest, rows=rows)
    provider = DatabaseMinuteKlineProvider(repo)
    provider.get_minute_klines('600150', '5m')
    kind, symbol, start_dt, end_dt = repo.calls[-1]
    assert end_dt.startswith(DAY) and end_dt.endswith('23:59:59')
    assert start_dt < end_dt


def test_窗口过滤后为空算健康无数据():
    rows = _bars('2020-01-02', ['09:35', '09:40', '09:45', '09:50'])
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(rows=rows))
    assert provider.get_minute_klines('600150', '5m', end_date=DAY,
                                      start_date=DAY) == []
    assert provider.last_error is None
    assert '过滤后' in provider.last_note


def test_每次调用重置last_note():
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(latest=None))
    provider.get_minute_klines('600150', '5m')
    assert provider.last_note
    rows = _bars(DAY, ['09:35', '09:40', '09:45', '09:50'])
    provider._repo = FakeMinuteRepo(rows=rows)
    provider.get_minute_klines('600150', '5m', end_date=DAY)
    assert provider.last_note == '', '命中数据后不得残留上一次的无数据说明'


def test_每次调用重置透出字段():
    rows = _bars(DAY, ['09:35', '09:40', '09:45', '09:50'])
    provider = DatabaseMinuteKlineProvider(FakeMinuteRepo(rows=rows))
    provider.get_minute_klines('600150', '5m', end_date=DAY)
    assert provider.granularity == '5m'
    provider.get_minute_klines('600150', '60m', end_date=DAY)
    assert provider.granularity in ('', '5m') and provider.last_error
    assert provider.last_note == '', '返回 None（故障）时不得同时留空结果说明'
