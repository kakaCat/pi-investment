"""盯盘旧账收敛测试（REQ-c9f899 t11）

验收口径（可证伪）：
  · dry-run 不写任何东西；
  · apply 后**未收敛触发数 = 0**；
  · 连续执行两次，第二次 changed = 0（幂等）；
  · 悬空 rule_id / 策略账户 → 收敛为 expired 并写明理由，不凭空建待办。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from scripts.migrate_watch_backlog import converge

NOW = datetime(2026, 9, 18, 10, 0, 0)
# symbol 列是 varchar(20)，标记必须短（踩过一次 StringDataRightTruncation）
MARK = 'T11FIX'

# 本模块会写测试库的**共享**盯盘数据（converge 按设计扫描全表未闭环触发），且依赖
# t1/t3 表结构 —— 因此：串行标记 + session 级结构固化 + 协作进程串行锁
# （REQ-c9f899 返工 D，见 tests/conftest.py 与 tests/_db_schema_sync.py）。
pytestmark = [
    pytest.mark.serial,
    pytest.mark.usefixtures("db_schema_synced", "watch_db_advisory_lock"),
]


@pytest.fixture()
def seeded():
    """种一批未闭环触发 + 一条正常规则 + 一条策略账户规则；用完清理。"""
    from infrastructure.persistence.orm import get_session
    from tests._db_schema_sync import sync_test_schema

    # 自洽：不再依赖别的测试恰好建过表 —— 由 session 级结构同步把 t1/t3 的表与列
    # 幂等补齐（成功后进程内缓存，重复调用零开销）。缺表缺列会在这里响亮抛出，
    # 而不是让用例在 INSERT 时以一句含糊的 UndefinedTable 报错。
    sync_test_schema()

    # 清掉可能残留的失败事务（否则后续语句一律 InFailedSqlTransaction）
    session = get_session()
    session.rollback()

    session.execute(text("DELETE FROM quant.watch_todos WHERE symbol LIKE :m"), {'m': MARK + '%'})
    session.execute(text("DELETE FROM quant.watch_triggers WHERE symbol LIKE :m"), {'m': MARK + '%'})
    session.execute(text("DELETE FROM quant.watch_rules WHERE symbol LIKE :m"), {'m': MARK + '%'})

    rid_ok = session.execute(text(
        "INSERT INTO quant.watch_rules (symbol, enabled, conditions, linked_account, intent) "
        "VALUES (:s, true, '[]'::jsonb, 'agent_brain', 'entry') RETURNING id"),
        {'s': MARK + '_ok'}).scalar()
    rid_strategy = session.execute(text(
        "INSERT INTO quant.watch_rules (symbol, enabled, conditions, linked_account, intent) "
        "VALUES (:s, true, '[]'::jsonb, 'v13_simulation', 'entry') RETURNING id"),
        {'s': MARK + '_stg'}).scalar()

    rows = [
        (rid_ok, MARK + '_ok', 'escalated', None),
        (rid_ok, MARK + '_ok2', 'pending', None),
        (rid_ok, MARK + '_ok3', 'meta_review', {'type': 'rule_overlap', 'params': {}}),
        (rid_strategy, MARK + '_stg', 'escalated', None),
        (None, MARK + '_dang', 'pending', None),
    ]
    ids = []
    for rid, sym, disp, cond in rows:
        tid = session.execute(text(
            "INSERT INTO quant.watch_triggers (rule_id, symbol, condition, trigger_price, "
            "notified, disposition, triggered_at) VALUES (:r, :s, CAST(:c AS jsonb), 10, false, "
            ":d, now()) RETURNING id"),
            {'r': rid, 's': sym, 'c': __import__('json').dumps(cond or {'type': 'price_break'}),
             'd': disp}).scalar()
        ids.append(tid)
    session.commit()
    yield {'session': session, 'trigger_ids': ids}

    session.rollback()
    session.execute(text("DELETE FROM quant.watch_todos WHERE symbol LIKE :m"), {'m': MARK + '%'})
    session.execute(text("DELETE FROM quant.watch_triggers WHERE id = ANY(:i)"), {'i': ids})
    session.execute(text("DELETE FROM quant.watch_rules WHERE symbol LIKE :m"), {'m': MARK + '%'})
    session.commit()


def _pending_of(session, ids):
    return int(session.execute(text(
        "SELECT count(*) FROM quant.watch_triggers WHERE id = ANY(:i) "
        "AND disposition = ANY(:d)"), {'i': ids, 'd': ['escalated', 'pending', 'meta_review']}).scalar() or 0)


def test_dry_run_changes_nothing(seeded):
    s = seeded['session']
    before = _pending_of(s, seeded['trigger_ids'])
    stats = converge(s, apply=False, now=NOW)
    assert stats['changed'] > 0            # 演练识别出可收敛项
    assert stats['todos_created'] > 0
    assert _pending_of(s, seeded['trigger_ids']) == before   # 但库里没变


def test_apply_converges_to_zero_then_idempotent(seeded):
    s = seeded['session']
    first = converge(s, apply=True, now=NOW)
    # 验收口径：orphaned（未闭环且无待办载体）= 0。注意 unresolved_total 在待办被
    # SLA/agent 收敛前本就 > 0——把 disposition 直接改成终态才是伪造"已处置"。
    assert first['orphaned_scoped'] == 0, first
    assert first['changed'] > 0
    assert first['errors'] == 0

    second = converge(s, apply=True, now=NOW)
    assert second['changed'] == 0, second          # 幂等：二次运行无变更
    assert second['orphaned_scoped'] == 0


def test_strategy_account_and_dangling_go_expired(seeded):
    s = seeded['session']
    converge(s, apply=True, now=NOW)
    rows = s.execute(text(
        "SELECT disposition, disposition_reason FROM quant.watch_triggers "
        "WHERE symbol = ANY(:s)"), {'s': [MARK + '_stg', MARK + '_dang']}).fetchall()
    assert len(rows) == 2
    for disp, reason in rows:
        assert disp == 'expired'
        assert reason and len(reason) > 5          # 必须写明理由，不许空话


def test_rule_overlap_becomes_rule_change_todo(seeded):
    s = seeded['session']
    converge(s, apply=True, now=NOW)
    row = s.execute(text(
        "SELECT t.action_kind, t.level, t.flow_state FROM quant.watch_todos t "
        "JOIN quant.watch_triggers g ON g.id = t.trigger_id "
        "WHERE g.symbol = :s"), {'s': MARK + '_ok3'}).fetchone()
    assert row is not None
    assert row[0] == 'rule_change' and row[1] == 'P1' and row[2] == 'L3'
