"""DecisionScoreService 前向接线测试（REQ-9bcd0a WP1）：打分同时生成并回写 learned_lesson。

不连库：repo/kline/bench 全部注入假实现，专测「_score_one → update_score(lesson=...)」这条
前向路径（回填走的是 update_decision，属另一条路径，已另有用例）。
"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import polars as pl
from sqlalchemy.dialects import postgresql

from adapters.outbound.repositories.agent_intelligence_repository import (
    AgentDecision,
    AgentIntelligenceORMRepository,
)
from qs_agenthub.application.services.evolution.decision_score_service import DecisionScoreService


class FakeDecisionRepo:
    def __init__(self, decision):
        self._d = decision
        self.calls = []

    def list_unscored_decisions(self, days=1, decision_types=None):
        if self._d.get('score') is not None:
            return []
        normalized = str(self._d.get('decision_type') or '').strip().lower()
        if decision_types is not None and normalized not in decision_types:
            return []
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


def test_unscored_query_ignores_generic_status_and_filters_scorable_types():
    """SQL资格必须是 score IS NULL + 日龄 + 类型，不得混入 evaluation_status。"""
    repo = AgentIntelligenceORMRepository()
    session = MagicMock()
    query = session.query.return_value
    query.filter.return_value.order_by.return_value.all.return_value = []

    with patch.object(type(repo), 'session', new_callable=PropertyMock) as session_prop:
        session_prop.return_value = session
        result = repo.list_unscored_decisions(
            days=30,
            decision_types=['trade_BUY', 'trade_sell', 'missed_opportunity'],
        )

    assert result == []
    criteria = query.filter.call_args.args
    where_sql = ' AND '.join(
        str(criterion.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={'literal_binds': True},
        ))
        for criterion in criteria
    )
    assert 'score IS NULL' in where_sql
    assert 'created_at <=' in where_sql
    assert 'evaluation_status' not in where_sql
    assert "'missed_opportunity'" in where_sql
    assert "'trade_buy'" in where_sql
    assert "'trade_sell'" in where_sql


def test_generic_evaluation_fault_injection_preserves_score_evidence():
    """故障注入：通用评估试图覆盖时，已有评分及其共享证据字段均不变。"""
    repo = AgentIntelligenceORMRepository()
    scored_at = datetime(2026, 8, 11, 16, 0)
    score_detail = {
        'scorer': 'decision_score_p0a',
        'score': 0.75,
        'band': 'big_win',
        'excess_return': 0.12,
    }
    row = AgentDecision(
        id=1,
        decision_id='DEC-SCORED-GUARD',
        decision_type='trade_buy',
        context={},
        parameters={'symbol': '600519', 'price': 10.0},
        created_at=datetime(2026, 7, 14, 10, 0),
        evaluation_status='evaluated',
        evaluation_result=score_detail,
        evaluation_date=scored_at,
        learned_lesson='20交易日评分教训',
        confidence_score=0.9,
        success=True,
        score=0.75,
        score_band='big_win',
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = row

    with patch.object(type(repo), 'session', new_callable=PropertyMock) as session_prop:
        session_prop.return_value = session
        result = repo.update_evaluation('DEC-SCORED-GUARD', {
            'success': False,
            'learned_lesson': 'trade_buy决策已执行',
            'confidence_score': 0.1,
        })

    assert result['score'] == 0.75
    assert result['score_band'] == 'big_win'
    assert result['evaluation_result'] == score_detail
    assert result['learned_lesson'] == '20交易日评分教训'
    assert result['evaluation_date'] == '2026-08-11 16:00:00'
    assert result['success'] is True
    assert result['confidence_score'] == 0.9
    assert row.evaluation_result is score_detail
    assert row.evaluation_date == scored_at
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
