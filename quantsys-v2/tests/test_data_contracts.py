"""数据契约校验器单测（步3 契约驱动监控，2026-09-11，w-f4aa1f6a）

用 SQLite 内存库跑**真实 SQL**（同一套检查逻辑），不碰生产库——
生产库连接在 engine._resolve_db_dsn() 里有 pytest 硬拦截（库名必须以 _test 结尾）。

覆盖：freshness 通过/违约、value_ranges、rowcount 下限、uniqueness、nullability、
      market_latest 完整性门槛、expected_trading_day 墙钟/日历口径、fingerprint 稳定性、
      退出码语义、标识符注入防护、error_events 行构造。
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine

from tools.check_data_contracts import (
    FINGERPRINT_PREFIX,
    UPSTREAM_SOURCE,
    UPSERT_EVENT,
    CheckContext,
    Contract,
    InfraError,
    SqlRunner,
    build_event_row,
    compute_expected_trading_day,
    compute_market_latest,
    evaluate_contract,
    exit_code_for,
    fingerprint_for,
    summarize,
)


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def run():
    """SQLite 内存库；ATTACH 'quant' 让 quant.<table> 这种真实限定名也能跑。"""
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS quant")
        conn.exec_driver_sql(
            'CREATE TABLE quant.daily_klines (symbol TEXT, trade_date TEXT, close REAL)')
        conn.exec_driver_sql(
            'CREATE TABLE quant.trading_calendar (trade_date TEXT, exchange TEXT, '
            'is_trading_day BOOLEAN)')
        conn.exec_driver_sql(
            'CREATE TABLE equity (account_name TEXT, snapshot_date TEXT, total_value REAL)')
        conn.exec_driver_sql(
            'CREATE TABLE bench (symbol TEXT, trade_date TEXT, close REAL)')
        conn.exec_driver_sql('CREATE TABLE empty_t (a TEXT)')
        conn.exec_driver_sql('CREATE TABLE dup_t (account_name TEXT, symbol TEXT)')
        conn.exec_driver_sql('CREATE TABLE nn_t (a TEXT, b TEXT)')
    return SqlRunner(engine)


def _ctx(run, market_latest=None, expected=None, calendar_available=False, today=date(2026, 9, 11)):
    return CheckContext(run=run, market_latest=market_latest, expected_trading_day=expected,
                        calendar_available=calendar_available, today=today)


def _c(dataset='ds', table='equity', schema=None, **kw):
    return Contract(dataset=dataset, table_name=table, table_schema=schema, **kw)


def _insert(run, table, rows, cols):
    from sqlalchemy import text
    placeholders = ', '.join(f':p{i}' for i in range(len(cols)))
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    with run.engine.begin() as conn:
        for r in rows:
            conn.execute(text(sql), {f'p{i}': v for i, v in enumerate(r)})


# ---------------------------------------------------------------------------
# freshness
# ---------------------------------------------------------------------------
def test_freshness_market_latest_pass(run):
    _insert(run, 'bench', [('000300.SH', '2026-09-09', 4500.0),
                           ('000300.SH', '2026-09-10', 4548.39)], ['symbol', 'trade_date', 'close'])
    c = _c('quant.index_daily:000300.SH', 'bench', severity='high',
           freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 0,
                      'filter': {'symbol': '000300.SH'}})
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    assert [r.status for r in res] == ['pass']
    assert res[0].severity == 'high'
    assert '已达标' in res[0].detail


def test_freshness_market_latest_fail_when_lagging(run):
    _insert(run, 'bench', [('000300.SH', '2026-08-27', 4400.0)], ['symbol', 'trade_date', 'close'])
    c = _c('quant.index_daily:000300.SH', 'bench', severity='high',
           freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 0,
                      'filter': {'symbol': '000300.SH'}})
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    assert res[0].status == 'fail'
    assert res[0].severity == 'high'
    assert '滞后 14 自然日' in res[0].detail
    assert res[0].observed == '2026-08-27'
    assert exit_code_for(res) == 1


def test_freshness_lag_within_tolerance_passes(run):
    _insert(run, 'equity', [('a', '2026-09-07', 1.0)], ['account_name', 'snapshot_date', 'total_value'])
    c = _c('ds', 'equity', freshness={'column': 'snapshot_date', 'mode': 'market_latest',
                                      'max_lag_days': 3})
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    assert res[0].status == 'pass'


def test_freshness_empty_table_fails(run):
    c = _c('ds', 'empty_t', severity='high',
           freshness={'column': 'a', 'mode': 'market_latest'})
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    assert res[0].status == 'fail'
    assert '无任何' in res[0].detail


def test_freshness_without_reference_skips(run):
    _insert(run, 'equity', [('a', '2026-09-07', 1.0)], ['account_name', 'snapshot_date', 'total_value'])
    c = _c('ds', 'equity', freshness={'column': 'snapshot_date', 'mode': 'market_latest'})
    res = evaluate_contract(c, _ctx(run, market_latest=None))
    assert res[0].status == 'skip'
    assert exit_code_for(res) == 0


def test_freshness_expected_trading_day_holiday_slack_vs_strict_calendar(run):
    # 最新=参考日前 3 个交易日
    _insert(run, 'equity', [('a', '2026-09-08', 1.0)], ['account_name', 'snapshot_date', 'total_value'])
    _insert(run, 'quant.trading_calendar',
            [('2026-09-09', 'SSE', 1), ('2026-09-10', 'SSE', 1), ('2026-09-11', 'SSE', 1)],
            ['trade_date', 'exchange', 'is_trading_day'])
    cfg = {'column': 'snapshot_date', 'mode': 'expected_trading_day',
           'max_lag_weekdays': 1, 'holiday_slack_weekdays': 5}
    # ① 交易日历不可用（降级口径）→ 1 + 5 冗余 = 6 容忍 → 通过
    res = evaluate_contract(_c('ds', 'equity', freshness=cfg),
                            _ctx(run, expected=date(2026, 9, 11), calendar_available=False))
    assert res[0].status == 'pass'
    # ② 日历可用 → 按日历数 3 个交易日，超出容忍 1 → 违约
    res2 = evaluate_contract(_c('ds', 'equity', freshness=cfg),
                             _ctx(run, expected=date(2026, 9, 11), calendar_available=True))
    assert res2[0].status == 'fail'
    assert '滞后 3 交易日' in res2[0].detail


def test_freshness_unknown_mode_is_infra_error(run):
    with pytest.raises(InfraError):
        evaluate_contract(_c('ds', 'equity',
                             freshness={'column': 'snapshot_date', 'mode': 'nonsense'}),
                          _ctx(run, market_latest=date(2026, 9, 10)))


# ---------------------------------------------------------------------------
# market_latest 完整性门槛 & expected_trading_day 口径
# ---------------------------------------------------------------------------
def test_market_latest_skips_incomplete_day(run):
    rows = [('600000', '2026-09-10', 1.0)] * 5 + [('600000', '2026-09-11', 1.0)]
    _insert(run, 'quant.daily_klines', rows, ['symbol', 'trade_date', 'close'])
    latest, raw, note = compute_market_latest(run, min_rows=5)
    assert latest == date(2026, 9, 10)
    assert raw == date(2026, 9, 11)
    assert '未完整交易日' in note


def test_market_latest_complete_day_wins(run):
    rows = [('600000', '2026-09-10', 1.0)] * 5 + [('600000', '2026-09-11', 1.0)] * 5
    _insert(run, 'quant.daily_klines', rows, ['symbol', 'trade_date', 'close'])
    latest, raw, note = compute_market_latest(run, min_rows=5)
    assert latest == raw == date(2026, 9, 11)
    assert note == ''


def test_market_latest_empty_table_returns_none(run):
    latest, raw, note = compute_market_latest(run, min_rows=5)
    assert (latest, raw) == (None, None)
    assert '无任何数据' in note


@pytest.mark.parametrize('now,expected', [
    (datetime(2026, 9, 11, 10, 0), date(2026, 9, 10)),   # 周五盘中（早于收盘+同步窗口）→ 上一个交易日
    (datetime(2026, 9, 11, 17, 0), date(2026, 9, 11)),   # 周五收盘后 → 当天
    (datetime(2026, 9, 12, 17, 0), date(2026, 9, 11)),   # 周六 → 回退到周五
])
def test_expected_trading_day_weekday_fallback(run, now, expected):
    got, cal = compute_expected_trading_day(run, now)
    assert got == expected
    assert cal is False  # 日历表为空 → 降级口径


def test_expected_trading_day_prefers_calendar(run):
    _insert(run, 'quant.trading_calendar',
            [('2026-09-10', 'SSE', 1), ('2026-09-11', 'SSE', 1), ('2026-09-12', 'SSE', 0)],
            ['trade_date', 'exchange', 'is_trading_day'])
    got, cal = compute_expected_trading_day(run, datetime(2026, 9, 12, 17, 0))
    assert got == date(2026, 9, 11)
    assert cal is True


# ---------------------------------------------------------------------------
# value_ranges / rowcount / uniqueness / nullability
# ---------------------------------------------------------------------------
def test_value_range_fail_and_pass(run):
    _insert(run, 'equity', [('a', '2026-09-10', 100.0), ('b', '2026-09-10', 0.0), ('c', '2026-09-10', -5.0)],
            ['account_name', 'snapshot_date', 'total_value'])
    c = _c('ds', 'equity', severity='high',
           value_ranges=[{'column': 'total_value', 'op': '>', 'value': 0, 'severity': 'high'}])
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    assert res[0].status == 'fail'
    assert res[0].observed == 2
    assert exit_code_for(res) == 1


def test_value_range_ignores_nulls(run):
    _insert(run, 'equity', [('a', '2026-09-10', None), ('b', '2026-09-10', 1.0)],
            ['account_name', 'snapshot_date', 'total_value'])
    c = _c('ds', 'equity', value_ranges=[{'column': 'total_value', 'op': '>', 'value': 0}])
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    assert res[0].status == 'pass'


def test_value_range_rejects_bad_operator(run):
    c = _c('ds', 'equity', value_ranges=[{'column': 'total_value', 'op': '; DROP TABLE', 'value': 0}])
    with pytest.raises(InfraError):
        evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))


def test_rowcount_min_fails_on_empty_table(run):
    c = _c('quant.trading_calendar', 'trading_calendar', schema='quant', severity='high',
           rowcount={'min': 1, 'severity': 'high'})
    res = evaluate_contract(c, _ctx(run))
    assert res[0].status == 'fail'
    assert res[0].check == 'rowcount'
    assert '空表' in res[0].detail
    assert exit_code_for(res) == 1


def test_rowcount_min_max_and_filter(run):
    _insert(run, 'bench', [('000300.SH', '2026-09-10', 1.0), ('399006.SZ', '2026-09-10', 1.0)],
            ['symbol', 'trade_date', 'close'])
    ok = evaluate_contract(_c('ds', 'bench', rowcount={'min': 1, 'max': 10}),
                           _ctx(run))[0]
    assert ok.status == 'pass'
    filtered = evaluate_contract(
        _c('ds', 'bench', rowcount={'min': 2, 'filter': {'symbol': '000300.SH'}}), _ctx(run))[0]
    assert filtered.status == 'fail'
    assert filtered.observed == 1
    too_many = evaluate_contract(_c('ds', 'bench', rowcount={'min': 1, 'max': 1}), _ctx(run))[0]
    assert too_many.status == 'fail'


def test_uniqueness(run):
    _insert(run, 'dup_t', [('a', '600000'), ('a', '600000'), ('a', '600519')],
            ['account_name', 'symbol'])
    c = _c('ds', 'dup_t', uniqueness=[{'columns': ['account_name', 'symbol'], 'severity': 'high'}])
    res = evaluate_contract(c, _ctx(run))
    assert res[0].status == 'fail'
    assert res[0].observed == 1    # 1 组重复键


def test_uniqueness_empty_columns_is_infra_error(run):
    with pytest.raises(InfraError):
        evaluate_contract(_c('ds', 'dup_t', uniqueness=[{'columns': []}]), _ctx(run))


def test_nullability(run):
    _insert(run, 'nn_t', [('a', 'x'), (None, 'y'), ('b', 'z'), (None, 'w')], ['a', 'b'])
    strict = evaluate_contract(
        _c('ds', 'nn_t', nullability=[{'column': 'a', 'max_null_ratio': 0.0}]), _ctx(run))[0]
    assert strict.status == 'fail'
    assert strict.observed == 2
    tolerant = evaluate_contract(
        _c('ds', 'nn_t', nullability=[{'column': 'a', 'max_null_ratio': 0.5}]), _ctx(run))[0]
    assert tolerant.status == 'pass'


# ---------------------------------------------------------------------------
# 契约/规则健壮性
# ---------------------------------------------------------------------------
def test_missing_table_is_contract_failure_not_crash(run):
    res = evaluate_contract(_c('ds', 'no_such_table', severity='high',
                               rowcount={'min': 1}), _ctx(run))
    assert res[0].status == 'fail'
    assert res[0].check == 'readability'
    assert exit_code_for(res) == 1


def test_identifier_injection_is_blocked(run):
    c = _c('ds', 'equity; DROP TABLE equity', rowcount={'min': 1})
    with pytest.raises(InfraError):
        evaluate_contract(c, _ctx(run))


def test_contract_without_checks_is_skip(run):
    res = evaluate_contract(_c('ds', 'equity'), _ctx(run))
    assert res[0].status == 'skip'
    assert exit_code_for(res) == 0


def test_medium_failure_does_not_set_exit_code(run):
    c = _c('ds', 'empty_t', severity='medium', rowcount={'min': 1, 'severity': 'medium'})
    res = evaluate_contract(c, _ctx(run))
    assert res[0].status == 'fail'
    assert exit_code_for(res) == 0
    assert summarize(res)['high_failed'] == 0
    assert summarize(res)['medium_failed'] == 1


# ---------------------------------------------------------------------------
# fingerprint / error_events
# ---------------------------------------------------------------------------
def test_fingerprint_is_stable_and_pinned():
    """指纹是台账 upsert 的键：变了就会刷屏（每次都插新行），故钉死字面值。"""
    fp = fingerprint_for('quant.daily_klines', 'freshness:trade_date:expected_trading_day')
    assert fp == 'data-contract:a687b06f374b02b5'
    assert fp == fingerprint_for('quant.daily_klines', 'freshness:trade_date:expected_trading_day')


def test_fingerprint_prefix_length_and_uniqueness():
    a = fingerprint_for('quant.daily_klines', 'rowcount')
    b = fingerprint_for('quant.index_daily:000300.SH', 'rowcount')
    c = fingerprint_for('quant.daily_klines', 'value_range:close:>:0')
    assert a != b != c and a != c
    for fp in (a, b, c):
        assert fp.startswith(FINGERPRINT_PREFIX)
        assert len(fp) <= 64          # public.error_events.fingerprint = varchar(64)


def test_fingerprint_matches_dataset_and_rule_key(run):
    _insert(run, 'equity', [('a', '2026-09-10', 0.0)], ['account_name', 'snapshot_date', 'total_value'])
    c = _c('quant.simulation_equity_snapshot', 'equity', severity='high',
           freshness={'column': 'snapshot_date', 'mode': 'market_latest', 'max_lag_days': 0},
           value_ranges=[{'column': 'total_value', 'op': '>', 'value': 0}])
    res = evaluate_contract(c, _ctx(run, market_latest=date(2026, 9, 10)))
    fails = [r for r in res if r.failed]
    assert len(fails) == 1
    assert fingerprint_for(fails[0].dataset, fails[0].rule_key) == \
        fingerprint_for('quant.simulation_equity_snapshot', 'value_range:total_value:>:0')


def test_build_event_row_contract(run):
    _insert(run, 'empty_t', [], ['a'])
    c = _c('quant.trading_calendar', 'empty_t', owner='w-f4aa1f6a', severity='high',
           rowcount={'min': 1, 'severity': 'high'})
    res = [r for r in evaluate_contract(c, _ctx(run)) if r.failed][0]
    row = build_event_row(c, res, datetime(2026, 9, 11, 13, 0))
    assert row['source'] == UPSTREAM_SOURCE == 'v2'
    assert row['level'] == 'error'
    assert row['fingerprint'].startswith(FINGERPRINT_PREFIX)
    detail = json.loads(row['detail'])
    assert detail['dataset'] == 'quant.trading_calendar'
    assert detail['severity'] == 'high'
    assert json.loads(row['metadata'])['probe'] == 'data-contract'


def test_build_event_row_level_maps_medium_to_warning(run):
    c = _c('ds', 'empty_t', severity='medium', rowcount={'min': 1, 'severity': 'medium'})
    res = [r for r in evaluate_contract(c, _ctx(run)) if r.failed][0]
    assert build_event_row(c, res, datetime(2026, 9, 11, 13, 0))['level'] == 'warning'


def test_upsert_event_sql_guards_own_fingerprints():
    """upsert 必须只碰自己的指纹（前缀护栏），且按 fingerprint 冲突更新。"""
    assert 'ON CONFLICT (fingerprint) DO UPDATE' in UPSERT_EVENT
    assert 'occurrence_count = public.error_events.occurrence_count + 1' in UPSERT_EVENT
    assert 'last_seen_at     = now()' in UPSERT_EVENT
    assert 'LIKE :fp_like' in UPSERT_EVENT
    assert "status           = 'open'" in UPSERT_EVENT
