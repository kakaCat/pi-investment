"""反复触发判定（noise_policy）单测 —— REQ-c9f899 R6 / t8

覆盖 test-cases.md §1「自愈阈值」的真值表：单日 8 次命中、7 次不命中；连续 3 日且日均 4
命中、2 日不命中、日均 3.9 不命中。并验证：
  · 阈值是**模块常量且可被参数覆写**（R6：默认值可证伪、可调）；
  · 判定函数**不读时钟/不读库**（时间由调用方注入，purity 断言见末尾）；
  · REPAIR_ACTIONS 枚举与各自适用场景齐备（data-model.md §4 / architecture §5）。
"""
import inspect
from datetime import date, datetime, timedelta, timezone

import pytest

from domain.watch.services import noise_policy

TODAY = date(2026, 9, 18)
NOW = datetime(2026, 9, 18, 10, 0, 0)


# ── 阈值常量与覆写能力 ────────────────────────────────────────

def test_default_thresholds_are_documented_module_constants():
    """默认阈值 = design/test-cases.md 定稿值（单日 8 次 / 连续 3 日日均 4 次）"""
    assert noise_policy.DEFAULT_MAX_TRIGGERS_PER_DAY == 8
    assert noise_policy.DEFAULT_MIN_CONSECUTIVE_DAYS == 3
    assert noise_policy.DEFAULT_MIN_AVG_PER_DAY == 4.0
    # 阈值必须能被参数覆写（keyword-only），否则"可调"只是口号
    params = inspect.signature(noise_policy.should_suppress).parameters
    for name in ("max_triggers_per_day", "min_consecutive_days", "min_avg_per_day"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert params[name].default == getattr(
            noise_policy, "DEFAULT_" + name.upper())


# ── 单日阈值边界：7 / 8 ───────────────────────────────────────

def test_single_day_7_not_suppressed():
    assert noise_policy.should_suppress(7, 0, 0.0) is False


def test_single_day_8_suppressed():
    assert noise_policy.should_suppress(8, 0, 0.0) is True


def test_single_day_hits_without_consecutive_days():
    """单日爆量即抑噪：不看连续天数（一天 23 次同样要治）"""
    assert noise_policy.should_suppress(23, 1, 23.0) is True


def test_single_day_just_below_threshold_not_suppressed():
    assert noise_policy.should_suppress(7, 99, 0.0) is False   # 单日不够且连续条件未给


# ── 连续阈值边界：2 日 / 3 日 × 日均 ──────────────────────────

def test_consecutive_3_days_avg_4_suppressed():
    assert noise_policy.should_suppress(4, 3, 4.0) is True


def test_consecutive_2_days_not_suppressed():
    assert noise_policy.should_suppress(4, 2, 4.0) is False


def test_consecutive_3_days_low_avg_not_suppressed():
    assert noise_policy.should_suppress(3, 3, 3.0) is False


def test_avg_boundary_3_9_vs_4_0():
    """日均边界：3.9 不命中、4.0 命中（连续 3 日）"""
    assert noise_policy.should_suppress(4, 3, 3.9) is False
    assert noise_policy.should_suppress(4, 3, 4.0) is True


def test_thresholds_overridable_by_parameters():
    """参数覆写立即生效：把单日阈值降到 3，则 3 次即命中；连续门槛改 2 日同理"""
    assert noise_policy.should_suppress(3, 0, 0.0, max_triggers_per_day=3) is True
    assert noise_policy.should_suppress(2, 2, 5.0, min_consecutive_days=2) is True
    assert noise_policy.should_suppress(2, 2, 5.0, min_avg_per_day=6.0) is False


def test_missing_and_invalid_values_treated_as_zero():
    """缺数据 ≠ 触发：None/非法值一律按 0，绝不臆造"""
    assert noise_policy.should_suppress(None, None, None) is False
    assert noise_policy.should_suppress("abc", "", "x") is False


def test_should_suppress_is_deterministic_and_pure():
    """同一输入两次调用结果一致（无隐藏状态）"""
    args = (8, 3, 4.0)
    assert noise_policy.should_suppress(*args) == noise_policy.should_suppress(*args)


# ── 修复动作枚举 ──────────────────────────────────────────────

def test_repair_actions_enum_matches_design():
    assert noise_policy.REPAIR_ACTIONS == (
        "cooldown", "threshold", "split", "merge", "retire")
    assert noise_policy.CHANGE_KINDS == noise_policy.REPAIR_ACTIONS + (
        "suppress", "unsuppress")


def test_every_repair_action_has_a_scenario():
    """每个动作都有适用场景说明（R6：动作枚举不能是光秃秃的字符串）"""
    for action in noise_policy.REPAIR_ACTIONS:
        scenario = noise_policy.REPAIR_ACTION_SCENARIOS.get(action)
        assert scenario and len(scenario) >= 10, action
    assert set(noise_policy.REPAIR_ACTION_SCENARIOS) == set(noise_policy.REPAIR_ACTIONS)


def test_action_predicates():
    assert noise_policy.is_repair_action(" retire ") is True
    assert noise_policy.is_repair_action("suppress") is False
    assert noise_policy.is_change_kind("suppress") is True
    assert noise_policy.is_change_kind("explode") is False
    assert noise_policy.is_change_kind(None) is False


# ── 抑噪态判定（触发摄入路径的判据：抑噪期内不建 todo）──────────

def test_is_suppressed_requires_suppressed_state():
    assert noise_policy.is_suppressed(None, None, NOW) is False
    assert noise_policy.is_suppressed("normal", NOW + timedelta(hours=1), NOW) is False


def test_is_suppressed_within_window():
    assert noise_policy.is_suppressed("suppressed", NOW + timedelta(hours=1), NOW) is True
    assert noise_policy.is_suppressed(" SUPPRESSED ", NOW + timedelta(hours=1), NOW) is True


def test_is_suppressed_expires_and_recovers():
    """到期即恢复原级别；到期时刻 == now 视为已恢复"""
    assert noise_policy.is_suppressed("suppressed", NOW - timedelta(seconds=1), NOW) is False
    assert noise_policy.is_suppressed("suppressed", NOW, NOW) is False


def test_is_suppressed_without_deadline_is_conservative():
    """抑噪态但无到期时刻 → 视为仍抑噪（保守），不误放行"""
    assert noise_policy.is_suppressed("suppressed", None, NOW) is True


def test_is_suppressed_tolerates_mixed_tzinfo():
    """aware/朴素混用不抛 TypeError（守卫抛错会阻断触发摄入，比误判更糟）"""
    aware = NOW.replace(tzinfo=timezone.utc)
    assert noise_policy.is_suppressed("suppressed", aware + timedelta(hours=1), NOW) is True


# ── 时间注入（纯函数不得读时钟）──────────────────────────────

def test_suppress_until_uses_injected_now():
    assert noise_policy.suppress_until(NOW, hours=2) == NOW + timedelta(hours=2)
    assert noise_policy.suppress_until(NOW) == NOW + timedelta(
        hours=noise_policy.DEFAULT_SUPPRESS_HOURS)
    # now 是必填参数（没有默认值 = 逼调用方注入时间，而不是偷偷读时钟）
    assert (inspect.signature(noise_policy.suppress_until)
            .parameters["now"].default is inspect.Parameter.empty)


# ── 日聚合纯计算 ──────────────────────────────────────────────

def test_consecutive_active_days():
    counts = {TODAY: 4, TODAY - timedelta(days=1): 5, TODAY - timedelta(days=2): 3}
    assert noise_policy.consecutive_active_days(counts, TODAY) == 3
    # 昨天断档 → 连续段只剩今天
    gap = {TODAY: 4, TODAY - timedelta(days=2): 9}
    assert noise_policy.consecutive_active_days(gap, TODAY) == 1
    # 今天没触发 → 0（正在收敛，不该抑噪）
    assert noise_policy.consecutive_active_days({TODAY - timedelta(days=1): 9}, TODAY) == 0


def test_average_per_active_day_uses_run_only():
    counts = {TODAY: 4, TODAY - timedelta(days=1): 5, TODAY - timedelta(days=2): 3,
              TODAY - timedelta(days=5): 100}   # 5 天前的孤立爆量不属于连续段
    assert noise_policy.average_per_active_day(counts, TODAY) == 4.0
    assert noise_policy.average_per_active_day({TODAY - timedelta(days=1): 9}, TODAY) == 0.0


def test_summarize_feeds_should_suppress():
    """聚合结果直接喂判定：3 日 × 4 次 → 命中；2 日 × 4 次 → 不命中"""
    three = {TODAY: 4, TODAY - timedelta(days=1): 4, TODAY - timedelta(days=2): 4}
    summary = noise_policy.summarize(three, TODAY)
    assert summary["trigger_today"] == 4
    assert summary["consecutive_days"] == 3
    assert summary["avg_per_day"] == 4.0
    assert summary["active_days"] == 3
    assert noise_policy.should_suppress(
        summary["trigger_today"], summary["consecutive_days"],
        summary["avg_per_day"]) is True

    two = {TODAY: 4, TODAY - timedelta(days=1): 4}
    s2 = noise_policy.summarize(two, TODAY)
    assert noise_policy.should_suppress(
        s2["trigger_today"], s2["consecutive_days"], s2["avg_per_day"]) is False


def test_summarize_trigger_days_detail_is_sorted():
    counts = {"2026-09-18": 2, "2026-09-16": 3}   # 字符串键也接受（SQL 可能给 str）
    summary = noise_policy.summarize(counts, TODAY)
    assert summary["trigger_days"] == [
        {"date": "2026-09-16", "count": 3}, {"date": "2026-09-18", "count": 2}]
    assert summary["consecutive_days"] == 1        # 09-17 缺失 → 断档


def test_summarize_handles_empty():
    summary = noise_policy.summarize({}, TODAY)
    assert summary == {"trigger_today": 0, "consecutive_days": 0, "avg_per_day": 0.0,
                       "active_days": 0, "trigger_days": []}


# ── purity：判定函数不得读时钟 / 读库 ─────────────────────────

@pytest.mark.parametrize("func_name", [
    "should_suppress", "noise_reason", "consecutive_active_days",
    "average_per_active_day", "summarize", "is_repair_action", "is_change_kind",
    "is_suppressed",
])
def test_pure_functions_do_not_read_clock_or_db(func_name):
    """这些函数体内不得出现时钟调用或任何 ORM/SQL 入口（时间由调用方注入）"""
    src = inspect.getsource(getattr(noise_policy, func_name))
    for forbidden in ("datetime.now", "date.today", "time.time", "sqlalchemy",
                      "session", "get_session"):
        assert forbidden not in src, f"{func_name} 含 {forbidden}"


def test_module_does_not_import_persistence_or_application_layers():
    src = inspect.getsource(noise_policy)
    for forbidden in ("import sqlalchemy", "infrastructure", "application.services"):
        assert forbidden not in src, forbidden
