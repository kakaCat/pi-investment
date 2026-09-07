"""Tests for Memory Service"""
import pytest
from unittest.mock import Mock, MagicMock

from domain.memory.models import MemoryEntry, MemoryKind, MemoryStatus
from domain.memory.service import MemoryService


class TestMemoryService:
    """测试 MemoryService"""

    @pytest.fixture
    def mock_repo(self):
        """Mock repository"""
        return Mock()

    @pytest.fixture
    def service(self, mock_repo):
        """创建 service 实例"""
        return MemoryService(mock_repo)

    def test_create_with_evidence(self, service, mock_repo):
        """测试创建有证据的记忆"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="测试",
            content="内容",
            evidence={"decision_id": 123},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "agent"},
        )

        mock_repo.create.return_value = {"id": 1, "title": "测试"}

        result = service.create(entry)

        assert result["id"] == 1
        mock_repo.create.assert_called_once()

    def test_create_without_evidence_testing(self, service, mock_repo):
        """测试创建无证据的 testing 记忆（强制为 testing）"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="测试",
            content="内容",
            evidence={},
            status=MemoryStatus.TESTING,
            provenance={"session_kind": "agent"},
        )

        mock_repo.create.return_value = {"id": 1, "title": "测试"}

        result = service.create(entry)

        assert result["id"] == 1
        assert entry.status == MemoryStatus.TESTING

    def test_create_without_evidence_active_fails(self, service, mock_repo):
        """测试创建无证据的 active 记忆失败"""
        entry = MemoryEntry(
            kind=MemoryKind.EXPERIENCE,
            title="测试",
            content="内容",
            evidence={},
            status=MemoryStatus.ACTIVE,
            provenance={"session_kind": "agent"},
        )

        with pytest.raises(ValueError, match="No Execution, No Memory"):
            service.create(entry)

    def test_search(self, service, mock_repo):
        """测试检索记忆"""
        mock_repo.search.return_value = [
            {"id": 1, "title": "记忆1"},
            {"id": 2, "title": "记忆2"},
        ]

        results = service.search(q="测试", kind=MemoryKind.EXPERIENCE, status=MemoryStatus.ACTIVE)

        assert len(results) == 2
        mock_repo.search.assert_called_once_with(
            q="测试", scope=None, kind=MemoryKind.EXPERIENCE, status=MemoryStatus.ACTIVE, limit=20
        )

    def test_validate_confidence_climb(self, service, mock_repo):
        """测试置信度爬坡"""
        # < 10 样本：0.3
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "validation_count": 5,
            "success_count": 3,
            "status": MemoryStatus.TESTING,
            "evidence": {"decision_id": 123},
        }
        mock_repo.update.return_value = {"id": 1, "confidence": 0.3}

        result = service.validate(1, success=True)
        assert mock_repo.update.call_args[0][1]["confidence"] == 0.3

        # 10-30 样本：0.5
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "validation_count": 15,
            "success_count": 10,
            "status": MemoryStatus.TESTING,
            "evidence": {"decision_id": 123},
        }

        result = service.validate(1, success=True)
        assert mock_repo.update.call_args[0][1]["confidence"] == 0.5

        # > 30 样本：0.7
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "validation_count": 35,
            "success_count": 25,
            "status": MemoryStatus.TESTING,
            "evidence": {"decision_id": 123},
        }

        result = service.validate(1, success=True)
        assert mock_repo.update.call_args[0][1]["confidence"] == 0.7

    def test_validate_promote_with_evidence(self, service, mock_repo):
        """测试提升状态（有证据）"""
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "validation_count": 10,
            "success_count": 8,
            "status": MemoryStatus.TESTING,
            "evidence": {"decision_id": 123},
        }
        mock_repo.update.return_value = {"id": 1, "status": MemoryStatus.ACTIVE}

        result = service.validate(1, success=True, promote=True)

        update_args = mock_repo.update.call_args[0][1]
        assert update_args["status"] == MemoryStatus.ACTIVE

    def test_validate_promote_without_evidence_fails(self, service, mock_repo):
        """测试提升状态（无证据）失败"""
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "validation_count": 10,
            "success_count": 8,
            "status": MemoryStatus.TESTING,
            "evidence": {},
        }

        with pytest.raises(ValueError, match="Cannot promote to active without evidence"):
            service.validate(1, success=True, promote=True)

    def test_supersede(self, service, mock_repo):
        """测试记忆替代"""
        mock_repo.get_by_id.side_effect = [
            {"id": 1, "title": "旧记忆"},
            {"id": 2, "title": "新记忆"},
        ]
        mock_repo.update.return_value = {}

        result = service.supersede(old_id=1, new_id=2)

        assert result["old_id"] == 1
        assert result["new_id"] == 2
        assert mock_repo.update.call_count == 2

    def test_export_all(self, service, mock_repo):
        """测试全量导出"""
        mock_repo.get_all.return_value = [
            {"id": 1, "title": "记忆1"},
            {"id": 2, "title": "记忆2"},
        ]

        results = service.export_all()

        assert len(results) == 2
        mock_repo.get_all.assert_called_once()

    def test_import_entries(self, service, mock_repo):
        """测试批量导入"""
        entries = [
            {
                "kind": "experience",
                "title": "记忆1",
                "content": "内容1",
                "evidence": {"decision_id": 123},
                "provenance": {"session_kind": "agent"},
                "source": "distiller",
            },
            {
                "kind": "experience",
                "title": "记忆2",
                "content": "内容2",
                "evidence": {"decision_id": 456},
                "provenance": {"session_kind": "agent"},
                "source": "distiller",
            },
        ]

        mock_repo.find_duplicate.return_value = None
        mock_repo.create.return_value = {"id": 1}

        result = service.import_entries(entries)

        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert len(result["errors"]) == 0

    def test_import_entries_with_duplicates(self, service, mock_repo):
        """测试导入重复记忆"""
        entries = [
            {
                "kind": "experience",
                "title": "记忆1",
                "content": "内容1",
                "evidence": {"decision_id": 123},
                "provenance": {"session_kind": "agent"},
                "source": "distiller",
            },
        ]

        mock_repo.find_duplicate.return_value = {"id": 1, "title": "记忆1"}

        result = service.import_entries(entries)

        assert result["imported"] == 0
        assert result["skipped"] == 1
