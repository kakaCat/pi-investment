"""显式 K 线修复与盘中日 K 防污染回归。"""
from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from adapters.inbound.fastapi_app.routes import data_sync_async
from qs_market_data.adapters.outbound.datasources.manager import DataProviderManager
from qs_market_data.adapters.outbound.datasources.providers.kline.base import KlineData
from qs_market_data.application.services.data_backfiller import DataBackfiller
from qs_ops.infrastructure.jobs.kline_update_job import _keep_completed_klines


def _row(source='akshare', volume=210_828_300, close=5.49):
    return KlineData(
        symbol='002027', date='2026-11-13', open=5.27, high=5.52,
        low=5.26, close=close, volume=volume, amount=1_155_000_000,
        source=source,
    )


class Provider:
    def __init__(self, name, row):
        self.name = name
        self.row = row

    def get_klines(self, *args):
        return [self.row]


class Manager:
    def __init__(self, providers):
        self.kline_providers = providers
        self.calls = []

    def _try_providers(self, providers, method, symbol, period, start, end):
        self.calls.append((providers[0].name, start, end))
        provider = providers[0]
        rows = provider.get_klines(symbol, period, start, end)
        return {'success': True, 'data': rows, 'source': provider.name}


class Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dicts(self):
        return list(self.rows)


class Repo:
    def __init__(self):
        self.row = {
            'trade_date': '2026-11-13', 'open': 5.27, 'high': 5.30,
            'low': 5.26, 'close': 5.29, 'volume': 4_574_200,
        }
        self.saves = []

    def get_daily_klines(self, *args, **kwargs):
        assert kwargs.get('raise_on_error') is True
        return Frame([self.row] if self.row else [])

    def save_daily_klines(self, rows):
        self.saves.append(rows)
        self.row = rows[0]
        return len(rows)


def _backfiller(monkeypatch, providers):
    repo = Repo()
    manager = Manager(providers)
    backfiller = DataBackfiller(kline_repo=repo, data_source_manager=manager)
    monkeypatch.setattr(backfiller, '_is_index_symbol', lambda _symbol: False)
    return backfiller, repo


def test_force_repair_bypasses_db_cross_validates_and_reads_back(monkeypatch):
    backfiller, repo = _backfiller(monkeypatch, [
        Provider('database', _row(source='database', close=5.29, volume=4_574_200)),
        Provider('akshare', _row()),
        Provider('sina', _row(source='sina', volume=210_828_333)),
    ])

    result = backfiller.repair_daily_kline('002027', '2026-11-13', source='akshare')

    assert result['success'] is True
    assert result['primary_source'] == 'akshare'
    assert result['confirmation_source'] == 'sina'
    assert backfiller.data_source_manager.calls == [
        ('akshare', '2026-11-13', '2026-11-13'),
        ('sina', '2026-11-13', '2026-11-13'),
    ]
    assert result['before'][0]['close'] == 5.29
    assert result['after'][0]['close'] == 5.49
    assert result['after'][0]['volume'] == 210_828_300
    assert result['after'][0]['source'] == 'akshare'
    assert len(repo.saves) == 1


def test_force_repair_disagreement_is_quarantined_without_write(monkeypatch):
    backfiller, repo = _backfiller(monkeypatch, [
        Provider('akshare', _row()),
        Provider('sina', _row(source='sina', volume=4_574_200, close=5.29)),
    ])

    with pytest.raises(RuntimeError, match='双源日 K 不一致'):
        backfiller.repair_daily_kline('002027', '2026-11-13', source='akshare')
    assert repo.saves == []
    assert repo.row['close'] == 5.29


def test_force_repair_requires_independent_confirmation(monkeypatch):
    backfiller, repo = _backfiller(monkeypatch, [Provider('akshare', _row())])
    with pytest.raises(RuntimeError, match='没有可用的独立网络 K 线确认源'):
        backfiller.repair_daily_kline('002027', '2026-11-13', source='akshare')
    assert repo.saves == []


def test_manager_drops_intraday_snapshot_before_backfill_and_keeps_eod():
    yesterday = _row()
    yesterday.date = '2026-11-16'
    today = _row()
    today.date = '2026-11-17'

    morning = DataProviderManager._completed_daily_rows(
        [yesterday, today], now=datetime(2026, 11, 17, 9, 35),
    )
    evening = DataProviderManager._completed_daily_rows(
        [yesterday, today], now=datetime(2026, 11, 17, 15, 5),
    )

    assert [r.date for r in morning] == ['2026-11-16']
    assert [r.date for r in evening] == ['2026-11-16', '2026-11-17']


def test_manager_real_get_klines_never_backfills_intraday_snapshot(monkeypatch):
    from qs_market_data.adapters.outbound.datasources import manager as manager_module

    class MorningDatetime:
        @staticmethod
        def now():
            return datetime(2026, 11, 17, 9, 35)

    monkeypatch.setattr(manager_module, '_datetime', MorningDatetime)
    yesterday = _row()
    yesterday.date = '2026-11-16'
    today = _row()
    today.date = '2026-11-17'
    manager = DataProviderManager.__new__(DataProviderManager)
    manager.kline_providers = []
    manager._try_providers = lambda *args: {
        'success': True, 'data': [yesterday, today], 'source': 'sina',
    }
    manager._backfill_klines_to_db = Mock()
    manager._ensure_amount = Mock()

    result = manager.get_klines('002027', 'daily', '20261116', '20261117')

    assert result['dropped_unclosed_daily_bars'] == 1
    manager._backfill_klines_to_db.assert_called_once()
    assert [r.date for r in manager._backfill_klines_to_db.call_args.args[1]] == ['2026-11-16']


def test_job_second_defense_filters_after_completed_target():
    yesterday = _row()
    yesterday.date = '2026-11-16'
    today = _row()
    today.date = '2026-11-17'
    assert [r.date for r in _keep_completed_klines([yesterday, today], '2026-11-16')] == ['2026-11-16']


def test_route_force_branch_uses_repair_not_normal_backfill(monkeypatch):
    calls = []

    class FakeBackfiller:
        def __init__(self, kline_repo):
            pass

        def repair_daily_kline(self, symbol, trade_date, source):
            calls.append((symbol, trade_date, source))
            return {'success': True, 'saved': 1, 'symbol': symbol, 'cross_validated': True}

        def backfill_batch(self, **kwargs):
            raise AssertionError('force 不得走常规回填')

    monkeypatch.setattr(data_sync_async, 'KlineORMRepository', lambda: object())
    monkeypatch.setattr(data_sync_async, 'DataBackfiller', FakeBackfiller)
    response = data_sync_async.sync_daily_klines(data_sync_async.KlineSyncRequest(
        date='2026-11-13', symbols=['002027'], force=True, source='akshare',
    ))

    assert calls == [('002027', '2026-11-13', 'akshare')]
    assert response.success is True
    assert response.total_rows == 1
    assert response.details[0]['cross_validated'] is True


def test_route_force_without_symbols_is_rejected():
    with pytest.raises(HTTPException) as exc:
        data_sync_async.sync_daily_klines(data_sync_async.KlineSyncRequest(
            date='2026-11-13', force=True,
        ))
    assert exc.value.status_code == 400
