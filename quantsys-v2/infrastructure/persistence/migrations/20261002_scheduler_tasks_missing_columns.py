#!/usr/bin/env python
"""quant.scheduler_tasks 补齐 ORM 模型声明的缺失列（2026-10-02 · REQ-261001145152-3982 t-2d52a7）

## 背景（实测，不是推测）

用户裁定"业务的定时任务由 **v2 自己调度**"后，实测 ② APSchedulerService **一条任务都加载不了**：

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn)
column scheduler_tasks.domain does not exist
[SQL: SELECT ... FROM quant.scheduler_tasks WHERE quant.scheduler_tasks.is_enabled = true]
```

根因：`infrastructure/persistence/orm/models/scheduler.py` 声明了 19 列，而
`quant.scheduler_tasks` 只有 16 列——**模型比库表多 3 列，且没有任何迁移添加它们**：

| 缺列 | 模型注释里的用途 | 缺失后果 |
|---|---|---|
| `domain` | 领域分组 data/signal/trading/analysis/report/monitor（2026-09-02 打标，09-12 起随接口暴露） | ORM 任何查询直接报错 |
| `task_type` | 任务类型 cron/delay/interval/once（默认 cron） | 同上 |
| `misfire_grace_time_seconds` | 错过唤醒的宽限；NULL=唤醒必补跑 | 同上（**且 CLAUDE.md 把这个特性当"现网已生效"写着**） |

即：**v2 自调度这条路自 2026-09-12 起就是坏的**——与"最后一次成功调度执行停在
2026-09-13"完全吻合。此前它一直躲在"Agent OS 调度"的名义下没被发现（Agent OS 8080
不可达 → 回退 APScheduler → 回退路径也读不了表 → 整条链路静默不跑）。

## 幂等

全部 ADD COLUMN IF NOT EXISTS；task_type 给默认值 'cron' 以免既有行违反 NOT NULL；
domain / misfire_grace_time_seconds 保持 NULL（后者 NULL 正是"必补跑"语义）。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261002_scheduler_tasks_missing_columns.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261002_scheduler_tasks_missing_columns.py --apply
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, text  # noqa: E402


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


DDL = [
    "ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS domain varchar(32)",
    "ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS task_type varchar(20) NOT NULL DEFAULT 'cron'",
    "ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS misfire_grace_time_seconds integer",
    "COMMENT ON COLUMN quant.scheduler_tasks.domain IS '领域模型分组: data/signal/trading/analysis/report/monitor（2026-09-02 打标）'",
    "COMMENT ON COLUMN quant.scheduler_tasks.task_type IS '任务类型: cron/delay/interval/once'",
    "COMMENT ON COLUMN quant.scheduler_tasks.misfire_grace_time_seconds IS '错过唤醒宽限秒数；NULL=唤醒必补跑'",
]

VERIFY = "select domain, task_type, misfire_grace_time_seconds from quant.scheduler_tasks limit 1"


def main() -> int:
    ap = argparse.ArgumentParser(description='补齐 scheduler_tasks 缺失列')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库）')
    args = ap.parse_args()

    engine = _engine(args.dsn)
    with engine.begin() as conn:
        have = {r[0] for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema='quant' and table_name='scheduler_tasks'"))}
        need = {'domain', 'task_type', 'misfire_grace_time_seconds'}
        print(f"[现状] 已有列数 {len(have)}；缺失 {sorted(need - have) or '无'}")
        if not (need - have):
            print("[跳过] 三列均已存在（幂等）")
            return 0
        if not args.apply:
            for stmt in DDL:
                print(f"[dry-run] {stmt}")
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0
        for stmt in DDL:
            conn.execute(text(stmt))
            print(f"[apply] {stmt}")
        row = conn.execute(text(VERIFY)).first()
        print(f"[verify] 抽样首行: domain={row[0]!r} task_type={row[1]!r} misfire_grace={row[2]!r}")
    print("[完成] scheduler_tasks 已与 ORM 模型一致")
    return 0


if __name__ == '__main__':
    sys.exit(main())
