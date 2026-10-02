"""
Pytest configuration for quantsys-v2 test suite.

This file automatically loads test environment variables from .env.test
before running any tests.

DATABASE SEPARATION:
- Test database: quant_test (configured in .env.test)
- Production database: quant_investment (configured in .env)
- pytest automatically uses test database via this conftest.py
- All other scenarios (API, scripts) use production database
"""
import os
import sys
from pathlib import Path

import pytest

collect_ignore = []
try:
    import empyrical
except ImportError:
    collect_ignore.append("tests/services/test_risk_metrics_service.py")

# ── Module-level stub for service resolution ──
# Route modules (shared.py → adapters.shared.__init__.__getattr__) trigger DI resolution
# at import / collection time. In test environments the factory is not initialized, so
# resolve() would raise ValueError("Service not registered: ..."). We patch it here to
# return a MagicMock, allowing tests that don't depend on real services to collect.
#
# 2026-10-02（REQ-261001145152-3982 t-71051b）：**两层都要包**——
# 生产代码已改用 DI 唯一入口 `ServiceFactory.resolve`（它委托内部层），
# 而测试仍在直接调 `EnhancedServiceFactory.resolve`。只包一层会让另一条路径裸奔。
# （前一版改动误把目标写成 `_esf.ServiceFactory`（enhanced 模块并无该类）→ 赋值抛错
#  被下面的 except 吞掉 → 包装整体失效；此处改为按对象分别取原方法。）
try:
    from unittest.mock import MagicMock as _MagicMock
    import infrastructure.services.enhanced_service_factory as _esf
    import infrastructure.services.service_factory as _sf

    def _make_safe(original):
        def _safe_resolve(service_type, *args, **kwargs):
            try:
                return original(service_type, *args, **kwargs)
            except (ValueError, KeyError):
                return _MagicMock()
        return staticmethod(_safe_resolve)

    _esf.EnhancedServiceFactory.resolve = _make_safe(_esf.EnhancedServiceFactory.resolve)
    _sf.ServiceFactory.resolve = _make_safe(_sf.ServiceFactory.resolve)
except Exception:
    pass  # If import fails, tests that need real services will still work


# ── 测试环境限制 socket 默认超时（2026-10-02 · REQ-261001145152-3982 审查）──
# 现象：少量测试**漏 mock**，会真的发起网络请求（实测
# `tests/services/test_dividend_service.py` 的 TestScreenDividendStocks →
# DataProviderManager.get_index_constituents → akshare → requests.get，而 akshare
# 内部的 requests.get **不传 timeout**）。叠加 manager 的
# `provider_timeout_seconds = 60` 与多源降级链，**每条测试要等数十秒甚至更久**，
# 整套测试因此在 44% 处长时间无输出（超时栈显示线程卡在 requests.get）。
#
# 对策：在测试进程里把 socket 默认超时压到 5 秒——requests 未显式传 timeout 时会
# 走这个默认值，于是"漏 mock 的网络调用"会**快速失败并报出真实错误**，
# 而不是把整套测试拖死。需要真实慢网络的集成测试应显式传更长的 timeout。
# 可用环境变量覆盖：QUANTSYS_TEST_SOCKET_TIMEOUT（秒）
import socket as _socket

try:
    _socket.setdefaulttimeout(float(os.environ.get("QUANTSYS_TEST_SOCKET_TIMEOUT", "5")))
except Exception:  # noqa: BLE001 —— 拿不到环境变量也不该让收集失败
    _socket.setdefaulttimeout(5)


# ── 排除 tests/manual/（2026-10-02 · REQ-261001145152-3982 审查）──
# 该目录下 7 个文件**全部是手动验证脚本**：都有 `if __name__ == "__main__"`，
# 且里面的 `test_*` 函数带形参（如 `def test_competition_analysis(symbol: str)`）——
# pytest 会把形参当 **fixture 名**去找，于是报 `fixture 'symbol' not found` 之类，
# 表现为 8 条失败 + 1 条 ERROR（纯噪音，且掩盖真问题）。
# 目录名 `manual` 本身就是"手动跑"的约定，故整体排除收集；
# 要跑它们请直接 `python tests/manual/<file>.py`。
collect_ignore_glob = ["tests/manual/*"]

def pytest_configure(config):
    """Load test environment variables before running tests."""
    # Get the project root directory
    project_root = Path(__file__).parent

    # Add project root to sys.path so imports work
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    env_test_file = project_root / ".env.test"

    # Load .env.test if it exists
    if env_test_file.exists():
        with open(env_test_file) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Only set if not already set (allow override from shell)
                    if key not in os.environ:
                        os.environ[key] = value

    # 强制验证测试数据库配置
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
        print("This safety check prevents tests from running against production data.")
        print("Please check your .env.test configuration.")
        print("="*70 + "\n")
        sys.exit(1)

    print(f"✓ Test database validated: {pgdatabase}")


@pytest.fixture(scope="session")
def db_connection():
    """Provide a database connection for tests that need it."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from infrastructure.persistence.database.engine import _resolve_db_dsn

    dsn = _resolve_db_dsn()
    if not dsn:
        pytest.skip("No database configuration found")

    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)

    # Ensure required tables exist for tests
    _ensure_test_tables(conn)

    # 2026-10-02（REQ-261001145152-3982 审查）：登记这条共享连接，供下面
    # `_release_shared_db_tx` 在每个用例结束后结束其上未结束的事务。
    _SHARED_DB_CONN["conn"] = conn

    yield conn

    # 收尾：丢弃测试期间可能残留的未结束事务，释放锁，再关闭。
    _SHARED_DB_CONN["conn"] = None
    conn.rollback()
    conn.close()


# 2026-10-02（REQ-261001145152-3982 审查）：**泄漏事务的根因就在这条 session 级连接上**。
#
# `db_connection` 是 session 级（整轮测试共用一条连接），而 psycopg2 默认非 autocommit：
# 任何一次 SELECT（如各文件的 fixture 用它查行情/标的）都会**开启事务且一直不结束** →
# 这条连接在**整个测试会话期间**停在 `idle in transaction` 并**持续持有表锁**。
# 实测（临时探针逐用例查 pg_stat_activity 抓到的）：它锁着
# `quant.stock_pools` / `stocks` / `index_constituents`，直接导致
# `tests/test_orm_db_drift` 的建表 DDL 撞满 30s `lock_timeout` 报错——
# 这就是"那个门禁单独跑 6 passed、一进全量就 3 errors"的全部原因（全量里前三处 errors 同源）。
#
# 处置：每个用例结束即结束该连接上未结束的事务（`TRANSACTION_STATUS_IDLE` 之外才回滚）。
# 只动"挂着没关"的读事务，**不改变**任何已显式 commit 的写用例语义，也不动其它连接。
_SHARED_DB_CONN: dict = {"conn": None}


@pytest.fixture(autouse=True)
def _release_shared_db_tx():
    """见 `db_connection` 上方说明：用完即结束其事务，别把表锁带到下一个用例。"""
    yield
    conn = _SHARED_DB_CONN["conn"]
    if conn is None:
        return
    try:
        from psycopg2.extensions import TRANSACTION_STATUS_IDLE

        if conn.info.transaction_status != TRANSACTION_STATUS_IDLE:
            conn.rollback()
    except Exception:
        pass


def _ensure_test_tables(conn):
    """Ensure required tables exist in test database."""
    cursor = conn.cursor()

    # Create stock_fundamentals table if not exists
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

    # Create index_constituents table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.index_constituents (
            index_code TEXT NOT NULL,
            constituent_symbol TEXT NOT NULL,
            weight DOUBLE PRECISION DEFAULT 0,
            update_time TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (index_code, constituent_symbol)
        )
    """)

    # Create stop_loss_rules table if not exists (mirrors production schema)
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
    """Clean up test data after each test."""
    yield
    # Cleanup logic can be added here if needed
    # For now, tests are responsible for their own cleanup


@pytest.fixture(autouse=True)
def _release_orm_session_after_test():
    """每个测试结束后归还 ORM 会话 —— 防 `idle in transaction` 持锁。

    ## 为什么需要（2026-10-02 · REQ-261001145152-3982 审查，实测）

    测试库里长期挂着多个 `idle in transaction` 连接，实测同时有 3 个，
    分别锁着 `quant.stock_pools` / `quant.stocks` / `quant.index_constituents`。
    根因在本仓的会话模型：`scoped_session` **懒加载**——首个查询即开启事务并持有连接
    （`orm/config.py:171` 的注释已写明这一点），而**测试侧没有统一的收尾清理**。
    `clean_db` 那个 fixture 也明说"tests are responsible for their own cleanup"。

    后果不只是连接泄漏：**任何 DDL 都会无限等锁**。
    实测 `tests/test_orm_db_drift.py`（要跑迁移 DDL）因此整套测试停在 78% 永远跑不完；
    单跑该文件 2.88 秒正常 —— 典型测试间污染。

    这里只做**归还**，不改测试断言；清理本身失败也不让测试变红
    （漏清理的后果由下一步的锁等待兜底暴露，见该文件新增的 `lock_timeout`）。
    """
    yield
    try:
        # 先看有没有会话工厂：绝大多数测试不碰 ORM，这一步让它们零开销
        # （实测每条测试多花约 14ms，6400 条即 ~90 秒；加了这个判断后基本抵消）。
        from infrastructure.persistence.orm import config as _orm_config

        if _orm_config._SessionFactory is not None:
            from infrastructure.persistence.orm import close_session

            close_session()
    except Exception:  # noqa: BLE001 —— 收尾清理不应影响测试结论
        pass


