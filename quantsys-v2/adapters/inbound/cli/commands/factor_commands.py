"""
Factor Commands

因子查询相关命令
"""

from typing import Any, Dict
from ..command_base import HTTPCommand


class FactorLatestCommand(HTTPCommand):
    """最新因子命令"""

    @property
    def name(self) -> str:
        return "factor.latest"

    @property
    def description(self) -> str:
        return "获取最新因子值"

    def get_endpoint(self) -> str:
        return "/api/factors/latest"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {'params': {'symbol': kwargs.get('symbol')}}


class FactorHistoryCommand(HTTPCommand):
    """因子历史命令"""

    @property
    def name(self) -> str:
        return "factor.history"

    @property
    def description(self) -> str:
        return "获取因子历史数据"

    def get_endpoint(self) -> str:
        return "/api/factors/history"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        if not kwargs.get('factor'):
            return "因子名称不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'symbol': kwargs.get('symbol'),
                'factor': kwargs.get('factor'),
                'start': kwargs.get('start'),
                'end': kwargs.get('end')
            }
        }


class FactorListCommand(HTTPCommand):
    """因子列表命令"""

    @property
    def name(self) -> str:
        return "factor.list"

    @property
    def description(self) -> str:
        return "获取可用因子列表"

    def get_endpoint(self) -> str:
        return "/api/factors/list"

    def get_method(self) -> str:
        return "GET"

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'symbol': kwargs.get('symbol')
            }
        }


class FactorCalculateCommand(HTTPCommand):
    """因子计算命令"""

    @property
    def name(self) -> str:
        return "factor.calculate"

    @property
    def description(self) -> str:
        return "计算指定因子"

    def get_endpoint(self) -> str:
        return "/api/factors/calculate"

    def get_method(self) -> str:
        return "POST"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        if not kwargs.get('factors'):
            return "因子列表不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'json': {
                'symbol': kwargs.get('symbol'),
                'factors': kwargs.get('factors'),
                'start': kwargs.get('start'),
                'end': kwargs.get('end')
            }
        }


def get_all_commands():
    """获取所有因子命令类"""
    return [
        FactorLatestCommand,
        FactorHistoryCommand,
        FactorListCommand,
        FactorCalculateCommand,
    ]
