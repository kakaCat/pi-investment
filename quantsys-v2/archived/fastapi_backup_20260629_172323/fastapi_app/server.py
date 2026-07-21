"""
QuantSys V2 FastAPI 应用

现代化的 ASGI 应用，与 Flask 并存，逐步迁移。

特性:
- 自动生成 OpenAPI 文档 (Swagger UI)
- 基于 Pydantic 的数据验证
- 原生异步支持
- 高性能 (3-10x Flask)

启动:
    python adapters/inbound/fastapi_app/server.py
    # 或
    uvicorn adapters.inbound.fastapi_app.server:app --host 0.0.0.0 --port 5002 --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="QuantSys V2 API",
    description="AI-Driven Quantitative Investment System",
    version="2.0.0",
    docs_url="/api/docs",          # Swagger UI
    redoc_url="/api/redoc",         # ReDoc
    openapi_url="/api/openapi.json" # OpenAPI schema
)

# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("🚀 FastAPI application starting...")

    # 先加载环境变量 - 从 fastapi_app 向上4级到达 quantsys-v2
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        # server.py -> fastapi_app -> inbound -> adapters -> quantsys-v2
        env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'

        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Loaded .env from {env_path}")
            # 验证环境变量
            import os
            pgdb = os.getenv('PGDATABASE')
            pghost = os.getenv('PGHOST')
            logger.info(f"   PGDATABASE: {pgdb}, PGHOST: {pghost}")
        else:
            logger.warning(f"⚠️ .env file not found at {env_path}")
    except Exception as e:
        logger.error(f"❌ Failed to load .env: {e}")
        import traceback
        traceback.print_exc()

    # 初始化 ORM
    try:
        from infrastructure.persistence.orm import init_orm
        init_orm()
        logger.info("✅ ORM initialized successfully")
    except Exception as e:
        logger.error(f"❌ ORM initialization failed: {e}")
        import traceback
        traceback.print_exc()

    logger.info("📖 API Documentation: http://localhost:5002/api/docs")
    logger.info("📚 ReDoc: http://localhost:5002/api/redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("👋 FastAPI application shutting down...")

    # 关闭 ORM 连接
    try:
        from infrastructure.persistence.orm import close_orm
        close_orm()
        logger.info("✅ ORM closed successfully")
    except Exception as e:
        logger.error(f"❌ ORM cleanup failed: {e}")


@app.get("/health", tags=["System"])
async def health_check():
    """
    健康检查端点

    返回:
        - status: 服务状态
        - framework: 框架类型
        - version: API 版本
    """
    return {
        "status": "ok",
        "framework": "fastapi",
        "version": "2.0.0"
    }


@app.get("/", tags=["System"])
async def root():
    """
    根路径

    返回 API 基本信息
    """
    return {
        "name": "QuantSys V2 API",
        "version": "2.0.0",
        "framework": "FastAPI",
        "docs": "/api/docs",
        "redoc": "/api/redoc"
    }


# ==================== 全局异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if app.debug else None
        }
    )


# ==================== 注册路由 ====================

# 测试路由
from .routes.health import router as health_router
app.include_router(health_router)

# 游戏智能路由
from .routes.game.intelligence import router as game_intelligence_router
app.include_router(game_intelligence_router)

# 股票池路由
from .routes.pools import router as pools_router
app.include_router(pools_router)

# 分析工具路由
from .routes.analysis_async import router as analysis_router
app.include_router(analysis_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=5002,
        reload=True,  # 开发模式自动重载
        log_level="info"
    )
