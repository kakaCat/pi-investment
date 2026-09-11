"""指数不得写入 daily_klines —— 补齐任务跳过指数（2026-09-11 w-f4aa1f6a）。

事故：data_backfiller 的指数分支取的是指数数据，却经同一保存路径写进 daily_klines，
撞上 daily_klines 的 CHECK chk_daily_klines_no_indexrows（指数已拆分到 quant.index_daily），
导致 2026-09-11 18:40 的补齐任务整批失败（事件 bbb56df6 / b376f70d / bc64397b）。

本测试锁定契约：指数符号必须在 backfill_symbol 入口被跳过（回报 skipped，非失败），
且**不得发起取数**（避免无谓网络与再犯）。
"""
import pytest

from application.services.data_backfiller import DataBackfiller


INDEX_CODES = ('399300', '399300.SZ', '000300')


def _make(monkeypatch, is_index):
    # __new__ 跳过依赖容器的 __init__；打桩指数判定与取数，避免触网/触库
    b = DataBackfiller.__new__(DataBackfiller)
    monkeypatch.setattr(DataBackfiller, '_is_index_symbol', lambda self, s: is_index(s), raising=True)

    fetched = []
    monkeypatch.setattr(DataBackfiller, '_fetch_index_klines',
                        lambda self, *a, **k: (fetched.append(a), {'success': False})[1], raising=True)
    monkeypatch.setattr(DataBackfiller, '_convert_klines', lambda self, *a, **k: [], raising=True)
    return b, fetched


@pytest.mark.parametrize('symbol', INDEX_CODES)
def test_index_symbol_skipped(monkeypatch, symbol):
    b, fetched = _make(monkeypatch, lambda s: s.startswith('399') or s in ('000300', '399300'))
    result = b.backfill_symbol(symbol, [{'start': '2026-09-11', 'end': '2026-09-11', 'days': 1}])

    assert result['skipped'] is True
    assert result['success'] is True, '跳过应计为成功，否则会把补齐任务打成失败'
    assert result['total_days_filled'] == 0
    assert 'index_daily' in result['message']
    assert fetched == [], '指数应直接跳过，不应发起取数'


def test_non_index_symbol_not_skipped(monkeypatch):
    b, fetched = _make(monkeypatch, lambda s: False)
    # 非指数：不会走 skipped 分支（此处仅断言分支不被误命中）
    try:
        result = b.backfill_symbol('600519', [{'start': '2026-09-11', 'end': '2026-09-11', 'days': 1}])
    except Exception:
        result = None  # 缺少真实依赖时的异常可接受，只要不是"被当成指数跳过"
    assert not (isinstance(result, dict) and result.get('skipped')), '真股票不得被指数分支跳过'


def test_is_index_symbol_uses_shared_classifier():
    """指数判定必须复用 utils.symbol_classifier（唯一口径），不得另起一套。"""
    import inspect

    from application.services import data_backfiller as mod

    src = inspect.getsource(mod)
    assert 'utils.symbol_classifier import is_index_symbol' in src
