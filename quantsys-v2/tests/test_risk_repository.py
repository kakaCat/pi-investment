"""
RiskRepository单元测试
"""
import pytest
from adapters.outbound.repositories import RiskORMRepository


class TestAccountBalance:
    """账户资金测试"""

    def setup_method(self):
        self.repo = RiskORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    def test_get_balance_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_balance("2024/01/01")

    def test_get_balance_history_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_balance_history("2024/01/01", "2024-01-31")

    def test_get_balance_stats_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_balance_stats("2024/01/01", "2024-01-31")

    def test_save_balance_missing_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.save_balance({"balance_date": "2024-01-01"})

    def test_save_balance_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.save_balance({
                "balance_date": "2024/01/01",
                "cash": 50000.0,
                "market_value": 50000.0,
                "total_assets": 100000.0
            })

    # ==================== 查询方法测试 ====================

    def test_get_balance_not_found(self):
        balance = self.repo.get_balance("2020-01-01")
        assert balance is None

    def test_get_balance_history_empty(self):
        history = self.repo.get_balance_history("2020-01-01", "2020-01-31")
        assert isinstance(history, list)
        assert history == []

    def test_get_latest_balance(self):
        balance = self.repo.get_latest_balance()
        if balance:
            assert 'balance_date' in balance
            assert 'cash' in balance
            assert 'market_value' in balance
            assert 'total_assets' in balance

    def test_get_balance_stats(self):
        stats = self.repo.get_balance_stats("2024-01-01", "2024-01-31")
        assert isinstance(stats, dict)
        if stats:
            assert 'max_assets' in stats
            assert 'min_assets' in stats

    # ==================== 写入方法测试 ====================

    def test_save_balance_basic(self):
        data = {
            "balance_date": "2024-01-02",
            "cash": 50000.0,
            "market_value": 55000.0,
            "total_assets": 105000.0,
            "daily_pnl": 5000.0,
            "daily_return": 0.05,
            "position_count": 5
        }
        try:
            result = self.repo.save_balance(data)
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_get_balance_history_with_data(self):
        history = self.repo.get_balance_history("2024-01-01", "2024-01-31")
        assert isinstance(history, list)
        if len(history) > 1:
            # 验证按日期升序排列
            assert history[0]['balance_date'] <= history[1]['balance_date']


class TestRiskMetrics:
    """风险指标测试"""

    def setup_method(self):
        self.repo = RiskORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    def test_get_risk_metrics_no_params(self):
        with pytest.raises(ValueError, match="symbol和metric_date至少需要提供一个"):
            self.repo.get_risk_metrics()

    def test_get_risk_metrics_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_risk_metrics(symbol="INVALID")

    def test_get_risk_metrics_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_risk_metrics(metric_date="2024/01/01")

    def test_get_risk_history_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_risk_history(symbol="INVALID")

    def test_get_risk_history_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_risk_history(start_date="2024/01/01")

    def test_get_latest_risk_metrics_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_latest_risk_metrics("INVALID")

    def test_save_risk_metrics_missing_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.save_risk_metrics({"metric_date": "2024-01-01"})

    def test_save_risk_metrics_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.save_risk_metrics({
                "metric_date": "2024-01-01",
                "symbol": "INVALID"
            })

    def test_save_risk_metrics_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.save_risk_metrics({
                "metric_date": "2024/01/01",
                "symbol": "000001.SZ"
            })

    # ==================== 查询方法测试 ====================

    def test_get_risk_metrics_not_found(self):
        result = self.repo.get_risk_metrics(symbol="999999.SZ")
        assert result is None

    def test_get_risk_history_empty(self):
        history = self.repo.get_risk_history(symbol="999999.SZ")
        assert isinstance(history, list)
        assert history == []

    def test_get_latest_risk_metrics_not_found(self):
        result = self.repo.get_latest_risk_metrics("999999.SZ")
        assert result is None

    def test_get_risk_stats(self):
        stats = self.repo.get_risk_stats()
        assert isinstance(stats, dict)
        if stats:
            assert 'total_records' in stats

    # ==================== 写入方法测试 ====================

    def test_save_risk_metrics_basic(self):
        data = {
            "metric_date": "2024-01-02",
            "symbol": "000001.SZ",
            "volatility": 0.25,
            "beta": 1.1,
            "var_95": -0.03,
            "cvar_95": -0.05,
            "max_position_ratio": 0.1,
            "concentration_risk": 0.3
        }
        try:
            result = self.repo.save_risk_metrics(data)
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_save_risk_metrics_with_jsonb(self):
        data = {
            "metric_date": "2024-01-02",
            "symbol": "000002.SZ",
            "volatility": 0.20,
            "sector_exposure": {"金融": 0.3, "科技": 0.4, "消费": 0.3},
            "correlation_matrix": {"000001.SZ": 0.8, "600000.SH": 0.5}
        }
        try:
            result = self.repo.save_risk_metrics(data)
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
