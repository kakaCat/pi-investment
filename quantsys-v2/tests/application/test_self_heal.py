"""NoiseSelfHealService 单测 + 路由契约（REQ-c9f899 R6 / t8）

三层覆盖，各自用最合适的替身，避免"用真库测不了拒绝、用 fake 测不了落库"：

  1. **服务层（内存 fake，不碰 DB）**：抑噪三件套（置抑噪态 / 建 P1「修规则」待办 / 写审计）、
     日阈值边界、日幂等（同日不重复建待办）、授权边界（用户账户被 agent 改 → 未授权）、
     reason 必填、change_kind 白名单、清抑噪态。
  2. **路由层（TestClient 自挂 router，替换 _service 工厂）**：200 / 400 / 403 / 404 的 HTTP 映射
     ——断言的是"领域错误码如何变成状态码"，不需要真库。
  3. **真库集成（fixture，无库自动 skip）**：真实适配器 + quant_test，端到端证明
     watch_triggers 聚合 → 抑噪 → watch_todos → watch_rule_changes 四条链真的落库。
  4. **引擎触发摄入路径（fake + 真库）**：抑噪期规则的触发落库 suppressed=true、
     disposition=auto_observed、**不进摘要队列（notify 不被调用）、不额外建待办**；
     抑噪到期/无抑噪态时行为与改造前完全一致（suppressed=false）。

为什么 fake 层必不可少：授权拒绝与「是否误写库」必须能精确断言（真库测不出「该拒绝却写了一半」）。

quant_test 同步说明：t1 的 20260918 迁移只对 quant_investment 建了表；本模块按 t5 的做法，
从迁移常量读 DDL 在**测试库**补齐 watch_rule_changes / watch_todos 与 watch_rules 的四个
noise 列（不执行迁移脚本、不碰生产库），缺库则整体 skip（不伪造通过）。
"""
from datetime import datetime, time, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes import watch_rule_repair_async as repair_route
from application.services.watch_engine.engine import SUPPRESSED_TRIGGER_REASON, WatchEngine
from application.services.watch_engine.noise_self_heal_service import NoiseSelfHealService
from application.services.watch_engine.todo_service import TodoService
from domain.watch.ports import (
    IWatchRuleChangeRepository,
    IWatchRuleNoiseRepository,
    WatchRuleChangeInvalidKind,
    WatchRuleChangeMissingReason,
    WatchRuleChangeRuleNotFound,
    WatchRuleChangeUnauthorized,
)

NOW = datetime(2026, 9, 18, 10, 0, 0)
TODAY = NOW.date()
DAY = timedelta(days=1)


# ── 内存替身（行为对齐端口契约）────────────────────────────────

def _rule(rule_id, symbol, account, **over):
    row = {"id": rule_id, "symbol": symbol, "account": account, "linked_account": None,
           "enabled": True, "noise_state": None, "suppress_until": None,
           "self_heal_count": 0, "last_repair_at": None}
    row.update(over)
    return row


class FakeRuleNoiseRepo:
    """IWatchRuleNoiseRepository 的内存实现（get_rule 返回可变 dict，便于断言写回）"""

    def __init__(self, rules, daily=None):
        self.rules = rules
        self.daily = dict(daily or {})
        self.suppressed_calls = []
        self.repaired_calls = []

    def get_rule(self, rule_id):
        return self.rules.get(rule_id)

    def daily_counts(self, since, until):
        out = {}
        for rid, counts in self.daily.items():
            selected = {d: c for d, c in counts.items()
                        if since <= datetime.combine(d, time.min) < until}
            if selected:
                out[rid] = selected
        return out

    def mark_suppressed(self, rule_id, suppress_until, now=None):
        row = self.rules[rule_id]
        row["noise_state"] = "suppressed"
        row["suppress_until"] = suppress_until
        row["self_heal_count"] = (row.get("self_heal_count") or 0) + 1
        self.suppressed_calls.append((rule_id, suppress_until))

    def mark_repaired(self, rule_id, now=None):
        row = self.rules[rule_id]
        row["noise_state"] = None
        row["suppress_until"] = None
        row["last_repair_at"] = now
        row["self_heal_count"] = (row.get("self_heal_count") or 0) + 1
        self.repaired_calls.append((rule_id, now))


class FakeChangeRepo:
    """IWatchRuleChangeRepository 的内存实现（clock 可注入，保证日幂等可测）"""

    def __init__(self, clock=None):
        self.rows = []
        self._seq = 0
        self._clock = clock or (lambda: NOW)

    def record(self, rule_id, changed_by, change_kind, before=None, after=None, reason="",
               trigger_id=None, todo_id=None, decision_audit_id=None):
        if not str(reason or "").strip():
            raise ValueError("reason 必填（fake 与适配器同契约）")
        self._seq += 1
        row = SimpleNamespace(
            id=self._seq, rule_id=rule_id, changed_by=changed_by,
            change_kind=str(change_kind or "").strip().lower(), before=before, after=after,
            reason=reason, trigger_id=trigger_id, todo_id=todo_id,
            decision_audit_id=decision_audit_id, created_at=self._clock())
        self.rows.append(row)
        return row

    def exists_since(self, rule_id, change_kind, since):
        kind = str(change_kind or "").strip().lower()
        return any(r.rule_id == rule_id and r.change_kind == kind and r.created_at >= since
                   for r in self.rows)

    def list_by_rule(self, rule_id, limit=50):
        rows = [r for r in reversed(self.rows) if r.rule_id == rule_id]
        return rows[:limit]


class FakeTodoRepo:
    """IWatchTodoRepository 的最小实现（t8 只用到 create）"""

    def __init__(self):
        self.rows = []
        self._seq = 100

    def create(self, symbol, *, rule_id=None, trigger_id=None, account=None, level,
               flow_state="L1", owner_kind=None, owner_ref=None, autonomy=None,
               sla_seconds=1800, due_at=None, action_kind=None):
        self._seq += 1
        todo = SimpleNamespace(id=self._seq, symbol=symbol, rule_id=rule_id,
                               trigger_id=trigger_id, account=account, level=level,
                               flow_state=flow_state, owner_kind=owner_kind,
                               owner_ref=owner_ref, autonomy=autonomy,
                               sla_seconds=sla_seconds, due_at=due_at,
                               action_kind=action_kind, terminal=None)
        self.rows.append(todo)
        return todo


AGENT_RULE = _rule(1, "600150.SH", "agent_brain")
USER_RULE = _rule(2, "601888.SH", "user_main_simulation")
STRATEGY_RULE = _rule(3, "600000.SH", "v13_simulation")
UNKNOWN_ACCOUNT_RULE = _rule(4, "600001.SH", "unregistered_account")
NO_ACCOUNT_RULE = _rule(5, "600002.SH", None)


def _build(rules=None, daily=None, clock=None, **kwargs):
    default_rules = {r["id"]: dict(r) for r in (AGENT_RULE, USER_RULE, STRATEGY_RULE,
                                                UNKNOWN_ACCOUNT_RULE, NO_ACCOUNT_RULE)}
    rule_repo = FakeRuleNoiseRepo(rules or default_rules, daily or {})
    change_repo = FakeChangeRepo(clock=clock)
    todo_repo = FakeTodoRepo()
    service = NoiseSelfHealService(rule_repo, change_repo, TodoService(todo_repo), **kwargs)
    return service, rule_repo, change_repo, todo_repo


def _eight_today(rule_id):
    return {rule_id: {TODAY: 8}}


def _three_days(rule_id, counts=(4, 4, 4)):
    return {rule_id: {TODAY - i * DAY: c for i, c in enumerate(counts)}}


# ── 服务：单日阈值 ────────────────────────────────────────────

def test_scan_7_triggers_no_suppress_no_todo():
    service, rule_repo, change_repo, todo_repo = _build(daily={1: {TODAY: 7}})
    result = service.scan(now=NOW)
    assert result["suppressed"] == []
    assert rule_repo.rules[1]["noise_state"] is None
    assert change_repo.rows == []
    assert todo_repo.rows == []


def test_scan_8_triggers_suppress_todo_and_audit():
    """t8 验收：超阈值 → ①抑噪态 ②P1「修规则」待办 ③system 抑噪审计"""
    service, rule_repo, change_repo, todo_repo = _build(daily=_eight_today(1))
    result = service.scan(now=NOW)

    assert len(result["suppressed"]) == 1
    item = result["suppressed"][0]
    assert item["rule_id"] == 1 and item["account"] == "agent_brain"
    assert item["trigger_today"] == 8

    # ① 置抑噪态：suppress_until = now + 默认 24h
    row = rule_repo.rules[1]
    assert row["noise_state"] == "suppressed"
    assert row["suppress_until"] == NOW + timedelta(hours=24)
    assert row["self_heal_count"] == 1

    # ② 建「修规则」待办：P1 / rule_change / 直达 L3 / owner 按账户路由（agent 自有 → agent）
    assert len(todo_repo.rows) == 1
    todo = todo_repo.rows[0]
    assert (todo.level, todo.action_kind, todo.flow_state) == ("P1", "rule_change", "L3")
    assert (todo.owner_kind, todo.autonomy) == ("agent", "autonomous")
    assert todo.account == "agent_brain" and todo.rule_id == 1
    assert todo.sla_seconds == 1800 and todo.due_at == NOW + timedelta(seconds=1800)

    # ③ 写审计：changed_by=system / change_kind=suppress / reason 含触发次数 / 关联待办
    assert len(change_repo.rows) == 1
    change = change_repo.rows[0]
    assert (change.changed_by, change.change_kind) == ("system", "suppress")
    assert change.todo_id == todo.id
    assert "8" in change.reason and "阈值" in change.reason
    assert change.after["noise_state"] == "suppressed"


def test_scan_3_days_avg_4_suppress():
    service, rule_repo, _, todo_repo = _build(daily=_three_days(1, (4, 4, 4)))
    result = service.scan(now=NOW)
    assert [s["rule_id"] for s in result["suppressed"]] == [1]
    assert rule_repo.rules[1]["noise_state"] == "suppressed"
    assert len(todo_repo.rows) == 1


def test_scan_2_days_avg_4_no_suppress():
    service, rule_repo, change_repo, todo_repo = _build(daily=_three_days(1, (4, 4)))
    assert service.scan(now=NOW)["suppressed"] == []
    assert rule_repo.rules[1]["noise_state"] is None
    assert (change_repo.rows, todo_repo.rows) == ([], [])


def test_scan_3_days_avg_below_4_no_suppress():
    service, rule_repo, _, _ = _build(daily=_three_days(1, (3, 3, 3)))
    assert service.scan(now=NOW)["suppressed"] == []
    assert rule_repo.rules[1]["noise_state"] is None


def test_scan_break_in_run_no_suppress():
    """今天火但昨天断档：连续天数是 1，不算「连续多日骚扰」（不误抑噪）"""
    daily = {1: {TODAY: 4, TODAY - 2 * DAY: 9, TODAY - 3 * DAY: 9}}
    service, rule_repo, _, _ = _build(daily=daily)
    assert service.scan(now=NOW)["suppressed"] == []
    assert rule_repo.rules[1]["noise_state"] is None


def test_scan_thresholds_overridable():
    """阈值可注入（同一份数据，阈值放宽后不再抑噪）"""
    strict, _, _, _ = _build(daily={1: {TODAY: 8}})
    assert strict.scan(now=NOW)["suppressed"] != []
    loose, rule_repo2, _, _ = _build(daily={1: {TODAY: 8}}, max_triggers_per_day=20,
                                     min_consecutive_days=5)
    assert loose.scan(now=NOW)["suppressed"] == []
    assert rule_repo2.rules[1]["noise_state"] is None


# ── 服务：幂等 / 边界 ─────────────────────────────────────────

def test_scan_idempotent_within_same_day():
    """同一规则同一日重复 scan：不重复建待办、不重复写审计（判据=当日已有 suppress 变更）"""
    service, _, change_repo, todo_repo = _build(daily=_eight_today(1))
    service.scan(now=NOW)
    second = service.scan(now=NOW + timedelta(hours=2))
    assert len(todo_repo.rows) == 1
    assert len(change_repo.rows) == 1
    assert second["suppressed"] == []
    assert second["skipped"][0]["reason"] == "already_healed_today"


def test_scan_next_day_can_heal_again():
    """跨日：新的一天若仍超阈值 → 再建一条修规则待办（R6 每日都要有人管）"""
    service, _, change_repo, todo_repo = _build(daily={1: {TODAY: 8, TODAY + DAY: 8}})
    service.scan(now=NOW)
    service.scan(now=NOW + DAY)
    assert len(todo_repo.rows) == 2
    assert len(change_repo.rows) == 2


def test_scan_skips_rule_missing_without_crash():
    """悬空触发（规则已删）：登记跳过，不抛错、不写任何东西"""
    service, _, change_repo, todo_repo = _build(daily={999: {TODAY: 8}})
    result = service.scan(now=NOW)
    assert result["suppressed"] == []
    assert result["skipped"] == [{"rule_id": 999, "reason": "rule_missing"}]
    assert (change_repo.rows, todo_repo.rows) == ([], [])


def test_scan_skips_out_of_scope_strategy_account():
    """策略账户规则属数据缺陷：盯盘不介入，不自愈（R3）"""
    service, rule_repo, change_repo, todo_repo = _build(daily=_eight_today(3))
    result = service.scan(now=NOW)
    assert result["suppressed"] == []
    assert result["skipped"][0]["reason"] == "out_of_scope"
    assert rule_repo.rules[3]["noise_state"] is None
    assert (change_repo.rows, todo_repo.rows) == ([], [])


def test_scan_no_account_rule_becomes_agent_remind_only_todo():
    """空账户 = 数据缺陷：照常建待办（不阻断闭环），交 agent 但只提醒、不得下单

    owner_kind='agent' + autonomy='remind_only' 是 owner_router 的数据缺陷档
    （照常叫 agent 去补归属，但补齐前不得下单），不是 user 档——别把两档混读。
    """
    service, _, _, todo_repo = _build(daily=_eight_today(5))
    service.scan(now=NOW)
    todo = todo_repo.rows[0]
    assert todo.account is None
    assert (todo.owner_kind, todo.autonomy) == ("agent", "remind_only")


# ── 服务：修复授权 / 校验 ─────────────────────────────────────

def test_apply_repair_agent_account_allowed_and_clears_noise():
    service, rule_repo, change_repo, _ = _build(daily=_eight_today(1), clock=lambda: NOW)
    service.scan(now=NOW)
    out = service.apply_repair(1, "cooldown", params={"cooldown_sec": 3600},
                               reason="同一条件反复穿越，冷却 60s→3600s", operator="agent",
                               decision_audit_id="DA-t8-1", now=NOW)
    change = out["change"]
    assert (change.changed_by, change.change_kind) == ("agent", "cooldown")
    assert change.after == {"cooldown_sec": 3600}
    assert change.decision_audit_id == "DA-t8-1"
    assert out["rule"]["noise_state"] is None           # 修复后清抑噪态、恢复原级别
    assert out["rule"]["last_repair_at"] == NOW.isoformat()
    assert rule_repo.repaired_calls and rule_repo.repaired_calls[0][0] == 1


def test_apply_repair_user_account_rejected_for_agent():
    """t8 验收：用户账户规则被 agent 直接改 → 未授权（路由层 403）"""
    service, rule_repo, change_repo, _ = _build()
    with pytest.raises(WatchRuleChangeUnauthorized):
        service.apply_repair(2, "retire", reason="规则已失效", operator="agent")
    assert change_repo.rows == []                       # 未授权不得留下任何痕迹
    assert rule_repo.rules[2]["noise_state"] is None


def test_apply_repair_user_account_allowed_for_user():
    service, _, change_repo, _ = _build()
    out = service.apply_repair(2, "threshold", params={"price": 55.0},
                               reason="阈值贴市价，上调到 55", operator="user")
    assert out["change"].changed_by == "user"
    assert len(change_repo.rows) == 1


def test_apply_repair_unregistered_account_rejected_for_agent():
    """未登记账户按最保守：owner_kind=user → agent 不得改"""
    service, _, change_repo, _ = _build()
    with pytest.raises(WatchRuleChangeUnauthorized):
        service.apply_repair(4, "cooldown", reason="改冷却", operator="agent")
    assert change_repo.rows == []


def test_apply_repair_no_account_rejected_for_agent():
    service, _, _, _ = _build()
    with pytest.raises(WatchRuleChangeUnauthorized):
        service.apply_repair(5, "cooldown", reason="改冷却", operator="agent")


def test_apply_repair_strategy_account_rejected_for_agent_allowed_for_user():
    """策略账户盯盘不介入：agent 不得改（R3）；用户本人可以处置这条缺陷规则"""
    service, _, _, _ = _build()
    with pytest.raises(WatchRuleChangeUnauthorized):
        service.apply_repair(3, "retire", reason="规则属数据缺陷", operator="agent")
    out = service.apply_repair(3, "retire", reason="退役这条缺陷规则", operator="user")
    assert out["change"].changed_by == "user"


def test_apply_repair_requires_reason():
    service, _, change_repo, _ = _build()
    for bad in (None, "", "   "):
        with pytest.raises(WatchRuleChangeMissingReason):
            service.apply_repair(1, "cooldown", reason=bad, operator="agent")
    assert change_repo.rows == []


def test_apply_repair_rejects_unknown_change_kind():
    service, _, change_repo, _ = _build()
    with pytest.raises(WatchRuleChangeInvalidKind):
        service.apply_repair(1, "explode", reason="随便", operator="agent")
    with pytest.raises(WatchRuleChangeInvalidKind):
        service.apply_repair(1, None, reason="随便", operator="agent")
    assert change_repo.rows == []


def test_apply_repair_rule_not_found():
    service, _, _, _ = _build()
    with pytest.raises(WatchRuleChangeRuleNotFound):
        service.apply_repair(999999, "cooldown", reason="改冷却", operator="agent")


def test_apply_repair_suppress_keeps_noise_state():
    """suppress 是抑噪动作：置态而不是清态（与修复类相反）"""
    service, rule_repo, _, _ = _build()
    out = service.apply_repair(1, "suppress", reason="手动抑噪", operator="agent", now=NOW)
    assert out["rule"]["noise_state"] == "suppressed"
    assert rule_repo.suppressed_calls and rule_repo.repaired_calls == []


def test_apply_repair_unsuppress_clears_state():
    service, rule_repo, _, _ = _build()
    rule_repo.rules[1]["noise_state"] = "suppressed"
    out = service.apply_repair(1, "unsuppress", reason="已修复，恢复投递", operator="agent")
    assert out["rule"]["noise_state"] is None
    assert out["change"].change_kind == "unsuppress"


def test_apply_repair_change_kind_case_and_space_insensitive():
    service, _, change_repo, _ = _build()
    service.apply_repair(1, "  RETIRE ", reason="退役", operator="agent")
    assert change_repo.rows[0].change_kind == "retire"


# ── 服务：读侧 noise_status ───────────────────────────────────

def test_noise_status_reports_state_and_counts():
    service, rule_repo, _, _ = _build(daily=_three_days(1, (4, 4, 4)))
    rule_repo.rules[1]["noise_state"] = "suppressed"
    rule_repo.rules[1]["self_heal_count"] = 2
    status = service.noise_status(1, now=NOW)
    assert status["noise_state"] == "suppressed"
    assert status["trigger_today"] == 4
    assert status["trigger_days"] == 3
    assert status["self_heal_count"] == 2
    assert status["should_suppress"] is True            # 连续 3 日 × 日均 4 → 命中
    assert len(status["trigger_days_detail"]) == 3


def test_noise_status_exposes_suppression_flag_for_ingestion_gate():
    """触发摄入路径的判据：is_suppressed=True 的新触发只进 P3 聚合、不建 todo

    ⚠️ 接线（触发写入/引擎承压保护）不在 t8 允许改动的文件内（属 t9/t12），本任务
    提供判定函数与读模型字段，供接线方单一事实源地调用。
    """
    service, _, _, _ = _build(daily=_eight_today(1))
    service.scan(now=NOW)
    assert service.noise_status(1, now=NOW)["is_suppressed"] is True
    assert service.noise_status(1, now=NOW + timedelta(hours=25))["is_suppressed"] is False


def test_noise_status_unknown_rule_raises():
    service, _, _, _ = _build()
    with pytest.raises(WatchRuleChangeRuleNotFound):
        service.noise_status(999999, now=NOW)


# ── 路由层：HTTP 映射（TestClient 自挂 router）──────────────────

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(repair_route.router)
    return TestClient(app)


@pytest.fixture
def fake_service(monkeypatch):
    service, rule_repo, change_repo, todo_repo = _build(daily=_eight_today(1))
    monkeypatch.setattr(repair_route, "_service", lambda: service)
    return SimpleNamespace(service=service, rules=rule_repo, changes=change_repo,
                           todos=todo_repo)


def test_route_get_noise_200(client, fake_service):
    resp = client.get("/api/watch/rules/1/noise")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["rule_id"] == 1 and data["trigger_today"] == 8
    assert data["noise_state"] is None
    assert data["trigger_days"] == 1
    assert data["thresholds"]["max_triggers_per_day"] == 8


def test_route_get_noise_404(client, fake_service):
    resp = client.get("/api/watch/rules/999999/noise")
    assert resp.status_code == 404
    assert resp.json()["error"] == "watch_rule_change_rule_not_found"


def test_route_post_repair_403_for_user_account(client, fake_service):
    """默认 operator=agent：改用户账户规则必须 403（保守默认）"""
    resp = client.post("/api/watch/rules/2/repair",
                       json={"change_kind": "retire", "reason": "规则失效"})
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"] == "watch_rule_change_unauthorized"
    assert fake_service.changes.rows == []


def test_route_post_repair_400_missing_reason(client, fake_service):
    for body in ({"change_kind": "cooldown"},
                 {"change_kind": "cooldown", "reason": "   "}):
        resp = client.post("/api/watch/rules/1/repair", json=body)
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"] == "watch_rule_change_missing_reason"
    assert fake_service.changes.rows == []


def test_route_post_repair_400_invalid_change_kind(client, fake_service):
    resp = client.post("/api/watch/rules/1/repair",
                       json={"change_kind": "explode", "reason": "乱来"})
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "watch_rule_change_invalid_kind"


def test_route_post_repair_200_agent_account(client, fake_service):
    resp = client.post("/api/watch/rules/1/repair",
                       json={"change_kind": "threshold", "params": {"price": 27.0},
                             "reason": "阈值贴市价，上调", "decision_audit_id": "DA-t8-2"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["rule"]["noise_state"] is None
    assert data["change"]["change_kind"] == "threshold"
    assert data["change"]["changed_by"] == "agent"
    assert data["change"]["reason"] == "阈值贴市价，上调"
    assert data["change"]["created_at"]                      # ISO 字符串（可 JSON 化）


def test_route_post_repair_404_unknown_rule(client, fake_service):
    resp = client.post("/api/watch/rules/999999/repair",
                       json={"change_kind": "cooldown", "reason": "改冷却"})
    assert resp.status_code == 404
    assert resp.json()["error"] == "watch_rule_change_rule_not_found"


def test_route_post_repair_user_operator_on_user_account_200(client, fake_service):
    resp = client.post("/api/watch/rules/2/repair",
                       json={"change_kind": "cooldown", "reason": "冷却延长",
                             "operator": "user"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["change"]["changed_by"] == "user"


# ── 真库集成（quant_test；无库自动 skip）────────────────────────

_MIGRATION_FILE = (Path(__file__).resolve().parents[2] / "infrastructure" / "persistence"
                   / "migrations" / "20260918_watch_todo_loop.py")
_DB_RULE_ID = 9998001
_DB_SYMBOL = "T8WATCH.SZ"
_DB_ACCOUNT = "t8_sentinel_account"


def _dsn():
    from infrastructure.persistence.database.engine import _resolve_db_dsn
    return _resolve_db_dsn()


def _db_available():
    import psycopg2
    dsn = _dsn()
    if not dsn:
        return False
    try:
        psycopg2.connect(dsn).close()
    except Exception:  # noqa: BLE001
        return False
    return True


def _migration_module():
    spec = spec_from_file_location("_t8_watch_migration", str(_MIGRATION_FILE))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def watch_tables():
    """把测试库补齐到「t8 能跑」的最小结构（幂等；不执行迁移脚本、不碰生产库）"""
    if not _db_available():
        pytest.skip("test database unavailable")
    import psycopg2
    migration = _migration_module()
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        for name, ddl in migration.TABLES:
            if name not in ("watch_todos", "watch_rule_changes"):
                continue
            cur.execute("SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'quant' AND table_name = %s", (name,))
            if cur.fetchone() is None:
                cur.execute(ddl)
        for table, column, coltype in migration.COLUMNS:
            if table != "watch_rules":
                continue
            cur.execute("SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = 'quant' AND table_name = %s AND column_name = %s",
                        (table, column))
            if cur.fetchone() is None:
                cur.execute("ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS %s %s"
                            % (column, coltype))
        cur.execute("CREATE INDEX IF NOT EXISTS idx_watch_rule_changes_rule "
                    "ON quant.watch_rule_changes (rule_id, created_at)")
    finally:
        conn.close()
    yield


def _db_cleanup():
    import psycopg2
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        for table in ("watch_rule_changes", "watch_todos", "watch_triggers"):
            cur.execute("DELETE FROM quant.%s WHERE rule_id = %%s" % table, (_DB_RULE_ID,))
        cur.execute("DELETE FROM quant.watch_rules WHERE id = %s", (_DB_RULE_ID,))
    finally:
        conn.close()


def _seed_db_rule(trigger_count=8, when=None, conditions_json="[]"):
    """造一条规则 + 当日 N 次触发（哨兵 id/symbol，测试后清理）

    conditions_json：规则条件（引擎用例需要一条真能触发的条件，缺省空列表=引擎不判定）。
    """
    import psycopg2
    stamp = when or datetime.now()
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO quant.watch_rules "
            "(id, symbol, enabled, conditions, created_by, account, notify_mode, "
            " created_at, updated_at) "
            "VALUES (%s, %s, TRUE, %s::jsonb, 'test', %s, 'direct', %s, %s)",
            (_DB_RULE_ID, _DB_SYMBOL, conditions_json, _DB_ACCOUNT, stamp, stamp))
        for _ in range(trigger_count):
            cur.execute(
                "INSERT INTO quant.watch_triggers "
                "(rule_id, symbol, condition, trigger_price, triggered_at) "
                "VALUES (%s, %s, '[]'::jsonb, %s, %s)",
                (_DB_RULE_ID, _DB_SYMBOL, 10.0, stamp))
    finally:
        conn.close()


def _set_suppress_until(rule_id, when, noise_state="suppressed"):
    """把抑噪态钉到指定时刻（引擎用例用固定 now_fn，避免依赖系统时钟）

    scan 写入的 suppress_until 基于真实 now；引擎用例断言必须可复现，故显式覆盖。
    """
    import psycopg2
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute("UPDATE quant.watch_rules SET noise_state = %s, suppress_until = %s "
                    "WHERE id = %s", (noise_state, when, rule_id))
    finally:
        conn.close()


def _real_service():
    from adapters.outbound.repositories.watch_rule_change_repository import (
        WatchRuleChangeRepository,
    )
    from adapters.outbound.repositories.watch_rule_noise_repository import (
        WatchRuleNoiseRepository,
    )
    from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
    return NoiseSelfHealService(WatchRuleNoiseRepository(), WatchRuleChangeRepository(),
                                TodoService(WatchTodoRepository()))


def test_real_db_scan_suppresses_creates_todo_and_audit(watch_tables):
    """端到端真库：watch_triggers 聚合 → 抑噪 → watch_todos → watch_rule_changes"""
    import psycopg2
    _db_cleanup()
    _seed_db_rule(trigger_count=8)
    try:
        service = _real_service()
        result = service.scan(now=datetime.now())
        assert _DB_RULE_ID in [s["rule_id"] for s in result["suppressed"]], result

        conn = psycopg2.connect(_dsn())
        try:
            cur = conn.cursor()
            cur.execute("SELECT noise_state, suppress_until, self_heal_count "
                        "FROM quant.watch_rules WHERE id = %s", (_DB_RULE_ID,))
            noise_state, suppress_until, self_heal_count = cur.fetchone()
            assert noise_state == "suppressed" and suppress_until is not None
            assert self_heal_count >= 1
            cur.execute("SELECT level, action_kind, account, owner_kind, autonomy "
                        "FROM quant.watch_todos WHERE rule_id = %s", (_DB_RULE_ID,))
            todos = cur.fetchall()
            assert todos == [("P1", "rule_change", _DB_ACCOUNT, "user", "remind_only")], todos
            cur.execute("SELECT changed_by, change_kind, reason "
                        "FROM quant.watch_rule_changes WHERE rule_id = %s", (_DB_RULE_ID,))
            changes = cur.fetchall()
            assert len(changes) == 1
            assert changes[0][0] == "system" and changes[0][1] == "suppress"
            assert "8" in changes[0][2]
        finally:
            conn.close()
    finally:
        _db_cleanup()


def test_real_db_route_get_noise(watch_tables):
    """真实适配器 + TestClient：GET /noise 返回落库状态与统计"""
    _db_cleanup()
    _seed_db_rule(trigger_count=8)
    try:
        app = FastAPI()
        app.include_router(repair_route.router)
        client = TestClient(app)
        # 先跑一次 scan（真实服务）把抑噪态落库
        _real_service().scan(now=datetime.now())
        resp = client.get("/api/watch/rules/%d/noise" % _DB_RULE_ID)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["noise_state"] == "suppressed"
        assert data["trigger_today"] >= 8
        assert data["self_heal_count"] >= 1
    finally:
        _db_cleanup()


# ── 端口 / 适配器契约防漂移（不需要 DB：校验在触碰 session 之前）────

def test_port_method_sets_are_stable():
    """端口方法集固定——增删/改名必须显式面对本测试"""
    assert IWatchRuleChangeRepository.__abstractmethods__ == frozenset(
        {"record", "exists_since", "list_by_rule"})
    assert IWatchRuleNoiseRepository.__abstractmethods__ == frozenset(
        {"get_rule", "daily_counts", "mark_suppressed", "mark_repaired"})


def test_adapter_and_fake_signatures_match_ports():
    """适配器/fake 的参数名必须与端口逐一相同（签名漂移 = 静默 TypeError 的温床）"""
    import inspect

    from adapters.outbound.repositories.watch_rule_change_repository import (
        WatchRuleChangeRepository,
    )
    from adapters.outbound.repositories.watch_rule_noise_repository import (
        WatchRuleNoiseRepository,
    )

    def names(func):
        return list(inspect.signature(func).parameters)

    pairs = [
        (IWatchRuleChangeRepository, WatchRuleChangeRepository(), FakeChangeRepo()),
        (IWatchRuleNoiseRepository, WatchRuleNoiseRepository(), FakeRuleNoiseRepo({})),
    ]
    for port, adapter, fake in pairs:
        for method in port.__abstractmethods__:
            expected = names(getattr(port, method))
            assert callable(getattr(adapter, method, None)), method
            assert callable(getattr(fake, method, None)), method
            assert names(getattr(type(adapter), method)) == expected, method
            assert names(getattr(type(fake), method)) == expected, method


def test_change_adapter_rejects_bad_input_before_touching_db():
    """reason 必填 / changed_by 枚举 / change_kind 非空：都在写库前响亮拒绝"""
    from adapters.outbound.repositories.watch_rule_change_repository import (
        WatchRuleChangeRepository,
    )

    repo = WatchRuleChangeRepository()
    for bad in (None, "", "   "):
        with pytest.raises(ValueError):
            repo.record(1, "agent", "cooldown", reason=bad)
    with pytest.raises(ValueError):
        repo.record(1, "hacker", "cooldown", reason="越权身份")
    with pytest.raises(ValueError):
        repo.record(1, "agent", "  ", reason="空动作")
    with pytest.raises(ValueError):
        repo.exists_since(1, "  ", NOW)


def test_change_adapter_accepts_valid_input_shape():
    """合法输入不被前置校验误拦（真正的落库由真库用例覆盖）——用 monkeypatch 短路 session"""
    from adapters.outbound.repositories.watch_rule_change_repository import (
        WatchRuleChangeRepository,
    )

    captured = {}

    class FakeSession:
        def add(self, obj):
            captured["obj"] = obj

        def commit(self):
            captured["committed"] = True

        def refresh(self, obj):
            pass

    repo = WatchRuleChangeRepository()
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(type(repo), "session", property(lambda self: FakeSession()))
        row = repo.record(7, "system", "suppress", before={"a": 1}, after={"b": 2},
                          reason="反复触发抑噪", todo_id=3)
    finally:
        monkeypatch.undo()
    assert captured["committed"] is True
    assert row.rule_id == 7 and row.changed_by == "system" and row.change_kind == "suppress"
    assert row.reason == "反复触发抑噪" and row.todo_id == 3

# ── 引擎触发摄入路径：抑噪期只归档（R6 / t8，2026-09-18 续工）──────────

_ENGINE_NOW = datetime(2026, 9, 18, 10, 0, 0)   # 周五 10:00，交易时段内


class _RecordingTriggerRepo:
    """WatchTriggerRepository 的内存替身：记录 record() 的 suppressed 形参"""

    def __init__(self):
        self.rows = []

    def record(self, rule_id, symbol, condition, trigger_price, detail=None, notified=False,
               disposition="pending", disposition_reason=None, disposition_by="system",
               dup_of=None, suppressed=False):
        row = SimpleNamespace(id=len(self.rows) + 1, rule_id=rule_id, symbol=symbol,
                              condition=condition, trigger_price=trigger_price,
                              disposition=disposition, disposition_reason=disposition_reason,
                              notified=notified, suppressed=bool(suppressed), dup_of=dup_of)
        self.rows.append(row)
        return row


class _EngineNotifier:
    """引擎用 notifier 替身：notify 被调用 = 进了摘要队列；同时模拟真实落库（默认 False）"""

    def __init__(self, trigger_repo=None):
        self.trigger_repo = trigger_repo
        self.notifications = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append((rule.id, condition["type"]))
        if self.trigger_repo is None:
            return SimpleNamespace(id=len(self.notifications))
        return self.trigger_repo.record(
            rule_id=rule.id, symbol=rule.symbol, condition=condition,
            trigger_price=float(quote.price),
            detail={"value": result.value, "message": result.message},
            notified=True, disposition=kwargs.get("disposition"),
            disposition_reason=kwargs.get("disposition_reason"))


class _EngineRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class _EngineQuoteService:
    def __init__(self, prices):
        self.prices = prices

    def get_realtime_quote(self, symbol):
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price, prev_close=98.0,
                               volume=1_000_000, change_pct=None)


def _engine_rule(**over):
    """引擎可消费的规则替身（字段口径对齐 tests/services/test_watch_engine.py）"""
    row = dict(id=1, symbol="600150.SH",
               conditions=[{"type": "price_break",
                            "params": {"direction": "above", "price": 100.0}}],
               cost_price=None, active_window=None, intent="exit_stop",
               action_hint={"trigger_level": "L2", "action_on_trigger": "sell"},
               escalation_policy=None, scope="symbol", linked_account=None,
               lifecycle_stage="watching", created_from=None, next_action_hint=None,
               target=None, review_interval_days=None, review_due_at=None, enabled=True,
               noise_state=None, suppress_until=None)
    row.update(over)
    return SimpleNamespace(**row)


def _engine(rules, prices, notifier, now=_ENGINE_NOW):
    return WatchEngine(rule_repo=_EngineRuleRepo(rules),
                       quote_service=_EngineQuoteService(prices),
                       notifier=notifier, now_fn=lambda: now)


def test_engine_suppressed_rule_archives_trigger_without_notify_or_todo():
    """抑噪期：落库 suppressed=true + auto_observed，不 notify（=不进摘要队列/不建待办）"""
    trigger_repo = _RecordingTriggerRepo()
    notifier = _EngineNotifier(trigger_repo)
    rule = _engine_rule(noise_state="suppressed",
                        suppress_until=_ENGINE_NOW + timedelta(hours=1))
    engine = _engine([rule], {"600150.SH": 101.0}, notifier)

    events = engine.tick()

    assert notifier.notifications == []                 # 不进摘要队列
    assert len(trigger_repo.rows) == 1                  # 但仍落库（账不丢）
    row = trigger_repo.rows[0]
    assert row.suppressed is True
    assert row.disposition == "auto_observed"           # 归档类处置
    assert row.notified is False
    assert "抑噪期" in row.disposition_reason
    assert "修规则待办" in row.disposition_reason
    assert len(events) == 1
    assert events[0]["suppressed"] is True and events[0]["notified"] is False
    assert events[0]["disposition"] == "auto_observed"
    assert events[0]["disposition_reason"] == SUPPRESSED_TRIGGER_REASON

    # 闩锁仍生效：同引擎再 tick 不重复落库（不逐条灌数据）
    assert engine.tick() == []
    assert len(trigger_repo.rows) == 1


def test_engine_suppression_expired_behaves_normally():
    """抑噪到期（suppress_until 已过）→ 恢复原级别：通知照发、suppressed=false"""
    trigger_repo = _RecordingTriggerRepo()
    notifier = _EngineNotifier(trigger_repo)
    rule = _engine_rule(noise_state="suppressed",
                        suppress_until=_ENGINE_NOW - timedelta(seconds=1))
    events = _engine([rule], {"600150.SH": 101.0}, notifier).tick()

    assert notifier.notifications == [(1, "price_break")]
    assert len(trigger_repo.rows) == 1
    assert trigger_repo.rows[0].suppressed is False
    assert "suppressed" not in events[0]


def test_engine_rule_without_noise_state_unchanged():
    """无抑噪态（noise_state=None）→ 行为与改造前完全一致"""
    trigger_repo = _RecordingTriggerRepo()
    notifier = _EngineNotifier(trigger_repo)
    events = _engine([_engine_rule()], {"600150.SH": 101.0}, notifier).tick()

    assert notifier.notifications == [(1, "price_break")]
    assert trigger_repo.rows[0].suppressed is False
    assert "suppressed" not in events[0]


def test_real_db_engine_archives_suppressed_trigger_without_new_todo(watch_tables):
    """真库端到端：抑噪期规则触发 → suppressed=true 归档；修规则待办不因触发变多"""
    import psycopg2

    from adapters.outbound.repositories.watch_rule_repository import (
        WatchRuleRepository, WatchTriggerRepository,
    )

    _db_cleanup()
    _seed_db_rule(trigger_count=8, conditions_json=(
        '[{"type": "price_break", "params": {"direction": "above", "price": 1.0}}]'))
    try:
        # ① 自愈 scan：置抑噪态 + 建 1 条「修规则」待办
        _real_service().scan(now=datetime.now())
        # 固定 now_fn 所需：把抑噪截止钉到可复现的时刻（不依赖系统时钟）
        _set_suppress_until(_DB_RULE_ID, _ENGINE_NOW + timedelta(hours=1))

        # ② 引擎在抑噪期 tick：只归档，不进摘要队列
        trigger_repo = WatchTriggerRepository()
        notifier = _EngineNotifier(trigger_repo)
        engine = WatchEngine(rule_repo=WatchRuleRepository(),
                             quote_service=_EngineQuoteService({_DB_SYMBOL: 10.0}),
                             notifier=notifier, now_fn=lambda: _ENGINE_NOW)
        events = engine.tick()
        mine = [e for e in events if e["rule_id"] == _DB_RULE_ID]
        assert notifier.notifications == [], notifier.notifications
        assert len(mine) == 1 and mine[0]["suppressed"] is True, events

        # ③ DB 事实：触发 suppressed=true / auto_observed；待办仍只有 scan 那一条
        conn = psycopg2.connect(_dsn())
        try:
            cur = conn.cursor()
            cur.execute("SELECT suppressed, disposition, disposition_reason, notified "
                        "FROM quant.watch_triggers WHERE rule_id = %s ORDER BY id DESC LIMIT 1",
                        (_DB_RULE_ID,))
            suppressed, disposition, reason, notified = cur.fetchone()
            assert suppressed is True
            assert disposition == "auto_observed"
            assert "抑噪期" in reason and "修规则待办" in reason
            assert notified is False
            cur.execute("SELECT count(*) FROM quant.watch_todos WHERE rule_id = %s",
                        (_DB_RULE_ID,))
            assert cur.fetchone()[0] == 1, "抑噪期触发不得再建待办（只有自愈那条修规则待办）"

            # ④ 非抑噪期行为不变：默认 suppressed=False（列默认与形参默认一致）
            WatchTriggerRepository().record(
                rule_id=_DB_RULE_ID, symbol=_DB_SYMBOL,
                condition={"type": "price_break"}, trigger_price=10.0,
                disposition="pending", disposition_reason="回归用")
            cur.execute("SELECT suppressed FROM quant.watch_triggers WHERE rule_id = %s "
                        "ORDER BY id DESC LIMIT 1", (_DB_RULE_ID,))
            assert cur.fetchone()[0] is False
        finally:
            conn.close()
    finally:
        _db_cleanup()

