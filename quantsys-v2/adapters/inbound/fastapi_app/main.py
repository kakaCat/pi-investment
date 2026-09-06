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

# Session 清理中间件
from adapters.inbound.fastapi_app.middleware.session_cleanup import SessionCleanupMiddleware

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

    # 初始化 JobRegistry（2026-09-01: scheduler 重构，优先使用 JobRegistry）
    try:
        from application.jobs.registry_setup import register_all_jobs
        register_all_jobs()
        logger.info("✅ JobRegistry initialized (28 jobs registered)")
    except Exception as e:
        logger.error(f"❌ JobRegistry initialization failed: {e}")

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

        # 启用 Session 泄漏检测（开发/测试环境）
        if settings.environment != 'production':
            try:
                from infrastructure.persistence.orm.session_guard import enable_session_guard
                enable_session_guard(timeout=300)  # 5 分钟超时
                logger.info("✅ Session guard enabled (timeout=300s)")
            except Exception as e:
                logger.warning(f"⚠️ Session guard failed: {e}")
    except Exception as e:
        logger.warning(f"⚠️ ORM initialization skipped: {e}")

    # 同步内置策略到数据库
    # 2026-08-30: 临时禁用，疑似触发K线获取导致启动阻塞
    if os.getenv('ENABLE_STRATEGY_SYNC', '').lower() == 'true':
        try:
            from domain.backtest.engine.strategy_factory import StrategyFactory
            from adapters.outbound.repositories import StrategyORMRepository
            StrategyFactory.auto_discover()
            count = StrategyFactory.sync_to_database(StrategyORMRepository())
            logger.info(f"✅ Synced {count} built-in strategies to database")
        except Exception as e:
            logger.warning(f"⚠️ Strategy sync failed: {e}")
    else:
        logger.warning("⚠️ Strategy sync disabled (set ENABLE_STRATEGY_SYNC=true to enable)")

    # WP-15: Agent OS Scheduler Integration (2026-08-16)
    # 注册 quantsys-v2 调度任务到 Agent OS Scheduler（webhook 模式）
    # 注册失败时回退到本地 APScheduler
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

        # 本地 APScheduler 作为备用（仅当 Agent OS 不可用时启动）
        # 2026-09-01: 从手写调度器迁移到 APScheduler 框架
        if not use_agent_os_scheduler:
            try:
                from infrastructure.scheduler.apscheduler_service import APSchedulerService
                from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
                from infrastructure.persistence.orm import get_session
                from infrastructure.config.settings import get_settings

                settings_obj = get_settings()
                db_url = (
                    f"postgresql://{settings_obj.database.pguser}:{settings_obj.database.pgpassword}"
                    f"@{settings_obj.database.pghost}:{settings_obj.database.pgport}/{settings_obj.database.pgdatabase}"
                )

                session = get_session()
                repo = SchedulerRepository(session)

                scheduler_service = APSchedulerService(db_url, repo)
                scheduler_service.start()

                # 保存到 app.state，用于 API 访问和关闭时清理
                app.state.scheduler_service = scheduler_service

                logger.info("✅ APScheduler started (fallback mode)")
            except Exception as e:
                logger.error(f"❌ APScheduler startup failed: {e}")

    # 启动 WatchEngine 实时盯盘线程（2026-08-12 起唯一宿主，原 scheduler_daemon
    # 已下线该职责；pytest 下不启动，避免测试进程拉起盯盘循环）。
    # 引擎句柄挂到 app.state，lifespan 关闭时优雅停止。
    # 2026-08-30: 添加 DISABLE_WATCH_ENGINE 环境变量开关，避免启动阻塞
    if os.getenv('DISABLE_WATCH_ENGINE', '').lower() != 'true':
        try:
            from adapters.inbound.fastapi_app.watch_bootstrap import start_watch_engine
            handles = start_watch_engine(skip='pytest' in _sys.modules)
            if handles is not None:
                app.state.watch_engine = handles[0]
                logger.info("✅ WatchEngine watch thread started")
        except Exception as e:
            logger.error(f"❌ WatchEngine startup failed: {e}")
    else:
        logger.warning("⚠️ WatchEngine disabled via DISABLE_WATCH_ENGINE")

    # 启动 DailyOrchestrator/IntradayMonitor tick 线程（2026-08-13 起唯一宿主，
    # 原 scheduler_daemon 已下线该职责——daemon 08-05 停跑致 T+1 结转静默中断 8 天；
    # pytest 下不启动，避免测试进程拉起调度循环）。
    # 2026-08-30: 添加 DISABLE_ORCHESTRATOR 环境变量开关，避免启动阻塞
    if os.getenv('DISABLE_ORCHESTRATOR', '').lower() != 'true':
        try:
            from adapters.inbound.fastapi_app.orchestrator_bootstrap import start_orchestrator
            orch_handles = start_orchestrator(skip='pytest' in _sys.modules)
            if orch_handles is not None:
                app.state.orchestrator = orch_handles
                logger.info("✅ DailyOrchestrator tick thread started")
        except Exception as e:
            logger.error(f"❌ Orchestrator startup failed: {e}")
    else:
        logger.warning("⚠️ Orchestrator disabled via DISABLE_ORCHESTRATOR")

    # 启动每日数据任务宿主线程（2026-09-02 起唯一宿主：K线同步/因子计算/
    # 筹码分布/数据质量/新鲜度巡检/财报更新。原 Agent OS 调度器中这些任务
    # 全部禁用或 /bin/true 占位，数据新鲜度无保障——实测 K线/因子更新不均。
    # 与 WatchEngine/Orchestrator 同模式：无独立进程 = 不会静默死亡）
    if os.getenv('DISABLE_DAILY_JOBS', '').lower() != 'true':
        try:
            from adapters.inbound.fastapi_app.daily_jobs_bootstrap import start_daily_jobs
            jobs_handle = start_daily_jobs(skip='pytest' in _sys.modules)
            if jobs_handle is not None:
                app.state.daily_jobs = jobs_handle
                logger.info("✅ DailyJobs host thread started")
        except Exception as e:
            logger.error(f"❌ DailyJobs startup failed: {e}")
    else:
        logger.warning("⚠️ DailyJobs disabled via DISABLE_DAILY_JOBS")

    # P2.3: 启动统一调度器（YAML-config-driven）
    if os.getenv('DISABLE_UNIFIED_SCHEDULER', '').lower() != 'true':
        try:
            from infrastructure.scheduler.unified_scheduler import get_scheduler
            unified_scheduler = get_scheduler()
            unified_scheduler.start()
            app.state.unified_scheduler = unified_scheduler
            logger.info("✅ UnifiedScheduler started", jobs_count=len(unified_scheduler.jobs))
        except Exception as e:
            logger.error(f"❌ UnifiedScheduler startup failed: {e}")
    else:
        logger.warning("⚠️ UnifiedScheduler disabled via DISABLE_UNIFIED_SCHEDULER")

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

    # 关闭 APScheduler（2026-09-01）
    scheduler_service = getattr(app.state, 'scheduler_service', None)
    if scheduler_service is not None:
        try:
            scheduler_service.shutdown(wait=True)
            logger.info("✅ APScheduler stopped")
        except Exception as e:
            logger.warning(f"⚠️ APScheduler shutdown failed: {e}")

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
        from infrastructure.persistence.database.engine import dispose_engine
        dispose_engine()
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

# Session 清理中间件（必须最先注册，确保最后执行）
app.add_middleware(SessionCleanupMiddleware)

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

# 导入重构后的路由注册器
from adapters.inbound.fastapi_app.route_registrar import register_routes as register_routes_refactored

def register_routes():
    """注册所有路由 —— 核心路由失败时中断启动"""
    """注册所有路由 - 使用重构后的 RouteRegistrar（复杂度从 78 降至 15）"""
    register_routes_refactored(app)

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
