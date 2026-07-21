"""
QuantSys V2 API 服务 — App Factory

Blueprint 路由:
  api/routes/analysis.py
  api/routes/backtest.py
  ...
"""
import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE any other imports
load_dotenv()

# Ensure quantsys-v2/ is on PYTHONPATH (needed when run directly: python api/server.py)
# File is at quantsys-v2/adapters/inbound/api/server.py, so go up 3 levels
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

# Load .env BEFORE any imports that depend on environment variables
# load_dotenv() will search upwards for .env file automatically
load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS

# 初始化 SQLAlchemy Engine
from infrastructure.persistence.database.engine import init_engine
import logging

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    CORS(app)

    # 初始化 SQLAlchemy Engine (统一连接池管理)
    try:
        init_engine(pool_size=10, max_overflow=20)
        logger.info("✅ SQLAlchemy Engine initialized (pool_size=10, max_overflow=20, capacity=30)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize Engine: {e}")
        logger.warning("Application will create connections on demand (fallback mode)")

    # 初始化 ORM (用于模拟交易等ORM-based功能)
    try:
        from infrastructure.persistence.orm.config import init_orm
        init_orm(pool_size=10, max_overflow=20)
        logger.info("✅ ORM initialized for simulation and other ORM-based features")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize ORM: {e}")
        logger.warning("ORM-based features (simulation) may not work properly")

    # 注册请求级 Session 清理钩子：防止 scoped_session 持有的连接以
    # "idle in transaction" 状态泄漏，耗尽连接池后新请求阻塞 ~30s
    try:
        from infrastructure.persistence.orm.config import register_session_teardown
        register_session_teardown(app)
        logger.info("✅ ORM session teardown registered (per-request connection cleanup)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to register session teardown: {e}")

    # ✅ 初始化依赖注入容器（使用简化版避开类型注解问题）
    try:
        from infrastructure.di.container_simple import SimpleContainer
        container = SimpleContainer()
        app.container = container
        logger.info("✅ Dependency injection container initialized (SimpleContainer)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize DI container: {e}")
        logger.warning("Application will use legacy shared.py services (fallback mode)")

    # ── 注册 blueprints ──

    from adapters.inbound.api.routes.analysis import analysis_bp
    app.register_blueprint(analysis_bp)
    from adapters.inbound.api.routes.backtest import backtest_bp
    app.register_blueprint(backtest_bp)
    from adapters.inbound.api.routes.backtest_history import backtest_history_bp
    app.register_blueprint(backtest_history_bp)
    from adapters.inbound.api.routes.benchmarks import benchmarks_bp
    app.register_blueprint(benchmarks_bp)
    from adapters.inbound.api.routes.chan import chan_bp
    app.register_blueprint(chan_bp)
    from adapters.inbound.api.routes.charts import charts_bp
    app.register_blueprint(charts_bp)
    from adapters.inbound.api.routes.discovery import discovery_bp
    app.register_blueprint(discovery_bp)
    from adapters.inbound.api.routes.dividends import dividends_bp
    from adapters.inbound.api.routes.financials_v2 import financials_v2_bp
    app.register_blueprint(dividends_bp)
    app.register_blueprint(financials_v2_bp)
    from adapters.inbound.api.routes.executions import executions_bp
    app.register_blueprint(executions_bp)
    from adapters.inbound.api.routes.factor_models import factor_models_bp
    app.register_blueprint(factor_models_bp)
    from adapters.inbound.api.routes.health import health_bp
    app.register_blueprint(health_bp)
    from adapters.inbound.api.routes.indicators import indicators_bp
    app.register_blueprint(indicators_bp)
    from adapters.inbound.api.routes.jobs import jobs_bp
    app.register_blueprint(jobs_bp)
    from adapters.inbound.api.routes.market import market_bp
    app.register_blueprint(market_bp)
    from adapters.inbound.api.routes.market_style import market_style_bp
    app.register_blueprint(market_style_bp)
    from adapters.inbound.api.routes.monitoring import monitoring_bp
    app.register_blueprint(monitoring_bp)
    from adapters.inbound.api.routes.orders import orders_bp
    app.register_blueprint(orders_bp)
    from adapters.inbound.api.routes.pipeline import pipeline_bp
    app.register_blueprint(pipeline_bp)
    from adapters.inbound.api.routes.pools import pools_bp
    app.register_blueprint(pools_bp)
    from adapters.inbound.api.routes.pool_scan import pool_scan_bp
    app.register_blueprint(pool_scan_bp)
    from adapters.inbound.api.routes.pool_scan_switch import pool_scan_switch_bp
    app.register_blueprint(pool_scan_switch_bp)
    from adapters.inbound.api.routes.opportunities import opportunities_bp
    app.register_blueprint(opportunities_bp)
    from adapters.inbound.api.routes.portfolio import portfolio_bp
    app.register_blueprint(portfolio_bp)
    from adapters.inbound.api.routes.quote_market import quote_market_bp
    app.register_blueprint(quote_market_bp)
    from adapters.inbound.api.routes.quote_v2 import quote_v2_bp
    app.register_blueprint(quote_v2_bp)
    from adapters.inbound.api.routes.risk import risk_bp
    app.register_blueprint(risk_bp)
    from adapters.inbound.api.routes.scheduler import scheduler_bp
    app.register_blueprint(scheduler_bp)
    from adapters.inbound.api.routes.sectors import sectors_bp
    app.register_blueprint(sectors_bp)
    from adapters.inbound.api.routes.sentiment import sentiment_bp
    app.register_blueprint(sentiment_bp)
    from adapters.inbound.api.routes.signal_execution import signal_execution_bp
    app.register_blueprint(signal_execution_bp)
    from adapters.inbound.api.routes.signals import signals_bp
    app.register_blueprint(signals_bp)
    from adapters.inbound.api.routes.signal_test import signal_test_bp
    app.register_blueprint(signal_test_bp)
    from adapters.inbound.api.routes.stock import stock_bp
    app.register_blueprint(stock_bp)
    from adapters.inbound.api.routes.strategies import strategies_bp
    app.register_blueprint(strategies_bp)
    from adapters.inbound.api.routes.strategy import strategy_bp
    app.register_blueprint(strategy_bp)
    from adapters.inbound.api.routes.strategy_execution import bp as strategy_execution_bp
    app.register_blueprint(strategy_execution_bp)
    from adapters.inbound.api.routes.timeseries import timeseries_bp
    app.register_blueprint(timeseries_bp)
    from adapters.inbound.api.routes.tools import tools_bp
    app.register_blueprint(tools_bp)
    from adapters.inbound.api.routes.training import training_bp
    app.register_blueprint(training_bp)
    from adapters.inbound.api.routes.watchlist import watchlist_bp
    app.register_blueprint(watchlist_bp)
    from adapters.inbound.api.routes.diagnosis import diagnosis_bp
    app.register_blueprint(diagnosis_bp)
    from adapters.inbound.api.routes.data_quality import data_quality_bp
    app.register_blueprint(data_quality_bp)
    from adapters.inbound.api.routes.signals_push import signals_bp as signals_push_bp
    app.register_blueprint(signals_push_bp)
    from adapters.inbound.api.routes.realtime_signals import bp as realtime_signals_bp
    app.register_blueprint(realtime_signals_bp)

    # 游戏智能模块 - 对手行为分析、战场评估、操纵检测
    from adapters.inbound.api.routes.game_intelligence import game_intelligence_bp
    app.register_blueprint(game_intelligence_bp)

    # 博弈智能系统 - 2026-07-19 重新启用（仓储依赖已补齐）
    from adapters.inbound.api.routes.decision_tracking import decision_tracking_bp
    app.register_blueprint(decision_tracking_bp)

    # 知识管理和学习系统 - 已启用（使用mock数据）
    from adapters.inbound.api.routes.knowledge_management import knowledge_management_bp
    app.register_blueprint(knowledge_management_bp)
    from adapters.inbound.api.routes.learning_system import learning_system_bp
    app.register_blueprint(learning_system_bp)

    # 博弈预警系统 - 已启用
    from adapters.inbound.api.routes.game_alert import game_alert_bp
    app.register_blueprint(game_alert_bp)

    from adapters.inbound.api.routes.config import config_bp
    app.register_blueprint(config_bp)

    # ✅ DI 测试路由（用于验证依赖注入是否正常工作）
    from adapters.inbound.api.routes.test_di import test_di_bp
    app.register_blueprint(test_di_bp)

    # ML engine routes (feature engineering + model training via v2 pipeline)
    from adapters.inbound.api.ml_routes import register_ml_routes
    from adapters.inbound.api.shared import ds
    register_ml_routes(app, ds)

    # Simulation routes (模拟交易API)
    from adapters.inbound.api.routes.simulation import simulation_bp
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')

    # 统一策略交易 API（重构版，支持 V13/V14/V15...）
    from adapters.inbound.api.routes.strategy_trading import strategy_bp
    app.register_blueprint(strategy_bp)
    logger.info("✅ 统一策略 API 已注册: /api/strategy/*")

    # V14量化交易 (保留作为兼容层)
    from adapters.inbound.api.routes.v14_trading import v14_bp
    app.register_blueprint(v14_bp)
    logger.info("⚠️ V14 API (兼容): /api/v14/* (建议使用 /api/strategy/v14/*)")

    # Enterprise Scheduler routes (企业级调度器管理API)
    from adapters.inbound.api.routes.scheduler_enterprise import scheduler_enterprise_bp
    app.register_blueprint(scheduler_enterprise_bp)

    # 初始化并注册V13策略
    try:
        from domain.strategies.v13_strategy import create_v13_strategy
        from domain.strategies import get_registry

        v13 = create_v13_strategy()
        registry = get_registry()
        registry.register('v13', v13)
        print("✓ V13 strategy registered")
    except Exception as e:
        print(f"⚠️  Failed to register V13 strategy: {e}")

    # Add basic health check since health_bp is disabled
    @app.route('/api/health')
    def health_check():
        try:
            # Test database connection
            stock_count = ds.stock.count_all()
            return jsonify({
                'status': 'ok',
                'db_connected': True,
                'db_info': {
                    'provider': ds.stock.db_type if hasattr(ds.stock, 'db_type') else 'postgres',
                    'stock_count': stock_count,
                    'version': 'v2'
                }
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'db_connected': False,
                'error': str(e)
            }), 500


    # Simulation web dashboard
    from flask import send_from_directory
    import os
    
    @app.route('/simulation')
    def simulation_dashboard():
        static_dir = os.path.join(os.path.dirname(__file__), '..', 'web', 'static')
        return send_from_directory(static_dir, 'simulation.html')

    return app


# ── 模块级 app 实例（兼容直接 python api/server.py 启动）──
app = create_app()


# ── Spring Boot 风格:启动 Scheduler 后台线程 ──
_scheduler_thread = None

def start_scheduler_background():
    """在后台线程启动 Scheduler 服务(类似 Spring Boot @Scheduled)"""
    global _scheduler_thread

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.info("Scheduler thread already running")
        return

    def _run_scheduler():
        """后台线程:运行 Scheduler 循环"""
        try:
            logger.info("Starting Scheduler background thread...")
            from infrastructure.scheduler.scheduler import SchedulerService
            scheduler = SchedulerService()
            scheduler.run_loop()  # Blocking loop
        except Exception as e:
            logger.error(f"Scheduler thread crashed: {e}", exc_info=True)

    _scheduler_thread = threading.Thread(target=_run_scheduler, name="scheduler-thread", daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler background thread started")


# 应用启动时自动启动 Scheduler(类似 Spring Boot ApplicationRunner)
@app.before_request
def _ensure_scheduler_started():
    """首次请求时启动 Scheduler(延迟初始化,避免影响启动速度)"""
    if not hasattr(app, '_scheduler_initialized'):
        start_scheduler_background()
        app._scheduler_initialized = True


if __name__ == "__main__":
    import os
    import threading

    # 立即启动 Scheduler(不等第一个请求)
    print("=" * 60)
    print("🚀 Starting quantsys-v2 in unified process mode...")
    print("=" * 60)

    # 初始化 Engine
    print("[1/3] Initializing SQLAlchemy Engine...")
    from infrastructure.persistence.database.engine import init_engine
    init_engine(pool_size=10, max_overflow=20)
    print("      ✓ Engine initialized (pool_size=10, max_overflow=20)")

    # 启动 Scheduler 后台线程
    print("[2/3] Starting Scheduler background thread...")
    start_scheduler_background()
    print("      ✓ Scheduler thread started")

    # 启动 Flask API
    print("[3/3] Starting Flask API server...")
    print("=" * 60)
    print("✓ Services ready:")
    print("  - REST API:  http://127.0.0.1:5001")
    print("  - Scheduler: Background thread (checks every 30s)")
    print("  - Health:    http://127.0.0.1:5001/api/health/db")
    print("=" * 60)

    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host="0.0.0.0", port=5001, debug=debug_mode, use_reloader=debug_mode)
