"""Test async DSN resolution pytest safety check

2026-10-21（S11 僵尸测试批次 1）重写对准真守卫：
- AsyncConnectionPool 已是 DEPRECATED no-op（__init__ 仅 DeprecationWarning，不起连接），
  旧用例对其注入 dsn= 永远不会触发守卫（DID NOT RAISE，先前 6F 的根因）；
- 守卫逻辑保留在模块级 `_resolve_db_dsn()`（env 优先级：QUANT_DATABASE_URL >
  DATABASE_URL > POSTGRES_DSN；pytest 下 DSN 解析失败回落 config，非测试库名拒绝）；
- 本文件 6 用例全部改打 `_resolve_db_dsn()`，以 monkeypatch 注入 env 模拟旧 dsn= 形参；
- get_config 由用例内打桩，库名回落结果确定性可控（真实 config 对齐由
  tests/infrastructure/config/* 覆盖）。
"""
import sys

import pytest

import qs_kernel.infrastructure.config as kernel_config
from qs_kernel.infrastructure.persistence.database.async_base_repository import (
    TEST_DB_SUFFIX,
    _resolve_db_dsn,
)


def test_resolve_dsn_rejects_production_db_in_pytest(monkeypatch):
    """pytest 环境下 DSN 指向生产库名必须被拒"""
    assert "pytest" in sys.modules

    monkeypatch.setenv("QUANT_DATABASE_URL", "postgresql://user:pass@localhost:5432/production_db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        _resolve_db_dsn()

    assert "Security check failed" in str(exc_info.value)
    assert "production_db" in str(exc_info.value)
    assert TEST_DB_SUFFIX in str(exc_info.value)


def test_resolve_dsn_accepts_test_db_in_pytest(monkeypatch):
    """pytest 环境下测试库名放行，返回 DSN 与注入一致"""
    assert "pytest" in sys.modules

    test_dsn = f"postgresql://user:pass@localhost:5432/quantsys{TEST_DB_SUFFIX}"
    monkeypatch.setenv("QUANT_DATABASE_URL", test_dsn)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    assert _resolve_db_dsn() == test_dsn


def test_resolve_dsn_prevents_bypass_via_pgdatabase_fallback(monkeypatch):
    """
    CRITICAL: DSN 解析失败必须回落校验 config 侧库名

    Attack scenario:
    - DATABASE_URL 指向无库名 DSN（解析不出库名）
    - config 来源库名指向生产库
    - 若无回落校验，此组合可绕过安全检查
    """
    assert "pytest" in sys.modules

    monkeypatch.delenv("QUANT_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/")  # DSN 无库名
    monkeypatch.setenv("PGDATABASE", "production_db")  # 攻击面：库名藏 config 侧

    class _DB:
        database = "production_db"
        async_url = ""

    class _Cfg:
        database = _DB()

    monkeypatch.setattr(kernel_config, "get_config", lambda *a, **k: _Cfg())

    with pytest.raises(RuntimeError) as exc_info:
        _resolve_db_dsn()

    assert "Security check failed" in str(exc_info.value)
    assert "production_db" in str(exc_info.value)


def test_resolve_dsn_validates_pgdatabase_when_dsn_has_no_db_name(monkeypatch):
    """DSN 无库名时回落 config 库名校验：测试库名放行"""
    assert "pytest" in sys.modules

    dsn_no_db = "postgresql://localhost:5432/"
    monkeypatch.delenv("QUANT_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", dsn_no_db)

    class _DB:
        database = f"quantsys{TEST_DB_SUFFIX}"
        async_url = ""

    class _Cfg:
        database = _DB()

    monkeypatch.setattr(kernel_config, "get_config", lambda *a, **k: _Cfg())

    # 应放行（库名以 _test 结尾），且返回原始 DSN
    assert _resolve_db_dsn() == dsn_no_db


def test_resolve_dsn_regex_extracts_db_name_correctly(monkeypatch):
    """DSN 解析：多种合法格式 + _test 后缀库名全部放行"""
    assert "pytest" in sys.modules

    test_cases = [
        f"postgresql://localhost/mydb{TEST_DB_SUFFIX}",
        f"postgresql://user:pass@localhost:5432/mydb{TEST_DB_SUFFIX}",
        f"postgresql://localhost/mydb{TEST_DB_SUFFIX}?sslmode=require",
        f"postgresql://user@host:5432/mydb{TEST_DB_SUFFIX}?connect_timeout=10",
    ]

    for dsn in test_cases:
        monkeypatch.setenv("QUANT_DATABASE_URL", dsn)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("POSTGRES_DSN", raising=False)
        assert _resolve_db_dsn() == dsn


def test_resolve_dsn_rejects_empty_db_name_bypass(monkeypatch):
    """
    CRITICAL: 库名不可判定必须拒绝（防落驱动默认库）

    Attack scenario:
    - DSN 无库名：postgresql://localhost:5432/
    - config 侧也拿不到库名（get_config 失败）
    - 若无空名判定，将悄悄连到默认库（bypass!）
    """
    assert "pytest" in sys.modules

    empty_dsn = "postgresql://localhost:5432/"
    monkeypatch.delenv("QUANT_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", empty_dsn)
    monkeypatch.delenv("PGDATABASE", raising=False)

    def _boom(*args, **kwargs):
        raise RuntimeError("no config available in this test")

    monkeypatch.setattr(kernel_config, "get_config", _boom)

    with pytest.raises(RuntimeError) as exc_info:
        _resolve_db_dsn()

    assert "Cannot determine database name" in str(exc_info.value)
    assert "PGDATABASE is not set" in str(exc_info.value)
