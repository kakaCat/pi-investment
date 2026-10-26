#!/usr/bin/env python
"""quant.watch_rules 加 rule_state 三分支 + confirm_count + invalid 留痕（2026-10-22）

背景：规则生命周期从「一个 enabled 布尔」升级为显式三态（2026-10-22 用户裁定）：
  · active    在盯盘里 → 参与判定
  · invalid   在失效里 → 待 agent 裁决（改规则 / 退役），不静默
  · archived  既不在盯盘也不在失效 → 过滤丢弃，不占管理成本

同时加 confirm_count（确认数直通计数）：同一规则同一条件的确认类触发累计 ≥10 次
后直通盯盘群（不走 agent、不进聚合缓冲）。exit_stop 无条件直通保留（资损底线，
与确认数无关）。

字段：
  rule_state                  active/invalid/archived，默认 active，CHECK 约束
  invalid_reason              失效原因文本（价格偏离 X%/已过期/长期未触发）
  invalid_at                  标失效时间
  confirm_count               确认触发累计（跨日由引擎重置，见 watch_runtime_state.emit_count_date）
  invalidation_threshold_pct  失效偏离阈值（agent 按规则设定，正数）。**必填**：像止盈价/
                              止损价一样是规则的具体参数，每条规则必须有明确数值
                              （2026-10-22 用户裁定——不是程序常量，是 agent 的数据）。
                              存量 NULL 回填全局默认 20.00，agent 可按规则逐个覆盖。

幂等：ADD COLUMN IF NOT EXISTS + CHECK（先加列后加约束，约束名若已存在跳过）+
列注释。存量迁移：enabled=false 且（expires_at 已过期 或 带 invalid 语义）→ invalid，
其余 enabled=false → archived；enabled=true 保持 active。

默认 dry-run，`--apply` 写库；请对生产库与 `*_test` 库各执行一次。

用法：
    PYTHONPATH=. python infrastructure/persistence/migrations/20261022_watch_rules_state.py
    PYTHONPATH=. python infrastructure/persistence/migrations/20261022_watch_rules_state.py --apply
"""
import argparse
import os

from sqlalchemy import create_engine, text

TABLE = 'quant.watch_rules'

COLUMNS = [
    ('watch_rules', 'rule_state', 'VARCHAR(16)'),
    ('watch_rules', 'invalid_reason', 'TEXT'),
    ('watch_rules', 'invalid_at', 'TIMESTAMP WITHOUT TIME ZONE'),
    ('watch_rules', 'confirm_count', 'INTEGER'),
    ('watch_rules', 'invalidation_threshold_pct', 'NUMERIC(6,2)'),
    ('watch_rules', 'invalid_escalated_at', 'TIMESTAMP WITHOUT TIME ZONE'),
]

DDL = [
    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS rule_state VARCHAR(16) NOT NULL DEFAULT 'active'",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS invalid_reason TEXT",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMP WITHOUT TIME ZONE",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS confirm_count INTEGER NOT NULL DEFAULT 0",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS invalidation_threshold_pct NUMERIC(6,2)",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS invalid_escalated_at TIMESTAMP WITHOUT TIME ZONE",

    # CHECK 约束：IF NOT EXISTS 不支持约束名查重，用 DO 块幂等包裹
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'watch_rules_rule_state_chk'
        ) THEN
            ALTER TABLE quant.watch_rules
            ADD CONSTRAINT watch_rules_rule_state_chk
            CHECK (rule_state IN ('active', 'invalid', 'archived'));
        END IF;
    END $$;
    """,

    "COMMENT ON COLUMN quant.watch_rules.rule_state IS "
    "'生命周期三态：active=在盯盘/invalid=失效待裁决/archived=过滤丢弃（2026-10-22）'",

    "COMMENT ON COLUMN quant.watch_rules.invalid_reason IS "
    "'失效原因（价格偏离%/已过期/长期未触发），投递 agent 裁决用'",

    "COMMENT ON COLUMN quant.watch_rules.confirm_count IS "
    "'确认触发累计：≥10 次直通盯盘群（exit_stop 无条件直通，与此无关）'",

    "COMMENT ON COLUMN quant.watch_rules.invalidation_threshold_pct IS "
    "'失效偏离阈值%（agent 按规则设定，正数）：|现价-触发价|/触发价 超此值即标 invalid。"
    "必填：像止盈价/止损价一样是规则的具体参数（2026-10-22 用户裁定）；"
    "存量回填默认 20.00，agent 可按规则逐个覆盖'",
]

# 存量分类：enabled=false 且有失效语义的 → invalid，其余 → archived
BACKFILL = [
    # 已过期 → invalid
    """
    UPDATE quant.watch_rules
    SET rule_state = 'invalid',
        invalid_reason = '存量迁移：已过有效期',
        invalid_at = COALESCE(expires_at, updated_at)
    WHERE NOT enabled
      AND rule_state = 'active'
      AND expires_at IS NOT NULL
      AND expires_at < now();
    """,
    # 其余 enabled=false → archived
    """
    UPDATE quant.watch_rules
    SET rule_state = 'archived'
    WHERE NOT enabled AND rule_state = 'active';
    """,
    # 失效阈值必填（2026-10-22 用户裁定）：像止盈价/止损价一样是规则的具体参数，
    # 每条规则必须有明确数值。存量 NULL 回填全局默认 20.00（与 watch_rule_health
    # 的 STALE 阈值一致，行为连续），agent 可按规则逐个覆盖。
    """
    UPDATE quant.watch_rules
    SET invalidation_threshold_pct = 20.00
    WHERE invalidation_threshold_pct IS NULL;
    """,
]

VERIFY = "SELECT rule_state, confirm_count FROM quant.watch_rules LIMIT 1"


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
        for stmt in BACKFILL:
            if args.apply:
                result = conn.execute(text(stmt))
                print(f'  backfill rows: {result.rowcount}')
            print(('APPLY ' if args.apply else 'DRY   ') + stmt[:100].replace('\n', ' '))
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY)).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
