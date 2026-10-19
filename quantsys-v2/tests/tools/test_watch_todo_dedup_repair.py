"""watch_todo_dedup_repair.plan_repairs（纯函数）"""
from tools.watch_todo_dedup_repair import plan_repairs


def _rows(*spec):
    return [{'rule_id': rid, 'id': tid, 'level': lv, 'created_at': d}
            for rid, tid, lv, d in spec]


def test_keeps_newest_per_rule():
    rows = _rows((57, 40, 'P1', '2026-09-24'), (57, 47, 'P1', '2026-09-25'),
                 (250, 72, 'P2', '2026-10-16'), (250, 90, 'P1', '2026-10-16'))
    plans = plan_repairs(rows)
    assert plans == [
        {'rule_id': 57, 'keep': 47, 'expire': [40]},
        {'rule_id': 250, 'keep': 90, 'expire': [72]},
    ]


def test_single_todo_no_plan():
    rows = _rows((1, 10, 'P2', '2026-10-16'), (2, 11, 'P1', '2026-10-16'))
    assert plan_repairs(rows) == []


def test_three_keep_last_two_expire():
    rows = _rows((9, 1, 'P1', 'a'), (9, 2, 'P1', 'b'), (9, 3, 'P2', 'c'))
    assert plan_repairs(rows) == [{'rule_id': 9, 'keep': 3, 'expire': [1, 2]}]
