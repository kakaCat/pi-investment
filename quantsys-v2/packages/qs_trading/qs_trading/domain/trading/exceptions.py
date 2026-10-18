"""Trading domain exceptions（2026-09-10，w-f4aa1f6a）

TradingError 原定义在 application/services/account_trading_service.py（应用层服务文件），
domain 层 trade_guard_service 反向 import 应用层——分层倒置。现上移到 domain，
原位置留别名保持兼容（调用点零改动）。
"""


class TradingError(Exception):
    """交易护栏/执行错误。status_code 供 API 层映射 HTTP 状态码。"""

    def __init__(self, message: str, status_code: int = 422, details: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details
