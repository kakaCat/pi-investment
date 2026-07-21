"""
测试 GET /api/strategies/list 端点（内置策略）

RED 阶段：编写失败的测试
"""
import pytest
from adapters.inbound.api.server import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_strategies_list_returns_all_strategies(client):
    """测试返回所有 18 种策略"""
    response = client.get('/api/strategies/list?source=builtin')

    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert 'strategies' in data['data']

    strategies = data['data']['strategies']
    assert len(strategies) >= 18  # 至少 18 种策略

    # 验证必需字段（camelCase 格式）
    for strategy in strategies:
        assert 'strategyType' in strategy
        assert 'className' in strategy
        assert 'description' in strategy
        assert 'category' in strategy
        assert 'defaultParams' in strategy


def test_strategies_list_includes_expected_strategies(client):
    """测试包含预期的策略类型"""
    response = client.get('/api/strategies/list?source=builtin')

    strategies = response.json['data']['strategies']
    strategy_types = [s['strategyType'] for s in strategies]

    # 验证关键策略存在（使用实际的策略类型名称）
    expected_strategies = [
        'ma_cross',
        'rsi_reversal',
        'bollinger_breakout',
        'turtle',
        'donchian_channel',
        'momentum',
        'breakout',
        'mean_reversion',
        'volatility_breakout',
        'multi_factor',
        'ensemble_vote',
    ]

    for expected in expected_strategies:
        assert expected in strategy_types, f"Missing strategy: {expected}"


def test_strategies_list_categorizes_correctly(client):
    """测试策略分类正确"""
    response = client.get('/api/strategies/list?source=builtin')

    strategies = response.json['data']['strategies']

    # 验证分类存在
    categories = set(s['category'] for s in strategies)
    expected_categories = {
        'trend_following',
        'mean_reversion',
        'volatility',
        'multi_factor',
    }

    assert expected_categories.issubset(categories)


def test_strategies_list_includes_metadata(client):
    """测试包含策略元数据"""
    response = client.get('/api/strategies/list?source=builtin')

    strategies = response.json['data']['strategies']

    # 找一个具体策略验证元数据
    ma_cross = next((s for s in strategies if s['strategyType'] == 'ma_cross'), None)
    assert ma_cross is not None

    # 验证元数据完整性
    assert ma_cross['className'] == 'MACrossStrategy'
    assert 'description' in ma_cross
    assert isinstance(ma_cross['defaultParams'], dict)
    assert ma_cross['category'] in ['trend_following', 'other']


def test_strategies_list_filter_by_category(client):
    """测试按分类过滤"""
    response = client.get('/api/strategies/list?source=builtin&category=trend_following')

    assert response.status_code == 200
    strategies = response.json['data']['strategies']

    # 所有返回的策略都应该是趋势跟踪类
    for strategy in strategies:
        assert strategy['category'] == 'trend_following'


def test_strategies_list_handles_invalid_category(client):
    """测试处理无效分类"""
    response = client.get('/api/strategies/list?source=builtin&category=invalid_category')

    assert response.status_code == 200
    strategies = response.json['data']['strategies']

    # 无效分类应该返回空列表
    assert len(strategies) == 0


def test_strategies_list_user_mode_still_works(client):
    """测试用户模式仍然正常工作"""
    response = client.get('/api/strategies/list')  # 默认 source=user

    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    # 用户模式返回 items，不是 strategies
    assert 'items' in data['data']
