"""路由注册降级可见性测试（2026-09-11, w-8f2c4cc5）

背景：启动期可选路由 import 失败曾被静默吞掉（仅 warning），进程可带数百个 404 端点运行数小时，
且启动期失败不重试。此测试锁定 /api/health/routes 的降级可见性契约。
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.health_async import router


def _client(failures):
    app = FastAPI()
    app.state.optional_route_failures = failures
    app.include_router(router)
    return TestClient(app)


def test_health_routes_reports_ok_when_no_failures():
    resp = _client([]).get("/api/health/routes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["failure_count"] == 0
    assert body["optional_route_failures"] == []


def test_health_routes_reports_degraded_with_failure_list():
    resp = _client(["alerts", "signals"]).get("/api/health/routes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["failure_count"] == 2
    assert body["optional_route_failures"] == ["alerts", "signals"]
    assert body["hint"]
