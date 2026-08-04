"""
Tests for RiskConfigORMRepository

Following TDD approach - tests written before implementation
"""
import pytest
from adapters.outbound.repositories import RiskConfigORMRepository


def test_get_config():
    """测试查询风控配置"""
    repo = RiskConfigORMRepository()

    config = repo.get_config('default')

    assert config is not None
    assert config['config_name'] == 'default'
    # 不断言具体数值：default 行是 quant_test 共享可变数据，
    # test_update_config 会改它，断言值会产生顺序依赖
    assert isinstance(config['max_single_order_percent'], (int, float))
    assert isinstance(config['max_position_percent'], (int, float))


def test_update_config():
    """测试更新风控配置"""
    repo = RiskConfigORMRepository()

    # 更新配置
    update_data = {
        'max_single_order_percent': 25.00,
        'max_position_percent': 35.00
    }

    success = repo.update_config('default', update_data)
    assert success is True

    # 验证更新
    config = repo.get_config('default')
    assert config['max_single_order_percent'] == 25.00
    assert config['max_position_percent'] == 35.00

    # 恢复默认值
    repo.update_config('default', {
        'max_single_order_percent': 20.00,
        'max_position_percent': 30.00
    })


def test_get_config_nonexistent():
    """测试查询不存在的配置"""
    repo = RiskConfigORMRepository()

    config = repo.get_config('nonexistent')

    assert config is None


def test_get_config_only_returns_active():
    """测试只返回激活的配置"""
    repo = RiskConfigORMRepository()

    # 不依赖 quant_test 共享行的既有状态：先确保 default 行存在且激活
    row = repo.session.query(repo.model).filter_by(config_name='default').first()
    assert row is not None, "quant_test.risk_config 缺 default 行"
    row.is_active = True
    repo.session.commit()

    # 获取默认配置（应该是激活的）
    config = repo.get_config('default')
    assert config is not None
    assert config['is_active'] is True


def test_update_config_excludes_protected_fields():
    """测试更新配置时排除受保护字段"""
    repo = RiskConfigORMRepository()

    # 尝试更新受保护字段
    update_data = {
        'id': 999,
        'config_name': 'hacked',
        'created_at': '2020-01-01 00:00:00',
        'max_single_order_percent': 25.00
    }

    success = repo.update_config('default', update_data)
    assert success is True

    # 验证受保护字段未被更新
    config = repo.get_config('default')
    assert config['config_name'] == 'default'  # 未被改变
    assert config['max_single_order_percent'] == 25.00  # 正常字段已更新

    # 恢复默认值
    repo.update_config('default', {
        'max_single_order_percent': 20.00
    })


def test_update_config_auto_updates_timestamp():
    """测试更新配置时自动更新时间戳"""
    repo = RiskConfigORMRepository()

    # 获取初始时间戳
    config_before = repo.get_config('default')
    updated_at_before = config_before['updated_at']

    # 更新配置
    import time
    time.sleep(0.1)  # 确保时间戳不同
    repo.update_config('default', {
        'max_single_order_percent': 25.00
    })

    # 验证时间戳已更新
    config_after = repo.get_config('default')
    updated_at_after = config_after['updated_at']
    assert updated_at_after > updated_at_before

    # 恢复默认值
    repo.update_config('default', {
        'max_single_order_percent': 20.00
    })
