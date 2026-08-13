"""Memory Service - 统一记忆服务编排层"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import structlog

from domain.memory.embedding import OllamaEmbeddingService
from domain.memory.hybrid_search import hybrid_rank
from domain.memory.models import MemoryEntry, MemoryKind, MemoryStatus

logger = structlog.get_logger(__name__)


def _load_cosine_floor() -> float:
    """读取向量相似度下限，解析失败回退 0.30"""
    try:
        return float(os.environ.get("MEMORY_RECALL_COSINE_FLOOR", "0.30"))
    except ValueError:
        return 0.30


class MemoryService:
    """记忆服务：统一记忆存储、检索、验证、导出"""

    def __init__(self, repo, embedding_service=None):
        self.repo = repo
        # 默认 ollama 本地 bge-m3；测试可注入 fake/None-valued service
        self.embedding_service = (
            embedding_service if embedding_service is not None else OllamaEmbeddingService()
        )

    # ---------- embedding（写入侧同步计算，失败静默降级） ----------

    def _compute_embedding_json(self, title: str, content: str) -> Optional[str]:
        """计算 title+content 的 embedding，返回 JSON 字符串；失败返回 None"""
        vec = self.embedding_service.embed(f"{title}\n{content}")
        if vec is None:
            logger.warning("embedding unavailable, writing without vector (degraded)")
            return None
        return json.dumps(vec)

    # ---------- 写入 ----------

    def create(self, entry: MemoryEntry) -> Dict[str, Any]:
        """创建新记忆条目

        证据链门禁：evidence 为空时，status 只能是 testing（或被拒）
        """
        # 证据链门禁
        if not entry.validate_evidence_gate():
            if entry.status == MemoryStatus.TESTING:
                logger.warning(
                    f"memory create without evidence, status forced to testing: {entry.title}"
                )
                entry.status = MemoryStatus.TESTING
            else:
                raise ValueError(
                    f"No Execution, No Memory: evidence required for status={entry.status}"
                )

        # 同步计算 embedding（ollama 不可用时为 None，写入不阻塞）
        if entry.embedding is None:
            entry.embedding = self._compute_embedding_json(entry.title, entry.content)

        result = self.repo.create(entry)
        logger.info(f"memory created: id={result['id']} kind={entry.kind} title={entry.title}")
        return result

    def update(self, entry_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新记忆条目"""
        existing = self.repo.get_by_id(entry_id)
        if not existing:
            raise ValueError(f"Memory entry not found: id={entry_id}")

        # 如果更新 status 到 active，检查证据链
        if updates.get("status") == MemoryStatus.ACTIVE:
            evidence = updates.get("evidence", existing.get("evidence", {}))
            if not evidence or not any(evidence.values()):
                raise ValueError(
                    f"Cannot promote to active without evidence: id={entry_id}"
                )

        # title/content 变更时重算 embedding
        if "title" in updates or "content" in updates:
            title = updates.get("title", existing.get("title", ""))
            content = updates.get("content", existing.get("content", ""))
            updates["embedding"] = self._compute_embedding_json(title, content)

        result = self.repo.update(entry_id, updates)
        logger.info(f"memory updated: id={entry_id}")
        return result

    # ---------- 查询 ----------

    def search(
        self,
        q: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """检索记忆（本期关键词 ILIKE，W1.3 升级向量检索）

        Args:
            q: 查询关键词（搜索 title + content）
            scope: 范围过滤（global | stock:X | strategy:Y | sector:Z）
            kind: 类型过滤（rule | episode | experience | stock_note）
            status: 状态过滤（testing | active | deprecated | archived）
            limit: 返回数量上限
        """
        results = self.repo.search(
            q=q, scope=scope, kind=kind, status=status, limit=limit
        )
        logger.info(
            f"memory search: q={q} scope={scope} kind={kind} status={status} found={len(results)}"
        )
        return results

    def hybrid_search(
        self,
        q: str,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """混合检索（W1.3）：BM25(jieba) + 向量余弦 + RRF 融合

        ollama 不可达时自动降级纯 BM25，返回 degraded:true，不抛错。

        Returns:
            {"items": [...带 score/source(bm25|vector|both)],
             "total": N, "degraded": bool, "strategy": "hybrid|bm25|vector|none"}
        """
        candidates = self.repo.list_filtered(scope=scope, kind=kind, status=status)
        query_embedding = self.embedding_service.embed(q)
        result = hybrid_rank(
            q, candidates, query_embedding, limit, cosine_floor=_load_cosine_floor()
        )
        logger.info(
            f"memory hybrid search: q={q} strategy={result['strategy']} "
            f"degraded={result['degraded']} found={result['total']}"
        )
        return result

    def get_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取记忆"""
        return self.repo.get_by_id(entry_id)

    # ---------- 验证与置信度爬坡 ----------

    def validate(
        self, entry_id: int, success: bool, promote: bool = False
    ) -> Dict[str, Any]:
        """验证记忆条目，更新置信度

        置信度爬坡规则（W1.2 规划）：
        - < 10 样本：0.3
        - 10-30 样本：0.5
        - > 30 样本：0.7

        Args:
            entry_id: 记忆 ID
            success: 本次验证是否成功
            promote: 是否提升状态（testing → active）
        """
        existing = self.repo.get_by_id(entry_id)
        if not existing:
            raise ValueError(f"Memory entry not found: id={entry_id}")

        validation_count = existing.get("validation_count", 0) + 1
        success_count = existing.get("success_count", 0) + (1 if success else 0)

        # 置信度爬坡
        if validation_count < 10:
            confidence = 0.3
        elif validation_count < 30:
            confidence = 0.5
        else:
            confidence = 0.7

        updates = {
            "validation_count": validation_count,
            "success_count": success_count,
            "confidence": confidence,
        }

        # 提升状态（testing → active）
        if promote and existing.get("status") == MemoryStatus.TESTING:
            # 检查证据链
            if not existing.get("evidence") or not any(existing["evidence"].values()):
                raise ValueError(
                    f"Cannot promote to active without evidence: id={entry_id}"
                )
            updates["status"] = MemoryStatus.ACTIVE
            logger.info(f"memory promoted to active: id={entry_id}")

        result = self.repo.update(entry_id, updates)
        logger.info(
            f"memory validated: id={entry_id} success={success} "
            f"validation_count={validation_count} confidence={confidence}"
        )
        return result

    # ---------- 替代关系 ----------

    def supersede(self, old_id: int, new_id: int) -> Dict[str, Any]:
        """标记旧记忆被新记忆替代

        Args:
            old_id: 被替代的旧记忆 ID
            new_id: 替代的新记忆 ID
        """
        old = self.repo.get_by_id(old_id)
        new = self.repo.get_by_id(new_id)

        if not old or not new:
            raise ValueError(f"Memory entry not found: old_id={old_id} new_id={new_id}")

        # 标记旧记忆为 deprecated
        self.repo.update(old_id, {"status": MemoryStatus.DEPRECATED})

        # 更新新记忆的 supersedes 字段
        self.repo.update(new_id, {"supersedes": old_id})

        logger.info(f"memory superseded: old_id={old_id} new_id={new_id}")
        return {"old_id": old_id, "new_id": new_id, "status": "superseded"}

    # ---------- 导出/导入 ----------

    def export_all(self) -> List[Dict[str, Any]]:
        """全量导出（JSON 格式，迁移保险用）"""
        results = self.repo.get_all()
        logger.info(f"memory export: total={len(results)}")
        return results

    def import_entries(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量导入记忆条目（往返无损用）

        Returns:
            {"imported": count, "skipped": count, "errors": [...]}
        """
        imported = 0
        skipped = 0
        errors = []

        for data in entries:
            try:
                # 检查是否已存在（根据 title + source + provenance 去重）
                existing = self.repo.find_duplicate(
                    title=data.get("title"),
                    source=data.get("source"),
                    provenance=data.get("provenance"),
                )
                if existing:
                    skipped += 1
                    continue

                entry = MemoryEntry.from_dict(data)
                self.create(entry)
                imported += 1
            except Exception as e:
                errors.append({"data": data, "error": str(e)})
                logger.error(f"memory import failed: {e}")

        logger.info(
            f"memory import done: imported={imported} skipped={skipped} errors={len(errors)}"
        )
        return {"imported": imported, "skipped": skipped, "errors": errors}
