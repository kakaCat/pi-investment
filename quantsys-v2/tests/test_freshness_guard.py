"""新鲜度巡检 _job_freshness_guard 回归测试（2026-09-11 w-f4aa1f6a）。

事故：2026-09-10 把 K 线判据从"全局 max(trade_date)"改成"按标的覆盖度"时，
两处 return 里遗留了 str(kline_latest) —— 该变量已不存在，导致**"数据新鲜"这条
正常分支每天 17:20 必抛 NameError: name 'kline_latest' is not defined**
（滞后分支反而正常，故长期未被发现；错误事件 7460c6b7 / ddea89ea）。

本测试用打桩数据覆盖三条分支，防止同类"重构残留"再次隐身：
  1. fresh（正常态）          —— 修复前必崩
  2. fresh_but_job_failed    —— 修复前必崩
  3. stale（异常态）          —— 修复前正常（需保持）
"""
import pytest

import adapters.inbound.fastapi_app.daily_jobs_bootstrap as m


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConn:
    def __init__(self, value):
        self._value = value

    def execute(self, *args, **kwargs):
        return _FakeResult(self._value)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeEngine:
    def __init__(self, value):
        self._value = value

    def connect(self):
        return _FakeConn(self._value)


def _patch(monkeypatch, *, factor_latest, coverage, failed_jobs=None):
    """打桩数据源与飞书，返回 (sent_alerts, ) 便于断言是否发告警。"""
    import infrastructure.persistence.database.engine as engine_mod

    monkeypatch.setattr(engine_mod, 'get_engine', lambda: _FakeEngine(factor_latest), raising=True)
    monkeypatch.setattr(m, '_last_trading_day', lambda _d: '2026-09-10', raising=True)
    monkeypatch.setattr(m, '_kline_coverage', lambda _engine, _expected: coverage, raising=True)
    monkeypatch.setattr(m, '_job_failure_watch', lambda _engine: (failed_jobs or []), raising=True)
    sent = []
    monkeypatch.setattr(m, '_send_feishu', lambda text: (sent.append(text), True)[1], raising=True)
    return sent


FRESH_COV = {'total': 5281, 'covered': 5262, 'stale': 19,
             'coverage': 0.9964, 'oldest_stale': '2026-03-13'}
STALE_COV = {'total': 5281, 'covered': 4200, 'stale': 1081,
             'coverage': 0.7953, 'oldest_stale': '2026-03-13'}


def test_fresh_path_returns_coverage_and_no_alert(monkeypatch):
    sent = _patch(monkeypatch, factor_latest='2026-09-11', coverage=FRESH_COV)
    result = m._job_freshness_guard()

    assert result['status'] == 'fresh'
    assert result['kline_coverage'] == '5262/5281'
    assert result['kline_stale'] == 19
    assert result['kline_oldest_stale'] == '2026-03-13'
    assert result['factor_latest'] == '2026-09-11'
    assert sent == [], '新鲜路径不应发告警'
    assert 'kline_latest' not in result, 'kline_latest 已废弃，不得再出现（正是本次 NameError 的来源）'


def test_fresh_but_job_failed_path(monkeypatch):
    sent = _patch(monkeypatch, factor_latest='2026-09-11', coverage=FRESH_COV,
                  failed_jobs=[{'job_id': 'chip_update', 'run_date': '2026-09-10', 'error': 'boom'}])
    result = m._job_freshness_guard()

    assert result['status'] == 'fresh_but_job_failed'
    assert result['kline_coverage'] == '5262/5281'
    assert result['failed_jobs'][0]['job_id'] == 'chip_update'
    assert len(sent) == 1 and '任务失败残留' in sent[0]


def test_stale_path_still_alerts(monkeypatch):
    sent = _patch(monkeypatch, factor_latest='2026-09-01', coverage=STALE_COV)
    result = m._job_freshness_guard()

    assert result['status'] == 'stale'
    assert result['alert_sent'] is True
    assert len(sent) == 1 and '数据新鲜度告警' in sent[0]
    joined = ' '.join(result['stale'])
    assert 'daily_klines 覆盖' in joined and 'factor_values 最新' in joined


def test_summarize_result_surfaces_coverage():
    text = m._summarize_result({'status': 'fresh', 'kline_coverage': '5262/5281',
                                'kline_stale': 19, 'factor_latest': '2026-09-11'})
    assert 'kline_coverage=5262/5281' in text
    assert 'kline_stale=19' in text
