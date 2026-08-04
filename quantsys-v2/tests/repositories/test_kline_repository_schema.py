"""kline_repository rows→polars 显式 schema 测试

事故根因（2026-08-04）：pl.DataFrame(rows) 默认 infer_schema_length=100，
某列前 100 行全 NULL 被判 Null 类型，第 101+ 行非空值 append 崩溃：
- 300059: turnover_rate 前 2000 行 NULL，2026-06 起回填 0.0 → "could not append 0.0 f64"
- 002049: remark 含回填任务写入的错误字符串（前 100 行 NULL）→ "could not append str"
- 300274: amount 同类 → "could not append 1.0944e10 f64"
"""
import polars as pl
import pytest

from adapters.outbound.repositories.kline_repository import (
    _rows_to_df, _DAILY_KLINE_SCHEMA, _MINUTE_KLINE_SCHEMA,
)


def _daily_rows(null_column: str, late_value, n_null: int = 120, n_value: int = 5):
    """前 n_null 行 null_column=None，后 n_value 行 = late_value"""
    rows = []
    for i in range(n_null + n_value):
        rows.append({
            'symbol': '300059',
            'trade_date': f'2026-01-{(i % 28) + 1:02d}',
            'open': 10.0, 'high': 10.5, 'low': 9.5, 'close': 10.2,
            'volume': 1000.0, 'amount': 10200.0,
            'turnover_rate': None if null_column != 'turnover_rate' or i < n_null else late_value,
            'remark': None if null_column != 'remark' or i < n_null else late_value,
        })
    # 修正：只有目标列超过 100 行后才出现非空
    for i, r in enumerate(rows):
        if null_column == 'turnover_rate':
            r['turnover_rate'] = None if i < n_null else late_value
        if null_column == 'remark':
            r['remark'] = None if i < n_null else late_value
    return rows


class TestRowsToDfExplicitSchema:
    def test_late_float_after_100_nulls_no_crash(self):
        """turnover_rate 前 120 行 NULL、之后 0.0 → 不崩且值正确（300059 事故）"""
        rows = _daily_rows('turnover_rate', 0.0)
        df = _rows_to_df(rows, _DAILY_KLINE_SCHEMA)
        assert df.height == 125
        assert df['turnover_rate'].null_count() == 120
        assert df['turnover_rate'][-1] == 0.0

    def test_late_string_after_100_nulls_no_crash(self):
        """remark 前 120 行 NULL、之后错误字符串 → 不崩且值正确（002049 事故）"""
        rows = _daily_rows('remark', 'akshare returned no daily data after retry')
        df = _rows_to_df(rows, _DAILY_KLINE_SCHEMA)
        assert df.height == 125
        assert df['remark'].null_count() == 120
        assert df['remark'][-1] == 'akshare returned no daily data after retry'

    def test_large_float_after_nulls_no_overflow(self):
        """amount 大值（1e10）不溢出（300274 事故）"""
        rows = _daily_rows('turnover_rate', 0.0)
        rows[-1]['amount'] = 1.0944e10
        df = _rows_to_df(rows, _DAILY_KLINE_SCHEMA)
        assert df['amount'][-1] == 1.0944e10

    def test_fields_subset_schema(self):
        """fields 过滤后的 rows 只含部分键 → schema 取子集不崩"""
        rows = [{'symbol': '600519', 'trade_date': '2026-08-01', 'close': 1700.0}]
        df = _rows_to_df(rows, _DAILY_KLINE_SCHEMA)
        assert df.columns == ['symbol', 'trade_date', 'close']

    def test_empty_rows_returns_schema_df(self):
        df = _rows_to_df([], _DAILY_KLINE_SCHEMA)
        assert df.is_empty()
        assert 'turnover_rate' in df.columns

    def test_minute_schema(self):
        rows = [{'symbol': '600519', 'trade_datetime': '2026-08-01 09:30:00',
                 'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.05,
                 'volume': 100.0, 'amount': 105.0}]
        df = _rows_to_df(rows, _MINUTE_KLINE_SCHEMA)
        assert df.height == 1
        assert df['close'][0] == 1.05
