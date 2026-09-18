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
    WatchRuleRepository, WatchTriggerRepository,
)
from application.services.agent_notification_service import AgentNotificationService
from application.services.watch_engine.digest_service import WatchDigestService
from application.services.watch_engine.factory import create_watch_engine

SYMBOL = "600887"          # 伊利：agent_virtual 持仓标的（止损伤痕真实存在）
ACCOUNT = "agent_virtual"
TRIGGER_PRICE = 24.00      # 明显低于建仓成本，确保命中

# 本模块用真库 + 真引擎：测试库里的**残留** 600887 规则/触发会与本次新建规则竞争
# 同一去重键（(600887, below)）——list_enabled() 无 ORDER BY，谁先被处理取决于物理
# 行序，于是同一命令逐轮漂移（实测 deduped + dup_of=673）。因此：
#   · serial 标记 + 结构固化 + 协作进程串行锁（REQ-c9f899 返工 D）；
#   · setup/teardown 里对本标的清场（_purge_watch_symbol_state），使结果只取决于本次数据。
pytestmark = [
    pytest.mark.serial,
    pytest.mark.usefixtures("db_schema_synced", "watch_db_advisory_lock"),
]


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


def _purge_watch_symbol_state(symbol: str) -> None:
    """清掉某标的的全部盯盘状态，让 e2e 只依赖本次数据、不依赖库内残留。

    清场对象（存在即删；表缺失则跳过——结构由 session 级 db_schema_synced 保证）：
      watch_receipts / watch_todos / watch_rule_changes / watch_runtime_state
      / watch_runtime_dedup / watch_trigger_events / watch_price_history
      / watch_triggers / watch_rules

    为什么按 symbol 而不是只删本次 rule.id：去重键 = (归一化标的, 方向)，跨规则共享；
    残留的同标的同向规则会先把键标记为"窗内已通知"，使本次新建规则被合并
    （disposition=deduped、notified=False），断言随之抖动。
    """
    from sqlalchemy import text

    from infrastructure.persistence.orm import get_session

    session = get_session()
    session.rollback()
    like = symbol + '%'

    def _table_exists(name: str) -> bool:
        return bool(session.execute(
            text("SELECT to_regclass(:n)"), {'n': 'quant.' + name}).scalar())

    rule_ids = [r[0] for r in session.execute(
        text("SELECT id FROM quant.watch_rules WHERE symbol LIKE :s"),
        {'s': like}).fetchall()]

    if _table_exists('watch_receipts') and _table_exists('watch_todos'):
        session.execute(text(
            "DELETE FROM quant.watch_receipts WHERE todo_id IN ("
            "SELECT id FROM quant.watch_todos WHERE symbol LIKE :s)"), {'s': like})
    if _table_exists('watch_todos'):
        if rule_ids:
            session.execute(text(
                "DELETE FROM quant.watch_todos WHERE symbol LIKE :s OR rule_id = ANY(:i)"),
                {'s': like, 'i': rule_ids})
        else:
            session.execute(text(
                "DELETE FROM quant.watch_todos WHERE symbol LIKE :s"), {'s': like})
    if rule_ids and _table_exists('watch_rule_changes'):
        session.execute(text(
            "DELETE FROM quant.watch_rule_changes WHERE rule_id = ANY(:i)"),
            {'i': rule_ids})
    if rule_ids and _table_exists('watch_runtime_state'):
        session.execute(text(
            "DELETE FROM quant.watch_runtime_state WHERE rule_id = ANY(:i)"),
            {'i': rule_ids})
    for table in ('watch_runtime_dedup', 'watch_trigger_events', 'watch_price_history'):
        if _table_exists(table):
            session.execute(
                text("DELETE FROM quant.%s WHERE symbol LIKE :s" % table), {'s': like})
    session.execute(text("DELETE FROM quant.watch_triggers WHERE symbol LIKE :s"), {'s': like})
    session.execute(text("DELETE FROM quant.watch_rules WHERE symbol LIKE :s"), {'s': like})
    session.commit()


@pytest.fixture
def rule_id():
    # 清场：移除残留的 600887 规则/触发/运行态，保证去重窗、闩锁、冷却都从零开始
    _purge_watch_symbol_state(SYMBOL)
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
    # 收场：本次产生的触发/待办/运行态连同规则一并清掉（失败不掩盖用例结论）
    try:
        _purge_watch_symbol_state(SYMBOL)
    except Exception:
        pass


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
    # 强化（返工 D）：断言本规则的触发确实进了该账户段——原断言的结尾是恒真的 or True，
    # 证伪不了"段内容来自残留数据"。
    assert ("规则%s" % rule_id) in seg[ACCOUNT]["text"], (
        "该账户摘要段未含本规则 #%s：%s" % (rule_id, seg[ACCOUNT]["text"]))

    res = svc.maybe_wake(now=datetime(2026, 9, 11, 10, 0))
    wakes = [c for c in captured if c["url"].endswith("/wake")]
    assert wakes, "摘要门没有唤醒任何 agent：%s" % res
    # 只认**本账户**的唤醒：投送按账户一账户一份，wakes[-1] 可能是其它账户/未归属桶，
    # 取末条会随残留数据抖动（flake 源之一）。
    acct_wakes = [c for c in wakes
                  if c["json"]["data"].get("account_name") == ACCOUNT]
    assert acct_wakes, "未按账户 %s 投送唤醒：%s" % (ACCOUNT, res)
    payload = acct_wakes[-1]["json"]["data"]
    assert payload["autonomy"] == "autonomous"      # agent 自有账户 → 可自主操作
    assert "autonomous" in payload["instruction"] or "自主操作" in payload["instruction"]
    assert payload["target_agent"] == "agent-dh"    # 投送目标（与消息频道解耦）
