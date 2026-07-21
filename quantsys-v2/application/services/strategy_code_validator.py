"""
策略代码验证器

负责验证用户策略代码的语法正确性、必需函数和信号生成
"""

import re
import structlog
import pandas as pd
from typing import Dict, Optional, List
from domain.quantlib.engine.code_validator import CodeValidator
from domain.quantlib.engine.param_parser import ParamParser

logger = structlog.get_logger(__name__)


class StrategyCodeValidator:
    """策略代码验证服务"""

    def __init__(self):
        self.code_validator = CodeValidator()
        self.param_parser = ParamParser()

    def validate_code(self, code: str, code_type: str) -> Dict:
        """
        验证策略代码

        Args:
            code: 策略代码字符串
            code_type: 策略类型 ('indicator' | 'script' | 'trend_following' | 'mean_reversion' | 'multi_factor')

        Returns:
            验证结果字典
            {
                'valid': True/False,
                'syntax_ok': True/False,
                'has_buy_signal': True/False,
                'has_sell_signal': True/False,
                'params': [...],
                'risk_config': {...},
                'metadata': {...},
                'error': None or str
            }
        """
        try:
            # 1. 语法验证（使用Python内置compile）
            try:
                compile(code, '<string>', 'exec')
                syntax_valid = True
            except SyntaxError as e:
                return {
                    'valid': False,
                    'syntax_ok': False,
                    'error': f'Python 语法错误: {str(e)}'
                }

            # 2. 根据类型进行特定验证
            if code_type == 'indicator':
                result = self._validate_indicator_code(code)
            elif code_type == 'script':
                result = self._validate_script_code(code)
            elif code_type in ('trend_following', 'mean_reversion', 'multi_factor'):
                result = self._validate_template_code(code, code_type)
            else:
                raise ValueError(f"不支持的策略类型: {code_type}")

            result['valid'] = result.get('syntax_ok', False)
            return result

        except Exception as e:
            logger.error(f"代码验证失败: {e}")
            return {
                'valid': False,
                'syntax_ok': False,
                'error': str(e)
            }

    def _validate_indicator_code(self, code: str) -> Dict:
        """验证 Indicator 策略代码"""
        # 检查必需的函数
        if 'def calc_indicator(ctx)' not in code and 'def calc_indicator (ctx)' not in code:
            raise ValueError("Indicator 策略必须定义 calc_indicator(ctx) 函数")

        # 解析参数和配置
        params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 提取元数据
        metadata = {}
        match = re.search(r'my_indicator_name\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['name'] = match.group(1)
        match = re.search(r'my_indicator_description\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['description'] = match.group(1)

        # 检查是否有分批信号
        has_tiered_buy = any(f"df['buy_tier{i}']" in code or f'df["buy_tier{i}"]' in code
                             for i in [1, 2, 3])
        has_tiered_sell = any(f"df['sell_tier{i}']" in code or f'df["sell_tier{i}"]' in code
                              for i in [1, 2, 3])

        # 检查旧格式信号
        has_simple_buy = "df['buy']" in code or 'df["buy"]' in code
        has_simple_sell = "df['sell']" in code or 'df["sell"]' in code

        # 不能混合使用
        if (has_simple_buy and has_tiered_buy) or (has_simple_sell and has_tiered_sell):
            raise ValueError("不能同时使用简单信号（buy/sell）和分批信号（buy_tier1/sell_tier1）")

        # 至少要有一种信号
        has_buy = has_simple_buy or has_tiered_buy
        has_sell = has_simple_sell or has_tiered_sell

        return {
            'syntax_ok': True,
            'has_buy_signal': has_buy,
            'has_sell_signal': has_sell,
            'is_tiered': has_tiered_buy or has_tiered_sell,  # 新增字段
            'params': params,
            'risk_config': risk_config,
            'metadata': metadata
        }

    def _validate_script_code(self, code: str) -> Dict:
        """验证 ScriptStrategy 代码"""
        # 检查必需的函数
        has_on_init = 'def on_init(ctx)' in code or 'def on_init (ctx)' in code
        has_on_bar = 'def on_bar(ctx, bar)' in code or 'def on_bar (ctx, bar)' in code

        if not has_on_init:
            raise ValueError("ScriptStrategy 必须定义 on_init(ctx) 函数")
        if not has_on_bar:
            raise ValueError("ScriptStrategy 必须定义 on_bar(ctx, bar) 函数")

        # 解析参数和配置
        params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 提取元数据
        metadata = {}
        match = re.search(r'strategy_name\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['name'] = match.group(1)
        match = re.search(r'strategy_description\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['description'] = match.group(1)

        return {
            'syntax_ok': True,
            'has_on_init': has_on_init,
            'has_on_bar': has_on_bar,
            'params': params,
            'risk_config': risk_config,
            'metadata': metadata
        }

    def _validate_template_code(self, code: str, code_type: str) -> Dict:
        """验证模板策略代码（trend_following, mean_reversion, multi_factor）"""
        # 解析参数和配置
        params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 提取元数据
        metadata = {}
        metadata['template_type'] = code_type

        # 检查是否有分批信号
        has_tiered_buy = any(f"df['buy_tier{i}']" in code or f'df["buy_tier{i}"]' in code
                             for i in [1, 2, 3])
        has_tiered_sell = any(f"df['sell_tier{i}']" in code or f'df["sell_tier{i}"]' in code
                              for i in [1, 2, 3])

        # 检查旧格式信号
        has_simple_buy = "df['buy']" in code or 'df["buy"]' in code
        has_simple_sell = "df['sell']" in code or 'df["sell"]' in code

        # 不能混合使用
        if (has_simple_buy and has_tiered_buy) or (has_simple_sell and has_tiered_sell):
            raise ValueError("不能同时使用简单信号（buy/sell）和分批信号（buy_tier1/sell_tier1）")

        # 至少要有一种信号
        has_buy = has_simple_buy or has_tiered_buy
        has_sell = has_simple_sell or has_tiered_sell

        return {
            'syntax_ok': True,
            'has_buy_signal': has_buy,
            'has_sell_signal': has_sell,
            'is_tiered': has_tiered_buy or has_tiered_sell,  # 新增字段
            'params': params,
            'risk_config': risk_config,
            'metadata': metadata
        }

    def validate_custom_prices(self, signals_df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        验证自定义价格列的合理性

        Args:
            signals_df: 包含信号和价格列的DataFrame (pandas or polars)

        Returns:
            包含 warnings 和 errors 的字典
            {
                'warnings': [...],  # 警告列表
                'errors': [...]     # 错误列表（阻止策略保存）
            }
        """
        warnings = []
        errors = []

        # 检查必需的OHLC列
        required_cols = ['open', 'high', 'low', 'close']
        missing_cols = [col for col in required_cols if col not in signals_df.columns]
        if missing_cols:
            errors.append(f"缺少必需的价格列: {', '.join(missing_cols)}")
            return {'warnings': warnings, 'errors': errors}

        # 检测DataFrame类型（Polars or Pandas）
        try:
            import polars as pl
            is_polars = isinstance(signals_df, pl.DataFrame)
        except ImportError:
            is_polars = False

        # ========== 规则1：价格在 O/H/L/C 范围内 (WARNING) ==========
        for tier in [1, 2, 3]:
            price_col = f'buy_tier{tier}_price'
            if price_col in signals_df.columns:
                # 买入价不应高于最高价
                if is_polars:
                    invalid_high_count = signals_df.filter(pl.col(price_col) > pl.col('high')).height
                else:
                    invalid_high_count = len(signals_df[signals_df[price_col] > signals_df['high']])

                if invalid_high_count > 0:
                    warnings.append(
                        f"buy_tier{tier}_price > high 在 {invalid_high_count} 行 "
                        f"(可能导致限价单无法成交)"
                    )

                # 买入价不应低于最低价
                if is_polars:
                    invalid_low_count = signals_df.filter(pl.col(price_col) < pl.col('low')).height
                else:
                    invalid_low_count = len(signals_df[signals_df[price_col] < signals_df['low']])

                if invalid_low_count > 0:
                    warnings.append(
                        f"buy_tier{tier}_price < low 在 {invalid_low_count} 行 "
                        f"(可能是限价未成交或数据错误)"
                    )

        # 检查卖出价格列
        for tier in [1, 2, 3]:
            price_col = f'sell_tier{tier}_price'
            if price_col in signals_df.columns:
                # 卖出价不应高于最高价
                if is_polars:
                    invalid_high_count = signals_df.filter(pl.col(price_col) > pl.col('high')).height
                else:
                    invalid_high_count = len(signals_df[signals_df[price_col] > signals_df['high']])

                if invalid_high_count > 0:
                    warnings.append(
                        f"sell_tier{tier}_price > high 在 {invalid_high_count} 行 "
                        f"(可能是限价未成交或数据错误)"
                    )

                # 卖出价不应低于最低价
                if is_polars:
                    invalid_low_count = signals_df.filter(pl.col(price_col) < pl.col('low')).height
                else:
                    invalid_low_count = len(signals_df[signals_df[price_col] < signals_df['low']])

                if invalid_low_count > 0:
                    warnings.append(
                        f"sell_tier{tier}_price < low 在 {invalid_low_count} 行 "
                        f"(可能导致限价单无法成交)"
                    )

        # ========== 规则2：价格偏离 close 超过阈值 (WARNING) ==========
        deviation_threshold = 0.03  # 3%

        for tier in [1, 2, 3]:
            buy_col = f'buy_tier{tier}_price'
            if buy_col in signals_df.columns:
                # 计算偏离度
                if is_polars:
                    deviations = ((pl.col(buy_col) - pl.col('close')).abs() / pl.col('close'))
                    large_dev_df = signals_df.select(deviations.alias('dev')).filter(pl.col('dev') > deviation_threshold)
                    large_dev_count = large_dev_df.height
                    avg_deviation = large_dev_df['dev'].mean() if large_dev_count > 0 else 0
                else:
                    deviations = (signals_df[buy_col] - signals_df['close']).abs() / signals_df['close']
                    large_deviations = deviations[deviations > deviation_threshold]
                    large_dev_count = len(large_deviations)
                    avg_deviation = large_deviations.mean() if large_dev_count > 0 else 0

                if large_dev_count > 0:
                    warnings.append(
                        f"buy_tier{tier}_price 与收盘价偏离超过 {deviation_threshold*100:.0f}% 在 {large_dev_count} 行 "
                        f"(平均偏离 {avg_deviation*100:.1f}%)，回测结果可能偏离实盘"
                    )

        for tier in [1, 2, 3]:
            sell_col = f'sell_tier{tier}_price'
            if sell_col in signals_df.columns:
                # 计算偏离度
                if is_polars:
                    deviations = ((pl.col(sell_col) - pl.col('close')).abs() / pl.col('close'))
                    large_dev_df = signals_df.select(deviations.alias('dev')).filter(pl.col('dev') > deviation_threshold)
                    large_dev_count = large_dev_df.height
                    avg_deviation = large_dev_df['dev'].mean() if large_dev_count > 0 else 0
                else:
                    deviations = (signals_df[sell_col] - signals_df['close']).abs() / signals_df['close']
                    large_deviations = deviations[deviations > deviation_threshold]
                    large_dev_count = len(large_deviations)
                    avg_deviation = large_deviations.mean() if large_dev_count > 0 else 0

                if large_dev_count > 0:
                    warnings.append(
                        f"sell_tier{tier}_price 与收盘价偏离超过 {deviation_threshold*100:.0f}% 在 {large_dev_count} 行 "
                        f"(平均偏离 {avg_deviation*100:.1f}%)，回测结果可能偏离实盘"
                    )

        # ========== 规则3：同时使用 low 买入和 high 卖出 (ERROR) ==========
        # 检测是否同时使用接近最低价买入和接近最高价卖出

        has_low_buy = False
        has_high_sell = False

        # 检查买入价是否接近最低价（low * 1.01 以内）
        for tier in [1, 2, 3]:
            buy_col = f'buy_tier{tier}_price'
            if buy_col in signals_df.columns:
                # 计算买入价与最低价的比率
                if is_polars:
                    near_low_count = signals_df.filter((pl.col(buy_col) / pl.col('low')) <= 1.01).height
                else:
                    buy_to_low_ratio = signals_df[buy_col] / signals_df['low']
                    near_low_count = len(buy_to_low_ratio[buy_to_low_ratio <= 1.01])

                if near_low_count > 0:
                    has_low_buy = True
                    break

        # 检查卖出价是否接近最高价（high * 0.99 以上）
        for tier in [1, 2, 3]:
            sell_col = f'sell_tier{tier}_price'
            if sell_col in signals_df.columns:
                # 计算卖出价与最高价的比率
                if is_polars:
                    near_high_count = signals_df.filter((pl.col(sell_col) / pl.col('high')) >= 0.99).height
                else:
                    sell_to_high_ratio = signals_df[sell_col] / signals_df['high']
                    near_high_count = len(sell_to_high_ratio[sell_to_high_ratio >= 0.99])

                if near_high_count > 0:
                    has_high_sell = True
                    break

        # 如果同时使用最低价买入和最高价卖出，这是严重错误
        if has_low_buy and has_high_sell:
            errors.append(
                "❌ 策略同时以最低价买入和最高价卖出，使用了未来信息，回测结果不可信。"
                "请改用 open/close 或扩大安全边际（如 low*1.03, high*0.97）"
            )

        return {'warnings': warnings, 'errors': errors}
