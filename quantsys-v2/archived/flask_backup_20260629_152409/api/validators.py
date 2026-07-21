"""
API 参数验证器
"""
import re
from datetime import datetime
from typing import Any, List


class ValidationError(Exception):
    """验证错误异常"""
    pass


def validate_stock_symbol(symbol: str) -> str:
    """验证股票代码格式

    支持格式:
    - A股: 000001.SZ, 600000.SH
    - 港股: 00700.HK
    - 美股: AAPL, TSLA

    Args:
        symbol: 股票代码

    Returns:
        str: 标准化后的股票代码

    Raises:
        ValidationError: 格式不正确
    """
    if not symbol or not isinstance(symbol, str):
        raise ValidationError("股票代码不能为空")

    symbol = symbol.strip().upper()

    # A股格式: 6位数字.SZ/SH
    if re.match(r'^\d{6}\.(SZ|SH)$', symbol):
        return symbol

    # 港股格式: 5位数字.HK
    if re.match(r'^\d{5}\.HK$', symbol):
        return symbol

    # 美股格式: 1-5个字母
    if re.match(r'^[A-Z]{1,5}$', symbol):
        return symbol

    raise ValidationError(f"股票代码格式不正确: {symbol}")


def validate_date(date_str: str) -> str:
    """验证日期格式 (YYYY-MM-DD)

    Args:
        date_str: 日期字符串

    Returns:
        str: 标准化后的日期字符串

    Raises:
        ValidationError: 格式不正确
    """
    if not date_str or not isinstance(date_str, str):
        raise ValidationError("日期不能为空")

    date_str = date_str.strip()

    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise ValidationError(f"日期格式不正确，应为 YYYY-MM-DD: {date_str}")


def validate_date_range(start_date: str, end_date: str) -> tuple:
    """验证日期范围

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        tuple: (start_date, end_date)

    Raises:
        ValidationError: 日期范围不正确
    """
    start = validate_date(start_date)
    end = validate_date(end_date)

    if start > end:
        raise ValidationError(f"开始日期不能晚于结束日期: {start} > {end}")

    return start, end


def validate_positive_int(value: Any, param_name: str = "参数") -> int:
    """验证正整数

    Args:
        value: 待验证的值
        param_name: 参数名称（用于错误消息）

    Returns:
        int: 验证后的整数

    Raises:
        ValidationError: 不是正整数
    """
    try:
        num = int(value)
        if num <= 0:
            raise ValidationError(f"{param_name} 必须是正整数")
        return num
    except (ValueError, TypeError):
        raise ValidationError(f"{param_name} 必须是正整数")


def validate_positive_number(value: Any, param_name: str = "参数") -> float:
    """验证正数

    Args:
        value: 待验证的值
        param_name: 参数名称（用于错误消息）

    Returns:
        float: 验证后的数值

    Raises:
        ValidationError: 不是正数
    """
    try:
        num = float(value)
        if num <= 0:
            raise ValidationError(f"{param_name} 必须是正数")
        return num
    except (ValueError, TypeError):
        raise ValidationError(f"{param_name} 必须是正数")


def validate_percentage(value: Any, param_name: str = "参数") -> float:
    """验证百分比 (0-100)

    Args:
        value: 待验证的值
        param_name: 参数名称（用于错误消息）

    Returns:
        float: 验证后的百分比

    Raises:
        ValidationError: 不在0-100范围内
    """
    try:
        num = float(value)
        if not 0 <= num <= 100:
            raise ValidationError(f"{param_name} 必须在 0-100 之间")
        return num
    except (ValueError, TypeError):
        raise ValidationError(f"{param_name} 必须是数值")


def validate_confidence(value: Any) -> float:
    """验证置信度 (0-1)

    Args:
        value: 待验证的值

    Returns:
        float: 验证后的置信度

    Raises:
        ValidationError: 不在0-1范围内
    """
    try:
        num = float(value)
        if not 0 <= num <= 1:
            raise ValidationError("置信度必须在 0-1 之间")
        return num
    except (ValueError, TypeError):
        raise ValidationError("置信度必须是数值")


def validate_signal_type(signal_type: str) -> str:
    """验证信号类型

    Args:
        signal_type: 信号类型

    Returns:
        str: 验证后的信号类型

    Raises:
        ValidationError: 不是有效的信号类型
    """
    valid_types = ['buy', 'sell', 'hold']
    signal_type = signal_type.strip().lower()

    if signal_type not in valid_types:
        raise ValidationError(f"信号类型必须是以下之一: {', '.join(valid_types)}")

    return signal_type


def validate_market(market: str) -> str:
    """验证市场代码

    Args:
        market: 市场代码

    Returns:
        str: 验证后的市场代码

    Raises:
        ValidationError: 不是有效的市场代码
    """
    valid_markets = ['SZ', 'SH', 'HK', 'US']
    market = market.strip().upper()

    if market not in valid_markets:
        raise ValidationError(f"市场代码必须是以下之一: {', '.join(valid_markets)}")

    return market


def validate_strategy_name(name: str) -> str:
    """验证策略名称

    Args:
        name: 策略名称

    Returns:
        str: 验证后的策略名称

    Raises:
        ValidationError: 格式不正确
    """
    if not name or not isinstance(name, str):
        raise ValidationError("策略名称不能为空")

    name = name.strip()

    # 只允许字母、数字、下划线、中划线
    if not re.match(r'^[a-zA-Z0-9_\-一-龥]+$', name):
        raise ValidationError("策略名称只能包含字母、数字、下划线、中划线和中文")

    if len(name) > 50:
        raise ValidationError("策略名称长度不能超过50个字符")

    return name


def validate_symbols_list(symbols: Any) -> List[str]:
    """验证股票代码列表

    Args:
        symbols: 股票代码列表（可以是list或逗号分隔的字符串）

    Returns:
        List[str]: 验证后的股票代码列表

    Raises:
        ValidationError: 格式不正确
    """
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(',') if s.strip()]
    elif not isinstance(symbols, list):
        raise ValidationError("股票代码列表格式不正确")

    if not symbols:
        raise ValidationError("股票代码列表不能为空")

    validated = []
    for symbol in symbols:
        validated.append(validate_stock_symbol(symbol))

    return validated


def validate_data_source(source: str) -> str:
    """验证数据源

    Args:
        source: 数据源标识

    Returns:
        str: 验证后的数据源

    Raises:
        ValidationError: 不是有效的数据源
    """
    valid_sources = ['portfolio', 'watchlist', 'hs300', 'all']
    source = source.strip().lower()

    if source not in valid_sources:
        raise ValidationError(f"数据源必须是以下之一: {', '.join(valid_sources)}")

    return source


def validate_execution_status(status: str) -> str:
    """验证执行状态

    Args:
        status: 执行状态

    Returns:
        str: 验证后的执行状态

    Raises:
        ValidationError: 不是有效的执行状态
    """
    valid_statuses = ['pending', 'executed', 'closed', 'cancelled']
    status = status.strip().lower()

    if status not in valid_statuses:
        raise ValidationError(f"执行状态必须是以下之一: {', '.join(valid_statuses)}")

    return status


def validate_json_object(data: Any, required_fields: List[str] = None) -> dict:
    """验证JSON对象

    Args:
        data: 待验证的数据
        required_fields: 必需字段列表

    Returns:
        dict: 验证后的字典

    Raises:
        ValidationError: 不是有效的JSON对象或缺少必需字段
    """
    if not isinstance(data, dict):
        raise ValidationError("请求体必须是JSON对象")

    if required_fields:
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValidationError(f"缺少必需字段: {', '.join(missing)}")

    return data


def validate_limit_offset(limit: Any = None, offset: Any = None, max_limit: int = 1000) -> tuple:
    """验证分页参数

    Args:
        limit: 限制数量
        offset: 偏移量
        max_limit: 最大限制数量

    Returns:
        tuple: (limit, offset)

    Raises:
        ValidationError: 参数不正确
    """
    if limit is not None:
        try:
            limit = int(limit)
            if limit <= 0:
                raise ValidationError("limit 必须是正整数")
            if limit > max_limit:
                raise ValidationError(f"limit 不能超过 {max_limit}")
        except (ValueError, TypeError):
            raise ValidationError("limit 必须是整数")
    else:
        limit = 100

    if offset is not None:
        try:
            offset = int(offset)
            if offset < 0:
                raise ValidationError("offset 不能为负数")
        except (ValueError, TypeError):
            raise ValidationError("offset 必须是整数")
    else:
        offset = 0

    return limit, offset
