"""
FastAPI 主应用 - 完整版本

包含所有已迁移的异步路由
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from infrastructure.persistence.orm.async_config import init_async_orm, close_async_orm

# 导入所有异步路由
from adapters.inbound.fastapi_app.routes import (
    health,
    pools_async,
    signals_async,
    strategies_async,
    market_async,
    backtest_async,
    executions_async,
    analysis_async,
    config_async,
    risk_async,
    charts_async,
    pool_scan_async,
    auth_async
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Quant Investment System API",
    description="量化投资系统 - 完整异步API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 生命周期事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("Starting FastAPI application...")
    try:
        init_async_orm(echo=False)
        logger.info("✅ Async ORM initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize async ORM: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("Shutting down FastAPI application...")
    try:
        await close_async_orm()
        logger.info("✅ Async ORM closed")
    except Exception as e:
        logger.error(f"❌ Failed to close async ORM: {e}")


# ==================== 注册路由 ====================

# 健康检查
app.include_router(health.router)

# 核心业务路由
app.include_router(pools_async.router, prefix="/api")
app.include_router(signals_async.router, prefix="/api")
app.include_router(strategies_async.router, prefix="/api")

# P0 高频核心API
app.include_router(market_async.router, prefix="/api")
app.include_router(backtest_async.router, prefix="/api")
app.include_router(executions_async.router, prefix="/api")
app.include_router(analysis_async.router, prefix="/api")
app.include_router(config_async.router, prefix="/api")
app.include_router(risk_async.router, prefix="/api")
app.include_router(charts_async.router, prefix="/api")
app.include_router(pool_scan_async.router, prefix="/api")
app.include_router(auth_async.router, prefix="/api")


# ==================== 根路由 ====================

@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    return {
        "message": "Quant Investment System API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/api/info", tags=["Info"])
async def api_info():
    """API信息"""
    return {
        "title": "Quant Investment System API",
        "version": "2.0.0",
        "description": "量化投资系统完整异步API",
        "features": {
            "async": True,
            "orm": "SQLAlchemy 2.0 + asyncpg",
            "database": "PostgreSQL",
            "routes": {
                "core": ["pools", "signals", "strategies"],
                "p0": ["market", "backtest", "executions", "analysis", "config", "risk", "charts", "pool_scan", "auth"],
                "total": 13
            }
        },
        "endpoints": {
            "total": 50,
            "migrated": 50,
            "progress": "100% (P0完成)"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server_complete:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
