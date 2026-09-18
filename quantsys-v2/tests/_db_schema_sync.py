"""幂等同步 quant_test 的盯盘（watch）表结构（REQ-c9f899 返工 D，2026-09-18）。

## 为什么需要这个模块

REQ-c9f899 新增了 t1/t3 的盯盘表与列，但**测试库 quant_test 的结构在此之前靠人工
补过一次、不可复现**（implementation.md §5.2："父 agent 手工补过一次但未固化"）。
后果：干净环境/新 checkout 上跑 watch 测试会因缺表缺列而红，而本机绿——绿与红都不算证据。

本模块把结构同步固化成一条幂等、可重复的路径，供 tests/conftest.py 的 session 级
fixture 调用（见 conftest 的 `_bootstrap_test_db_schema` / `db_schema_synced`）。

## 机制（两条腿，互为兜底）

1. **迁移文件为准**：发现 REQ-c9f899 的迁移模块（`20260918*watch*.py`），逐条执行其
   声明的 `TABLES`（CREATE TABLE IF NOT EXISTS）/ `COLUMNS`（ALTER TABLE ADD COLUMN
   IF NOT EXISTS）/ `INDEXES`（CREATE INDEX IF NOT EXISTS）。迁移是生产 DDL 的单一
   事实源，测试库结构与之一致才谈得上"可复现"。
2. **ORM 元数据兜底**：对盯盘表执行 `Base.metadata.create_all(checkfirst=True)`，
   覆盖"ORM 声明了、迁移未建"的新表（当前为去重窗/事件窗/价格历史三张轻量表）。

## 纪律

* **只在测试库执行**：先查 `current_database()`，名字不以 `_test` 结尾即拒绝
  （与 conftest.py 的库名校验同口径；避免误改生产库）。
* **失败响亮**：缺表/缺列一律抛错，不静默放过（"结构没同步上"必须当场暴露）。
* 幂等：重复调用零变更（由 glob 到的迁移 DDL 自带 IF NOT EXISTS 保证）；成功结果缓存，
  同一进程内只跑一次。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / 'infrastructure' / 'persistence' / 'migrations'
#: REQ-c9f899 的迁移文件命名（t1：20260918_watch_todo_loop.py；t3：20260918b_watch_runtime_complete.py）
MIGRATION_GLOB = '20260918*watch*.py'

#: 基础盯盘表（更早的迁移建立；t1 的 watch_todos 有 FK 指向 watch_triggers）。
#: 在完全空的测试库上先建这两张，迁移的 FK 才立得住——使同步不依赖"别的测试恰好建过表"。
BASE_WATCH_TABLES = ('watch_rules', 'watch_triggers')
#: 需要在测试库存在的盯盘表（t1 五张 + t3 三张）
REQUIRED_TABLES = (
    'watch_todos', 'watch_runtime_state', 'watch_runtime_meta',
    'watch_rule_changes', 'watch_receipts',
    'watch_runtime_dedup', 'watch_trigger_events', 'watch_price_history',
)
#: t1 + t3 给既有表加的列（迁移 COLUMNS 声明；这里只用于最终校验，DDL 从迁移模块取）
REQUIRED_COLUMNS = (
    ('watch_triggers', 'metric'), ('watch_triggers', 'metric_unit'),
    ('watch_triggers', 'level'), ('watch_triggers', 'todo_id'),
    ('watch_triggers', 'suppressed'),
    ('watch_rules', 'noise_state'), ('watch_rules', 'suppress_until'),
    ('watch_rules', 'self_heal_count'), ('watch_rules', 'last_repair_at'),
    ('watch_runtime_meta', 'digest_shadow_since'),
)

_SCHEMA = 'quant'
_done_report: Dict[str, Any] | None = None


def _load_migration_modules() -> List[Any]:
    """加载 REQ-c9f899 的迁移模块（只读常量与 upgrade；DB 动作在 __main__ 守卫内）。"""
    modules = []
    for path in sorted(MIGRATIONS_DIR.glob(MIGRATION_GLOB)):
        spec = importlib.util.spec_from_file_location(
            '_reqc9f899_watch_migration_%s' % path.stem, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    if not modules:
        raise RuntimeError(
            '未发现 REQ-c9f899 迁移文件（%s/%s）：无法确定测试库结构口径'
            % (MIGRATIONS_DIR, MIGRATION_GLOB))
    return modules


def _table_exists(conn, table: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = '%s' AND table_name = '%s'" % (_SCHEMA, table)).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = '%s' AND table_name = '%s' AND column_name = '%s'"
        % (_SCHEMA, table, column)).fetchone()
    return row is not None


def sync_test_schema(engine=None) -> Dict[str, Any]:
    """把盯盘 t1/t3 的新表与列幂等同步到测试库。返回同步报告（成功结果进程内缓存）。

    Raises:
        RuntimeError: 目标库名不以 _test 结尾，或同步后仍缺表/缺列。
    """
    global _done_report
    if _done_report is not None:
        return _done_report

    if engine is None:
        from infrastructure.persistence.database.engine import get_engine
        engine = get_engine()

    # 安全闸：只允许打在 *_test 库上（第二道防线；conftest 已在校验一遍）
    with engine.connect() as _conn:
        db_name = str(_conn.exec_driver_sql('SELECT current_database()').scalar() or '')
    if not db_name.endswith('_test'):
        raise RuntimeError(
            '拒绝在非测试库上同步测试结构：当前库 %r（要求以 _test 结尾）' % db_name)

    # 让 ORM 元数据完整登记盯盘模型（models 包不 import 时 Base.metadata 只有零星表）。
    # watch_rules/watch_triggers 的模型内联在仓储适配器里，需显式 import 才登记。
    import infrastructure.persistence.orm.models  # noqa: F401
    import adapters.outbound.repositories.watch_rule_repository  # noqa: F401
    from infrastructure.persistence.orm.base import Base

    report: Dict[str, Any] = {
        'database': db_name,
        'modules': [],
        'tables_created': [],
        'columns_added': [],
        'indexes': 0,
    }

    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE SCHEMA IF NOT EXISTS %s' % _SCHEMA)
        # 先建基础盯盘表：t1 迁移的 watch_todos 有 FK → watch_triggers，
        # 顺序反了会让"完全空的库"同步失败（checkfirst 幂等，既有库上是 no-op）。
        base_tables = [t for t in Base.metadata.tables.values()
                       if t.name in BASE_WATCH_TABLES]
        Base.metadata.create_all(bind=conn, checkfirst=True, tables=base_tables)
        for module in _load_migration_modules():
            report['modules'].append(Path(module.__file__).name)
            for name, ddl in (getattr(module, 'TABLES', None) or []):
                if not _table_exists(conn, name):
                    conn.exec_driver_sql(ddl)
                    report['tables_created'].append(name)
            for table, column, coltype in (getattr(module, 'COLUMNS', None) or []):
                if not _table_exists(conn, table):
                    continue
                if not _column_exists(conn, table, column):
                    conn.exec_driver_sql(
                        'ALTER TABLE %s.%s ADD COLUMN IF NOT EXISTS %s %s'
                        % (_SCHEMA, table, column, coltype))
                    report['columns_added'].append('%s.%s' % (table, column))
            for index, target in (getattr(module, 'INDEXES', None) or []):
                conn.exec_driver_sql(
                    'CREATE INDEX IF NOT EXISTS %s ON %s' % (index, target))
                report['indexes'] += 1

        # ORM 元数据兜底：ORM 声明但迁移未显式 CREATE 的盯盘表（checkfirst 幂等）
        watch_tables = [t for t in Base.metadata.tables.values() if t.name in REQUIRED_TABLES]
        Base.metadata.create_all(bind=conn, checkfirst=True, tables=watch_tables)

        # 运行态 meta 单行（列加在该行上；与两条迁移同款幂等）
        conn.exec_driver_sql(
            'INSERT INTO %s.watch_runtime_meta (id) VALUES (1) ON CONFLICT (id) DO NOTHING'
            % _SCHEMA)

    missing = _verify(engine)
    if missing:
        raise RuntimeError(
            '测试库结构同步后仍缺失：%s（sync_test_schema 未能收敛）' % ', '.join(missing))

    _done_report = report
    return report


def _verify(engine) -> List[str]:
    """校验必需表/列存在；返回缺失清单（空 = 通过）。"""
    with engine.connect() as conn:
        missing = []
        for table in REQUIRED_TABLES:
            if not _table_exists(conn, table):
                missing.append('table:%s.%s' % (_SCHEMA, table))
        for table, column in REQUIRED_COLUMNS:
            if not _column_exists(conn, table, column):
                missing.append('column:%s.%s.%s' % (_SCHEMA, table, column))
    return missing
