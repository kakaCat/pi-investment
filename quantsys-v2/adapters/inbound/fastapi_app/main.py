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
import os
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

# 统一使用结构化日志配置
from infrastructure.logging import configure_structured_logging

# 加载统一配置
from infrastructure.config.settings import get_settings
settings = get_settings()

configure_structured_logging(
    level=settings.logging.log_level,
    json_format=(settings.logging.log_format == "json"),
    enable_trace_id=True
)

import structlog
logger = structlog.get_logger(__name__)

# 加载统一配置
from infrastructure.config.settings import get_settings
settings = get_settings()


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 FastAPI application starting...")

    # 初始化数据库引擎
    try:
        from infrastructure.persistence.database.engine import init_engine
        init_engine(
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow
        )
        logger.info(
            "database_engine_initialized",
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow
        )
    except Exception as e:
        logger.error("database_engine_init_failed", error=str(e))

    # 初始化 ORM（可选，用于支持旧代码）
    try:
        from infrastructure.persistence.orm import init_orm
        init_orm()
        logger.info("✅ ORM initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ ORM initialization skipped: {e}")

    # 同步内置策略到数据库
    try:
        from domain.backtest.engine.strategy_factory import StrategyFactory
        from adapters.outbound.repositories import StrategyORMRepository
        StrategyFactory.auto_discover()
        count = StrategyFactory.sync_to_database(StrategyORMRepository())
        logger.info(f"✅ Synced {count} built-in strategies to database")
    except Exception as e:
        logger.warning(f"⚠️ Strategy sync failed: {e}")

    # WP-15: Agent OS Scheduler Integration (2026-08-16)
    # 注册 quantsys-v2 调度任务到 Agent OS Scheduler（webhook 模式）
    # 注册失败时回退到本地 SchedulerService
    import sys as _sys
    if 'pytest' not in _sys.modules:
        use_agent_os_scheduler = settings.scheduler.agent_os_enabled

        if use_agent_os_scheduler:
            try:
                logger.info("🔄 Registering jobs to Agent OS Scheduler...")
                from tools.register_jobs_to_agent_os import register_all_jobs
                success = await register_all_jobs()
                if success:
                    logger.info("✅ Agent OS Scheduler integration enabled")
                else:
                    logger.warning("⚠️ Job registration failed, falling back to local scheduler")
                    use_agent_os_scheduler = False
            except Exception as e:
                logger.error(f"❌ Agent OS Scheduler registration failed: {e}")
                logger.warning("⚠️ Falling back to local scheduler")
                use_agent_os_scheduler = False

        # 本地 SchedulerService 作为备用（仅当 Agent OS 不可用时启动）
        if not use_agent_os_scheduler:
            try:
                import threading
                from infrastructure.scheduler.scheduler import SchedulerService

                def _run_scheduler():
                    try:
                        SchedulerService().run_loop()
                    except Exception as e:
                        logger.error(f"Scheduler thread crashed: {e}", exc_info=True)

                threading.Thread(target=_run_scheduler, name="scheduler-thread", daemon=True).start()
                logger.info("✅ Local SchedulerService background thread started (fallback mode)")
            except Exception as e:
                logger.error(f"❌ SchedulerService startup failed: {e}")

    # 启动 WatchEngine 实时盯盘线程（2026-08-12 起唯一宿主，原 scheduler_daemon
    # 已下线该职责；pytest 下不启动，避免测试进程拉起盯盘循环）。
    # 引擎句柄挂到 app.state，lifespan 关闭时优雅停止。
    try:
        from adapters.inbound.fastapi_app.watch_bootstrap import start_watch_engine
        handles = start_watch_engine(skip='pytest' in _sys.modules)
        if handles is not None:
            app.state.watch_engine = handles[0]
            logger.info("✅ WatchEngine watch thread started")
    except Exception as e:
        logger.error(f"❌ WatchEngine startup failed: {e}")

    # 启动 DailyOrchestrator/IntradayMonitor tick 线程（2026-08-13 起唯一宿主，
    # 原 scheduler_daemon 已下线该职责——daemon 08-05 停跑致 T+1 结转静默中断 8 天；
    # pytest 下不启动，避免测试进程拉起调度循环）。
    try:
        from adapters.inbound.fastapi_app.orchestrator_bootstrap import start_orchestrator
        orch_handles = start_orchestrator(skip='pytest' in _sys.modules)
        if orch_handles is not None:
            app.state.orchestrator = orch_handles
            logger.info("✅ DailyOrchestrator tick thread started")
    except Exception as e:
        logger.error(f"❌ Orchestrator startup failed: {e}")

    logger.info("📖 API Documentation: http://localhost:5001/docs")
    logger.info("📚 ReDoc: http://localhost:5001/redoc")

    yield  # 应用运行期间

    # 关闭时
    logger.info("👋 FastAPI application shutting down...")

    # WP-15: Close Agent OS client
    try:
        from application.services.agent_os_client import close_agent_os_client
        await close_agent_os_client()
        logger.info("✅ Agent OS client closed")
    except Exception as e:
        logger.warning(f"⚠️ Agent OS client cleanup failed: {e}")

    engine = getattr(app.state, 'watch_engine', None)
    if engine is not None:
        try:
            engine.stop()
            logger.info("✅ WatchEngine stopped")
        except Exception as e:
            logger.warning(f"⚠️ WatchEngine stop failed: {e}")

    orch_handles = getattr(app.state, 'orchestrator', None)
    if orch_handles is not None:
        try:
            from adapters.inbound.fastapi_app.orchestrator_bootstrap import stop_orchestrator
            stop_orchestrator(orch_handles)
            logger.info("✅ Orchestrator tick thread stopped")
        except Exception as e:
            logger.warning(f"⚠️ Orchestrator stop failed: {e}")

    # 关闭线程池（优雅关闭，等待任务完成）
    try:
        from infrastructure.threading.thread_pool import shutdown_all_pools
        logger.info("Shutting down thread pools...")
        shutdown_all_pools(wait=True, timeout=30)
        logger.info("✅ All thread pools shut down")
    except Exception as e:
        logger.warning(f"⚠️ Thread pool shutdown failed: {e}")

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


# ORM Session 释放（2026-08-18 补——Flask→FastAPI 迁移时遗失 teardown 导致
# 连接池耗尽事故：scoped_session 是线程级的，同步路由跑在 anyio 线程池的
# worker 线程上，每个跑过 ORM 查询的线程在首个查询后开启事务并永久持有连接
# （pg 中呈 "idle in transaction"），pool_size+overflow（10+20）耗尽后新请求
# 阻塞 30s 超时 500。Flask 侧由 register_session_teardown(teardown_appcontext)
# 兜底；FastAPI 侧需双管齐下：
#   1. 中间件 close_session() —— 清理事件循环线程的 session（async 路由用）
#   2. install_sync_session_cleanup() —— 包装每个同步路由的 dependant.call，
#      使其在 worker 线程内 finally close_session()（中间件跑在事件循环线程，
#      清不到 worker 线程的 thread-local session，这是本事故的关键点）
@app.middleware("http")
async def release_orm_session(request: Request, call_next):
    """每个请求结束时释放事件循环线程的 ORM Session（覆盖 async 路由）"""
    try:
        return await call_next(request)
    finally:
        from infrastructure.persistence.orm.config import close_session
        close_session()


def install_sync_session_cleanup() -> None:
    """给所有同步路由的 dependant.call 包一层 finally close_session()

    同步端点经 run_in_threadpool(dependant.call) 执行，包装后的 call 与
    ORM session 同在 worker 线程，finally 能真正归还连接。async 端点由上面
    的中间件覆盖，这里跳过。

    注意：本项目 FastAPI 为定制版，include_router 以 _IncludedRouter 懒包装
    挂载，真实 APIRoute 需经 original_router 递归取得（同 tools_async
    ._iter_route_rules 的遍历方式）；且请求时实际执行的是 _EffectiveRouteContext
    上由 route.endpoint 重建的 dependant，所以必须包装 route.endpoint
    （在首个请求构建 effective context 之前完成，本函数在 register_routes
    之后、服务接收请求之前调用，时序安全）。
    """
    import asyncio
    import functools
    from fastapi.routing import APIRoute
    from infrastructure.persistence.orm.config import close_session

    wrapped = 0

    def _walk(routes):
        nonlocal wrapped
        for route in routes:
            original = getattr(route, "original_router", None)
            if original is not None:
                _walk(getattr(original, "routes", []))
                continue
            if not isinstance(route, APIRoute):
                continue
            call = route.endpoint
            if call is None or asyncio.iscoroutinefunction(call):
                continue
            if getattr(call, "_orm_cleanup_wrapped", False):
                continue

            @functools.wraps(call)
            def call_with_cleanup(*args, _call=call, **kwargs):
                try:
                    return _call(*args, **kwargs)
                finally:
                    close_session()

            call_with_cleanup._orm_cleanup_wrapped = True
            route.endpoint = call_with_cleanup
            if route.dependant is not None:
                route.dependant.call = call_with_cleanup
            wrapped += 1

    _walk(app.routes)
    logger.info(f"✅ ORM session cleanup wrapped on {wrapped} sync routes")


# ==================== 全局异常处理 ====================

# 导入业务异常类型
# P0-2 Fix: Replace individual exception handlers with unified exception handling
# Uses structured QuantSysException hierarchy with proper error codes and logging
from adapters.inbound.fastapi_app.exception_handlers import register_exception_handlers
register_exception_handlers(app)


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
    """注册所有路由 —— 核心路由失败时中断启动"""

    # ===== P0 核心路由（CRITICAL - 失败时中断启动） =====
    
    logger.info("=" * 60)
    logger.info("Registering CRITICAL routes...")
    logger.info("=" * 60)
    
    critical_routes = []
    
    # 健康检查（监控依赖）
    try:
        from adapters.inbound.fastapi_app.routes.health_async import router as health_router
        app.include_router(health_router)
        logger.info("✅ Registered (CRITICAL): health")
        critical_routes.append("health")
    except (ImportError, AttributeError) as e:
        logger.error(f"❌ CRITICAL route failed: health - {e}")
        raise RuntimeError(f"Critical route 'health' failed to register: {e}") from e
    
    # 认证授权（安全基础）
    try:
        from adapters.inbound.fastapi_app.routes.auth_async import router as auth_router
        app.include_router(auth_router, prefix="/api")
        logger.info("✅ Registered (CRITICAL): auth")
        critical_routes.append("auth")
    except (ImportError, AttributeError) as e:
        logger.error(f"❌ CRITICAL route failed: auth - {e}")
        raise RuntimeError(f"Critical route 'auth' failed to register: {e}") from e
    
    # Agent OS Scheduler Webhook（关键集成）
    try:
        from api.internal.scheduler_webhook import router as scheduler_webhook_router
        app.include_router(scheduler_webhook_router, prefix="/internal/scheduler", tags=["internal"])
        logger.info("✅ Registered (CRITICAL): scheduler_webhook")
        critical_routes.append("scheduler_webhook")
    except (ImportError, AttributeError) as e:
        logger.error(f"❌ CRITICAL route failed: scheduler_webhook - {e}")
        raise RuntimeError(f"Critical route 'scheduler_webhook' failed to register: {e}") from e
    
    logger.info("=" * 60)
    logger.info(f"✅ All {len(critical_routes)} CRITICAL routes registered successfully")
    logger.info("=" * 60)
    
    # ===== P1 可选路由（失败时告警但继续） =====
    
    logger.info("Registering optional routes...")
    optional_failed = []

    # 执行记录（P5 迁移，parity 对齐 Flask executions.py）
    try:
        from adapters.inbound.fastapi_app.routes.executions_async import router as executions_router
        app.include_router(executions_router)
        logger.info("✅ Registered: executions (P5 迁移)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import executions_async: {e}")
        optional_failed.append("executions")

    # 市场数据
    try:
        from adapters.inbound.fastapi_app.routes.market_async import router as market_router
        app.include_router(market_router, prefix="/api")
        logger.info("✅ Registered: market")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import market_async: {e}")
        optional_failed.append("market")

    # 分析工具（analysis 域，P6 迁移：backtest/compute-factors/technical）
    try:
        from adapters.inbound.fastapi_app.routes.analysis_async import router as analysis_router
        app.include_router(analysis_router)
        logger.info("✅ Registered: analysis (P6 迁移)")
    except ImportError as e:
        optional_failed.append("analysis")
        logger.warning(f"⚠️ Failed to import analysis_async: {e}")

    # 市场/港股数据（market_data 域迁移，parity 对齐 Flask market.py/quote_market.py）
    try:
        from adapters.inbound.fastapi_app.routes.market_data_async import router as market_data_router
        app.include_router(market_data_router)
        logger.info("✅ Registered: market_data (market/hk 迁移)")
    except ImportError as e:
        optional_failed.append("market_data")
        logger.warning(f"⚠️ Failed to import market_data_async: {e}")

    # M1 市场感知（RFC 007: regime落库/主线识别/情绪时间序列）
    try:
        from adapters.inbound.fastapi_app.routes.market_perception_async import router as market_perception_router
        app.include_router(market_perception_router)
        logger.info("✅ Registered: market_perception (M1 RFC 007)")
    except ImportError as e:
        optional_failed.append("market_perception")
        logger.warning(f"⚠️ Failed to import market_perception_async: {e}")

    # 行情K线（quote_market 域迁移：/api/stock/{symbol}/history，agent data_fetch_kline 依赖）
    try:
        from adapters.inbound.fastapi_app.routes.quote_market_async import router as quote_market_router
        app.include_router(quote_market_router)
        logger.info("✅ Registered: quote_market (stock/history 迁移)")
    except ImportError as e:
        optional_failed.append("quote_market")
        logger.warning(f"⚠️ Failed to import quote_market_async: {e}")

    # 图表数据
    try:
        from adapters.inbound.fastapi_app.routes.charts_async import router as charts_router
        app.include_router(charts_router, prefix="/api")
        logger.info("✅ Registered: charts")
    except ImportError as e:
        optional_failed.append("charts")
        logger.warning(f"⚠️ Failed to import charts_async: {e}")

    # 图表（Flask charts.py parity 迁移：accuracy/equity/comparison/importance）
    try:
        from adapters.inbound.fastapi_app.routes.charts_async import flask_parity_router as charts_flask_parity_router
        app.include_router(charts_flask_parity_router)
        logger.info("✅ Registered: charts (Flask parity 迁移)")
    except ImportError as e:
        optional_failed.append("charts_flask_parity")
        logger.warning(f"⚠️ Failed to import charts_async flask_parity_router: {e}")

    # 组合优化（Flask portfolio.py parity 迁移：markowitz/black-litterman/risk-parity）
    try:
        from adapters.inbound.fastapi_app.routes.portfolio_opt_async import router as portfolio_opt_router
        app.include_router(portfolio_opt_router)
        logger.info("✅ Registered: portfolio optimize (Flask parity 迁移)")
    except ImportError as e:
        optional_failed.append("portfolio_opt")
        logger.warning(f"⚠️ Failed to import portfolio_opt_async: {e}")

    # 因子模型（Flask factor_models.py parity 迁移：fama-french-3/5, carhart, barra）
    try:
        from adapters.inbound.fastapi_app.routes.factor_models_async import router as factor_models_router
        app.include_router(factor_models_router)
        logger.info("✅ Registered: factor_models (Flask parity 迁移)")
    except ImportError as e:
        optional_failed.append("factor_models")
        logger.warning(f"⚠️ Failed to import factor_models_async: {e}")

    # 配置管理
    try:
        from adapters.inbound.fastapi_app.routes.config_async import router as config_router
        app.include_router(config_router, prefix="/api")
        logger.info("✅ Registered: config")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import config_async: {e}")
        optional_failed.append("config")

    # V14量化交易 (新增)
    try:
        from adapters.inbound.fastapi_app.routes.v14_trading import router as v14_router
        app.include_router(v14_router)
        logger.info("✅ Registered: v14_trading")
    except ImportError as e:
        optional_failed.append("v14_trading")
        logger.warning(f"⚠️ Failed to import v14_trading: {e}")

    # 池子扫描
    try:
        from adapters.inbound.fastapi_app.routes.pool_scan_async import router as pool_scan_router
        app.include_router(pool_scan_router, prefix="/api")
        logger.info("✅ Registered: pool_scan")
    except ImportError as e:
        optional_failed.append("pool_scan")
        logger.warning(f"⚠️ Failed to import pool_scan_async: {e}")

    # 风控（risk 域，P6 迁移：check + stop-loss 规则）
    try:
        from adapters.inbound.fastapi_app.routes.risk_async import router as risk_router
        app.include_router(risk_router)
        logger.info("✅ Registered: risk (P6 迁移)")
    except ImportError as e:
        optional_failed.append("risk")
        logger.warning(f"⚠️ Failed to import risk_async: {e}")

    # ===== P1 业务路由 =====

    # 投资组合管理（portfolio 端点已并入 orders_async.py，P5 迁移；原 portfolio_async 空桩已删）

    # 股票池管理（P3 迁移，parity 对齐 Flask pools/pool_scan/pool_scan_switch）
    try:
        from adapters.inbound.fastapi_app.routes.pools_async import router as pools_router
        app.include_router(pools_router)
        logger.info("✅ Registered: pools (P3 迁移)")
    except ImportError as e:
        optional_failed.append("pools")
        logger.warning(f"⚠️ Failed to import pools_async: {e}")

    # 信号管理（P3 迁移，parity 对齐 Flask signals.py）
    try:
        from adapters.inbound.fastapi_app.routes.signals_async import router as signals_router
        app.include_router(signals_router)
        logger.info("✅ Registered: signals (P3 迁移)")
    except ImportError as e:
        optional_failed.append("signals")
        logger.warning(f"⚠️ Failed to import signals_async: {e}")

    # 股票数据（stocks 域，P1 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.stock_async import router as stock_router
        app.include_router(stock_router)
        logger.info("✅ Registered: stock (P1 迁移)")
    except ImportError as e:
        optional_failed.append("stock")
        logger.warning(f"⚠️ Failed to import stock_async: {e}")

    # 自选股（watchlist 域，P1 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.watchlist_async import router as watchlist_router
        app.include_router(watchlist_router)
        logger.info("✅ Registered: watchlist (P1 迁移)")
    except ImportError as e:
        optional_failed.append("watchlist")
        logger.warning(f"⚠️ Failed to import watchlist_async: {e}")

    # 实时盯盘（watch 域，WatchEngine parity 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.watch_async import router as watch_router
        app.include_router(watch_router)
        logger.info("✅ Registered: watch (WatchEngine parity 迁移)")
    except ImportError as e:
        optional_failed.append("watch")
        logger.warning(f"⚠️ Failed to import watch_async: {e}")

    # 订单/交易/投资组合（orders 域，P5 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.orders_async import router as orders_router
        app.include_router(orders_router)
        logger.info("✅ Registered: orders (P5 迁移)")
    except ImportError as e:
        optional_failed.append("orders")
        logger.warning(f"⚠️ Failed to import orders_async: {e}")

    # 每日报告（report 域，P7 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.report_async import router as report_router
        app.include_router(report_router)
        logger.info("✅ Registered: report (P7 迁移)")
    except ImportError as e:
        optional_failed.append("report")
        logger.warning(f"⚠️ Failed to import report_async: {e}")

    # 分红数据（dividends 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.dividends_async import router as dividends_router
        app.include_router(dividends_router)
        logger.info("✅ Registered: dividends (agent 迁移)")
    except ImportError as e:
        optional_failed.append("dividends")
        logger.warning(f"⚠️ Failed to import dividends_async: {e}")

    # 数据质量（data_quality 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.data_quality_async import router as data_quality_router
        app.include_router(data_quality_router)
        logger.info("✅ Registered: data_quality (agent 迁移)")
    except ImportError as e:
        optional_failed.append("data_quality")
        logger.warning(f"⚠️ Failed to import data_quality_async: {e}")

    # 情绪/资金（sentiment 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.sentiment_async import router as sentiment_router
        app.include_router(sentiment_router)
        logger.info("✅ Registered: sentiment (agent 迁移)")
    except ImportError as e:
        optional_failed.append("sentiment")
        logger.warning(f"⚠️ Failed to import sentiment_async: {e}")

    # 信号测试（signal_test 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.signal_test_async import router as signal_test_router
        app.include_router(signal_test_router)
        logger.info("✅ Registered: signal_test (agent 迁移)")
    except ImportError as e:
        optional_failed.append("signal_test")
        logger.warning(f"⚠️ Failed to import signal_test_async: {e}")

    # 市场预警（alerts 域，agent 新建）
    try:
        from adapters.inbound.fastapi_app.routes.alerts_async import router as alerts_router
        app.include_router(alerts_router)
        logger.info("✅ Registered: alerts (agent 新建)")
    except ImportError as e:
        optional_failed.append("alerts")
        logger.warning(f"⚠️ Failed to import alerts_async: {e}")

    # Agent 会话事件（sessions 域，parity 迁移——syncer 事件摄入 + web 查询/诊断）
    try:
        from adapters.inbound.fastapi_app.routes.agent_sessions_async import router as agent_sessions_router
        app.include_router(agent_sessions_router)
        logger.info("✅ Registered: agent_sessions (parity 迁移)")
    except ImportError as e:
        optional_failed.append("agent_sessions")
        logger.warning(f"⚠️ Failed to import agent_sessions_async: {e}")

    # 策略发现（discovery 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.discovery_async import router as discovery_router
        app.include_router(discovery_router)
        logger.info("✅ Registered: discovery (agent 迁移)")
    except ImportError as e:
        optional_failed.append("discovery")
        logger.warning(f"⚠️ Failed to import discovery_async: {e}")

    # 市场风格（market_style 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.market_style_async import router as market_style_router
        app.include_router(market_style_router)
        logger.info("✅ Registered: market_style (agent 迁移)")
    except ImportError as e:
        optional_failed.append("market_style")
        logger.warning(f"⚠️ Failed to import market_style_async: {e}")

    # 时间序列分析（timeseries 域，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.timeseries_async import router as timeseries_router
        app.include_router(timeseries_router)
        logger.info("✅ Registered: timeseries (agent 迁移)")
    except ImportError as e:
        optional_failed.append("timeseries")
        logger.warning(f"⚠️ Failed to import timeseries_async: {e}")

    # 诊断（diagnosis 域，P8 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.diagnosis_async import router as diagnosis_router
        app.include_router(diagnosis_router)
        logger.info("✅ Registered: diagnosis (P8 迁移)")
    except ImportError as e:
        optional_failed.append("diagnosis")
        logger.warning(f"⚠️ Failed to import diagnosis_async: {e}")

    # 缠论分析（chan 域，P8 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.chan_async import router as chan_router
        app.include_router(chan_router)
        logger.info("✅ Registered: chan (P8 迁移)")
    except ImportError as e:
        optional_failed.append("chan")
        logger.warning(f"⚠️ Failed to import chan_async: {e}")

    # 统一记忆存储（memory 域，W1.2 框架演进 P1）
    try:
        from adapters.inbound.fastapi_app.routes.memory_async import router as memory_router
        app.include_router(memory_router)
        logger.info("✅ Registered: memory (W1.2 统一记忆)")
    except ImportError as e:
        optional_failed.append("memory")
        logger.warning(f"⚠️ Failed to import memory_async: {e}")

    # 记忆蒸馏（memory distill 域，W1.5a T1）
    try:
        from adapters.inbound.fastapi_app.routes.memory_distill_async import router as memory_distill_router
        app.include_router(memory_distill_router)
        logger.info("✅ Registered: memory_distill (W1.5a 记忆蒸馏)")
    except ImportError as e:
        optional_failed.append("memory_distill")
        logger.warning(f"⚠️ Failed to import memory_distill_async: {e}")

    # 知识库（knowledge 域，W1.1 修断链后补 FastAPI 路由——此前仅 Flask 有，5001 上 404）
    try:
        from adapters.inbound.fastapi_app.routes.knowledge_async import router as knowledge_router
        app.include_router(knowledge_router)
        logger.info("✅ Registered: knowledge (W1.1 FastAPI 补全)")
    except ImportError as e:
        optional_failed.append("knowledge")
        logger.warning(f"⚠️ Failed to import knowledge_async: {e}")

    # 行为进化（evolution 域，2026-08-05 Phase 1）
    try:
        from adapters.inbound.fastapi_app.routes.evolution_async import router as evolution_router
        app.include_router(evolution_router)
        logger.info("✅ Registered: evolution (行为进化 Phase 1)")
    except ImportError as e:
        optional_failed.append("evolution")
        logger.warning(f"⚠️ Failed to import evolution_async: {e}")

    # 流水线（pipeline 域，P8 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.pipeline_async import router as pipeline_router
        app.include_router(pipeline_router)
        logger.info("✅ Registered: pipeline (P8 迁移)")
    except ImportError as e:
        optional_failed.append("pipeline")
        logger.warning(f"⚠️ Failed to import pipeline_async: {e}")

    # 机器学习（ml 域，P8 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.ml_async import router as ml_router
        app.include_router(ml_router)
        logger.info("✅ Registered: ml (P8 迁移)")
    except ImportError as e:
        optional_failed.append("ml")
        logger.warning(f"⚠️ Failed to import ml_async: {e}")

    # 财务报表 V2（financials_v2 域，parity 对齐 Flask financials_v2.py）
    try:
        from adapters.inbound.fastapi_app.routes.financials_async import router as financials_router
        app.include_router(financials_router)
        logger.info("✅ Registered: financials_v2 (parity 迁移)")
    except ImportError as e:
        optional_failed.append("financials")
        logger.warning(f"⚠️ Failed to import financials_async: {e}")

    # 策略管理（P2 迁移，parity 对齐 Flask strategies.py）
    try:
        from adapters.inbound.fastapi_app.routes.strategies_async import router as strategies_router
        app.include_router(strategies_router)
        logger.info("✅ Registered: strategies (P2 迁移)")
    except ImportError as e:
        optional_failed.append("strategies")
        logger.warning(f"⚠️ Failed to import strategies_async: {e}")

    # 策略执行（P2 迁移，run/status）
    try:
        from adapters.inbound.fastapi_app.routes.strategy_async import router as strategy_exec_router
        app.include_router(strategy_exec_router)
        logger.info("✅ Registered: strategy run/status (P2 迁移)")
    except ImportError as e:
        optional_failed.append("strategy")
        logger.warning(f"⚠️ Failed to import strategy_async: {e}")

    # 统一策略交易 API（重构版，支持 V13/V14/V15...）
    try:
        from adapters.inbound.fastapi_app.routes.strategy_trading_async import router as strategy_trading_router
        app.include_router(strategy_trading_router, prefix="/api")
        logger.info("✅ Registered: strategy_trading (统一策略API: /api/strategy/*)")
    except ImportError as e:
        optional_failed.append("strategy_trading")
        logger.warning(f"⚠️ Failed to import strategy_trading_async: {e}")

    # 多账户域 API（账户发现/开户/手工交易/绩效）
    try:
        from adapters.inbound.fastapi_app.routes.simulation_async import router as simulation_async_router
        app.include_router(simulation_async_router)
        logger.info("✅ Registered: simulation accounts (多账户API: /api/simulation/accounts/*)")
    except ImportError as e:
        optional_failed.append("simulation")
        logger.warning(f"⚠️ Failed to import simulation_async: {e}")

    # 决策追踪（/api/decisions/*，走 DecisionService → PG，Flask parity）
    try:
        from adapters.inbound.fastapi_app.routes.decisions_async import router as decisions_router
        app.include_router(decisions_router)
        logger.info("✅ Registered: decisions (/api/decisions/*, PG 持久化)")
    except ImportError as e:
        optional_failed.append("decisions")
        logger.warning(f"⚠️ Failed to import decisions_async: {e}")

    # 决策跟踪（旧内存桩，/api/decision-tracking/*，保留兼容）
    try:
        from adapters.inbound.fastapi_app.routes.decision_tracking_async import router as decision_tracking_router
        app.include_router(decision_tracking_router, prefix="/api")
        logger.info("✅ Registered: decision_tracking")
    except ImportError as e:
        optional_failed.append("decision_tracking")
        logger.warning(f"⚠️ Failed to import decision_tracking_async: {e}")

    # 实时信号（包含新迁移的 3 个端点）
    try:
        from adapters.inbound.fastapi_app.routes.realtime_signals_async import router as realtime_signals_router
        app.include_router(realtime_signals_router, prefix="/api")
        logger.info("✅ Registered: realtime_signals (包含 t1/generate, filter/executable, morning-scan)")
    except ImportError as e:
        optional_failed.append("realtime_signals")
        logger.warning(f"⚠️ Failed to import realtime_signals_async: {e}")

    # 策略执行（新迁移的 3 个端点）
    try:
        from adapters.inbound.fastapi_app.routes.strategy_execution_async import router as strategy_execution_router
        app.include_router(strategy_execution_router, prefix="/api")
        logger.info("✅ Registered: strategy_execution (execute, batch-execute, pipeline-execute)")
    except ImportError as e:
        optional_failed.append("strategy_execution")
        logger.warning(f"⚠️ Failed to import strategy_execution_async: {e}")

    # 回测
    try:
        from adapters.inbound.fastapi_app.routes.backtest_async import router as backtest_router
        app.include_router(backtest_router, prefix="/api")
        logger.info("✅ Registered: backtest")
    except ImportError as e:
        optional_failed.append("backtest")
        logger.warning(f"⚠️ Failed to import backtest_async: {e}")

    # 回测（Flask backtest.py 迁移：results/run/strategy/combo + performance/*）
    try:
        from adapters.inbound.fastapi_app.routes.backtest_async import flask_parity_router as backtest_flask_parity_router
        app.include_router(backtest_flask_parity_router)
        logger.info("✅ Registered: backtest (Flask parity 迁移)")
    except ImportError as e:
        optional_failed.append("backtest_flask_parity")
        logger.warning(f"⚠️ Failed to import backtest_async flask_parity_router: {e}")

    # 回测历史
    try:
        from adapters.inbound.fastapi_app.routes.backtest_history_async import router as backtest_history_router
        app.include_router(backtest_history_router)
        logger.info("✅ Registered: backtest_history")
    except ImportError as e:
        optional_failed.append("backtest_history")
        logger.warning(f"⚠️ Failed to import backtest_history_async: {e}")

    # 指标管理
    try:
        from adapters.inbound.fastapi_app.routes.indicators_async import router as indicators_router
        app.include_router(indicators_router)
        logger.info("✅ Registered: indicators")
    except ImportError as e:
        optional_failed.append("indicators")
        logger.warning(f"⚠️ Failed to import indicators_async: {e}")

    # ===== P2 批量路由 =====

    # P1 批量路由（包含多个子路由）
    try:
        from .routes import p1_batch_async
        app.include_router(p1_batch_async.sentiment_router, prefix="/api")
        app.include_router(p1_batch_async.discovery_router, prefix="/api")
        app.include_router(p1_batch_async.game_alert_router, prefix="/api")
        app.include_router(p1_batch_async.chan_router, prefix="/api")
        app.include_router(p1_batch_async.data_quality_router, prefix="/api")
        logger.info("✅ Registered: p1_batch (sentiment, discovery, game_alert, chan, data_quality)")
    except ImportError as e:
        optional_failed.append("p1_batch")
        logger.warning(f"⚠️ Failed to import p1_batch_async: {e}")

    # P2 批量路由 - Batch 1
    try:
        from .routes import p2_batch1_async
        app.include_router(p2_batch1_async.diagnosis_router, prefix="/api")
        app.include_router(p2_batch1_async.dividends_router, prefix="/api")
        app.include_router(p2_batch1_async.financial_router, prefix="/api")
        app.include_router(p2_batch1_async.fund_flow_router, prefix="/api")
        app.include_router(p2_batch1_async.automation_router, prefix="/api")
        app.include_router(p2_batch1_async.agent_intelligence_router, prefix="/api")
        logger.info("✅ Registered: p2_batch1 (diagnosis, dividends, financial, fund_flow, automation, agent_intelligence)")
    except ImportError as e:
        optional_failed.append("p2_batch1")
        logger.warning(f"⚠️ Failed to import p2_batch1_async: {e}")

    # P2 批量路由 - Batch 2
    try:
        from .routes import p2_batch2_async
        app.include_router(p2_batch2_async.ml_model_router, prefix="/api")
        app.include_router(p2_batch2_async.position_router, prefix="/api")
        app.include_router(p2_batch2_async.industry_router, prefix="/api")
        app.include_router(p2_batch2_async.concept_router, prefix="/api")
        app.include_router(p2_batch2_async.utils_router, prefix="/api")
        logger.info("✅ Registered: p2_batch2 (ml_model, position, industry, concept, utils)")
    except ImportError as e:
        optional_failed.append("p2_batch2")
        logger.warning(f"⚠️ Failed to import p2_batch2_async: {e}")

    # 定时任务管理
    try:
        from adapters.inbound.fastapi_app.routes.scheduler_async import router as scheduler_router
        app.include_router(scheduler_router)
        logger.info("✅ Registered: scheduler")
    except ImportError as e:
        optional_failed.append("scheduler")
        logger.warning(f"⚠️ Failed to import scheduler_async: {e}")

    # （scheduler_webhook 已在 CRITICAL 路由部分注册，此处跳过）

    # Agent 决策执行 API
    try:
        from adapters.inbound.fastapi_app.routes.agent_decision_async import router as agent_decision_router
        app.include_router(agent_decision_router)
        logger.info("✅ Registered: agent_decision (Agent决策执行: /api/agent/*)")
    except ImportError as e:
        optional_failed.append("agent_decision")
        logger.warning(f"⚠️ Failed to import agent_decision_async: {e}")

    # 任务管理（P4 迁移，jobs）
    try:
        from adapters.inbound.fastapi_app.routes.jobs_async import router as jobs_router
        app.include_router(jobs_router)
        logger.info("✅ Registered: jobs (P4 迁移)")
    except ImportError as e:
        optional_failed.append("jobs")
        logger.warning(f"⚠️ Failed to import jobs_async: {e}")

    # ===== 游戏智能模块 =====
    try:
        from adapters.inbound.fastapi_app.routes.game.intelligence import router as game_intelligence_router
        app.include_router(game_intelligence_router)
        logger.info("✅ Registered: game.intelligence")
    except ImportError as e:
        optional_failed.append("game.intelligence")
        logger.warning(f"⚠️ Failed to import game.intelligence: {e}")

    # 流水线杂项（cli/calibrate、cli/signal-generate、stocks/data-status，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.pipeline_misc_async import router as pipeline_misc_router
        app.include_router(pipeline_misc_router)
        logger.info("✅ Registered: pipeline_misc (agent 迁移)")
    except ImportError as e:
        optional_failed.append("pipeline_misc")
        logger.warning(f"⚠️ Failed to import pipeline_misc_async: {e}")

    # 工具自省（tools/list、tools/describe，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.tools_async import router as tools_router
        app.include_router(tools_router)
        logger.info("✅ Registered: tools (agent 迁移)")
    except ImportError as e:
        optional_failed.append("tools")
        logger.warning(f"⚠️ Failed to import tools_async: {e}")

    # 训练报告（training/reports、training/history，agent 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.training_async import router as training_router
        app.include_router(training_router)
        logger.info("✅ Registered: training (agent 迁移)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import training_async: {e}")
        optional_failed.append("training")

    # 线程监控（monitoring/threads）
    try:
        from adapters.inbound.fastapi_app.routes.thread_monitoring_async import router as thread_monitoring_router
        app.include_router(thread_monitoring_router)
        logger.info("✅ Registered: thread_monitoring")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import thread_monitoring_async: {e}")
        optional_failed.append("thread_monitoring")

    # ===== 路由注册总结 =====
    logger.info("=" * 60)
    logger.info("Route Registration Summary")
    logger.info("=" * 60)
    logger.info(f"✅ CRITICAL routes: {len(critical_routes)}/{len(critical_routes)} (all must succeed)")
    logger.info(f"   Routes: {', '.join(critical_routes)}")
    
    if optional_failed:
        logger.warning(f"⚠️  Optional routes: some failed ({len(optional_failed)} failures)")
        logger.warning(f"   Failed: {', '.join(optional_failed)}")
        logger.warning(f"   Note: Application will continue with reduced functionality")
    else:
        logger.info(f"✅ Optional routes: all registered successfully")
    
    logger.info("=" * 60)
    logger.info("✅ Route registration completed")
    logger.info("=" * 60)


# 注册所有路由
register_routes()

# 同步路由 ORM session 清理包装（必须在 register_routes 之后）
install_sync_session_cleanup()


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
