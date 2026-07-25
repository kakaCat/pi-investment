"""decision 记录透传 session_key（仓储级，真实落库验证）"""
import pytest
from adapters.outbound.repositories.agent_intelligence_repository import AgentIntelligenceORMRepository


@pytest.fixture
def repo():
    return AgentIntelligenceORMRepository()


def test_create_decision_persists_session_key(repo):
    created = repo.create_decision({
        'decision_type': 'create_pool',
        'context': {}, 'parameters': {},
        'reasoning': 'gateway 联动测试',
        'session_key': 'agent:main:wake:default',
    })
    assert created['decision_id']

    fetched = repo.get_decision(created['decision_id'])
    assert fetched['session_key'] == 'agent:main:wake:default'

    # 清理
    repo.session.query(repo.model).filter_by(decision_id=created['decision_id']).delete()
    repo.session.commit()
