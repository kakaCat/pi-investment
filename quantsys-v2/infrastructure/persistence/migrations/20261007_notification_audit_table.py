#!/usr/bin/env python
"""建立 quant.notification_audit：**外发审计**（2026-10-07 · REQ-261007101318-c392 FR-3）

## 为什么需要它（实测证据，不是推测）

用户 2026-10-07 收到飞书卡「盯盘触发 - 688525 / 现价 192.35 ≤ 阈值 218.24（下破）」，
要回答"谁发的"，本机把所有能查的地方都查了一遍：

| 查了什么 | 结果 |
|---|---|
| `quant.watch_rules` | 无 688525 规则 |
| `quant.watch_triggers` | 无 688525 记录 |
| v2 保留日志（10-01 21:48 → 10-07 10:07） | **77 条外发全是 `system_alert`，零条 watch** |
| 整盘文件扫描 `218.24` | 只命中该窗口的会话记录 |
| `NotificationService(repository=None)` | **外发零持久化**——`NotificationRepository` 全仓只有一处类型注解 |

再叠加两条结构性事实：v2 与 agent-ts 的 `FEISHU_WEBHOOK` **完全相同**（同一机器人/群），
且盯盘卡**不带署名** ⇒ **卡面与日志都无法回答"谁发的"**。
用户并明确指出「执行可能是另外一个机器执行的」——所以来源必须**写进卡面并落库**。

## 表设计要点

- **一通知一行**（`notification_id` 唯一）+ `ON CONFLICT DO UPDATE`：
  `NotificationService.send` 会在 mark_sending / mark_sent / mark_failed 处**多次** save，
  追加式会写出 2~3 行噪声；upsert 后一行即完整的生命周期（末态 = 最终结果）。
- `content_digest`（sha1）+ `content_excerpt`（前 500 字）：既能核对"发的是不是这张卡"，
  又不把长正文整存进审计表。
- `sender_id`：`v2-watch@<host>#<pid>`（见 `application/notification/sender_identity.py`）——
  跨机靠 host 段、跨进程靠 pid 段。
- 不做外键、不删改历史：审计表是"发生过什么"的事实，不参与业务约束。

## 幂等

`CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`，可重复执行。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261007_notification_audit_table.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261007_notification_audit_table.py --apply
    # 测试库镜像（本仓要求两个库都跑）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261007_notification_audit_table.py \
        --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, text  # noqa: E402

TABLE = 'notification_audit'
SCHEMA = 'quant'

#: 与 test_orm_db_drift 同源的 DDL 等待上限：DDL 撞上 idle in transaction 会无限等锁，
#: 宁可响亮报错也不要静默挂住（本仓既有要求，见 CLAUDE.md）。
LOCK_TIMEOUT = '30s'

DDL = [
    f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE} (
        id BIGSERIAL PRIMARY KEY,
        notification_id VARCHAR(64) NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        notification_type VARCHAR(32) NOT NULL,
        priority VARCHAR(16),
        title VARCHAR(255),
        content_digest VARCHAR(64),
        content_excerpt TEXT,
        status VARCHAR(20) NOT NULL,
        error TEXT,
        delivery_channel VARCHAR(32),
        delivered BOOLEAN,
        sender_id VARCHAR(128),
        payload_meta JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_notification_audit_notification_id UNIQUE (notification_id)
    )""",
    f"""CREATE INDEX IF NOT EXISTS idx_notification_audit_occurred
        ON {SCHEMA}.{TABLE} (occurred_at DESC)""",
    f"""CREATE INDEX IF NOT EXISTS idx_notification_audit_title
        ON {SCHEMA}.{TABLE} (title)""",
    f"""CREATE INDEX IF NOT EXISTS idx_notification_audit_sender
        ON {SCHEMA}.{TABLE} (sender_id, occurred_at DESC)""",
    f"""COMMENT ON TABLE {SCHEMA}.{TABLE} IS
        '外发审计（REQ-261007101318-c392 FR-3）：一通知一行，随生命周期 upsert；
         用于回答「谁在几点、为哪条规则、发了什么标题」——v2 与 agent 侧共用同一飞书机器人，
         不落审计则事后不可归因'""",
    f"""COMMENT ON COLUMN {SCHEMA}.{TABLE}.sender_id IS
        '发送方标识 v2-watch@<host>#<pid>（跨机靠 host、跨进程靠 pid）'""",
]

VERIFY = (f"select count(*) from {SCHEMA}.{TABLE}")


def _engine(dsn: str = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def main() -> int:
    ap = argparse.ArgumentParser(description='建立 quant.notification_audit（外发审计）')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库）')
    args = ap.parse_args()

    engine = _engine(args.dsn)
    with engine.begin() as conn:
        conn.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
        exists = conn.execute(text(
            "select 1 from information_schema.tables "
            "where table_schema = :s and table_name = :t"), {'s': SCHEMA, 't': TABLE}).first()
        print(f"[现状] {SCHEMA}.{TABLE} {'已存在' if exists else '不存在'}")
        if exists:
            print("[跳过] 表已存在（幂等）；索引/注释不重复创建")
            count = conn.execute(text(VERIFY)).scalar()
            print(f"[verify] 现有审计行数: {count}")
            return 0
        if not args.apply:
            for stmt in DDL:
                print(f"[dry-run] {' '.join(stmt.split())[:120]}…")
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0
        for stmt in DDL:
            conn.execute(text(stmt))
            print(f"[apply] {' '.join(stmt.split())[:100]}…")
        count = conn.execute(text(VERIFY)).scalar()
        print(f"[verify] 建表完成，当前审计行数: {count}（新表应为 0）")
    print("[完成] 外发审计表已就绪")
    return 0


if __name__ == '__main__':
    sys.exit(main())
