"""机会闭环三条新链路端到端场景（opp-loop-e2e，2026-10-20）

本文件是 `tests/scenarios` 场景矩阵的续篇，只回答「这条链路到底走不走得通」：

  E1 全局环境闸（engine-global-gate + env-gate-risk-exempt 的**最终语义**）
     · 环境不达标 → 个股信号只归档（suppressed）、不通知、不占日配额；
     · 止损/保护线（动作类型 + 结构化锚点）→ **豁免照常通知**；
     · 豁免只跳过全局环境闸：非保护线 exit_stop 仍归档，规则自己的
       per-rule market_gate 仍可加严拦截。
  E2 假信号归档（confirm-verify-pipeline）
     · staged_break 确认成立后核验未通过 → 只归档假信号样本，不通知/不建待办；
     · 核验全过 → 照常通知（同一套假件下的可证伪对照）。
  E3 板块共振加权（sector-resonance → confirm-verify 的 resonance 阶段）
     · 孤立异动 = 不按板块共振加权 → 判假信号归档；
     · 共振成立 → 放行通知；
     · 映射/行情缺失 → skipped fail-open：不拿「没数据」当「孤立异动」。

风格与 `test_watch_scenario_matrix.py` 一致：假件只替换**出口与取数**
（notifier / quote / state_provider / 新闻 / 盘口 / 板块数据源），判定与
流水线全部走生产代码；每个用例都写明证伪点（哪条断言失败说明哪条语义破了）。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.confirm_verify_pipeline import (
    STAGE_NEWS,
    STAGE_RESONANCE,
    ConfirmVerifyPipeline,
)
from qs_watch.application.services.watch_engine.engine import (
    ENV_GATE_EXEMPT_REASON,
    WatchEngine,
)
from qs_watch.application.services.watch_engine.sector_resonance_service import (
    STATUS_ISOLATED,
    STATUS_RESONANT,
    STATUS_SKIPPED,
    SectorResonanceService,
)
from qs_watch.domain.watch.models import MarketState

NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内（与场景矩阵同一基准）
ENV_BLOCKED_PREFIX = '环境闸拦截：'
FALSE_SIGNAL_PREFIX = '假信号：'


# ── 假件：出口（通知 / 归档 / 待办）──────────────────────────
class _TriggerRepo:
    """suppressed 归档口（`notifier.trigger_repo.record`）。"""

    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
        self.rows.append(row)
        return row


class _Notifier:
    """三条出口分开计数：notify=真通知；record_only=市场门归档；record=抑制归档。"""

    def __init__(self):
        self.trigger_repo = _TriggerRepo()
        self.notifications = []
        self.record_only_calls = []
        self.governance_calls = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append({'rule_id': rule.id,
                                   'disposition': kwargs.get('disposition'),
                                   'reason': kwargs.get('disposition_reason')})
        return SimpleNamespace(
            id=100 + len(self.notifications),
            notified=kwargs.get('disposition') != 'deduped',
            todo_id=None,
        )

    def record_only(self, rule, condition, quote, result,
                    disposition=None, disposition_reason=None):
        self.record_only_calls.append({'rule_id': rule.id,
                                       'reason': disposition_reason})
        return SimpleNamespace(id=200 + len(self.record_only_calls),
                               notified=False)

    def record_governance(self, rule, reason, detail=None):
        self.governance_calls.append({'rule_id': rule.id, 'reason': reason})


class _TodoService:
    def __init__(self):
        self.created = []

    def create(self, *args, **kwargs):
        self.created.append({'symbol': args[0] if args else None, **kwargs})
        return SimpleNamespace(id=len(self.created))


# ── 假件：取数（行情 / 市场状态）────────────────────────────
class _RuleRepo:
    def __init__(self, rules):
        self._rules = list(rules)
        self.updates = []

    def list_enabled(self):
        return list(self._rules)

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))


class _StaticQuotes:
    """每标的固定报价；prev_close 可按标的给（陈旧驻留判定用）。"""

    def __init__(self, prices, prev_close=98.0):
        self.prices = dict(prices)
        self.prev_close = prev_close

    def get_realtime_quote(self, symbol):
        price = self.prices.get(symbol)
        if price is None:
            return None
        prev = (self.prev_close.get(symbol)
                if isinstance(self.prev_close, dict) else self.prev_close)
        return SimpleNamespace(symbol=symbol, price=price, prev_close=prev,
                               volume=1_000_000, change_pct=None)


class _SequenceQuotes:
    """两拍行情：先触及、再确认（staged_break e2e 用）。"""

    def __init__(self, frames, prev_close=102.0, change_pct=6.0):
        self.frames = {symbol: list(prices) for symbol, prices in frames.items()}
        self.prev_close = prev_close
        self.change_pct = change_pct

    def get_realtime_quote(self, symbol):
        frames = self.frames.get(symbol) or []
        if not frames:
            return None
        price = frames.pop(0) if len(frames) > 1 else frames[0]
        return SimpleNamespace(symbol=symbol, price=price,
                               prev_close=self.prev_close,
                               volume=1_000_000,
                               change_pct=self.change_pct)


class _StateProvider:
    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state


class _MarketWatchSvc:
    """引擎侧只用 state_provider；市场级扫描返回空清单。"""

    def __init__(self, state):
        self.state_provider = _StateProvider(state)

    def scan_market_rules(self, now):
        return {'scanned': 0, 'triggered': 0, 'skipped_no_data': 0,
                'evaluated': []}


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


# ── 假件：确认核验三服务（E2 用；E3 换成真共振服务）──────────
class _News:
    """利空查询替身：默认干净；negative=True 时命中强利空。"""

    def __init__(self, negative=False, title='公司被立案调查'):
        self.negative = negative
        self.title = title
        self.calls = []

    def query_negative_news(self, symbol, now=None, **kwargs):
        self.calls.append(symbol)
        if self.negative:
            return {'symbol': str(symbol).split('.')[0], 'has_negative': True,
                    'tier': 'critical', 'hits': [{'title': self.title}],
                    'checked': 3, 'total': 9, 'skipped': False, 'error': None}
        return {'symbol': str(symbol).split('.')[0], 'has_negative': False,
                'tier': 'none', 'hits': [], 'checked': 6, 'total': 9,
                'skipped': False, 'error': None}


class _LiquidityResult:
    def __init__(self, ok=True, reason='盘口正常：成交额与量比均达标'):
        self.ok = ok
        self.reason = reason

    def to_dict(self):
        return {'verdict': 'normal' if self.ok else 'drained',
                'ok': self.ok, 'reason': self.reason}


class _Liquidity:
    def __init__(self):
        self.calls = []

    def check(self, quote):
        self.calls.append(quote)
        return _LiquidityResult()


class _Resonance:
    """共振替身：E2 里固定通过，把失败点留给新闻/流动性。"""

    def __init__(self):
        self.calls = []

    def verify(self, symbol, change_pct=None, **kwargs):
        self.calls.append(symbol)
        return SimpleNamespace(
            passed=True, reason='板块共振成立：核心标的同步异动',
            to_dict=lambda: {'status': 'resonant', 'passed': True})


def _pipeline(news=None, liquidity=None, resonance=None):
    return ConfirmVerifyPipeline(
        news_service=news if news is not None else _News(),
        liquidity_service=liquidity if liquidity is not None else _Liquidity(),
        resonance_service=resonance if resonance is not None else _Resonance(),
        now_fn=lambda: NOW,
    )


# ── 假件：板块共振数据源（E3 用真服务，只替数据源）────────────
BAIJIU = {
    '白酒': [
        {'symbol': '600519', 'name': '贵州茅台', 'market_cap': 2.1e12},
        {'symbol': '000858', 'name': '五粮液', 'market_cap': 5.0e11},
        {'symbol': '000568', 'name': '泸州老窖', 'market_cap': 2.4e11},
        {'symbol': '600809', 'name': '山西汾酒', 'market_cap': 2.2e11},
        {'symbol': '000799', 'name': '酒鬼酒', 'market_cap': 3.0e10},
    ]
}
BAIJIU_CANDIDATES = ['600519', '000858', '000568', '600809', '000799']


class _SectorSource:
    def __init__(self, boards):
        self.boards = boards

    def list_sectors(self):
        return list(self.boards)

    def get_members(self, sector):
        return [dict(member) for member in self.boards.get(sector, [])]


class _PeerQuotes:
    """核心标的批量行情：changes = {裸码: 涨跌幅%}。"""

    def __init__(self, changes):
        self.changes = dict(changes)
        self.calls = []

    def get_quotes(self, symbols):
        self.calls.append(list(symbols))
        data = {symbol: SimpleNamespace(symbol=symbol,
                                        change_pct=self.changes[symbol])
                for symbol in symbols if symbol in self.changes}
        return {'success': True, 'data': data}


class _RecordingResonance:
    """包一层真服务，记录它在流水线里**实际**返回的三态结论（证据用）。"""

    def __init__(self, service):
        self.service = service
        self.results = []

    def verify(self, symbol, change_pct=None, **kwargs):
        result = self.service.verify(symbol, change_pct, **kwargs)
        self.results.append(result)
        return result


def _resonance(changes, *, build_map=True):
    service = SectorResonanceService(
        sector_source=_SectorSource(BAIJIU),
        quote_source=_PeerQuotes(changes),
        now_fn=lambda: NOW,
    )
    if build_map:
        built = service.refresh(candidates=BAIJIU_CANDIDATES)
        assert built['built'] is True, '测试前置：板块映射应能构建'
    return _RecordingResonance(service)


# ── 规则 / 引擎工厂 ─────────────────────────────────────────
def _rule(id=1, symbol='600519.SH', *, intent='exit_stop', scope='symbol',
          lifecycle_stage='watching', cost_price=None, conditions=None,
          action_hint=None, action_params=None, account='agent_brain'):
    return SimpleNamespace(
        id=id, symbol=symbol, scope=scope,
        conditions=conditions or [
            {'type': 'price_break',
             'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=cost_price, active_window=None,
        intent=intent,
        action_hint=action_hint or {'trigger_level': 'L2',
                                    'action_on_trigger': 'sell'},
        escalation_policy=None,
        linked_account=account,
        account=account,
        lifecycle_stage=lifecycle_stage,
        created_from=None, next_action_hint=None, target=None,
        review_interval_days=None, review_due_at=None, enabled=True,
        action_params=action_params, ops_notes=None,
        noise_state=None, suppress_until=None,
    )


def _staged_rule(id=1, symbol='600519.SH'):
    return _rule(
        id=id, symbol=symbol, intent='exit_stop',
        conditions=[{
            'type': 'staged_break',
            'params': {'touch': {'price': 100.0, 'direction': 'below'},
                       'confirm': {'kind': 'reclaim'},
                       'window_min': 120},
            'cooldown_sec': 300,
        }],
    )


def _engine(rules, quotes, notifier, *, state=None, pipeline=None, todo=None):
    kwargs = {}
    if state is not None:
        kwargs['market_watch_service'] = _MarketWatchSvc(state)
    if pipeline is not None:
        kwargs['confirm_verify_pipeline'] = pipeline
    if todo is not None:
        kwargs['todo_service'] = todo
    return WatchEngine(
        rule_repo=_RuleRepo(rules),
        quote_service=quotes,
        notifier=notifier,
        now_fn=lambda: NOW,
        **kwargs,
    )


# ══════════════════════════════════════════════════════════════
# E1. 全局环境闸：归档 vs 通知（含止损豁免后的最终语义）
# ══════════════════════════════════════════════════════════════

def test_E1_blocked_environment_archives_observe_but_notifies_protection_stop():
    """环境日同 tick 两条信号：持仓保护线照常通知，观察类只归档。

    证伪点：
      · 通知出口少了保护线 → 止损被环境闸吞掉（资损风险）；
      · 观察类也发了通知 → 豁免被放大成「环境日全部放行」；
      · 归档占用了日配额 → 归档被当成一次通知记账；
      · 保护线事件没有 env_gate_exempt 溯源 → 复盘无法区分豁免日与正常日。
    """
    notifier, todo = _Notifier(), _TodoService()
    stop = _rule(
        id=1, symbol='600519.SH', scope='position', lifecycle_stage='holding',
        cost_price=95.0, intent='exit_stop',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 100.0}}],
    )
    observe = _rule(
        id=2, symbol='600036.SH', intent='trend_observe',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'above', 'price': 100.0}}],
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
    )
    engine = _engine(
        [stop, observe],
        _StaticQuotes({'600519.SH': 99.0, '600036.SH': 101.0},
                      prev_close={'600519.SH': 102.0, '600036.SH': 98.0}),
        notifier, state=_blocked_state(), todo=todo,
    )

    events = engine.tick()

    # 通知差异：只有保护线一条；归档差异：只有观察类一条。
    assert [n['rule_id'] for n in notifier.notifications] == [1], \
        '环境日应只放行保护线止损，实际通知：%s' % notifier.notifications
    assert len(notifier.trigger_repo.rows) == 1
    archived = notifier.trigger_repo.rows[0]
    assert archived.rule_id == 2, '被拦截的观察类应归档'
    assert archived.suppressed is True and archived.notified is False
    assert str(archived.disposition_reason).startswith(ENV_BLOCKED_PREFIX)
    assert '只记录不动作' in archived.disposition_reason

    by_rule = {event['rule_id']: event for event in events}
    exempt_event = by_rule[1]
    assert exempt_event['notified'] is True
    assert exempt_event['env_gate_exempt'] is True
    assert exempt_event['env_gate_exempt_reason'].startswith(ENV_GATE_EXEMPT_REASON)
    assert 'intent=exit_stop' in exempt_event['env_gate_exempt_reason']
    assert '锚点=scope=position' in exempt_event['env_gate_exempt_reason']

    blocked_event = by_rule[2]
    assert blocked_event['notified'] is False
    assert blocked_event['suppressed'] is True
    assert 'env_gate_exempt' not in blocked_event

    # 通知占配额（且只占这一条）；归档不占。
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}
    # 未动作的归档不建待办；保护线通知照常进待办（P0）。
    assert [item['symbol'] for item in todo.created] == ['600519.SH']


def test_E1_stop_intent_without_protection_anchor_still_archived():
    """最终语义边界：exit_stop 意图 + 无保护线锚点（上破提醒）仍只归档。

    豁免判据是「动作类型 + 结构化锚点」，不是「intent 写着 exit_stop」。
    这条守住场景矩阵 B7 的原有口径，防止豁免扩大成「止损字样通行证」。
    """
    notifier = _Notifier()
    engine = _engine(
        [_rule(id=1, symbol='600519.SH', intent='exit_stop')],
        _StaticQuotes({'600519.SH': 101.0}, prev_close=98.0),
        notifier, state=_blocked_state(),
    )

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1
    assert notifier.trigger_repo.rows[0].suppressed is True
    assert events[0]['notified'] is False
    assert 'env_gate_exempt' not in events[0]
    assert engine.state.daily_emit_counts == {}
    # 被拦截 = 本次没有消费止损线，规则不得被自动退役。
    assert engine.rule_repo.updates == []


def test_E1_exempt_stop_still_blocked_by_its_own_stricter_market_gate():
    """豁免只跳过全局环境闸：规则自己的 per-rule market_gate 仍可加严拦截。

    证伪点：若豁免被实现成「直接 return 放行」，这里会误发通知；
    正确语义是继续走后续门，拦截时事件仍保留「全局闸已豁免」的溯源。
    """
    notifier = _Notifier()
    stop = _rule(
        id=1, symbol='600519.SH', scope='position', lifecycle_stage='holding',
        cost_price=95.0, intent='exit_stop',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 100.0}}],
        action_params={'market_gate': {'index': '000300.SH',
                                       'max_down_pct': -1.5}},
    )
    engine = _engine([stop], _StaticQuotes({'600519.SH': 99.0},
                                           prev_close=102.0),
                     notifier, state=_blocked_state())

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.record_only_calls) == 1
    assert str(notifier.record_only_calls[0]['reason']).startswith('市场门拦截：')
    assert notifier.trigger_repo.rows == [], 'market_gate 不应重复落 suppressed 归档'
    assert events[0]['notified'] is False
    assert events[0]['env_gate_exempt'] is True, '应保留「全局闸已豁免」的溯源'
    # market_gate 是加严项，沿用既有语义：日计数照常。
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}


# ══════════════════════════════════════════════════════════════
# E2. 确认核验：假信号归档 vs 全过通知
# ══════════════════════════════════════════════════════════════

def test_E2_false_signal_archived_without_notify_or_todo():
    """staged 确认成立但利空核验失败 → 只归档假信号样本。

    证伪点：
      · 发了通知 / 建了待办 → 假信号仍打扰用户；
      · 占了日通知配额 → 假信号被当成一次投送；
      · 归档 detail 缺少逐项结论 → 复盘无法回答「哪一道没通过」。
    """
    notifier, todo = _Notifier(), _TodoService()
    news = _News(negative=True)
    pipeline = _pipeline(news=news)
    engine = _engine([_staged_rule()],
                     _SequenceQuotes({'600519.SH': [99.0, 101.0]}),
                     notifier, pipeline=pipeline, todo=todo)

    assert engine.tick() == [], '第一拍只是触及，应静默进观察态'
    events = engine.tick()        # 第二拍：收复确认 → 三道核验

    assert news.calls == ['600519.SH'], '利空核验没有被调用'
    assert notifier.notifications == []
    assert todo.created == []
    assert engine.state.daily_emit_counts == {}

    assert len(notifier.trigger_repo.rows) == 1
    row = notifier.trigger_repo.rows[0]
    assert row.suppressed is True and row.notified is False
    assert row.disposition == 'auto_observed'
    assert str(row.disposition_reason).startswith(FALSE_SIGNAL_PREFIX)
    assert '确认核验未通过' in row.disposition_reason
    # 复盘下钻：假信号标记 + 三道逐项结论（利空失败、另外两道也各留结论）。
    assert row.detail['false_signal'] is True
    assert row.detail['failed_stages'] == [STAGE_NEWS]
    verify = row.detail['confirm_verify']
    assert verify['passed'] is False and verify['verified'] is False
    assert [stage['stage'] for stage in verify['stages']] == [
        'news', 'liquidity', 'resonance']

    assert len(events) == 1
    event = events[0]
    assert event['suppressed'] is True and event['notified'] is False
    assert event['false_signal'] is True
    assert event['confirm_verify']['failed_stages'] == [STAGE_NEWS]
    assert event['trigger_id'] == 1


def test_E2_clean_confirmation_notifies_and_archives_nothing():
    """同一套 staged 假件，核验全过 → 通知出口打开、归档口为空。

    与上一条构成可证伪对照：若两条用例结论相同，说明核验闸没有真正接进
    引擎流水线（不是「假信号被拦」而是「所有信号都被拦」）。
    """
    notifier, todo = _Notifier(), _TodoService()
    news = _News(negative=False)
    pipeline = _pipeline(news=news)
    engine = _engine([_staged_rule()],
                     _SequenceQuotes({'600519.SH': [99.0, 101.0]}),
                     notifier, pipeline=pipeline, todo=todo)

    assert engine.tick() == []
    events = engine.tick()

    assert news.calls == ['600519.SH']
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0]['rule_id'] == 1
    assert notifier.trigger_repo.rows == []
    assert notifier.record_only_calls == []
    assert len(events) == 1
    assert events[0]['notified'] is True
    assert 'false_signal' not in events[0]
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}
    assert [item['symbol'] for item in todo.created] == ['600519.SH']


# ══════════════════════════════════════════════════════════════
# E3. 板块共振加权：共振放行 vs 孤立异动归档
# ══════════════════════════════════════════════════════════════

def test_E3_isolated_move_archived_as_false_signal():
    """个股孤立异动（板块核心标的未同步）→ 不按共振加权 → 判假信号归档。

    证伪点：
      · 共振阶段被跳过（skipped）却归档 → 缺数据被当成「未共振」；
      · 归档理由没有「不按板块共振加权」→ 复盘看不出是共振维度否掉的；
      · 通知出口未关 → 孤立异动仍打扰用户。
    """
    notifier = _Notifier()
    resonance = _resonance({
        '000858': 0.4, '000568': -0.2, '600809': 0.6, '000799': -0.1})
    pipeline = _pipeline(resonance=resonance)
    engine = _engine([_staged_rule()],
                     _SequenceQuotes({'600519.SH': [99.0, 101.0]}),
                     notifier, pipeline=pipeline)

    engine.tick()
    events = engine.tick()

    # 真共振服务确实被调用，并明确给出「孤立异动」（不是 skipped）。
    assert len(resonance.results) == 1
    verdict = resonance.results[0]
    assert verdict.status == STATUS_ISOLATED
    assert verdict.verified is True and verdict.passed is False

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1
    row = notifier.trigger_repo.rows[0]
    assert row.suppressed is True
    assert row.detail['failed_stages'] == [STAGE_RESONANCE]
    assert '孤立异动' in row.disposition_reason
    assert '不按板块共振加权' in row.disposition_reason
    stages = {stage['stage']: stage
              for stage in row.detail['confirm_verify']['stages']}
    assert stages[STAGE_RESONANCE]['verdict'] == 'failed'
    assert '不按板块共振加权' in stages[STAGE_RESONANCE]['reason']
    assert events[0]['notified'] is False
    assert events[0]['false_signal'] is True
    assert engine.state.daily_emit_counts == {}


def test_E3_sector_resonance_notifies_and_does_not_archive():
    """同板块核心标的同步异动（共振成立）→ 放行通知、不落假信号归档。

    证伪点：若真服务返回 resonant 却仍归档，说明共振结论没有进入流水线闸门；
    若归档口有行，则「共振加权」又被误判成缺数据/孤立。
    """
    notifier = _Notifier()
    resonance = _resonance({
        '000858': 3.2, '000568': 2.4, '600809': -0.8, '000799': 0.2})
    pipeline = _pipeline(resonance=resonance)
    engine = _engine([_staged_rule()],
                     _SequenceQuotes({'600519.SH': [99.0, 101.0]}),
                     notifier, pipeline=pipeline)

    engine.tick()
    events = engine.tick()

    assert len(resonance.results) == 1
    verdict = resonance.results[0]
    assert verdict.status == STATUS_RESONANT
    assert verdict.verified is True and verdict.passed is True

    assert len(notifier.notifications) == 1
    assert notifier.trigger_repo.rows == []
    assert notifier.record_only_calls == []
    assert events[0]['notified'] is True
    assert 'false_signal' not in events[0]
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}


def test_E3_missing_resonance_data_fails_open_without_archive():
    """共振映射/行情缺失 → skipped 不校验：不是孤立异动，不得据此归档。

    数据缺失 ≠ 事实（R-013）：把「没取到」当成「未共振」会因数据源抖动
    冤枉真信号。此用例守住 fail-open 与「不臆造加权结论」的边界。
    """
    notifier = _Notifier()
    # build_map=False：映射未构建 → 真服务必然返回 skipped/verified=False。
    resonance = _resonance({}, build_map=False)
    pipeline = _pipeline(resonance=resonance)
    engine = _engine([_staged_rule()],
                     _SequenceQuotes({'600519.SH': [99.0, 101.0]}),
                     notifier, pipeline=pipeline)

    engine.tick()
    events = engine.tick()

    assert len(resonance.results) == 1
    verdict = resonance.results[0]
    assert verdict.status == STATUS_SKIPPED
    assert verdict.verified is False and verdict.passed is None

    assert len(notifier.notifications) == 1, '缺数据不得拦信号（fail-open）'
    assert notifier.trigger_repo.rows == []
    assert events[0]['notified'] is True
    assert 'false_signal' not in events[0]
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}
