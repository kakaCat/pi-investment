"""Memory domain models and types"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class MemoryKind(str, Enum):
    """记忆类型"""
    RULE = "rule"              # 规则/原则（蒸馏产出，需人工确认）
    EPISODE = "episode"        # 情节记忆（完整叙事，如 v13 复盘）
    EXPERIENCE = "experience"  # 经验（结构化，条件→动作）
    STOCK_NOTE = "stock_note"  # 个股笔记


class MemoryStatus(str, Enum):
    """记忆状态"""
    TESTING = "testing"        # 测试中（候选规则，需验证）
    ACTIVE = "active"          # 激活（生产使用）
    DEPRECATED = "deprecated"  # 废弃（被更好规则替代）
    ARCHIVED = "archived"      # 归档（历史参考）


class MemoryEntry:
    """统一记忆条目模型"""

    def __init__(
        self,
        id: Optional[int] = None,
        kind: str = MemoryKind.EXPERIENCE,
        scope: str = "global",
        title: str = "",
        content: str = "",
        payload: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        status: str = MemoryStatus.TESTING,
        confidence: float = 0.3,
        validation_count: int = 0,
        success_count: int = 0,
        provenance: Optional[Dict[str, Any]] = None,
        last_recalled_at: Optional[datetime] = None,
        source: Optional[str] = None,
        supersedes: Optional[int] = None,
        embedding: Optional[list] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.kind = kind
        self.scope = scope
        self.title = title
        self.content = content
        self.payload = payload or {}
        self.evidence = evidence or {}
        self.status = status
        self.confidence = confidence
        self.validation_count = validation_count
        self.success_count = success_count
        self.provenance = provenance or {}
        self.last_recalled_at = last_recalled_at
        self.source = source
        self.supersedes = supersedes
        self.embedding = embedding
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "kind": self.kind,
            "scope": self.scope,
            "title": self.title,
            "content": self.content,
            "payload": self.payload,
            "evidence": self.evidence,
            "status": self.status,
            "confidence": self.confidence,
            "validation_count": self.validation_count,
            "success_count": self.success_count,
            "provenance": self.provenance,
            "last_recalled_at": self.last_recalled_at.isoformat() if self.last_recalled_at else None,
            "source": self.source,
            "supersedes": self.supersedes,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """从字典创建"""
        return cls(
            id=data.get("id"),
            kind=data.get("kind", MemoryKind.EXPERIENCE),
            scope=data.get("scope", "global"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            payload=data.get("payload"),
            evidence=data.get("evidence"),
            status=data.get("status", MemoryStatus.TESTING),
            confidence=data.get("confidence", 0.3),
            validation_count=data.get("validation_count", 0),
            success_count=data.get("success_count", 0),
            provenance=data.get("provenance"),
            last_recalled_at=data.get("last_recalled_at"),
            source=data.get("source"),
            supersedes=data.get("supersedes"),
            embedding=data.get("embedding"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def validate_evidence_gate(self) -> bool:
        """证据链门禁（2026-08-12 粒度修订）

        "No Execution, No Memory" 只约束固化类记忆：
        - kind=rule/experience：status>=testing 必须有非空 evidence（蒸馏/经验固化必须引用执行证据）
        - kind=episode/stock_note：流水类笔记免证据（agent 日常 memory_write 无天然证据）
        """
        GATED_KINDS = (MemoryKind.RULE, MemoryKind.EXPERIENCE)
        if self.kind in GATED_KINDS and self.status in [MemoryStatus.TESTING, MemoryStatus.ACTIVE]:
            if not self.evidence or not any(self.evidence.values()):
                return False
        return True
