"""executions 两个线上 500 的回归守卫（2026-09-14 w-c8cae280）

背景（都是实测复现的真缺陷，不是测试写错）：
  1) POST /api/executions 原样把 payload（dict）传给 SignalExecutionORMRepository.create_execution(...)，
     而该仓库方法的签名是 (signal_id, execution_date, execution_price, quantity, commission=0.0, status='pending')
     → TypeError: missing 3 required positional arguments → 被 except Exception 包成 **500**。
  2) PUT /api/executions/{id}/close 只传 3 个参数，仓库要 4 个（含 pnl）
     → TypeError: missing 1 required positional argument: 'pnl' → **500**。
  3) GET /api/executions 声明 offset 却从未使用（分页静默失效），已补仓库 offset 形参并接线。

本测试的意义：这两条都是"测试红着、线上 500 着"的典型 —— 修完必须有回归守卫，
否则下次重构又会把签名对不上悄悄带回来（而且只会以 500 的形式暴露）。
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _client():
    from adapters.inbound.fastapi_app.routes.executions_async import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_post_execution_missing_fields_returns_400_not_500():
    r = _client().post('/api/executions', json={})
    assert r.status_code == 400, "缺字段必须是 400（客户端错误），不该是 500：%s" % r.text[:200]
    assert '缺少必需参数' in r.text


def test_post_execution_valid_payload_not_500():
    payload = {'signal_id': 1, 'execution_date': '2024-01-15',
               'execution_price': 10.0, 'quantity': 100, 'status': 'pending'}
    r = _client().post('/api/executions', json=payload)
    assert r.status_code == 201, "合法载荷应创建成功（201），不该 500：%s" % r.text[:200]
    assert 'id' in r.json()


def test_close_execution_nonexistent_returns_404_not_500():
    """pnl 由已存记录推算的路径：id 不存在时应 404，而不是因缺 pnl 抛 TypeError 变 500。"""
    r = _client().put('/api/executions/99999999/close',
                      json={'close_date': '2024-01-20', 'close_price': 11.0})
    assert r.status_code in (404, 400), "应给业务错误码，不该 500：%s" % r.text[:200]
    assert r.status_code != 500


def test_close_execution_missing_body_returns_400():
    r = _client().put('/api/executions/1/close', json={})
    assert r.status_code == 400


def test_list_executions_accepts_status_and_offset():
    r = _client().get('/api/executions', params={'status': 'pending', 'limit': 5, 'offset': 0})
    assert r.status_code == 200, r.text[:200]
    assert 'executions' in r.json()


def test_list_executions_invalid_status_returns_400():
    r = _client().get('/api/executions', params={'status': 'unknown'})
    assert r.status_code == 400, "非法 status 应 400（仓库抛 ValueError）：%s" % r.text[:200]
