"""K 线回填不得写入指数行（daily_klines 约束 chk_daily_klines_no_indexrows）。

背景（2026-09-12 00:25，看板事件 585f5a3f）：evening_pipeline 回填 399001（深证成指）
撞 CHECK 约束 → CheckViolation → 该批 K 线整批回滚、日志刷 error。
指数价格按 2026-09-11 分表设计存 quant.index_daily（键带市场后缀 399001.SZ），
daily_klines 只放个股 —— 修复是在建 stocks 元数据之前拦截，避免造出假个股行。
"""
import pytest

from adapters.outbound.datasources.manager import DataProviderManager
from utils.symbol_classifier import is_index_symbol


class _DbReached(BaseException):
    """哨兵：证明流程真的走到了取 DB session（BaseException 不会被 except Exception 吞掉）。"""


def _boom():
    raise _DbReached()


def test_is_index_symbol_detects_399_family():
    # 399 族走短路径判定，不需要查库
    assert is_index_symbol('399001') is True
    assert is_index_symbol('399300') is True


def test_backfill_skips_index_symbol_before_db(monkeypatch):
    monkeypatch.setattr('utils.symbol_classifier.is_index_symbol', lambda s: True)
    monkeypatch.setattr('infrastructure.persistence.orm.config.get_session', _boom)
    mgr = object.__new__(DataProviderManager)
    assert mgr._backfill_klines_to_db('399001', []) is False


def test_backfill_does_not_over_block_real_stock(monkeypatch):
    monkeypatch.setattr('utils.symbol_classifier.is_index_symbol', lambda s: False)
    monkeypatch.setattr('infrastructure.persistence.orm.config.get_session', _boom)
    mgr = object.__new__(DataProviderManager)
    with pytest.raises(_DbReached):
        mgr._backfill_klines_to_db('600519', [])
