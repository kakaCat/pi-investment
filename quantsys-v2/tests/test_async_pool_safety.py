"""pytest 生产库守卫测试（同步/异步轨共用）

## 为什么重写（2026-10-02 · REQ-261001145152-3982 审查）

原文件测的是 `async_base_repository.AsyncConnectionPool` —— 那个类早被掏空成 no-op 壳
（`__init__` 只发一条 DeprecationWarning），而 6 条测试仍在按**已删除的实现**断言
（要 `pool.dsn`、要抛 "Cannot determine database name"）→ **6 条全失败**，
而且它们已不再保护任何东西：真实守卫早就搬到别处了。

本文件改测**真正生效的守卫** `engine.assert_test_db_in_pytest`（同步/异步轨共用），
并新增一条集成测试锁住本次修掉的漏洞：
`init_async_engine(dsn=...)` **显式**传 DSN 原先完全跳过守卫（实测可连生产库）——
即 CLAUDE.md 声称的"三层防护"在异步轨的缺口。6 条原始意图逐条保留，一一对应如下：

| 原用例 | 本文件 |
|---|---|
| rejects_production_db_in_pytest | test_rejects_production_db_in_pytest |
| accepts_test_db_in_pytest | test_accepts_test_db_in_pytest |
| prevents_bypass_via_pgdatabase_fallback | test_rejects_when_config_falls_back_to_production_name |
| validates_pgdatabase_when_dsn_has_no_db_name | 同上（改为确定性的配置替身） |
| regex_extracts_db_name_correctly | test_regex_extracts_db_name_from_various_dsn_forms |
| rejects_empty_db_name_bypass | test_rejects_when_db_name_cannot_be_determined |
| （新增）本次修复的回归锁 | test_init_async_engine_guards_explicit_dsn |
"""
import asyncio
import sys
import types

import infrastructure.config as config_mod

import pytest

from infrastructure.persistence.database import async_engine as async_engine_mod
from infrastructure.persistence.database.engine import (
    TEST_DB_SUFFIX,
    assert_test_db_in_pytest,
)


def _config_with_db_name(db_name: str):
    """构造最小配置替身（守卫只读 config.database.database）"""
    cfg = types.SimpleNamespace()
    cfg.database = types.SimpleNamespace(database=db_name)
    return cfg


def test_rejects_production_db_in_pytest():
    """pytest 环境下生产库 DSN 必须被拒"""
    assert "pytest" in sys.modules

    with pytest.raises(RuntimeError) as exc_info:
        assert_test_db_in_pytest("postgresql://user:pass@localhost:5432/production_db")

    msg = str(exc_info.value)
    assert "Security check failed" in msg
    assert "production_db" in msg
    assert TEST_DB_SUFFIX in msg


def test_accepts_test_db_in_pytest():
    """pytest 环境下测试库 DSN 必须放行"""
    assert "pytest" in sys.modules

    # 不抛即通过（原用例断言 pool.dsn == dsn，那个对象已不存在）
    assert_test_db_in_pytest(f"postgresql://user:pass@localhost:5432/quantsys{TEST_DB_SUFFIX}")


def test_rejects_when_config_falls_back_to_production_name(monkeypatch):
    """DSN 里取不到库名时回退配置；配置给的是生产库名 → 必须拒绝

    （原用例用 monkeypatch PGDATABASE 制造"绕过"场景；这里改为替换配置替身，
    判定与"配置回退"这条真实逻辑一一对应，且不依赖环境变量是否被配置层读取。）
    """
    monkeypatch.setattr(config_mod, "get_config", lambda: _config_with_db_name("production_db"))

    with pytest.raises(RuntimeError) as exc_info:
        assert_test_db_in_pytest("postgresql://localhost/")  # 无库名

    msg = str(exc_info.value)
    assert "Security check failed" in msg
    assert "production_db" in msg


def test_rejects_when_db_name_cannot_be_determined(monkeypatch):
    """DSN 无库名 + 配置也取不到 → 必须拒绝（否则会连到默认库，等于绕过）"""
    monkeypatch.setattr(config_mod, "get_config", lambda: _config_with_db_name(""))

    with pytest.raises(RuntimeError) as exc_info:
        assert_test_db_in_pytest("postgresql://localhost:5432/")

    msg = str(exc_info.value)
    assert "Security check failed" in msg
    assert "cannot determine" in msg


def test_regex_extracts_db_name_from_various_dsn_forms():
    """各种 DSN 形态都要能正确取出库名（带/不带 user、port、query 参数）"""
    assert "pytest" in sys.modules

    test_cases = [
        f"postgresql://localhost/mydb{TEST_DB_SUFFIX}",
        f"postgresql://user:pass@localhost:5432/mydb{TEST_DB_SUFFIX}",
        f"postgresql://localhost/mydb{TEST_DB_SUFFIX}?sslmode=require",
        f"postgresql://user@host:5432/mydb{TEST_DB_SUFFIX}?connect_timeout=10",
    ]
    for dsn in test_cases:
        assert_test_db_in_pytest(dsn)  # 不抛即通过

    # 反向：同样形态但库名不是 _test → 必须拒绝（证明取到的是库名而非别的片段）
    with pytest.raises(RuntimeError):
        assert_test_db_in_pytest("postgresql://user:pass@localhost:5432/mydb?sslmode=require")


def test_init_async_engine_guards_explicit_dsn(monkeypatch):
    """**本次修复的回归锁**：显式传 DSN 也必须过守卫

    修前行为：`init_async_engine(dsn=...)` 只在 `dsn is None` 时才走带守卫的解析器，
    显式传生产库 DSN **直接跳过校验**（实测未被拒绝）。
    """
    # 让"已初始化"短路不生效，确保走到守卫（否则会直接 return 既有引擎而假通过）
    monkeypatch.setattr(async_engine_mod, "_async_engine_initialized", False)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            async_engine_mod.init_async_engine(
                dsn="postgresql+asyncpg://user@127.0.0.1/quant_investment"
            )
        )

    assert "Security check failed" in str(exc_info.value)
