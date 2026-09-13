"""daily_klines 不得写入指数行（约束 chk_daily_klines_no_indexrows）。

背景（2026-09-11 18:40 / 2026-09-12 00:25-00:26，看板事件 bc64397b / d0f549d1 /
bbb56df6 / 585f5a3f / f1b3a7f8 共 11 次）：调用方漏过滤指数码时 upsert 撞 CHECK 约束
→ CheckViolation → 整批 K 线回滚、日志刷 error。
指数价格按 2026-09-11 分表设计存 quant.index_daily（键带市场后缀 399001.SZ），
daily_klines 只放个股 —— 修复是在 batch_insert_daily_klines 统一收口剔除。
"""
from datetime import date

from adapters.outbound.repositories.kline_repository import (
    KlineORMRepository,
    filter_index_rows,
)
from infrastructure.persistence.orm.models import DailyKline


def _kl(symbol: str) -> DailyKline:
    return DailyKline(
        symbol=symbol, trade_date=date(2026, 7, 13),
        open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0,
    )


def test_filter_keeps_stocks_and_drops_399_family():
    kept, dropped = filter_index_rows([_kl('399001'), _kl('600519'), _kl('399300')])
    assert [k.symbol for k in kept] == ['600519']
    assert dropped == ['399001', '399300']


def test_filter_is_idempotent_and_dedupes_reporting():
    kept, dropped = filter_index_rows([_kl('399006'), _kl('399006'), _kl('000001')])
    assert [k.symbol for k in kept] == ['000001']
    assert dropped == ['399006']


def test_filter_handles_empty_input():
    assert filter_index_rows([]) == ([], [])


def test_batch_insert_all_index_rows_returns_true_without_touching_db(monkeypatch):
    """全是指数行时直接返回 True，且不得访问 session（避免造 stocks 行 / 触发 INSERT）。"""

    class _Boom:
        def __getattr__(self, name):
            raise AssertionError(f'session 不应被访问（{name}）')

    monkeypatch.setattr(KlineORMRepository, 'session', property(lambda self: _Boom()))
    repo = object.__new__(KlineORMRepository)
    assert repo.batch_insert_daily_klines([_kl('399001'), _kl('399005')]) is True
