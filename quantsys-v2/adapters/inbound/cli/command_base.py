"""
Command Pattern Base Classes

所有CLI命令的基类，定义统一接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class CommandResult:
    """命令执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'success': self.success,
            'data': self.data,
        }
        if self.error:
            result['error'] = self.error
        if self.warnings:
            result['warnings'] = self.warnings
        return result


class Command(ABC):
    """命令基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """命令名称，如 'stock.search'"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """命令描述"""
        pass

    @property
    def domain(self) -> str:
        """命令域，从name中提取"""
        return self.name.split('.')[0] if '.' in self.name else 'unknown'

    @property
    def action(self) -> str:
        """命令动作，从name中提取"""
        return self.name.split('.')[1] if '.' in self.name else self.name

    @abstractmethod
    def execute(self, **kwargs) -> CommandResult:
        """
        执行命令

        Args:
            **kwargs: 命令参数

        Returns:
            CommandResult: 执行结果
        """
        pass

    def validate_params(self, **kwargs) -> Optional[str]:
        """
        验证参数（可选重写）

        Returns:
            Optional[str]: 错误信息，None表示验证通过
        """
        return None


class HTTPCommand(Command):
    """通过HTTP调用API的命令基类"""

    def __init__(self, http_client):
        """
        Args:
            http_client: HTTP客户端实例
        """
        self.http_client = http_client

    @abstractmethod
    def get_endpoint(self) -> str:
        """获取API端点"""
        pass

    @abstractmethod
    def get_method(self) -> str:
        """获取HTTP方法 (GET/POST/PUT/DELETE)"""
        pass

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        """
        准备请求参数（可选重写）

        Returns:
            Dict包含 'params' (query params) 或 'json' (request body)
        """
        return {'params': kwargs}

    def process_response(self, response_data: Dict[str, Any]) -> Any:
        """
        处理响应数据（可选重写）

        Args:
            response_data: API返回的原始数据

        Returns:
            处理后的数据
        """
        return response_data

    def execute(self, **kwargs) -> CommandResult:
        """执行HTTP命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            # 准备请求
            endpoint = self.get_endpoint()
            method = self.get_method()
            request_data = self.prepare_request(**kwargs)

            # 发送请求
            response = self.http_client.request(
                method=method,
                endpoint=endpoint,
                **request_data
            )

            # 处理响应
            if response.get('error'):
                return CommandResult(
                    success=False,
                    error=response.get('error')
                )

            processed_data = self.process_response(response)

            return CommandResult(
                success=True,
                data=processed_data
            )

        except Exception as e:
            return CommandResult(
                success=False,
                error=f"命令执行失败: {str(e)}"
            )
