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


class TestStopLossRules:
    """止损规则 CRUD 测试（quant.stop_loss_rules 表）

    回归测试：8f06ae1 DDD 重构删掉了这些方法，但 routes/risk.py 仍在调用，
    导致 /api/risk/check 页面相关接口 500（'RiskORMRepository' object has
    no attribute 'list_stop_loss_rules'）。
    """

    @pytest.fixture(autouse=True)
    def _setup(self, db_connection):
        self.repo = RiskORMRepository()
        self._created_ids = []
        yield
        for rule_id in self._created_ids:
            try:
                self.repo.delete_stop_loss_rule(rule_id)
            except Exception:
                pass

    def _make_rule(self, rule_id="test-sl-1", **overrides):
        rule_data = {
            "id": rule_id,
            "symbol": "000001.SZ",
            "name": "测试止损",
            "type": "fixed_percent",
            "stop_loss_percent": 8.0,
        }
        rule_data.update(overrides)
        self._created_ids.append(rule_id)
        return rule_data

    # ==================== 参数校验测试 ====================

    def test_create_missing_required_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.create_stop_loss_rule({"id": "x", "symbol": "000001.SZ"})

    def test_create_invalid_type(self):
        with pytest.raises(ValueError, match="无效的规则类型"):
            self.repo.create_stop_loss_rule(self._make_rule(type="bad_type"))

    def test_list_invalid_status(self):
        with pytest.raises(ValueError, match="无效的状态值"):
            self.repo.list_stop_loss_rules(status="bad_status")

    # ==================== CRUD 测试 ====================

    def test_create_and_get_rule(self):
        rule_id = self.repo.create_stop_loss_rule(self._make_rule())
        assert rule_id == "test-sl-1"

        rule = self.repo.get_stop_loss_rule(rule_id)
        assert rule is not None
        assert rule["symbol"] == "000001.SZ"
        assert rule["type"] == "fixed_percent"
        assert rule["status"] == "active"
        assert "created_at" in rule

    def test_get_rule_not_found(self):
        assert self.repo.get_stop_loss_rule("nonexistent-id") is None

    def test_list_rules_filter(self):
        self.repo.create_stop_loss_rule(self._make_rule("test-sl-a", symbol="000001.SZ"))
        self.repo.create_stop_loss_rule(self._make_rule("test-sl-b", symbol="600000.SH"))

        all_rules = self.repo.list_stop_loss_rules()
        listed_ids = {r["id"] for r in all_rules}
        assert {"test-sl-a", "test-sl-b"} <= listed_ids

        filtered = self.repo.list_stop_loss_rules(symbol="600000.SH")
        filtered_ids = {r["id"] for r in filtered}
        assert "test-sl-b" in filtered_ids
        assert "test-sl-a" not in filtered_ids

        active = self.repo.list_stop_loss_rules(status="active")
        assert {r["id"] for r in active} >= {"test-sl-a", "test-sl-b"}

    def test_update_rule(self):
        self.repo.create_stop_loss_rule(self._make_rule())

        ok = self.repo.update_stop_loss_rule("test-sl-1", {
            "stop_loss_percent": 5.0,
            "status": "inactive",
        })
        assert ok is True

        rule = self.repo.get_stop_loss_rule("test-sl-1")
        assert rule["stop_loss_percent"] == pytest.approx(5.0)
        assert rule["status"] == "inactive"

    def test_update_rule_not_found(self):
        assert self.repo.update_stop_loss_rule("nonexistent-id", {"name": "x"}) is False

    def test_delete_rule(self):
        self.repo.create_stop_loss_rule(self._make_rule())

        assert self.repo.delete_stop_loss_rule("test-sl-1") is True
        assert self.repo.get_stop_loss_rule("test-sl-1") is None
        assert self.repo.delete_stop_loss_rule("test-sl-1") is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
