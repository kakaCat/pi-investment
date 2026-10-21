#!/usr/bin/env python
"""新建 quant.watch_outcome_checks（2026-10-20 · P3 预判验证闭环）

每条盯盘触发（含 suppressed 的「触及未确认」样本）在触发后第 5/10/20 个交易日
回填一次走势对照：check_date 收盘价 vs 触发价、预判方向、是否命中。
这是「盘感样本库」的事实表：复盘命中率、伏击点质量都从这里出。

幂等：CREATE TABLE IF NOT EXISTS + 唯一约束（trigger_id, horizon_td）。
默认 dry-run，`--apply` 写库。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261020_watch_outcome_checks.py --apply
"""
import argparse
import os

from sqlalchemy import create_engine, text


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


DDL = [
    """
    CREATE TABLE IF NOT EXISTS quant.watch_outcome_checks (
        id serial PRIMARY KEY,
        trigger_id integer NOT NULL,
        rule_id integer,
        symbol varchar(20) NOT NULL,
        horizon_td integer NOT NULL,
        trigger_at timestamp,
        trigger_price numeric(12,4),
        expected_direction varchar(8),
        check_date date,
        close_price numeric(12,4),
        pct_change numeric(10,4),
        hit boolean,
        note text,
        created_at timestamp NOT NULL DEFAULT now()
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_watch_outcome_checks_trigger_horizon
       ON quant.watch_outcome_checks (trigger_id, horizon_td)""",
    """CREATE INDEX IF NOT EXISTS idx_watch_outcome_checks_rule
       ON quant.watch_outcome_checks (rule_id, check_date DESC)""",
    """COMMENT ON TABLE quant.watch_outcome_checks IS
       '盯盘触发走势回填（P3 预判验证闭环）：触发后第5/10/20交易日收盘对照，命中率事实表'""",
]

VERIFY = "select count(*) from quant.watch_outcome_checks"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    eng = _engine()
    with eng.begin() as conn:
        for ddl in DDL:
            if args.apply:
                conn.execute(text(ddl))
            print(('APPLY ' if args.apply else 'DRY   ') + ddl.strip().split(chr(10))[0][:90])
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY)).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
