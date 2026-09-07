"""
Market Commands

市场查询相关命令
"""

from typing import Any, Dict
from ..command_base import HTTPCommand


class MarketOverviewCommand(HTTPCommand):
    """市场概览命令"""

    @property
    def name(self) -> str:
        return "market.overview"

    @property
    def description(self) -> str:
        return "获取市场概览（主要指数）"

    def get_endpoint(self) -> str:
        return "/api/market/overview"

    def get_method(self) -> str:
        return "GET"


class MarketIndexCommand(HTTPCommand):
    """指数行情命令"""

    @property
    def name(self) -> str:
        return "market.index"

    @property
    def description(self) -> str:
        return "获取指数行情"

    def get_endpoint(self) -> str:
        return "/api/market/index"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "指数代码不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {'params': {'symbol': kwargs.get('symbol')}}


class MarketSectorCommand(HTTPCommand):
    """板块列表命令"""

    @property
    def name(self) -> str:
        return "market.sector"

    @property
    def description(self) -> str:
        return "获取行业板块列表"

    def get_endpoint(self) -> str:
        return "/api/market/sectors"

    def get_method(self) -> str:
        return "GET"


class MarketStatusCommand(HTTPCommand):
    """市场状态命令"""

    @property
    def name(self) -> str:
        return "market.status"

    @property
    def description(self) -> str:
        return "获取市场交易状态"

    def get_endpoint(self) -> str:
        return "/api/platform/status"

    def get_method(self) -> str:
        return "GET"


def get_all_commands():
    """获取所有市场命令类"""
    return [
        MarketOverviewCommand,
        MarketIndexCommand,
        MarketSectorCommand,
        MarketStatusCommand,
    ]
