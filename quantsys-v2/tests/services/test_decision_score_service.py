"""DecisionScoreService 前向接线测试（REQ-9bcd0a WP1）：打分同时生成并回写 learned_lesson。

不连库：repo/kline/bench 全部注入假实现，专测「_score_one → update_score(lesson=...)」这条
前向路径（回填走的是 update_decision，属另一条路径，已另有用例）。
"""
from datetime import date, datetime, timedelta

import polars as pl

from application.services.evolution.decision_score_service import DecisionScoreService


class FakeDecisionRepo:
    def __init__(self, decision):
        self._d = decision
        self.calls = []

    def list_pending_evaluations(self, days=1):
        return [self._d]

    def update_score(self, decision_id, score, band, detail, lesson=None):
        self.calls.append({'decision_id': decision_id, 'score': score, 'band': band,
                           'detail': detail, 'lesson': lesson})
        return {'decision_id': decision_id}


class FakeKlineRepo:
    def __init__(self, rows):
        self._rows = rows

    def get_daily_klines(self, symbol, start_date=None, end_date=None):
        return pl.DataFrame(self._rows)


def _future_rows(start: date, n: int, first_close: float = 100.0):
    rows, d = [], start
    for i in range(n):
        rows.append({'trade_date': d.isoformat(), 'close': first_close + i})
        d += timedelta(days=1)
    return rows


def _run(decision_type='trade_buy', price=100.0, rows=None, mature_window=20):
    decision = {
        'decision_id': 'TEST-LESSON-1',
        'decision_type': decision_type,
        'parameters': {'symbol': '600519', 'price': price},
        'context': {'regime': 'risk_off'},
        'created_at': datetime(2026, 7, 14, 10, 0),
    }
    repo = FakeDecisionRepo(decision)
    svc = DecisionScoreService(
        decision_repo=repo,
        kline_repo=FakeKlineRepo(rows if rows is not None else _future_rows(date(2026, 7, 15), 25)),
        bench_klines_provider=lambda **kw: [],   # 基准缺失 → benchmark_missing=True
        mature_window=mature_window,
    )
    return svc.score_mature_decisions(pending_days=30), repo


def test_forward_path_writes_learned_lesson():
    result, repo = _run()
    assert result['scored'] == 1
    assert len(repo.calls) == 1
    lesson = repo.calls[0]['lesson']
    # 四要素齐备（禁模板化：缺一即视为退化）
    assert lesson, 'lesson 不得为空 —— 为空即回流边数据入口断链'
    assert '600519' in lesson          # 标的
    assert '2026-07-14' in lesson      # 日期区间
    assert '超额' in lesson             # 超额数值
    assert 'big_win' in lesson         # band
    # 基准缺失须显式标注，不得静默
    assert '基准缺失' in lesson
    # band/score 与 update_score 入参一致
    assert repo.calls[0]['band'] == 'big_win'


def test_unmature_decision_not_scored_and_no_lesson():
    result, repo = _run(rows=_future_rows(date(2026, 7, 15), 5))
    assert result['scored'] == 0
    assert result['skipped_unmature'] == 1
    assert repo.calls == []
