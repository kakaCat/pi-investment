"""
Kline Commands

K线查询相关命令
"""

from typing import Any, Dict
from ..command_base import HTTPCommand


class KlineQueryCommand(HTTPCommand):
    """K线查询命令"""

    @property
    def name(self) -> str:
        return "kline.query"

    @property
    def description(self) -> str:
        return "查询K线数据"

    def get_endpoint(self) -> str:
        return "/api/klines/query"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'symbol': kwargs.get('symbol'),
                'start': kwargs.get('start'),
                'end': kwargs.get('end'),
                'limit': kwargs.get('limit', 100)
            }
        }


class KlineLatestCommand(HTTPCommand):
    """最新K线命令"""

    @property
    def name(self) -> str:
        return "kline.latest"

    @property
    def description(self) -> str:
        return "获取最新K线"

    def get_endpoint(self) -> str:
        return "/api/klines/latest"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'symbol': kwargs.get('symbol'),
                'limit': kwargs.get('limit', 20)
            }
        }


class KlineStatsCommand(HTTPCommand):
    """K线统计命令"""

    @property
    def name(self) -> str:
        return "kline.stats"

    @property
    def description(self) -> str:
        return "获取K线统计信息"

    def get_endpoint(self) -> str:
        return "/api/klines/stats"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        if not kwargs.get('start') or not kwargs.get('end'):
            return "开始日期和结束日期不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'symbol': kwargs.get('symbol'),
                'start': kwargs.get('start'),
                'end': kwargs.get('end')
            }
        }


def get_all_commands():
    """获取所有K线命令类"""
    return [
        KlineQueryCommand,
        KlineLatestCommand,
        KlineStatsCommand,
    ]
