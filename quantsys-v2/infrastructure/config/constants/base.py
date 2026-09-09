"""配置基类

提供配置类的基础功能：
1. 不可变性 (frozen dataclass)
2. 环境变量覆盖
3. 验证机制
4. 导出功能
"""

from typing import Any, Dict, Type, TypeVar
from dataclasses import dataclass, fields
import os

T = TypeVar('T', bound='ConfigBase')


@dataclass(frozen=True)
class ConfigBase:
    """配置基类

    所有配置类应继承此类，并使用 @dataclass(frozen=True) 装饰器。

    特性:
    1. 不可变 (frozen=True) - 配置一旦创建不可修改
    2. 支持环境变量覆盖
    3. 提供验证机制
    4. 提供导出功能

    使用示例:
        @dataclass(frozen=True)
        class MyConfig(ConfigBase):
            MAX_VALUE: float = 0.20
            MIN_VALUE: int = 5

            def validate(self) -> tuple[bool, list[str]]:
                errors = []
                if self.MAX_VALUE <= 0:
                    errors.append("MAX_VALUE 必须大于 0")
                return len(errors) == 0, errors

        # 使用默认值
        config = MyConfig()

        # 从环境变量覆盖
        # 环境变量: MY_MAX_VALUE=0.30
        config = MyConfig.from_env(prefix="MY_")
    """

    @classmethod
    def from_env(cls: Type[T], prefix: str = "") -> T:
        """从环境变量创建配置实例

        Args:
            prefix: 环境变量前缀，例如 "RISK_" 会匹配 RISK_MAX_VALUE

        Returns:
            配置实例，环境变量中的值会覆盖默认值

        示例:
            # 环境变量: RISK_MAX_SINGLE_POSITION_RATIO=0.15
            config = RiskLimits.from_env(prefix="RISK_")
            # config.MAX_SINGLE_POSITION_RATIO == 0.15
        """
        kwargs = {}

        for field in fields(cls):
            # 构造环境变量名: prefix + 字段名大写
            env_key = f"{prefix}{field.name.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                # 根据字段类型转换
                field_type = field.type

                # 处理 Optional 类型
                if hasattr(field_type, '__origin__'):
                    # typing.Optional[X] 的 __args__[0] 是 X
                    if field_type.__origin__ is type(None):
                        field_type = field_type.__args__[0]

                try:
                    if field_type == int:
                        kwargs[field.name] = int(env_value)
                    elif field_type == float:
                        kwargs[field.name] = float(env_value)
                    elif field_type == bool:
                        kwargs[field.name] = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif field_type == str:
                        kwargs[field.name] = env_value
                    else:
                        # 其他类型保持字符串
                        kwargs[field.name] = env_value
                except (ValueError, AttributeError) as e:
                    # 类型转换失败，跳过此字段
                    import warnings
                    warnings.warn(
                        f"Failed to convert env var {env_key}={env_value} to {field_type}: {e}"
                    )
                    continue

        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典

        Returns:
            包含所有字段名和值的字典
        """
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def validate(self) -> tuple[bool, list[str]]:
        """验证配置合法性

        子类应重写此方法添加自定义验证逻辑。

        Returns:
            (is_valid, errors)
            - is_valid: 配置是否合法
            - errors: 错误信息列表

        示例:
            def validate(self) -> tuple[bool, list[str]]:
                errors = []

                if not 0 < self.MAX_RATIO <= 1.0:
                    errors.append(f"MAX_RATIO 必须在 (0, 1] 范围内，当前: {self.MAX_RATIO}")

                if self.MIN_VALUE >= self.MAX_VALUE:
                    errors.append("MIN_VALUE 必须小于 MAX_VALUE")

                return len(errors) == 0, errors
        """
        return True, []
