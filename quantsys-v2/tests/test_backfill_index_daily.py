"""指数日线采集通道单测（2026-09-13，w-32314d00，修事件 81d8f56c）

背景：quant.index_daily 的两个采集通道修好之前，"16:30 跑成功但只有 T-1 数据 → exit 0"
没有任何地方会报警，表静默停在 09-10 而契约在 09-11/09-12 连判两次 high 违约。
本测试锁住三件事，防止回归：
  1. cutoff/字段归一（NaN volume/amount → 0，避免把 None 写进库）
  2. 新鲜度判定（滞后必须被识别为不新鲜；无基准时不误报）
  3. 指数键覆盖（000300.SH + 遗留键 399300.SZ 都必须有采集通道——
     漏一个，表级契约 quant.index_daily 就天天判违约）

纯函数测试，不碰生产库。
"""
from datetime import datetime
from math import nan

import pandas as pd
import pytest

from tools.backfill_index_daily import (
    EXIT_STALE,
    INDEX_SINA,
    evaluate_freshness,
    parse_deadline,
    select_rows,
)


def _df(rows):
    return pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])


def test_select_rows_drops_before_cutoff():
    df = _df([
        ['2026-08-01', 1.0, 1.0, 1.0, 1.0, 100, 1000],
        ['2026-08-14', 2.0, 2.0, 2.0, 2.0, 200, 2000],
        ['2026-09-11', 3.0, 3.0, 3.0, 3.0, 300, 3000],
    ])
    rows = select_rows(df, '2026-08-14', '000300.SH', 'sina:stock_zh_index_daily')
    assert [r['trade_date'] for r in rows] == ['2026-08-14', '2026-09-11']
    assert rows[0] == {
        'symbol': '000300.SH', 'trade_date': '2026-08-14',
        'open': 2.0, 'high': 2.0, 'low': 2.0, 'close': 2.0,
        'volume': 200.0, 'amount': 2000.0, 'source': 'sina:stock_zh_index_daily',
    }


def test_select_rows_normalizes_nan_volume_amount():
    """新浪偶尔不给 volume/amount；NaN/None 必须落成 0 而不是写进库。"""
    df = _df([['2026-09-11', 3.0, 3.0, 3.0, 3.0, nan, None]])
    row = select_rows(df, '2026-01-01', '399300.SZ', 'sina')[0]
    assert row['volume'] == 0.0 and row['amount'] == 0.0


def test_evaluate_freshness_ok():
    ok, detail = evaluate_freshness({'000300.SH': '2026-09-11', '399300.SZ': '2026-09-11'},
                                    '2026-09-11')
    assert ok is True and detail == []


def test_evaluate_freshness_flags_only_lagging_symbol():
    ok, detail = evaluate_freshness({'000300.SH': '2026-09-11', '399300.SZ': '2026-09-10'},
                                    '2026-09-11')
    assert ok is False
    assert len(detail) == 1 and '399300.SZ' in detail[0] and '2026-09-10' in detail[0]


def test_evaluate_freshness_without_reference_does_not_alarm():
    """daily_klines 不可读（market_latest=None）时不判滞后——不能让不可信基准造告警。"""
    ok, detail = evaluate_freshness({'000300.SH': '2026-09-10'}, None)
    assert ok is True and detail == []


def test_parse_deadline():
    ref = datetime(2026, 9, 13, 20, 50)
    assert parse_deadline('23:15', ref) == datetime(2026, 9, 13, 23, 15)
    assert parse_deadline(None, ref) is None
    assert parse_deadline('', ref) is None


def test_parse_deadline_rejects_garbage():
    with pytest.raises(ValueError):
        parse_deadline('23h15', datetime(2026, 9, 13, 20, 50))
    with pytest.raises(ValueError):
        parse_deadline('25:00', datetime(2026, 9, 13, 20, 50))


def test_legacy_399300_has_collection_channel():
    """回归：399300.SZ（深市沪深300，分表遗留键）在索引表里却没有采集通道，
    表级契约 quant.index_daily（整表 max(trade_date)）因此天天违约。"""
    assert '399300.SZ' in INDEX_SINA
    assert '000300.SH' in INDEX_SINA


def test_index_codes_use_market_prefixed_sina_code():
    for symbol, sina_code in INDEX_SINA.items():
        assert symbol[-3:] in ('.SH', '.SZ'), symbol
        assert sina_code[:2] in ('sh', 'sz') and sina_code[2:].isdigit(), sina_code


def test_stale_exit_code_is_nonzero():
    """fail-loud 的契约：滞后必须是非零退出码，否则 launchd 状态永远是 0。"""
    assert EXIT_STALE != 0
