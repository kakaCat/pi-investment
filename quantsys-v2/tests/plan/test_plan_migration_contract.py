"""qs_plan 包骨架 + 20261105 五表迁移的**离线契约**（REQ-261021222905-6dff · t-180c05 dev 段）。

本测试**不连数据库**，只把「迁移声称要做的事」钉成可复核断言：

1. 包骨架文件齐备 + pyproject 声明正确（`packages/qs_plan` 可被 editable 装）；
2. 迁移模块可独立加载（不依赖 app 壳/PYTHONPATH）；
3. DDL 契约 = 5 张新表 + **2 张既有表加 3 个可空列**（卡面「5 表 2 列」口径）；
4. 幂等口径：建表/索引一律 IF NOT EXISTS，约束逐条预检后 ADD（不用 PG14 不支持的
   `ADD CONSTRAINT IF NOT EXISTS`），dry-run 是默认、`--apply` 是唯一写开关。

真实迁移的 dry-run / --apply / 重跑 0 变更证据由迁移脚本自身输出（见任务卡汇报）：

    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105_trading_plan.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105_trading_plan.py --apply
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'packages' / 'qs_plan'
MIGRATION = ROOT / 'infrastructure' / 'persistence' / 'migrations' / '20261105_trading_plan.py'

NEW_TABLES = {
    'trading_plans',
    'trading_plan_versions',
    'trading_plan_rules',
    'trading_plan_events',
    'plan_reflections',
}

EXPECTED_COLUMNS = {
    ('watch_rules', 'plan_id'),
    ('simulation_trades', 'plan_id'),
    ('simulation_trades', 'plan_version'),
}


def _load_migration():
    spec = importlib.util.spec_from_file_location('mig_20261105_trading_plan', MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── 1. 包骨架 ────────────────────────────────────────────────────────────
def test_package_skeleton_files_exist():
    for rel in (
        'pyproject.toml',
        'qs_plan/__init__.py',
        'qs_plan/domain/__init__.py',
        'qs_plan/domain/plan/__init__.py',
        'qs_plan/application/__init__.py',
    ):
        assert (PKG / rel).is_file(), '缺骨架文件: packages/qs_plan/%s' % rel


def test_pyproject_declares_qs_plan_distribution():
    text = (PKG / 'pyproject.toml').read_text(encoding='utf-8')
    assert 'name = "qs-plan"' in text
    assert 'include = ["qs_plan*"]' in text
    # 单向依赖边（架构设计 §架构与依赖）：本包 import 兄弟包就必须声明
    for dep in ('qs-kernel', 'qs-market-data', 'qs-sourcing', 'qs-trading', 'qs-watch'):
        assert '"%s"' % dep in text, 'pyproject 缺依赖声明: %s' % dep


# ── 2. 迁移模块可独立加载 ────────────────────────────────────────────────
def test_migration_module_loads_standalone():
    mod = _load_migration()
    assert mod.DEFAULT_SCHEMA == 'quant'
    for fn in ('apply_migration', 'verify', 'main'):
        assert callable(getattr(mod, fn)), '迁移缺入口: %s' % fn


# ── 3. 五表 + 2 张既有表加列 ─────────────────────────────────────────────
def test_migration_defines_five_new_tables_with_idempotent_ddl():
    mod = _load_migration()
    assert set(mod.NEW_TABLES) == NEW_TABLES
    assert set(mod.TABLE_DDL) == NEW_TABLES
    for table in NEW_TABLES:
        ddl = mod.TABLE_DDL[table].format(schema='quant')
        assert 'CREATE TABLE IF NOT EXISTS quant.%s' % table in ddl, table
    # data-model.md 的键：版本号/规则映射/反思周期三处唯一键
    assert mod.TABLE_DDL['trading_plan_rules'].format(schema='quant').count(
        'PRIMARY KEY (plan_id, role, symbol)') == 1


def test_migration_adds_three_nullable_columns_on_two_existing_tables():
    mod = _load_migration()
    assert {(t, c) for t, c, _ in mod.NEW_COLUMNS} == EXPECTED_COLUMNS
    assert {t for t, _, _ in mod.NEW_COLUMNS} == {'watch_rules', 'simulation_trades'}
    # 归因列口径：可空、无默认、不回填（NULL = 非托管 / 计划外）
    for table, column, ddl in mod.NEW_COLUMNS:
        low = ddl.lower()
        assert 'not null' not in low and 'default' not in low, (table, column, ddl)


def test_unique_and_foreign_keys_match_data_model():
    mod = _load_migration()
    uniques = {name for _, name, _ in mod.UNIQUE_CONSTRAINTS}
    assert uniques == {
        'uq_trading_plan_versions_plan_version',
        'uq_trading_plan_rules_rule_id',
        'uq_plan_reflections_period_version',
    }
    fks = {name for _, name, _, _ in mod.FOREIGN_KEYS}
    assert {
        'fk_trading_plan_versions_plan_id',
        'fk_trading_plan_rules_plan_id',
        'fk_trading_plan_rules_rule_id',
        'fk_trading_plan_events_plan_id',
        'fk_plan_reflections_plan_id',
        'fk_watch_rules_plan_id',
        'fk_simulation_trades_plan_id',
    } == fks
    # 归因列外键必须 SET NULL（删计划不丢历史成交），其余 CASCADE
    by_name = {name: ddl for _, name, ddl, _ in mod.FOREIGN_KEYS}
    assert 'ON DELETE SET NULL' in by_name['fk_watch_rules_plan_id']
    assert 'ON DELETE SET NULL' in by_name['fk_simulation_trades_plan_id']
    assert 'ON DELETE CASCADE' in by_name['fk_plan_reflections_plan_id']


# ── 4. 幂等与写闸 ────────────────────────────────────────────────────────
def test_indexes_are_idempotent_and_schema_parameterized():
    mod = _load_migration()
    assert len(mod.INDEXES) == 5
    for table, name, sql in mod.INDEXES:
        assert 'CREATE INDEX IF NOT EXISTS' in sql, (table, name)
        rendered = sql.format(schema='quant', index=name)
        assert rendered.startswith('CREATE INDEX IF NOT EXISTS %s ON quant.' % name)
        assert name in rendered


def test_dry_run_is_default_and_apply_is_only_write_switch(capsys):
    mod = _load_migration()
    # 默认（不带 --apply）= dry-run：只预检，绝不写库
    defaults = mod.build_parser().parse_args([])
    assert defaults.apply is False
    assert defaults.schema == 'quant'
    # 显式 --apply 才进入写库分支
    assert mod.build_parser().parse_args(['--apply']).apply is True
    # 帮助文本如实告知这是唯一写开关
    with pytest.raises(SystemExit) as excinfo:
        mod.main(['--help'])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert '--apply' in out and '默认 dry-run' in out


def test_verify_expected_counts_lock_23_objects():
    """自检口径：5 表 + 3 列 + 10 约束 + 5 索引 = 23 个对象，改动数应为 23。"""
    mod = _load_migration()
    assert len(mod.NEW_TABLES) == 5
    assert len(mod.NEW_COLUMNS) == 3
    assert len(mod.UNIQUE_CONSTRAINTS) + len(mod.FOREIGN_KEYS) == 10
    assert len(mod.INDEXES) == 5
