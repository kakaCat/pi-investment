"""
IndicatorStrategy 执行引擎

负责执行信号驱动的策略代码，生成买卖信号。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .code_validator import CodeValidator
from .param_parser import ParamParser


@dataclass
class IndicatorStrategyResult:
    """IndicatorStrategy 执行结果"""

    signals: pd.DataFrame  # 包含 buy/sell 列的信号 DataFrame
    output: Optional[Dict[str, Any]] = None  # 图表输出（可选）
    params_used: Dict[str, Any] = field(default_factory=dict)  # 实际使用的参数
    risk_config: Dict[str, Any] = field(default_factory=dict)  # 风控配置
    metadata: Dict[str, Any] = field(default_factory=dict)  # 策略元数据


class IndicatorStrategyExecutor:
    """IndicatorStrategy 执行引擎"""

    def __init__(self):
        self.code_validator = CodeValidator()
        self.param_parser = ParamParser()

    def execute(
        self,
        code: str,
        klines: List[Dict],
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorStrategyResult:
        """
        执行 IndicatorStrategy 代码

        Args:
            code: 策略代码字符串
            klines: K线数据列表，每个元素包含 open, high, low, close, volume 等字段
            params: 用户传入的参数（可选），会覆盖代码中的默认值

        Returns:
            IndicatorStrategyResult 执行结果

        Raises:
            ValueError: 代码验证失败或执行失败

        Example:
            >>> executor = IndicatorStrategyExecutor()
            >>> code = '''
            ... df['ma5'] = df['close'].rolling(5).mean()
            ... df['ma20'] = df['close'].rolling(20).mean()
            ... df['buy'] = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))
            ... df['sell'] = (df['ma5'] < df['ma20']) & (df['ma5'].shift(1) >= df['ma20'].shift(1))
            ... '''
            >>> result = executor.execute(code, klines, {})
        """
        # 1. 验证代码安全性
        self.code_validator.validate(code, code_type='indicator')

        # 2. 解析参数和配置
        parsed_params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 3. 合并参数（用户传入覆盖默认值）
        params_used = {}
        for param_def in parsed_params:
            param_name = param_def['name']
            # 优先使用用户传入的参数，否则使用默认值
            if params and param_name in params:
                params_used[param_name] = params[param_name]
            else:
                params_used[param_name] = param_def['default']

        # 4. 转换 K线数据为 DataFrame
        df = self._klines_to_dataframe(klines)

        # 5. 创建沙箱环境
        namespace = self._create_sandbox_namespace(df, params_used)

        # 6. 执行代码
        try:
            exec(code, namespace)
        except KeyError as e:
            # KeyError 通常表示策略代码访问了不存在的列
            available_cols = list(namespace['df'].columns)
            raise ValueError(
                f"策略代码执行失败: 列 {str(e)} 不存在。"
                f"可用列: {', '.join(available_cols)}"
            )
        except Exception as e:
            raise ValueError(f"策略代码执行失败: {type(e).__name__}: {str(e)}")

        # 6.5 🔧 兼容旧版 calc_indicator(ctx) 包装格式
        # 如果代码定义了 calc_indicator 函数，且 df 没有 buy/sell 列，自动调用
        calc_func = namespace.get('calc_indicator')
        if callable(calc_func) and 'buy' not in namespace.get('df', pd.DataFrame()).columns and 'sell' not in namespace.get('df', pd.DataFrame()).columns:
            ctx = type('Ctx', (), {
                'kline_df': namespace.get('df'),
                'params': namespace.get('params', {}),
            })()
            calc_indicator_df = calc_func(ctx)
            if calc_indicator_df is not None:
                namespace['df'] = calc_indicator_df

        # 7. 获取执行后的 DataFrame
        result_df = namespace.get('df')
        if result_df is None:
            raise ValueError("策略代码未返回 df 变量")

        # 8. 验证信号列
        self._validate_signals(result_df)

        # 9. 提取 output（可选）
        output = namespace.get('output', None)

        # 10. 提取元数据
        metadata = self._extract_metadata(code, namespace)

        # 11. 返回结果
        return IndicatorStrategyResult(
            signals=result_df,
            output=output,
            params_used=params_used,
            risk_config=risk_config,
            metadata=metadata
        )

    def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        """
        将 K线数据列表转换为 DataFrame

        Args:
            klines: K线数据列表

        Returns:
            pd.DataFrame
        """
        # 检查 klines 是否为空（兼容 list 和 DataFrame）
        if klines is None:
            raise ValueError("K线数据不能为空")

        # 如果是 Polars DataFrame，转换为 list of dicts
        try:
            import polars as pl
            if isinstance(klines, pl.DataFrame):
                if klines.is_empty():
                    raise ValueError("K线数据不能为空")
                klines = klines.to_dicts()
        except ImportError:
            pass

        # 如果是 list，检查是否为空
        if isinstance(klines, list) and len(klines) == 0:
            raise ValueError("K线数据不能为空")

        # 记录输入的列
        import logging
        logger = logging.getLogger(__name__)
        input_cols = list(klines[0].keys()) if klines else []
        logger.debug(f"_klines_to_dataframe 输入列: {input_cols}")

        df = pd.DataFrame(klines)

        # 确保必需的列存在
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"K线数据缺少必需的列: {', '.join(missing_columns)}")

        # 转换数值类型
        for col in required_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 如果有日期列，转换为 datetime（支持 'trade_date' 和 'date'）
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')

        logger.debug(f"_klines_to_dataframe 输出列: {list(df.columns)}")

        return df

    def _create_sandbox_namespace(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建沙箱执行环境

        Args:
            df: K线 DataFrame
            params: 参数字典

        Returns:
            沙箱命名空间字典
        """
        # 安全的内置函数列表
        safe_builtins = {
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sum': sum,
            'max': max,
            'min': min,
            'abs': abs,
            'round': round,
            'print': print,  # 允许 print 用于调试
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'sorted': sorted,
            'reversed': reversed,
            'any': any,
            'all': all,
            # 对象属性访问函数（pandas DataFrame 操作需要）
            'getattr': getattr,
            'setattr': setattr,
            'hasattr': hasattr,
        }

        # 创建沙箱命名空间
        namespace = {
            'df': df.copy(),  # 传入 DataFrame 的副本，避免修改原始数据
            'params': params.copy(),  # 传入参数的副本
            'pd': pd,  # pandas 库
            'np': np,  # numpy 库
            '__builtins__': safe_builtins,  # 受限的内置函数
        }

        return namespace

    def _validate_signals(self, df: pd.DataFrame) -> None:
        """
        验证信号列存在且有效（支持分批信号）

        Args:
            df: 执行后的 DataFrame

        Raises:
            ValueError: 信号列不存在或无效
        """
        # 检查是否有分批信号
        has_tiered_buy = any(f'buy_tier{i}' in df.columns for i in [1, 2, 3])
        has_tiered_sell = any(f'sell_tier{i}' in df.columns for i in [1, 2, 3])

        # 检查旧格式信号
        has_simple_buy = 'buy' in df.columns
        has_simple_sell = 'sell' in df.columns

        # 至少要有一种买入信号
        if not has_simple_buy and not has_tiered_buy:
            raise ValueError("策略代码未生成 'buy' 或 'buy_tier1/2/3' 信号列")

        # 至少要有一种卖出信号
        if not has_simple_sell and not has_tiered_sell:
            raise ValueError("策略代码未生成 'sell' 或 'sell_tier1/2/3' 信号列")

        # 验证简单信号的类型
        if has_simple_buy and df['buy'].dtype != bool:
            try:
                df['buy'] = df['buy'].astype(bool)
            except Exception:
                raise ValueError("'buy' 信号列必须是布尔类型")

        if has_simple_sell and df['sell'].dtype != bool:
            try:
                df['sell'] = df['sell'].astype(bool)
            except Exception:
                raise ValueError("'sell' 信号列必须是布尔类型")

        # 验证分批信号的类型
        for tier in [1, 2, 3]:
            buy_col = f'buy_tier{tier}'
            sell_col = f'sell_tier{tier}'

            if buy_col in df.columns and df[buy_col].dtype != bool:
                try:
                    df[buy_col] = df[buy_col].astype(bool)
                except Exception:
                    raise ValueError(f"'{buy_col}' 信号列必须是布尔类型")

            if sell_col in df.columns and df[sell_col].dtype != bool:
                try:
                    df[sell_col] = df[sell_col].astype(bool)
                except Exception:
                    raise ValueError(f"'{sell_col}' 信号列必须是布尔类型")

        # 检查是否至少有一个信号（简单信号或分批信号）
        has_any_signal = False

        if has_simple_buy and df['buy'].any():
            has_any_signal = True
        if has_simple_sell and df['sell'].any():
            has_any_signal = True

        for tier in [1, 2, 3]:
            if f'buy_tier{tier}' in df.columns and df[f'buy_tier{tier}'].any():
                has_any_signal = True
            if f'sell_tier{tier}' in df.columns and df[f'sell_tier{tier}'].any():
                has_any_signal = True

        if not has_any_signal:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("策略未生成任何买卖信号（所有信号均为 False）")

    def _extract_metadata(
        self,
        code: str,
        namespace: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提取策略元数据

        从代码中提取策略名称、描述等元数据。
        优先从命名空间中获取变量，如果不存在则从注释中提取。

        Args:
            code: 策略代码字符串
            namespace: 执行后的命名空间

        Returns:
            元数据字典
        """
        metadata = {}

        # 从命名空间中提取元数据变量
        metadata_vars = {
            'name': ['my_indicator_name', 'indicator_name', 'strategy_name'],
            'description': ['my_indicator_description', 'indicator_description', 'strategy_description']
        }

        for key, var_names in metadata_vars.items():
            for var_name in var_names:
                if var_name in namespace:
                    metadata[key] = namespace[var_name]
                    break

        # 如果命名空间中没有，尝试从注释中提取
        if 'name' not in metadata:
            # 查找第一个非空注释行作为名称
            for line in code.split('\n'):
                line = line.strip()
                if line.startswith('#') and not line.startswith('#@'):
                    # 移除 # 和多余的 = 符号
                    name = line.lstrip('#').strip().strip('=').strip()
                    if name and len(name) < 100:  # 合理的名称长度
                        metadata['name'] = name
                        break

        return metadata
