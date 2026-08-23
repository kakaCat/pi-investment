"""
参数解析器 (ParamParser)

解析策略代码中的参数声明和策略配置注释。
"""

import re
from typing import List, Dict, Any


class ParamParser:
    """策略参数解析器"""

    # 支持的参数类型
    SUPPORTED_TYPES = {'int', 'float', 'str', 'bool'}

    # @param 格式: # @param <name> <type> <default> <description>
    PARAM_PATTERN = re.compile(
        r'#\s*@param\s+(\w+)\s+(int|float|str|bool)\s+(\S+)\s+(.+)',
        re.IGNORECASE
    )

    # @strategy 格式: # @strategy <key> <value>
    STRATEGY_PATTERN = re.compile(
        r'#\s*@strategy\s+(\w+)\s+(.+)',
        re.IGNORECASE
    )

    def parse_params(self, code: str) -> List[Dict[str, Any]]:
        """
        解析 @param 注释

        格式: # @param <name> <type> <default> <description>
        示例: # @param ma_short int 5 短期均线周期

        Args:
            code: 策略代码字符串

        Returns:
            参数列表，每个参数包含 name, type, default, description

        Example:
            >>> parser = ParamParser()
            >>> code = "# @param ma_short int 5 短期均线周期"
            >>> params = parser.parse_params(code)
            >>> params[0]
            {'name': 'ma_short', 'type': 'int', 'default': 5, 'description': '短期均线周期'}
        """
        params = []

        for line in code.split('\n'):
            match = self.PARAM_PATTERN.match(line.strip())
            if match:
                name, param_type, default_str, description = match.groups()

                # 验证参数类型
                if param_type not in self.SUPPORTED_TYPES:
                    raise ValueError(f"不支持的参数类型: {param_type}")

                # 转换默认值
                try:
                    default_value = self._convert_value(default_str, param_type)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"参数 '{name}' 的默认值 '{default_str}' 无法转换为 {param_type}: {e}"
                    )

                params.append({
                    'name': name,
                    'type': param_type,
                    'default': default_value,
                    'description': description.strip()
                })

        return params

    def parse_strategy_config(self, code: str) -> Dict[str, Any]:
        """
        解析 @strategy 注释

        格式: # @strategy <key> <value>
        示例: # @strategy stopLossPct 0.02

        Args:
            code: 策略代码字符串

        Returns:
            策略配置字典

        Example:
            >>> parser = ParamParser()
            >>> code = "# @strategy stopLossPct 0.02\\n# @strategy takeProfitPct 0.05"
            >>> config = parser.parse_strategy_config(code)
            >>> config
            {'stopLossPct': 0.02, 'takeProfitPct': 0.05}
        """
        config = {}

        for line in code.split('\n'):
            match = self.STRATEGY_PATTERN.match(line.strip())
            if match:
                key, value_str = match.groups()

                # 自动推断值类型并转换
                try:
                    value = self._auto_convert_value(value_str.strip())
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"策略配置 '{key}' 的值 '{value_str}' 无法解析: {e}"
                    )

                config[key] = value

        return config

    def _convert_value(self, value_str: str, target_type: str) -> Any:
        """
        将字符串值转换为指定类型

        Args:
            value_str: 值字符串
            target_type: 目标类型 (int, float, str, bool)

        Returns:
            转换后的值
        """
        if target_type == 'int':
            return int(value_str)
        elif target_type == 'float':
            return float(value_str)
        elif target_type == 'str':
            # 移除可能的引号
            return value_str.strip('"\'')
        elif target_type == 'bool':
            # 支持多种布尔值表示
            lower_val = value_str.lower()
            if lower_val in ('true', '1', 'yes', 'on'):
                return True
            elif lower_val in ('false', '0', 'no', 'off'):
                return False
            else:
                raise ValueError(f"无法将 '{value_str}' 转换为布尔值")
        else:
            raise ValueError(f"不支持的类型: {target_type}")

    def _auto_convert_value(self, value_str: str) -> Any:
        """
        自动推断并转换值类型

        优先级: bool > int > float > str

        Args:
            value_str: 值字符串

        Returns:
            转换后的值
        """
        # 尝试布尔值
        lower_val = value_str.lower()
        if lower_val in ('true', 'false', 'yes', 'no', 'on', 'off'):
            return lower_val in ('true', 'yes', 'on')

        # 尝试整数
        try:
            if '.' not in value_str and 'e' not in value_str.lower():
                return int(value_str)
        except ValueError:
            pass

        # 尝试浮点数
        try:
            return float(value_str)
        except ValueError:
            pass

        # 默认为字符串
        return value_str.strip('"\'')
