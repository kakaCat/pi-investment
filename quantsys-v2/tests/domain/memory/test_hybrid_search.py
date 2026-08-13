"""W1.3 混合检索测试：BM25 + 向量 + RRF + 降级

分两层：
- 纯函数层（hybrid_search.py）：分词/BM25/余弦/RRF，不依赖 DB 与 ollama
- 服务/路由层：fake embedding service 注入，不依赖真实 ollama；
  路由层降级路径用 OLLAMA_BASE_URL 指向废弃端口确定性触发
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.memory import hybrid_search as hs
from domain.memory.embedding import OllamaEmbeddingService
from domain.memory.models import MemoryEntry, MemoryKind
from domain.memory.service import MemoryService


# ---------- 纯函数层 ----------


def _item(i, title, content, embedding=None):
    return {
        "id": i,
        "title": title,
        "content": content,
        "embedding": embedding,
    }


class TestTokenize:
    def test_chinese_segmentation(self):
        tokens = hs.tokenize("崩盘日买入抗跌股")
        assert "崩盘" in tokens
        assert "买入" in tokens

    def test_empty(self):
        assert hs.tokenize("") == []
        assert hs.tokenize(None) == []


class TestBM25:
    def test_relevant_doc_ranks_first(self):
        items = [
            _item(1, "v13 崩盘日调仓复盘", "创业板崩盘日 -7.35%，买入 5 只抗跌股后 V 型反弹"),
            _item(2, "止盈规则", "+10% 机械止盈，不格局"),
            _item(3, "筹码分布", "获利盘比例与成本区间"),
        ]
        ranked = hs.bm25_rank("崩盘日买入", items)
        assert ranked[0]["id"] == 1
        assert all("bm25_score" in r for r in ranked)

    def test_no_match_returns_empty(self):
        items = [_item(1, "止盈规则", "机械止盈")]
        assert hs.bm25_rank("美联储加息缩表", items) == []


class TestVector:
    def test_cosine_ordering_and_null_skip(self):
        items = [
            _item(1, "a", "x", json.dumps([1.0, 0.0])),
            _item(2, "b", "y", json.dumps([0.0, 1.0])),
            _item(3, "c", "z", None),  # 无 embedding，跳过
        ]
        ranked = hs.vector_rank([0.9, 0.1], items)
        assert [r["id"] for r in ranked] == [1, 2]
        assert ranked[0]["vector_score"] > ranked[1]["vector_score"]

    def test_parse_embedding_bad(self):
        assert hs.parse_embedding("not-json") is None
        assert hs.parse_embedding("") is None
        assert hs.parse_embedding(None) is None
        assert hs.parse_embedding([1.0]) == [1.0]


class TestRRF:
    def test_both_sources_win(self):
        bm25 = [_item(1, "t1", "c1"), _item(2, "t2", "c2")]
        vec = [_item(2, "t2", "c2"), _item(3, "t3", "c3")]
        merged = hs.rrf_merge(bm25, vec)
        by_id = {m["id"]: m for m in merged}
        # id=2 两路都命中，source=both
        assert by_id[2]["source"] == "both"
        assert by_id[1]["source"] == "bm25"
        assert by_id[3]["source"] == "vector"
        # 双路命中者 RRF 分 = 两路 rank 分之和，高于单路
        assert by_id[2]["score"] > by_id[1]["score"]
        assert all("score" in m for m in merged)


class TestHybridRank:
    def test_degraded_when_no_query_embedding(self):
        items = [_item(1, "崩盘日买入", "v13 抗跌股")]
        result = hs.hybrid_rank("崩盘", items, query_embedding=None, limit=10)
        assert result["degraded"] is True
        assert result["strategy"] == "bm25"
        assert result["items"][0]["source"] == "bm25"
        assert "score" in result["items"][0]

    def test_hybrid_strategy_when_both_available(self):
        items = [
            _item(1, "崩盘日买入", "v13 抗跌股反弹", json.dumps([1.0, 0.0])),
            _item(2, "止盈", "机械止盈", json.dumps([0.0, 1.0])),
        ]
        result = hs.hybrid_rank("崩盘买入", items, query_embedding=[1.0, 0.0], limit=10)
        assert result["degraded"] is False
        assert result["strategy"] == "hybrid"
        assert result["items"][0]["id"] == 1

    def test_empty_corpus(self):
        result = hs.hybrid_rank("崩盘", [], query_embedding=None, limit=10)
        assert result["items"] == []
        assert result["strategy"] == "none"


class TestCosineFloor:
    def test_below_floor_filtered(self):
        # 查询向量 [1,0]；item1 同向 sim=1.0，item2 正交 sim=0.0
        items = [_item(1, "t1", "c1", [1.0, 0.0]), _item(2, "t2", "c2", [0.0, 1.0])]
        ranked = hs.vector_rank([1.0, 0.0], items, cosine_floor=0.30)
        assert [r["id"] for r in ranked] == [1]

    def test_floor_zero_backward_compatible(self):
        items = [_item(1, "t1", "c1", [1.0, 0.0]), _item(2, "t2", "c2", [0.0, 1.0])]
        ranked = hs.vector_rank([1.0, 0.0], items, cosine_floor=0.0)
        assert len(ranked) == 2

    def test_default_floor_keeps_old_behavior(self):
        # 不传 cosine_floor = 0.0，与现状一致
        items = [_item(1, "t1", "c1", [1.0, 0.0]), _item(2, "t2", "c2", [0.0, 1.0])]
        assert len(hs.vector_rank([1.0, 0.0], items)) == 2

    def test_hybrid_rank_threads_floor(self):
        # 向量无一过线且 BM25 零命中 → none
        items = [_item(1, "t1", "c1", [0.0, 1.0])]
        result = hs.hybrid_rank(
            "完全无关的词xyz", items, [1.0, 0.0], 5, cosine_floor=0.30
        )
        assert result["strategy"] == "none"
        assert result["items"] == []


# ---------- embedding 客户端降级 ----------


class TestOllamaEmbeddingDegrade:
    def test_unreachable_returns_none(self):
        # 127.0.0.1:9 是 discard 端口，连接即拒
        svc = OllamaEmbeddingService(base_url="http://127.0.0.1:9", connect_timeout=1.0)
        assert svc.embed("崩盘日买入") is None

    def test_empty_text_returns_none(self):
        svc = OllamaEmbeddingService(base_url="http://127.0.0.1:9", connect_timeout=1.0)
        assert svc.embed("") is None
        assert svc.embed("   ") is None


# ---------- 服务层（fake embedding 注入） ----------


class _FakeEmbedder:
    """固定向量，按文本哈希给方向，保证可断言"""

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        if self.fail:
            return None
        # 含"崩盘"的文本给 [1,0]，其他给 [0,1]
        return [1.0, 0.0] if "崩盘" in text else [0.0, 1.0]


class _FakeRepo:
    def __init__(self):
        self.rows = {}
        self._next = 1

    def create(self, entry):
        d = entry.to_dict()
        d["id"] = self._next
        self._next += 1
        self.rows[d["id"]] = d
        return d

    def get_by_id(self, entry_id):
        return self.rows.get(entry_id)

    def update(self, entry_id, updates):
        self.rows[entry_id].update(updates)
        return self.rows[entry_id]

    def list_filtered(self, scope=None, kind=None, status=None, max_rows=5000):
        rows = list(self.rows.values())
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        return rows


def _entry(title, content, kind=MemoryKind.EPISODE):
    return MemoryEntry(
        kind=kind,
        scope="global",
        title=title,
        content=content,
        evidence={"trades": ["t1"]},
        status="active",
        provenance={"session_kind": "user", "channel": "pytest"},
        source="pytest",
    )


class TestServiceEmbeddingWrite:
    def test_create_computes_embedding_json(self):
        repo, embedder = _FakeRepo(), _FakeEmbedder()
        svc = MemoryService(repo, embedding_service=embedder)
        result = svc.create(_entry("崩盘日复盘", "买入抗跌股"))
        assert embedder.calls == 1
        assert json.loads(result["embedding"]) == [1.0, 0.0]

    def test_create_degrades_when_embed_fails(self):
        repo, embedder = _FakeRepo(), _FakeEmbedder(fail=True)
        svc = MemoryService(repo, embedding_service=embedder)
        result = svc.create(_entry("止盈", "机械止盈"))
        assert result["embedding"] is None  # 不抛错，NULL 写入

    def test_update_title_recomputes_embedding(self):
        repo, embedder = _FakeRepo(), _FakeEmbedder()
        svc = MemoryService(repo, embedding_service=embedder)
        created = svc.create(_entry("止盈", "机械止盈"))
        assert json.loads(created["embedding"]) == [0.0, 1.0]
        updated = svc.update(created["id"], {"title": "崩盘日止损"})
        assert json.loads(updated["embedding"]) == [1.0, 0.0]

    def test_update_without_text_change_keeps_embedding(self):
        repo, embedder = _FakeRepo(), _FakeEmbedder()
        svc = MemoryService(repo, embedding_service=embedder)
        created = svc.create(_entry("止盈", "机械止盈"))
        calls_before = embedder.calls
        svc.update(created["id"], {"confidence": 0.5})
        assert embedder.calls == calls_before


class TestServiceHybridSearch:
    def test_hybrid_search_returns_score_source(self):
        repo, embedder = _FakeRepo(), _FakeEmbedder()
        svc = MemoryService(repo, embedding_service=embedder)
        svc.create(_entry("v13 崩盘日调仓", "创业板崩盘买入抗跌股，V 型反弹"))
        svc.create(_entry("止盈规则", "+10% 机械止盈"))

        result = svc.hybrid_search("崩盘日买入", kind="episode")
        assert result["degraded"] is False
        assert result["total"] >= 1
        top = result["items"][0]
        assert "崩盘" in top["title"]
        assert "score" in top and top["source"] in ("bm25", "vector", "both")

    def test_hybrid_search_degraded(self):
        repo, embedder = _FakeRepo(), _FakeEmbedder(fail=True)
        svc = MemoryService(repo, embedding_service=embedder)
        svc.create(_entry("v13 崩盘日调仓", "崩盘买入抗跌股"))
        result = svc.hybrid_search("崩盘买入")
        assert result["degraded"] is True
        assert result["strategy"] == "bm25"
        assert result["items"][0]["source"] == "bm25"


# ---------- 路由层（真实 quant_test 库 + 降级路径确定性触发） ----------


@pytest.fixture
def route_client(monkeypatch):
    # 指向废弃端口：embed 必然失败 → degraded:true，不依赖 ollama 状态
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    from adapters.inbound.fastapi_app.routes.memory_async import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_search_returns_score_source_degraded(route_client):
    payload = {
        "kind": "episode",
        "scope": "global",
        "title": "test_w13_route_崩盘日买入",
        "content": "创业板崩盘日买入抗跌股，V 型反弹全部盈利",
        "evidence": {"trades": ["simulation_trades v13"]},
        "status": "active",
        "provenance": {"session_kind": "user", "channel": "pytest"},
        "source": "pytest",
    }
    resp = route_client.post("/api/memory", json=payload)
    assert resp.status_code == 200, resp.text
    entry_id = resp.json()["id"]
    try:
        resp = route_client.get("/api/memory/search", params={"q": "崩盘日买入抗跌股"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["degraded"] is True  # ollama 指向废弃端口
        assert body["items"], "BM25 降级路径应仍命中"
        top_ids = [i["id"] for i in body["items"][:3]]
        assert entry_id in top_ids
        for item in body["items"]:
            assert "score" in item
            assert item["source"] == "bm25"
    finally:
        from infrastructure.persistence.orm import get_session
        from sqlalchemy import text

        session = get_session()
        session.execute(
            text("DELETE FROM quant.memory_entries WHERE id = :id"), {"id": entry_id}
        )
        session.commit()


def test_route_search_filter_without_q(route_client):
    resp = route_client.get("/api/memory/search", params={"kind": "episode", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy"] == "filter"
    assert "items" in body
