"""tools API - FastAPI 版（从 Flask tools.py 迁移，响应契约保持一致）

端点为服务自省（列出/描述当前服务的路由）。Flask 遍历 current_app.url_map，
FastAPI 遍历 request.app.routes；两边路由集合不同属预期（迁移进行中），
故 parity 测试对命中路由的响应用结构比对，错误路径用精确比对。
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Tools - 工具自省"])


def _iter_route_rules(app) -> List[Dict[str, Any]]:
    """遍历 FastAPI app 路由，产出与 Flask url_map.iter_rules 相同形状的 dict 列表。

    本项目的 FastAPI 为定制版：include_router 以 _IncludedRouter 懒包装挂载，
    需经 original_router 递归取到实际 APIRoute。
    """
    rules = []

    def _walk(routes, prefix=''):
        for route in routes:
            original = getattr(route, 'original_router', None)
            if original is not None:
                ctx = getattr(route, 'include_context', None)
                _walk(getattr(original, 'routes', []),
                      prefix + getattr(ctx, 'prefix', '') if ctx else prefix)
                continue
            path = getattr(route, 'path', None)
            methods = getattr(route, 'methods', None)
            if not path or not methods:
                continue
            name = getattr(route, 'name', '') or ''
            if name == 'static':
                continue
            rules.append({
                'endpoint': name,
                'path': prefix + path,
                'methods': sorted(set(methods) - {'HEAD', 'OPTIONS'}),
            })

    _walk(app.routes)
    return rules


@router.get('/api/tools/list')
@handle_api_error
def list_tools(request: Request):
    """列出所有可用的 v2 命令（替代旧 quant_cli tools.list）"""
    rules = _iter_route_rules(request.app)
    rules.sort(key=lambda r: r['path'])
    return api_response({
        'success': True,
        'count': len(rules),
        'endpoints': rules,
    })


# 命令名 → 路由路径映射表（从 quant-v2-client.ts V2_ROUTES 同步）
COMMAND_TO_PATH = {
    'tools.list': '/api/tools/list',
    'tools.describe': '/api/tools/describe',
    'strategy.create': '/api/strategies/create',
    'strategy.list': '/api/strategies/list',
    'strategy.get': '/api/strategies/detail/{strategy_id}',
    'strategy.run': '/api/strategy/run',
    'strategy.status': '/api/strategy/status',
    'indicators.list': '/api/indicators/list',
    'indicators.detail': '/api/indicators/detail/{indicator_id}',
    'indicators.create': '/api/indicators/create',
    'indicators.update': '/api/indicators/update/{indicator_id}',
    'indicators.delete': '/api/indicators/delete/{indicator_id}',
    'indicators.run': '/api/indicators/run/{indicator_id}',
    'indicators.backtest': '/api/indicators/backtest',
    'indicators.compare': '/api/indicators/compare',
    'indicators.sandbox_columns': '/api/indicators/sandbox-columns',
    # 可以根据需要扩展更多映射
}


@router.get('/api/tools/describe')
@handle_api_error
def describe_tool(request: Request, path: str = Query(''), name: str = Query('')):
    """描述单个 v2 命令（替代旧 quant_cli tools.describe）"""

    # 支持两种查询方式：
    # 1. path=/api/strategies/create - 直接查询路由路径
    # 2. name=strategy.create - 通过命令名查询（需要映射到路由）

    # 如果传了 name，先转换为 path
    if name and not path:
        path = COMMAND_TO_PATH.get(name, '')
        if not path:
            return error_response({
                'success': False,
                'error': f'Unknown command name: {name}. Use path parameter for direct route lookup.'
            }, 404)

    if not path:
        return error_response({
            'success': False,
            'error': 'Missing required parameter: path or name'
        }, 400)

    # 查找匹配的路由（FastAPI 路由路径原生使用 {param} 占位符，直接比较即可；
    # 等价于 Flask 版将 <param> 归一化为 {param} 后的比较）
    for rule in _iter_route_rules(request.app):
        if rule['path'] == path:
            return api_response({
                'success': True,
                'endpoint': rule['endpoint'],
                'path': rule['path'],
                'methods': rule['methods'],
            })

    return error_response({'success': False, 'error': f'No endpoint matches path: {path}'}, 404)
