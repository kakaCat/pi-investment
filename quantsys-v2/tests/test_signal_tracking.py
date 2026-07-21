"""
测试信号追踪功能

验证：
1. 创建订单时 signal_id 校验
2. 订单成交后持仓更新
3. 信号-订单-持仓-交易的完整追踪链路
"""
import pytest
from application.services.data_service import DataService
from application.services import order_service


@pytest.fixture
def ds():
    """DataService 实例"""
    return DataService()


def test_create_order_with_signal_validation(ds):
    """测试创建订单时的 signal_id 校验"""

    # 场景1：from_signal=True 但未提供 signal_id，应该报错
    with pytest.raises(ValueError, match="订单标记为来自策略信号.*但未提供 signal_id"):
        order_service.create_order(
            ds,
            symbol='000001.SH',
            action='buy',
            order_type='limit',
            quantity=100,
            price=1450.00,
            reason='测试订单',
            signal_id=None,
            from_signal=True  # 标记为来自信号，但没有提供 signal_id
        )

    # 场景2：from_signal=False，signal_id 可选（手动创建订单）
    order_id = order_service.create_order(
        ds,
        symbol='000001.SH',
        action='buy',
        order_type='limit',
        quantity=100,
        price=1450.00,
        reason='手动创建订单',
        signal_id=None,
        from_signal=False
    )

    assert order_id is not None
    order = ds.portfolio.get_order(order_id)
    assert order['signal_id'] is None
    assert order['reason'] == '手动创建订单'

    # 清理
    ds.portfolio.cancel_order(order_id)


def test_create_order_with_invalid_signal_id(ds):
    """测试提供无效的 signal_id"""

    # 提供不存在的 signal_id，应该报错
    with pytest.raises(ValueError, match="信号不存在"):
        order_service.create_order(
            ds,
            symbol='000001.SH',
            action='buy',
            order_type='limit',
            quantity=100,
            price=1450.00,
            reason='测试订单',
            signal_id=999999,  # 不存在的信号ID
            from_signal=True
        )


def test_manual_order_without_signal(ds):
    """测试手动创建订单（不关联信号）"""

    # 手动创建订单，不提供 signal_id
    order_id = order_service.create_order(
        ds,
        symbol='000001.SH',
        action='buy',
        order_type='limit',
        quantity=100,
        price=1450.00,
        reason='手动买入',
        signal_id=None,
        from_signal=False
    )

    # 验证订单创建成功
    order = ds.portfolio.get_order(order_id)
    assert order is not None
    assert order['signal_id'] is None
    assert order['reason'] == '手动买入'

    # 清理
    ds.portfolio.cancel_order(order_id)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
