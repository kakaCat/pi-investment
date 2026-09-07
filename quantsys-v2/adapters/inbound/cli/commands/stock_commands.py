"""
Stock Commands

股票查询相关命令
"""

from typing import Any, Dict
from ..command_base import HTTPCommand, CommandResult


class StockSearchCommand(HTTPCommand):
    """股票搜索命令"""

    @property
    def name(self) -> str:
        return "stock.search"

    @property
    def description(self) -> str:
        return "搜索股票（代码或名称模糊匹配）"

    def get_endpoint(self) -> str:
        return "/api/stocks/search"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('q'):
            return "搜索关键词不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'q': kwargs.get('q'),
                'page': kwargs.get('page', 1),
                'pageSize': kwargs.get('limit', 20)
            }
        }


class StockInfoCommand(HTTPCommand):
    """股票信息命令"""

    @property
    def name(self) -> str:
        return "stock.info"

    @property
    def description(self) -> str:
        return "获取股票基本信息"

    def get_endpoint(self) -> str:
        return "/api/stocks/info"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {'params': {'symbol': kwargs.get('symbol')}}


class StockListCommand(HTTPCommand):
    """股票列表命令"""

    @property
    def name(self) -> str:
        return "stock.list"

    @property
    def description(self) -> str:
        return "获取股票列表"

    def get_endpoint(self) -> str:
        return "/api/stocks/list"

    def get_method(self) -> str:
        return "GET"

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'market': kwargs.get('market'),
                'limit': kwargs.get('limit', 50)
            }
        }


class StockAnalysisCommand(HTTPCommand):
    """股票综合分析命令"""

    @property
    def name(self) -> str:
        return "stock.analysis"

    @property
    def description(self) -> str:
        return "获取股票综合分析"

    def get_endpoint(self) -> str:
        return "/api/stocks/analysis"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {'params': {'symbol': kwargs.get('symbol')}}


def get_all_commands():
    """获取所有股票命令类"""
    return [
        StockSearchCommand,
        StockInfoCommand,
        StockListCommand,
        StockAnalysisCommand,
    ]
