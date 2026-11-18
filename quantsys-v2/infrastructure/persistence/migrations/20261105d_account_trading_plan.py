#!/usr/bin/env python
"""quant schema 账户级交易计划：多标 item、状态、运行记录和精确归因（REQ-261026140857-c192）

本迁移是 20261105 交易计划五表之后的增量结构迁移：

1. 扩展既有计划表：
   - trading_plans：plan_kind/current_revision_id/draft_revision_id/migrated_to_plan_id/lock_version
   - trading_plan_versions：trade_date/status/data_as_of/market_gate/risk_budget/generation_key/审核与激活时间
   - trading_plan_rules：item_id/plan_version
   - trading_plan_events、plan_reflections：item 归因列
2. 既有执行表增加 item 归因：
   - watch_rules.item_id
   - simulation_trades.item_id
3. 新增 6 表：
   - trading_plan_items：稳定计划项
   - trading_plan_item_versions：不可变逐标决策
   - trading_plan_item_states：独立执行状态
   - trading_plan_conditions：item 版本条件
   - trading_plan_runs：生成/就绪/对账/迁移运行历史
   - trading_plan_fill_receipts：成交推进幂等凭证
4. 将新账户主计划不再使用的 trading_plans.horizon/spec 与 versions.spec 调整为可空。
   旧行原值保留，新链路不得写入占位 spec。

默认 dry-run；只有 --apply 写库；支持显式 --dsn 指向 quant_test。
"""
from __future__ import annotations

import argparse
import os
import re
from typing import Optional, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

DEFAULT_SCHEMA = "quant"

PLANS = "trading_plans"
VERSIONS = "trading_plan_versions"
RULES = "trading_plan_rules"
EVENTS = "trading_plan_events"
REFLECTIONS = "plan_reflections"
WATCH_RULES = "watch_rules"
SIM_TRADES = "simulation_trades"

ITEMS = "trading_plan_items"
ITEM_VERSIONS = "trading_plan_item_versions"
ITEM_STATES = "trading_plan_item_states"
CONDITIONS = "trading_plan_conditions"
RUNS = "trading_plan_runs"
RECEIPTS = "trading_plan_fill_receipts"

NEW_TABLES = (ITEMS, ITEM_VERSIONS, ITEM_STATES, CONDITIONS, RUNS, RECEIPTS)

NEW_COLUMNS = (
    (PLANS, "plan_kind", "varchar(16) NOT NULL DEFAULT 'legacy_single'"),
    (PLANS, "current_revision_id", "integer"),
    (PLANS, "draft_revision_id", "integer"),
    (PLANS, "migrated_to_plan_id", "integer"),
    (PLANS, "lock_version", "integer NOT NULL DEFAULT 1"),
    (VERSIONS, "trade_date", "date"),
    (VERSIONS, "status", "varchar(16)"),
    (VERSIONS, "data_as_of", "timestamptz"),
    (VERSIONS, "market_gate", "jsonb"),
    (VERSIONS, "risk_budget", "jsonb"),
    (VERSIONS, "generation_key", "varchar(120)"),
    (VERSIONS, "reviewed_by", "varchar(50)"),
    (VERSIONS, "reviewed_at", "timestamptz"),
    (VERSIONS, "activated_at", "timestamptz"),
    (VERSIONS, "superseded_at", "timestamptz"),
    (RULES, "item_id", "integer"),
    (RULES, "plan_version", "integer"),
    (EVENTS, "item_id", "integer"),
    (EVENTS, "plan_version", "integer"),
    (REFLECTIONS, "item_id", "integer"),
    (REFLECTIONS, "plan_version", "integer"),
    (WATCH_RULES, "item_id", "integer"),
    (SIM_TRADES, "item_id", "integer"),
)

NULLABLE_COLUMNS = (
    (PLANS, "horizon"),
    (PLANS, "spec"),
    (VERSIONS, "spec"),
)

TABLE_DDL = {
    ITEMS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_items (
        id serial PRIMARY KEY,
        plan_id integer NOT NULL,
        symbol varchar(20) NOT NULL,
        legacy_plan_id integer,
        opened_at timestamptz NOT NULL DEFAULT now(),
        closed_at timestamptz
    )""",
    ITEM_VERSIONS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_item_versions (
        id serial PRIMARY KEY,
        revision_id integer NOT NULL,
        item_id integer NOT NULL,
        action varchar(12) NOT NULL,
        horizon varchar(16) NOT NULL,
        target_weight numeric(9,6),
        max_weight numeric(9,6),
        target_qty bigint,
        entry_combinator varchar(8) NOT NULL DEFAULT 'all_of',
        thesis text,
        invalidation text,
        entry_valid_until timestamptz,
        evidence jsonb,
        created_at timestamptz NOT NULL DEFAULT now()
    )""",
    ITEM_STATES: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_item_states (
        item_id integer PRIMARY KEY,
        state varchar(16) NOT NULL,
        target_qty bigint,
        filled_qty bigint NOT NULL DEFAULT 0,
        remaining_qty bigint,
        initial_position_qty bigint NOT NULL DEFAULT 0,
        initial_sold_qty bigint NOT NULL DEFAULT 0,
        last_fill_at timestamptz,
        lock_version integer NOT NULL DEFAULT 1,
        updated_at timestamptz NOT NULL DEFAULT now()
    )""",
    CONDITIONS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_conditions (
        id serial PRIMARY KEY,
        item_version_id integer NOT NULL,
        role varchar(16) NOT NULL,
        batch integer NOT NULL DEFAULT 0,
        sequence integer NOT NULL DEFAULT 0,
        condition_type varchar(40) NOT NULL,
        params jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )""",
    RUNS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_runs (
        id bigserial PRIMARY KEY,
        account varchar(60) NOT NULL,
        trade_date date NOT NULL,
        run_kind varchar(24) NOT NULL,
        idempotency_key varchar(160),
        attempt integer NOT NULL DEFAULT 1,
        plan_id integer,
        revision_id integer,
        status varchar(16) NOT NULL DEFAULT 'running',
        reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
        error text,
        started_at timestamptz NOT NULL DEFAULT now(),
        finished_at timestamptz
    )""",
    RECEIPTS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_fill_receipts (
        trade_id varchar(120) PRIMARY KEY,
        plan_id integer NOT NULL,
        item_id integer NOT NULL,
        plan_version integer NOT NULL,
        side varchar(4) NOT NULL,
        qty bigint NOT NULL,
        remaining_qty bigint,
        received_at timestamptz NOT NULL DEFAULT now()
    )""",
}

UNIQUE_CONSTRAINTS = (
    (VERSIONS, "uq_trading_plan_versions_generation_key", "UNIQUE (generation_key)"),
    (ITEM_VERSIONS, "uq_trading_plan_item_versions_revision_item", "UNIQUE (revision_id, item_id)"),
    (
        CONDITIONS,
        "uq_trading_plan_conditions_version_role_seq",
        "UNIQUE (item_version_id, role, batch, sequence)",
    ),
    (RUNS, "uq_trading_plan_runs_idempotency_attempt", "UNIQUE (idempotency_key, attempt)"),
    (RECEIPTS, "uq_trading_plan_fill_receipts_trade_id", "UNIQUE (trade_id)"),
)

FOREIGN_KEYS = (
    (
        ITEMS,
        "fk_trading_plan_items_plan_id",
        "FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE CASCADE",
        PLANS,
    ),
    (
        ITEMS,
        "fk_trading_plan_items_legacy_plan_id",
        "FOREIGN KEY (legacy_plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE SET NULL",
        PLANS,
    ),
    (
        PLANS,
        "fk_trading_plans_current_revision_id",
        "FOREIGN KEY (current_revision_id) REFERENCES {schema}.trading_plan_versions (id) ON DELETE SET NULL",
        VERSIONS,
    ),
    (
        PLANS,
        "fk_trading_plans_draft_revision_id",
        "FOREIGN KEY (draft_revision_id) REFERENCES {schema}.trading_plan_versions (id) ON DELETE SET NULL",
        VERSIONS,
    ),
    (
        PLANS,
        "fk_trading_plans_migrated_to_plan_id",
        "FOREIGN KEY (migrated_to_plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE SET NULL",
        PLANS,
    ),
    (
        ITEM_VERSIONS,
        "fk_trading_plan_item_versions_revision_id",
        "FOREIGN KEY (revision_id) REFERENCES {schema}.trading_plan_versions (id) ON DELETE CASCADE",
        VERSIONS,
    ),
    (
        ITEM_VERSIONS,
        "fk_trading_plan_item_versions_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE CASCADE",
        ITEMS,
    ),
    (
        ITEM_STATES,
        "fk_trading_plan_item_states_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE CASCADE",
        ITEMS,
    ),
    (
        CONDITIONS,
        "fk_trading_plan_conditions_item_version_id",
        "FOREIGN KEY (item_version_id) REFERENCES {schema}.trading_plan_item_versions (id) ON DELETE CASCADE",
        ITEM_VERSIONS,
    ),
    (
        RULES,
        "fk_trading_plan_rules_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE SET NULL",
        ITEMS,
    ),
    (
        EVENTS,
        "fk_trading_plan_events_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE SET NULL",
        ITEMS,
    ),
    (
        REFLECTIONS,
        "fk_plan_reflections_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE SET NULL",
        ITEMS,
    ),
    (
        WATCH_RULES,
        "fk_watch_rules_plan_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE SET NULL",
        ITEMS,
    ),
    (
        SIM_TRADES,
        "fk_simulation_trades_plan_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE SET NULL",
        ITEMS,
    ),
    (
        RUNS,
        "fk_trading_plan_runs_plan_id",
        "FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE SET NULL",
        PLANS,
    ),
    (
        RUNS,
        "fk_trading_plan_runs_revision_id",
        "FOREIGN KEY (revision_id) REFERENCES {schema}.trading_plan_versions (id) ON DELETE SET NULL",
        VERSIONS,
    ),
    (
        RECEIPTS,
        "fk_trading_plan_fill_receipts_plan_id",
        "FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE SET NULL",
        PLANS,
    ),
    (
        RECEIPTS,
        "fk_trading_plan_fill_receipts_item_id",
        "FOREIGN KEY (item_id) REFERENCES {schema}.trading_plan_items (id) ON DELETE CASCADE",
        ITEMS,
    ),
)

CHECK_CONSTRAINTS = (
    (PLANS, "chk_trading_plans_plan_kind", "CHECK (plan_kind IN ('legacy_single','account'))"),
    (
        VERSIONS,
        "chk_trading_plan_versions_status",
        "CHECK (status IS NULL OR status IN "
        "('draft','reviewing','approved','active','superseded','rejected'))",
    ),
    (
        ITEM_VERSIONS,
        "chk_trading_plan_item_versions_action",
        "CHECK (action IN ('buy','sell','hold','avoid'))",
    ),
    (
        ITEM_VERSIONS,
        "chk_trading_plan_item_versions_entry_combinator",
        "CHECK (entry_combinator IN ('all_of','any_of'))",
    ),
    (
        ITEM_VERSIONS,
        "chk_trading_plan_item_versions_weights",
        "CHECK ((target_weight IS NULL OR target_weight BETWEEN 0 AND 1) "
        "AND (max_weight IS NULL OR max_weight BETWEEN 0 AND 1))",
    ),
    (
        CONDITIONS,
        "chk_trading_plan_conditions_role",
        "CHECK (role IN ('entry','stop_loss','reduce'))",
    ),
    (
        ITEM_STATES,
        "chk_trading_plan_item_states_state",
        "CHECK (state IN ('planned','ready','entering','holding','reducing','exited','cancelled'))",
    ),
    (
        ITEM_STATES,
        "chk_trading_plan_item_states_nonnegative",
        "CHECK (filled_qty >= 0 AND initial_position_qty >= 0 AND initial_sold_qty >= 0 "
        "AND (remaining_qty IS NULL OR remaining_qty >= 0))",
    ),
    (
        RUNS,
        "chk_trading_plan_runs_kind",
        "CHECK (run_kind IN ('generate','review','readiness','reconcile','migrate'))",
    ),
    (
        RUNS,
        "chk_trading_plan_runs_status",
        "CHECK (status IN ('running','succeeded','failed','degraded','interrupted'))",
    ),
    (RECEIPTS, "chk_trading_plan_fill_receipts_side", "CHECK (side IN ('buy','sell'))"),
    (RECEIPTS, "chk_trading_plan_fill_receipts_qty", "CHECK (qty > 0)"),
)

UNIQUE_INDEXES = (
    (
        PLANS,
        "uq_trading_plans_account_current_idx",
        "CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {schema}.trading_plans (account) "
        "WHERE plan_kind = 'account' AND status NOT IN ('closed','archived')",
    ),
    (
        ITEMS,
        "uq_trading_plan_items_open_symbol_idx",
        "CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_items (plan_id, symbol) "
        "WHERE closed_at IS NULL",
    ),
    (
        VERSIONS,
        "uq_trading_plan_versions_pending_day_idx",
        "CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_versions "
        "(plan_id, trade_date) WHERE status IN ('draft','reviewing','approved')",
    ),
    (
        VERSIONS,
        "uq_trading_plan_versions_active_idx",
        "CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_versions (plan_id) "
        "WHERE status = 'active'",
    ),
    (
        RULES,
        "uq_trading_plan_rules_item_role_batch_idx",
        "CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_rules "
        "(item_id, role, batch) WHERE item_id IS NOT NULL",
    ),
)

INDEXES = (
    (
        ITEMS,
        "idx_trading_plan_items_plan",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_items (plan_id, closed_at)",
    ),
    (
        ITEMS,
        "idx_trading_plan_items_legacy_plan",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_items (legacy_plan_id)",
    ),
    (
        ITEM_VERSIONS,
        "idx_trading_plan_item_versions_revision",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_item_versions (revision_id)",
    ),
    (
        ITEM_VERSIONS,
        "idx_trading_plan_item_versions_item",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_item_versions (item_id)",
    ),
    (
        CONDITIONS,
        "idx_trading_plan_conditions_item_version",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_conditions (item_version_id)",
    ),
    (
        VERSIONS,
        "idx_trading_plan_versions_plan_trade_status",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_versions "
        "(plan_id, trade_date, status)",
    ),
    (
        EVENTS,
        "idx_trading_plan_events_item_created",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_events (item_id, created_at)",
    ),
    (
        REFLECTIONS,
        "idx_plan_reflections_item",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.plan_reflections (item_id)",
    ),
    (
        WATCH_RULES,
        "idx_watch_rules_plan_item",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.watch_rules (item_id)",
    ),
    (
        SIM_TRADES,
        "idx_simulation_trades_plan_item_date",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.simulation_trades (item_id, trade_date)",
    ),
    (
        RUNS,
        "idx_trading_plan_runs_account_trade_kind",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_runs "
        "(account, trade_date, run_kind, started_at)",
    ),
    (
        RECEIPTS,
        "idx_trading_plan_fill_receipts_plan_item",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_fill_receipts (plan_id, item_id)",
    ),
)

TABLE_COMMENTS = {
    ITEMS: "账户计划项：跨 revision 稳定身份；legacy_plan_id 记录旧单标迁移来源",
    ITEM_VERSIONS: "计划项不可变决策：每个 revision 每个 item 一行",
    ITEM_STATES: "计划项当前执行状态：成交与持仓推进独立更新，初始数量保存迁移基线",
    CONDITIONS: "计划项条件：entry/stop_loss/reduce 的角色与批次使用关系列",
    RUNS: "交易计划任务运行历史：生成、readiness、对账和迁移均持久化",
    RECEIPTS: "成交推进幂等凭证：trade_id 主键，重放不产生重复推进",
}

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError("非法标识符: %r" % (name,))
    return name


def _engine(dsn: Optional[str] = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get("QUANT_DATABASE_URL") or "postgresql+psycopg2:///quant_investment"
    return create_engine(url)


def table_exists(conn: Connection, schema: str, table: str) -> bool:
    return (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :table"
            ),
            {"schema": _ident(schema), "table": _ident(table)},
        ).first()
        is not None
    )


def column_names(conn: Connection, schema: str, table: str) -> set[str]:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": _ident(schema), "table": _ident(table)},
    ).fetchall()
    return {r[0] for r in rows}


def column_nullable(conn: Connection, schema: str, table: str, column: str) -> bool:
    return conn.execute(
        text(
            "SELECT is_nullable = 'YES' FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": _ident(schema), "table": _ident(table), "column": _ident(column)},
    ).scalar()


def constraint_names(conn: Connection, schema: str, table: str) -> set[str]:
    rows = conn.execute(
        text(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": _ident(schema), "table": _ident(table)},
    ).fetchall()
    return {r[0] for r in rows}


def index_names(conn: Connection, schema: str, table: str) -> set[str]:
    rows = conn.execute(
        text(
            "SELECT indexname FROM pg_indexes " "WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": _ident(schema), "table": _ident(table)},
    ).fetchall()
    return {r[0] for r in rows}


def _comment_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _table_present(conn: Connection, schema: str, table: str, *, apply: bool) -> bool:
    return table_exists(conn, schema, table) or (not apply and table in NEW_TABLES)


def ensure_table(conn: Connection, schema: str, table: str, *, apply: bool = True) -> dict:
    schema, table = _ident(schema), _ident(table)
    if table_exists(conn, schema, table):
        return {"table": table, "status": "exists"}
    if not apply:
        return {"table": table, "status": "would-create"}
    conn.execute(text(TABLE_DDL[table].format(schema=schema)))
    if table in TABLE_COMMENTS:
        conn.execute(
            text(
                "COMMENT ON TABLE %s.%s IS %s"
                % (schema, table, _comment_literal(TABLE_COMMENTS[table]))
            )
        )
    return {"table": table, "status": "created"}


def ensure_column(
    conn: Connection, schema: str, table: str, column: str, ddl_type: str, *, apply: bool = True
) -> dict:
    schema, table, column = _ident(schema), _ident(table), _ident(column)
    if not _table_present(conn, schema, table, apply=apply):
        return {"table": table, "column": column, "status": "skipped-no-table"}
    if column in column_names(conn, schema, table):
        return {"table": table, "column": column, "status": "exists"}
    if not apply:
        return {"table": table, "column": column, "status": "would-add"}
    conn.execute(
        text("ALTER TABLE %s.%s ADD COLUMN IF NOT EXISTS %s %s" % (schema, table, column, ddl_type))
    )
    return {"table": table, "column": column, "status": "added"}


def ensure_nullable(
    conn: Connection, schema: str, table: str, column: str, *, apply: bool = True
) -> dict:
    schema, table, column = _ident(schema), _ident(table), _ident(column)
    if not table_exists(conn, schema, table):
        return {"table": table, "column": column, "status": "skipped-no-table"}
    if column_nullable(conn, schema, table, column):
        return {"table": table, "column": column, "status": "exists"}
    if not apply:
        return {"table": table, "column": column, "status": "would-drop-not-null"}
    conn.execute(text("ALTER TABLE %s.%s ALTER COLUMN %s DROP NOT NULL" % (schema, table, column)))
    return {"table": table, "column": column, "status": "dropped-not-null"}


def ensure_constraint(
    conn: Connection,
    schema: str,
    table: str,
    name: str,
    definition: str,
    *,
    apply: bool = True,
    requires: Optional[str] = None,
) -> dict:
    schema, table, name = _ident(schema), _ident(table), _ident(name)
    if not _table_present(conn, schema, table, apply=apply):
        return {"table": table, "constraint": name, "status": "skipped-no-table"}
    if requires and not _table_present(conn, schema, requires, apply=apply):
        return {"table": table, "constraint": name, "status": "skipped-no-%s" % requires}
    if name in constraint_names(conn, schema, table):
        return {"table": table, "constraint": name, "status": "exists"}
    if not apply:
        return {"table": table, "constraint": name, "status": "would-create"}
    conn.execute(
        text(
            "ALTER TABLE %s.%s ADD CONSTRAINT %s %s"
            % (schema, table, name, definition.format(schema=schema))
        )
    )
    return {"table": table, "constraint": name, "status": "created"}


def ensure_index(
    conn: Connection, schema: str, table: str, name: str, sql: str, *, apply: bool = True
) -> dict:
    schema, table, name = _ident(schema), _ident(table), _ident(name)
    if not _table_present(conn, schema, table, apply=apply):
        return {"table": table, "index": name, "status": "skipped-no-table"}
    if name in index_names(conn, schema, table):
        return {"table": table, "index": name, "status": "exists"}
    if not apply:
        return {"table": table, "index": name, "status": "would-create"}
    conn.execute(text(sql.format(schema=schema, index=name)))
    return {"table": table, "index": name, "status": "created"}


_CHANGE_STATUSES = (
    "created",
    "added",
    "dropped-not-null",
    "would-create",
    "would-add",
    "would-drop-not-null",
)


def apply_migration(conn: Connection, schema: str = DEFAULT_SCHEMA, *, apply: bool = True) -> dict:
    """执行增量迁移并返回报告。apply=False 时只预检，不执行 DDL。"""
    schema = _ident(schema)
    report: dict = {
        "schema": schema,
        "tables": [],
        "columns": [],
        "constraints": [],
        "indexes": [],
        "skipped": [],
        "changes": 0,
    }

    for table in NEW_TABLES:
        report["tables"].append(ensure_table(conn, schema, table, apply=apply))

    for table, column, ddl_type in NEW_COLUMNS:
        report["columns"].append(ensure_column(conn, schema, table, column, ddl_type, apply=apply))

    for table, column in NULLABLE_COLUMNS:
        report["columns"].append(ensure_nullable(conn, schema, table, column, apply=apply))

    for table, name, definition in UNIQUE_CONSTRAINTS:
        report["constraints"].append(
            ensure_constraint(conn, schema, table, name, definition, apply=apply)
        )

    for table, name, definition in CHECK_CONSTRAINTS:
        report["constraints"].append(
            ensure_constraint(conn, schema, table, name, definition, apply=apply)
        )

    for table, name, definition, requires in FOREIGN_KEYS:
        report["constraints"].append(
            ensure_constraint(conn, schema, table, name, definition, apply=apply, requires=requires)
        )

    for table, name, sql in UNIQUE_INDEXES:
        report["indexes"].append(ensure_index(conn, schema, table, name, sql, apply=apply))

    for table, name, sql in INDEXES:
        report["indexes"].append(ensure_index(conn, schema, table, name, sql, apply=apply))

    for section in ("tables", "columns", "constraints", "indexes"):
        for item in report[section]:
            if item["status"] in _CHANGE_STATUSES:
                report["changes"] += 1
            elif item["status"].startswith("skipped"):
                report["skipped"].append(item)
    return report


def verify(conn: Connection, schema: str = DEFAULT_SCHEMA) -> dict:
    """apply 后自检：6 表 / 25 加列 / 3 空值调整 / 全部约束与索引。"""
    schema = _ident(schema)
    missing: list[str] = []
    present = {"tables": 0, "columns": 0, "constraints": 0, "indexes": 0}

    for table in NEW_TABLES:
        if table_exists(conn, schema, table):
            present["tables"] += 1
        else:
            missing.append("table %s.%s" % (schema, table))

    for table, column, _ddl in NEW_COLUMNS:
        if table_exists(conn, schema, table) and column in column_names(conn, schema, table):
            present["columns"] += 1
        else:
            missing.append("column %s.%s.%s" % (schema, table, column))

    for table, column in NULLABLE_COLUMNS:
        if table_exists(conn, schema, table) and column_nullable(conn, schema, table, column):
            present["columns"] += 1
        else:
            missing.append("nullable %s.%s.%s" % (schema, table, column))

    constraints = [(t, n) for t, n, _d in UNIQUE_CONSTRAINTS]
    constraints += [(t, n) for t, n, _d in CHECK_CONSTRAINTS]
    constraints += [(t, n) for t, n, _d, _r in FOREIGN_KEYS]
    for table, name in constraints:
        if table_exists(conn, schema, table) and name in constraint_names(conn, schema, table):
            present["constraints"] += 1
        else:
            missing.append("constraint %s.%s" % (table, name))

    indexes = [(t, n, s) for t, n, s in UNIQUE_INDEXES] + list(INDEXES)
    for table, name, _sql in indexes:
        if table_exists(conn, schema, table) and name in index_names(conn, schema, table):
            present["indexes"] += 1
        else:
            missing.append("index %s.%s" % (table, name))

    expected = {
        "tables": len(NEW_TABLES),
        "columns": len(NEW_COLUMNS) + len(NULLABLE_COLUMNS),
        "constraints": len(constraints),
        "indexes": len(indexes),
    }
    return {"ok": not missing, "missing": missing, "present": present, "expected": expected}


def format_report(report: dict, *, applied: bool) -> list[str]:
    tag = "APPLY " if applied else "DRY   "
    lines: list[str] = []

    def _name(item: dict) -> str:
        if "column" in item:
            return "%s.%s" % (item["table"], item["column"])
        if "constraint" in item:
            return "%s.%s" % (item["table"], item["constraint"])
        if "index" in item:
            return "%s.%s" % (item["table"], item["index"])
        return "quant.%s" % (item["table"],)

    def _emit(kind: str, item: dict) -> None:
        lines.append("%s%-10s %-19s %s" % (tag, kind, item["status"], _name(item)))

    for section, kind in (
        ("tables", "table"),
        ("columns", "column"),
        ("constraints", "constraint"),
        ("indexes", "index"),
    ):
        for item in report[section]:
            _emit(kind, item)
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="账户级交易计划增量迁移（dry-run 默认 / --apply 写库）"
    )
    parser.add_argument(
        "--apply", action="store_true", help="实际写库（默认 dry-run：只预检与报告）"
    )
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="目标 schema（默认 quant）")
    parser.add_argument("--dsn", default=None, help="显式数据库 DSN")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    eng = _engine(args.dsn)
    with eng.begin() as conn:
        report = apply_migration(conn, args.schema, apply=args.apply)
        for line in format_report(report, applied=args.apply):
            print(line)
        print(
            "%s summary: schema=%s · %d 新表 · %d 加列 · %d 空值调整 · %d 约束 · %d 索引 · changes=%d%s"
            % (
                "APPLY" if args.apply else "DRY  ",
                report["schema"],
                len(NEW_TABLES),
                len(NEW_COLUMNS),
                len(NULLABLE_COLUMNS),
                len(UNIQUE_CONSTRAINTS) + len(CHECK_CONSTRAINTS) + len(FOREIGN_KEYS),
                len(UNIQUE_INDEXES) + len(INDEXES),
                report["changes"],
                "" if args.apply else "（dry-run 未写库）",
            )
        )

    if not args.apply:
        print("DRY-RUN done（--apply 才写库）")
        return 0

    with eng.connect() as conn:
        result = verify(conn, args.schema)
        exp, got = result["expected"], result["present"]
        if not result["ok"]:
            print("VERIFY FAILED: 缺失 %s" % (result["missing"],))
            return 2
        print(
            "VERIFY OK: %d/%d tables · %d/%d columns · %d/%d constraints · %d/%d indexes"
            % (
                got["tables"],
                exp["tables"],
                got["columns"],
                exp["columns"],
                got["constraints"],
                exp["constraints"],
                got["indexes"],
                exp["indexes"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
