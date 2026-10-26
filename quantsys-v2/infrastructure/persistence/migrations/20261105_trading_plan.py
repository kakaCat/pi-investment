#!/usr/bin/env python
"""quant schema 交易计划与反思闭环：五表 + 既有表归因列（2026-11-05 · REQ-261021222905-6dff t-180c05）

## 做什么

方案卡 `docs/requirements/REQ-261021222905-6dff/design/data-model.md` 把「交易计划」
立为一等实体。本迁移只落**存储契约**（不含 ORM/仓储/服务——那由后续卡 t2+ 承接）：

1. 新建 5 表（quant schema）：
   - `trading_plans` —— 计划本体（spec 四段 / status / version / 反思周期与到期）
   - `trading_plan_versions` —— 版本快照（行不可变，修改对照的基线来源）
   - `trading_plan_rules` —— 编译产物映射（plan_id + role + symbol → rule_id，即幂等键）
   - `trading_plan_events` —— 状态/修改留痕（时间线查询）
   - `plan_reflections` —— 反思报告 + 材料包快照（同周期重写 = version+1 新行）
2. 既有表加**可空**归因列（**2 张表 / 3 列**）：
   - `watch_rules.plan_id` —— 托管归属（NULL = 非托管）
   - `simulation_trades.plan_id` / `simulation_trades.plan_version` —— 成交归因
     （NULL = 计划外；历史行不回填，行为零变化）

> 卡面「5 表 2 列」的口径 = **5 张新表 + 2 张既有表加列**；实际列数为 3
> （watch_rules 1 列 + simulation_trades 2 列）。见 data-model.md「既有表加列」表。

## 约束与键（与 data-model.md 逐条对齐）

| 表 | 键 / 约束 | 语义 |
|---|---|---|
| trading_plans | PK id；idx (account, status)、(review_due_at) | today 视图主查询 / 反思到期扫描 |
| trading_plan_versions | UNIQUE (plan_id, version)；FK plan_id CASCADE | 版本号在计划内唯一，行只插不改 |
| trading_plan_rules | PK (plan_id, role, symbol)；UNIQUE (rule_id)；FK plan_id CASCADE；FK rule_id → watch_rules CASCADE | 联合键即编译幂等键；一规则最多属一计划 |
| trading_plan_events | PK id；idx (plan_id, created_at)；FK plan_id CASCADE | 时间线 |
| plan_reflections | PK id；UNIQUE (plan_id, kind, period, version)；FK plan_id CASCADE | 同周期重写 = version+1 新行（旧报告保留可查） |

- **不加 CHECK 枚举约束**（data-model.md 明确：值域由应用层把守，给未来扩枚举留余地）；
- **归因列不设默认值、不回填**：NULL 语义是「不参评 / 计划外」，与 watch 系
  `position_state` 的 fail-open 口径一致；
- FK `watch_rules.plan_id` / `simulation_trades.plan_id` 用 `ON DELETE SET NULL`：
  计划行被删时历史成交与规则留存，归属回到「计划外」，不阻塞删除、不丢历史。

## 幂等（重跑 0 变更）

- 建表 `CREATE TABLE IF NOT EXISTS`；索引 `CREATE INDEX IF NOT EXISTS`；
- 唯一/外键约束**不写在 CREATE TABLE 里**，而是逐条查 `information_schema.table_constraints`
  后再 `ALTER TABLE ... ADD CONSTRAINT`——这样「上一次跑到一半、表已建但约束没建」的半成品
  也能被重跑补齐（否则 IF NOT EXISTS 会把缺约束的表永远跳过）；
- 列 `ADD COLUMN IF NOT EXISTS`（另加 information_schema 预检，供 dry-run 报告）；
- 表/列 COMMENT 只在**本次新建**时写（重跑不再执行，保证「0 变更」名副其实）。

## 失败模式与回滚

- 任一 DDL 失败 → 整个 `main()` 的事务回滚（`eng.begin()`），不留半成品；
- 回滚动作：`DROP TABLE` 新五表（自带 CASCADE 约束随之消失），既有表归因列**保留无害**
  （新代码见缺列/NULL 一律 fail-open，见 data-model.md「失败模式与回滚」）；
- 迁移必须先于任何代码上线（表结构是编译器与归因的先决条件）。

## 用法（在 quantsys-v2/ 下）

```bash
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105_trading_plan.py            # dry-run（默认，不写库）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105_trading_plan.py --apply    # 写库
# 生产库与 *_test 库各执行一次（--dsn / --schema 可显式指定）

# 自检（verify）只在 --apply 之后执行：缺表/缺列/缺约束 → VERIFY FAILED + 退出码 2。
# 纯查看（不写库）直接用 SQL：
#   select table_name from information_schema.tables where table_schema='quant'
#     and (table_name like 'trading_plan%' or table_name = 'plan_reflections');
```

退出码：0 = 成功（dry-run 完成 / apply 后自检通过）；2 = apply 后自检缺表/缺列/缺约束。
"""
from __future__ import annotations

import argparse
import os
import re
from typing import Optional, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

DEFAULT_SCHEMA = 'quant'

PLANS = 'trading_plans'
VERSIONS = 'trading_plan_versions'
RULES = 'trading_plan_rules'
EVENTS = 'trading_plan_events'
REFLECTIONS = 'plan_reflections'

#: 本迁移新建的表（顺序 = 建表顺序；被引用者在前）
NEW_TABLES = (PLANS, VERSIONS, RULES, EVENTS, REFLECTIONS)

#: 既有表（本迁移只加列，不改既有列语义）
EXISTING_TABLES = ('watch_rules', 'simulation_trades')

#: (表, 列, 列定义) —— 既有表只加可空列：无默认值、无回填（NULL = 非托管 / 计划外）
NEW_COLUMNS = (
    ('watch_rules', 'plan_id', 'integer'),
    ('simulation_trades', 'plan_id', 'integer'),
    ('simulation_trades', 'plan_version', 'integer'),
)

#: CREATE TABLE 语句（PK 内联；唯一/外键约束走 ensure_constraint，便于半成品补齐）
TABLE_DDL = {
    PLANS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plans (
    id serial PRIMARY KEY,
    account varchar(60) NOT NULL,
    name varchar(120) NOT NULL,
    horizon varchar(16) NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'draft',
    spec jsonb NOT NULL,
    draft_spec jsonb,
    version integer NOT NULL DEFAULT 1,
    stats jsonb,
    review_interval_days integer DEFAULT 1,
    review_due_at timestamptz,
    last_reflected_at timestamptz,
    reflection_overdue_count integer NOT NULL DEFAULT 0,
    activated_at timestamptz,
    closed_at timestamptz,
    close_reason text,
    created_by varchar(50) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
)""",
    VERSIONS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_versions (
    id serial PRIMARY KEY,
    plan_id integer NOT NULL,
    version integer NOT NULL,
    spec jsonb NOT NULL,
    baseline jsonb,
    window_days integer DEFAULT 10,
    window_ends_at date,
    change_reason text,
    hypothesis jsonb,
    created_by varchar(50) NOT NULL,
    decision_audit_id varchar(64),
    created_at timestamptz NOT NULL DEFAULT now()
)""",
    RULES: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_rules (
    plan_id integer NOT NULL,
    rule_id integer NOT NULL,
    role varchar(24) NOT NULL,
    symbol varchar(20) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (plan_id, role, symbol)
)""",
    EVENTS: """CREATE TABLE IF NOT EXISTS {schema}.trading_plan_events (
    id serial PRIMARY KEY,
    plan_id integer NOT NULL,
    kind varchar(24) NOT NULL,
    from_status varchar(16),
    to_status varchar(16),
    detail jsonb,
    reason text,
    actor varchar(50) NOT NULL,
    decision_audit_id varchar(64),
    created_at timestamptz NOT NULL DEFAULT now()
)""",
    REFLECTIONS: """CREATE TABLE IF NOT EXISTS {schema}.plan_reflections (
    id serial PRIMARY KEY,
    plan_id integer NOT NULL,
    kind varchar(16) NOT NULL,
    period varchar(16) NOT NULL,
    version integer NOT NULL DEFAULT 1,
    evidence_pack jsonb NOT NULL,
    answers jsonb NOT NULL,
    verdict varchar(16) NOT NULL,
    reasoning text,
    actions jsonb,
    knowledge_updates jsonb,
    agent_session_id varchar(120),
    created_at timestamptz NOT NULL DEFAULT now()
)""",
}

#: (表, 约束名, 约束定义) —— 逐条查 information_schema 后 ADD（幂等且可补半成品）
UNIQUE_CONSTRAINTS = (
    (VERSIONS, 'uq_trading_plan_versions_plan_version', 'UNIQUE (plan_id, version)'),
    (RULES, 'uq_trading_plan_rules_rule_id', 'UNIQUE (rule_id)'),
    (REFLECTIONS, 'uq_plan_reflections_period_version',
     'UNIQUE (plan_id, kind, period, version)'),
)

#: (表, 约束名, 约束定义, 被引用表或 None) —— 第 4 项 = 建约束前必须存在的表（临时 schema 演练用）
FOREIGN_KEYS = (
    (VERSIONS, 'fk_trading_plan_versions_plan_id',
     'FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE CASCADE', None),
    (RULES, 'fk_trading_plan_rules_plan_id',
     'FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE CASCADE', None),
    (RULES, 'fk_trading_plan_rules_rule_id',
     'FOREIGN KEY (rule_id) REFERENCES {schema}.watch_rules (id) ON DELETE CASCADE', 'watch_rules'),
    (EVENTS, 'fk_trading_plan_events_plan_id',
     'FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE CASCADE', None),
    (REFLECTIONS, 'fk_plan_reflections_plan_id',
     'FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE CASCADE', None),
    # 既有表归因列：计划行删除 → 归属回 NULL（历史留存，语义回到「计划外」）
    ('watch_rules', 'fk_watch_rules_plan_id',
     'FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE SET NULL', None),
    ('simulation_trades', 'fk_simulation_trades_plan_id',
     'FOREIGN KEY (plan_id) REFERENCES {schema}.trading_plans (id) ON DELETE SET NULL', None),
)

#: (表, 索引名, 建索引 SQL)
INDEXES = (
    (PLANS, 'idx_trading_plans_account_status',
     'CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plans (account, status)'),
    (PLANS, 'idx_trading_plans_review_due_at',
     'CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plans (review_due_at)'),
    (EVENTS, 'idx_trading_plan_events_plan_created',
     'CREATE INDEX IF NOT EXISTS {index} ON {schema}.trading_plan_events (plan_id, created_at)'),
    # 编译 diff 按 plan_id 取托管规则；FK 不自动建索引
    ('watch_rules', 'idx_watch_rules_plan_id',
     'CREATE INDEX IF NOT EXISTS {index} ON {schema}.watch_rules (plan_id)'),
    # 计划内/外成交分组统计（FR-7）
    ('simulation_trades', 'idx_simulation_trades_plan_id',
     'CREATE INDEX IF NOT EXISTS {index} ON {schema}.simulation_trades (plan_id)'),
)

TABLE_COMMENTS = {
    PLANS: '交易计划本体（REQ-261021222905-6dff）：spec 四段 targets/entry/exit/monitoring+schedule；'
           'status 值域由应用层把守（draft/active/holding/closing/closed/archived/paused）',
    VERSIONS: '交易计划版本快照：每次 apply 一行，行不可变（修改对照的基线来源）',
    RULES: '计划编译产物映射：plan_id+role+symbol 为幂等键，rule_id 一规则最多属一计划',
    EVENTS: '计划事件留痕：状态变迁/spec 修改/编译/drift/反思/成交归因的时间线',
    REFLECTIONS: '计划反思报告+材料包快照：同 (plan_id,kind,period) 重写时 version+1 新行',
}

COLUMN_COMMENTS = {
    ('watch_rules', 'plan_id'): '托管归属计划 id（NULL=非托管/通用规则）：编译产物回填，'
                                '驱动规则收敛与修改对照',
    ('simulation_trades', 'plan_id'): '成交的计划归因（NULL=计划外）：FR-4 归因与统计分组',
    ('simulation_trades', 'plan_version'): '成交时的计划版本（实验对照用，NULL=无版本）',
}

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


# ── 基础设施 ─────────────────────────────────────────────────────────────
def _ident(name: str) -> str:
    """schema/表名只接受合法标识符（本模块支持测试/演练用参数化 schema）。"""
    if not _IDENT_RE.match(name or ''):
        raise ValueError('非法标识符: %r' % (name,))
    return name


def _engine(dsn: Optional[str] = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


# ── 预检：现状读取 ───────────────────────────────────────────────────────
def table_exists(conn: Connection, schema: str, table: str) -> bool:
    row = conn.execute(text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_name = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).first()
    return row is not None


def column_names(conn: Connection, schema: str, table: str) -> set[str]:
    rows = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).fetchall()
    return {r[0] for r in rows}


def constraint_names(conn: Connection, schema: str, table: str) -> set[str]:
    rows = conn.execute(text(
        "SELECT constraint_name FROM information_schema.table_constraints "
        "WHERE table_schema = :schema AND table_name = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).fetchall()
    return {r[0] for r in rows}


def index_names(conn: Connection, schema: str, table: str) -> set[str]:
    rows = conn.execute(text(
        "SELECT indexname FROM pg_indexes "
        "WHERE schemaname = :schema AND tablename = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).fetchall()
    return {r[0] for r in rows}


def _comment_literal(value: str) -> str:
    """COMMENT 的注释体必须是字面量（PostgreSQL 不接受绑定参数）。"""
    return "'" + value.replace("'", "''") + "'"


def _table_present(conn: Connection, schema: str, table: str, *, apply: bool) -> bool:
    """目标表是否可用：已存在；或（dry-run 时）属于本迁移将新建的表。

    dry-run 不建表，但依赖新表的约束/索引**不是**「跳过」，而是「将会创建」——
    否则 dry-run 报告会把 10 个约束里的 7 个误报成 skipped，与 --apply 结果对不上。
    """
    return table_exists(conn, schema, table) or (not apply and table in NEW_TABLES)


# ── 幂等 DDL 单元 ────────────────────────────────────────────────────────
def ensure_table(conn: Connection, schema: str, table: str, *,
                 apply: bool = True) -> dict:
    """建表（IF NOT EXISTS）。已存在 → exists；dry-run → would-create。"""
    schema, table = _ident(schema), _ident(table)
    if table_exists(conn, schema, table):
        return {'table': table, 'status': 'exists'}
    if not apply:
        return {'table': table, 'status': 'would-create'}
    conn.execute(text(TABLE_DDL[table].format(schema=schema)))
    if table in TABLE_COMMENTS:
        conn.execute(text('COMMENT ON TABLE %s.%s IS %s'
                          % (schema, table, _comment_literal(TABLE_COMMENTS[table]))))
    return {'table': table, 'status': 'created'}


def ensure_column(conn: Connection, schema: str, table: str, column: str,
                  ddl_type: str, *, apply: bool = True) -> dict:
    """加列（IF NOT EXISTS）。目标表不存在 → skipped-no-table（不失败，便于分库/新环境）。"""
    schema, table, column = _ident(schema), _ident(table), _ident(column)
    if not _table_present(conn, schema, table, apply=apply):
        return {'table': table, 'column': column, 'status': 'skipped-no-table'}
    if column in column_names(conn, schema, table):
        return {'table': table, 'column': column, 'status': 'exists'}
    if not apply:
        return {'table': table, 'column': column, 'status': 'would-add'}
    conn.execute(text('ALTER TABLE %s.%s ADD COLUMN IF NOT EXISTS %s %s'
                      % (schema, table, column, ddl_type)))
    comment = COLUMN_COMMENTS.get((table, column))
    if comment:
        conn.execute(text('COMMENT ON COLUMN %s.%s.%s IS %s'
                          % (schema, table, column, _comment_literal(comment))))
    return {'table': table, 'column': column, 'status': 'added'}


def ensure_constraint(conn: Connection, schema: str, table: str, name: str,
                      definition: str, *, apply: bool = True,
                      requires: Optional[str] = None) -> dict:
    """加约束（逐条预检后 ADD，不用 IF NOT EXISTS——PG14 的 ADD CONSTRAINT 没有该语法）。"""
    schema, table, name = _ident(schema), _ident(table), _ident(name)
    if not _table_present(conn, schema, table, apply=apply):
        return {'table': table, 'constraint': name, 'status': 'skipped-no-table'}
    if requires and not _table_present(conn, schema, requires, apply=apply):
        return {'table': table, 'constraint': name,
                'status': 'skipped-no-%s' % requires}
    if name in constraint_names(conn, schema, table):
        return {'table': table, 'constraint': name, 'status': 'exists'}
    if not apply:
        return {'table': table, 'constraint': name, 'status': 'would-create'}
    conn.execute(text('ALTER TABLE %s.%s ADD CONSTRAINT %s %s'
                      % (schema, table, name, definition.format(schema=schema))))
    return {'table': table, 'constraint': name, 'status': 'created'}


def ensure_index(conn: Connection, schema: str, table: str, name: str,
                 sql: str, *, apply: bool = True) -> dict:
    """建索引（CREATE INDEX IF NOT EXISTS）。表不存在 → skipped-no-table。"""
    schema, table, name = _ident(schema), _ident(table), _ident(name)
    if not _table_present(conn, schema, table, apply=apply):
        return {'table': table, 'index': name, 'status': 'skipped-no-table'}
    if name in index_names(conn, schema, table):
        return {'table': table, 'index': name, 'status': 'exists'}
    if not apply:
        return {'table': table, 'index': name, 'status': 'would-create'}
    conn.execute(text(sql.format(schema=schema, index=name)))
    return {'table': table, 'index': name, 'status': 'created'}


# ── 编排 ─────────────────────────────────────────────────────────────────
_CHANGE_STATUSES = ('created', 'added', 'would-create', 'would-add')


def apply_migration(conn: Connection, schema: str = DEFAULT_SCHEMA, *,
                    apply: bool = True) -> dict:
    """整体执行：建表 → 加列 → 唯一约束 → 外键 → 索引。

    返回报告：{'schema', 'tables', 'columns', 'constraints', 'indexes',
    'skipped', 'changes'}。apply=False 时只做预检，不执行任何 DDL（dry-run），
    此时所有 changes 都是 would-*，据此可与重跑对照判「0 变更」。
    """
    schema = _ident(schema)
    report: dict = {'schema': schema, 'tables': [], 'columns': [],
                    'constraints': [], 'indexes': [], 'skipped': [], 'changes': 0}

    for table in NEW_TABLES:
        report['tables'].append(ensure_table(conn, schema, table, apply=apply))

    for table, column, ddl_type in NEW_COLUMNS:
        report['columns'].append(
            ensure_column(conn, schema, table, column, ddl_type, apply=apply))

    for table, name, definition in UNIQUE_CONSTRAINTS:
        report['constraints'].append(
            ensure_constraint(conn, schema, table, name, definition, apply=apply))

    for table, name, definition, requires in FOREIGN_KEYS:
        report['constraints'].append(
            ensure_constraint(conn, schema, table, name, definition,
                              apply=apply, requires=requires))

    for table, name, sql in INDEXES:
        report['indexes'].append(
            ensure_index(conn, schema, table, name, sql, apply=apply))

    for section in ('tables', 'columns', 'constraints', 'indexes'):
        for item in report[section]:
            if item['status'] in _CHANGE_STATUSES:
                report['changes'] += 1
            elif item['status'].startswith('skipped'):
                report['skipped'].append(item)
    return report


def verify(conn: Connection, schema: str = DEFAULT_SCHEMA) -> dict:
    """apply 后自检：五表 / 3 列 / 7 约束 / 5 索引是否全部就位。

    返回 {'ok', 'missing', 'present', 'expected'}；ok=False 时 main() 退出码 2。
    """
    schema = _ident(schema)
    missing: list[str] = []
    present = {'tables': 0, 'columns': 0, 'constraints': 0, 'indexes': 0}

    for table in NEW_TABLES:
        if table_exists(conn, schema, table):
            present['tables'] += 1
        else:
            missing.append('table %s.%s' % (schema, table))

    for table, column, _ddl in NEW_COLUMNS:
        if table_exists(conn, schema, table) and column in column_names(conn, schema, table):
            present['columns'] += 1
        else:
            missing.append('column %s.%s.%s' % (schema, table, column))

    all_constraints = [(t, n) for t, n, _d in UNIQUE_CONSTRAINTS]
    all_constraints += [(t, n) for t, n, _d, _r in FOREIGN_KEYS]
    for table, name in all_constraints:
        if table_exists(conn, schema, table) and name in constraint_names(conn, schema, table):
            present['constraints'] += 1
        else:
            missing.append('constraint %s.%s' % (table, name))

    for table, name, _sql in INDEXES:
        if table_exists(conn, schema, table) and name in index_names(conn, schema, table):
            present['indexes'] += 1
        else:
            missing.append('index %s.%s' % (table, name))

    expected = {
        'tables': len(NEW_TABLES),
        'columns': len(NEW_COLUMNS),
        'constraints': len(UNIQUE_CONSTRAINTS) + len(FOREIGN_KEYS),
        'indexes': len(INDEXES),
    }
    return {'ok': not missing, 'missing': missing,
            'present': present, 'expected': expected}


# ── 报告 ─────────────────────────────────────────────────────────────────
def format_report(report: dict, *, applied: bool) -> list[str]:
    """把报告投影成人读的行（每行一条增量/状态）。"""
    tag = 'APPLY ' if applied else 'DRY   '
    lines: list[str] = []

    def _name(item: dict) -> str:
        if 'column' in item:
            return '%s.%s' % (item['table'], item['column'])
        if 'constraint' in item:
            return '%s.%s' % (item['table'], item['constraint'])
        if 'index' in item:
            return '%s.%s' % (item['table'], item['index'])
        return 'quant.%s' % (item['table'],)

    def _emit(kind: str, item: dict) -> None:
        lines.append('%s%-10s %-13s %s' % (tag, kind, item['status'], _name(item)))

    for item in report['tables']:
        _emit('table', item)
    for item in report['columns']:
        _emit('column', item)
    for item in report['constraints']:
        _emit('constraint', item)
    for item in report['indexes']:
        _emit('index', item)
    return lines


def build_parser() -> argparse.ArgumentParser:
    """CLI 定义（独立成函数便于测试「dry-run 是默认值」这一约定）。"""
    parser = argparse.ArgumentParser(
        description='quant schema 交易计划五表 + 既有表归因列（dry-run 默认 / --apply 写库）')
    parser.add_argument('--apply', action='store_true',
                        help='实际写库（默认 dry-run：只预检与报告，不执行任何 DDL）')
    parser.add_argument('--schema', default=DEFAULT_SCHEMA,
                        help='目标 schema（默认 quant）')
    parser.add_argument('--dsn', default=None,
                        help='显式数据库 DSN（默认 QUANT_DATABASE_URL，再退 PG 默认库）')
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    eng = _engine(args.dsn)
    with eng.begin() as conn:
        report = apply_migration(conn, args.schema, apply=args.apply)
        for line in format_report(report, applied=args.apply):
            print(line)
        print('%s summary: schema=%s · %d 表 · 既有表加列 %d 列 / %d 表 · %d 约束 · %d 索引 · changes=%d%s'
              % ('APPLY' if args.apply else 'DRY  ', report['schema'],
                 len(NEW_TABLES), len(NEW_COLUMNS), len(EXISTING_TABLES),
                 len(UNIQUE_CONSTRAINTS) + len(FOREIGN_KEYS), len(INDEXES),
                 report['changes'],
                 '' if args.apply else '（dry-run 未写库）'))

    if not args.apply:
        print('DRY-RUN done（--apply 才写库；请对生产库与 *_test 库各执行一次）')
        return 0

    with eng.connect() as conn:
        result = verify(conn, args.schema)
        exp, got = result['expected'], result['present']
        if not result['ok']:
            print('VERIFY FAILED: 缺失 %s' % (result['missing'],))
            return 2
        print('VERIFY OK: %d/%d tables · %d/%d columns · %d/%d constraints · %d/%d indexes'
              % (got['tables'], exp['tables'], got['columns'], exp['columns'],
                 got['constraints'], exp['constraints'], got['indexes'], exp['indexes']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
