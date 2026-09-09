"""回归测试：确保策略配置重构后值不变

这些测试验证重构后的 v13_config.py 和 v14_config.py 与原始硬编码值完全一致。
"""

import pytest


class TestV13ConfigRegression:
    """测试 V13_CONFIG 重构后值不变"""

    def test_v13_config_values_unchanged(self):
        """确保 V13_CONFIG 的所有参数与原始值一致"""
        from application.strategies.v13_config import V13_CONFIG

        # 验证每个参数与原始硬编码值完全一致
        assert V13_CONFIG.name == "xgboost_multi_factor"
        assert V13_CONFIG.version == "V13"
        assert V13_CONFIG.rebalance_days == 5
        assert V13_CONFIG.max_positions == 8
        assert V13_CONFIG.max_position_pct == 0.85
        assert V13_CONFIG.stop_loss_pct == -0.12
        assert V13_CONFIG.trailing_stop_pct == -0.08
        assert V13_CONFIG.portfolio_stop_loss_pct == -0.20
        assert V13_CONFIG.model_path == "live_trading/models/xgboost_multi_factor_model.json"
        assert V13_CONFIG.factors_path == "config/v13_factors.json"

    def test_v13_config_type_unchanged(self):
        """确保 V13_CONFIG 的类型不变"""
        from application.strategies.v13_config import V13_CONFIG
        from domain.strategies.value_objects import StrategyConfig

        assert isinstance(V13_CONFIG, StrategyConfig)

    def test_v13_config_can_be_used_as_before(self):
        """确保 V13_CONFIG 可以像以前一样使用"""
        from application.strategies.v13_config import V13_CONFIG

        # 测试 dict-like 访问（向后兼容）
        assert V13_CONFIG.get('rebalance_days') == 5
        assert V13_CONFIG.get('max_positions') == 8
        assert V13_CONFIG.get('nonexistent', 'default') == 'default'


class TestV14ConfigRegression:
    """测试 V14_CONFIG 重构后值不变"""

    def test_v14_config_values_unchanged(self):
        """确保 V14_CONFIG 的所有参数与原始值一致"""
        from application.strategies.v14_config import V14_CONFIG

        # 验证每个参数与原始硬编码值完全一致
        assert V14_CONFIG.name == "xgboost_optimized"
        assert V14_CONFIG.version == "V14"
        assert V14_CONFIG.rebalance_days == 30
        assert V14_CONFIG.max_positions == 15
        assert V14_CONFIG.max_position_pct == 0.95
        assert V14_CONFIG.stop_loss_pct == -0.15
        assert V14_CONFIG.trailing_stop_pct == -0.10
        assert V14_CONFIG.portfolio_stop_loss_pct == -0.25
        assert V14_CONFIG.model_path == "live_trading/models/v14_p0_model.json"
        assert V14_CONFIG.factors_path == "config/v14_factors.json"

    def test_v14_config_type_unchanged(self):
        """确保 V14_CONFIG 的类型不变"""
        from application.strategies.v14_config import V14_CONFIG
        from domain.strategies.value_objects import StrategyConfig

        assert isinstance(V14_CONFIG, StrategyConfig)

    def test_v14_config_can_be_used_as_before(self):
        """确保 V14_CONFIG 可以像以前一样使用"""
        from application.strategies.v14_config import V14_CONFIG

        # 测试 dict-like 访问（向后兼容）
        assert V14_CONFIG.get('rebalance_days') == 30
        assert V14_CONFIG.get('max_positions') == 15
        assert V14_CONFIG.get('nonexistent', 'default') == 'default'


class TestStrategyConfigComparison:
    """比较 V13 和 V14 策略配置"""

    def test_v13_vs_v14_differences(self):
        """验证 V13 和 V14 的已知差异"""
        from application.strategies.v13_config import V13_CONFIG
        from application.strategies.v14_config import V14_CONFIG

        # V14 调仓周期更长
        assert V14_CONFIG.rebalance_days > V13_CONFIG.rebalance_days
        assert V14_CONFIG.rebalance_days == 30
        assert V13_CONFIG.rebalance_days == 5

        # V14 持仓更多
        assert V14_CONFIG.max_positions > V13_CONFIG.max_positions
        assert V14_CONFIG.max_positions == 15
        assert V13_CONFIG.max_positions == 8

        # V14 仓位比例更高
        assert V14_CONFIG.max_position_pct > V13_CONFIG.max_position_pct
        assert V14_CONFIG.max_position_pct == 0.95
        assert V13_CONFIG.max_position_pct == 0.85

        # V14 止损更宽松
        assert abs(V14_CONFIG.stop_loss_pct) > abs(V13_CONFIG.stop_loss_pct)
        assert V14_CONFIG.stop_loss_pct == -0.15
        assert V13_CONFIG.stop_loss_pct == -0.12


class TestStrategyConfigImportability:
    """测试配置可以正常导入"""

    def test_can_import_v13_config(self):
        """测试可以导入 V13_CONFIG"""
        try:
            from application.strategies.v13_config import V13_CONFIG
            assert V13_CONFIG is not None
        except ImportError as e:
            pytest.fail(f"Failed to import V13_CONFIG: {e}")

    def test_can_import_v14_config(self):
        """测试可以导入 V14_CONFIG"""
        try:
            from application.strategies.v14_config import V14_CONFIG
            assert V14_CONFIG is not None
        except ImportError as e:
            pytest.fail(f"Failed to import V14_CONFIG: {e}")

    def test_configs_are_frozen(self):
        """测试配置对象是只读的"""
        from application.strategies.v13_config import V13_CONFIG
        from application.strategies.v14_config import V14_CONFIG

        # StrategyConfig 使用 frozen=True，应该是不可变的
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            V13_CONFIG.rebalance_days = 999  # type: ignore

        with pytest.raises(Exception):
            V14_CONFIG.max_positions = 999  # type: ignore
