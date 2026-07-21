"""
Unit tests for Broker Abstraction Layer
"""

import pytest
from datetime import datetime

from brokers import (
    BrokerRegistry,
    BaseBroker,
    OrderSide,
    OrderType,
    ProductType,
    UnifiedOrder,
    BrokerProfile,
    ApiResponse,
)
from domain.brokers.adapters.akshare_broker import AkshareBroker


class TestBrokerRegistry:
    """测试 BrokerRegistry"""

    def setup_method(self):
        """每个测试前重置注册表"""
        BrokerRegistry.reset()

    def test_singleton(self):
        """测试单例模式"""
        registry1 = BrokerRegistry.instance()
        registry2 = BrokerRegistry.instance()
        assert registry1 is registry2

    def test_get_broker(self):
        """测试获取券商"""
        registry = BrokerRegistry.instance()
        broker = registry.get('akshare')
        assert broker is not None
        assert broker.get_id() == 'akshare'
        assert broker.get_name() == 'AkShare'

    def test_list_brokers(self):
        """测试列举券商"""
        registry = BrokerRegistry.instance()
        brokers = registry.list_brokers()
        assert 'akshare' in brokers
        assert len(brokers) >= 1

    def test_has_broker(self):
        """测试检查券商是否存在"""
        registry = BrokerRegistry.instance()
        assert registry.has('akshare') is True
        assert registry.has('nonexistent') is False

    def test_list_broker_profiles(self):
        """测试列举券商配置"""
        registry = BrokerRegistry.instance()
        profiles = registry.list_broker_profiles()
        assert len(profiles) >= 1
        assert any(p['id'] == 'akshare' for p in profiles)

    def test_get_data_brokers(self):
        """测试获取数据源券商"""
        registry = BrokerRegistry.instance()
        data_brokers = registry.get_data_brokers()
        assert len(data_brokers) >= 1
        assert any(b.get_id() == 'akshare' for b in data_brokers)

    def test_get_trading_brokers(self):
        """测试获取交易券商"""
        registry = BrokerRegistry.instance()
        trading_brokers = registry.get_trading_brokers()
        # AkShare 不支持交易，所以应该为空或不包含 akshare
        assert not any(b.get_id() == 'akshare' for b in trading_brokers)


class TestAkshareBroker:
    """测试 AkShare 适配器"""

    @pytest.fixture
    def broker(self):
        """创建 AkShare 券商实例"""
        return AkshareBroker()

    def test_get_id(self, broker):
        """测试获取 ID"""
        assert broker.get_id() == 'akshare'

    def test_get_name(self, broker):
        """测试获取名称"""
        assert broker.get_name() == 'AkShare'

    def test_get_profile(self, broker):
        """测试获取配置"""
        profile = broker.get_profile()
        assert isinstance(profile, BrokerProfile)
        assert profile.id == 'akshare'
        assert profile.region == 'CN'
        assert profile.currency == 'CNY'
        assert len(profile.credential_fields) == 0  # 无需凭证
        assert 'SSE' in profile.supported_exchanges

    def test_is_trading_broker(self, broker):
        """测试是否为交易券商"""
        assert broker.is_trading_broker() is False

    @pytest.mark.skip(reason="需要网络连接和 akshare 库")
    def test_get_quotes(self, broker):
        """测试获取实时行情"""
        response = broker.get_quotes(['000001', '000001'])
        assert response.success is True
        assert len(response.data) == 2
        assert response.data[0].symbol in ['000001', '000001.SH']
        assert response.data[0].last_price > 0

    @pytest.mark.skip(reason="需要网络连接和 akshare 库")
    def test_get_history(self, broker):
        """测试获取历史数据"""
        response = broker.get_history(
            symbol='000001',
            start_date='2024-01-01',
            end_date='2024-01-31',
            frequency='daily'
        )
        assert response.success is True
        assert len(response.data) > 0
        assert response.data[0].symbol == '000001'
        assert response.data[0].open > 0

    @pytest.mark.skip(reason="需要网络连接和 akshare 库")
    def test_search_symbols(self, broker):
        """测试搜索股票"""
        response = broker.search_symbols('平安')
        assert response.success is True
        assert len(response.data) > 0
        assert any('平安' in item['name'] for item in response.data)

    def test_trading_not_supported(self, broker):
        """测试交易功能不支持"""
        from domain.brokers.trading_types import BrokerCredentials

        creds = BrokerCredentials(broker_id='akshare')
        order = UnifiedOrder(
            symbol='000001',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )

        # 下单应该返回不支持
        response = broker.place_order(creds, order)
        assert response.success is False
        assert 'not supported' in response.error.lower()


class TestTradingTypes:
    """测试交易类型"""

    def test_order_side_enum(self):
        """测试订单方向枚举"""
        assert OrderSide.BUY.value == 'buy'
        assert OrderSide.SELL.value == 'sell'

    def test_order_type_enum(self):
        """测试订单类型枚举"""
        assert OrderType.MARKET.value == 'market'
        assert OrderType.LIMIT.value == 'limit'

    def test_unified_order(self):
        """测试统一订单结构"""
        order = UnifiedOrder(
            symbol='000001',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=1800.0
        )
        assert order.symbol == '000001'
        assert order.side == OrderSide.BUY
        assert order.price == 1800.0

        # 测试转换为字典
        order_dict = order.to_dict()
        assert order_dict['symbol'] == '000001'
        assert order_dict['side'] == 'buy'
        assert order_dict['price'] == 1800.0

    def test_api_response(self):
        """测试 API 响应"""
        # 成功响应
        success_resp = ApiResponse.ok([1, 2, 3])
        assert success_resp.success is True
        assert success_resp.data == [1, 2, 3]
        assert success_resp.error is None

        # 失败响应
        fail_resp = ApiResponse.fail("Something went wrong")
        assert fail_resp.success is False
        assert fail_resp.data is None
        assert fail_resp.error == "Something went wrong"


class TestBrokerProfile:
    """测试券商配置"""

    def test_broker_profile_creation(self):
        """测试创建券商配置"""
        profile = BrokerProfile(
            id='test',
            display_name='Test Broker',
            region='CN',
            currency='CNY',
            supported_exchanges=['SSE', 'SZSE'],
        )
        assert profile.id == 'test'
        assert profile.display_name == 'Test Broker'
        assert 'SSE' in profile.supported_exchanges


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
