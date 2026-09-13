"""pool_change_log.symbol 列宽契约（2026-09-13，w-32314d00，看板事件 c4cade93 / bcea3fe8）。

背景：StockPoolService._log_change 写的是批量摘要 ','.join(symbols[:50])，
一张 5 只票的池子 refresh 即 34 字符；列原为 varchar(20) → StringDataRightTruncation，
变更日志整条写入失败（fail-soft 只打 warning，审计留痕静默丢失，共 6 次事件）。
本用例锁住「symbol 列必须能容纳批量摘要」这一契约，防止再次被改窄。
"""
from sqlalchemy import Text

from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog


def test_symbol_column_is_unbounded_text():
    col = PoolChangeLog.__table__.c.symbol
    assert isinstance(col.type, Text), (
        'pool_change_log.symbol 必须是无长度限制的 Text —— 它存的是批量摘要'
        '（如 002916,000988,300207,688795,000807 = 34 字符），改窄会让变更日志静默丢失'
    )
    assert getattr(col.type, "length", None) is None


def test_batch_summary_exceeds_old_varchar_20():
    """记录当时触发故障的真实取值长度，避免有人误以为 20 够用。"""
    joined = ','.join(['002916', '000988', '300207', '688795', '000807'])
    assert len(joined) == 34
    assert len(joined) > 20
