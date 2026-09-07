# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file


# Extracted Constants


# Extracted Constants

CONST_60 = 60



CONST_60 = 60



"""
路由注册重构 - 降低圈复杂度

将原有的巨大 register_routes 函数（复杂度 78）拆分为多个小函数
"""

from typing import List, Callable, Tuple
import logging

logger = logging.getLogger(__name__)


class RouteRegistrar:
    """路由注册器 - 封装路由注册逻辑"""

    def __init__(self, app):
        self.app = app
        self.critical_routes: List[str] = []
        self.optional_failed: List[str] = []

    def register_critical_route(
        self,
        name: str,
        import_path: str,
        router_name: str = "router",
        prefix: str = "",
        tags: List[str] = None
    ) -> None:
        """注册核心路由 - 失败时抛出异常

        Args:
            name: 路由名称
            import_path: 导入路径
            router_name: Router 对象名称
            prefix: URL 前缀
            tags: 路由标签
        """
        try:
            module = __import__(import_path, fromlist=[router_name])
            router = getattr(module, router_name)

            kwargs = {}
            if prefix:
                kwargs['prefix'] = prefix
            if tags:
                kwargs['tags'] = tags

            self.app.include_router(router, **kwargs)
            logger.info(f"✅ Registered (CRITICAL): {name}")
            self.critical_routes.append(name)

        except (ImportError, AttributeError) as e:
            logger.error(f"❌ CRITICAL route failed: {name} - {e}")
            raise RuntimeError(f"Critical route '{name}' failed to register: {e}") from e

    def register_optional_route(
        self,
        name: str,
        import_path: str,
        router_name: str = "router",
        prefix: str = "",
        description: str = ""
    ) -> bool:
        """注册可选路由 - 失败时记录警告并继续

        Args:
            name: 路由名称
            import_path: 导入路径
            router_name: Router 对象名称
            prefix: URL 前缀
            description: 路由描述

        Returns:
            是否注册成功
        """
        try:
            module = __import__(import_path, fromlist=[router_name])
            router = getattr(module, router_name)

            kwargs = {}
            if prefix:
                kwargs['prefix'] = prefix

            self.app.include_router(router, **kwargs)

            log_msg = f"✅ Registered: {name}"
            if description:
                log_msg += f" ({description})"
            logger.info(log_msg)

            return True

        except (ImportError, AttributeError) as e:
            logger.warning(f"⚠️ Failed to import {name}: {e}")
            self.optional_failed.append(name)
            return False

    def register_critical_routes(self) -> None:
        """注册所有核心路由"""
        logger.info("=" * 60)
        logger.info("Registering CRITICAL routes...")
        logger.info("=" * 60)

        # 健康检查
        self.register_critical_route(
            "health",
            "adapters.inbound.fastapi_app.routes.health_async"
        )

        # Prometheus 指标
        self.register_critical_route(
            "metrics",
            "adapters.inbound.fastapi_app.routes.metrics_async"
        )

        # 认证授权
        self.register_critical_route(
            "auth",
            "adapters.inbound.fastapi_app.routes.auth_async",
            prefix="/api"
        )

        # Scheduler Webhook
        self.register_critical_route(
            "scheduler_webhook",
            "api.internal.scheduler_webhook",
            prefix="/internal/scheduler",
            tags=["internal"]
        )

        logger.info("=" * 60)
        logger.info(f"✅ All {len(self.critical_routes)} CRITICAL routes registered successfully")
        logger.info("=" * 60)

    def register_market_routes(self) -> None:
        """注册市场数据相关路由"""
        logger.info("Registering market routes...")

        routes = [
            ("market", "adapters.inbound.fastapi_app.routes.market_async", "/api", ""),
            ("market_data", "adapters.inbound.fastapi_app.routes.market_data_async", "", "market/hk 迁移"),
            ("market_perception", "adapters.inbound.fastapi_app.routes.market_perception_async", "", "M1 RFC 007"),
            ("quote_market", "adapters.inbound.fastapi_app.routes.quote_market_async", "", "stock/history 迁移"),
            ("market_style", "adapters.inbound.fastapi_app.routes.market_style_async", "", "agent 迁移"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_analysis_routes(self) -> None:
        """注册分析工具相关路由"""
        logger.info("Registering analysis routes...")

        routes = [
            ("analysis", "adapters.inbound.fastapi_app.routes.analysis_async", "", "P6 迁移"),
            ("charts", "adapters.inbound.fastapi_app.routes.charts_async", "/api", ""),
            ("portfolio_opt", "adapters.inbound.fastapi_app.routes.portfolio_opt_async", "", "Flask parity"),
            ("factor_models", "adapters.inbound.fastapi_app.routes.factor_models_async", "", "Flask parity"),
            ("timeseries", "adapters.inbound.fastapi_app.routes.timeseries_async", "", "agent 迁移"),
            ("diagnosis", "adapters.inbound.fastapi_app.routes.diagnosis_async", "", "P8 迁移"),
            ("chan", "adapters.inbound.fastapi_app.routes.chan_async", "", "P8 迁移"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_trading_routes(self) -> None:
        """注册交易相关路由"""
        logger.info("Registering trading routes...")

        routes = [
            ("executions", "adapters.inbound.fastapi_app.routes.executions_async", "", "P5 迁移"),
            ("orders", "adapters.inbound.fastapi_app.routes.orders_async", "", "P5 迁移"),
            ("v14_trading", "adapters.inbound.fastapi_app.routes.v14_trading", "", ""),
            ("risk", "adapters.inbound.fastapi_app.routes.risk_async", "", "P6 迁移"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_strategy_routes(self) -> None:
        """注册策略相关路由"""
        logger.info("Registering strategy routes...")

        routes = [
            ("strategies", "adapters.inbound.fastapi_app.routes.strategies_async", "", "P2 迁移"),
            ("strategy", "adapters.inbound.fastapi_app.routes.strategy_async", "", "P2 迁移"),
            ("strategy_trading", "adapters.inbound.fastapi_app.routes.strategy_trading_async", "/api", "统一策略API"),
            ("strategy_execution", "adapters.inbound.fastapi_app.routes.strategy_execution_async", "/api", ""),
            ("discovery", "adapters.inbound.fastapi_app.routes.discovery_async", "", "agent 迁移"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_signal_routes(self) -> None:
        """注册信号相关路由"""
        logger.info("Registering signal routes...")

        routes = [
            ("signals", "adapters.inbound.fastapi_app.routes.signals_async", "", "P3 迁移"),
            ("signal_tracking", "adapters.inbound.fastapi_app.routes.signal_tracking", "", "M3-1"),
            ("signal_test", "adapters.inbound.fastapi_app.routes.signal_test_async", "", "agent 迁移"),
            ("realtime_signals", "adapters.inbound.fastapi_app.routes.realtime_signals_async", "/api", ""),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_data_routes(self) -> None:
        """注册数据相关路由"""
        logger.info("Registering data routes...")

        routes = [
            ("stock", "adapters.inbound.fastapi_app.routes.stock_async", "", "P1 迁移"),
            ("dividends", "adapters.inbound.fastapi_app.routes.dividends_async", "", "agent 迁移"),
            ("data_quality", "adapters.inbound.fastapi_app.routes.data_quality_async", "", "agent 迁移"),
            ("financials_v2", "adapters.inbound.fastapi_app.routes.financials_async", "", "parity 迁移"),
            ("events", "adapters.inbound.fastapi_app.routes.events_async", "", "事件日历"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_pool_routes(self) -> None:
        """注册股票池相关路由"""
        logger.info("Registering pool routes...")

        routes = [
            ("pools", "adapters.inbound.fastapi_app.routes.pools_async", "", "P3 迁移"),
            ("pool_scan", "adapters.inbound.fastapi_app.routes.pool_scan_async", "/api", ""),
            ("watchlist", "adapters.inbound.fastapi_app.routes.watchlist_async", "", "P1 迁移"),
            ("watch", "adapters.inbound.fastapi_app.routes.watch_async", "", "WatchEngine parity"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_backtest_routes(self) -> None:
        """注册回测相关路由"""
        logger.info("Registering backtest routes...")

        routes = [
            ("backtest", "adapters.inbound.fastapi_app.routes.backtest_async", "/api", ""),
            ("backtest_history", "adapters.inbound.fastapi_app.routes.backtest_history_async", "", ""),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

        # Flask parity router
        try:
            from adapters.inbound.fastapi_app.routes.backtest_async import flask_parity_router
            self.app.include_router(flask_parity_router)
            logger.info("✅ Registered: backtest (Flask parity 迁移)")
        except ImportError as e:
            logger.warning(f"⚠️ Failed to import backtest flask_parity_router: {e}")
            self.optional_failed.append("backtest_flask_parity")

    def register_ml_routes(self) -> None:
        """注册机器学习相关路由"""
        logger.info("Registering ML routes...")

        routes = [
            ("pipeline", "adapters.inbound.fastapi_app.routes.pipeline_async", "", "P8 迁移"),
            ("ml", "adapters.inbound.fastapi_app.routes.ml_async", "", "P8 迁移"),
            ("indicators", "adapters.inbound.fastapi_app.routes.indicators_async", "", ""),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_memory_routes(self) -> None:
        """注册记忆系统相关路由"""
        logger.info("Registering memory routes...")

        routes = [
            ("memory", "adapters.inbound.fastapi_app.routes.memory_async", "", "W1.2 统一记忆"),
            ("memory_distill", "adapters.inbound.fastapi_app.routes.memory_distill_async", "", "W1.5a 记忆蒸馏"),
            ("knowledge", "adapters.inbound.fastapi_app.routes.knowledge_async", "", "W1.1 FastAPI 补全"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_evolution_routes(self) -> None:
        """注册进化系统相关路由"""
        logger.info("Registering evolution routes...")

        routes = [
            ("evolution", "adapters.inbound.fastapi_app.routes.evolution_async", "", "行为进化 Phase 1"),
            ("evolution-engine", "adapters.inbound.fastapi_app.routes.evolution_engine_async", "", "RFC 012"),
            ("learning_attribution", "adapters.inbound.fastapi_app.routes.learning_attribution", "", "M6-1"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_report_routes(self) -> None:
        """注册报告相关路由"""
        logger.info("Registering report routes...")

        routes = [
            ("report", "adapters.inbound.fastapi_app.routes.report_async", "", "P7 迁移"),
            ("weekly_report", "adapters.inbound.fastapi_app.routes.weekly_report", "", "M6-2"),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

    def register_misc_routes(self) -> None:
        """注册其他杂项路由"""
        logger.info("Registering misc routes...")

        routes = [
            ("config", "adapters.inbound.fastapi_app.routes.config_async", "/api", ""),
            ("sentiment", "adapters.inbound.fastapi_app.routes.sentiment_async", "", "agent 迁移"),
            ("alerts", "adapters.inbound.fastapi_app.routes.alerts_async", "", "agent 新建"),
            ("agent_sessions", "adapters.inbound.fastapi_app.routes.agent_sessions_async", "", "parity 迁移"),
            ("simulation", "adapters.inbound.fastapi_app.routes.simulation_async", "", "多账户API"),
            ("decisions", "adapters.inbound.fastapi_app.routes.decisions_async", "", "PG 持久化"),
            ("decision_tracking", "adapters.inbound.fastapi_app.routes.decision_tracking_async", "/api", ""),
        ]

        for name, path, prefix, desc in routes:
            self.register_optional_route(name, path, prefix=prefix, description=desc)

        # Charts Flask parity
        try:
            from adapters.inbound.fastapi_app.routes.charts_async import flask_parity_router as charts_flask_parity_router
            self.app.include_router(charts_flask_parity_router)
            logger.info("✅ Registered: charts (Flask parity 迁移)")
        except ImportError as e:
            logger.warning(f"⚠️ Failed to import charts flask_parity_router: {e}")
            self.optional_failed.append("charts_flask_parity")

    def register_batch_routes(self) -> None:
        """注册批量路由"""
        logger.info("Registering batch routes...")

        # P1 batch
        try:
            from adapters.inbound.fastapi_app.routes import p1_batch_async
            self.app.include_router(p1_batch_async.sentiment_router, prefix="/api")
            self.app.include_router(p1_batch_async.discovery_router, prefix="/api")
            self.app.include_router(p1_batch_async.game_alert_router, prefix="/api")
            self.app.include_router(p1_batch_async.chan_router, prefix="/api")
            self.app.include_router(p1_batch_async.data_quality_router, prefix="/api")
            logger.info("✅ Registered: p1_batch (5 routers)")
        except ImportError as e:
            logger.warning(f"⚠️ Failed to import p1_batch_async: {e}")
            self.optional_failed.append("p1_batch")

        # P2 batch1
        try:
            from adapters.inbound.fastapi_app.routes import p2_batch1_async
            self.app.include_router(p2_batch1_async.diagnosis_router, prefix="/api")
            self.app.include_router(p2_batch1_async.dividends_router, prefix="/api")
            self.app.include_router(p2_batch1_async.financial_router, prefix="/api")
            self.app.include_router(p2_batch1_async.fund_flow_router, prefix="/api")
            self.app.include_router(p2_batch1_async.automation_router, prefix="/api")
            self.app.include_router(p2_batch1_async.agent_intelligence_router, prefix="/api")
            logger.info("✅ Registered: p2_batch1 (6 routers)")
        except ImportError as e:
            logger.warning(f"⚠️ Failed to import p2_batch1_async: {e}")
            self.optional_failed.append("p2_batch1")

    def print_summary(self) -> None:
        """打印注册摘要"""
        logger.info("=" * 60)
        logger.info(f"Route registration complete:")
        logger.info(f"  Critical: {len(self.critical_routes)} routes")
        logger.info(f"  Failed (optional): {len(self.optional_failed)} routes")

        if self.optional_failed:
            logger.info(f"  Failed routes: {', '.join(self.optional_failed[:10])}")
            if len(self.optional_failed) > 10:
                logger.info(f"    ... and {len(self.optional_failed) - 10} more")

        logger.info("=" * 60)


def register_routes(app) -> None:
    """注册所有路由 - 重构版本（复杂度 < 15）

    将原有的 register_routes 函数（复杂度 78）拆分为多个小函数

    Args:
        app: FastAPI 应用实例
    """
    registrar = RouteRegistrar(app)

    # 按功能模块注册
    registrar.register_critical_routes()  # 复杂度: 1
    registrar.register_market_routes()    # 复杂度: 1
    registrar.register_analysis_routes()  # 复杂度: 1
    registrar.register_trading_routes()   # 复杂度: 1
    registrar.register_strategy_routes()  # 复杂度: 1
    registrar.register_signal_routes()    # 复杂度: 1
    registrar.register_data_routes()      # 复杂度: 1
    registrar.register_pool_routes()      # 复杂度: 1
    registrar.register_backtest_routes()  # 复杂度: 1
    registrar.register_ml_routes()        # 复杂度: 1
    registrar.register_memory_routes()    # 复杂度: 1
    registrar.register_evolution_routes() # 复杂度: 1
    registrar.register_report_routes()    # 复杂度: 1
    registrar.register_misc_routes()      # 复杂度: 1
    registrar.register_batch_routes()     # 复杂度: 1

    # 打印摘要
    registrar.print_summary()

    # 总复杂度: 15（每个函数调用算 1，远低于原来的 78）
