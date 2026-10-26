"""端到端冒烟（t15 · UC-1/UC-2）：建计划→激活→成交回执→反思→改计划→重编译

走真实路由 + 真实仓储（quant_test）；执行侧用 FillSyncService + PlanProgressPort
串起来（与生产组合根同款装配），不碰真实下单。
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from adapters.inbound.fastapi_app.routes.plan_async import router
from adapters.outbound.repositories.plan_progress_port import PlanProgressPort
from adapters.outbound.repositories.trading_plan_repository import TradingPlanRepository
from qs_trading.application.ports.fill_listener import FillEvent
from qs_watch.application.services.watch_engine.fill_sync_service import FillSyncService

ACC = 'test-plan-e2e'
SYM = '999996.SZ'


def _spec(stop=8.0):
    return {
        'targets': [{'symbol': SYM, 'budget_pct': 5, 'role': 'core'}],
        'entry': {'conditions': [{'type': 'price_break',
                                  'params': {'price': 9999, 'direction': 'above'}}],
                  'combinator': 'all_of'},
        'exit': {'stop_loss': {'type': 'pct', 'value': stop}},
        'monitoring': {'news': True}, 'schedule': {'interval_sec': 30},
    }


class _NoRuleRepo:
    def list_rules(self, **kw):
        return []

    def set_position_state(self, *a, **kw):
        return True


class _NoPosRepo:
    def get_position(self, a, s):
        return None


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestPlanEndToEnd:
    def teardown_method(self):
        from qs_kernel.infrastructure.persistence.database.engine import get_engine
        with get_engine().begin() as conn:
            conn.execute(text(
                "DELETE FROM quant.watch_rule_changes WHERE rule_id IN "
                "(SELECT id FROM quant.watch_rules WHERE plan_id IN "
                "(SELECT id FROM quant.trading_plans WHERE account=:a))"), {'a': ACC})
            conn.execute(text(
                "DELETE FROM quant.watch_rules WHERE plan_id IN "
                "(SELECT id FROM quant.trading_plans WHERE account=:a)"), {'a': ACC})
            conn.execute(text("DELETE FROM quant.trading_plans WHERE account=:a"), {'a': ACC})

    def test_uc1_uc2_full_loop(self, client):
        # UC-1 建计划 + 激活
        r = client.post('/api/plans', json={'account': ACC, 'name': 'e2e', 'horizon': 'day',
                                            'spec': _spec()})
        pid = r.json()['data']['plan']['id']
        assert client.post(f'/api/plans/{pid}/activate',
                           json={'expected_version': 1}).status_code == 200

        # 成交回执：买 → holding；卖光 → closed
        svc = FillSyncService(rule_repo=_NoRuleRepo(), position_repo=_NoPosRepo(),
                              plan_progress=PlanProgressPort(
                                  repo=TradingPlanRepository(),
                                  remaining_provider=lambda a, s: 100))
        ev_buy = FillEvent(account_name=ACC, symbol=SYM, action='buy', shares=100,
                           price=10.0, trade_id=1, plan_id=pid, plan_version=1)
        svc.on_fill(ev_buy)
        assert client.get(f'/api/plans/{pid}').json()['data']['plan']['status'] == 'holding'

        closing = FillSyncService(rule_repo=_NoRuleRepo(), position_repo=_NoPosRepo(),
                                  plan_progress=PlanProgressPort(
                                      repo=TradingPlanRepository(),
                                      remaining_provider=lambda a, s: 0))
        ev_sell = FillEvent(account_name=ACC, symbol=SYM, action='sell', shares=100,
                            price=11.0, trade_id=2, plan_id=pid, plan_version=1)
        closing.on_fill(ev_sell)
        assert client.get(f'/api/plans/{pid}').json()['data']['plan']['status'] == 'closed'

        # UC-2 反思：五问齐全落库
        body = {'answers': {f'q{i}': f'a{i}' for i in range(1, 6)},
                'verdict': 'keep', 'reasoning': '维持', 'period': '2026-10-21'}
        r = client.post(f'/api/plans/{pid}/reflections', json=body)
        assert r.status_code == 201
        assert client.get(f'/api/plans/{pid}/reflections').json()['data']['count'] == 1

        # 已关闭计划不可再改（防「关了还在改」的幽灵计划）
        r = client.patch(f'/api/plans/{pid}', json={
            'expected_version': 1,
            'spec_patch': {'exit': {'stop_loss': {'type': 'pct', 'value': 10}}},
            'reason': '放宽止损', 'actor': 'user'})
        assert r.status_code == 422 and r.json()['code'] == 'PLAN_STATE_ILLEGAL'

        # 统计可读
        stats = client.get(f'/api/plans/{pid}/stats').json()['data']
        assert stats['versions'] >= 1
