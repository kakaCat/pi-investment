#!/usr/bin/env python
"""quant.watch_rules 增列 position_state / interval_sec + 按持仓回填（2026-10-21 · RFC 017）

## 做什么

RFC 017（盯盘执行闭环 · 持仓状态显式化 · 分标的频率）要求规则自带两项运行时前提：

1. `position_state varchar(16) NOT NULL DEFAULT 'none'` —— 规则当前面对的是
   「无持仓（none）」还是「有持仓（holding）」。引擎据此显式分支（entry 族只在 none
   求值、exit 族只在 holding 求值；状态不可信时 fail-open 照常评估）。
2. `interval_sec integer NULL` —— 规则级盯盘频率（秒）。**NULL = 跟随全局档**
   （base 60s / fast 10s），不设默认值，避免改变存量规则的节奏。

### 回填口径（RFC 017 §2.2 / §3）

`position_state='holding'` 的条件（全部满足）：

- 存在同标的、数量为正的持仓：`coalesce(shares_total, 0) > 0`；
- **账户匹配**：`linked_account` 为空（通用观察/无主规则）→ 任意账户的持仓都算；
  `linked_account` 有值 → 只认该账户（`simulation_positions.account_name`）的持仓。
  账户串两端 btrim（历史数据里见过尾部空格），空串按"无账户"处理；
- **标的归一**：规则与持仓的 symbol 可能一端带交易所后缀一端不带
  （规则常存 `600519`，持仓常存 `600519.SH`）→ 代码段（`.` 前缀）相等即视为同标的；
  两端都带后缀时还要求后缀一致，否则 `000001.SH`（指数）会把 `000001.SZ`（平安银行）
  的持仓误算进去。

### 与 RFC 原文的两处订正（以真实库表为准）

RFC §3 写的是 `quant.simulation_position` + `p.quantity` + `p.account`；
本仓真实表是 **`quant.simulation_positions`（复数）**，列是
**`account_name` / `shares_total`**（2026-10-21 实测 `information_schema`）。
若照 RFC 字面执行，语句会直接 UndefinedTable/UndefinedColumn —— 故此处按真实
schema 落 SQL，语义（linked_account + symbol + 正持仓）与 RFC 完全一致。

### 幂等

- DDL 一律 `ADD COLUMN IF NOT EXISTS`（另加 information_schema 预检，便于 dry-run 报告）；
- 回填带 `position_state IS DISTINCT FROM 'holding'`：第二次执行更新 **0 行**，
  且不会把已被 fill 事件写成 holding、但持仓表尚未同步的规则刷回去；
- 回填是**单向晋升**（只 none→holding），不是对账器：持仓消失后的 holding→none
  由 fill 事件与 `position_lifecycle` 日频对账负责。迁移重跑不覆盖运行时状态。

### 回滚

列保留无害（RFC 017 §3）：引擎/仓储见缺列或 NULL 都按旧行为 fail-open
（见 `adapters/outbound/repositories/watch_rule_repository.py` 的列预检分支）。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261021_watch_rules_position_interval.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261021_watch_rules_position_interval.py --apply
    # 生产库与 *_test 库各执行一次（--dsn 可显式指定）
"""
from __future__ import annotations

import argparse
import os
import re
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

DEFAULT_SCHEMA = 'quant'
RULES_TABLE = 'watch_rules'
POSITIONS_TABLE = 'simulation_positions'

#: (列名, 列定义)。position_state 用 DB 默认 'none' 兜住存量行；interval_sec 可空。
NEW_COLUMNS = (
    ('position_state', "varchar(16) NOT NULL DEFAULT 'none'"),
    ('interval_sec', 'integer'),
)

COLUMN_COMMENTS = {
    'position_state': (
        '规则面对的持仓状态（RFC 017）：none=无持仓 / holding=有持仓；'
        '驱动 entry 族与 exit 族的显式求值分支，NULL/缺列按 fail-open 处理'
    ),
    'interval_sec': (
        '规则级盯盘频率（秒，RFC 017 §2.3）：NULL=跟随全局 base/fast 档；'
        '引擎按规则算 next_due_at，下限由引擎保护（5s）'
    ),
}

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

#: 回填的 EXISTS 判据（账户匹配 + 标的归一 + 正持仓）。schema 经 _ident 校验后格式化。
_BACKFILL_EXISTS = """
        EXISTS (
            SELECT 1
              FROM {schema}.{positions} p
             WHERE coalesce(p.shares_total, 0) > 0
               AND split_part(p.symbol, '.', 1) = split_part(r.symbol, '.', 1)
               AND (
                    strpos(r.symbol, '.') = 0
                    OR strpos(p.symbol, '.') = 0
                    OR upper(split_part(r.symbol, '.', 2)) = upper(split_part(p.symbol, '.', 2))
               )
               AND (
                    NULLIF(btrim(r.linked_account), '') IS NULL
                    OR btrim(p.account_name) = btrim(r.linked_account)
               )
        )
"""


def _ident(name: str) -> str:
    """schema/表名只接受合法标识符（本模块用参数化 schema 供测试建临时 schema）。"""
    if not _IDENT_RE.match(name or ''):
        raise ValueError('非法标识符: %r' % (name,))
    return name


def _engine(dsn: Optional[str] = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def table_exists(conn: Connection, schema: str = DEFAULT_SCHEMA,
                 table: str = RULES_TABLE) -> bool:
    row = conn.execute(text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_name = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).first()
    return row is not None


def column_names(conn: Connection, schema: str = DEFAULT_SCHEMA,
                 table: str = RULES_TABLE) -> set[str]:
    rows = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).fetchall()
    return {r[0] for r in rows}


def ensure_columns(conn: Connection, schema: str = DEFAULT_SCHEMA,
                   *, apply: bool = True) -> list[dict]:
    """幂等建列。返回 [{column, status}]，status ∈ added/exists/would-add。

    apply=False 时只做预检与报告，不执行任何 DDL（dry-run）。
    """
    schema = _ident(schema)
    if not table_exists(conn, schema, RULES_TABLE):
        raise RuntimeError('表不存在: %s.%s（无法加列）' % (schema, RULES_TABLE))
    present = column_names(conn, schema, RULES_TABLE)
    results = []
    for name, ddl_type in NEW_COLUMNS:
        stmt = ('ALTER TABLE %s.%s ADD COLUMN IF NOT EXISTS %s %s'
                % (schema, RULES_TABLE, name, ddl_type))
        if name in present:
            results.append({'column': name, 'status': 'exists'})
            continue
        if apply:
            conn.execute(text(stmt))
            # COMMENT 的注释体必须是字面量（PostgreSQL 不接受绑定参数），转义后内联
            comment_sql = COLUMN_COMMENTS[name].replace("'", "''")
            conn.execute(text(
                'COMMENT ON COLUMN %s.%s.%s IS \'%s\''
                % (schema, RULES_TABLE, name, comment_sql)
            ))
            results.append({'column': name, 'status': 'added'})
        else:
            results.append({'column': name, 'status': 'would-add'})
    return results


def _backfill_exists_sql(schema: str) -> str:
    return _BACKFILL_EXISTS.format(schema=_ident(schema),
                                   positions=_ident(POSITIONS_TABLE))


def count_backfill_candidates(conn: Connection, schema: str = DEFAULT_SCHEMA) -> int:
    """回填候选数（有正持仓的规则数）。不依赖新列，dry-run 也能算。"""
    sql = ('SELECT count(*) FROM %s.%s r WHERE %s'
           % (_ident(schema), RULES_TABLE, _backfill_exists_sql(schema)))
    return int(conn.execute(text(sql)).scalar() or 0)


def backfill_position_state(conn: Connection, schema: str = DEFAULT_SCHEMA,
                            *, apply: bool = True) -> int:
    """按持仓把规则 position_state 晋升为 holding。

    返回值：apply=True 时是**实际更新行数**；apply=False（dry-run）时是
    **将会更新的候选数**——两者口径都是"有正持仓且当前非 holding 的规则数"
    （`IS DISTINCT FROM 'holding'` 保证重跑 0 行，且单向晋升、
    绝不把 holding 刷回 none：运行时状态由 fill 事件/日频对账维护）。
    """
    schema = _ident(schema)
    if 'position_state' not in column_names(conn, schema, RULES_TABLE):
        if apply:
            raise RuntimeError('position_state 列不存在：请先 ensure_columns(apply=True)')
        return 0
    if not table_exists(conn, schema, POSITIONS_TABLE):
        # 没有持仓表 = 没有可回填的证据，保持 DB 默认 none（不失败，便于分库/新环境）
        return 0
    sql = (
        'UPDATE %s.%s r SET position_state = \'holding\''
        ' WHERE r.position_state IS DISTINCT FROM \'holding\''
        '   AND %s'
        % (schema, RULES_TABLE, _backfill_exists_sql(schema))
    )
    if not apply:
        return count_backfill_candidates(conn, schema)
    return int(conn.execute(text(sql)).rowcount or 0)


def column_info(conn: Connection, schema: str = DEFAULT_SCHEMA,
                table: str = RULES_TABLE) -> dict:
    """列元数据（{name: {nullable, default, type}}），供 --apply 后自检与测试断言。"""
    rows = conn.execute(text(
        "SELECT column_name, is_nullable, column_default, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table"
    ), {'schema': _ident(schema), 'table': _ident(table)}).fetchall()
    return {r[0]: {'nullable': r[1], 'default': r[2], 'type': r[3]} for r in rows}


def apply_migration(conn: Connection, schema: str = DEFAULT_SCHEMA,
                    *, apply: bool = True) -> dict:
    """整体执行：建列 → 回填。

    返回 {schema, columns, candidates, backfilled}；dry-run 时 backfilled=0
    （不写库），candidates 为"将会晋升"的规则数。
    """
    columns = ensure_columns(conn, schema, apply=apply)
    candidates = count_backfill_candidates(conn, schema) if table_exists(
        conn, schema, POSITIONS_TABLE) else 0
    backfilled = backfill_position_state(conn, schema, apply=True) if apply else 0
    return {'schema': schema, 'columns': columns,
            'candidates': candidates, 'backfilled': backfilled}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='watch_rules 加 position_state/interval_sec 并按持仓回填')
    parser.add_argument('--apply', action='store_true', help='实际写库（默认 dry-run）')
    parser.add_argument('--schema', default=DEFAULT_SCHEMA, help='目标 schema（默认 quant）')
    parser.add_argument('--dsn', default=None, help='显式数据库 DSN（默认 QUANT_DATABASE_URL）')
    args = parser.parse_args(argv)

    eng = _engine(args.dsn)
    tag = 'APPLY ' if args.apply else 'DRY   '
    with eng.begin() as conn:
        result = apply_migration(conn, args.schema, apply=args.apply)
        for col in result['columns']:
            print('%sADD COLUMN %s.%s %-16s %s'
                  % (tag, args.schema, RULES_TABLE, col['column'], col['status']))
        if args.apply:
            print('%s回填：候选 %d 条，实际晋升 holding %d 条'
                  % (tag, result['candidates'], result['backfilled']))
        else:
            print('%s回填：将晋升 holding %d 条（dry-run 未写库）'
                  % (tag, result['candidates']))

    if not args.apply:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
        return 0

    with eng.connect() as conn:
        info = column_info(conn, args.schema)
        missing = [n for n, _ in NEW_COLUMNS if n not in info]
        if missing:
            print('VERIFY FAILED: 缺列 %s' % (missing,))
            return 2
        print('VERIFY OK: position_state(nullable=%s default=%s) / interval_sec(nullable=%s default=%s)'
              % (info['position_state']['nullable'], info['position_state']['default'],
                 info['interval_sec']['nullable'], info['interval_sec']['default']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
