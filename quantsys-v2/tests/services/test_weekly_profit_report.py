"""每周盈利报告单测（2026-10-19）

钉住三段口径与诚实降级：
- 周区间 = 上周一~上周日；
- 账户段：零卖出时如实提示"没有利润落袋"；净值快照缺失显示 N/A；
- 命中率：0 样本明示原因；样本 <5 标注仅供参考；
- 机会段：BUY 信号标的与买入成交标的的捕捉/错过对照；
- 汇总：send 失败 → status=failed；dry_run 不推送。
"""
from datetime import date, datetime
from unittest.mock import MagicMock

from qs_ops.infrastructure.jobs.weekly_profit_report_job import (
    WeeklyProfitReportJob, gather_weekly_report, render_markdown, week_range,
)


class TestWeekRange:
    def test_sunday_reports_last_monday_to_sunday(self):
        ws, we = week_range(datetime(2026, 10, 18, 20, 30))  # 周日
        assert ws == date(2026, 10, 5) and we == date(2026, 10, 11)

    def test_midweek_still_last_full_week(self):
        ws, we = week_range(datetime(2026, 10, 21, 12, 0))  # 周三
        assert ws == date(2026, 10, 12) and we == date(2026, 10, 18)


class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """按 SQL 文本片段路由到预置结果的最小打桩。"""

    def __init__(self, sells=(), accounts=(), snap_end=None, snap_start=None,
                 hit_row=(0, 0, 0, 0, 0), sig_rows=(), traded=()):
        self._sells, self._accounts = sells, accounts
        self._snap_end, self._snap_start = snap_end, snap_start
        self._hit_row, self._sig_rows, self._traded = hit_row, sig_rows, traded

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if 'simulation_trades' in sql and 'SELL' in sql:
            return _Result(self._sells)
        if 'simulation_account' in sql:
            return _Result(self._accounts)
        if 'simulation_equity_snapshot' in sql:
            if params and 'we' in params:
                return _Result([self._snap_end] if self._snap_end else [])
            return _Result([self._snap_start] if self._snap_start else [])
        if 'signal_tracking' in sql:
            return _Result([self._hit_row])
        if 'FROM quant.signals' in sql:
            return _Result(self._sig_rows)
        if 'simulation_trades' in sql:  # BUY distinct symbols
            return _Result(self._traded)
        raise AssertionError(f'未预置的查询: {sql[:80]}')


def _report(conn):
    return gather_weekly_report(conn, date(2026, 10, 5), date(2026, 10, 11))


class TestGather:
    def test_account_pnl_and_week_return(self):
        conn = _FakeConn(
            sells=[('agent_virtual', 2, 1234.5)],
            accounts=[('agent_virtual', 'Agent 虚拟仓', 104449.52, 0.0445)],
            snap_end=(104449.52,), snap_start=(100000.0,),
        )
        r = _report(conn)
        acct = r['accounts'][0]
        assert acct['sells'] == 2 and acct['realized_pnl'] == 1234.5
        assert acct['week_return_pct'] == 4.45  # 104449.52/100000-1

    def test_week_return_na_when_snapshot_missing(self):
        conn = _FakeConn(accounts=[('a', 'A', 100, 0.0)], snap_end=None, snap_start=None)
        assert _report(conn)['accounts'][0]['week_return_pct'] is None

    def test_hit_rate_computed(self):
        conn = _FakeConn(hit_row=(10, 6, 5, 10, 10))  # 评估10, T+5中6, T+10中5
        h = _report(conn)['hit_rate']
        assert h['hit5_rate'] == 60.0 and h['hit10_rate'] == 50.0 and h['enough']

    def test_opportunity_split(self):
        conn = _FakeConn(
            sig_rows=[('000001', '平安银行', 11.5, 2), ('600519', '贵州茅台', 1700.0, 1)],
            traded=[('000001',)],
        )
        o = _report(conn)['opportunities']
        assert len(o['captured']) == 1 and len(o['missed']) == 1
        assert o['missed'][0]['symbol'] == '600519'


class TestRender:
    def test_zero_sells_honest_banner(self):
        conn = _FakeConn(accounts=[('a', 'A账户', 100, 0.0)])
        md = render_markdown(_report(conn))
        assert '零卖出' in md and '没有利润落袋' in md

    def test_hit_rate_low_sample_marked(self):
        conn = _FakeConn(hit_row=(3, 2, 1, 3, 3))
        md = render_markdown(_report(conn))
        assert '仅供参考' in md

    def test_no_signals_honest(self):
        md = render_markdown(_report(_FakeConn()))
        assert '本周无 BUY 信号' in md


class TestExecute:
    def test_dry_run_never_sends(self, monkeypatch):
        job = WeeklyProfitReportJob(facade=MagicMock())
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value = _FakeConn()
        monkeypatch.setattr(
            'infrastructure.persistence.database.engine.get_engine', lambda: engine)
        r = job.execute(dry_run=True, now=datetime(2026, 10, 18, 20, 30))
        assert r['status'] == 'completed'
        job.facade.send_card.assert_not_called()

    def test_send_failure_marks_failed(self, monkeypatch):
        facade = MagicMock()
        facade.send_card.side_effect = RuntimeError('channel down')
        job = WeeklyProfitReportJob(facade=facade)
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value = _FakeConn()
        monkeypatch.setattr(
            'infrastructure.persistence.database.engine.get_engine', lambda: engine)
        r = job.execute(dry_run=False)
        assert r['status'] == 'failed' and r['send_ok'] is False
