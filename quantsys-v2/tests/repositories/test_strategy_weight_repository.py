"""
StrategyWeightORMRepository 测试
"""
import pytest
from adapters.outbound.repositories import StrategyWeightORMRepository


@pytest.fixture(autouse=True)
def setup_test_data(db_connection):
    """每个测试前准备测试数据"""
    cursor = db_connection.cursor()

    # 清空表
    cursor.execute("DELETE FROM quant.strategy_weight_config")

    # 插入测试数据
    cursor.execute("""
        INSERT INTO quant.strategy_weight_config (strategy_type, market_style, static_weight, is_active)
        VALUES
            ('trend_following', 'momentum', 0.30, TRUE),
            ('trend_following', 'oscillation', -0.40, TRUE),
            ('mean_reversion', 'oscillation', 0.30, TRUE),
            ('mean_reversion', 'momentum', -0.20, TRUE),
            ('multi_factor', 'value', 0.20, TRUE),
            ('multi_factor', 'low_volatility', 0.10, FALSE)
    """)

    db_connection.commit()
    cursor.close()
    yield


def test_get_static_weight(db_connection):
    """测试查询静态权重"""
    repo = StrategyWeightORMRepository(db_connection)

    weight = repo.get_static_weight('trend_following', 'momentum')

    assert weight == 0.30


def test_get_static_weight_not_found(db_connection):
    """测试查询不存在的权重配置"""
    repo = StrategyWeightORMRepository(db_connection)

    weight = repo.get_static_weight('unknown_type', 'momentum')

    assert weight == 0.0  # 默认值


def test_get_static_weight_inactive(db_connection):
    """测试查询未激活的权重配置（应返回 0.0）"""
    repo = StrategyWeightORMRepository(db_connection)

    weight = repo.get_static_weight('multi_factor', 'low_volatility')

    assert weight == 0.0  # is_active=FALSE 应返回默认值


def test_get_all_for_style(db_connection):
    """测试查询某风格下所有策略权重"""
    repo = StrategyWeightORMRepository(db_connection)

    weights = repo.get_all_for_style('momentum')

    assert len(weights) == 2  # trend_following +0.30, mean_reversion -0.20
    assert weights['trend_following'] == 0.30
    assert weights['mean_reversion'] == -0.20


def test_get_all_for_style_empty(db_connection):
    """测试查询不存在的风格"""
    repo = StrategyWeightORMRepository(db_connection)

    weights = repo.get_all_for_style('unknown_style')

    assert weights == {}


def test_get_all_for_strategy(db_connection):
    """测试查询某策略类型下所有风格权重"""
    repo = StrategyWeightORMRepository(db_connection)

    weights = repo.get_all_for_strategy('trend_following')

    assert len(weights) == 2  # momentum +0.30, oscillation -0.40
    assert weights['momentum'] == 0.30
    assert weights['oscillation'] == -0.40


def test_get_all_for_strategy_empty(db_connection):
    """测试查询不存在的策略类型"""
    repo = StrategyWeightORMRepository(db_connection)

    weights = repo.get_all_for_strategy('unknown_strategy')

    assert weights == {}


def test_update_weight(db_connection):
    """测试更新权重"""
    repo = StrategyWeightORMRepository(db_connection)

    # 更新现有权重
    repo.update_weight('trend_following', 'momentum', 0.50)

    # 验证更新成功
    weight = repo.get_static_weight('trend_following', 'momentum')
    assert weight == 0.50


def test_update_weight_insert_new(db_connection):
    """测试更新不存在的权重（应插入新记录）"""
    repo = StrategyWeightORMRepository(db_connection)

    # 插入新权重
    repo.update_weight('new_strategy', 'new_style', 0.25)

    # 验证插入成功
    weight = repo.get_static_weight('new_strategy', 'new_style')
    assert weight == 0.25


def test_update_weight_validation(db_connection):
    """测试权重范围验证"""
    repo = StrategyWeightORMRepository(db_connection)

    # 测试超出范围的权重（应抛出异常）
    with pytest.raises(ValueError, match="static_weight must be between -1.0 and 1.0"):
        repo.update_weight('trend_following', 'momentum', 1.5)

    with pytest.raises(ValueError, match="static_weight must be between -1.0 and 1.0"):
        repo.update_weight('trend_following', 'momentum', -1.5)


def test_error_handling(db_connection):
    """测试数据库错误处理"""
    repo = StrategyWeightORMRepository(db_connection)

    # 关闭连接模拟数据库错误
    db_connection.close()

    # 应该抛出异常
    with pytest.raises(Exception):
        repo.get_static_weight('trend_following', 'momentum')
