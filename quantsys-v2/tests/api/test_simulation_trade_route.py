"""simulation 账户交易路由：T+1 拦截响应携带 details"""
import pytest
from datetime import datetime
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.simulation_async import router

ACCOUNT = 'test_route_t1_acc'


@pytest.fixture(autouse=True)
def _fixed_trading_clock(monkeypatch):
    """固定交易时段时钟（同 test_multi_account_domain.py）：交易时段护栏是生产行为，
    非本文件测试目标，统一注入固定交易时间 + 常真日历。"""
    from application.services import account_trading_service as ats
    real_init = ats.AccountTradingService.__init__

    def patched_init(self, repo=None, calendar=None, now_fn=None):
        real_init(self, repo=repo, calendar=calendar, now_fn=now_fn)
        if now_fn is None:
            self.now_fn = lambda: datetime(2026, 8, 3, 10, 0)  # 周一 10:00，交易时段内
        if calendar is None:
            self.calendar = SimpleNamespace(is_trading_day=lambda d: True)

    monkeypatch.setattr(ats.AccountTradingService, '__init__', patched_init)


@pytest.fixture
def client():
    app = FastAPI()

    @app.middleware("http")
    async def _close_session_after_request(request, call_next):
        # 请求结束关闭 scoped_session（orm/config.py close_session 文档规定的用法）：
        # 否则路由线程的事务 idle in transaction，阻塞后续测试文件的 DDL（ALTER TABLE）
        try:
            return await call_next(request)
        finally:
            from infrastructure.persistence.orm.config import close_session
            close_session()

    app.include_router(router)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _release_main_thread_session():
    """主线程 scoped_session 收尾（同理防 idle-in-transaction 阻塞 DDL）"""
    yield
    from infrastructure.persistence.orm.config import close_session
    close_session()


@pytest.fixture
def account_partial_sellable():
    """持仓 200 股，其中仅 100 股可卖（模拟昨日 100 + 今日 100）"""
    from adapters.outbound.repositories import SimulationORMRepository
    repo = SimulationORMRepository()
    if repo.get_account(ACCOUNT) is None:
        repo.create_account(ACCOUNT, initial_capital=100000)
    repo.upsert_position(ACCOUNT, '600519', shares_total=200, avg_cost=10.0,
                         shares_available=100, current_price=11.0)
    return ACCOUNT


def test_t1_block_response_has_details(client, account_partial_sellable):
    resp = client.post(f'/api/simulation/accounts/{ACCOUNT}/trade', json={
        'action': 'SELL', 'symbol': '600519', 'shares': 200,
        'price': 11.0, 'reason': '测试卖出：超出可卖数量应被拦截',
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body['success'] is False
    assert body['details'] == {'sellable_shares': 100, 'symbol': '600519'}


def test_non_t1_error_has_no_details_key(client, account_partial_sellable):
    """向后兼容：非 T+1 错误响应体不输出 details 键"""
    resp = client.post(f'/api/simulation/accounts/{ACCOUNT}/trade', json={
        'action': 'SELL', 'symbol': '000001', 'shares': 100,
        'price': 11.0, 'reason': '测试卖出：无持仓应被拒绝',
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body['success'] is False
    assert 'details' not in body
