"""
Indicator Commands

指标工具相关命令
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from ..command_base import HTTPCommand, CommandResult


def _read_code_file(file_path: str) -> str:
    """
    安全地读取代码文件内容

    Args:
        file_path: 文件路径

    Returns:
        文件内容

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件路径不安全（路径遍历攻击）
    """
    # 转换为绝对路径
    abs_path = Path(file_path).resolve()

    # 验证文件存在
    if not abs_path.exists():
        raise FileNotFoundError(f"指标代码文件不存在: {file_path}")

    # 验证是文件而非目录
    if not abs_path.is_file():
        raise ValueError(f"路径不是文件: {file_path}")

    # 验证文件扩展名
    if abs_path.suffix != '.py':
        raise ValueError(f"文件必须是 .py 文件: {file_path}")

    # 安全检查：防止路径遍历攻击
    # 检查路径中是否包含 .. 组件（在规范化之前）
    if '..' in Path(file_path).parts:
        raise ValueError(f"文件路径不安全，不允许使用 '..' 路径遍历: {file_path}")

    # 使用 with 语句确保文件正确关闭
    with open(abs_path, 'r', encoding='utf-8') as f:
        return f.read()


class IndicatorListCommand(HTTPCommand):
    """列出指标命令"""

    @property
    def name(self) -> str:
        return "indicators.list"

    @property
    def description(self) -> str:
        return "列出所有指标"

    def get_endpoint(self) -> str:
        return "/api/indicators"

    def get_method(self) -> str:
        return "GET"

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        params = {}
        if kwargs.get('active') is not None:
            params['active'] = kwargs['active']
        if kwargs.get('page'):
            params['page'] = kwargs['page']
        if kwargs.get('limit'):
            params['limit'] = kwargs['limit']
        return {'params': params}


class IndicatorCreateCommand(HTTPCommand):
    """创建指标命令"""

    @property
    def name(self) -> str:
        return "indicators.create"

    @property
    def description(self) -> str:
        return "创建新指标"

    def get_endpoint(self) -> str:
        return "/api/indicators"

    def get_method(self) -> str:
        return "POST"

    def validate_params(self, **kwargs) -> Optional[str]:
        if not kwargs.get('name'):
            return "指标名称 (name) 不能为空"
        if not kwargs.get('code'):
            return "指标代码 (code) 不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        # 处理 code 参数：如果是 .py 文件路径，读取文件内容
        code = kwargs['code']
        if code.endswith('.py'):
            code = _read_code_file(code)

        # 构建请求体
        body = {
            'name': kwargs['name'],
            'code': code
        }

        # 可选参数
        if kwargs.get('description'):
            body['description'] = kwargs['description']
        if kwargs.get('params'):
            # 解析 JSON 参数
            try:
                body['params'] = json.loads(kwargs['params'])
            except json.JSONDecodeError as e:
                raise ValueError(f"参数 (params) 必须是有效的 JSON 字符串: {e}")
        if kwargs.get('active') is not None:
            body['active'] = kwargs['active']

        return {'json': body}


class IndicatorUpdateCommand(HTTPCommand):
    """更新指标命令"""

    def __init__(self, http_client):
        super().__init__(http_client)
        self._current_indicator_id = None

    @property
    def name(self) -> str:
        return "indicators.update"

    @property
    def description(self) -> str:
        return "更新指标"

    def get_endpoint(self) -> str:
        if self._current_indicator_id is None:
            raise ValueError("indicator_id 未设置")
        return f"/api/indicators/{self._current_indicator_id}"

    def get_method(self) -> str:
        return "PUT"

    def validate_params(self, **kwargs) -> Optional[str]:
        if not kwargs.get('indicator_id'):
            return "指标ID (indicator_id) 不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        # 设置 indicator_id 用于构建 endpoint
        self._current_indicator_id = kwargs['indicator_id']

        # 构建请求体
        body = {}

        if kwargs.get('name'):
            body['name'] = kwargs['name']
        if kwargs.get('description'):
            body['description'] = kwargs['description']
        if kwargs.get('code'):
            # 处理 code 参数：如果是 .py 文件路径，读取文件内容
            code = kwargs['code']
            if code.endswith('.py'):
                code = _read_code_file(code)
            body['code'] = code
        if kwargs.get('params'):
            # 解析 JSON 参数
            try:
                body['params'] = json.loads(kwargs['params'])
            except json.JSONDecodeError as e:
                raise ValueError(f"参数 (params) 必须是有效的 JSON 字符串: {e}")
        if kwargs.get('active') is not None:
            # 转换为布尔值
            active = kwargs['active']
            if isinstance(active, str):
                body['active'] = active.lower() in ('true', '1', 'yes')
            else:
                body['active'] = bool(active)

        return {'json': body}

    def execute(self, **kwargs) -> CommandResult:
        """重写 execute 以确保每次调用都清理状态"""
        # 在执行前清理状态
        self._current_indicator_id = None

        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            # 先调用 prepare_request 设置 _current_indicator_id
            request_data = self.prepare_request(**kwargs)

            # 然后获取 endpoint（此时 _current_indicator_id 已设置）
            endpoint = self.get_endpoint()
            method = self.get_method()

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
        finally:
            # 确保执行后清理状态，防止实例复用时泄漏
            self._current_indicator_id = None


class IndicatorRunCommand(HTTPCommand):
    """运行指标命令"""

    def __init__(self, http_client):
        super().__init__(http_client)
        self._current_indicator_id = None

    @property
    def name(self) -> str:
        return "indicators.run"

    @property
    def description(self) -> str:
        return "运行指标计算"

    def get_endpoint(self) -> str:
        if self._current_indicator_id is None:
            raise ValueError("indicator_id 未设置")
        return f"/api/indicators/{self._current_indicator_id}/run"

    def get_method(self) -> str:
        return "POST"

    def validate_params(self, **kwargs) -> Optional[str]:
        if not kwargs.get('indicator_id'):
            return "指标ID (indicator_id) 不能为空"
        if not kwargs.get('symbol'):
            return "股票代码 (symbol) 不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        # 设置 indicator_id 用于构建 endpoint
        self._current_indicator_id = kwargs['indicator_id']

        # 构建请求体
        body = {
            'symbol': kwargs['symbol']
        }

        # 可选参数
        if kwargs.get('start_date'):
            body['start_date'] = kwargs['start_date']
        if kwargs.get('end_date'):
            body['end_date'] = kwargs['end_date']
        if kwargs.get('params'):
            # 解析 JSON 参数
            try:
                body['params'] = json.loads(kwargs['params'])
            except json.JSONDecodeError as e:
                raise ValueError(f"参数 (params) 必须是有效的 JSON 字符串: {e}")

        return {'json': body}

    def execute(self, **kwargs) -> CommandResult:
        """重写 execute 以确保每次调用都清理状态"""
        # 在执行前清理状态
        self._current_indicator_id = None

        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            # 先调用 prepare_request 设置 _current_indicator_id
            request_data = self.prepare_request(**kwargs)

            # 然后获取 endpoint（此时 _current_indicator_id 已设置）
            endpoint = self.get_endpoint()
            method = self.get_method()

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
        finally:
            # 确保执行后清理状态，防止实例复用时泄漏
            self._current_indicator_id = None


class IndicatorBacktestCommand(HTTPCommand):
    """回测指标命令"""

    def __init__(self, http_client):
        super().__init__(http_client)
        self._current_indicator_id = None

    @property
    def name(self) -> str:
        return "indicators.backtest"

    @property
    def description(self) -> str:
        return "回测指标策略"

    def get_endpoint(self) -> str:
        if self._current_indicator_id is None:
            raise ValueError("indicator_id 未设置")
        return f"/api/indicators/{self._current_indicator_id}/backtest"

    def get_method(self) -> str:
        return "POST"

    def validate_params(self, **kwargs) -> Optional[str]:
        if not kwargs.get('indicator_id'):
            return "指标ID (indicator_id) 不能为空"
        if not kwargs.get('symbol'):
            return "股票代码 (symbol) 不能为空"
        if not kwargs.get('start_date'):
            return "开始日期 (start_date) 不能为空"
        return None

    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        # 设置 indicator_id 用于构建 endpoint
        self._current_indicator_id = kwargs['indicator_id']

        # 构建请求体
        body = {
            'symbol': kwargs['symbol'],
            'start_date': kwargs['start_date']
        }

        # 可选参数
        if kwargs.get('end_date'):
            body['end_date'] = kwargs['end_date']
        if kwargs.get('initial_capital'):
            body['initial_capital'] = float(kwargs['initial_capital'])
        if kwargs.get('params'):
            # 解析 JSON 参数
            try:
                body['params'] = json.loads(kwargs['params'])
            except json.JSONDecodeError as e:
                raise ValueError(f"参数 (params) 必须是有效的 JSON 字符串: {e}")

        return {'json': body}

    def execute(self, **kwargs) -> CommandResult:
        """重写 execute 以确保每次调用都清理状态"""
        # 在执行前清理状态
        self._current_indicator_id = None

        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            # 先调用 prepare_request 设置 _current_indicator_id
            request_data = self.prepare_request(**kwargs)

            # 然后获取 endpoint（此时 _current_indicator_id 已设置）
            endpoint = self.get_endpoint()
            method = self.get_method()

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
        finally:
            # 确保执行后清理状态，防止实例复用时泄漏
            self._current_indicator_id = None


def get_all_commands():
    """返回所有指标命令类"""
    return [
        IndicatorListCommand,
        IndicatorCreateCommand,
        IndicatorUpdateCommand,
        IndicatorRunCommand,
        IndicatorBacktestCommand
    ]

