"""
量化流程端到端测试 — 完整闭环验证

测试范围: 信号 → 执行 → 盈亏 → 统计 → 经验 全链路

依赖:
- PostgreSQL 测试数据库 (quant_test)
- conftest.py 中的 db_connection fixture
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from application.services.signal_test_log import SignalTestLog
from application.services.order_service import _update_signal_tracking
from application.services.experience_accumulator import ExperienceAccumulator
from adapters.outbound.repositories import StrategyPerformanceRepository


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def signal_log():
    """创建 SignalTestLog 实例"""
    return SignalTestLog()


@pytest.fixture
def perf_repo():
    """创建 StrategyPerformanceRepository 实例"""
    return StrategyPerformanceRepository()


@pytest.fixture
def accumulator():
    """创建 ExperienceAccumulator 实例"""
    return ExperienceAccumulator()


@pytest.fixture(autouse=True)
def cleanup_test_data(signal_log):
    """每个测试前清理测试数据，测试后也清理"""
    # 测试前清理
    _cleanup(signal_log)
    yield
    # 测试后清理
    _cleanup(signal_log)


def _cleanup(signal_log):
    """清理测试数据"""
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM quant.signal_test_log WHERE reason LIKE '%E2E 测试%'"
        )
        # strategy_performance 表没有 reason 列，只用 symbol 匹配 E2E 测试数据
        cursor.execute(
            "DELETE FROM quant.strategy_performance WHERE symbol LIKE 'E2E%'"
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cursor.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _create_test_signal(signal_log, strategy="e2e_test_strategy",
                         symbol="E2E001.SH", name="端到端测试股",
                         signal_price=100.0, confidence=0.85):
    """创建测试信号"""
    return signal_log.record_signal({
        'symbol': symbol,
        'name': name,
        'strategy_name': strategy,
        'signal_date': date.today(),
        'action': 'buy',
        'confidence': confidence,
        'signal_price': signal_price,
        'entry_price': None,
        'stop_loss': signal_price * 0.92,
        'reason': f'{strategy} E2E 测试'
    })


def _verify_db_value(signal_log, signal_id: int, field: str) -> float:
    """读取数据库字段值"""
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"SELECT {field} FROM {signal_log.TABLE_NAME} WHERE id = %s",
            (signal_id,)
        )
        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else None
    finally:
        cursor.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════

class TestFullPipelineE2E:
    """完整流水线端到端测试"""

    @pytest.mark.integration
    def test_signal_to_pnl_full_chain(self, signal_log, perf_repo):
        """
        测试: 信号生成 → 买入成交 → 卖出成交 → 盈亏计算 → 统计验证

        全链路:
        1. 创建信号 (status=pending, entry_price=null)
        2. 模拟买入成交 → entry_price 更新
        3. 模拟卖出成交 → pnl_pct 计算 → strategy_performance 写入
        4. 验证所有中间状态
        5. 查询统计结果
        """
        # ── Step 1: 创建信号 ──
        signal_id = _create_test_signal(
            signal_log, strategy="e2e_ma_cross",
            symbol="E2E001.SH", signal_price=100.0
        )
        assert signal_id > 0, "信号创建失败"

        # 验证初始状态
        assert _verify_db_value(signal_log, signal_id, 'entry_price') is None
        assert _verify_db_value(signal_log, signal_id, 'pnl_pct') is None

        # ── Step 2: 模拟买入成交 ──
        buy_price = 102.0
        _update_signal_tracking(
            signal_id=signal_id,
            action='buy',
            fill_price=buy_price,
            symbol='E2E001.SH'
        )

        # 验证 entry_price 更新
        entry_price = _verify_db_value(signal_log, signal_id, 'entry_price')
        assert entry_price == buy_price, f"entry_price 应为 {buy_price}，实际 {entry_price}"

        # ── Step 3: 模拟卖出成交 ──
        sell_price = 110.0
        _update_signal_tracking(
            signal_id=signal_id,
            action='sell',
            fill_price=sell_price,
            symbol='E2E001.SH'
        )

        # 验证盈亏计算
        pnl_pct = _verify_db_value(signal_log, signal_id, 'pnl_pct')
        expected_pnl = (sell_price - buy_price) / buy_price * 100
        assert abs(pnl_pct - expected_pnl) < 0.01, \
            f"pnl_pct 应为 {expected_pnl:.2f}%，实际 {pnl_pct:.2f}%"

        # 验证 status 变为 verified
        conn = signal_log._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT status FROM {signal_log.TABLE_NAME} WHERE id = %s",
            (signal_id,)
        )
        status = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        assert status == 'verified', f"status 应为 'verified'，实际 {status}"

        # ── Step 4: 验证 strategy_performance 记录 ──
        records = perf_repo.get_by_strategy_and_symbol('e2e_ma_cross', 'E2E001.SH')
        assert len(records) >= 1, "strategy_performance 应至少有 1 条记录"

        perf = records[-1]
        assert float(perf['entry_price']) == buy_price
        assert float(perf['exit_price']) == sell_price
        assert abs(float(perf['pnl_pct']) - expected_pnl) < 0.01
        assert perf['source'] == 'live'

        # ── Step 5: 查询统计 ──
        stats = perf_repo.get_statistics(
            strategy_name='e2e_ma_cross',
            symbol='E2E001.SH',
            source='live'
        )
        assert stats['total_trades'] >= 1
        assert stats['win_trades'] >= 1  # 盈利交易
        assert stats['win_rate'] > 0
        assert stats['avg_pnl_pct'] > 0

    @pytest.mark.integration
    def test_signal_to_experience_flow(self, signal_log, perf_repo, accumulator, tmp_path):
        """
        测试: 多笔交易 → 统计 → 经验积累 → 写入文件

        验证经验积累器能从多笔交易中生成正确的经验条目
        """
        strategy = "e2e_momentum"
        symbol = "E2E002.SH"

        # 创建多笔完整的买卖记录
        trades = [
            (100.0, 105.0),   # +5%
            (100.0, 103.0),   # +3%
            (100.0, 97.0),    # -3%
            (100.0, 108.0),   # +8%
            (100.0, 104.0),   # +4%
            (100.0, 98.0),    # -2%
            (100.0, 106.0),   # +6%
            (100.0, 102.0),   # +2%
            (100.0, 109.0),   # +9%
            (100.0, 95.0),    # -5%
            (100.0, 107.0),   # +7%
            (100.0, 101.0),   # +1%
        ]

        for i, (buy, sell) in enumerate(trades):
            # 创建信号
            signal_id = _create_test_signal(
                signal_log, strategy=strategy,
                symbol=symbol, signal_price=buy
            )
            # 买入
            _update_signal_tracking(
                signal_id=signal_id, action='buy',
                fill_price=buy, symbol=symbol
            )
            # 卖出
            _update_signal_tracking(
                signal_id=signal_id, action='sell',
                fill_price=sell, symbol=symbol
            )

        # 验证有 12 条记录
        records = perf_repo.get_by_strategy_and_symbol(strategy, symbol)
        assert len(records) == len(trades), \
            f"应有 {len(trades)} 条记录，实际 {len(records)}"

        # ── 积累经验 ──
        output_file = str(tmp_path / "e2e_experiences.json")
        result = accumulator.accumulate_from_performance(
            strategy_name=strategy,
            symbol=symbol,
            min_samples=10,  # 最少 10 个样本
            output_file=output_file
        )

        assert result['success'] is True
        assert result['experience_created'] is True, \
            f"经验应被创建: {result.get('reason', '')}"

        experience = result['experience']
        # 验证经验条目字段
        assert 'scenario' in experience
        assert 'pattern' in experience
        assert 'outcomes' in experience
        assert 'recommendation' in experience
        assert 'reason' in experience

        # 验证统计数据
        # 注意：total_cases = paper(verified signals) + live(strategy_performance)
        # 每笔交易同时记录在两个源头，所以 total 是 trades 的 2 倍
        outcomes = experience['outcomes']
        assert outcomes['total_cases'] >= len(trades), \
            f"总案例应 >= {len(trades)}，实际 {outcomes['total_cases']}"
        win_trades = sum(1 for b, s in trades if s > b)
        expected_win_rate = win_trades / len(trades) * 100
        assert abs(outcomes['win_rate'] - expected_win_rate) < 5.0

        # 推荐等级应合理
        assert experience['recommendation'] in ('aggressive', 'moderate', 'cautious', 'avoid')

        # 验证文件写入
        import json
        with open(output_file, 'r') as f:
            saved = json.load(f)
        assert 'experiences' in saved
        assert len(saved['experiences']) >= 1

    @pytest.mark.integration
    def test_pipeline_with_loss_trades(self, signal_log, perf_repo):
        """
        测试: 亏损交易场景 — 验证胜率和统计正确性
        """
        strategy = "e2e_loss_test"
        symbol = "E2E003.SH"

        # 3 赚 7 亏
        trades = [
            (100.0, 108.0),   # +8% win
            (100.0, 103.0),   # +3% win
            (100.0, 92.0),    # -8% loss
            (100.0, 90.0),    # -10% loss
            (100.0, 95.0),    # -5% loss
            (100.0, 91.0),    # -9% loss
            (100.0, 105.0),   # +5% win
            (100.0, 88.0),    # -12% loss
            (100.0, 93.0),    # -7% loss
            (100.0, 85.0),    # -15% loss
        ]

        for buy, sell in trades:
            signal_id = _create_test_signal(
                signal_log, strategy=strategy,
                symbol=symbol, signal_price=buy
            )
            _update_signal_tracking(
                signal_id=signal_id, action='buy',
                fill_price=buy, symbol=symbol
            )
            _update_signal_tracking(
                signal_id=signal_id, action='sell',
                fill_price=sell, symbol=symbol
            )

        # 验证统计
        stats = perf_repo.get_statistics(
            strategy_name=strategy,
            symbol=symbol,
            source='live'
        )

        assert stats['total_trades'] == 10
        assert stats['win_trades'] == 3
        assert stats['loss_trades'] == 7
        assert abs(stats['win_rate'] - 30.0) < 0.5
        # 平均盈亏应为负
        assert stats['avg_pnl_pct'] < 0

    @pytest.mark.integration
    def test_pipeline_entry_price_immutable(self, signal_log):
        """
        测试: 多次买入成交不应覆盖 entry_price
        """
        signal_id = _create_test_signal(
            signal_log, strategy="e2e_immutable",
            symbol="E2E004.SH", signal_price=50.0
        )

        # 第一次买入
        _update_signal_tracking(
            signal_id=signal_id, action='buy',
            fill_price=51.0, symbol='E2E004.SH'
        )

        # 第二次买入（部分成交）
        _update_signal_tracking(
            signal_id=signal_id, action='buy',
            fill_price=52.0, symbol='E2E004.SH'
        )

        # 验证 entry_price 保持不变
        entry_price = _verify_db_value(signal_log, signal_id, 'entry_price')
        assert entry_price == 51.0, \
            f"entry_price 应保持第一次成交价 51.0，实际 {entry_price}"


class TestPipelineEdgeCases:
    """流水线边界条件测试"""

    @pytest.mark.integration
    def test_sell_without_entry_price_no_pnl(self, signal_log, perf_repo):
        """
        测试: 卖出时没有 entry_price — 不计算盈亏
        """
        signal_id = _create_test_signal(
            signal_log, strategy="e2e_no_entry",
            symbol="E2E005.SH", signal_price=50.0
        )

        # 直接卖出（没有买入过）
        _update_signal_tracking(
            signal_id=signal_id, action='sell',
            fill_price=52.0, symbol='E2E005.SH'
        )

        # pnl_pct 应为 None
        pnl = _verify_db_value(signal_log, signal_id, 'pnl_pct')
        assert pnl is None, f"没有 entry_price 时 pnl_pct 应为 None，实际 {pnl}"

        # 不应写入 strategy_performance
        records = perf_repo.get_by_strategy_and_symbol('e2e_no_entry', 'E2E005.SH')
        assert len(records) == 0, "无 entry_price 时不应写入 performance 记录"

    @pytest.mark.integration
    def test_experience_insufficient_samples(self, signal_log, accumulator):
        """
        测试: 样本不足时经验积累器拒绝生成经验
        """
        strategy = "e2e_insufficient"
        symbol = "E2E006.SH"

        # 只创建 3 笔交易
        for buy, sell in [(100, 105), (100, 103), (100, 98)]:
            signal_id = _create_test_signal(
                signal_log, strategy=strategy,
                symbol=symbol, signal_price=buy
            )
            _update_signal_tracking(
                signal_id=signal_id, action='buy',
                fill_price=buy, symbol=symbol
            )
            _update_signal_tracking(
                signal_id=signal_id, action='sell',
                fill_price=sell, symbol=symbol
            )

        result = accumulator.accumulate_from_performance(
            strategy_name=strategy,
            symbol=symbol,
            min_samples=10  # 要求最少 10，只有 3
        )

        assert result['success'] is True
        assert result['experience_created'] is False
        assert 'Insufficient samples' in result.get('reason', '')


class TestPipelineRecommendationLevels:
    """测试经验推荐等级逻辑"""

    @pytest.mark.integration
    def test_aggressive_recommendation(self, signal_log, perf_repo, accumulator, tmp_path):
        """
        测试: 高胜率+高收益 → aggressive 推荐
        胜率 >= 70% 且平均收益 >= 3%
        """
        strategy = "e2e_aggressive"
        symbol = "E2E007.SH"

        # 8 赢 2 亏 = 80% 胜率，平均收益约 4%
        trades = [
            (100, 106), (100, 108), (100, 105), (100, 107),
            (100, 104), (100, 109), (100, 103), (100, 110),
            (100, 97), (100, 95),
        ]

        for buy, sell in trades:
            signal_id = _create_test_signal(
                signal_log, strategy=strategy,
                symbol=symbol, signal_price=buy
            )
            _update_signal_tracking(
                signal_id=signal_id, action='buy',
                fill_price=buy, symbol=symbol
            )
            _update_signal_tracking(
                signal_id=signal_id, action='sell',
                fill_price=sell, symbol=symbol
            )

        result = accumulator.accumulate_from_performance(
            strategy_name=strategy,
            symbol=symbol,
            min_samples=5,
            output_file=str(tmp_path / "aggressive.json")
        )

        assert result['experience_created'] is True
        # 验证推荐等级
        outcomes = result['experience']['outcomes']
        assert outcomes['win_rate'] >= 70
        assert outcomes['avg_return'] >= 3
        # 推荐等级应为 aggressive
        assert result['experience']['recommendation'] == 'aggressive', \
            f"应为 aggressive，实际 {result['experience']['recommendation']}"

    @pytest.mark.integration
    def test_avoid_recommendation(self, signal_log, perf_repo, accumulator, tmp_path):
        """
        测试: 低胜率+负收益 → avoid 推荐
        胜率 < 50% 或平均收益 < 1%
        """
        strategy = "e2e_avoid"
        symbol = "E2E008.SH"

        # 3 赢 7 亏 = 30% 胜率
        trades = [
            (100, 106), (100, 103), (100, 105),
            (100, 90), (100, 92), (100, 88),
            (100, 85), (100, 93), (100, 91), (100, 87),
        ]

        for buy, sell in trades:
            signal_id = _create_test_signal(
                signal_log, strategy=strategy,
                symbol=symbol, signal_price=buy
            )
            _update_signal_tracking(
                signal_id=signal_id, action='buy',
                fill_price=buy, symbol=symbol
            )
            _update_signal_tracking(
                signal_id=signal_id, action='sell',
                fill_price=sell, symbol=symbol
            )

        result = accumulator.accumulate_from_performance(
            strategy_name=strategy,
            symbol=symbol,
            min_samples=5,
            output_file=str(tmp_path / "avoid.json")
        )

        assert result['experience_created'] is True
        assert result['experience']['recommendation'] == 'avoid', \
            f"应为 avoid，实际 {result['experience']['recommendation']}"
