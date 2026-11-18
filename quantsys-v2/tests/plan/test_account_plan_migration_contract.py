"""账户级交易计划增量迁移的离线契约（REQ-261026140857-c192）

不连数据库：把迁移 DDL、约束、索引、dry-run 默认值和危险占位语义钉成可复核断言。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "infrastructure" / "persistence" / "migrations" / "20261105d_account_trading_plan.py"
)

NEW_TABLES = {
    "trading_plan_items",
    "trading_plan_item_versions",
    "trading_plan_item_states",
    "trading_plan_conditions",
    "trading_plan_runs",
    "trading_plan_fill_receipts",
}

EXPECTED_COLUMNS = {
    ("trading_plans", "plan_kind"),
    ("trading_plans", "current_revision_id"),
    ("trading_plans", "draft_revision_id"),
    ("trading_plans", "migrated_to_plan_id"),
    ("trading_plans", "lock_version"),
    ("trading_plan_versions", "trade_date"),
    ("trading_plan_versions", "status"),
    ("trading_plan_versions", "data_as_of"),
    ("trading_plan_versions", "market_gate"),
    ("trading_plan_versions", "risk_budget"),
    ("trading_plan_versions", "generation_key"),
    ("trading_plan_versions", "reviewed_by"),
    ("trading_plan_versions", "reviewed_at"),
    ("trading_plan_versions", "activated_at"),
    ("trading_plan_versions", "superseded_at"),
    ("trading_plan_rules", "item_id"),
    ("trading_plan_rules", "plan_version"),
    ("trading_plan_events", "item_id"),
    ("trading_plan_events", "plan_version"),
    ("plan_reflections", "item_id"),
    ("plan_reflections", "plan_version"),
    ("watch_rules", "item_id"),
    ("simulation_trades", "item_id"),
}

PARTIAL_UNIQUE_INDEXES = {
    "uq_trading_plans_account_current_idx",
    "uq_trading_plan_items_open_symbol_idx",
    "uq_trading_plan_versions_pending_day_idx",
    "uq_trading_plan_versions_active_idx",
    "uq_trading_plan_rules_item_role_batch_idx",
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_20261105d_account_trading_plan", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_module_loads_standalone():
    mod = _load_migration()
    assert mod.DEFAULT_SCHEMA == "quant"
    for name in ("apply_migration", "verify", "build_parser", "main"):
        assert callable(getattr(mod, name)), "迁移缺入口: %s" % name


def test_migration_defines_account_model_tables_and_idempotent_ddl():
    mod = _load_migration()
    assert set(mod.NEW_TABLES) == NEW_TABLES
    assert set(mod.TABLE_DDL) == NEW_TABLES
    for table in NEW_TABLES:
        ddl = mod.TABLE_DDL[table].format(schema="quant")
        assert "CREATE TABLE IF NOT EXISTS quant.%s" % table in ddl, table
    assert "PRIMARY KEY" in mod.TABLE_DDL["trading_plan_fill_receipts"]
    assert "DEFAULT '[]'::jsonb" in mod.TABLE_DDL["trading_plan_runs"]


def test_migration_extends_existing_tables_and_new_core_columns_are_nullable():
    mod = _load_migration()
    assert {(t, c) for t, c, _ in mod.NEW_COLUMNS} == EXPECTED_COLUMNS
    attribution_columns = EXPECTED_COLUMNS - {
        ("trading_plans", "plan_kind"),
        ("trading_plans", "lock_version"),
    }
    for table, column, ddl in mod.NEW_COLUMNS:
        if (table, column) in attribution_columns:
            low = ddl.lower()
            assert "not null" not in low and "default" not in low, (table, column, ddl)
    by_column = {(t, c): ddl for t, c, ddl in mod.NEW_COLUMNS}
    assert "NOT NULL DEFAULT 'legacy_single'" in by_column[("trading_plans", "plan_kind")]
    assert "NOT NULL DEFAULT 1" in by_column[("trading_plans", "lock_version")]
    assert set(mod.NULLABLE_COLUMNS) == {
        ("trading_plans", "horizon"),
        ("trading_plans", "spec"),
        ("trading_plan_versions", "spec"),
    }


def test_migration_defines_state_and_identity_constraints():
    mod = _load_migration()
    names = {name for _, name, _ in mod.UNIQUE_CONSTRAINTS}
    assert {
        "uq_trading_plan_versions_generation_key",
        "uq_trading_plan_item_versions_revision_item",
        "uq_trading_plan_conditions_version_role_seq",
        "uq_trading_plan_runs_idempotency_attempt",
        "uq_trading_plan_fill_receipts_trade_id",
    } <= names
    checks = {name: ddl for _, name, ddl in mod.CHECK_CONSTRAINTS}
    assert (
        "('draft','reviewing','approved','active','superseded','rejected')"
        in checks["chk_trading_plan_versions_status"]
    )
    assert "('buy','sell','hold','avoid')" in checks["chk_trading_plan_item_versions_action"]
    assert (
        "('planned','ready','entering','holding','reducing','exited','cancelled')"
        in checks["chk_trading_plan_item_states_state"]
    )
    assert (
        "('generate','review','readiness','reconcile','migrate')"
        in checks["chk_trading_plan_runs_kind"]
    )


def test_migration_adds_item_attribution_foreign_keys():
    mod = _load_migration()
    fks = {name: (table, ddl) for table, name, ddl, _requires in mod.FOREIGN_KEYS}
    for name, table in {
        "fk_trading_plan_items_plan_id": "trading_plan_items",
        "fk_trading_plan_items_legacy_plan_id": "trading_plan_items",
        "fk_trading_plans_current_revision_id": "trading_plans",
        "fk_trading_plans_draft_revision_id": "trading_plans",
        "fk_trading_plan_rules_item_id": "trading_plan_rules",
        "fk_watch_rules_plan_item_id": "watch_rules",
        "fk_simulation_trades_plan_item_id": "simulation_trades",
        "fk_trading_plan_fill_receipts_item_id": "trading_plan_fill_receipts",
    }.items():
        assert name in fks, name
        assert fks[name][0] == table
    assert any("ON DELETE SET NULL" in ddl for _, ddl in fks.values())
    assert any("ON DELETE CASCADE" in ddl for _, ddl in fks.values())


def test_migration_defines_partial_unique_and_regular_indexes():
    mod = _load_migration()
    unique_indexes = {name for _, name, _ in mod.UNIQUE_INDEXES}
    assert unique_indexes == PARTIAL_UNIQUE_INDEXES
    for _table, name, sql in mod.UNIQUE_INDEXES + mod.INDEXES:
        assert "CREATE" in sql and "IF NOT EXISTS" in sql, name
        rendered = sql.format(schema="quant", index=name)
        assert name in rendered, name
        assert rendered.startswith("CREATE") and " ON quant." in rendered
    index_names = {name for _, name, _ in mod.UNIQUE_INDEXES + mod.INDEXES}
    assert "idx_trading_plan_runs_account_trade_kind" in index_names
    assert "idx_simulation_trades_plan_item_date" in index_names


def test_dry_run_is_default_and_apply_is_only_write_switch(capsys):
    mod = _load_migration()
    assert mod.build_parser().parse_args([]).apply is False
    assert mod.build_parser().parse_args(["--apply"]).apply is True
    assert mod.build_parser().parse_args([]).schema == "quant"


def test_daily_task_migration_registers_new_jobs_and_disables_legacy():
    path = ROOT / 'infrastructure' / 'persistence' / 'migrations' / '20261105e_trading_plan_daily_tasks.py'
    spec = importlib.util.spec_from_file_location('mig_20261105e_daily_tasks', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rows = {row[0]: row for row in module.ROWS}
    assert rows['trading_plan_generate_daily'][2] == '5 9 * * 1-5'
    assert rows['trading_plan_readiness'][2] == '20 9 * * 1-5'
    assert rows['trading_plan_generate_daily'][3] == 'trading_plan_generate_daily'
    assert rows['trading_plan_readiness'][3] == 'trading_plan_readiness'
    assert module.LEGACY_TASK == 'core_plan_generate'
