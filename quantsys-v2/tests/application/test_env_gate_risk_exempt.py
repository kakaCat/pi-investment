"""环境闸「止损/保护线」豁免（用户 2026-10-20 裁定）

裁定原文：环境不达标时 **exit_stop/保护线类信号照常通知**，其余个股信号仍只归档。

验收口径（与任务卡逐条对应）：
  0. 豁免用例覆盖：exit_stop/保护线信号照常通知；非止损个股信号仍静音归档；
  1. 豁免不破坏原有语义：symbol 级普通 exit_stop 告警、止盈/观察规则在环境日
     仍走「只记录不动作」；既有场景矩阵 B7 口径原样保留（回归由矩阵文件守护）；
  2. 判定依据**规则动作类型 + 结构化锚点**，不解析消息文案：
       · 动作类型 = disposition.CONSTITUTIONAL_INTENTS（intent 缺省时经 intent_of
         按 action_on_trigger 归一，如 sell + pnl_pct below → exit_stop）；
       · 保护线锚点 = scope=position / lifecycle_stage=holding / cost_price /
         触发条件为下行保护阈值（price_break|ma_break|pnl_pct 且 direction=below）；
     豁免理由写进事件（env_gate_exempt / env_gate_exempt_reason）与日志，可追溯。

叠加语义：豁免只跳过**全局环境闸**这一道。规则自己的 per-rule market_gate
（加严项）仍可拦截；日上限依旧对宪法级意图豁免；抑噪/去重/处置链原样执行。

测试用假件只替换出口与取数（notifier / quote / state_provider），判定与流水线
全部走生产代码。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.engine import (
    ENV_GATE_EXEMPT_REASON,
    WatchEngine,
)
from qs_watch.domain.watch.models import MarketState

NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内（与场景矩阵同一基准）
BLOCKED_REASON_PREFIX = '环境闸拦截：'


# ── 假件 ────────────────────────────────────────────────────
class _RuleRepo:
    def __init__(self, rules):
        self._rules = list(rules)
        self.updates = []

    def list_enabled(self):
        return list(self._rules)

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))


class _QuoteService:
    def __init__(self, prices, prev_close=102.0):
        self.prices = dict(prices)
        self.prev_close = prev_close

    def get_realtime_quote(self, symbol):
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price,
                               prev_close=self.prev_close,
                               volume=1_000_000, change_pct=None)


class _TriggerRepo:
    """_record_suppressed_trigger 的归档口。"""

    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
        self.rows.append(row)
        return row


class _Notifier:
    """三条出口分开计数：notify=真通知，record_only=市场门归档，record=suppressed 归档。"""

    def __init__(self):
        self.trigger_repo = _TriggerRepo()
        self.notifications = []
        self.record_only_calls = []
        self.governance_calls = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append({'rule_id': rule.id, 'kwargs': kwargs})
        return SimpleNamespace(id=100 + len(self.notifications), notified=True,
                               todo_id=None)

    def record_only(self, rule, condition, quote, result,
                    disposition=None, disposition_reason=None):
        self.record_only_calls.append({'rule_id': rule.id,
                                       'reason': disposition_reason})
        return SimpleNamespace(id=200 + len(self.record_only_calls), notified=False)

    def record_governance(self, rule, reason, detail=None):
        self.governance_calls.append({'rule_id': rule.id, 'reason': reason})


class _StateProvider:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def get_state(self):
        self.calls += 1
        return self.state


class _MarketWatchSvc:
    """引擎侧只用 state_provider；市场级扫描返回空清单。"""

    def __init__(self, state):
        self.state_provider = _StateProvider(state)

    def scan_market_rules(self, now):
        return {'scanned': 0, 'triggered': 0, 'skipped_no_data': 0, 'evaluated': []}


# ── 快照 / 规则工厂 ─────────────────────────────────────────
def _blocked_state():
    """三维同时命中：指数暴跌 + 板块无主线 + 资金偏冷。"""
    return MarketState(
        indices={'000300.SH': {'change_pct': -1.80}},
        sectors={'银行': 0.30, '农林牧渔': -1.20},
        sentiment_score=18.0, advance_decline_ratio=0.30, degraded=[])


def _ok_state():
    return MarketState(
        indices={'000300.SH': {'change_pct': 0.60}},
        sectors={'半导体': 2.40, '银行': 0.30},
        sentiment_score=58.0, advance_decline_ratio=1.30, degraded=[])


def _down_break_cond(price=100.0):
    """下行破位（保护线形态）：现价 99 下破 100，昨收 102 在触发侧之上 = 今日新穿。"""
    return {'type': 'price_break',
            'params': {'direction': 'below', 'price': price}}


def _up_break_cond(price=100.0):
    """上行突破——场景矩阵 make_rule 的默认形态，不是保护线。"""
    return {'type': 'price_break',
            'params': {'direction': 'above', 'price': price}}


def _rule(id=1, symbol='600519.SH', *, intent='exit_stop', scope='position',
          lifecycle_stage='holding', cost_price=95.0, conditions=None,
          action_hint=None, action_params=None, context=None):
    return SimpleNamespace(
        id=id, symbol=symbol, scope=scope,
        conditions=conditions or [_down_break_cond()],
        cost_price=cost_price, active_window=None,
        intent=intent,
        action_hint=action_hint or {'trigger_level': 'L2',
                                    'action_on_trigger': 'sell'},
        escalation_policy=None,
        linked_account='agent_virtual' if scope == 'position' else None,
        account='agent_virtual',
        lifecycle_stage=lifecycle_stage,
        created_from=('position_lifecycle:%s' % symbol
                      if scope == 'position' else None),
        next_action_hint=None, target=None, review_interval_days=None,
        review_due_at=None, enabled=True, action_params=action_params,
        ops_notes=None, noise_state=None, suppress_until=None, context=context,
    )


def _engine(rules, prices, notifier, state=None, *, prev_close=102.0, **kw):
    return WatchEngine(
        rule_repo=_RuleRepo(rules),
        quote_service=_QuoteService(prices, prev_close=prev_close),
        notifier=notifier,
        now_fn=lambda: NOW,
        market_watch_service=_MarketWatchSvc(state or _blocked_state()),
        **kw,
    )


# ── 0. 豁免：止损/保护线信号照常通知 ────────────────────────
def test_position_stop_loss_notifies_despite_blocked_environment():
    """持仓保护线（scope=position、成本锚定）在环境日**照常通知**，不进归档口。"""
    notifier = _Notifier()
    rule = _rule()
    engine = _engine([rule], {'600519.SH': 99.0}, notifier)

    events = engine.tick()

    assert len(notifier.notifications) == 1, '环境日把止损信号静音了'
    assert notifier.trigger_repo.rows == [], '通知信号不得再落 suppressed 归档'
    assert notifier.record_only_calls == []
    assert len(events) == 1
    ev = events[0]
    assert ev['notified'] is True
    # 豁免理由可追溯：动作类型 + 结构锚点都写进事件
    assert ev['env_gate_exempt'] is True
    assert ev['env_gate_exempt_reason'].startswith(ENV_GATE_EXEMPT_REASON)
    assert 'intent=exit_stop' in ev['env_gate_exempt_reason']
    assert '锚点=scope=position' in ev['env_gate_exempt_reason']
    # 照常通知 = 占日配额（与「环境闸拦截不占配额」形成可证伪对照）
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}


def test_symbol_scope_stop_with_cost_price_is_exempt():
    """symbol 级规则只要有成本锚点，同样是保护线 → 豁免。"""
    notifier = _Notifier()
    rule = _rule(scope='symbol', lifecycle_stage='watching', cost_price=95.0,
                 conditions=[_down_break_cond()])
    engine = _engine([rule], {'600519.SH': 99.0}, notifier)

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert notifier.trigger_repo.rows == []
    assert '锚点=cost_price' in events[0]['env_gate_exempt_reason']


def test_downside_protective_condition_is_exempt_without_position_or_cost():
    """无持仓/成本，但触发条件本身是下行保护阈值（below）→ 保护线 → 豁免。"""
    notifier = _Notifier()
    rule = _rule(scope='symbol', lifecycle_stage='watching', cost_price=None,
                 conditions=[_down_break_cond()])
    engine = _engine([rule], {'600519.SH': 99.0}, notifier)

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert '锚点=condition:price_break:below' in (
        events[0]['env_gate_exempt_reason'])


def test_action_type_normalized_from_action_hint_sell_pnl_pct_below():
    """intent 缺省时按动作类型归一：sell + pnl_pct below → exit_stop → 豁免。

    证明判据消费的是规则声明的动作类型（intent_of 单一事实源），而不是某个
    单字段恰好写着 exit_stop。
    """
    notifier = _Notifier()
    cond = {'type': 'pnl_pct',
            'params': {'direction': 'below', 'pct': -8.0}}
    rule = _rule(intent='', scope='symbol', lifecycle_stage='watching',
                 cost_price=95.0, conditions=[cond],
                 action_hint={'action_on_trigger': 'sell'})
    # 95 成本、现价 87 → 浮亏 -8.42% 触发
    engine = _engine([rule], {'600519.SH': 87.0}, notifier, prev_close=87.5)

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert 'intent=exit_stop' in events[0]['env_gate_exempt_reason']


# ── 1. 非止损：仍只归档不动作（豁免没有扩大成「全部放行」） ──
def test_non_stop_signal_still_archived_in_blocked_environment():
    notifier = _Notifier()
    rule = _rule(intent='trend_observe', scope='symbol',
                 lifecycle_stage='watching', cost_price=None,
                 conditions=[_up_break_cond()],
                 action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'})
    engine = _engine([rule], {'600519.SH': 101.0}, notifier, prev_close=98.0)

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1, '非止损信号必须只归档一条'
    row = notifier.trigger_repo.rows[0]
    assert row.suppressed is True and row.notified is False
    assert str(row.disposition_reason).startswith(BLOCKED_REASON_PREFIX)
    ev = events[0]
    assert ev['notified'] is False and ev['suppressed'] is True
    assert 'env_gate_exempt' not in ev
    assert engine.state.daily_emit_counts == {}, '归档不得占日通知配额'


def test_position_take_profit_still_archived_even_with_holding_anchor():
    """保护线锚点不是万能通行证：position+holding 的止盈规则仍只归档。"""
    notifier = _Notifier()
    rule = _rule(intent='exit_take_profit', scope='position',
                 lifecycle_stage='holding', cost_price=95.0,
                 conditions=[{'type': 'price_break',
                              'params': {'direction': 'above', 'price': 110.0}}],
                 action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'})
    engine = _engine([rule], {'600519.SH': 111.0}, notifier, prev_close=105.0)

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1
    assert 'env_gate_exempt' not in events[0]


def test_symbol_exit_stop_without_protection_anchor_still_archived():
    """场景矩阵 B7 口径原样保留：symbol 级、无成本/持仓/下行阈值的 exit_stop
    告警（如价格上破提醒）不是保护线 → 环境日仍只归档。

    这是「豁免不破坏原有语义」的边界回归；B7 本身由场景矩阵文件守护。
    """
    notifier = _Notifier()
    rule = _rule(scope='symbol', lifecycle_stage='watching', cost_price=None,
                 conditions=[_up_break_cond()])
    engine = _engine([rule], {'600519.SH': 101.0}, notifier, prev_close=98.0)

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1
    assert 'env_gate_exempt' not in events[0]


# ── 2. 判定依据：动作类型 + 结构锚点，不猜文案 ───────────────
def test_exemption_ignores_message_text():
    """文案里写满「止损/保护线/清仓」也不是判据；动作类型不是 exit_stop 就不豁免。"""
    notifier = _Notifier()
    rule = _rule(intent='trend_observe', scope='symbol',
                 lifecycle_stage='watching', cost_price=None,
                 conditions=[_up_break_cond()],
                 action_hint={'action_on_trigger': 'observe'},
                 context='止损 保护线 清仓 立即卖出（这是文案，不是动作类型）')
    engine = _engine([rule], {'600519.SH': 101.0}, notifier, prev_close=98.0)

    exempt, reason = engine._env_gate_exemption(rule, rule.conditions[0])

    assert exempt is False and reason == ''
    engine.tick()
    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1


def test_exemption_anchor_matrix_is_structural():
    """锚点判定表：结构字段命中即保护线；只看 params.direction，不读文案。"""
    engine = _engine([], {}, _Notifier())
    base = dict(intent='exit_stop', cost_price=None, conditions=[])

    def make(**kw):
        data = dict(id=1, symbol='600519.SH', scope='symbol',
                    lifecycle_stage='watching', action_hint={}, context=None,
                    action_params=None)
        data.update(base)
        data.update(kw)
        return SimpleNamespace(**data)

    assert engine._protection_line_anchor(
        make(scope='position'), _down_break_cond()) == 'scope=position'
    assert engine._protection_line_anchor(
        make(lifecycle_stage='holding'), _down_break_cond()) == (
            'lifecycle_stage=holding')
    assert engine._protection_line_anchor(
        make(cost_price=95.0), _down_break_cond()) == 'cost_price'
    assert engine._protection_line_anchor(
        make(action_hint={'stop_loss': 95.0}), _up_break_cond()) == (
            'action_hint.stop_loss')
    assert engine._protection_line_anchor(
        make(), _down_break_cond()) == 'condition:price_break:below'
    assert engine._protection_line_anchor(
        make(), _up_break_cond()) == ''
    assert engine._protection_line_anchor(
        make(), {'type': 'pnl_pct',
                 'params': {'direction': 'above', 'pct': 15.0}}) == ''
    assert engine._protection_line_anchor(
        make(context='止损 保护线'), _up_break_cond()) == ''


def test_reason_is_traceable_and_uses_action_type_single_source():
    """豁免理由必须同时给出动作类型与锚点，复盘能回答「凭什么放行」。"""
    notifier = _Notifier()
    rule = _rule()
    engine = _engine([rule], {'600519.SH': 99.0}, notifier)

    exempt, reason = engine._env_gate_exemption(rule, rule.conditions[0])

    assert exempt is True
    assert reason.startswith(ENV_GATE_EXEMPT_REASON)
    assert 'intent=exit_stop' in reason
    assert '锚点=scope=position' in reason


# ── 3. 叠加语义：豁免只跳过全局闸，其余门照旧 ──────────────
def test_exempt_stop_still_blocked_by_stricter_per_rule_market_gate():
    """全局环境闸豁免 ≠ 全部放行：规则自己的 market_gate 更严时仍只归档。

    叠加语义：环境闸先豁免放行（事件带豁免溯源），per-rule 加严项随后拦截
    （record_only 归档 + 日计数照常）；两者不重复落归档行。
    """
    notifier = _Notifier()
    rule = _rule(action_params={'market_gate': {
        'index': '000300.SH', 'max_down_pct': -1.5}})
    engine = _engine([rule], {'600519.SH': 99.0}, notifier)

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.record_only_calls) == 1
    assert str(notifier.record_only_calls[0]['reason']).startswith('市场门拦截：')
    assert notifier.trigger_repo.rows == []      # 不走 suppressed 归档双通道
    ev = events[0]
    assert ev['notified'] is False
    assert ev['env_gate_exempt'] is True, '应保留「全局闸已豁免」的溯源'
    # 市场门是加严项，日计数照常（既有语义）
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}


def test_constitutional_stop_not_capped_by_daily_emit_limit():
    """日上限对宪法级意图的既有豁免不变：豁免信号照常通知，不被上限吞掉。"""
    notifier = _Notifier()
    rule = _rule()
    engine = _engine([rule], {'600519.SH': 99.0}, notifier)
    # 手工把该规则该条件当日计数顶到上限
    from qs_watch.application.services.watch_engine.conditions import (
        DEFAULT_DAILY_EMIT_CAP,
    )
    engine.state.daily_emit_counts[(1, 0)] = (NOW.date(), DEFAULT_DAILY_EMIT_CAP)

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert events[0]['notified'] is True


def test_exemption_only_applies_on_blocked_environment_days():
    """环境正常日不发生「豁免」：事件不带豁免溯源，避免口径混淆。"""
    notifier = _Notifier()
    rule = _rule()
    engine = _engine([rule], {'600519.SH': 99.0}, notifier, _ok_state())

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert 'env_gate_exempt' not in events[0]
