"""
QuantSys V2 FastAPI 主应用
完整替换 Flask 应用，提供所有功能

启动方式:
    python adapters/inbound/fastapi_app/main.py
    # 或通过 start_all.py（修改后）

端口: 5001 (替换原 Flask 端口)
文档: http://localhost:5001/docs
"""
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
load_dotenv(env_path)

# 确保项目根目录在 PYTHONPATH
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 FastAPI application starting...")

    # 初始化数据库引擎
    try:
        from infrastructure.persistence.database.engine import init_engine
        init_engine(pool_size=20, max_overflow=20)
        logger.info("✅ SQLAlchemy Engine initialized (pool_size=20, max_overflow=20)")
    except Exception as e:
        logger.error(f"❌ Engine initialization failed: {e}")

    # 初始化 ORM（可选，用于支持旧代码）
    try:
        from infrastructure.persistence.orm import init_orm
        init_orm()
        logger.info("✅ ORM initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ ORM initialization skipped: {e}")

    # 同步内置策略到数据库
    try:
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()
        count = StrategyFactory.sync_to_database()
        logger.info(f"✅ Synced {count} built-in strategies to database")
    except Exception as e:
        logger.warning(f"⚠️ Strategy sync failed: {e}")

    logger.info("📖 API Documentation: http://localhost:5001/docs")
    logger.info("📚 ReDoc: http://localhost:5001/redoc")

    yield  # 应用运行期间

    # 关闭时
    logger.info("👋 FastAPI application shutting down...")

    try:
        from infrastructure.persistence.database.engine import close_engine
        close_engine()
        logger.info("✅ Engine closed successfully")
    except Exception as e:
        logger.error(f"❌ Engine cleanup failed: {e}")

    try:
        from infrastructure.persistence.orm import close_orm
        close_orm()
        logger.info("✅ ORM closed successfully")
    except Exception as e:
        logger.warning(f"⚠️ ORM cleanup skipped: {e}")


# ==================== 创建应用 ====================

app = FastAPI(
    title="QuantSys V2 API",
    description="""
    AI-Driven Quantitative Investment System

    完整的量化投资系统后端，支持：
    - 股票池管理
    - 策略回测和信号生成
    - 实时市场数据
    - 风险分析
    - 博弈智能
    - 自动化交易
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# ==================== 中间件配置 ====================

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip 压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求的日志"""
    start_time = time.time()

    # 处理请求
    response = await call_next(request)

    # 计算处理时间
    process_time = time.time() - start_time

    # 记录日志
    logger.info(
        f"{request.method} {request.url.path} "
        f"- {response.status_code} "
        f"- {process_time:.3f}s"
    )

    # 添加响应头
    response.headers["X-Process-Time"] = str(process_time)

    return response


# ==================== 全局异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


# ==================== 基础路由 ====================

@app.get("/", tags=["System"])
async def root():
    """根路径 - API 基本信息"""
    return {
        "name": "QuantSys V2 API",
        "version": "2.0.0",
        "framework": "FastAPI",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["System"])
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "framework": "fastapi",
        "version": "2.0.0"
    }


# ==================== 注册路由模块 ====================

def register_routes():
    """注册所有路由"""

    # ===== P0 核心路由 =====

    # 健康检查
    try:
        from .routes.health_async import router as health_router
        app.include_router(health_router)
        logger.info("✅ Registered: health")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import health_async: {e}")

    # 执行记录
    try:
        from .routes.executions_async import router as executions_router
        app.include_router(executions_router, prefix="/api")
        logger.info("✅ Registered: executions")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import executions_async: {e}")

    # 市场数据
    try:
        from .routes.market_async import router as market_router
        app.include_router(market_router, prefix="/api")
        logger.info("✅ Registered: market")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import market_async: {e}")

    # 分析工具
    try:
        from .routes.analysis_async import router as analysis_router
        app.include_router(analysis_router, prefix="/api")
        logger.info("✅ Registered: analysis")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import analysis_async: {e}")

    # 图表数据
    try:
        from .routes.charts_async import router as charts_router
        app.include_router(charts_router, prefix="/api")
        logger.info("✅ Registered: charts")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import charts_async: {e}")

    # 配置管理
    try:
        from .routes.config_async import router as config_router
        app.include_router(config_router, prefix="/api")
        logger.info("✅ Registered: config")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import config_async: {e}")

    # 认证授权
    try:
        from .routes.auth_async import router as auth_router
        app.include_router(auth_router, prefix="/api")
        logger.info("✅ Registered: auth")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import auth_async: {e}")

    # 池子扫描
    try:
        from .routes.pool_scan_async import router as pool_scan_router
        app.include_router(pool_scan_router, prefix="/api")
        logger.info("✅ Registered: pool_scan")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import pool_scan_async: {e}")

    # 风险指标
    try:
        from .routes.risk_async import router as risk_router
        app.include_router(risk_router, prefix="/api")
        logger.info("✅ Registered: risk")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import risk_async: {e}")

    # ===== P1 业务路由 =====

    # 股票池管理
    try:
        from .routes.pools_async import router as pools_router
        app.include_router(pools_router, prefix="/api")
        logger.info("✅ Registered: pools")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import pools_async: {e}")

    # 信号管理
    try:
        from .routes.signals_async import router as signals_router
        app.include_router(signals_router, prefix="/api")
        logger.info("✅ Registered: signals")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import signals_async: {e}")

    # 策略管理
    try:
        from .routes.strategies_async import router as strategies_router
        app.include_router(strategies_router, prefix="/api")
        logger.info("✅ Registered: strategies")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import strategies_async: {e}")

    # 决策跟踪
    try:
        from .routes.decision_tracking_async import router as decision_tracking_router
        app.include_router(decision_tracking_router, prefix="/api")
        logger.info("✅ Registered: decision_tracking")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import decision_tracking_async: {e}")

    # 实时信号
    try:
        from .routes.realtime_signals_async import router as realtime_signals_router
        app.include_router(realtime_signals_router, prefix="/api")
        logger.info("✅ Registered: realtime_signals")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import realtime_signals_async: {e}")

    # 回测
    try:
        from .routes.backtest_async import router as backtest_router
        app.include_router(backtest_router, prefix="/api")
        logger.info("✅ Registered: backtest")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import backtest_async: {e}")

    # 回测历史
    try:
        from .routes.backtest_history_async import router as backtest_history_router
        app.include_router(backtest_history_router)
        logger.info("✅ Registered: backtest_history")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import backtest_history_async: {e}")

    # ===== P2 批量路由 =====

    # P1 批量路由
    try:
        from .routes.p1_batch_async import router as p1_batch_router
        app.include_router(p1_batch_router, prefix="/api")
        logger.info("✅ Registered: p1_batch (game_alert, game_intelligence, sentiment, etc.)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import p1_batch_async: {e}")

    # P2 批量路由 - Batch 1
    try:
        from .routes.p2_batch1_async import router as p2_batch1_router
        app.include_router(p2_batch1_router, prefix="/api")
        logger.info("✅ Registered: p2_batch1 (data_quality, diagnosis, etc.)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import p2_batch1_async: {e}")

    # P2 批量路由 - Batch 2
    try:
        from .routes.p2_batch2_async import router as p2_batch2_router
        app.include_router(p2_batch2_router, prefix="/api")
        logger.info("✅ Registered: p2_batch2 (orders, positions, etc.)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import p2_batch2_async: {e}")

    # ===== 游戏智能模块 =====
    try:
        from .routes.game.intelligence import router as game_intelligence_router
        app.include_router(game_intelligence_router)
        logger.info("✅ Registered: game.intelligence")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import game.intelligence: {e}")

    logger.info("=" * 60)
    logger.info("✅ All routes registered successfully")
    logger.info("=" * 60)


# 注册所有路由
register_routes()


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn

    # 获取配置
    import os
    host = os.environ.get('QUANTSYS_API_HOST', '127.0.0.1')
    port = int(os.environ.get('QUANTSYS_API_PORT', '5001'))

    logger.info(f"Starting FastAPI server on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # 生产环境关闭自动重载
        log_level="info",
        access_log=True
    )
