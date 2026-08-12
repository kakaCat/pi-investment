"""Tests for MemoryDistiller"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from domain.memory.distiller import MemoryDistiller
from domain.memory.models import MemoryKind, MemoryStatus


class TestMemoryDistiller:
    """MemoryDistiller 单元测试"""

    def test_collect_inputs_excludes_recall_source(self):
        """(a) collect_inputs 排除 source=recall 且 last_recalled_at 非空的条目"""
        distiller = MemoryDistiller()

        # Mock MemoryRepository.list_filtered
        with patch.object(distiller._memory_repo, 'list_filtered') as mock_list:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=7)

            # 准备测试数据
            mock_list.return_value = [
                {
                    'id': 1,
                    'title': 'normal episode',
                    'content': 'content1',
                    'created_at': now.isoformat(),
                    'last_recalled_at': None,
                    'source': 'agent',
                },
                {
                    'id': 2,
                    'title': 'recalled episode',
                    'content': 'content2',
                    'created_at': now.isoformat(),
                    'last_recalled_at': (now - timedelta(days=1)).isoformat(),
                    'source': 'recall',
                },
                {
                    'id': 3,
                    'title': 'recalled but not recall source',
                    'content': 'content3',
                    'created_at': now.isoformat(),
                    'last_recalled_at': (now - timedelta(days=1)).isoformat(),
                    'source': 'agent',
                },
            ]

            # Mock agent_decisions query
            with patch('domain.memory.distiller.get_session') as mock_session:
                mock_sess = MagicMock()
                mock_session.return_value = mock_sess
                mock_sess.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

                result = distiller.collect_inputs(days=7)

            # 验证：只有 id=1 和 id=3 被保留（id=2 被排除）
            assert len(result['episodes']) == 2
            episode_ids = [ep['id'] for ep in result['episodes']]
            assert 1 in episode_ids
            assert 2 not in episode_ids  # 被排除
            assert 3 in episode_ids

    def test_save_candidates_skips_empty_evidence(self):
        """(b) save_candidates 跳过 evidence_ids 为空的候选"""
        distiller = MemoryDistiller()

        candidates = [
            {'title': 'rule1', 'content': 'content1', 'evidence_ids': [1, 2]},
            {'title': 'rule2', 'content': 'content2', 'evidence_ids': []},  # 应该被跳过
            {'title': 'rule3', 'content': 'content3'},  # 缺少 evidence_ids，应该被跳过
        ]

        # Mock MemoryService.create
        with patch('domain.memory.distiller.MemoryService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            with patch('domain.memory.distiller.get_session') as mock_session:
                mock_sess = MagicMock()
                mock_session.return_value = mock_sess

                result = distiller.save_candidates(candidates, session=mock_sess)

        # 验证：只保存了 1 条（rule1），跳过了 2 条
        assert result['saved'] == 1
        assert result['skipped'] == 2
        assert mock_service.create.call_count == 1

    def test_save_candidates_writes_testing_status(self):
        """(c) save_candidates 正常写入 testing 状态的条目"""
        distiller = MemoryDistiller()

        candidates = [
            {'title': 'good rule', 'content': 'good content', 'evidence_ids': [10, 20]},
        ]

        # Mock MemoryService.create
        with patch('domain.memory.distiller.MemoryService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            with patch('domain.memory.distiller.get_session') as mock_session:
                mock_sess = MagicMock()
                mock_session.return_value = mock_sess

                result = distiller.save_candidates(candidates, session=mock_sess)

        # 验证：保存成功
        assert result['saved'] == 1
        assert result['skipped'] == 0

        # 验证调用参数
        assert mock_service.create.call_count == 1
        call_args = mock_service.create.call_args[0][0]
        assert call_args.kind == MemoryKind.RULE
        assert call_args.status == MemoryStatus.TESTING
        assert call_args.source == 'distiller'
        assert call_args.evidence == {"refs": [10, 20]}
        assert call_args.provenance == {
            "session_kind": "distiller",
            "channel": "weekly_memory_distill"
        }
