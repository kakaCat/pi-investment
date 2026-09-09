"""测试风控限制配置

验证 RiskLimits 配置类的默认值与原始代码一致，并测试验证逻辑。
"""

import pytest
from infrastructure.config.constants.trading.risk_limits import RiskLimits, RISK_LIMITS


class TestRiskLimits:
    """测试风控限制配置"""

    def test_default_values_match_original(self):
        """确保默认值与原始 risk_rules.py 完全一致"""
        config = RiskLimits()

        # 仓位控制
        assert config.MAX_SINGLE_POSITION_RATIO == 0.20
        assert config.MAX_SECTOR_CONCENTRATION == 0.40
        assert config.MAX_CONCURRENT_POSITIONS == 10

        # 止损控制
        assert config.STOP_LOSS_THRESHOLD == -0.08
        assert config.MAX_DAILY_DRAWDOWN == 0.05

        # 流动性控制
        assert config.MAX_ORDER_VS_DAILY_VOLUME == 0.20
        assert config.VOLUME_LOOKBACK_DAYS == 60
        assert config.VOLUME_RECENT_DAYS == 20
        assert config.MIN_KLINE_COUNT == 20

        # 相关性风险
        assert config.HIGH_CORRELATION_THRESHOLD == 0.80
        assert config.CORRELATION_LOOKBACK_DAYS == 90

        # Beta 敞口
        assert config.MIN_BETA_EXPOSURE == 0.5
        assert config.MAX_BETA_EXPOSURE == 1.5

        # 波动率
        assert config.MAX_STOCK_VOLATILITY == 0.30
        assert config.VOLATILITY_LOOKBACK_DAYS == 60

        # 市场环境
        assert config.VIX_PANIC_THRESHOLD == 30.0
        assert config.MIN_ADVANCE_DECLINE_RATIO == 0.30
        assert config.MARKET_REGIME_LOOKBACK_DAYS == 60
        assert config.MARKET_REGIME_MA_SHORT == 20

        # 交易时段
        assert config.AVOID_OPEN_MINUTES == 30
        assert config.AVOID_CLOSE_MINUTES == 30

        # 默认账户余额
        assert config.DEFAULT_ACCOUNT_BALANCE == 1000000.0

    def test_singleton_instance(self):
        """测试全局单例实例"""
        assert RISK_LIMITS.MAX_SINGLE_POSITION_RATIO == 0.20
        assert RISK_LIMITS.STOP_LOSS_THRESHOLD == -0.08

    def test_immutable(self):
        """测试配置不可变"""
        config = RiskLimits()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.MAX_SINGLE_POSITION_RATIO = 0.30  # type: ignore

    def test_validate_success(self):
        """测试默认配置验证通过"""
        config = RiskLimits()
        is_valid, errors = config.validate()
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0

    def test_validate_max_single_position_ratio_range(self):
        """测试单只股票仓位比例范围"""
        # 测试 0
        config = RiskLimits(MAX_SINGLE_POSITION_RATIO=0.0)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("MAX_SINGLE_POSITION_RATIO" in err for err in errors)

        # 测试负数
        config = RiskLimits(MAX_SINGLE_POSITION_RATIO=-0.1)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试大于 1
        config = RiskLimits(MAX_SINGLE_POSITION_RATIO=1.1)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试边界值 1.0（需要同时调整 MAX_SECTOR_CONCENTRATION）
        config = RiskLimits(
            MAX_SINGLE_POSITION_RATIO=1.0,
            MAX_SECTOR_CONCENTRATION=1.0  # 必须大于等于单只股票仓位
        )
        is_valid, errors = config.validate()
        assert is_valid

    def test_validate_sector_concentration_vs_position_ratio(self):
        """测试行业集中度必须大于等于单只股票仓位"""
        # 错误：行业集中度 15% < 单只股票 20%
        config = RiskLimits(
            MAX_SINGLE_POSITION_RATIO=0.20,
            MAX_SECTOR_CONCENTRATION=0.15
        )
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("MAX_SECTOR_CONCENTRATION" in err and "不能小于" in err for err in errors)

    def test_validate_stop_loss_threshold_range(self):
        """测试止损阈值必须为负数"""
        # 测试正数（错误）
        config = RiskLimits(STOP_LOSS_THRESHOLD=0.08)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试 0（错误）
        config = RiskLimits(STOP_LOSS_THRESHOLD=0.0)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试小于 -1（错误）
        config = RiskLimits(STOP_LOSS_THRESHOLD=-1.5)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试边界值 -1.0（应通过）
        config = RiskLimits(STOP_LOSS_THRESHOLD=-1.0)
        is_valid, errors = config.validate()
        assert is_valid

    def test_validate_volume_days_consistency(self):
        """测试成交量天数参数一致性"""
        # 错误：VOLUME_RECENT_DAYS > VOLUME_LOOKBACK_DAYS
        config = RiskLimits(
            VOLUME_LOOKBACK_DAYS=60,
            VOLUME_RECENT_DAYS=90
        )
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("VOLUME_RECENT_DAYS" in err and "不能大于" in err for err in errors)

    def test_validate_beta_exposure_range(self):
        """测试 Beta 敞口范围"""
        # 错误：MIN >= MAX
        config = RiskLimits(
            MIN_BETA_EXPOSURE=1.5,
            MAX_BETA_EXPOSURE=0.5
        )
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("MIN_BETA_EXPOSURE" in err and "必须小于" in err for err in errors)

    def test_validate_positive_values(self):
        """测试必须为正数的参数"""
        # 测试 MAX_CONCURRENT_POSITIONS
        config = RiskLimits(MAX_CONCURRENT_POSITIONS=0)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试 VOLUME_LOOKBACK_DAYS
        config = RiskLimits(VOLUME_LOOKBACK_DAYS=-1)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试 VIX_PANIC_THRESHOLD
        config = RiskLimits(VIX_PANIC_THRESHOLD=-10.0)
        is_valid, errors = config.validate()
        assert not is_valid

    def test_validate_non_negative_values(self):
        """测试必须非负的参数"""
        # 测试 AVOID_OPEN_MINUTES
        config = RiskLimits(AVOID_OPEN_MINUTES=-5)
        is_valid, errors = config.validate()
        assert not is_valid

        # 测试 AVOID_CLOSE_MINUTES
        config = RiskLimits(AVOID_CLOSE_MINUTES=-10)
        is_valid, errors = config.validate()
        assert not is_valid

    def test_to_dict(self):
        """测试导出为字典"""
        config = RiskLimits()
        d = config.to_dict()

        assert d['MAX_SINGLE_POSITION_RATIO'] == 0.20
        assert d['STOP_LOSS_THRESHOLD'] == -0.08
        assert d['MAX_CONCURRENT_POSITIONS'] == 10
        assert d['DEFAULT_ACCOUNT_BALANCE'] == 1000000.0

    def test_from_env(self, monkeypatch):
        """测试从环境变量覆盖"""
        monkeypatch.setenv("RISK_MAX_SINGLE_POSITION_RATIO", "0.15")
        monkeypatch.setenv("RISK_STOP_LOSS_THRESHOLD", "-0.10")
        monkeypatch.setenv("RISK_MAX_CONCURRENT_POSITIONS", "12")

        config = RiskLimits.from_env(prefix="RISK_")

        assert config.MAX_SINGLE_POSITION_RATIO == 0.15
        assert config.STOP_LOSS_THRESHOLD == -0.10
        assert config.MAX_CONCURRENT_POSITIONS == 12
        # 未覆盖的保持默认值
        assert config.MAX_SECTOR_CONCENTRATION == 0.40

    def test_production_config_example(self):
        """测试生产环境更保守的配置"""
        # 生产环境可能使用更严格的风控参数
        prod_config = RiskLimits(
            MAX_SINGLE_POSITION_RATIO=0.15,  # 从 20% 降到 15%
            STOP_LOSS_THRESHOLD=-0.06,        # 从 -8% 提到 -6%
            MAX_DAILY_DRAWDOWN=0.03           # 从 5% 降到 3%
        )

        is_valid, errors = prod_config.validate()
        assert is_valid, f"Production config validation failed: {errors}"

        assert prod_config.MAX_SINGLE_POSITION_RATIO == 0.15
        assert prod_config.STOP_LOSS_THRESHOLD == -0.06
        assert prod_config.MAX_DAILY_DRAWDOWN == 0.03

    def test_all_fields_have_types(self):
        """测试所有字段都有类型注解"""
        from dataclasses import fields

        for field in fields(RiskLimits):
            assert field.type is not None, f"Field {field.name} missing type annotation"

    def test_comprehensive_validation_error_messages(self):
        """测试验证错误消息包含有用信息"""
        config = RiskLimits(
            MAX_SINGLE_POSITION_RATIO=1.5,  # 错误
            STOP_LOSS_THRESHOLD=0.05,        # 错误
            MAX_CONCURRENT_POSITIONS=-5      # 错误
        )

        is_valid, errors = config.validate()
        assert not is_valid
        assert len(errors) >= 3

        # 验证错误消息包含参数名和当前值
        error_text = " ".join(errors)
        assert "MAX_SINGLE_POSITION_RATIO" in error_text
        assert "1.5" in error_text
        assert "STOP_LOSS_THRESHOLD" in error_text
        assert "0.05" in error_text
        assert "MAX_CONCURRENT_POSITIONS" in error_text
