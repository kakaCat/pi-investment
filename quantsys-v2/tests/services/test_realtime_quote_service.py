"""
RealtimeQuoteService 单元测试
"""
import pytest
from unittest.mock import Mock, patch
from application.services.realtime_quote_service import RealtimeQuoteService
from application.services.quote_providers import QuoteData


class TestRealtimeQuoteService:
    """RealtimeQuoteService 测试套件"""

    def test_first_provider_success(self):
        """测试第一个 provider 成功返回数据"""
        # Arrange
        mock_provider1 = Mock()
        mock_provider1.name = "provider1"
        mock_provider1.get_quote.return_value = QuoteData(
            symbol="000001.SH",
            name="浦发银行",
            price=1800.0,
            source="provider1",
            timestamp="2026-05-29T14:30:00"
        )

        mock_provider2 = Mock()
        mock_provider2.name = "provider2"

        service = RealtimeQuoteService(providers=[mock_provider1, mock_provider2])

        # Act
        result = service.get_realtime_quote("000001.SH")

        # Assert
        assert result is not None
        assert result.symbol == "000001.SH"
        assert result.price == 1800.0
        assert result.source == "provider1"

        # 第一个成功，不应该调用第二个
        mock_provider1.get_quote.assert_called_once_with("000001.SH")
        mock_provider2.get_quote.assert_not_called()

        # 统计验证
        stats = service.get_stats()
        assert stats['total_requests'] == 1
        assert stats['success_count'] == 1
        assert stats['failure_count'] == 0
        assert stats['provider_stats']['provider1']['success'] == 1

    def test_fallback_to_second_provider(self):
        """测试第一个 provider 失败，fallback 到第二个"""
        # Arrange
        mock_provider1 = Mock()
        mock_provider1.name = "provider1"
        mock_provider1.get_quote.side_effect = Exception("Network error")

        mock_provider2 = Mock()
        mock_provider2.name = "provider2"
        mock_provider2.get_quote.return_value = QuoteData(
            symbol="000001.SH",
            name="浦发银行",
            price=1800.0,
            source="provider2",
            timestamp="2026-05-29T14:30:00"
        )

        service = RealtimeQuoteService(providers=[mock_provider1, mock_provider2])

        # Act
        result = service.get_realtime_quote("000001.SH")

        # Assert
        assert result is not None
        assert result.source == "provider2"

        # 两个都应该被调用
        mock_provider1.get_quote.assert_called_once_with("000001.SH")
        mock_provider2.get_quote.assert_called_once_with("000001.SH")

        # 统计验证
        stats = service.get_stats()
        assert stats['total_requests'] == 1
        assert stats['success_count'] == 1
        assert stats['failure_count'] == 0
        assert stats['provider_stats']['provider1']['failure'] == 1
        assert stats['provider_stats']['provider2']['success'] == 1

    def test_all_providers_fail(self):
        """测试所有 provider 都失败，返回 None"""
        # Arrange
        mock_provider1 = Mock()
        mock_provider1.name = "provider1"
        mock_provider1.get_quote.side_effect = Exception("Error 1")

        mock_provider2 = Mock()
        mock_provider2.name = "provider2"
        mock_provider2.get_quote.side_effect = Exception("Error 2")

        service = RealtimeQuoteService(providers=[mock_provider1, mock_provider2])

        # Act
        result = service.get_realtime_quote("000001.SH")

        # Assert
        assert result is None

        # 两个都应该被调用
        mock_provider1.get_quote.assert_called_once_with("000001.SH")
        mock_provider2.get_quote.assert_called_once_with("000001.SH")

        # 统计验证
        stats = service.get_stats()
        assert stats['total_requests'] == 1
        assert stats['success_count'] == 0
        assert stats['failure_count'] == 1
        assert stats['provider_stats']['provider1']['failure'] == 1
        assert stats['provider_stats']['provider2']['failure'] == 1

    def test_provider_returns_none(self):
        """测试 provider 返回 None（而非抛异常），尝试下一个"""
        # Arrange
        mock_provider1 = Mock()
        mock_provider1.name = "provider1"
        mock_provider1.get_quote.return_value = None

        mock_provider2 = Mock()
        mock_provider2.name = "provider2"
        mock_provider2.get_quote.return_value = QuoteData(
            symbol="000001.SH",
            name="浦发银行",
            price=1800.0,
            source="provider2",
            timestamp="2026-05-29T14:30:00"
        )

        service = RealtimeQuoteService(providers=[mock_provider1, mock_provider2])

        # Act
        result = service.get_realtime_quote("000001.SH")

        # Assert
        assert result is not None
        assert result.source == "provider2"

        # 两个都应该被调用
        mock_provider1.get_quote.assert_called_once_with("000001.SH")
        mock_provider2.get_quote.assert_called_once_with("000001.SH")

        # 统计验证
        stats = service.get_stats()
        assert stats['provider_stats']['provider1']['failure'] == 1
        assert stats['provider_stats']['provider2']['success'] == 1

    def test_stats_tracking(self):
        """测试统计信息跟踪"""
        # Arrange
        mock_provider = Mock()
        mock_provider.name = "provider1"
        mock_provider.get_quote.side_effect = [
            QuoteData(symbol="000001.SH", name="浦发银行", price=1800.0, source="provider1", timestamp="2026-05-29T14:30:00"),
            None,
            QuoteData(symbol="000001.SZ", name="平安", price=50.0, source="provider1", timestamp="2026-05-29T14:31:00"),
        ]

        service = RealtimeQuoteService(providers=[mock_provider])

        # Act
        service.get_realtime_quote("000001.SH")  # 成功
        service.get_realtime_quote("999999.SH")  # 失败
        service.get_realtime_quote("000001.SZ")  # 成功

        # Assert
        stats = service.get_stats()
        assert stats['total_requests'] == 3
        assert stats['success_count'] == 2
        assert stats['failure_count'] == 1
        assert stats['provider_stats']['provider1']['success'] == 2
        assert stats['provider_stats']['provider1']['failure'] == 1
