"""
Signal Commands

信号查询相关命令
"""

from typing import Any, Dict
from ..command_base import HTTPCommand


class SignalQueryCommand(HTTPCommand):
    """信号查询命令"""

    @property
    def name(self) -> str:
        return "signal.query"

    @property
    def description(self) -> str:
        return "查询交易信号"

    def get_endpoint(self) -> str:
        return "/api/signals/query"

    def get_method(self) -> str:
        return "GET"

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'date': kwargs.get('date'),
                'type': kwargs.get('type'),
                'limit': kwargs.get('limit', 20)
            }
        }


class SignalLatestCommand(HTTPCommand):
    """最新信号命令"""

    @property
    def name(self) -> str:
        return "signal.latest"

    @property
    def description(self) -> str:
        return "获取最新交易信号"

    def get_endpoint(self) -> str:
        return "/api/signals/latest"

    def get_method(self) -> str:
        return "GET"

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'limit': kwargs.get('limit', 10)
            }
        }


class SignalStatsCommand(HTTPCommand):
    """信号统计命令"""

    @property
    def name(self) -> str:
        return "signal.stats"

    @property
    def description(self) -> str:
        return "获取信号统计信息"

    def get_endpoint(self) -> str:
        return "/api/signals/stats"

    def get_method(self) -> str:
        return "GET"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('start') or not kwargs.get('end'):
            return "开始日期和结束日期不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        return {
            'params': {
                'start': kwargs.get('start'),
                'end': kwargs.get('end')
            }
        }


def get_all_commands():
    """获取所有信号命令类"""
    return [
        SignalQueryCommand,
        SignalLatestCommand,
        SignalStatsCommand,
    ]
