"""Integration tests for Memory API - 完整 CRUD + 迁移验证"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from adapters.outbound.repositories.memory_repository import MemoryRepository
from domain.memory import MemoryEntry, MemoryKind, MemoryStatus, MemoryService


class TestMemoryIntegration:
    """集成测试：Repository + Service + Database"""

    @pytest.fixture
    def repo(self):
        """创建 repository 实例"""
        return MemoryRepository()

    @pytest.fixture
    def service(self, repo):
        """创建 service 实例"""
        return MemoryService(repo)

    @pytest.fixture(autouse=True)
    def cleanup(self, repo):
        """每个测试后清理数据"""
        yield
        try:
            from sqlalchemy import text
            repo.session.execute(text("DELETE FROM quant.memory_entries WHERE title LIKE 'test_%'"))
            repo.session.commit()
        except Exception:
            repo.session.rollback()

    def test_create_and_retrieve(self, service):
        """测试创建和检索记忆"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            scope="global",
            title="test_create_retrieve",
            content="测试内容",
            evidence={"decision_id": 123},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "user", "channel": "test"},
        )

        # 创建
        result = service.create(entry)
        assert result["id"] is not None
        entry_id = result["id"]

        # 检索
        retrieved = service.get_by_id(entry_id)
        assert retrieved is not None
        assert retrieved["title"] == "test_create_retrieve"
        assert retrieved["kind"] == MemoryKind.EXPERIENCE
        assert retrieved["evidence"] == {"decision_id": 123}

    def test_search_by_keyword(self, service):
        """测试关键词搜索"""
        # 创建多条记忆
        entries = [
            MemoryEntry(
                kind=MemoryKind.EXPERIENCE,
                title="test_search_崩盘日买入",
                content="崩盘日相对强度买入策略",
                evidence={"decision_id": 1},
                provenance={"session_kind": "agent"},
            ),
            MemoryEntry(
                kind=MemoryKind.EXPERIENCE,
                title="test_search_止盈规则",
                content="+10% 机械止盈",
                evidence={"decision_id": 2},
                provenance={"session_kind": "agent"},
            ),
        ]

        for e in entries:
            service.create(e)

        # 搜索 "崩盘"
        results = service.search(q="崩盘")
        assert len(results) >= 1
        assert any("崩盘" in r["title"] or "崩盘" in r["content"] for r in results)

        # 搜索 "止盈"
        results = service.search(q="止盈")
        assert len(results) >= 1
        assert any("止盈" in r["title"] or "止盈" in r["content"] for r in results)

    def test_search_by_filters(self, service):
        """测试过滤搜索"""
        # 创建不同类型和状态的记忆
        service.create(
            MemoryEntry(
                kind=MemoryKind.RULE,
                title="test_filter_rule",
                content="规则内容",
                evidence={"decision_id": 1},
                status=MemoryStatus.ACTIVE,
                provenance={"session_kind": "distiller"},
            )
        )
        service.create(
            MemoryEntry(
                kind=MemoryKind.EPISODE,
                title="test_filter_episode",
                content="情节内容",
                evidence={"session_id": "abc"},
                status=MemoryStatus.TESTING,
                provenance={"session_kind": "agent"},
            )
        )

        # 按 kind 过滤
        results = service.search(kind=MemoryKind.RULE)
        assert all(r["kind"] == MemoryKind.RULE for r in results if r["title"].startswith("test_filter"))

        # 按 status 过滤
        results = service.search(status=MemoryStatus.ACTIVE)
        assert all(r["status"] == MemoryStatus.ACTIVE for r in results if r["title"].startswith("test_filter"))

    def test_validate_and_confidence_climb(self, service):
        """测试验证和置信度爬坡"""
        # 创建 testing 记忆
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="test_validate",
            content="测试验证",
            evidence={"decision_id": 123},
            status=MemoryStatus.TESTING,
            provenance={"session_kind": "agent"},
        )
        result = service.create(entry)
        entry_id = result["id"]

        # 验证 5 次（< 10 样本，置信度 0.3）
        for _ in range(5):
            service.validate(entry_id, success=True)

        retrieved = service.get_by_id(entry_id)
        assert retrieved["validation_count"] == 5
        assert retrieved["confidence"] == 0.3

        # 继续验证到 15 次（10-30 样本，置信度 0.5）
        for _ in range(10):
            service.validate(entry_id, success=True)

        retrieved = service.get_by_id(entry_id)
        assert retrieved["validation_count"] == 15
        assert retrieved["confidence"] == 0.5

        # 继续验证到 35 次（> 30 样本，置信度 0.7）
        for _ in range(20):
            service.validate(entry_id, success=True)

        retrieved = service.get_by_id(entry_id)
        assert retrieved["validation_count"] == 35
        assert retrieved["confidence"] == 0.7

    def test_promote_to_active(self, service):
        """测试提升到 active 状态"""
        entry = MemoryEntry(
            kind=MemoryKind.RULE,
            title="test_promote",
            content="待提升规则",
            evidence={"decision_id": 123},
            status=MemoryStatus.TESTING,
            provenance={"session_kind": "distiller"},
        )
        result = service.create(entry)
        entry_id = result["id"]

        # 提升到 active
        service.validate(entry_id, success=True, promote=True)

        retrieved = service.get_by_id(entry_id)
        assert retrieved["status"] == MemoryStatus.ACTIVE

    def test_supersede(self, service):
        """测试记忆替代"""
        # 创建旧记忆
        old_entry = MemoryEntry(
            kind=MemoryKind.RULE,
            title="test_supersede_old",
            content="旧规则",
            evidence={"decision_id": 1},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "distiller"},
        )
        old_result = service.create(old_entry)
        old_id = old_result["id"]

        # 创建新记忆
        new_entry = MemoryEntry(
            kind=MemoryKind.RULE,
            title="test_supersede_new",
            content="新规则（改进版）",
            evidence={"decision_id": 2},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "distiller"},
        )
        new_result = service.create(new_entry)
        new_id = new_result["id"]

        # 标记替代关系
        service.supersede(old_id=old_id, new_id=new_id)

        # 验证
        old_retrieved = service.get_by_id(old_id)
        new_retrieved = service.get_by_id(new_id)

        assert old_retrieved["status"] == MemoryStatus.DEPRECATED
        assert new_retrieved["supersedes"] == old_id

    def test_export_import_roundtrip(self, service):
        """测试导出/导入往返无损"""
        # 创建测试数据
        entries = [
            MemoryEntry(
                kind=MemoryKind.EXPERIENCE,
                title="test_export_1",
                content="导出测试1",
                evidence={"decision_id": 1},
                provenance={"session_kind": "agent"},
            ),
            MemoryEntry(
                kind=MemoryKind.RULE,
                title="test_export_2",
                content="导出测试2",
                evidence={"decision_id": 2},
                provenance={"session_kind": "distiller"},
            ),
        ]

        created_ids = []
        for e in entries:
            result = service.create(e)
            created_ids.append(result["id"])

        # 导出
        exported = service.export_all()
        exported_test = [e for e in exported if e["title"].startswith("test_export")]
        assert len(exported_test) == 2

        # 删除原数据
        from infrastructure.persistence.orm import get_session
        from sqlalchemy import text
        temp_session = get_session()
        for eid in created_ids:
            temp_session.execute(text(f"DELETE FROM quant.memory_entries WHERE id = {eid}"))
        temp_session.commit()

        # 导入
        result = service.import_entries(exported_test)
        assert result["imported"] == 2
        assert result["skipped"] == 0

        # 验证
        results = service.search(q="test_export")
        assert len(results) == 2

    def test_evidence_gate_enforcement(self, service):
        """测试证据链门禁"""
        # 无证据的 active 记忆应该被拒绝
        entry_no_evidence = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="test_no_evidence",
            content="无证据",
            evidence={},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "agent"},
        )

        with pytest.raises(ValueError, match="No Execution, No Memory"):
            service.create(entry_no_evidence)

        # 无证据的 testing 记忆应该被允许
        entry_testing = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="test_testing_no_evidence",
            content="测试中无证据",
            evidence={},
            status=MemoryStatus.TESTING,
            provenance={"session_kind": "agent"},
        )

        result = service.create(entry_testing)
        assert result["id"] is not None
