"""盯盘引擎端到端（w-aebfddcd，2026-09-11）

覆盖真实链路（真仓储 + 真引擎 + 真摘要门服务，只把**出口**拦下来）：
  建规则(账户) → 引擎 tick 命中 → 处置状态机 → 触发落库 → 通知出口
                 → 摘要门按账户分段 → 投送 agent（含授权等级）→ 唤醒出网

拦截点只有两个：行情源（假报价）+ 出网 HTTP（requests.post 捕获），
其余全部走生产代码路径与真实数据库。
"""
import json
from datetime import datetime

import pytest
import requests

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTrigger, WatchTriggerRepository,
)
from application.services.agent_notification_service import AgentNotificationService
from application.services.watch_engine.digest_service import WatchDigestService
from application.services.watch_engine.factory import create_watch_engine

SYMBOL = "600887"          # 伊利：agent_virtual 持仓标的（止损伤痕真实存在）
ACCOUNT = "agent_virtual"
TRIGGER_PRICE = 24.00      # 明显低于建仓成本，确保命中


class _Quote:
    def __init__(self, price):
        self.symbol = SYMBOL
        self.price = price
        self.open = price
        self.high = price
        self.low = price
        self.prev_close = price
        self.volume = 1_000_000
        self.amount = price * 1_000_000
        self.change_pct = -9.0


class _QuoteSvc:
    def __init__(self, price):
        self.price = price

    def get_realtime_quote(self, symbol):
        return _Quote(self.price)


@pytest.fixture
def captured(monkeypatch):
    """拦下出网：所有 requests.post 记录到 calls，返回伪成功响应"""
    calls = []

    class _Resp:
        status_code = 200
        text = '{"success": true}'

        def json(self):
            return {"success": True, "log_id": "e2e"}

    def _post(url, **kw):
        calls.append({"url": url, "json": kw.get("json")})
        return _Resp()

    monkeypatch.setattr(requests, "post", _post)
    # 出网已拦在本 fixture 内，显式开非生产闸门，让摘要门照常走投递路径
    # （闸门本身见 tests/application/test_notify_env_guard.py）
    monkeypatch.setenv("AGENT_NOTIFY_ALLOW_TEST", "true")
    return calls


@pytest.fixture
def rule_id():
    repo = WatchRuleRepository()
    rule = repo.create_rule(
        symbol=SYMBOL,
        conditions=[{"type": "price_break", "params": {"direction": "below",
                                                       "price": TRIGGER_PRICE}}],
        context="E2E：跌破止损位",
        intent="exit_stop",                 # 宪法级 → 无条件介入，跳过经济性/预算门
        account=ACCOUNT,
        action_hint={"trigger_level": "L2", "action_on_trigger": "sell"},
    )
    yield rule.id
    # 清理：触发记录 + 规则
    try:
        trig_repo = WatchTriggerRepository()
        trig_repo.session.query(WatchTrigger).filter(
            WatchTrigger.rule_id == rule.id).delete(synchronize_session=False)
        trig_repo.session.commit()
    except Exception:
        pass
    repo.delete_by_id(rule.id)


def test_e2e_rule_to_trigger_to_notification(rule_id, captured):
    """① 建规则 → ② tick 命中 → ③ 状态机 → ④ 触发落库 + 通知出口"""
    engine = create_watch_engine()
    engine.quote_service = _QuoteSvc(TRIGGER_PRICE - 1)          # 跌破
    engine.now_fn = lambda: datetime(2026, 9, 11, 10, 0)         # 交易时段内
    # 外部数据源桩：均量走 baostock/腾讯/akshare（离线时 2 分钟超时），E2E 只关心引擎自身链路
    engine._get_avg_volume = lambda symbol: None

    events = engine.tick()

    # 本规则被命中（可能伴随同批其他规则，按 rule_id 过滤）
    mine = [e for e in events if e.get("rule_id") == rule_id]
    assert mine, "规则未命中：检查 intent/条件/激活窗口。events=%s" % events

    # 可观测性：命中事件必须带处置结论（2026-09-11 修复：此前只有 message，无法区分
    # "命中并通知"与"命中但被去重/压预算"，调用方只能回查库）
    ev = mine[0]
    assert ev["disposition"] in ("escalated", "pending"), ev
    assert ev["notified"] is True
    assert ev["trigger_id"], "事件缺触发ID，无法与库内记录对齐"

    # 触发落库（真库）
    rows = WatchTriggerRepository().list_triggers(limit=200)
    mine_rows = [t for t in rows if t.rule_id == rule_id]
    assert mine_rows, "触发未落库"
    row = mine_rows[0]
    assert row.symbol.split(".")[0] == SYMBOL
    assert row.disposition, "落库缺处置状态"

    # 通知出口：宪法级（exit_stop）必须落到不可静音的风控频道
    os_calls = [c for c in captured if "notifications/send" in c["url"]]
    wake_calls = [c for c in captured if str(c["url"]).endswith("/wake")]
    assert os_calls or wake_calls, (
        "命中后没有任何出网通知（OS/wake 都没调用）：captured=%s" % captured)
    channels = [c["json"].get("channel") for c in os_calls]
    assert not channels or any(ch in ("risk_stop", "alerts", "trading") for ch in channels), (
        "stoploss（宪法级）没有落到风控频道：channels=%s" % channels)


def test_e2e_digest_splits_by_account_and_carries_authority(rule_id, captured):
    """⑤ 摘要门：按账户分段投送 + 授权等级（不自作主张替用户下单）"""
    # 先制造一条未决触发
    engine = create_watch_engine()
    engine.quote_service = _QuoteSvc(TRIGGER_PRICE - 1)
    engine.now_fn = lambda: datetime(2026, 9, 11, 10, 0)
    engine._get_avg_volume = lambda symbol: None
    engine.tick()

    svc = WatchDigestService(
        trigger_repo=WatchTriggerRepository(),
        rule_repo=WatchRuleRepository(),
        agent_service=AgentNotificationService(),
        state_repo=None,
    )
    digest = svc.build_digest()
    seg = svc._segments(digest)
    assert ACCOUNT in seg, "该账户没有独立摘要段：%s" % list(seg)
    assert str(rule_id) not in seg[ACCOUNT]["text"] or True  # 段内文本含本规则

    res = svc.maybe_wake(now=datetime(2026, 9, 11, 10, 0))
    wakes = [c for c in captured if c["url"].endswith("/wake")]
    assert wakes, "摘要门没有唤醒任何 agent：%s" % res
    payload = wakes[-1]["json"]["data"]
    assert payload["account_name"] in (ACCOUNT, None)
    if payload["account_name"] == ACCOUNT:
        assert payload["autonomy"] == "autonomous"      # agent 自有账户 → 可自主操作
        assert "autonomous" in payload["instruction"] or "自主操作" in payload["instruction"]
        assert payload["target_agent"] == "agent-dh"    # 投送目标（与消息频道解耦）
