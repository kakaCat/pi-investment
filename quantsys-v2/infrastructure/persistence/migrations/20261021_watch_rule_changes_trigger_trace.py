#!/usr/bin/env python
"""quant.watch_rule_changes 加 trigger_id 溯源列 + 索引（2026-10-21 · 卡 rule-change-linkage）

背景：处置卡「不执行」的四类动作（调阈值 / 延期 / 停用 / 退役）落地为 `watch_rules`
的真实更新后，审计行必须能回答「这次规则变更由**哪次触发**引起」——没有 trigger_id
的变更无法复盘，也无法把「卡上说的处置」与「库里留下的变更」对上账。

为什么还要加列迁移：`20260918_watch_todo_loop.py` 建表时已含 trigger_id/todo_id，但
**存量环境存在没有 trigger_id 的旧表**（建表早于该迁移、或历史上手工补过结构）。
ORM 已声明该列（`infrastructure/persistence/orm/models/watch_todo.py` 的 WatchRuleChange）：
缺列时读会 UndefinedColumn、写会静默丢溯源——与 2026-09-11「intent/lifecycle_stage
漏映射」（migration 加了列但 ORM 没声明）是同一类事故的两面。故这里补齐为幂等加列，
并建 `(trigger_id, created_at)` 索引支撑仓储 `list_by_trigger` 的按触发反查
（联动一次触发可能先后引发多条变更，必须按时间正序取全）。

change_kind 词汇：本次联动新增 `disable`（停用）与 `postpone`（延期）两个值，
阈值/退役复用既有 `threshold`/`retire`。该列**没有 CHECK 约束**，故无需改约束；
这里只把列注释同步成全集（注释是数据字典的一部分，不能停在旧版本）。

幂等：ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS + COMMENT；
存量行 trigger_id 保持 NULL（历史自愈/人工变更没有触发来源，**绝不臆造回填**）。
默认 dry-run，`--apply` 写库；请对生产库与 `*_test` 库各执行一次
（测试库同时由 `tests/_db_schema_sync.py` 读取本模块的 COLUMNS/INDEXES 自动同步）。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261021_watch_rule_changes_trigger_trace.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261021_watch_rule_changes_trigger_trace.py --apply
"""
import argparse
import os

from sqlalchemy import create_engine, text

TABLE = 'quant.watch_rule_changes'

# ── 既有表加列（additive；tests/_db_schema_sync.py 消费同一声明）────────────
COLUMNS = [
    ('watch_rule_changes', 'trigger_id', 'INTEGER'),
]

#: 按触发反查（list_by_trigger）的支撑索引；created_at 同列保证同触发多条变更有序
INDEXES = [
    ('idx_watch_rule_changes_trigger',
     'quant.watch_rule_changes (trigger_id, created_at)'),
]

#: 幂等杂项 DDL（列/词汇注释；重复执行零副作用）
IDEMPOTENT_DDL = [
    "COMMENT ON COLUMN quant.watch_rule_changes.trigger_id IS "
    "'溯源触发 id（watch_triggers.id）：处置卡联动的变更必填；自愈/人工变更可为空'",
    "COMMENT ON COLUMN quant.watch_rule_changes.change_kind IS "
    "'cooldown/threshold/split/merge/retire/suppress/unsuppress/postpone/disable"
    "（postpone/disable 为 2026-10-21 处置卡联动新增）'",
]

#: 完整升级步骤（dry-run 逐条打印；--apply 逐条执行）
DDL = [
    "ALTER TABLE quant.watch_rule_changes ADD COLUMN IF NOT EXISTS trigger_id INTEGER",
    "CREATE INDEX IF NOT EXISTS idx_watch_rule_changes_trigger "
    "ON quant.watch_rule_changes (trigger_id, created_at)",
] + IDEMPOTENT_DDL

#: 验收探针：迁移后该列必须可读（缺列会在此处报错，而不是等业务查询才炸）
VERIFY = "SELECT trigger_id FROM quant.watch_rule_changes LIMIT 1"


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    eng = _engine()
    with eng.begin() as conn:
        for ddl in DDL:
            if args.apply:
                conn.execute(text(ddl))
            print(('APPLY ' if args.apply else 'DRY   ') + ddl[:100].replace('\n', ' '))
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY)).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
