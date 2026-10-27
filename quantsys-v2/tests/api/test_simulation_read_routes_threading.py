"""RFC 017 P0：simulation 只读路由必须为同步 def（FastAPI 线程池执行）。

背景（2026-10-26 实测事故）：`/api/simulation/accounts/{name}` 声明为 async def，
内部却直接执行同步 DB 查询 + 同步外网行情调用 → 阻塞事件循环线程，一个账户
11~18s 的响应拖住**所有**并发请求（实测账户列表与账户状态以完全相同的
10.936s 完成 = 队头阻塞证据）。

同步 def 路由由 FastAPI 放到 anyio 线程池执行，事件循环不再被占用；
scoped_session 清理由 install_sync_session_cleanup() 在 worker 线程内兜底。

本测试是结构级守卫：有人把这些路由改回 async def（或新增同类的
async+阻塞调用路由）即红。
"""
import asyncio

from adapters.inbound.fastapi_app.routes import simulation_async


# 只做同步 DB/外部 I/O 的只读路由。/strategies 系列是内存注册表操作，不在此列。
READ_PATHS = {
    '/api/simulation/accounts',
    '/api/simulation/accounts/{account_name}',
    '/api/simulation/accounts/{account_name}/pending-orders',
    '/api/simulation/accounts/{account_name}/slippage-report',
    '/api/simulation/trades',
    '/api/simulation/accounts/{account_name}/trades',
    '/api/simulation/performance',
    '/api/simulation/execution-history',
}


def test_read_routes_are_sync_def():
    checked = set()
    for route in simulation_async.router.routes:
        path = getattr(route, 'path', None)
        # 同一路径可能有多个 method（如 POST /accounts 开户仍是 async def，合法）——只查 GET
        if path in READ_PATHS and 'GET' in (getattr(route, 'methods', None) or set()):
            checked.add(path)
            assert not asyncio.iscoroutinefunction(route.endpoint), (
                f'{path} 是 async def：其同步 DB/行情调用会阻塞事件循环，'
                f'必须改为同步 def（FastAPI 自动在线程池执行，RFC 017 P0）'
            )
    assert checked == READ_PATHS, f'路由未全部命中，检查路径是否改名: {READ_PATHS - checked}'
