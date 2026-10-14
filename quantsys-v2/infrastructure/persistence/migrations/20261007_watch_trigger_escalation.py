#!/usr/bin/env python
"""watch_triggers 加两列：升级理由码与理由（2026-10-07 · REQ-261007133807-eda6 t7 / FR-2）

## 为什么需要它（实测证据）

用户 2026-10-07 原话：「③ L1 是agent设置的，也应该设置何时调用agent的规则」——
派生出本需求的核心问题：**这条触发为什么叫了 / 没叫 agent？** 读码取证结论：

| 查了什么 | 结果 |
|---|---|
| `quant.watch_triggers` 列 | 只有 `disposition` + `disposition_reason`（**自由文本**），无理由码 |
| 本机 89 条触发分布 | `(NULL)` 82 条、`meta_review` 7 条、**`escalated` 0 条** |
| `WatchTriggerRepository.record(...)` | 参数里**不接受**任何升级理由/码 |
| `escalation_reason` 的归宿 | 只在 `escalated` 分支被拼进 `disposition_reason` 一段中文 |

即：**「为什么叫」在库里结构上缺席**——没有受控码，也没覆盖"没叫"的四种门与预算。
故本迁移加两列，使「叫没叫 + 为什么」一条 SQL 可查。

## 列设计要点

- `escalation_code`：受控枚举（15 值，见 `domain/watch/services/escalation_verdict.py` 的
  `EscalationCode`），**"没叫"也有码**（预算门 / 四道门 / 去重 / 抑噪）——只记"叫"的理由
  等于把成本控制留成黑盒。
- `escalation_reason`：人话理由；被去重/抑噪覆盖时含「原判：…」段，使"本来会叫、被压掉"可查。
- **不加 NOT NULL**：历史行如实为 NULL（= 改造前未记录），**不回填**（回填等于臆造理由）。
- **不加 CHECK 约束到码枚举**：码表在代码里演进，用 CHECK 会把"加一个码"变成"改 schema + 两库迁移"；
  受控性由 `EscalationCode.ALL` + 写库侧归一（非枚举值一律先归一为 `UNKNOWN`）保证。
- **不新增索引**：码列基数低（15 值），主查询走 `rule_id` / `triggered_at` 既有索引（YAGNI）。

## 幂等

`ADD COLUMN IF NOT EXISTS`，可重复执行；已存在的列跳过并照常 verify。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py --apply
    # 测试库镜像（本仓要求两个库都跑）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py \
        --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, text  # noqa: E402

SCHEMA = 'quant'
TABLE = 'watch_triggers'

#: 与 test_orm_db_drift 同源的 DDL 等待上限：DDL 撞上 idle in transaction 会无限等锁，
#: 宁可响亮报错也不要静默挂住（本仓既有要求，见 CLAUDE.md）。
LOCK_TIMEOUT = '30s'

#: 要加的列：列名 → 类型（列名即码表取值容器，见 escalation_verdict.EscalationCode）
COLUMNS = {
    'escalation_code': 'TEXT',
    'escalation_reason': 'TEXT',
}

DDL = [
    f"ALTER TABLE {SCHEMA}.{TABLE} ADD COLUMN IF NOT EXISTS {name} {ctype}"
    for name, ctype in COLUMNS.items()
]

COMMENTS = [
    (f"COMMENT ON COLUMN {SCHEMA}.{TABLE}.escalation_code IS "
     "'升级理由码（REQ-261007133807-eda6，受控枚举见 domain/watch/services/escalation_verdict.py）："
     "叫与没叫都在词表内（预算门/金额门/增量门/经济门/观察类/去重/抑噪）；"
     "NULL = 该列上线前的历史触发，未记录，不回填'"),
    (f"COMMENT ON COLUMN {SCHEMA}.{TABLE}.escalation_reason IS "
     "'升级理由人话文本；被去重或抑噪覆盖时含「原判：…」段，"
     "用于回答「本来会不会叫 agent」'"),
]


def _engine(dsn: str = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def _existing_columns(conn) -> set:
    rows = conn.execute(text(
        "select column_name from information_schema.columns "
        "where table_schema = :s and table_name = :t"), {'s': SCHEMA, 't': TABLE}).fetchall()
    return {r[0] for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description='watch_triggers 加升级理由两列')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库）')
    args = ap.parse_args()

    engine = _engine(args.dsn)
    with engine.begin() as conn:
        conn.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
        before = _existing_columns(conn)
        missing = [n for n in COLUMNS if n not in before]
        print(f"[现状] {SCHEMA}.{TABLE} 缺失列: {missing or '（无，已就绪）'}")

        if not missing:
            print("[跳过] 两列均已存在（幂等）；注释与数据不动")
        elif not args.apply:
            for stmt in DDL:
                print(f"[dry-run] {' '.join(stmt.split())}")
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0
        else:
            for stmt in DDL:
                conn.execute(text(stmt))
                print(f"[apply] {' '.join(stmt.split())}")
            for stmt in COMMENTS:
                conn.execute(text(stmt))
            print(f"[apply] 列注释已写入（{len(COMMENTS)} 条）")

        after = _existing_columns(conn)
        for name, ctype in COLUMNS.items():
            ok = name in after
            print(f"[verify] {name} {ctype}: {'存在' if ok else '缺失'}")
            if not ok:
                print("[失败] 列未建成")
                return 2
        nulls = conn.execute(text(
            f"select count(*) filter (where escalation_code is null), count(*) "
            f"from {SCHEMA}.{TABLE}")).first()
        print(f"[verify] escalation_code 为 NULL 的行: {nulls[0]} / 全表 {nulls[1]}"
              f"（历史行如实为 NULL，不回填）")
    print("[完成] 升级理由两列已就绪")
    return 0


if __name__ == '__main__':
    sys.exit(main())
