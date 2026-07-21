"""
代码安全验证器

负责验证用户自定义策略代码的安全性，包括：
- 语法检查
- 禁止的导入模块检查
- 禁止的操作检查
- 策略类型特定的验证
"""

import ast
import re
from typing import Dict, List, Optional


class CodeValidator:
    """代码安全验证器"""

    # 禁止的导入模块
    FORBIDDEN_IMPORTS = [
        'os', 'sys', 'subprocess', 'socket', 'requests',
        'urllib', 'http', 'ftplib', 'smtplib', 'pickle',
        '__import__', 'eval', 'exec', 'compile'
    ]

    # 禁止的内置函数
    FORBIDDEN_BUILTINS = [
        'open', 'file', 'input', 'raw_input',
        'execfile', 'reload', '__import__'
    ]

    def validate(self, code: str, code_type: str) -> Dict[str, any]:
        """
        验证代码安全性

        Args:
            code: 策略代码字符串
            code_type: 策略类型 ('indicator' 或 'script')

        Returns:
            验证结果字典，包含：
            - valid: bool, 是否通过验证
            - errors: List[str], 错误信息列表

        Raises:
            ValueError: 验证失败时抛出异常
        """
        errors = []

        # 1. 语法检查
        try:
            self.check_syntax(code)
        except SyntaxError as e:
            errors.append(f"语法错误: {str(e)}")

        # 2. 检查禁止的导入
        try:
            self.check_forbidden_imports(code)
        except ValueError as e:
            errors.append(str(e))

        # 3. 检查禁止的操作
        try:
            self.check_forbidden_operations(code)
        except ValueError as e:
            errors.append(str(e))

        # 4. 策略类型特定验证
        if code_type == 'indicator':
            try:
                self._validate_indicator_strategy(code)
            except ValueError as e:
                errors.append(str(e))
        elif code_type == 'script':
            try:
                self._validate_script_strategy(code)
            except ValueError as e:
                errors.append(str(e))
        elif code_type in ('trend_following', 'mean_reversion', 'multi_factor'):
            try:
                self._validate_template_strategy(code)
            except ValueError as e:
                errors.append(str(e))
        else:
            errors.append(f"不支持的策略类型: {code_type}")

        # 如果有错误，抛出异常
        if errors:
            raise ValueError("\n".join(errors))

        return {
            'valid': True,
            'errors': []
        }

    def check_syntax(self, code: str) -> None:
        """
        检查代码语法

        Args:
            code: 策略代码字符串

        Raises:
            SyntaxError: 语法错误时抛出
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"第 {e.lineno} 行: {e.msg}")

    def check_forbidden_imports(self, code: str) -> None:
        """
        检查禁止的导入模块

        Args:
            code: 策略代码字符串

        Raises:
            ValueError: 发现禁止的导入时抛出
        """
        # 检查 import xxx 形式
        for forbidden in self.FORBIDDEN_IMPORTS:
            # 匹配 "import xxx" 或 "import xxx as yyy"
            pattern = rf'\bimport\s+{re.escape(forbidden)}\b'
            if re.search(pattern, code):
                raise ValueError(f"禁止导入模块: {forbidden}")

            # 匹配 "from xxx import yyy"
            pattern = rf'\bfrom\s+{re.escape(forbidden)}\s+import\b'
            if re.search(pattern, code):
                raise ValueError(f"禁止导入模块: {forbidden}")

        # 检查动态导入
        if re.search(r'__import__\s*\(', code):
            raise ValueError("禁止使用 __import__ 动态导入")

    def check_forbidden_operations(self, code: str) -> None:
        """
        检查禁止的操作

        Args:
            code: 策略代码字符串

        Raises:
            ValueError: 发现禁止的操作时抛出
        """
        # 检查禁止的内置函数
        for forbidden in self.FORBIDDEN_BUILTINS:
            pattern = rf'\b{re.escape(forbidden)}\s*\('
            if re.search(pattern, code):
                raise ValueError(f"禁止使用函数: {forbidden}")

        # 检查 eval/exec/compile
        dangerous_funcs = ['eval', 'exec', 'compile']
        for func in dangerous_funcs:
            pattern = rf'\b{func}\s*\('
            if re.search(pattern, code):
                raise ValueError(f"禁止使用函数: {func}")

        # 检查文件操作
        file_operations = [
            r'\bopen\s*\(',
            r'\bfile\s*\(',
            r'\.read\s*\(',
            r'\.write\s*\(',
            r'\.readlines\s*\(',
            r'\.writelines\s*\('
        ]
        for pattern in file_operations:
            if re.search(pattern, code):
                raise ValueError("禁止进行文件操作")

    def _validate_indicator_strategy(self, code: str) -> None:
        """
        验证 IndicatorStrategy 特定要求

        Args:
            code: 策略代码字符串

        Raises:
            ValueError: 验证失败时抛出
        """
        # 移除注释行，避免注释掉的代码通过验证
        code_lines = []
        for line in code.split('\n'):
            # 移除以 # 开头的注释行（保留行内注释后的代码）
            stripped = line.strip()
            if not stripped.startswith('#'):
                code_lines.append(line)
        code_without_comments = '\n'.join(code_lines)

        # 检查是否生成 df['buy'] 或 df['buy_tier1/2/3'] 信号
        # 支持多种写法：df['buy'], df["buy"], df.loc[:, 'buy'] 等
        buy_patterns = [
            r"df\s*\[\s*['\"]buy['\"]\s*\]\s*=",  # df['buy'] = 或 df["buy"] =
            r"df\.loc\s*\[.*?,\s*['\"]buy['\"]\s*\]\s*=",  # df.loc[:, 'buy'] =
            r"df\.at\s*\[.*?,\s*['\"]buy['\"]\s*\]\s*=",  # df.at[idx, 'buy'] =
        ]

        # 检查分批买入信号
        tiered_buy_patterns = [
            r"df\s*\[\s*['\"]buy_tier[123]['\"]\s*\]\s*=",
            r"df\.loc\s*\[.*?,\s*['\"]buy_tier[123]['\"]\s*\]\s*=",
        ]

        has_buy = any(re.search(pattern, code_without_comments) for pattern in buy_patterns)
        has_tiered_buy = any(re.search(pattern, code_without_comments) for pattern in tiered_buy_patterns)

        if not has_buy and not has_tiered_buy:
            raise ValueError("IndicatorStrategy 必须生成 df['buy'] 或 df['buy_tier1/2/3'] 信号")

        # 检查是否生成 df['sell'] 或 df['sell_tier1/2/3'] 信号
        # 支持多种写法：df['sell'], df["sell"], df.loc[:, 'sell'] 等
        sell_patterns = [
            r"df\s*\[\s*['\"]sell['\"]\s*\]\s*=",  # df['sell'] = 或 df["sell"] =
            r"df\.loc\s*\[.*?,\s*['\"]sell['\"]\s*\]\s*=",  # df.loc[:, 'sell'] =
            r"df\.at\s*\[.*?,\s*['\"]sell['\"]\s*\]\s*=",  # df.at[idx, 'sell'] =
        ]

        # 检查分批卖出信号
        tiered_sell_patterns = [
            r"df\s*\[\s*['\"]sell_tier[123]['\"]\s*\]\s*=",
            r"df\.loc\s*\[.*?,\s*['\"]sell_tier[123]['\"]\s*\]\s*=",
        ]

        has_sell = any(re.search(pattern, code_without_comments) for pattern in sell_patterns)
        has_tiered_sell = any(re.search(pattern, code_without_comments) for pattern in tiered_sell_patterns)

        if not has_sell and not has_tiered_sell:
            raise ValueError("IndicatorStrategy 必须生成 df['sell'] 或 df['sell_tier1/2/3'] 信号")

    def _validate_script_strategy(self, code: str) -> None:
        """
        验证 ScriptStrategy 特定要求

        Args:
            code: 策略代码字符串

        Raises:
            ValueError: 验证失败时抛出
        """
        # 检查是否定义 on_init 函数
        if not re.search(r'\bdef\s+on_init\s*\(', code):
            raise ValueError("ScriptStrategy 必须定义 on_init 函数")

        # 检查是否定义 on_bar 函数
        if not re.search(r'\bdef\s+on_bar\s*\(', code):
            raise ValueError("ScriptStrategy 必须定义 on_bar 函数")

    def _validate_template_strategy(self, code: str) -> None:
        """
        验证模板策略特定要求（trend_following, mean_reversion, multi_factor）

        Args:
            code: 策略代码字符串

        Raises:
            ValueError: 验证失败时抛出
        """
        # 移除注释行，避免注释掉的代码通过验证
        code_lines = []
        for line in code.split('\n'):
            stripped = line.strip()
            if not stripped.startswith('#'):
                code_lines.append(line)
        code_without_comments = '\n'.join(code_lines)

        # 检查是否生成 df['buy'] 或 df['buy_tier1/2/3'] 信号
        buy_patterns = [
            r"df\s*\[\s*['\"]buy['\"]\s*\]\s*=",
            r"df\.loc\s*\[.*?,\s*['\"]buy['\"]\s*\]\s*=",
            r"df\.at\s*\[.*?,\s*['\"]buy['\"]\s*\]\s*=",
        ]

        tiered_buy_patterns = [
            r"df\s*\[\s*['\"]buy_tier[123]['\"]\s*\]\s*=",
            r"df\.loc\s*\[.*?,\s*['\"]buy_tier[123]['\"]\s*\]\s*=",
        ]

        has_buy = any(re.search(pattern, code_without_comments) for pattern in buy_patterns)
        has_tiered_buy = any(re.search(pattern, code_without_comments) for pattern in tiered_buy_patterns)

        if not has_buy and not has_tiered_buy:
            raise ValueError("模板策略必须生成 df['buy'] 或 df['buy_tier1/2/3'] 信号")

        # 检查是否生成 df['sell'] 或 df['sell_tier1/2/3'] 信号
        sell_patterns = [
            r"df\s*\[\s*['\"]sell['\"]\s*\]\s*=",
            r"df\.loc\s*\[.*?,\s*['\"]sell['\"]\s*\]\s*=",
            r"df\.at\s*\[.*?,\s*['\"]sell['\"]\s*\]\s*=",
        ]

        tiered_sell_patterns = [
            r"df\s*\[\s*['\"]sell_tier[123]['\"]\s*\]\s*=",
            r"df\.loc\s*\[.*?,\s*['\"]sell_tier[123]['\"]\s*\]\s*=",
        ]

        has_sell = any(re.search(pattern, code_without_comments) for pattern in sell_patterns)
        has_tiered_sell = any(re.search(pattern, code_without_comments) for pattern in tiered_sell_patterns)

        if not has_sell and not has_tiered_sell:
            raise ValueError("模板策略必须生成 df['sell'] 或 df['sell_tier1/2/3'] 信号")

    def get_forbidden_imports(self) -> List[str]:
        """获取禁止的导入模块列表"""
        return self.FORBIDDEN_IMPORTS.copy()

    def get_forbidden_builtins(self) -> List[str]:
        """获取禁止的内置函数列表"""
        return self.FORBIDDEN_BUILTINS.copy()
