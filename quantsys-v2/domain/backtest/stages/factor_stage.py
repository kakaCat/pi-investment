"""
因子计算Stage

使用新的BaseCalculator框架（通过FactorCalculatorAdapter）进行因子计算。
提供高性能的NumPy向量化计算和丰富的元数据支持。
"""

from __future__ import annotations

from typing import Any
from functools import lru_cache
import hashlib
import json

from domain.quantlib.core.pipeline import PipelineStage
from domain.quantlib.adapters import get_factor_adapter
import logging

logger = logging.getLogger(__name__)


class FactorStage(PipelineStage):
    """
    因子计算Stage

    输入：
    - symbol: 股票代码
    - klines: K线数据 (list of dict)

    输出：
    - factors: 计算后的因子值 (dict)
    - factors_metadata: 因子元数据 (dict, 可选)

    参数：
    - include_metadata: 是否包含因子元数据（默认：False）
    """

    # Factor names to calculate by default (subset of all registered).
    # Add to this list to include new factors in default pipeline output.
    DEFAULT_TECHNICAL_FACTORS = [
        # MA family
        "ma5", "ma10", "ma20",
        # RSI
        "rsi14",
        # MACD
        "macd", "macd_signal", "macd_histogram",
        # Bollinger
        "bollinger_upper", "bollinger_middle", "bollinger_lower",
        # ATR
        "atr14",
        # Volume
        "volume_ma5", "volume_ratio",
        # Reversal factors (high IC: 0.08-0.12)
        "reversal_1d", "reversal_5d", "overnight_return",
        # Advanced momentum factors (high IC: 0.06-0.10)
        "momentum_6m", "momentum_52w_high", "acceleration",
    ]

    # Fundamental factors (require financial data)
    DEFAULT_FUNDAMENTAL_FACTORS = [
        "fscore",
        "earnings_quality",
    ]

    def __init__(
        self,
        name: str = "factors",
        include_metadata: bool = False,
        factor_names: list[str] = None
    ):
        super().__init__(name)
        self.include_metadata = include_metadata
        self.factor_names = factor_names  # Allow custom factor list
        logger.info("FactorStage initialized with BaseCalculator framework")

    def _hash_klines(self, klines: list[dict]) -> str:
        """
        生成K线数据的哈希值，用于缓存键

        Args:
            klines: K线数据列表

        Returns:
            K线数据的MD5哈希值
        """
        # 只使用关键字段生成哈希，避免序列化整个数据
        key_data = []
        for kline in klines:
            key_data.append((
                kline.get("close"),
                kline.get("high"),
                kline.get("low"),
                kline.get("open"),
                kline.get("volume"),
            ))

        # 使用json序列化并计算哈希
        data_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    @lru_cache(maxsize=256)
    def _calculate_factors_cached(
        self,
        symbol: str,
        klines_hash: str,
        factor_names_tuple: tuple[str, ...],
        klines_tuple: tuple[tuple, ...]
    ) -> dict[str, float | None]:
        """
        缓存的因子计算方法

        Args:
            symbol: 股票代码
            klines_hash: K线数据的哈希值（用于缓存键）
            factor_names_tuple: 因子名称元组（用于缓存键）
            klines_tuple: K线数据元组（可哈希格式）

        Returns:
            计算后的因子字典
        """
        # 将元组格式的klines转回列表格式
        klines_list = []
        for kline_tuple in klines_tuple:
            klines_list.append({
                "close": kline_tuple[0],
                "high": kline_tuple[1],
                "low": kline_tuple[2],
                "open": kline_tuple[3],
                "volume": kline_tuple[4],
            })

        # 使用新框架计算因子
        adapter = get_factor_adapter()
        return adapter.calculate_batch(list(factor_names_tuple), klines_list)

    def validate_input(self, data: dict[str, Any]) -> bool:
        """验证输入数据"""
        if "symbol" not in data:
            raise ValueError("Missing required field: symbol")

        if "klines" not in data:
            raise ValueError("Missing required field: klines")

        if not isinstance(data["klines"], list):
            raise ValueError("klines must be a list")

        if len(data["klines"]) < 20:
            logger.warning(
                "Insufficient klines data: %d < 20", len(data["klines"])
            )

        return True

    def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        计算因子

        Args:
            data: 输入数据，包含 symbol 和 klines

        Returns:
            包含因子的数据
        """
        symbol = data["symbol"]
        klines = data["klines"]

        logger.info(
            "Calculating factors for %s, klines count: %d",
            symbol, len(klines),
        )

        # --- validate required columns exist ---
        required_cols = {"close", "high", "low", "open", "volume"}
        if klines:
            available = set(klines[0].keys())
            missing = required_cols - available
            if missing:
                # volume is less critical -- only raise for price fields
                price_fields = {"close", "high", "low", "open"}
                critical_missing = missing & price_fields
                if critical_missing:
                    col = sorted(critical_missing)[0]
                    logger.error("Missing required column: %s", col)
                    raise ValueError(f"Missing required column: {col}")

        # --- calculate factors via adapter ---
        factor_names = self._resolve_factor_names(data)
        financial_data = data.get('financial_data')

        # Separate technical and fundamental factors
        adapter = get_factor_adapter()
        technical_factors = [f for f in factor_names if f not in self.DEFAULT_FUNDAMENTAL_FACTORS]
        fundamental_factors = [f for f in factor_names if f in self.DEFAULT_FUNDAMENTAL_FACTORS]

        # Calculate technical factors with caching
        if technical_factors:
            # 生成缓存键
            klines_hash = self._hash_klines(klines)
            factor_names_tuple = tuple(sorted(technical_factors))

            # 将klines转换为可哈希的元组格式
            klines_tuple = tuple(
                (
                    kline.get("close"),
                    kline.get("high"),
                    kline.get("low"),
                    kline.get("open"),
                    kline.get("volume"),
                )
                for kline in klines
            )

            # 调用缓存方法
            if self.include_metadata:
                # Use adapter with metadata
                factors_with_metadata = adapter.calculate_batch_with_metadata(
                    list(factor_names_tuple), klines
                )
                # Extract values for backward compatibility
                factors = {
                    k: v['value'] if v and 'value' in v else None
                    for k, v in factors_with_metadata.items()
                }
            else:
                # Use standard calculation
                factors = self._calculate_factors_cached(
                    symbol, klines_hash, factor_names_tuple, klines_tuple
                )
        else:
            factors = {}
            if self.include_metadata:
                factors_with_metadata = {}

        # Calculate fundamental factors (no caching, as financial data changes less frequently)
        if fundamental_factors and financial_data:
            logger.info(
                "Calculating fundamental factors for %s: %s",
                symbol, fundamental_factors
            )
            if self.include_metadata:
                fund_factors_meta = adapter.calculate_batch_with_metadata(
                    fundamental_factors, klines, financial_data
                )
                factors_with_metadata.update(fund_factors_meta)
                # Extract values
                for k, v in fund_factors_meta.items():
                    factors[k] = v['value'] if v and 'value' in v else None
            else:
                fund_factors = adapter.calculate_batch(
                    fundamental_factors, klines, financial_data
                )
                factors.update(fund_factors)

        # Drop None values (factors that could not be computed)
        factors = {k: v for k, v in factors.items() if v is not None}

        result = data.copy()
        result["factors"] = factors

        if self.include_metadata:
            result["factors_metadata"] = factors_with_metadata

        logger.info(
            "Factors calculated for %s: %s", symbol, list(result["factors"].keys())
        )

        return result

    def _resolve_factor_names(self, data: dict[str, Any]) -> list[str]:
        """
        Return the list of factor names to calculate.

        Args:
            data: Input data (may contain financial_data for fundamental factors)

        Returns:
            List of factor names to calculate
        """
        # Use custom factor names if provided
        if self.factor_names:
            return self.factor_names

        # Default: technical factors only
        factor_names = list(self.DEFAULT_TECHNICAL_FACTORS)

        # Add fundamental factors if financial data is available
        if 'financial_data' in data and data['financial_data']:
            factor_names.extend(self.DEFAULT_FUNDAMENTAL_FACTORS)

        return factor_names
