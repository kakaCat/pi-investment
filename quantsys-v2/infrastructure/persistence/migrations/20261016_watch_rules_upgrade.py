#!/usr/bin/env python
"""quant.watch_rules 决策化改造迁移（2026-10-16 · REQ-261016155500-4f2a）

## 做什么

1. **加两列**（幂等，ADD COLUMN IF NOT EXISTS）：
   - `action_params JSONB` —— 结构化操作指引（action/reference_price/position_pct|quantity/
     invalidation/observation_criterion），消息「建议动作」块的权威数据源；
   - `ops_notes JSONB` —— 机器注记数组 [{at, by, text}]。
2. **context 注记剥离**：把机器写入的注记行（健康检查巡检 / 事实校正 / 误停恢复，
   形如 `[2026年10月12日 规则健康检查误停·已恢复 by investor/w-xxx] ...`）从
   `context` 移入 `ops_notes`，消息与摘要只引用剥离后的真预案。

## 幂等

- DDL 全部 IF NOT EXISTS；
- 剥离按行匹配注记正则，已剥离的行不再匹配 → 重跑零变更。

## 安全

- 执行前已由人工 pg_dump 单表备份（backups/watch_rules_20261016_pre_upgrade.dump）；
- 默认 dry-run（只打印将发生的变更），`--apply` 才写库。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261016_watch_rules_upgrade.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261016_watch_rules_upgrade.py --apply
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


DDL = [
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS action_params JSONB",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS ops_notes JSONB",
    "COMMENT ON COLUMN quant.watch_rules.action_params IS "
    "'结构化操作指引（REQ-261016155500-4f2a）: action/reference_price/position_pct|quantity/invalidation/observation_criterion'",
    "COMMENT ON COLUMN quant.watch_rules.ops_notes IS "
    "'机器注记数组 [{at, by, text}]（REQ-261016155500-4f2a）：从 context 剥离，不进用户视野'",
]

#: 机器注记行：以 [ 开头，含健康检查/误停/事实校正 或 "by 操作者/会话" 落款。
#: 与真实预案的区分依据：真实预案是交易语义（价位/仓位/条件），不含 "by xxx/yyy" 机器落款。
NOTE_LINE_RE = re.compile(
    r'^\[[^\]\n]*(健康检查|误停|事实校正|by\s+[A-Za-z0-9_.-]+/\S+)[^\]\n]*\]'
)

MIGRATION_BY = 'migration/20261016_watch_rules_upgrade'

VERIFY = "select action_params, ops_notes from quant.watch_rules limit 1"


def strip_notes(context: str):
    """(剥离后正文, 注记行列表)。无注记返回 (原文, [])。"""
    if not context:
        return context, []
    kept, notes = [], []
    for line in context.splitlines():
        if NOTE_LINE_RE.match(line.strip()):
            notes.append(line.strip())
        else:
            kept.append(line)
    # 收掉剥离后产生的连续空行
    text = '\n'.join(kept)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='实际写库（默认 dry-run）')
    args = parser.parse_args()

    eng = _engine()
    now_iso = datetime.now(timezone.utc).isoformat()

    with eng.begin() as conn:
        for ddl in DDL:
            if args.apply:
                conn.execute(text(ddl))
            print(('APPLY ' if args.apply else 'DRY   ') + ddl.split(' COMMENT')[0][:100])

        # dry-run 时新列尚不存在，只取 context；apply 时列已建，可顺带读 ops_notes 做追加
        select_cols = 'id, context, ops_notes' if args.apply else 'id, context, NULL'
        rows = conn.execute(text(
            "select %s from quant.watch_rules "
            "where context is not null and context <> ''" % select_cols
        )).fetchall()

        changed = 0
        for rule_id, context, ops_notes in rows:
            stripped, notes = strip_notes(context)
            if not notes:
                continue
            changed += 1
            new_notes = list(ops_notes or [])
            new_notes.extend({'at': now_iso, 'by': MIGRATION_BY, 'text': n} for n in notes)
            print('--- rule #%s: 剥离 %d 行注记（正文 %d → %d 字符）'
                  % (rule_id, len(notes), len(context), len(stripped)))
            for n in notes:
                print('    注记: %s' % n[:120])
            if args.apply:
                conn.execute(
                    text("update quant.watch_rules set context = :ctx, ops_notes = :notes "
                         "where id = :rid"),
                    {'ctx': stripped or None, 'notes': json.dumps(new_notes,
                                                                  ensure_ascii=False),
                     'rid': rule_id},
                )

        print('== %s: 共 %d 条规则需剥离注记 ==' % ('APPLIED' if args.apply else 'DRY-RUN', changed))

    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY)).fetchone()
            print('VERIFY OK: 两列可读')
    else:
        print('VERIFY SKIP: dry-run 未建列（--apply 后自动校验）')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
