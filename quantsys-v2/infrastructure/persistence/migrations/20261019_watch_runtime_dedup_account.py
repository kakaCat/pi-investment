#!/usr/bin/env python
"""quant.watch_runtime_dedup 主键加 account 维度（2026-10-19 · qs_watch P0-2 审查修复）

背景：引擎 dedup_key 从 (symbol, direction) 改为 (account, symbol, direction)——
账户是投送维度（digest 按「账户×标的」聚合、同标的两账户绝不合并），去重键不含
账户时，B 账户的同标的同向触发会被 A 账户窗内通知吞掉（deduped 不在 UNRESOLVED
里），该账户信号从所有通道消失。持久化侧主键必须同步，否则 upsert 的
ON CONFLICT (symbol, direction) 会把不同账户的键互相覆盖。

ORM：infrastructure/persistence/orm/models/watch_todo.py WatchRuntimeDedup；
仓储：adapters/outbound/repositories/watch_runtime_state_repository.py
（load_dedup / upsert_dedup）。

存量行：account 回填为 ''（未归属桶），与新键不冲突（新键带真实账户或 ''），
窗口外由 prune 自然过期。幂等：ADD COLUMN IF NOT EXISTS + 约束存在性检查。
默认 dry-run，`--apply` 写库。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_runtime_dedup_account.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_runtime_dedup_account.py --apply
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
    "ALTER TABLE quant.watch_runtime_dedup "
    "ADD COLUMN IF NOT EXISTS account varchar(64) NOT NULL DEFAULT ''",
    "COMMENT ON COLUMN quant.watch_runtime_dedup.account IS "
    "'规则归属账户（linked_account 优先；空串=未归属）。2026-10-19 起为去重键一部分'",
    "ALTER TABLE quant.watch_runtime_dedup DROP CONSTRAINT IF EXISTS watch_runtime_dedup_pkey",
    """DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'watch_runtime_dedup_pkey'
      AND conrelid = 'quant.watch_runtime_dedup'::regclass
  ) THEN
    ALTER TABLE quant.watch_runtime_dedup
      ADD CONSTRAINT watch_runtime_dedup_pkey PRIMARY KEY (account, symbol, direction);
  END IF;
END $$""",
]

# ── 测试库同步（tests/_db_schema_sync.py）消费的结构化声明 ──────────────
# COLUMNS 走同步器的 ADD COLUMN IF NOT EXISTS 路径；
# IDEMPOTENT_DDL 由同步器逐条原样执行（全部幂等：IF EXISTS / 约束存在性检查）。
COLUMNS = [
    ('watch_runtime_dedup', 'account', "varchar(64) NOT NULL DEFAULT ''"),
]
IDEMPOTENT_DDL = [
    "ALTER TABLE quant.watch_runtime_dedup DROP CONSTRAINT IF EXISTS watch_runtime_dedup_pkey",
    """DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'watch_runtime_dedup_pkey'
      AND conrelid = 'quant.watch_runtime_dedup'::regclass
  ) THEN
    ALTER TABLE quant.watch_runtime_dedup
      ADD CONSTRAINT watch_runtime_dedup_pkey PRIMARY KEY (account, symbol, direction);
  END IF;
END $$""",
]

VERIFY = ("select account from quant.watch_runtime_dedup limit 1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    eng = _engine()
    with eng.begin() as conn:
        for ddl in DDL:
            if args.apply:
                conn.execute(text(ddl))
            print(('APPLY ' if args.apply else 'DRY   ') + ddl[:90].replace('\n', ' '))
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY)).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
