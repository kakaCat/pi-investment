"""
FastAPI 应用包

包含 FastAPI 路由和中间件。

注意：不在包级别导入 `app`（避免 import 任何子模块时触发整个应用的
路由注册等副作用）。需要应用实例时请显式：
    from adapters.inbound.fastapi_app.main import app
"""
