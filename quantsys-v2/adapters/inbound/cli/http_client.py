"""
HTTP Client for CLI to API communication

封装对v2 API的HTTP调用，提供统一的错误处理和重试机制。
"""

import json
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from infrastructure.config import get_config


class HTTPClient:
    """HTTP客户端"""

    def __init__(
        self,
        base_url: str = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Args:
            base_url: API基础URL，默认从配置读取
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        if base_url is None:
            config = get_config()
            base_url = config.app.quantsys_api_url
        
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'QuantSys-CLI/2.0'
        })

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送HTTP请求

        Args:
            method: HTTP方法 (GET/POST/PUT/DELETE)
            endpoint: API端点 (如 '/api/stocks/search')
            params: URL查询参数
            json_data: JSON请求体
            **kwargs: 其他requests参数

        Returns:
            Dict: API响应数据

        Raises:
            HTTPError: HTTP错误
            ConnectionError: 连接错误
            Timeout: 超时错误
        """
        url = urljoin(self.base_url, endpoint)
        method = method.upper()

        # 清理参数（移除None值）
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                    **kwargs
                )

                # 检查HTTP状态码
                if response.status_code >= 500:
                    # 服务器错误，重试
                    last_error = f"服务器错误: {response.status_code}"
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    raise requests.HTTPError(last_error, response=response)

                elif response.status_code >= 400:
                    # 客户端错误，不重试
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', f'HTTP {response.status_code}')
                    except json.JSONDecodeError:
                        error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                    return {'error': error_msg}

                # 成功响应
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {'error': f'无效的JSON响应: {response.text[:200]}'}

            except requests.Timeout as e:
                last_error = f"请求超时: {str(e)}"
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return {'error': last_error}

            except requests.ConnectionError as e:
                last_error = f"连接失败: {str(e)}"
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return {'error': last_error}

            except Exception as e:
                last_error = f"请求失败: {str(e)}"
                return {'error': last_error}

        return {'error': f'重试{self.max_retries}次后失败: {last_error}'}

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET请求"""
        return self.request('GET', endpoint, params=params)

    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST请求"""
        return self.request('POST', endpoint, json_data=json_data)

    def put(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PUT请求"""
        return self.request('PUT', endpoint, json_data=json_data)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE请求"""
        return self.request('DELETE', endpoint)

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            bool: API是否可用
        """
        try:
            response = self.get('/api/health')
            return response.get('status') == 'ok'
        except Exception:
            return False

    def close(self):
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
