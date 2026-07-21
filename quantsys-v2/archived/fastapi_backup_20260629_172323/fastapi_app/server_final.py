"""
FastAPI 主应用 - 最终完整版本

包含所有P0+P1异步路由
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from infrastructure.persistence.orm.async_config import init_async_orm, close_async_orm

# P0核心路由
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

# P1中频路由
from adapters.inbound.fastapi_app.routes import (
    realtime_signals_async,
    decision_tracking_async,
)

from adapters.inbound.fastapi_app.routes.p1_batch_async import (
    sentiment_router,
    discovery_router,
    game_alert_router,
    chan_router,
    data_quality_router
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Quant Investment System API",
    description="量化投资系统 - 完整异步API (P0+P1)",
    version="2.0.1",
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
    logger.info("Starting FastAPI application (P0+P1)...")
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

# P0 核心业务路由
app.include_router(pools_async.router, prefix="/api")
app.include_router(signals_async.router, prefix="/api")
app.include_router(strategies_async.router, prefix="/api")
app.include_router(market_async.router, prefix="/api")
app.include_router(backtest_async.router, prefix="/api")
app.include_router(executions_async.router, prefix="/api")
app.include_router(analysis_async.router, prefix="/api")
app.include_router(config_async.router, prefix="/api")
app.include_router(risk_async.router, prefix="/api")
app.include_router(charts_async.router, prefix="/api")
app.include_router(pool_scan_async.router, prefix="/api")
app.include_router(auth_async.router, prefix="/api")

# P1 中频业务路由
app.include_router(realtime_signals_async.router, prefix="/api")
app.include_router(decision_tracking_async.router, prefix="/api")
app.include_router(sentiment_router, prefix="/api")
app.include_router(discovery_router, prefix="/api")
app.include_router(game_alert_router, prefix="/api")
app.include_router(chan_router, prefix="/api")
app.include_router(data_quality_router, prefix="/api")


# ==================== 根路由 ====================

@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    return {
        "message": "Quant Investment System API",
        "version": "2.0.1",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "features": ["P0 Core APIs", "P1 Medium-Frequency APIs"]
    }


@app.get("/api/info", tags=["Info"])
async def api_info():
    """API信息"""
    return {
        "title": "Quant Investment System API",
        "version": "2.0.1",
        "description": "量化投资系统完整异步API (P0+P1)",
        "features": {
            "async": True,
            "orm": "SQLAlchemy 2.0 + asyncpg",
            "database": "PostgreSQL",
            "modules": {
                "p0_core": 12,
                "p1_medium": 7,
                "total": 19
            }
        },
        "endpoints": {
            "p0": 47,
            "p1": 15,
            "total": 62,
            "progress": "完成P0+P1"
        },
        "routes": {
            "p0": [
                "pools", "signals", "strategies", "market", "backtest",
                "executions", "analysis", "config", "risk", "charts",
                "pool-scan", "auth"
            ],
            "p1": [
                "realtime-signals", "decision-tracking", "sentiment",
                "discovery", "game-alert", "chan", "data-quality"
            ]
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server_final:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
