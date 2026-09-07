"""
测试 Agent Intelligence Repository - 符合 quantsys-v2 项目规范
"""
import pytest
from datetime import datetime
from adapters.outbound.repositories import (
    AgentDecisionRepository,
    PoolChangeLogRepository,
)
from adapters.outbound.repositories import StockPoolORMRepository


# ==================== Fixtures ====================

@pytest.fixture
def repo_decision():
    """提供 AgentDecisionRepository 实例"""
    return AgentDecisionRepository()


@pytest.fixture
def repo_change_log():
    """提供 PoolChangeLogRepository 实例"""
    return PoolChangeLogRepository()


@pytest.fixture
def test_pool():
    """创建一个测试用的股票池"""
    pool_repo = StockPoolORMRepository()
    pool = pool_repo.create({
        'name': f'测试池_{int(datetime.now().timestamp())}',
        'pool_type': 'static',
        'symbols': ['600519.SH']
    })
    return pool


# ==================== Tests ====================

class TestAgentDecisionRepository:
    """测试 Agent 决策 Repository"""

    def test_create_decision(self, repo_decision):
        """测试创建决策记录"""
        decision = {
            'decision_id': f'dec_{int(datetime.now().timestamp())}',
            'decision_type': 'create_pool',
            'context': {'market_condition': 'neutral', 'date': '2026-06-25'},
            'parameters': {'min_roe': 15, 'sector': '白酒'},
            'reasoning': '白酒行业基本面稳健，适合建池',
            'created_by': 'agent',
            'related_entity_type': 'pool',
            'related_entity_id': '5'
        }

        result = repo_decision.create_decision(decision)

        assert result is not None
        assert result['decision_id'] == decision['decision_id']
        assert result['decision_type'] == 'create_pool'
        assert result['evaluation_status'] == 'pending'

    def test_get_decision(self, repo_decision):
        """测试获取决策记录"""
        decision_id = f'dec_{int(datetime.now().timestamp())}_test'
        decision = {
            'decision_id': decision_id,
            'decision_type': 'refresh_pool',
            'context': {},
            'parameters': {},
            'reasoning': 'Test decision'
        }
        repo_decision.create_decision(decision)

        result = repo_decision.get_decision(decision_id)

        assert result is not None
        assert result['decision_id'] == decision_id

    def test_update_evaluation(self, repo_decision):
        """测试更新决策评估"""
        decision_id = f'dec_{int(datetime.now().timestamp())}_eval'
        decision = {
            'decision_id': decision_id,
            'decision_type': 'buy_stock',
            'context': {},
            'parameters': {'symbol': '600519.SH'},
            'reasoning': 'Test'
        }
        repo_decision.create_decision(decision)

        evaluation = {
            'result': {'profit': 5.2, 'days_held': 10},
            'learned_lesson': '白酒股在此市场环境下表现良好',
            'confidence_score': 0.85,
            'success': True
        }
        result = repo_decision.update_evaluation(decision_id, evaluation)

        assert result['evaluation_status'] == 'evaluated'
        assert result['success'] is True
        assert result['confidence_score'] == 0.85


class TestPoolChangeLogRepository:
    """测试池子变更日志 Repository"""

    def test_log_change(self, repo_change_log, test_pool):
        """测试记录变更"""
        change = {
            'pool_id': test_pool['id'],
            'action': 'add',
            'symbol': '600519.SH',
            'reason': 'ROE提升至20%，符合入池标准',
            'triggered_by': 'agent_auto',
            'agent_decision_id': 'dec_001',
            'context': {'date': '2026-06-25'},
            'before_state': {},
            'after_state': {'members': ['600519.SH']}
        }

        result = repo_change_log.log_change(change)

        assert result is not None
        assert result['action'] == 'add'
        assert result['symbol'] == '600519.SH'

    def test_get_pool_history(self, repo_change_log, test_pool):
        """测试获取池子历史"""
        for i in range(3):
            change = {
                'pool_id': test_pool['id'],
                'action': 'refresh',
                'symbol': None,
                'reason': f'定时刷新 {i}',
                'triggered_by': 'scheduled',
                'agent_decision_id': None,
                'context': {},
                'before_state': {},
                'after_state': {}
            }
            repo_change_log.log_change(change)

        history = repo_change_log.get_pool_history(pool_id=test_pool['id'], limit=10)

        assert len(history) >= 3


