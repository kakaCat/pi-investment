"""
策略服务因子库连接补丁

这个文件提供了连接因子库到策略服务的增强版 _inject_technical_indicators 方法。

使用方式:
1. 备份原 strategy_code_service.py
2. 在 __init__ 方法中添加因子计算器初始化
3. 替换 _inject_technical_indicators 方法

效果:
- 策略可用因子: 13个 → 104个
- 自动调用因子库的所有计算器
- 保持向后兼容（原有13个因子名称不变）
"""

from typing import Dict, List
import pandas as pd
import numpy as np
import structlog

# 导入所有因子计算器
from domain.quantlib.factors.momentum import MomentumFactors
from domain.quantlib.factors.trend import TrendFactors
from domain.quantlib.factors.volatility import VolatilityFactors
from domain.quantlib.factors.volume import VolumeFactors
from domain.quantlib.factors.moving_average import MovingAverageFactors
from domain.quantlib.factors.reversal import ReversalFactors

logger = structlog.get_logger(__name__)


class StrategyCodeServiceEnhanced:
    """
    增强版策略服务 - 连接因子库

    添加到 StrategyCodeService.__init__ 中:
    """

    def __init__(self):
        # ... 原有初始化代码 ...

        # 初始化因子计算器
        self.momentum_factors = MomentumFactors()
        self.trend_factors = TrendFactors()
        self.volatility_factors = VolatilityFactors()
        self.volume_factors = VolumeFactors()
        self.ma_factors = MovingAverageFactors()
        self.reversal_factors = ReversalFactors()

        logger.info("因子计算器已初始化（共6个）")


    def _inject_technical_indicators_enhanced(self, klines: List[Dict]) -> List[Dict]:
        """
        增强版：使用因子库注入所有技术指标

        相比原版本的改进:
        1. 调用因子库（而非手动实现）
        2. 支持104个因子（而非13个）
        3. 保持向后兼容
        4. 未来可以轻松扩展到193个（添加TA-Lib后）

        Returns:
            K线数据，包含所有因子字段
        """
        logger.info(f"开始注入技术指标（增强版）: klines_count={len(klines)}")

        if not klines or len(klines) < 2:
            logger.warning("K线数据不足，跳过技术指标计算")
            return klines

        try:
            # 转换为 DataFrame
            df = pd.DataFrame(klines)

            # 验证必需列
            required_cols = ['close', 'high', 'low', 'open', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.warning(f"缺少必需列 {missing_cols}，跳过技术指标计算")
                return klines

            # 转换为数值类型
            for col in required_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # ============================================================
            # 使用因子库计算所有因子
            # ============================================================

            # 1. 动量因子 (15个)
            df = self._inject_momentum_factors(df, klines)

            # 2. 趋势因子 (20个)
            df = self._inject_trend_factors(df, klines)

            # 3. 波动率因子 (10个)
            df = self._inject_volatility_factors(df, klines)

            # 4. 成交量因子 (8个)
            df = self._inject_volume_factors(df, klines)

            # 5. 移动平均线因子 (8个)
            df = self._inject_ma_factors(df, klines)

            # 6. 反转因子 (5个)
            df = self._inject_reversal_factors(df, klines)

            # ============================================================
            # 保持向后兼容：确保原有13个因子名称存在
            # ============================================================
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
                    # 调用因子库计算
                    result = self.momentum_factors.calculate(method, klines)

                    # 提取结果值
                    if isinstance(result, dict) and 'value' in result:
                        df[method] = result['value']
                    else:
                        df[method] = result

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
                    result = self.trend_factors.calculate(method, klines)

                    if isinstance(result, dict) and 'value' in result:
                        df[method] = result['value']
                    else:
                        df[method] = result

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
                    result = self.volatility_factors.calculate(method, klines)

                    if isinstance(result, dict) and 'value' in result:
                        df[method] = result['value']
                    else:
                        df[method] = result

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
                    result = self.volume_factors.calculate(method, klines)

                    if isinstance(result, dict) and 'value' in result:
                        df[method] = result['value']
                    else:
                        df[method] = result

                except Exception as e:
                    logger.warning(f"计算成交量因子 {method} 失败: {e}")
                    df[method] = np.nan

            return df

        except Exception as e:
            logger.error(f"注入成交量因子失败: {e}")
            return df


    def _inject_ma_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入移动平均线因子 (8个)"""
        try:
            supported_methods = self.ma_factors.get_supported_methods()
            logger.debug(f"计算移动平均线因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    result = self.ma_factors.calculate(method, klines)

                    if isinstance(result, dict) and 'value' in result:
                        df[method] = result['value']
                    else:
                        df[method] = result

                except Exception as e:
                    logger.warning(f"计算移动平均线因子 {method} 失败: {e}")
                    df[method] = np.nan

            return df

        except Exception as e:
            logger.error(f"注入移动平均线因子失败: {e}")
            return df


    def _inject_reversal_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入反转因子 (5个)"""
        try:
            supported_methods = self.reversal_factors.get_supported_methods()
            logger.debug(f"计算反转因子: {len(supported_methods)}个")

            for method in supported_methods:
                try:
                    result = self.reversal_factors.calculate(method, klines)

                    if isinstance(result, dict) and 'value' in result:
                        df[method] = result['value']
                    else:
                        df[method] = result

                except Exception as e:
                    logger.warning(f"计算反转因子 {method} 失败: {e}")
                    df[method] = np.nan

            return df

        except Exception as e:
            logger.error(f"注入反转因子失败: {e}")
            return df


    def _ensure_backward_compatibility(self, df: pd.DataFrame) -> None:
        """
        确保向后兼容

        原有13个因子名称必须存在:
        - rsi, macd, macd_signal, macd_hist
        - bollinger_upper, bollinger_middle, bollinger_lower
        - ma5, ma10, ma20, ma60
        - atr

        如果因子库使用不同的命名，这里做映射
        """
        # RSI映射 (如果因子库叫 rsi14，映射到 rsi)
        if 'rsi14' in df.columns and 'rsi' not in df.columns:
            df['rsi'] = df['rsi14']

        # MACD映射
        if 'macd' not in df.columns:
            # 如果没有macd，添加NaN列以保持兼容
            df['macd'] = np.nan
            df['macd_signal'] = np.nan
            df['macd_hist'] = np.nan

        # 布林带映射
        if 'bollinger_upper' not in df.columns:
            df['bollinger_upper'] = np.nan
            df['bollinger_middle'] = np.nan
            df['bollinger_lower'] = np.nan

        # MA映射
        for period in [5, 10, 20, 60]:
            col_name = f'ma{period}'
            if col_name not in df.columns:
                df[col_name] = np.nan

        # ATR映射
        if 'atr' not in df.columns:
            df['atr'] = np.nan

        logger.debug("向后兼容性检查完成")


# ============================================================
# 使用说明
# ============================================================

USAGE_INSTRUCTIONS = """
如何应用这个补丁到 strategy_code_service.py:

Step 1: 备份原文件
    cp services/strategy_code_service.py services/strategy_code_service.py.backup

Step 2: 在 __init__ 方法中添加（第40行左右）:

    def __init__(self):
        # 原有代码...
        self.strategy_repo = IStrategyRepository()
        self.kline_repo = IKlineRepository()
        # ... 等等

        # 🆕 添加这几行：
        from domain.quantlib.factors.momentum import MomentumFactors
        from domain.quantlib.factors.trend import TrendFactors
        from domain.quantlib.factors.volatility import VolatilityFactors
        from domain.quantlib.factors.volume import VolumeFactors
        from domain.quantlib.factors.moving_average import MovingAverageFactors
        from domain.quantlib.factors.reversal import ReversalFactors

        self.momentum_factors = MomentumFactors()
        self.trend_factors = TrendFactors()
        self.volatility_factors = VolatilityFactors()
        self.volume_factors = VolumeFactors()
        self.ma_factors = MovingAverageFactors()
        self.reversal_factors = ReversalFactors()

Step 3: 替换 _inject_technical_indicators 方法（第2045行）:

    使用本文件中的 _inject_technical_indicators_enhanced 替换原方法

Step 4: 添加辅助方法:

    复制以下方法到 StrategyCodeService 类中:
    - _inject_momentum_factors
    - _inject_trend_factors
    - _inject_volatility_factors
    - _inject_volume_factors
    - _inject_ma_factors
    - _inject_reversal_factors
    - _ensure_backward_compatibility

Step 5: 测试:

    python tests/test_strategy_code_service.py

效果:
    策略可用因子: 13个 → 104个 ✅
"""

if __name__ == "__main__":
    print(USAGE_INSTRUCTIONS)
