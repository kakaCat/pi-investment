"""进化层消费反思知识段（t13）：沉淀/跳过/幂等 + 结构只读检查"""
from types import SimpleNamespace

from qs_agenthub.application.services.evolution.plan_reflection_consumer import (
    PlanReflectionConsumer,
)


class FakeKnowledge:
    def __init__(self):
        self.rows = {}

    def upsert_knowledge(self, **kw):
        self.rows[kw['knowledge_id']] = kw


def _row(plan_id=1, updates=None):
    return SimpleNamespace(plan_id=plan_id, period='2026-10-21', version=1,
                           verdict='adjust', knowledge_updates=updates)


class TestConsumer:
    def test_upserts_with_evidence(self):
        kb = FakeKnowledge()
        out = PlanReflectionConsumer(kb).consume([_row(updates=[
            {'domain': 'environment_gate',
             'lesson': '主线板块个股应豁免大盘情绪维',
             'evidence': ['sim: 拦截后 2 日上行'], 'confidence': 0.7}])])
        assert out == {'upserted': 1, 'skipped': 0, 'failed': 0}
        row = list(kb.rows.values())[0]
        assert row['knowledge_type'] == 'plan_reflection_lesson'
        assert row['domain'] == 'environment_gate'
        assert row['confidence'] == 0.7
        assert row['evidence']['items'][0].startswith('sim:')

    def test_skips_missing_evidence(self):
        kb = FakeKnowledge()
        out = PlanReflectionConsumer(kb).consume([_row(updates=[
            {'lesson': '无证据的感觉'}])])
        assert out == {'upserted': 0, 'skipped': 1, 'failed': 0}
        assert kb.rows == {}

    def test_idempotent_same_id(self):
        kb = FakeKnowledge()
        c = PlanReflectionConsumer(kb)
        row = _row(updates=[{'lesson': 'x', 'evidence': ['e']}])
        c.consume([row])
        c.consume([row])
        assert len(kb.rows) == 1

    def test_bad_entry_does_not_break_batch(self):
        class Boom(FakeKnowledge):
            def upsert_knowledge(self, **kw):
                raise RuntimeError('db down')
        out = PlanReflectionConsumer(Boom()).consume([_row(updates=[
            {'lesson': 'x', 'evidence': ['e']}])])
        assert out['failed'] == 1

    def test_module_does_not_write_plans(self):
        """结构只读检查：进化消费者源码不得出现对 plans 表的写调用。"""
        import inspect
        from qs_agenthub.application.services.evolution import plan_reflection_consumer as mod
        src = inspect.getsource(mod)
        for banned in ('INSERT INTO quant.trading_plan', 'UPDATE quant.trading_plan',
                       'DELETE FROM quant.trading_plan', 'create_plan', 'transition_status'):
            assert banned not in src, '进化层不得写计划：%s' % banned
