import os
import sys
import types
from pathlib import Path

import pytest


class _Stub(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []
        self.__file__ = "/dev/null"
        self.__spec__ = None

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        return _StubClass(f"{self.__name__}.{attr}")


class _StubClass:
    def __init__(self, name):
        self._name = name

    def __call__(self, *a, **kw):
        raise ImportError(f"Module under test was removed: {self._name}")

    def __getattr__(self, attr):
        return _StubClass(f"{self._name}.{attr}")

    def __mro_entries__(self, bases):
        return (object,)


_DEAD_MODULES = [
    "domain.quantlib.adapters.base_adapter",
    "domain.quantlib.adapters.eastmoney_adapter",
    "domain.quantlib.adapters.factor_calculator_adapter",
    "domain.quantlib.adapters.factory",
    "domain.quantlib.backtest.market_impact",
    "domain.quantlib.backtest.walk_forward",
    "domain.quantlib.core.base_calculator",
    "domain.quantlib.core.config",
    "domain.quantlib.core.data_cleaning",
    "domain.quantlib.core.data_validator",
    "domain.quantlib.core.exceptions",
    "domain.quantlib.core.pipeline",
    "domain.quantlib.core.portfolio_calculator",
    "domain.quantlib.core.validators",
    "domain.quantlib.engine.backtest_report",
    "domain.quantlib.engine.backtrader.backtrader_engine",
    "domain.quantlib.engine.backtrader.data_feed",
    "domain.quantlib.engine.commission",
    "domain.quantlib.engine.donchian_channel_strategy",
    "domain.quantlib.engine.indicator_strategy_executor",
    "domain.quantlib.engine.momentum_strategy",
    "domain.quantlib.engine.position_sizing",
    "domain.quantlib.engine.risk_rules",
    "domain.quantlib.engine.slippage",
    "domain.quantlib.engine.stress_test",
    "domain.quantlib.engine.strategy_base",
    "domain.quantlib.engine.strategy_runner",
    "domain.quantlib.engine.turtle_strategy",
    "domain.quantlib.engine.volatility_breakout_strategy",
    "domain.quantlib.factor_analysis.ic_analyzer",
    "domain.quantlib.factor_analysis.layering_backtest",
    "domain.quantlib.factor_analysis.orthogonalizer",
    "domain.quantlib.factors.fundamental",
    "domain.quantlib.factors.momentum",
    "domain.quantlib.factors.moving_average",
    "domain.quantlib.factors.other",
    "domain.quantlib.factors.reversal",
    "domain.quantlib.factors.trend",
    "domain.quantlib.factors.volatility",
    "domain.quantlib.factors.volume",
    "domain.quantlib.risk.aggregation",
    "domain.quantlib.risk.attribution",
    "domain.quantlib.risk.counterparty_risk",
    "domain.quantlib.risk.cvar",
    "domain.quantlib.risk.regulatory",
    "domain.quantlib.risk.backtesting",
    "domain.quantlib.risk.margining",
    "domain.quantlib.risk.reporting",
    "domain.quantlib.risk.risk_monitor",
    "domain.quantlib.risk.var",
    "domain.quantlib.stages.backtest_stage",
    "domain.quantlib.stages.data_pipeline.anomaly_detection_stage",
    "domain.quantlib.stages.data_pipeline.conflict_resolution_stage",
    "domain.quantlib.stages.data_pipeline.data_fetch_stage",
    "domain.quantlib.stages.data_pipeline.deduplication_stage",
    "domain.quantlib.stages.data_pipeline.factor_compute_stage",
    "domain.quantlib.stages.data_pipeline.imputation_stage",
    "domain.quantlib.stages.data_pipeline.storage_stage",
    "domain.quantlib.stages.data_pipeline.time_alignment_stage",
    "domain.quantlib.stages.factor_stage",
    "domain.quantlib.stages.model_stage",
    "domain.quantlib.stages.risk_stage",
    "domain.brokers.adapters.akshare_broker",
    "adapters.inbound.api",
]

collect_ignore = [
    "tests/domain/memory/",
    "tests/quantlib/test_talib_bridge.py",
    "tests/services/test_risk_metrics_service.py",
    "tests/test_factor_library_connection.py",
    "tests/test_redis_cache.py",
    "tests/test_response_utils.py",
    "tests/test_websocket.py",
    "tests/api/test_signals_list_route.py",
]


def pytest_configure(config):
    for mod in _DEAD_MODULES:
        if mod not in sys.modules:
            sys.modules[mod] = _Stub(mod)

    parent_modules = [
        "domain.quantlib.stages.data_pipeline",
        "domain.quantlib.adapters",
    ]
    for pm in parent_modules:
        if pm not in sys.modules:
            sys.modules[pm] = _Stub(pm)

    _load_env(config)


def _load_env(config):
    project_root = Path(__file__).parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    env_test_file = project_root / ".env.test"
    if env_test_file.exists():
        with open(env_test_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    if key not in os.environ:
                        os.environ[key] = value

    pgdatabase = os.environ.get("PGDATABASE", "")
    if not pgdatabase:
        print("\n" + "="*70)
        print("ERROR: PGDATABASE environment variable is not set!")
        print("Please ensure .env.test exists and contains PGDATABASE=quant_test")
        print("="*70 + "\n")
        sys.exit(1)

    if not pgdatabase.endswith("_test"):
        print("\n" + "="*70)
        print("ERROR: Test database validation failed!")
        print(f"Current PGDATABASE: {pgdatabase}")
        print("Test database name must end with '_test' (e.g., 'quant_test')")
        print("="*70 + "\n")
        sys.exit(1)

    print(f"✓ Test database validated: {pgdatabase}")


@pytest.fixture(scope="session")
def db_connection():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from infrastructure.persistence.database.engine import _resolve_db_dsn

    dsn = _resolve_db_dsn()
    if not dsn:
        pytest.skip("No database configuration found")

    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    _ensure_test_tables(conn)
    yield conn
    conn.close()


def _ensure_test_tables(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.stock_fundamentals (
            symbol TEXT PRIMARY KEY,
            pe_ratio DOUBLE PRECISION,
            roe DOUBLE PRECISION,
            gross_margin DOUBLE PRECISION,
            debt_ratio DOUBLE PRECISION,
            update_time DATE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.index_constituents (
            index_code TEXT NOT NULL,
            constituent_symbol TEXT NOT NULL,
            weight DOUBLE PRECISION DEFAULT 0,
            update_time TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (index_code, constituent_symbol)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.stop_loss_rules (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('fixed_price', 'fixed_percent', 'trailing_stop')),
            stop_loss_percent REAL,
            trailing_percent REAL,
            atr_multiplier REAL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive', 'triggered')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()


@pytest.fixture(scope="function")
def clean_db(db_connection):
    yield
