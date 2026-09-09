"""测试配置基类功能"""

import pytest
import os
from dataclasses import dataclass
from infrastructure.config.constants.base import ConfigBase


@dataclass(frozen=True)
class TestConfig(ConfigBase):
    """测试用配置类"""
    INT_VALUE: int = 10
    FLOAT_VALUE: float = 0.5
    BOOL_VALUE: bool = True
    STR_VALUE: str = "test"

    def validate(self) -> tuple[bool, list[str]]:
        errors = []
        if self.INT_VALUE <= 0:
            errors.append("INT_VALUE must be positive")
        if not 0 < self.FLOAT_VALUE < 1:
            errors.append("FLOAT_VALUE must be in (0, 1)")
        return len(errors) == 0, errors


class TestConfigBase:
    """测试 ConfigBase 基类"""

    def test_default_values(self):
        """测试默认值"""
        config = TestConfig()
        assert config.INT_VALUE == 10
        assert config.FLOAT_VALUE == 0.5
        assert config.BOOL_VALUE is True
        assert config.STR_VALUE == "test"

    def test_immutable(self):
        """测试不可变性"""
        config = TestConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.INT_VALUE = 20  # type: ignore

    def test_to_dict(self):
        """测试导出为字典"""
        config = TestConfig()
        d = config.to_dict()
        assert d == {
            'INT_VALUE': 10,
            'FLOAT_VALUE': 0.5,
            'BOOL_VALUE': True,
            'STR_VALUE': 'test'
        }

    def test_validate_success(self):
        """测试验证成功"""
        config = TestConfig()
        is_valid, errors = config.validate()
        assert is_valid
        assert len(errors) == 0

    def test_validate_failure(self):
        """测试验证失败"""
        config = TestConfig(INT_VALUE=-5, FLOAT_VALUE=1.5)
        is_valid, errors = config.validate()
        assert not is_valid
        assert len(errors) == 2
        assert any("INT_VALUE" in err for err in errors)
        assert any("FLOAT_VALUE" in err for err in errors)

    def test_from_env_int(self, monkeypatch):
        """测试从环境变量加载整数"""
        monkeypatch.setenv("TEST_INT_VALUE", "20")
        config = TestConfig.from_env(prefix="TEST_")
        assert config.INT_VALUE == 20

    def test_from_env_float(self, monkeypatch):
        """测试从环境变量加载浮点数"""
        monkeypatch.setenv("TEST_FLOAT_VALUE", "0.75")
        config = TestConfig.from_env(prefix="TEST_")
        assert config.FLOAT_VALUE == 0.75

    def test_from_env_bool_true(self, monkeypatch):
        """测试从环境变量加载布尔值（true）"""
        for val in ['true', 'True', '1', 'yes', 'YES', 'on', 'ON']:
            monkeypatch.setenv("TEST_BOOL_VALUE", val)
            config = TestConfig.from_env(prefix="TEST_")
            assert config.BOOL_VALUE is True, f"Failed for value: {val}"

    def test_from_env_bool_false(self, monkeypatch):
        """测试从环境变量加载布尔值（false）"""
        for val in ['false', 'False', '0', 'no', 'NO', 'off', 'OFF']:
            monkeypatch.setenv("TEST_BOOL_VALUE", val)
            config = TestConfig.from_env(prefix="TEST_")
            assert config.BOOL_VALUE is False, f"Failed for value: {val}"

    def test_from_env_string(self, monkeypatch):
        """测试从环境变量加载字符串"""
        monkeypatch.setenv("TEST_STR_VALUE", "custom")
        config = TestConfig.from_env(prefix="TEST_")
        assert config.STR_VALUE == "custom"

    def test_from_env_partial_override(self, monkeypatch):
        """测试部分字段覆盖"""
        monkeypatch.setenv("TEST_INT_VALUE", "30")
        monkeypatch.setenv("TEST_FLOAT_VALUE", "0.8")
        config = TestConfig.from_env(prefix="TEST_")
        assert config.INT_VALUE == 30
        assert config.FLOAT_VALUE == 0.8
        assert config.BOOL_VALUE is True  # 未覆盖，保持默认值
        assert config.STR_VALUE == "test"  # 未覆盖，保持默认值

    def test_from_env_invalid_type(self, monkeypatch):
        """测试环境变量类型转换失败"""
        monkeypatch.setenv("TEST_INT_VALUE", "invalid")
        # 类型转换失败时应使用默认值（发出警告）
        with pytest.warns(UserWarning):
            config = TestConfig.from_env(prefix="TEST_")
        assert config.INT_VALUE == 10  # 保持默认值

    def test_from_env_no_prefix(self, monkeypatch):
        """测试无前缀的环境变量"""
        monkeypatch.setenv("INT_VALUE", "25")
        config = TestConfig.from_env(prefix="")
        assert config.INT_VALUE == 25
