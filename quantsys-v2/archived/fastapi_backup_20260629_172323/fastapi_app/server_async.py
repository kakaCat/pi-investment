"""
FastAPI 主应用 - 完整异步版本

集成所有异步路由
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from infrastructure.persistence.orm.async_config import init_async_orm, close_async_orm
from adapters.inbound.fastapi_app.routes import pools_async, signals_async, strategies_async
from adapters.inbound.fastapi_app.routes import health

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Quant Investment System API",
    description="量化投资系统 - 异步API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 生命周期事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("Starting FastAPI application...")

    # 初始化异步ORM
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

    # 关闭异步ORM
    try:
        await close_async_orm()
        logger.info("✅ Async ORM closed")
    except Exception as e:
        logger.error(f"❌ Failed to close async ORM: {e}")


# ==================== 注册路由 ====================

# 健康检查
app.include_router(health.router)

# 股票池管理
app.include_router(pools_async.router, prefix="/api")

# 交易信号
app.include_router(signals_async.router, prefix="/api")

# 策略管理
app.include_router(strategies_async.router, prefix="/api")


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
        "description": "量化投资系统异步API",
        "features": {
            "async": True,
            "orm": "SQLAlchemy 2.0 + asyncpg",
            "database": "PostgreSQL",
            "routes": [
                "/api/pools - 股票池管理",
                "/api/signals - 交易信号",
                "/api/strategies - 策略管理"
            ]
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
