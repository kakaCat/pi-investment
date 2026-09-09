"""测试交易策略配置

验证 V13 和 V14 策略配置的默认值与原代码完全一致。
"""

import pytest
from infrastructure.config.constants.trading.strategy import (
    V13StrategyDefaults,
    V14StrategyDefaults,
    V13_DEFAULTS,
    V14_DEFAULTS,
)


class TestV13StrategyDefaults:
    """测试 V13 策略默认参数"""

    def test_default_values_match_original(self):
        """确保默认值与原 v13_config.py 完全一致"""
        config = V13StrategyDefaults()

        # 验证每个参数与原始代码一致
        assert config.REBALANCE_DAYS == 5
        assert config.MAX_POSITIONS == 8
        assert config.MAX_POSITION_PCT == 0.85
        assert config.STOP_LOSS_PCT == -0.12
        assert config.TRAILING_STOP_PCT == -0.08
        assert config.PORTFOLIO_STOP_LOSS_PCT == -0.20

    def test_singleton_instance(self):
        """测试全局单例实例"""
        assert V13_DEFAULTS.REBALANCE_DAYS == 5
        assert V13_DEFAULTS.MAX_POSITIONS == 8

    def test_immutable(self):
        """测试配置不可变"""
        config = V13StrategyDefaults()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.REBALANCE_DAYS = 10  # type: ignore

    def test_validate_success(self):
        """测试默认配置验证通过"""
        config = V13StrategyDefaults()
        is_valid, errors = config.validate()
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0

    def test_validate_rebalance_days_positive(self):
        """测试调仓周期必须为正数"""
        config = V13StrategyDefaults(REBALANCE_DAYS=0)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("REBALANCE_DAYS" in err and "大于 0" in err for err in errors)

    def test_validate_max_positions_positive(self):
        """测试持仓数量必须为正数"""
        config = V13StrategyDefaults(MAX_POSITIONS=0)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("MAX_POSITIONS" in err and "大于 0" in err for err in errors)

    def test_validate_max_position_pct_range(self):
        """测试仓位比例必须在 (0, 1] 范围内"""
        # 测试 0
        config = V13StrategyDefaults(MAX_POSITION_PCT=0.0)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试负数
        config = V13StrategyDefaults(MAX_POSITION_PCT=-0.1)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试大于 1
        config = V13StrategyDefaults(MAX_POSITION_PCT=1.1)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试边界值 1.0（应通过）
        config = V13StrategyDefaults(MAX_POSITION_PCT=1.0)
        is_valid, errors = config.validate()
        assert is_valid

    def test_validate_stop_loss_must_be_negative(self):
        """测试止损比例必须为负数"""
        config = V13StrategyDefaults(STOP_LOSS_PCT=0.12)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("STOP_LOSS_PCT" in err and "负数" in err for err in errors)

    def test_validate_trailing_stop_must_be_negative(self):
        """测试移动止损比例必须为负数"""
        config = V13StrategyDefaults(TRAILING_STOP_PCT=0.08)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("TRAILING_STOP_PCT" in err and "负数" in err for err in errors)

    def test_validate_portfolio_stop_loss_must_be_negative(self):
        """测试组合止损比例必须为负数"""
        config = V13StrategyDefaults(PORTFOLIO_STOP_LOSS_PCT=0.20)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("PORTFOLIO_STOP_LOSS_PCT" in err and "负数" in err for err in errors)

    def test_validate_trailing_stop_stricter_than_stop_loss(self):
        """测试移动止损应该比固定止损更严格"""
        # 错误：移动止损 -15% 比固定止损 -12% 更宽松
        config = V13StrategyDefaults(
            STOP_LOSS_PCT=-0.12,
            TRAILING_STOP_PCT=-0.15
        )
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("TRAILING_STOP_PCT" in err and "更严格" in err for err in errors)

    def test_validate_portfolio_stop_loss_wider_than_stop_loss(self):
        """测试组合止损应该比单只股票止损更宽松"""
        # 错误：组合止损 -10% 比单只股票止损 -12% 更严格
        config = V13StrategyDefaults(
            STOP_LOSS_PCT=-0.12,
            PORTFOLIO_STOP_LOSS_PCT=-0.10
        )
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("PORTFOLIO_STOP_LOSS_PCT" in err and "更宽松" in err for err in errors)

    def test_to_dict(self):
        """测试导出为字典"""
        config = V13StrategyDefaults()
        d = config.to_dict()
        assert d['REBALANCE_DAYS'] == 5
        assert d['MAX_POSITIONS'] == 8
        assert d['MAX_POSITION_PCT'] == 0.85
        assert d['STOP_LOSS_PCT'] == -0.12

    def test_from_env(self, monkeypatch):
        """测试从环境变量覆盖"""
        monkeypatch.setenv("V13_REBALANCE_DAYS", "7")
        monkeypatch.setenv("V13_MAX_POSITIONS", "10")
        monkeypatch.setenv("V13_MAX_POSITION_PCT", "0.90")

        config = V13StrategyDefaults.from_env(prefix="V13_")

        assert config.REBALANCE_DAYS == 7
        assert config.MAX_POSITIONS == 10
        assert config.MAX_POSITION_PCT == 0.90
        # 未覆盖的保持默认值
        assert config.STOP_LOSS_PCT == -0.12


class TestV14StrategyDefaults:
    """测试 V14 策略默认参数"""

    def test_default_values_match_original(self):
        """确保默认值与原 v14_config.py 完全一致"""
        config = V14StrategyDefaults()

        # 验证每个参数与原始代码一致
        assert config.REBALANCE_DAYS == 30
        assert config.MAX_POSITIONS == 15
        assert config.MAX_POSITION_PCT == 0.95
        assert config.STOP_LOSS_PCT == -0.15
        assert config.TRAILING_STOP_PCT == -0.10
        assert config.PORTFOLIO_STOP_LOSS_PCT == -0.25

    def test_singleton_instance(self):
        """测试全局单例实例"""
        assert V14_DEFAULTS.REBALANCE_DAYS == 30
        assert V14_DEFAULTS.MAX_POSITIONS == 15

    def test_validate_success(self):
        """测试默认配置验证通过"""
        config = V14StrategyDefaults()
        is_valid, errors = config.validate()
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0

    def test_immutable(self):
        """测试配置不可变"""
        config = V14StrategyDefaults()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.REBALANCE_DAYS = 20  # type: ignore

    def test_v13_vs_v14_differences(self):
        """验证 V13 和 V14 的差异"""
        v13 = V13StrategyDefaults()
        v14 = V14StrategyDefaults()

        # V14 调仓周期更长
        assert v14.REBALANCE_DAYS > v13.REBALANCE_DAYS

        # V14 持仓更多
        assert v14.MAX_POSITIONS > v13.MAX_POSITIONS

        # V14 仓位比例更高
        assert v14.MAX_POSITION_PCT > v13.MAX_POSITION_PCT

        # V14 止损更宽松（绝对值更大）
        assert abs(v14.STOP_LOSS_PCT) > abs(v13.STOP_LOSS_PCT)
        assert abs(v14.TRAILING_STOP_PCT) > abs(v13.TRAILING_STOP_PCT)
        assert abs(v14.PORTFOLIO_STOP_LOSS_PCT) > abs(v13.PORTFOLIO_STOP_LOSS_PCT)

    def test_to_dict(self):
        """测试导出为字典"""
        config = V14StrategyDefaults()
        d = config.to_dict()
        assert d['REBALANCE_DAYS'] == 30
        assert d['MAX_POSITIONS'] == 15
        assert d['MAX_POSITION_PCT'] == 0.95
        assert d['STOP_LOSS_PCT'] == -0.15

    def test_from_env(self, monkeypatch):
        """测试从环境变量覆盖"""
        monkeypatch.setenv("V14_REBALANCE_DAYS", "45")
        monkeypatch.setenv("V14_MAX_POSITIONS", "20")

        config = V14StrategyDefaults.from_env(prefix="V14_")

        assert config.REBALANCE_DAYS == 45
        assert config.MAX_POSITIONS == 20
        # 未覆盖的保持默认值
        assert config.MAX_POSITION_PCT == 0.95
