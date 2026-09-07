# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""
统一异常体系 - quantsys-v2

所有业务异常应继承此模块的基础异常类，确保一致的错误处理。
"""

from typing import Optional, Dict, Any


class QuantSysError(Exception):
    """quantsys-v2 基础异常类

    所有自定义异常应继承此类。
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or self.__class__.__name__.upper()
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 响应格式"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


# ==================== 业务逻辑异常 ====================

class BusinessError(QuantSysError):
    """业务逻辑错误基类"""
    pass


class ValidationError(BusinessError):
    """数据验证错误"""
    pass


class ResourceNotFoundError(BusinessError):
    """资源不存在"""
    pass


class ResourceAlreadyExistsError(BusinessError):
    """资源已存在"""
    pass


# ==================== 交易相关异常 ====================

class TradingError(BusinessError):
    """交易相关错误基类"""
    pass


class InsufficientFundsError(TradingError):
    """资金不足"""

    def __init__(self, required: float, available: float, account_name: str = None):
        details = {
            "required": required,
            "available": available,
            "deficit": required - available
        }
        if account_name:
            details["account_name"] = account_name

        message = f"资金不足: 需要 ¥{required:,.2f}, 可用 ¥{available:,.2f}"
        if account_name:
            message = f"账户 {account_name} {message}"

        super().__init__(message, code="INSUFFICIENT_FUNDS", details=details)
        self.required = required
        self.available = available


class InsufficientSharesError(TradingError):
    """持仓不足"""

    def __init__(self, symbol: str, required: int, available: int, account_name: str = None):
        details = {
            "symbol": symbol,
            "required": required,
            "available": available,
            "deficit": required - available
        }
        if account_name:
            details["account_name"] = account_name

        message = f"{symbol} 持仓不足: 需要 {required} 股, 可用 {available} 股"
        if account_name:
            message = f"账户 {account_name} {message}"

        super().__init__(message, code="INSUFFICIENT_SHARES", details=details)
        self.symbol = symbol
        self.required = required
        self.available = available


class MarketClosedError(TradingError):
    """非交易时段"""

    def __init__(self, current_time: str = None):
        message = "当前为非交易时段"
        details = {}
        if current_time:
            message = f"当前时间 {current_time} 为非交易时段"
            details["current_time"] = current_time

        super().__init__(message, code="MARKET_CLOSED", details=details)


class InvalidOrderError(TradingError):
    """订单参数错误"""

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            f"订单参数错误: {reason}",
            code="INVALID_ORDER",
            details=kwargs
        )


class OrderExecutionError(TradingError):
    """订单执行失败"""

    def __init__(self, order_id: str, reason: str):
        super().__init__(
            f"订单 {order_id} 执行失败: {reason}",
            code="ORDER_EXECUTION_FAILED",
            details={"order_id": order_id, "reason": reason}
        )


# ==================== 数据相关异常 ====================

class DataError(BusinessError):
    """数据相关错误基类"""
    pass


class SymbolNotFoundError(DataError, ResourceNotFoundError):
    """股票代码不存在"""

    def __init__(self, symbol: str):
        super().__init__(
            f"股票代码 {symbol} 不存在",
            code="SYMBOL_NOT_FOUND",
            details={"symbol": symbol}
        )
        self.symbol = symbol


class DataSourceUnavailableError(DataError):
    """数据源不可用"""

    def __init__(self, source: str, reason: str = None):
        message = f"数据源 {source} 不可用"
        if reason:
            message = f"{message}: {reason}"

        super().__init__(
            message,
            code="DATA_SOURCE_UNAVAILABLE",
            details={"source": source, "reason": reason}
        )


class DataQualityError(DataError):
    """数据质量问题"""

    def __init__(self, issue: str, **kwargs):
        super().__init__(
            f"数据质量问题: {issue}",
            code="DATA_QUALITY_ERROR",
            details=kwargs
        )


# ==================== 策略相关异常 ====================

class StrategyError(BusinessError):
    """策略相关错误基类"""
    pass


class StrategyNotFoundError(StrategyError, ResourceNotFoundError):
    """策略不存在"""

    def __init__(self, strategy_id: int):
        super().__init__(
            f"策略 ID {strategy_id} 不存在",
            code="STRATEGY_NOT_FOUND",
            details={"strategy_id": strategy_id}
        )
        self.strategy_id = strategy_id


class BacktestError(StrategyError):
    """回测执行错误"""

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            f"回测执行失败: {reason}",
            code="BACKTEST_ERROR",
            details=kwargs
        )


class SignalGenerationError(StrategyError):
    """信号生成错误"""

    def __init__(self, strategy_id: int, reason: str):
        super().__init__(
            f"策略 {strategy_id} 信号生成失败: {reason}",
            code="SIGNAL_GENERATION_ERROR",
            details={"strategy_id": strategy_id, "reason": reason}
        )


# ==================== 系统相关异常 ====================

class SystemError(QuantSysError):
    """系统级错误"""
    pass


class DatabaseError(SystemError):
    """数据库错误"""

    def __init__(self, operation: str, reason: str = None):
        message = f"数据库操作失败: {operation}"
        if reason:
            message = f"{message} - {reason}"

        super().__init__(
            message,
            code="DATABASE_ERROR",
            details={"operation": operation, "reason": reason}
        )


class ConfigurationError(SystemError):
    """配置错误"""

    def __init__(self, config_key: str, reason: str):
        super().__init__(
            f"配置错误 {config_key}: {reason}",
            code="CONFIGURATION_ERROR",
            details={"config_key": config_key, "reason": reason}
        )


class ExternalServiceError(SystemError):
    """外部服务调用失败"""

    def __init__(self, service: str, reason: str = None):
        message = f"外部服务 {service} 调用失败"
        if reason:
            message = f"{message}: {reason}"

        super().__init__(
            message,
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "reason": reason}
        )


# ==================== 权限相关异常 ====================

class PermissionError(BusinessError):
    """权限不足"""

    def __init__(self, resource: str, action: str, user: str = None):
        message = f"权限不足: 无法对 {resource} 执行 {action} 操作"
        details = {"resource": resource, "action": action}

        if user:
            message = f"用户 {user} {message}"
            details["user"] = user

        super().__init__(message, code="PERMISSION_DENIED", details=details)


# ==================== 工具函数 ====================

def is_business_error(exc: Exception) -> bool:
    """判断是否为业务异常（可预期的错误）"""
    return isinstance(exc, BusinessError)


def is_system_error(exc: Exception) -> bool:
    """判断是否为系统异常（需要告警）"""
    return isinstance(exc, SystemError)


__all__ = [
    # 基础异常
    "QuantSysError",
    "BusinessError",
    "SystemError",

    # 通用业务异常
    "ValidationError",
    "ResourceNotFoundError",
    "ResourceAlreadyExistsError",
    "PermissionError",

    # 交易异常
    "TradingError",
    "InsufficientFundsError",
    "InsufficientSharesError",
    "MarketClosedError",
    "InvalidOrderError",
    "OrderExecutionError",

    # 数据异常
    "DataError",
    "SymbolNotFoundError",
    "DataSourceUnavailableError",
    "DataQualityError",

    # 策略异常
    "StrategyError",
    "StrategyNotFoundError",
    "BacktestError",
    "SignalGenerationError",

    # 系统异常
    "DatabaseError",
    "ConfigurationError",
    "ExternalServiceError",

    # 工具函数
    "is_business_error",
    "is_system_error",
]
