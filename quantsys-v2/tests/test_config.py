"""
测试 core.config 模块
"""
import pytest
from domain.quantlib.core.config import CHART_KLINE_LIMIT, CHART_KLINE_MAX_LIMIT


class TestConfig:
    """测试配置常量"""

    def test_chart_kline_limit_exists(self):
        """测试 CHART_KLINE_LIMIT 常量存在"""
        assert CHART_KLINE_LIMIT is not None

    def test_chart_kline_limit_is_integer(self):
        """测试 CHART_KLINE_LIMIT 是整数"""
        assert isinstance(CHART_KLINE_LIMIT, int)

    def test_chart_kline_limit_is_positive(self):
        """测试 CHART_KLINE_LIMIT 是正数"""
        assert CHART_KLINE_LIMIT > 0

    def test_chart_kline_limit_reasonable_value(self):
        """测试 CHART_KLINE_LIMIT 值合理（通常在10-100之间）"""
        assert 10 <= CHART_KLINE_LIMIT <= 100

    def test_chart_kline_max_limit_exists(self):
        """测试 CHART_KLINE_MAX_LIMIT 常量存在"""
        assert CHART_KLINE_MAX_LIMIT is not None

    def test_chart_kline_max_limit_is_integer(self):
        """测试 CHART_KLINE_MAX_LIMIT 是整数"""
        assert isinstance(CHART_KLINE_MAX_LIMIT, int)

    def test_chart_kline_max_limit_is_positive(self):
        """测试 CHART_KLINE_MAX_LIMIT 是正数"""
        assert CHART_KLINE_MAX_LIMIT > 0

    def test_chart_kline_max_limit_greater_than_default(self):
        """测试 CHART_KLINE_MAX_LIMIT 大于 CHART_KLINE_LIMIT"""
        assert CHART_KLINE_MAX_LIMIT >= CHART_KLINE_LIMIT

    def test_chart_kline_max_limit_reasonable_value(self):
        """测试 CHART_KLINE_MAX_LIMIT 值合理（通常在50-500之间）"""
        assert 50 <= CHART_KLINE_MAX_LIMIT <= 500

    def test_config_values_match_expected(self):
        """测试配置值符合预期"""
        # 根据实际配置验证
        assert CHART_KLINE_LIMIT == 30
        assert CHART_KLINE_MAX_LIMIT == 500


class TestConfigUsage:
    """测试配置常量的使用场景"""

    def test_limit_calculation(self):
        """测试限制计算逻辑"""
        # 模拟 strategy_code_service.py 中的使用
        data_length = 50
        chart_limit = min(CHART_KLINE_LIMIT, data_length)
        assert chart_limit == 30

        data_length = 20
        chart_limit = min(CHART_KLINE_LIMIT, data_length)
        assert chart_limit == 20

    def test_max_limit_enforcement(self):
        """测试最大限制强制执行"""
        # 用户请求的限制
        user_limit = 600
        actual_limit = min(user_limit, CHART_KLINE_MAX_LIMIT)
        assert actual_limit == 500

        user_limit = 260
        actual_limit = min(user_limit, CHART_KLINE_MAX_LIMIT)
        assert actual_limit == 260

    def test_default_limit_when_no_user_input(self):
        """测试没有用户输入时使用默认限制"""
        user_limit = None
        actual_limit = user_limit or CHART_KLINE_LIMIT
        assert actual_limit == 30

    def test_limit_range_validation(self):
        """测试限制范围验证"""
        def validate_limit(limit):
            """验证限制值是否在有效范围内"""
            if limit is None:
                return CHART_KLINE_LIMIT
            if limit < 1:
                return CHART_KLINE_LIMIT
            if limit > CHART_KLINE_MAX_LIMIT:
                return CHART_KLINE_MAX_LIMIT
            return limit

        assert validate_limit(None) == 30
        assert validate_limit(0) == 30
        assert validate_limit(-10) == 30
        assert validate_limit(50) == 50
        assert validate_limit(600) == 500


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
