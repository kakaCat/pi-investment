"""
MarketStyleRepository 测试
"""
import pytest
from datetime import date, timedelta
from adapters.outbound.repositories import MarketStyleRepository


@pytest.fixture(autouse=True)
def clean_market_style_table(db_connection):
    """每个测试前清空 market_style_state 表"""
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM quant.market_style_state")
    db_connection.commit()
    cursor.close()
    yield


def test_save_and_get_latest_style(db_connection):
    """测试保存和获取最新市场风格"""
    repo = MarketStyleORMRepository(db_connection)

    style_data = {
        'trade_date': date(2026, 5, 29),
        'style': 'momentum',
        'confidence': 0.68,
        'metrics': {
            'rsi_avg': 58.3,
            'macd_golden_ratio': 0.65,
            'atr_percentile': 72,
            'volume_growth': 1.15
        }
    }

    repo.save(style_data)
    result = repo.get_latest()

    assert result is not None
    assert result['style'] == 'momentum'
    assert result['confidence'] == 0.68
    assert result['metrics']['rsi_avg'] == 58.3


def test_get_by_date(db_connection):
    """测试按日期查询"""
    repo = MarketStyleORMRepository(db_connection)

    style_data = {
        'trade_date': date(2026, 5, 28),
        'style': 'oscillation',
        'confidence': 0.55,
        'metrics': {}
    }

    repo.save(style_data)
    result = repo.get_by_date(date(2026, 5, 28))

    assert result is not None
    assert result['style'] == 'oscillation'
    assert result['confidence'] == 0.55


def test_get_recent(db_connection):
    """测试获取最近N天的市场风格"""
    repo = MarketStyleORMRepository(db_connection)

    # 插入3天的数据
    for i in range(3):
        style_data = {
            'trade_date': date(2026, 5, 27) + timedelta(days=i),
            'style': f'style_{i}',
            'confidence': 0.5 + i * 0.1,
            'metrics': {'day': i}
        }
        repo.save(style_data)

    results = repo.get_recent(days=2)

    assert len(results) == 2
    # 应该按日期降序排列
    assert results[0]['trade_date'] == date(2026, 5, 29)
    assert results[1]['trade_date'] == date(2026, 5, 28)


def test_save_upsert_behavior(db_connection):
    """测试 UPSERT 行为（同一日期更新）"""
    repo = MarketStyleORMRepository(db_connection)

    # 第一次插入
    style_data = {
        'trade_date': date(2026, 5, 30),
        'style': 'momentum',
        'confidence': 0.6,
        'metrics': {'version': 1}
    }
    repo.save(style_data)

    # 同一日期再次插入（应该更新）
    style_data_updated = {
        'trade_date': date(2026, 5, 30),
        'style': 'oscillation',
        'confidence': 0.7,
        'metrics': {'version': 2}
    }
    repo.save(style_data_updated)

    result = repo.get_by_date(date(2026, 5, 30))

    assert result is not None
    assert result['style'] == 'oscillation'
    assert result['confidence'] == 0.7
    assert result['metrics']['version'] == 2


def test_get_by_date_not_found(db_connection):
    """测试查询不存在的日期"""
    repo = MarketStyleORMRepository(db_connection)

    result = repo.get_by_date(date(2020, 1, 1))

    assert result is None


def test_get_latest_empty_table(db_connection):
    """测试空表时获取最新记录"""
    repo = MarketStyleORMRepository(db_connection)

    result = repo.get_latest()

    assert result is None


def test_metrics_json_deserialization(db_connection):
    """测试 metrics 字段正确反序列化为 dict，而非 str"""
    repo = MarketStyleORMRepository(db_connection)

    # 保存复杂的 metrics 对象
    style_data = {
        'trade_date': date(2026, 5, 31),
        'style': 'momentum',
        'confidence': 0.75,
        'metrics': {
            'rsi_avg': 58.3,
            'macd_golden_ratio': 0.65,
            'atr_percentile': 72,
            'volume_growth': 1.15,
            'nested': {
                'level1': {
                    'level2': 'deep_value'
                }
            }
        }
    }

    repo.save(style_data)

    # 测试 get_latest
    result = repo.get_latest()
    assert result is not None
    assert isinstance(result['metrics'], dict), "metrics should be dict, not str"
    assert result['metrics']['rsi_avg'] == 58.3
    assert result['metrics']['nested']['level1']['level2'] == 'deep_value'

    # 测试 get_by_date
    result = repo.get_by_date(date(2026, 5, 31))
    assert result is not None
    assert isinstance(result['metrics'], dict), "metrics should be dict, not str"
    assert result['metrics']['macd_golden_ratio'] == 0.65

    # 测试 get_recent
    results = repo.get_recent(days=1)
    assert len(results) == 1
    assert isinstance(results[0]['metrics'], dict), "metrics should be dict, not str"
    assert results[0]['metrics']['atr_percentile'] == 72

