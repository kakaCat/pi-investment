"""
策略因子注入器

负责向K线数据注入104个技术因子，供策略代码使用
"""

import structlog
import numpy as np
import pandas as pd
from typing import Dict, List

# 导入因子计算器（6个核心类）
from domain.quantlib.factors.momentum import MomentumFactors
from domain.quantlib.factors.trend import TrendFactors
from domain.quantlib.factors.volatility import VolatilityFactors
from domain.quantlib.factors.volume import VolumeFactors
from domain.quantlib.factors.moving_average import MovingAverageFactors
from domain.quantlib.factors.reversal import ReversalFactors

# 导入需要 TA-Lib 的因子（可选）
try:
    from domain.quantlib.factors.advanced import AdvancedFactors
    from domain.quantlib.factors.cycle import CycleFactors
    from domain.quantlib.factors.pattern_recognition import PatternRecognitionFactors
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

# 导入其他因子
try:
    from domain.quantlib.factors.other import OtherFactors
    OTHER_FACTORS_AVAILABLE = True
except ImportError:
    OTHER_FACTORS_AVAILABLE = False

logger = structlog.get_logger(__name__)


class StrategyFactorInjector:
    """策略因子注入服务"""

    def __init__(self):
        # 核心因子（6个类别，58个因子）- 始终可用
        self.momentum_factors = MomentumFactors()
        self.trend_factors = TrendFactors()
        self.volatility_factors = VolatilityFactors()
        self.volume_factors = VolumeFactors()
        self.ma_factors = MovingAverageFactors()
        self.reversal_factors = ReversalFactors()

        # 可选因子（4个类别，70个因子）- 需要 TA-Lib
        if TALIB_AVAILABLE:
            self.advanced_factors = AdvancedFactors()
            self.cycle_factors = CycleFactors()
            self.pattern_factors = PatternRecognitionFactors()
        else:
            self.advanced_factors = None
            self.cycle_factors = None
            self.pattern_factors = None

        if OTHER_FACTORS_AVAILABLE:
            self.other_factors = OtherFactors()
        else:
            self.other_factors = None

        # 统计可用因子数量
        base_factors = 58  # 6个核心类
        talib_factors = 47 if TALIB_AVAILABLE else 0  # 高级17 + 周期6 + 形态24
        other_factors = 23 if OTHER_FACTORS_AVAILABLE else 0  # 其他23
        self.total_factors = base_factors + talib_factors + other_factors

        logger.info(f"因子注入器初始化完成（{self.total_factors}个因子可用）")

    def inject_all_factors(self, klines: List[Dict]) -> List[Dict]:
        """
        注入所有可用因子到K线数据

        Args:
            klines: K线数据列表

        Returns:
            增强后的K线数据（包含所有因子）
        """
        try:
            # 转换为 DataFrame
            df = pd.DataFrame(klines)

            # 确保数值类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 注入各类因子
            df = self._inject_momentum_factors(df, klines)
            df = self._inject_trend_factors(df, klines)
            df = self._inject_volatility_factors(df, klines)
            df = self._inject_volume_factors(df, klines)
            df = self._inject_ma_factors(df, klines)
            df = self._inject_reversal_factors(df, klines)

            # 可选因子（需要 TA-Lib）
            if TALIB_AVAILABLE:
                df = self._inject_advanced_factors(df, klines)
                df = self._inject_cycle_factors(df, klines)
                df = self._inject_pattern_factors(df, klines)

            # 其他因子
            if OTHER_FACTORS_AVAILABLE:
                df = self._inject_other_factors(df, klines)

            # 向后兼容：确保原有13个因子名称存在
            self._ensure_backward_compatibility(df)

            logger.info(f"技术指标注入完成: 新增 {len([c for c in df.columns if c not in klines[0].keys()])} 个因子列")

            return df.to_dict('records')

        except Exception as e:
            logger.error(f"注入技术指标失败: {e}", exc_info=True)
            return klines

    def _inject_momentum_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入动量因子 (15个)"""
        try:
            supported_methods = self.momentum_factors.get_supported_methods()
            logger.debug(f"计算动量因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.momentum_factors, method):
                        result = getattr(self.momentum_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        logger.warning(f"动量因子方法不存在: {method}")
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算动量因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入动量因子失败: {e}")
            return df

    def _inject_trend_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入趋势因子 (20个)"""
        try:
            supported_methods = self.trend_factors.get_supported_methods()
            logger.debug(f"计算趋势因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.trend_factors, method):
                        result = getattr(self.trend_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        logger.warning(f"趋势因子方法不存在: {method}")
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算趋势因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入趋势因子失败: {e}")
            return df

    def _inject_volatility_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入波动率因子 (10个)"""
        try:
            supported_methods = self.volatility_factors.get_supported_methods()
            logger.debug(f"计算波动率因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.volatility_factors, method):
                        result = getattr(self.volatility_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算波动率因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入波动率因子失败: {e}")
            return df

    def _inject_volume_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入成交量因子 (8个)"""
        try:
            supported_methods = self.volume_factors.get_supported_methods()
            logger.debug(f"计算成交量因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.volume_factors, method):
                        result = getattr(self.volume_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算成交量因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入成交量因子失败: {e}")
            return df

    def _inject_ma_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入移动平均因子 (11个)"""
        try:
            supported_methods = self.ma_factors.get_supported_methods()
            logger.debug(f"计算移动平均因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.ma_factors, method):
                        result = getattr(self.ma_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算移动平均因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入移动平均因子失败: {e}")
            return df

    def _inject_reversal_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入反转因子 (4个)"""
        try:
            supported_methods = self.reversal_factors.get_supported_methods()
            logger.debug(f"计算反转因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.reversal_factors, method):
                        result = getattr(self.reversal_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算反转因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入反转因子失败: {e}")
            return df

    def _inject_advanced_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入高级因子 (17个, 需要 TA-Lib)"""
        if not self.advanced_factors:
            return df

        try:
            supported_methods = self.advanced_factors.get_supported_methods()
            logger.debug(f"计算高级因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.advanced_factors, method):
                        result = getattr(self.advanced_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算高级因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入高级因子失败: {e}")
            return df

    def _inject_cycle_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入周期因子 (6个, 需要 TA-Lib)"""
        if not self.cycle_factors:
            return df

        try:
            supported_methods = self.cycle_factors.get_supported_methods()
            logger.debug(f"计算周期因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.cycle_factors, method):
                        result = getattr(self.cycle_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算周期因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入周期因子失败: {e}")
            return df

    def _inject_pattern_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入形态识别因子 (24个, 需要 TA-Lib)"""
        if not self.pattern_factors:
            return df

        try:
            supported_methods = self.pattern_factors.get_supported_methods()
            logger.debug(f"计算形态因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.pattern_factors, method):
                        result = getattr(self.pattern_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算形态因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入形态因子失败: {e}")
            return df

    def _inject_other_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入其他因子 (23个)"""
        if not self.other_factors:
            return df

        try:
            supported_methods = self.other_factors.get_supported_methods()
            logger.debug(f"计算其他因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    if hasattr(self.other_factors, method):
                        result = getattr(self.other_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            df[method] = result['value']
                        else:
                            df[method] = result
                    else:
                        df[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算其他因子 {method} 失败: {e}")
                    df[method] = np.nan
            return df
        except Exception as e:
            logger.error(f"注入其他因子失败: {e}")
            return df

    def _ensure_backward_compatibility(self, df: pd.DataFrame):
        """确保向后兼容：原有13个因子名称映射"""
        # RSI 映射
        if 'rsi14' in df.columns and 'rsi' not in df.columns:
            df['rsi'] = df['rsi14']

        # MACD 映射
        if 'macd' in df.columns and 'macd_line' not in df.columns:
            df['macd_line'] = df['macd']

        # 均线映射
        for period in [5, 10, 20, 60]:
            col_name = f'ma{period}'
            if col_name in df.columns and f'sma{period}' not in df.columns:
                df[f'sma{period}'] = df[col_name]
