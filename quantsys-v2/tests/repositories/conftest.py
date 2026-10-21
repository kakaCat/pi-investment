"""tests/repositories 目录级结构补齐（RFC 017，2026-10-21）

## 为什么需要

`quant.watch_rules.position_state / interval_sec` 两列由 **Python 迁移**
（`infrastructure/persistence/migrations/20261021_watch_rules_position_interval.py`）
添加，不在 `migrations/*.sql`（ORM 漂移门禁只重放后者），也尚未纳入
`tests/_db_schema_sync.py` 的迁移白名单（该文件不在本任务的写域内）。

后果：干净 checkout + 干净 `quant_test` 上，仓储测试会因 ORM 声明了列、
库中没有而 UndefinedColumn。此处的 session 级 fixture 先**幂等**把列补上，
让"绿"可复现，而不是依赖某台机器上有人手工执行过迁移。

## 纪律

* 只在 `*_test` 库执行（与根 conftest 的库名校验同口径，双保险）；
* 幂等：迁移模块的 `ensure_columns` 只做 `ADD COLUMN IF NOT EXISTS`；
* 不建表、不改数据、不回填（回填口径由 test_watch_rule_columns_migration.py 在
  临时 schema 上验证）。
"""
import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (Path(__file__).resolve().parents[2]
                  / 'infrastructure' / 'persistence' / 'migrations'
                  / '20261021_watch_rules_position_interval.py')


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        'watch_rules_position_interval_migration', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='session', autouse=True)
def _ensure_watch_rules_rfc017_columns():
    from sqlalchemy import text

    if not MIGRATION_PATH.exists():          # 迁移被移除时不阻塞本目录其它测试
        return
    migration = _load_migration()
    from qs_kernel.infrastructure.persistence.database.engine import get_engine
    engine = get_engine()
    with engine.connect() as conn:
        dbname = conn.execute(text('select current_database()')).scalar()
    if not str(dbname).endswith('_test'):
        return                                # 绝不在生产库做结构变更
    with engine.begin() as conn:
        if migration.table_exists(conn, 'quant'):
            migration.ensure_columns(conn, 'quant', apply=True)
