"""update_score / list_scored_decisions 落库测试（P0a），连 quant_test。"""
from adapters.outbound.repositories.agent_intelligence_repository import (
    AgentIntelligenceORMRepository,
)


def test_update_score_roundtrip():
    repo = AgentIntelligenceORMRepository()
    created = repo.create_decision({
        'decision_type': 'trade_buy',
        'parameters': {'symbol': '600519', 'price': 10.0, 'shares': 100},
        'reasoning': 'P0a 打分落库测试',
    })
    decision_id = created['decision_id']
    try:
        detail = {'scorer': 'decision_score_p0a', 'score': 0.8, 'band': 'big_win',
                  'excess_return': 0.08, 'benchmark': 'sh000300'}
        updated = repo.update_score(decision_id, 0.8, 'big_win', detail)
        assert updated is not None
        assert updated['evaluation_status'] == 'evaluated'
        assert updated['success'] is True

        rows = repo.list_scored_decisions(limit=10, band='big_win')
        hit = [r for r in rows if r['decision_id'] == decision_id]
        assert len(hit) == 1
        assert abs(hit[0]['score'] - 0.8) < 1e-6
        assert hit[0]['score_band'] == 'big_win'
        assert hit[0]['evaluation_result']['scorer'] == 'decision_score_p0a'

        # 负分 → success=False；band 过滤生效
        repo.update_score(decision_id, -0.6, 'big_loss', {'scorer': 'decision_score_p0a'})
        rows = repo.list_scored_decisions(limit=10, band='big_win')
        assert all(r['decision_id'] != decision_id for r in rows)
        row = repo.get_decision(decision_id)
        assert row['success'] is False
    finally:
        session = repo.session
        session.query(repo.model).filter_by(decision_id=decision_id).delete()
        session.commit()


def test_create_decision_with_created_at_override():
    """P0b：补登历史/信号决策需要把 created_at 设为事件日（成熟度从事件日起算）"""
    from datetime import datetime as _dt
    repo = AgentIntelligenceORMRepository()
    created = repo.create_decision({
        'decision_id': 'TEST-CREATED-AT-001',
        'decision_type': 'missed_opportunity',
        'parameters': {'symbol': '600519', 'price': 10.0},
        'reasoning': 'created_at 覆盖测试',
        'created_at': _dt(2026, 6, 15, 10, 30),
    })
    try:
        assert created['created_at'] is not None
        assert str(created['created_at'])[:10] == '2026-06-15'
    finally:
        session = repo.session
        session.query(repo.model).filter_by(decision_id='TEST-CREATED-AT-001').delete()
        session.commit()


def test_update_score_writes_learned_lesson():
    """REQ-9bcd0a WP1：update_score 支持写入 learned_lesson（M6↔L2 回流边的数据入口）。

    回归要点：①传 lesson 时落库；②不传 lesson 时保持旧行为（不覆盖已有教训）。
    """
    repo = AgentIntelligenceORMRepository()
    created = repo.create_decision({
        'decision_type': 'trade_buy',
        'parameters': {'symbol': '600519', 'price': 10.0, 'shares': 100},
        'reasoning': 'WP1 learned_lesson 落库测试',
    })
    decision_id = created['decision_id']
    try:
        detail = {'scorer': 'decision_score_p0a', 'excess_return': -0.44,
                  'trade_date': '2026-07-14', 'ref_date': '2026-08-11',
                  'benchmark': 'sh000300'}
        lesson = ('买入 600519@10.00（2026-07-14→2026-08-11，20 交易日）'
                  '超额 -44.4%（band=big_loss，score=-1.00）→ 测试教训')
        updated = repo.update_score(decision_id, -1.0, 'big_loss', detail, lesson=lesson)
        assert updated is not None
        assert updated['learned_lesson'] == lesson

        # 不传 lesson → 旧行为：不覆盖已有教训
        again = repo.update_score(decision_id, -1.0, 'big_loss', detail)
        assert again['learned_lesson'] == lesson
    finally:
        session = repo.session
        session.query(repo.model).filter_by(decision_id=decision_id).delete()
        session.commit()
