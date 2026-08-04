"""AgentKnowledgeRepository 测试——agent_knowledge 表 upsert/查询"""
import pytest

from adapters.outbound.repositories.agent_knowledge_repository import AgentKnowledgeORMRepository


class TestAgentKnowledgeRepository:
    def test_upsert_creates_then_updates(self):
        repo = AgentKnowledgeORMRepository()
        kid = 'test_chan_1买_20d'
        try:
            repo.upsert_knowledge(
                knowledge_id=kid,
                domain='chan_theory',
                knowledge_type='signal_effectiveness',
                content={'strategy': 'chan_1买', 'window': 20, 'win_rate': 0.5, 'samples': 8},
                confidence=0.3,
                validation_count=8,
                success_count=4,
            )
            row = repo.get_by_knowledge_id(kid)
            assert row is not None
            assert row['content']['win_rate'] == 0.5
            assert row['validation_count'] == 8

            # 再次 upsert 同 knowledge_id → 更新而非新增
            repo.upsert_knowledge(
                knowledge_id=kid,
                domain='chan_theory',
                knowledge_type='signal_effectiveness',
                content={'strategy': 'chan_1买', 'window': 20, 'win_rate': 0.62, 'samples': 37},
                confidence=0.7,
                validation_count=37,
                success_count=23,
            )
            row2 = repo.get_by_knowledge_id(kid)
            assert row2['content']['win_rate'] == 0.62
            assert row2['validation_count'] == 37
            rows = repo.get_by_domain('chan_theory', 'signal_effectiveness')
            assert len([r for r in rows if r['knowledge_id'] == kid]) == 1
        finally:
            repo.delete_by_knowledge_id(kid)

    def test_get_by_domain_filters(self):
        repo = AgentKnowledgeORMRepository()
        kid = 'test_chan_2买_20d'
        try:
            repo.upsert_knowledge(
                knowledge_id=kid, domain='chan_theory',
                knowledge_type='signal_effectiveness',
                content={'strategy': 'chan_2买'}, confidence=0.3,
                validation_count=5, success_count=3,
            )
            rows = repo.get_by_domain('chan_theory', 'signal_effectiveness')
            assert any(r['knowledge_id'] == kid for r in rows)
            assert repo.get_by_knowledge_id('nonexistent_id') is None
        finally:
            repo.delete_by_knowledge_id(kid)
