"""
测试经验自动积累功能

RED 阶段：编写失败的测试
"""
import pytest
from datetime import date, timedelta
import json
from pathlib import Path
from application.services.experience_accumulator import ExperienceAccumulator
from application.services.signal_test_log import SignalTestLog
from adapters.outbound.repositories import StrategyPerformanceRepository


@pytest.fixture
def accumulator():
    """创建 ExperienceAccumulator 实例"""
    return ExperienceAccumulator()


@pytest.fixture
def signal_log():
    """创建 SignalTestLog 实例"""
    return SignalTestLog()


@pytest.fixture
def perf_repo():
    """创建 StrategyPerformanceRepository 实例"""
    return StrategyPerformanceRepository()


@pytest.fixture
def test_data(signal_log, perf_repo):
    """准备测试数据"""
    # 创建多条已验证的信号记录
    for i in range(10):
        signal_log.record_signal({
            'symbol': '000001.SH',
            'name': '浦发银行',
            'strategy_name': 'ma_cross',
            'signal_date': date.today() - timedelta(days=20 - i),
            'action': 'buy',
            'confidence': 0.85,
            'signal_price': 1800.0 + i * 10,
            'entry_price': 1800.0 + i * 10,
            'stop_loss': 1700.0 + i * 10,
            'reason': '均线金叉'
        })

    # 更新为已验证状态（模拟盈利和亏损）
    conn = signal_log._get_conn()
    cursor = conn.cursor()

    # 7条盈利，3条亏损
    cursor.execute(
        f"""
        UPDATE {signal_log.TABLE_NAME}
        SET status = 'verified',
            current_price = signal_price * 1.05,
            pnl_pct = 5.0,
            verify_date = CURRENT_DATE
        WHERE id IN (
            SELECT id FROM {signal_log.TABLE_NAME}
            WHERE strategy_name = 'ma_cross' AND symbol = '000001.SH'
            ORDER BY id
            LIMIT 7
        )
        """
    )

    cursor.execute(
        f"""
        UPDATE {signal_log.TABLE_NAME}
        SET status = 'verified',
            current_price = signal_price * 0.97,
            pnl_pct = -3.0,
            verify_date = CURRENT_DATE
        WHERE strategy_name = 'ma_cross' AND symbol = '000001.SH' AND status = 'pending'
        """
    )

    conn.commit()
    cursor.close()
    conn.close()

    yield

    # 清理测试数据
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quant.signal_test_log WHERE symbol = '000001.SH'")
    conn.commit()
    cursor.close()
    conn.close()


def test_accumulate_creates_experience_entry(accumulator, test_data):
    """测试积累经验时创建经验条目"""
    # 积累经验（样本数 >= 10）
    result = accumulator.accumulate_from_performance(
        strategy_name='ma_cross',
        symbol='000001.SH',
        min_samples=10
    )

    assert result['success'] is True
    assert result['experience_created'] is True
    assert 'experience_id' in result


def test_accumulate_requires_minimum_samples(accumulator, signal_log):
    """测试需要最小样本数"""
    # 只创建 5 条记录
    for i in range(5):
        signal_log.record_signal({
            'symbol': '000001.SZ',
            'name': '平安银行',
            'strategy_name': 'turtle',
            'signal_date': date.today() - timedelta(days=10 - i),
            'action': 'buy',
            'confidence': 0.80,
            'signal_price': 10.0,
            'entry_price': 10.0,
            'stop_loss': 9.0,
            'reason': '测试'
        })

    # 尝试积累经验（样本数不足）
    result = accumulator.accumulate_from_performance(
        strategy_name='turtle',
        symbol='000001.SZ',
        min_samples=10
    )

    assert result['success'] is True
    assert result['experience_created'] is False
    assert 'reason' in result
    assert 'insufficient samples' in result['reason'].lower()

    # 清理
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quant.signal_test_log WHERE symbol = '000001.SZ'")
    conn.commit()
    cursor.close()
    conn.close()


def test_experience_entry_format(accumulator, test_data):
    """测试经验条目格式正确"""
    result = accumulator.accumulate_from_performance(
        strategy_name='ma_cross',
        symbol='000001.SH',
        min_samples=10
    )

    experience = result['experience']

    # 验证必需字段
    assert 'id' in experience
    assert 'scenario' in experience
    assert 'pattern' in experience
    assert 'outcomes' in experience
    assert 'recommendation' in experience
    assert 'reason' in experience

    # 验证 pattern 结构
    assert 'conditions' in experience['pattern']
    assert 'action' in experience['pattern']
    assert isinstance(experience['pattern']['conditions'], list)

    # 验证 outcomes 结构
    outcomes = experience['outcomes']
    assert 'total_cases' in outcomes
    assert 'win_rate' in outcomes
    assert 'avg_return' in outcomes
    assert outcomes['total_cases'] >= 10
    assert 0 <= outcomes['win_rate'] <= 100


def test_recommendation_based_on_performance(accumulator, test_data):
    """测试根据表现生成推荐"""
    result = accumulator.accumulate_from_performance(
        strategy_name='ma_cross',
        symbol='000001.SH',
        min_samples=10
    )

    experience = result['experience']
    outcomes = experience['outcomes']

    # 胜率 70%，平均收益 2.8%，应该是 moderate 或 aggressive
    if outcomes['win_rate'] >= 70 and outcomes['avg_return'] >= 3:
        assert experience['recommendation'] in ['aggressive', 'moderate']
    elif outcomes['win_rate'] >= 60:
        assert experience['recommendation'] in ['moderate', 'cautious']
    else:
        assert experience['recommendation'] in ['cautious', 'avoid']


def test_accumulate_all_strategies(accumulator, test_data):
    """测试批量积累所有策略的经验"""
    result = accumulator.accumulate_all(min_samples=10)

    assert result['success'] is True
    assert 'total_processed' in result
    assert 'experiences_created' in result
    assert result['total_processed'] >= 1


def test_experience_saved_to_file(accumulator, test_data, tmp_path):
    """测试经验保存到文件"""
    # 使用临时目录
    experience_file = tmp_path / "experiences.json"

    result = accumulator.accumulate_from_performance(
        strategy_name='ma_cross',
        symbol='000001.SH',
        min_samples=10,
        output_file=str(experience_file)
    )

    assert result['success'] is True
    assert experience_file.exists()

    # 验证文件内容
    with open(experience_file, 'r') as f:
        data = json.load(f)

    assert 'version' in data
    assert 'experiences' in data
    assert len(data['experiences']) >= 1
