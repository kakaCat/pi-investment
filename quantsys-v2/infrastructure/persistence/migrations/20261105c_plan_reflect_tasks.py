#!/usr/bin/env python
"""注册计划反思调度任务（REQ-261021222905-6dff t11）

向 quant.scheduler_tasks 插入两行（幂等：同名存在则跳过）：
  · plan_reflect_daily   工作日 15:35（盘后反思）
  · plan_reflect_weekly  周六 10:00（周度深反思）
命令与 PlanReflectionJob.name 一致；handler 由 job_registry 提供（main.py 注册）。
"""
import argparse
import sys

from sqlalchemy import text

from qs_kernel.infrastructure.persistence.database.engine import get_engine

ROWS = [
    ('plan_reflect_daily', '交易计划反思：四输入材料包 + 唤醒 agent（盘后）',
     '35 15 * * 1-5', 'plan_reflect_daily'),
    ('plan_reflect_weekly', '交易计划周度深反思（跨计划）',
     '0 10 * * 6', 'plan_reflect_weekly'),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dsn', default=None)
    args = ap.parse_args()
    eng = get_engine()
    if args.dsn:
        from sqlalchemy import create_engine
        eng = create_engine(args.dsn)
    with eng.begin() as conn:
        for name, desc, cron, command in ROWS:
            exists = conn.execute(text(
                "SELECT 1 FROM quant.scheduler_tasks WHERE name=:n"), {'n': name}).scalar()
            print(('DRY   ' if not args.apply else 'APPLY ') +
                  ('exists' if exists else 'would-insert') + ' ' + name)
            if args.apply and not exists:
                conn.execute(text(
                    "INSERT INTO quant.scheduler_tasks "
                    "(name, description, cron_expression, command, params, is_enabled) "
                    "VALUES (:n, :d, :c, :cmd, '{}'::jsonb, true)"),
                    {'n': name, 'd': desc, 'c': cron, 'cmd': command})
    print('DRY-RUN done' if not args.apply else 'APPLY done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
