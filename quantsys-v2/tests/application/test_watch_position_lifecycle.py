"""持仓生命周期联动单测（REQ-f08def P5，RFC 014 v3 §2.3，w-c8cae280）"""
from datetime import datetime
from types import SimpleNamespace

from application.services.watch_engine.position_lifecycle_service import (
    PositionLifecycleService, stop_loss_pct,
)


class FakeRuleRepo:
    def __init__(self, rules):
        self._rules = list(rules)
        self.updates = []
        self.created = []

    def list_enabled(self):
        return [r for r in self._rules if r.enabled]

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))
        for r in self._rules:
            if r.id == rule_id:
                for k, v in fields.items():
                    setattr(r, k, v)
        return None

    def create_rule(self, symbol, conditions, context=None, cost_price=None,
                    active_window=None, expires_at=None, created_by="agent", account=None):
        r = _rule(rid=900 + len(self.created), symbol=symbol, intent=None)
        r.conditions = conditions
        r.cost_price = cost_price
        r.account = account
        r.context = context
        self.created.append(r)
        self._rules.append(r)
        return r


class FakePosRepo:
    def __init__(self, positions):
        self._p = positions

    def get_all_positions(self, account):
        return [SimpleNamespace(symbol=s, shares_total=v["shares"], avg_cost=v["avg_cost"],
                                market_value=v.get("market_value", 0))
                for s, v in self._p.items() if v.get("account", account) == account]


def _rule(rid=1, symbol="600150", intent="entry", enabled=True, account=None):
    return SimpleNamespace(id=rid, symbol=symbol, intent=intent, enabled=enabled,
                           account=account, context="原预案", cost_price=10.0,
                           conditions=[], lifecycle_stage="tracking")


def test_stop_loss_pct_by_board():
    assert stop_loss_pct("300750") == 0.10
    assert stop_loss_pct("688981") == 0.10
    assert stop_loss_pct("600150") == 0.08


def test_entry_rule_preserved_after_buy_but_stop_loss_created():
    """已持仓时：**不退役**等买规则（可能尚未执行的加仓计划），但必须补挂止损 + 阶段推进

    2026-09-11 教训：原实现"持仓已有 → 等买规则退役"会毁掉有效计划——伊利 #95
    （突破27+放量买入）从未触发过，只因该标的已有持仓就被退役。规则使命是否结束是
    投资判断，属 agent 终判（RFC 014 v3 §2.1/§3.4），机器只做安全网与状态标注。
    """
    rules = FakeRuleRepo([_rule(rid=1, symbol="600150", intent="entry")])
    svc = PositionLifecycleService(rules, FakePosRepo({"600150": {"shares": 100, "avg_cost": 10.0,
                                                       "market_value": 1000}}))
    out = svc.reconcile(datetime(2026, 9, 11, 16, 0))
    assert out["retired"] == 0, "不得自动退役可能仍有效的等买计划"
    assert out["created"] == 1, "必须补挂止损（宪法要求持仓有止损盯盘）"
    assert out["promoted"] == 1, "阶段应推进到 holding"
    stop = rules.created[0]
    assert stop.conditions[0]["params"]["price"] == 9.2   # 10.0 × (1-8%)
    assert stop.conditions[0]["params"]["direction"] == "below"
    assert rules.list_enabled()[0].enabled is True, "原等买规则必须仍然启用"


class RaisingPosRepo:
    def get_all_positions(self, account):
        raise RuntimeError("模拟持仓源故障（字段名不符/连接失败）")


def test_fail_closed_when_position_read_fails():
    """持仓读不到时必须 fail-closed：绝不退役任何规则（否则等于亲手拆掉止损保护）"""
    rules = FakeRuleRepo([_rule(rid=3, symbol="600489", intent="exit_stop", account="agent_virtual")])
    svc = PositionLifecycleService(rules, RaisingPosRepo())
    out = svc.reconcile()
    assert out["skipped"].startswith("持仓读取失败")
    assert out["retired"] == 0 and out["created"] == 0
    assert rules.list_enabled()[0].enabled is True, "fail-closed 下止损规则必须保持启用"


def test_no_duplicate_stop_loss_when_exists():
    rules = FakeRuleRepo([
        _rule(rid=1, symbol="600150", intent="entry"),
        _rule(rid=2, symbol="600150", intent="exit_stop"),
    ])
    svc = PositionLifecycleService(rules, FakePosRepo({"600150": {"shares": 100, "avg_cost": 10.0}}))
    out = svc.reconcile()
    assert out["created"] == 0


def test_exit_rules_retire_after_position_closed():
    """清仓完成 → 卖出规则族收摊（有归属账户的才收，通用观察保留）"""
    rules = FakeRuleRepo([
        _rule(rid=3, symbol="600489", intent="exit_stop", account="agent_virtual"),
        _rule(rid=4, symbol="600489", intent="exit_take_profit", account=None),
    ])
    svc = PositionLifecycleService(rules, FakePosRepo({}))
    out = svc.reconcile()
    assert out["retired"] == 1
    retired_ids = [d["rule_id"] for d in out["retired_details"]]
    assert retired_ids == [3]


def test_entry_rule_kept_when_not_bought():
    """还没买 → 等买规则必须保留（不能因为没持仓就收摊）"""
    rules = FakeRuleRepo([_rule(rid=5, symbol="600737", intent="entry")])
    svc = PositionLifecycleService(rules, FakePosRepo({}))
    out = svc.reconcile()
    assert out["retired"] == 0 and out["created"] == 0
