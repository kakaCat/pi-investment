"""
RealtimeQuoteService 单元测试
"""
import pytest
from unittest.mock import patch
from application.services.realtime_quote_service import RealtimeQuoteService
from application.services.quote_providers import QuoteData


class FakeDataProviderManager:
    """模拟 DataProviderManager，用于隔离 RealtimeQuoteService 测试"""

    def __init__(self, quote_results=None):
        self.quote_results = quote_results or {}
        self.provider_stats = {}

    def get_quote(self, symbol):
        result = self.quote_results.get(symbol, {'success': False, 'error': 'not configured'})
        if result.get('success'):
            source = result.get('source') or result['data'].source
            self._inc(source, 'success')
        else:
            for source in result.get('attempted_sources', []):
                self._inc(source, 'failure')
        return result

    def get_provider_health(self):
        return self.provider_stats

    def _inc(self, source, key):
        if not source:
            source = 'unknown'
        self.provider_stats.setdefault(source, {'success': 0, 'failure': 0})
        self.provider_stats[source][key] += 1


class TestRealtimeQuoteService:
    """RealtimeQuoteService 测试套件"""

    def _service(self, manager):
        with patch(
            'adapters.outbound.datasources.manager.get_data_provider_manager',
            return_value=manager,
        ):
            return RealtimeQuoteService()

    def test_first_provider_success(self):
        """测试 DataProviderManager 成功返回数据"""
        quote = QuoteData(
            symbol='000001.SH',
            name='浦发银行',
            price=1800.0,
            source='provider1',
            timestamp='2026-05-29T14:30:00',
        )
        manager = FakeDataProviderManager(
            {'000001.SH': {'success': True, 'data': quote, 'source': 'provider1'}}
        )
        service = self._service(manager)

        result = service.get_realtime_quote('000001.SH')

        assert result is not None
        assert result.symbol == '000001.SH'
        assert result.price == 1800.0
        assert result.source == 'provider1'

        stats = service.get_provider_health()
        assert stats['provider1']['success'] == 1
        assert stats['provider1']['failure'] == 0

    def test_fallback_to_second_provider(self):
        """测试 DataProviderManager 内部降级后返回数据"""
        quote = QuoteData(
            symbol='000001.SH',
            name='浦发银行',
            price=1800.0,
            source='provider2',
            timestamp='2026-05-29T14:30:00',
        )
        manager = FakeDataProviderManager(
            {'000001.SH': {'success': True, 'data': quote, 'source': 'provider2'}}
        )
        service = self._service(manager)

        result = service.get_realtime_quote('000001.SH')

        assert result is not None
        assert result.source == 'provider2'

        stats = service.get_provider_health()
        assert stats['provider2']['success'] == 1

    def test_all_providers_fail(self):
        """测试所有 provider 都失败，返回 None"""
        manager = FakeDataProviderManager(
            {
                '000001.SH': {
                    'success': False,
                    'error': 'All providers failed',
                    'attempted_sources': ['provider1', 'provider2'],
                }
            }
        )
        service = self._service(manager)

        result = service.get_realtime_quote('000001.SH')

        assert result is None

        stats = service.get_provider_health()
        assert stats['provider1']['failure'] == 1
        assert stats['provider2']['failure'] == 1

    def test_provider_returns_none(self):
        """测试 DataProviderManager 返回空数据，服务返回 None"""
        manager = FakeDataProviderManager(
            {'000001.SH': {'success': False, 'error': 'empty', 'attempted_sources': ['provider1']}}
        )
        service = self._service(manager)

        result = service.get_realtime_quote('000001.SH')

        assert result is None

        stats = service.get_provider_health()
        assert stats['provider1']['failure'] == 1

    def test_stats_tracking(self):
        """测试统计信息跟踪"""
        quote1 = QuoteData(
            symbol='000001.SH',
            name='浦发银行',
            price=1800.0,
            source='provider1',
            timestamp='2026-05-29T14:30:00',
        )
        quote3 = QuoteData(
            symbol='000001.SZ',
            name='平安',
            price=50.0,
            source='provider1',
            timestamp='2026-05-29T14:31:00',
        )
        manager = FakeDataProviderManager(
            {
                '000001.SH': {'success': True, 'data': quote1, 'source': 'provider1'},
                '999999.SH': {'success': False, 'error': 'empty', 'attempted_sources': ['provider1']},
                '000001.SZ': {'success': True, 'data': quote3, 'source': 'provider1'},
            }
        )
        service = self._service(manager)

        service.get_realtime_quote('000001.SH')
        service.get_realtime_quote('999999.SH')
        service.get_realtime_quote('000001.SZ')

        stats = service.get_provider_health()
        assert stats['provider1']['success'] == 2
        assert stats['provider1']['failure'] == 1
