"""召回审计 API 路由测试（P1-T4）

契约：
- POST /api/memory/recall-audit → 201 {"id": N}；flow/gate_result 非空，缺 → 422
- GET  /api/memory/recall-audit → {"items": [...], "total": N}（ts DESC 分页 + 筛选）
- GET  /api/memory/recall-audit/stats → 注入率/分流统计/抑制原因/分数直方图
- POST /api/memory/recall-audit/{id}/feedback → hits 内标注；human 覆盖 agent 允许，反向 409
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.memory_async import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _cleanup(ids):
    from infrastructure.persistence.orm import get_session
    from sqlalchemy import text
    session = get_session()
    session.execute(
        text("DELETE FROM quant.memory_recall_audit WHERE id = ANY(:ids)"), {"ids": ids}
    )
    session.commit()


def _payload(**overrides):
    base = {
        "ts": "2026-08-13T10:00:00+00:00",
        "session_id": "s-test",
        "flow": "chat",
        "query_text": "茅台 买点",
        "strategy": "hybrid",
        "degraded": False,
        "gate_result": "passed",
        "suppress_reason": None,
        "hits": [{"memory_id": 101, "score": 0.85, "title": "t1"}],
    }
    base.update(overrides)
    return base


@pytest.fixture
def created_ids(client):
    """测试后自动清理"""
    ids = []
    yield ids
    if ids:
        _cleanup(ids)


# ---------- POST 创建 ----------

def test_post_create_201(client, created_ids):
    resp = client.post("/api/memory/recall-audit", json=_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert isinstance(body["id"], int)
    created_ids.append(body["id"])


def test_post_validation_422(client):
    # 缺 flow
    p = _payload()
    del p["flow"]
    assert client.post("/api/memory/recall-audit", json=p).status_code == 422
    # 缺 gate_result
    p = _payload()
    del p["gate_result"]
    assert client.post("/api/memory/recall-audit", json=p).status_code == 422
    # 空字符串也算缺
    assert client.post("/api/memory/recall-audit", json=_payload(flow="")).status_code == 422
    assert client.post("/api/memory/recall-audit", json=_payload(gate_result="  ")).status_code == 422


# ---------- GET 分页与筛选 ----------

def test_get_list_pagination_and_filters(client, created_ids):
    specs = [
        dict(flow="chat", gate_result="passed", ts="2026-08-13T10:00:00+00:00"),
        dict(flow="chat", gate_result="suppressed", suppress_reason="low_score",
             ts="2026-08-13T11:00:00+00:00"),
        dict(flow="watch", gate_result="passed", ts="2026-08-13T12:00:00+00:00"),
    ]
    for s in specs:
        resp = client.post("/api/memory/recall-audit", json=_payload(**s))
        assert resp.status_code == 201, resp.text
        created_ids.append(resp.json()["id"])

    # flow 筛选
    resp = client.get("/api/memory/recall-audit", params={"flow": "chat"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert all(i["flow"] == "chat" for i in body["items"])

    # gate_result 筛选
    resp = client.get("/api/memory/recall-audit", params={"gate_result": "suppressed"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["suppress_reason"] == "low_score"

    # suppressed_only
    resp = client.get("/api/memory/recall-audit", params={"suppressed_only": "true"})
    assert resp.json()["total"] == 1

    # ts DESC：最新（watch, 12:00）在最前
    resp = client.get("/api/memory/recall-audit")
    items = resp.json()["items"]
    assert items[0]["flow"] == "watch"

    # 分页：page_size=2 第 1 页 2 条、第 2 页 1 条，total 恒为 3
    resp = client.get("/api/memory/recall-audit", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert body["total"] == 3 and len(body["items"]) == 2
    resp = client.get("/api/memory/recall-audit", params={"page": 2, "page_size": 2})
    assert len(resp.json()["items"]) == 1

    # 日期范围：date_from 在未来 → 0 条
    resp = client.get("/api/memory/recall-audit", params={"date_from": "2027-01-01"})
    assert resp.json()["total"] == 0
    # date_to 在过去 → 0 条
    resp = client.get("/api/memory/recall-audit", params={"date_to": "2020-01-01"})
    assert resp.json()["total"] == 0


# ---------- stats 聚合 ----------

def test_stats_aggregation(client, created_ids):
    specs = [
        # flow=chat: 2 passed(=injected) + 1 suppressed
        dict(flow="chat", gate_result="passed",
             hits=[{"memory_id": 1, "score": 0.05}, {"memory_id": 2, "score": 0.15}]),
        dict(flow="chat", gate_result="passed", hits=[{"memory_id": 3, "score": 0.95}]),
        dict(flow="chat", gate_result="suppressed", suppress_reason="low_score", hits=[]),
        # flow=watch: 1 suppressed
        dict(flow="watch", gate_result="suppressed", suppress_reason="low_score", hits=[]),
    ]
    for s in specs:
        resp = client.post("/api/memory/recall-audit", json=_payload(**s))
        assert resp.status_code == 201, resp.text
        created_ids.append(resp.json()["id"])

    resp = client.get("/api/memory/recall-audit/stats",
                      params={"date_from": "2026-08-13", "date_to": "2026-08-14"})
    assert resp.status_code == 200, resp.text
    stats = resp.json()

    assert stats["total"] == 4
    assert stats["injected"] == 2
    assert stats["suppressed"] == 2
    assert stats["injection_rate"] == 0.5

    assert stats["by_flow"]["chat"] == {"total": 3, "injected": 2, "suppressed": 1}
    assert stats["by_flow"]["watch"] == {"total": 1, "injected": 0, "suppressed": 1}

    assert stats["suppress_reasons"] == {"low_score": 2}

    hist = {b["bucket"]: b["count"] for b in stats["score_histogram"]}
    assert hist["0.0-0.1"] == 1
    assert hist["0.1-0.2"] == 1
    assert hist["0.9-1.0"] == 1
    assert sum(hist.values()) == 3  # 共 3 个 hit

    # 未来日期范围 → 全零
    resp = client.get("/api/memory/recall-audit/stats",
                      params={"date_from": "2027-01-01", "date_to": "2027-01-02"})
    stats = resp.json()
    assert stats["total"] == 0 and stats["injected"] == 0 and stats["suppressed"] == 0


def test_stats_same_day_date_to_inclusive(client, created_ids):
    """date_from == date_to 同一天必须覆盖当日全天（生产 bug：date_to 被解析为当日 0 点导致全零）"""
    resp = client.post("/api/memory/recall-audit", json=_payload(
        gate_result="passed", ts="2026-08-13T13:00:00+00:00"))
    assert resp.status_code == 201
    created_ids.append(resp.json()["id"])

    resp = client.get("/api/memory/recall-audit/stats",
                      params={"date_from": "2026-08-13", "date_to": "2026-08-13"})
    stats = resp.json()
    assert stats["total"] == 1
    assert stats["injected"] == 1

    # list 同日边界同理
    resp = client.get("/api/memory/recall-audit",
                      params={"date_from": "2026-08-13", "date_to": "2026-08-13"})
    assert resp.json()["total"] == 1


def test_stats_legacy_injected_value_counted(client, created_ids):
    """历史/外部写入的 gate_result='injected' 也计入注入数（与 passed 等价）"""
    resp = client.post("/api/memory/recall-audit", json=_payload(
        gate_result="injected", ts="2026-08-13T14:00:00+00:00"))
    assert resp.status_code == 201
    created_ids.append(resp.json()["id"])

    resp = client.get("/api/memory/recall-audit/stats",
                      params={"date_from": "2026-08-13", "date_to": "2026-08-13"})
    stats = resp.json()
    assert stats["total"] == 1
    assert stats["injected"] == 1


# ---------- feedback 标注 ----------

def test_feedback_flow(client, created_ids):
    resp = client.post("/api/memory/recall-audit", json=_payload(
        hits=[{"memory_id": 101, "score": 0.85}, {"memory_id": 102, "score": 0.40}],
    ))
    assert resp.status_code == 201, resp.text
    audit_id = resp.json()["id"]
    created_ids.append(audit_id)

    # 1) agent 首次标注 → 200，hits[0] 补上 feedback 三字段
    resp = client.post(f"/api/memory/recall-audit/{audit_id}/feedback",
                       json={"memory_id": 101, "feedback": "relevant", "feedback_by": "agent"})
    assert resp.status_code == 200, resp.text
    hits = resp.json()["hits"]
    target = next(h for h in hits if h["memory_id"] == 101)
    assert target["feedback"] == "relevant"
    assert target["feedback_by"] == "agent"
    assert target["feedback_at"]
    # 未标注的 hit 不受影响
    other = next(h for h in hits if h["memory_id"] == 102)
    assert "feedback" not in other

    # 2) human 覆盖 agent → 允许
    resp = client.post(f"/api/memory/recall-audit/{audit_id}/feedback",
                       json={"memory_id": 101, "feedback": "irrelevant", "feedback_by": "human"})
    assert resp.status_code == 200, resp.text
    target = next(h for h in resp.json()["hits"] if h["memory_id"] == 101)
    assert target["feedback"] == "irrelevant"
    assert target["feedback_by"] == "human"

    # 3) agent 覆盖 human → 409
    resp = client.post(f"/api/memory/recall-audit/{audit_id}/feedback",
                       json={"memory_id": 101, "feedback": "relevant", "feedback_by": "agent"})
    assert resp.status_code == 409, resp.text

    # 4) human 覆盖 human → 允许
    resp = client.post(f"/api/memory/recall-audit/{audit_id}/feedback",
                       json={"memory_id": 101, "feedback": "relevant", "feedback_by": "human"})
    assert resp.status_code == 200, resp.text

    # 5) audit 不存在 → 404
    resp = client.post("/api/memory/recall-audit/999999999/feedback",
                       json={"memory_id": 101, "feedback": "relevant", "feedback_by": "agent"})
    assert resp.status_code == 404

    # 6) memory_id 不在 hits 中 → 404
    resp = client.post(f"/api/memory/recall-audit/{audit_id}/feedback",
                       json={"memory_id": 999, "feedback": "relevant", "feedback_by": "agent"})
    assert resp.status_code == 404

    # 7) feedback 值非法 → 422
    resp = client.post(f"/api/memory/recall-audit/{audit_id}/feedback",
                       json={"memory_id": 101, "feedback": "meh", "feedback_by": "agent"})
    assert resp.status_code == 422
