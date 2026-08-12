"""Tests for Memory domain models and service"""
import pytest
from datetime import datetime

from domain.memory.models import MemoryEntry, MemoryKind, MemoryStatus


class TestMemoryEntry:
    """测试 MemoryEntry 模型"""

    def test_create_basic_entry(self):
        """测试创建基本记忆条目"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            scope="global",
            title="测试记忆",
            content="这是一条测试记忆",
            provenance={"session_kind": "user", "channel": "test"},
        )

        assert entry.kind == MemoryKind.EXPERIENCE
        assert entry.scope == "global"
        assert entry.title == "测试记忆"
        assert entry.status == MemoryStatus.TESTING
        assert entry.confidence == 0.3

    def test_to_dict(self):
        """测试转换为字典"""
        entry = MemoryEntry(
            kind=MemoryKind.RULE,
            scope="strategy:v13",
            title="规则测试",
            content="规则内容",
            evidence={"decision_id": 123},
            provenance={"session_kind": "distiller"},
        )

        data = entry.to_dict()
        assert data["kind"] == MemoryKind.RULE
        assert data["scope"] == "strategy:v13"
        assert data["title"] == "规则测试"
        assert data["evidence"] == {"decision_id": 123}

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "kind": "episode",
            "scope": "stock:600519",
            "title": "v13复盘",
            "content": "完整叙事",
            "payload": {"key": "value"},
            "evidence": {"trade_id": 456},
            "status": "active",
            "confidence": 0.7,
            "provenance": {"session_kind": "agent"},
        }

        entry = MemoryEntry.from_dict(data)
        assert entry.kind == "episode"
        assert entry.scope == "stock:600519"
        assert entry.title == "v13复盘"
        assert entry.confidence == 0.7

    def test_evidence_gate_with_evidence(self):
        """测试证据链门禁：有证据时通过"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="有证据",
            content="内容",
            evidence={"decision_id": 123},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "agent"},
        )

        assert entry.validate_evidence_gate() is True

    def test_evidence_gate_without_evidence_testing(self):
        """测试证据链门禁：无证据但 status=testing 时通过"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="无证据测试",
            content="内容",
            evidence={},
            status=MemoryStatus.TESTING,
            provenance={"session_kind": "agent"},
        )

        assert entry.validate_evidence_gate() is False

    def test_evidence_gate_without_evidence_active(self):
        """测试证据链门禁：无证据且 status=active 时失败"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="无证据激活",
            content="内容",
            evidence={},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "agent"},
        )

        assert entry.validate_evidence_gate() is False

    def test_evidence_gate_archived(self):
        """测试证据链门禁：archived 状态不受限制"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="归档",
            content="内容",
            evidence={},
            status=MemoryStatus.ARCHIVED,
            provenance={"session_kind": "agent"},
        )

        assert entry.validate_evidence_gate() is True


class TestEvidenceGateGranularity:
    """2026-08-12 粒度修订：门禁只约束固化类（rule/experience），流水类（episode/stock_note）免证据"""

    def test_episode_without_evidence_passes(self):
        entry = MemoryEntry(
            kind=MemoryKind.EPISODE,
            title="agent 日常笔记",
            content="memory_write 流水，无天然证据",
            evidence=None,
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "cron"},
        )
        assert entry.validate_evidence_gate() is True

    def test_stock_note_without_evidence_passes(self):
        entry = MemoryEntry(
            kind=MemoryKind.STOCK_NOTE,
            title="个股笔记",
            content="300765 观察记录",
            evidence={},
            status=MemoryStatus.TESTING,
            provenance={"session_kind": "user"},
        )
        assert entry.validate_evidence_gate() is True

    def test_rule_without_evidence_fails(self):
        entry = MemoryEntry(
            kind=MemoryKind.RULE,
            title="固化规则无证据",
            content="内容",
            evidence=None,
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "distiller"},
        )
        assert entry.validate_evidence_gate() is False
