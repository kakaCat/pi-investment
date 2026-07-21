"""
测试统一统计 API

RED 阶段：编写失败的测试
"""
import pytest
from datetime import date, timedelta
from flask import Flask
from adapters.inbound.api.server import create_app
from application.services.signal_test_log import SignalTestLog
from adapters.outbound.repositories import StrategyPerformanceRepository


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def signal_log():
    """创建 SignalTestLog 实例"""
    return SignalTestLog()


@pytest.fixture
def perf_repo():
    """创建 StrategyPerformanceRepository 实例"""
    return StrategyPerformanceORMRepository()


@pytest.fixture
def test_data(signal_log, perf_repo):
    """准备测试数据"""
    # 创建纸面测试数据
    signal_log.record_signal({
        'symbol': '600000.SH',
        'name': '浦发银行',
        'strategy_name': 'ma_cross',
        'signal_date': date.today() - timedelta(days=10),
        'action': 'buy',
        'confidence': 0.85,
        'signal_price': 10.0,
        'entry_price': 10.2,
        'stop_loss': 9.0,
        'reason': '纸面测试信号'
    })

    # 更新为已验证状态
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        UPDATE {signal_log.TABLE_NAME}
        SET status = 'verified',
            current_price = 11.0,
            pnl_pct = 7.84,
            verify_date = CURRENT_DATE
        WHERE symbol = '600000.SH'
        """
    )
    conn.commit()
    cursor.close()
    conn.close()

    # 创建实盘数据
    perf_repo.create(
        strategy_name='ma_cross',
        symbol='600000.SH',
        signal_date=date.today() - timedelta(days=5),
        entry_price=10.5,
        exit_price=11.2,
        pnl_pct=6.67,
        holding_days=3,
        source='live'
    )

    yield

    # 清理测试数据
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quant.signal_test_log WHERE symbol = '600000.SH'")
    cursor.execute("DELETE FROM quant.strategy_performance WHERE symbol = '600000.SH'")
    conn.commit()
    cursor.close()
    conn.close()


def test_get_performance_returns_combined_stats(client, test_data):
    """测试返回纸面+实盘的综合统计"""
    response = client.get('/api/signal-test/performance?strategy=ma_cross&symbol=600000.SH')

    assert response.status_code == 200
    data = response.json

    assert data['success'] is True
    assert 'data' in data

    result = data['data']
    assert result['strategy_name'] == 'ma_cross'
    assert result['symbol'] == '600000.SH'

    # 应该包含纸面和实盘两部分统计
    assert 'paper' in result
    assert 'live' in result
    assert 'combined' in result


def test_get_performance_paper_stats(client, test_data):
    """测试纸面测试统计"""
    response = client.get('/api/signal-test/performance?strategy=ma_cross&symbol=600000.SH')

    paper = response.json['data']['paper']

    assert paper['total_trades'] >= 1
    assert paper['verified_trades'] >= 1
    assert 'avg_pnl_pct' in paper
    assert 'win_rate' in paper


def test_get_performance_live_stats(client, test_data):
    """测试实盘统计"""
    response = client.get('/api/signal-test/performance?strategy=ma_cross&symbol=600000.SH')

    live = response.json['data']['live']

    assert live['total_trades'] >= 1
    assert 'avg_pnl_pct' in live
    assert 'win_rate' in live
    assert 'avg_holding_days' in live


def test_get_performance_combined_stats(client, test_data):
    """测试综合统计"""
    response = client.get('/api/signal-test/performance?strategy=ma_cross&symbol=600000.SH')

    combined = response.json['data']['combined']

    # 综合统计应该合并纸面和实盘数据
    assert combined['total_trades'] >= 2  # 至少有纸面1条+实盘1条
    assert 'avg_pnl_pct' in combined
    assert 'win_rate' in combined


def test_get_performance_filter_by_strategy_only(client, test_data):
    """测试只按策略过滤"""
    response = client.get('/api/signal-test/performance?strategy=ma_cross')

    assert response.status_code == 200
    data = response.json['data']

    assert data['strategy_name'] == 'ma_cross'
    assert data['symbol'] is None  # 没有指定 symbol


def test_get_performance_filter_by_date_range(client, test_data):
    """测试按日期范围过滤"""
    start_date = (date.today() - timedelta(days=15)).isoformat()
    end_date = date.today().isoformat()

    response = client.get(
        f'/api/signal-test/performance?strategy=ma_cross&start_date={start_date}&end_date={end_date}'
    )

    assert response.status_code == 200
    data = response.json['data']

    assert 'date_range' in data
    assert data['date_range']['start_date'] == start_date
    assert data['date_range']['end_date'] == end_date


def test_get_performance_missing_strategy(client):
    """测试缺少必需参数"""
    response = client.get('/api/signal-test/performance')

    assert response.status_code == 400
    assert response.json['success'] is False
    assert 'strategy' in response.json['error'].lower()


def test_get_performance_no_data(client):
    """测试没有数据的情况"""
    response = client.get('/api/signal-test/performance?strategy=nonexistent_strategy')

    assert response.status_code == 200
    data = response.json['data']

    # 应该返回空统计
    assert data['paper']['total_trades'] == 0
    assert data['live']['total_trades'] == 0
    assert data['combined']['total_trades'] == 0
