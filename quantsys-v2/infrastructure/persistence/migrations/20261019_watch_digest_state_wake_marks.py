#!/usr/bin/env python
"""quant.watch_digest_state 加 wake_marks 列（2026-10-19 · qs_watch 审查 P1-5）

支撑「逐账户唤醒水位」：摘要门按账户分段投送，此前水位线（last_wake_at）是全局的——
部分账户唤醒成功就推进全局水位，失败账户的触发被 since 过滤出增量段，只剩 backlog
计数、永不进摘要分组。wake_marks = {账户: ISO 时间}，唤醒成功才推进该账户的水位。

ORM：infrastructure/persistence/orm/models/watch_state.py WatchDigestState；
仓储：adapters/outbound/repositories/watch_state_repository.py（load_state/save_wake）。

幂等：ADD COLUMN IF NOT EXISTS。默认 dry-run，`--apply` 写库。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_digest_state_wake_marks.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_digest_state_wake_marks.py --apply
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
    "ALTER TABLE quant.watch_digest_state ADD COLUMN IF NOT EXISTS wake_marks jsonb",
    "COMMENT ON COLUMN quant.watch_digest_state.wake_marks IS "
    "'逐账户唤醒水位 {account: ISO 时间}（2026-10-19；部分失败不再推进全局水位）'",
]

# 测试库同步（tests/_db_schema_sync.py）消费的结构化声明
COLUMNS = [
    ('watch_digest_state', 'wake_marks', 'jsonb'),
]

VERIFY = "select wake_marks from quant.watch_digest_state limit 1"


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
