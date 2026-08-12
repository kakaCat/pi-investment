"""混合检索引擎（W1.3）：BM25(jieba) + 向量余弦 + RRF 融合

参照 TencentDB-Agent-Memory src/core/tools/memory-search.ts 的思想裁剪：
- 两路检索各自容错，单路失败不致命
- RRF k=60 融合，item 标注命中来源（bm25|vector|both）
- embedding 不可用时降级纯 BM25，响应标 degraded:true

设计定稿（2026-08-12）：embedding 存 memory_entries.embedding（TEXT 列 JSON 数组），
余弦相似度在应用层算（条目量级数百，无需 pgvector）。
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

import jieba
import structlog
from rank_bm25 import BM25Okapi

logger = structlog.get_logger(__name__)

# RRF 常数（原始论文标准值）
RRF_K = 60

# 候选语料上限（条目量级数百，全量载入内存索引足够）
MAX_CORPUS = 5000


class _BM25Lucene(BM25Okapi):
    """Lucene 风格 idf：log(1 + (N-n+0.5)/(n+0.5))，恒非负。

    rank_bm25 的 BM25Okapi 原版 idf 在小语料（查询词出现于 ≥50% 文档）时为负，
    会导致匹配文档得分 < 0 被误杀——本域语料常只有数百条，必须规避。
    """

    def _calc_idf(self, nd):
        n_docs = self.corpus_size
        self.idf = {}
        idf_sum = 0.0
        for word, freq in nd.items():
            self.idf[word] = math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))
            idf_sum += self.idf[word]
        self.average_idf = idf_sum / len(nd) if nd else 0.0


def tokenize(text: str) -> List[str]:
    """jieba 搜索引擎模式分词，过滤空白与单字符标点"""
    if not text:
        return []
    return [t.strip() for t in jieba.lcut_for_search(text) if t.strip()]


def doc_text(item: Dict[str, Any]) -> str:
    """条目索引文本：title 权重高于 content（重复一次）"""
    title = item.get("title") or ""
    content = item.get("content") or ""
    return f"{title} {title} {content}"


def parse_embedding(raw: Any) -> Optional[List[float]]:
    """解析 TEXT 列中的 JSON 向量，非法/为空返回 None"""
    if not raw:
        return None
    if isinstance(raw, list):
        return raw
    try:
        vec = json.loads(raw)
        return vec if isinstance(vec, list) and vec else None
    except (json.JSONDecodeError, TypeError):
        return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度，维度不一致或零向量返回 0"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def bm25_rank(query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """BM25 排序，返回带 bm25_score 的降序列表（零分条目剔除）"""
    if not items:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    corpus = [tokenize(doc_text(it)) for it in items]
    bm25 = _BM25Lucene(corpus)
    scores = bm25.get_scores(query_tokens)
    ranked = [
        {**it, "bm25_score": float(s)} for it, s in zip(items, scores) if s > 0
    ]
    ranked.sort(key=lambda x: x["bm25_score"], reverse=True)
    return ranked


def vector_rank(
    query_embedding: List[float], items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """向量余弦排序（应用层计算），无 embedding 的条目跳过"""
    ranked = []
    for it in items:
        vec = parse_embedding(it.get("embedding"))
        if vec is None:
            continue
        sim = cosine_similarity(query_embedding, vec)
        if sim > 0:
            ranked.append({**it, "vector_score": sim})
    ranked.sort(key=lambda x: x["vector_score"], reverse=True)
    return ranked


def rrf_merge(
    bm25_list: List[Dict[str, Any]], vector_list: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """RRF 融合（k=60），score 为 RRF 分，source 标注命中来源"""
    scores: Dict[Any, float] = {}
    sources: Dict[Any, set] = {}
    items_by_id: Dict[Any, Dict[str, Any]] = {}

    for rank, it in enumerate(bm25_list):
        key = it["id"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        sources.setdefault(key, set()).add("bm25")
        items_by_id.setdefault(key, it)

    for rank, it in enumerate(vector_list):
        key = it["id"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        sources.setdefault(key, set()).add("vector")
        items_by_id.setdefault(key, it)

    merged = []
    for key, score in scores.items():
        src = sources[key]
        source = "both" if len(src) > 1 else next(iter(src))
        it = items_by_id[key]
        merged.append({**it, "score": score, "source": source})

    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged


def hybrid_rank(
    query: str,
    items: List[Dict[str, Any]],
    query_embedding: Optional[List[float]],
    limit: int,
) -> Dict[str, Any]:
    """混合检索主入口

    Args:
        query: 查询文本
        items: 候选语料（已过 scope/kind/status 过滤）
        query_embedding: 查询向量；None 表示 embedding 不可用（降级纯 BM25）
        limit: 返回数量上限

    Returns:
        {"items": [...带 score/source], "total": N, "degraded": bool, "strategy": str}
    """
    candidate_k = max(limit * 3, 10)
    degraded = query_embedding is None

    bm25_list = bm25_rank(query, items)[:candidate_k]
    vector_list = (
        vector_rank(query_embedding, items)[:candidate_k] if query_embedding else []
    )

    if bm25_list and vector_list:
        strategy = "hybrid"
        merged = rrf_merge(bm25_list, vector_list)
    elif bm25_list:
        strategy = "bm25"
        merged = [
            {**it, "score": it["bm25_score"], "source": "bm25"} for it in bm25_list
        ]
    elif vector_list:
        strategy = "vector"
        merged = [
            {**it, "score": it["vector_score"], "source": "vector"}
            for it in vector_list
        ]
    else:
        strategy = "none"
        merged = []

    merged = merged[:limit]
    logger.info(
        f"hybrid search: q={query!r} strategy={strategy} degraded={degraded} "
        f"bm25={len(bm25_list)} vector={len(vector_list)} merged={len(merged)}"
    )
    return {
        "items": merged,
        "total": len(merged),
        "degraded": degraded,
        "strategy": strategy,
    }
