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
