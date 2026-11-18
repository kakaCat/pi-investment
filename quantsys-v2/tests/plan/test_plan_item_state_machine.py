"""账户计划项状态机（REQ-261026140857-c192）"""

from qs_plan.domain.plan import (
    ITEM_STATUSES,
    LEGAL_ITEM_TRANSITIONS,
    STATUS_CANCELLED,
    STATUS_ENTERING,
    STATUS_EXITED,
    STATUS_HOLDING,
    STATUS_PLANNED,
    STATUS_READY,
    STATUS_REDUCING,
    evaluate_item_transition,
    initial_item_state,
    transition_for_fill,
)


def _assert_legal(path):
    for left, right in zip(path, path[1:]):
        ok, reason = evaluate_item_transition(left, right)
        assert ok, (left, right, reason)


def test_legal_main_path_and_cancel_branches():
    _assert_legal(
        [
            STATUS_PLANNED,
            STATUS_READY,
            STATUS_ENTERING,
            STATUS_HOLDING,
            STATUS_REDUCING,
            STATUS_EXITED,
        ]
    )
    _assert_legal([STATUS_PLANNED, STATUS_CANCELLED])
    _assert_legal([STATUS_READY, STATUS_HOLDING])
    _assert_legal([STATUS_READY, STATUS_CANCELLED])
    _assert_legal([STATUS_ENTERING, STATUS_CANCELLED])
    _assert_legal([STATUS_HOLDING, STATUS_CANCELLED])
    _assert_legal([STATUS_REDUCING, STATUS_CANCELLED])


def test_terminal_states_have_no_outgoing_edges():
    for terminal in (STATUS_EXITED, STATUS_CANCELLED):
        assert LEGAL_ITEM_TRANSITIONS[terminal] == set()


def test_illegal_and_unknown_transitions_have_readable_reasons():
    cases = [
        (STATUS_PLANNED, STATUS_HOLDING),
        (STATUS_PLANNED, STATUS_PLANNED),
        (STATUS_REDUCING, STATUS_HOLDING),
        (STATUS_EXITED, STATUS_PLANNED),
    ]
    for left, right in cases:
        ok, reason = evaluate_item_transition(left, right)
        assert not ok
        assert reason
    assert not evaluate_item_transition("unknown", STATUS_READY)[0]
    assert not evaluate_item_transition(STATUS_READY, "unknown")[0]


def test_status_set_matches_schema_check_constraint():
    assert ITEM_STATUSES == (
        "planned",
        "ready",
        "entering",
        "holding",
        "reducing",
        "exited",
        "cancelled",
    )


def test_initial_state_from_action_position_and_entry_readiness():
    assert initial_item_state("buy", 0, entry_ready=True) == STATUS_READY
    assert initial_item_state("buy", 0, entry_ready=False) == STATUS_PLANNED
    assert initial_item_state("sell", 100, entry_ready=False) == STATUS_REDUCING
    assert initial_item_state("sell", 0, entry_ready=False) == STATUS_PLANNED
    assert initial_item_state("hold", 100, entry_ready=False) == STATUS_HOLDING
    assert initial_item_state("hold", 0, entry_ready=False) == STATUS_PLANNED
    assert initial_item_state("avoid", 0, entry_ready=False) == STATUS_PLANNED


def test_fill_transition_does_not_close_other_items_context():
    assert transition_for_fill("buy", 100) == STATUS_HOLDING
    assert transition_for_fill("buy", 0) == STATUS_EXITED
    assert transition_for_fill("sell", 70) == STATUS_REDUCING
    assert transition_for_fill("sell", 0) == STATUS_EXITED
    assert transition_for_fill("hold", 0) == STATUS_EXITED
