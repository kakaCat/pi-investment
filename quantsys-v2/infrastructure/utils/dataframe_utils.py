"""
DataFrame 工具函数

提供兼容 Pandas 和 Polars DataFrame 的通用函数
"""
import structlog
logger = structlog.get_logger(__name__)

from typing import Any, Union


def is_dataframe_empty(df: Any) -> bool:
    """
    检查 DataFrame 是否为空（兼容 Pandas 和 Polars）

    Args:
        df: DataFrame 对象（pandas.DataFrame 或 polars.DataFrame）

    Returns:
        bool: DataFrame 是否为空
    """
    if df is None:
        return True

    # 尝试 Polars
    try:
        import polars as pl
        if isinstance(df, pl.DataFrame):
            return df.is_empty()
    except (ImportError, AttributeError):
        pass

    # 尝试 Pandas
    try:
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            return df.empty
    except (ImportError, AttributeError):
        pass

    # 回退到长度检查
    try:
        return len(df) == 0
    except Exception:
        logger.debug("unexpected exception in module", exc_info=True)
        return True


def dataframe_length(df: Any) -> int:
    """
    获取 DataFrame 的行数（兼容 Pandas 和 Polars）

    Args:
        df: DataFrame 对象

    Returns:
        int: 行数
    """
    if df is None:
        return 0

    try:
        return len(df)
    except Exception:
        logger.debug("unexpected exception in module", exc_info=True)
        return 0


def to_pandas(df: Any):
    """
    将 DataFrame 转换为 Pandas DataFrame（如果需要）

    Args:
        df: DataFrame 对象

    Returns:
        pandas.DataFrame
    """
    if df is None:
        return None

    # 如果已经是 Pandas，直接返回
    try:
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            return df
    except ImportError:
        pass

    # 尝试从 Polars 转换
    try:
        import polars as pl
        if isinstance(df, pl.DataFrame):
            return df.to_pandas()
    except (ImportError, AttributeError):
        pass

    # 如果是其他类型，尝试用 pandas 构造
    try:
        import pandas as pd
        return pd.DataFrame(df)
    except Exception:
        logger.debug("unexpected exception in module", exc_info=True)
        return df


def to_polars(df: Any):
    """
    将 DataFrame 转换为 Polars DataFrame（如果需要）

    Args:
        df: DataFrame 对象

    Returns:
        polars.DataFrame
    """
    if df is None:
        return None

    # 如果已经是 Polars，直接返回
    try:
        import polars as pl
        if isinstance(df, pl.DataFrame):
            return df
    except ImportError:
        pass

    # 尝试从 Pandas 转换
    try:
        import polars as pl
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            return pl.from_pandas(df)
    except (ImportError, AttributeError):
        pass

    # 如果是其他类型，尝试用 polars 构造
    try:
        import polars as pl
        return pl.DataFrame(df)
    except Exception:
        logger.debug("unexpected exception in module", exc_info=True)
        return df
