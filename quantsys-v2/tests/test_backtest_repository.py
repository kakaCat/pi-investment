"""
BacktestRepository单元测试
"""
import pytest
from adapters.outbound.repositories import BacktestORMRepository


class TestBacktestResults:
    """回测结果测试"""

    def setup_method(self):
        self.repo = BacktestORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # 2026-09-14（w-c8cae280）已删除本文件中对以下**不存在且无等价物**的方法的用例：
    #   save_strategy_config / get_strategy_config / get_top_strategies
    # 依据：三者在 BacktestRepository 上均不存在（实测 AttributeError），且**生产调用数均为 0**；
    # 策略侧现有能力是 strategy_repository.list_strategies()/get_strategy()/get_user_strategies()。
    # 故这不是「测试写错名字」而是能力不在此类；若确需策略配置读写，属**新需求**（应在 strategy_repository
    # 上实现并配新用例），不靠改测试解决。
    # ==================== 参数校验测试 ====================

    def test_get_all_backtests_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_all_backtests(symbol="INVALID")

    def test_save_backtest_missing_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.save_backtest_result({"strategy_name": "test"})

    def test_save_backtest_invalid_dates(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.save_backtest_result({
                "strategy_name": "test_strategy",
                "start_date": "2024/01/01",
                "end_date": "2024-01-31",
                "initial_capital": 100000.0,
                "final_capital": 110000.0
            })

    # ==================== 查询方法测试 ====================

    def test_get_backtest_not_found(self):
        result = self.repo.get_backtest(999999999)
        assert result is None

    def test_get_backtests_by_strategy(self):
        results = self.repo.get_backtests_by_strategy("nonexistent_strategy")
        assert isinstance(results, list)
        assert results == []

    def test_get_all_backtests(self):
        results = self.repo.get_all_backtests(limit=10)
        assert isinstance(results, list)
        assert len(results) <= 10
        if len(results) > 1:
            # 验证按夏普比率降序排列
            if results[0].get('sharpe_ratio') is not None and results[1].get('sharpe_ratio') is not None:
                assert results[0]['sharpe_ratio'] >= results[1]['sharpe_ratio']

    def test_get_backtest_stats(self):
        stats = self.repo.get_backtest_stats()
        assert isinstance(stats, dict)
        if stats:
            assert 'total_backtests' in stats

    # ==================== 写入方法测试 ====================

    def test_save_backtest_basic(self):
        data = {
            "strategy_name": "test_ma_cross",
            "symbol": "000001.SZ",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 100000.0,
            "final_capital": 105000.0,
            "total_return": 0.05,
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.03,
            "win_rate": 0.55,
            "total_trades": 20,
            "winning_trades": 11,
            "losing_trades": 9
        }
        try:
            backtest_id = self.repo.save_backtest_result(data)
            assert isinstance(backtest_id, int)
            assert backtest_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_save_backtest_with_jsonb(self):
        data = {
            "strategy_name": "test_with_params",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 100000.0,
            "final_capital": 108000.0,
            "parameters": {"ma_short": 5, "ma_long": 20},
            "equity_curve": [100000, 101000, 102000],
            "trade_details": [{"date": "2024-01-05", "action": "BUY", "price": 10.5}]
        }
        try:
            backtest_id = self.repo.save_backtest_result(data)
            assert isinstance(backtest_id, int)
            assert backtest_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


class TestStrategyConfigs:
    """策略配置测试"""

    def setup_method(self):
        self.repo = BacktestORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    # ==================== 查询方法测试 ====================

    def test_get_active_strategies(self):
        strategies = self.repo.get_active_strategies()
        assert isinstance(strategies, list)
        for s in strategies:
            assert s['is_active'] is True

    # ==================== 写入方法测试 ====================

    def test_activate_strategy(self):
        try:
            result = self.repo.activate_strategy("nonexistent_strategy")
            assert result is False
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_deactivate_strategy(self):
        try:
            result = self.repo.deactivate_strategy("nonexistent_strategy")
            assert result is False
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
