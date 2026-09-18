"""测试库结构固化 + 串行保障（REQ-c9f899 返工 D，2026-09-18）。

背景（implementation.md §5.2）：t1/t3 新增的盯盘表与列此前只在 quant_test 被
**人工补过一次**，不可复现 —— 干净环境下 watch 测试会因缺表缺列而红，而本机绿，
于是"绿与红都不算证据"。

本 conftest 只做三件事（都不碰业务代码）：

  1. **_bootstrap_test_db_schema**（session 级、autouse、尽力而为）：跑
     tests/_db_schema_sync.sync_test_schema()，把 t1/t3 的表与列幂等同步到测试库。
     任何按本套件惯例连不上测试库的场景（纯单测）只告警不阻断。
  2. **db_schema_synced**（session 级、严格）：需要盯盘结构保证的用例显式依赖它，
     同步失败即响亮报错——绝不把"缺表"伪装成"通过"。
  3. **watch_db_advisory_lock**（session 级 PostgreSQL advisory lock）：把**协作进程**
     的全量门禁串行化（同仓其它窗口跑同一套件时互斥）。拿不到锁只告警降级，
     绝不无限阻塞；非协作写入者无法被它约束（诚实边界，见返工 D 汇报）。

外加登记 `serial` marker（pytest.ini 开了 --strict-markers，自定义 marker 必须显式登记）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_configure(config):
    """登记自定义 marker（--strict-markers 下必须显式登记，否则收集即报错）。"""
    config.addinivalue_line(
        "markers",
        "serial: 写测试库共享结构/数据的用例，必须串行执行，不得与并发写入者同跑",
    )


#: 所有协作进程共用的 advisory lock key（任意固定 bigint；仅本仓测试使用）
_WATCH_DB_LOCK_KEY = 728134221300519001


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_test_db_schema():
    """尽力同步测试库盯盘结构；失败只告警，不阻断（纯单测仍可运行）。"""
    import warnings

    try:
        from tests._db_schema_sync import sync_test_schema
        sync_test_schema()
    except Exception as exc:  # noqa: BLE001 —— 结构同步失败不应连坐非 DB 用例
        warnings.warn(
            "测试库盯盘结构同步失败（依赖该结构的用例会各自响亮失败）：%r" % (exc,),
            stacklevel=1,
        )
    yield


@pytest.fixture(scope="session")
def db_schema_synced(_bootstrap_test_db_schema):
    """严格版结构同步：失败即抛错。需要盯盘表结构的用例显式依赖本 fixture。"""
    from tests._db_schema_sync import sync_test_schema
    return sync_test_schema()


@pytest.fixture(scope="session")
def watch_db_advisory_lock(_bootstrap_test_db_schema):
    """协作进程间的测试库串行锁（session 级 advisory lock，尽力获取）。

    拿不到（等待超过 30s）只告警降级，绝不无限阻塞——门禁的可复现性优先于
    对"非协作写入者"的强行互斥（后者无法从测试侧保证，属已登记的诚实边界）。
    """
    import time
    import warnings

    from infrastructure.persistence.database.engine import get_engine

    conn = None
    cursor = None
    acquired = False
    try:
        conn = get_engine().raw_connection()
        cursor = conn.cursor()
        deadline = time.monotonic() + 30.0
        while True:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (_WATCH_DB_LOCK_KEY,))
            acquired = bool(cursor.fetchone()[0])
            conn.commit()
            if acquired or time.monotonic() >= deadline:
                break
            time.sleep(0.5)
        if not acquired:
            warnings.warn(
                "未能取得测试库 watch 串行锁（等待 >30s）：并发保障降级为尽力而为",
                stacklevel=1,
            )
    except Exception as exc:  # noqa: BLE001 —— 锁不可用不阻断测试
        warnings.warn("测试库 watch 串行锁不可用：%r" % (exc,), stacklevel=1)

    yield

    if conn is not None:
        try:
            if acquired and cursor is not None:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (_WATCH_DB_LOCK_KEY,))
                conn.commit()
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
