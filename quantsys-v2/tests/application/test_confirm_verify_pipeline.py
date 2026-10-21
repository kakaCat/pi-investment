"""确认核验流水线单测（2026-10-20，机会闭环 M2）

覆盖任务卡验收口径：
  0) 流水线：全过 / 单项失败 / 多项失败 / skipped fail-open / 阶段异常隔离；
  1) 引擎接线：staged_break 确认成立后先过三道核验，全过才进触发流水线；
  2) 失败样本：归档 suppressed（disposition=auto_observed，detail 带逐项结论），
     不通知、不进摘要队列、不建待办、不占日通知配额；未装配流水线时行为不变。

设计纪律：三道核验服务全部用替身（零外呼），但引擎/流水线走生产代码。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.confirm_verify_pipeline import (
    STAGE_LIQUIDITY,
    STAGE_NEWS,
    STAGE_ORDER,
    STAGE_RESONANCE,
    VERDICT_FAILED,
    VERDICT_PASSED,
    VERDICT_SKIPPED,
    ConfirmVerifyPipeline,
)
from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.liquidity_check_service import (
    LiquidityCheckService,
)

NOW = datetime(2026, 10, 20, 10, 0)  # 周二，交易时段内


# ── 替身 ────────────────────────────────────────────────────

class _News:
    """利空查询替身：默认干净，可配置命中/取数失败/直接抛错。"""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def query_negative_news(self, symbol, now=None, limit=15):
        self.calls.append((symbol, now))
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return dict(self.result)
        return {'symbol': str(symbol).split('.')[0], 'has_negative': False,
                'tier': 'none', 'hits': [], 'checked': 6, 'total': 9,
                'skipped': False, 'error': None}


class _LiquidityResult:
    def __init__(self, ok, reason, verdict='normal'):
        self.ok = ok
        self.reason = reason
        self.verdict = verdict

    def to_dict(self):
        return {'verdict': self.verdict, 'ok': self.ok, 'reason': self.reason}


class _Liquidity:
    def __init__(self, ok=True, reason='盘口正常：成交额与量比均达标'):
        self.result = _LiquidityResult(ok, reason,
                                       'normal' if ok else 'drained')
        self.calls = []

    def check(self, quote):
        self.calls.append(quote)
        return self.result


class _ResonanceResult:
    def __init__(self, passed, reason, status='resonant'):
        self.passed = passed
        self.reason = reason
        self.status = status

    def to_dict(self):
        return {'status': self.status, 'passed': self.passed,
                'reason': self.reason}


class _Resonance:
    def __init__(self, passed=True, reason='板块共振：核心标的同步异动'):
        self.result = _ResonanceResult(passed, reason,
                                       'resonant' if passed else 'isolated')
        self.calls = []

    def verify(self, symbol, change_pct=None, **kwargs):
        self.calls.append((symbol, change_pct, kwargs))
        return self.result


def _pipeline(news=None, liquidity=None, resonance=None, **kwargs):
    return ConfirmVerifyPipeline(
        news_service=news if news is not None else _News(),
        liquidity_service=liquidity if liquidity is not None else _Liquidity(),
        resonance_service=resonance if resonance is not None else _Resonance(),
        now_fn=lambda: NOW, **kwargs)


def _quote(price=101.0):
    return SimpleNamespace(symbol='600519.SH', price=price, prev_close=102.0,
                           volume=1_000_000, change_pct=None)


# ── 1. 流水线语义 ────────────────────────────────────────────

def test_all_stages_pass():
    pipeline = _pipeline()
    result = pipeline.verify('600519.SH', quote=_quote())

    assert result.passed is True
    assert result.verified is True
    assert result.failed_stages == ()
    assert result.skipped_stages == ()
    assert [s.stage for s in result.stages] == list(STAGE_ORDER)
    assert all(s.verdict == VERDICT_PASSED for s in result.stages)
    assert '全过' in result.reason


def test_news_failure_blocks_pipeline():
    news = _News({'symbol': '600519', 'has_negative': True, 'tier': 'critical',
                  'hits': [{'title': '公司被立案调查'}], 'checked': 6,
                  'total': 9, 'skipped': False, 'error': None})
    liquidity, resonance = _Liquidity(), _Resonance()
    result = _pipeline(news, liquidity, resonance).verify(
        '600519.SH', quote=_quote())

    assert result.passed is False
    assert result.failed_stages == (STAGE_NEWS,)
    assert result.first_failure.label == '利空核验'
    assert '强利空' in result.first_failure.reason
    assert '公司被立案调查' in result.first_failure.reason
    # 不在首个失败处短路：另外两道照常执行并各自留结论（复盘要看全貌）
    assert len(liquidity.calls) == 1
    assert len(resonance.calls) == 1
    assert result.stages[1].verdict == VERDICT_PASSED
    assert result.stages[2].verdict == VERDICT_PASSED


def test_liquidity_failure_blocks_pipeline():
    result = _pipeline(liquidity=_Liquidity(
        ok=False, reason='流动性枯竭：成交额 3000万 < 下限 1.00亿')).verify(
        '600519.SH', quote=_quote())

    assert result.passed is False
    assert result.failed_stages == (STAGE_LIQUIDITY,)
    assert '流动性枯竭' in result.reason


def test_resonance_failure_blocks_pipeline():
    result = _pipeline(resonance=_Resonance(
        passed=False, reason='孤立异动：同向核心标的 0/5')).verify(
        '600519.SH', quote=_quote())

    assert result.passed is False
    assert result.failed_stages == (STAGE_RESONANCE,)
    assert '孤立异动' in result.reason


def test_multiple_failures_are_all_reported():
    news = _News({'symbol': '600519', 'has_negative': True, 'tier': 'soft',
                  'hits': [{'title': '股东减持计划'}], 'checked': 3,
                  'total': 9, 'skipped': False, 'error': None})
    liquidity = _Liquidity(ok=False, reason='疑似大单诱骗：大单无真实承接')
    resonance = _Resonance(passed=False, reason='孤立异动：核心标的未同步')

    result = _pipeline(news, liquidity, resonance).verify(
        '600519.SH', quote=_quote())

    assert result.passed is False
    assert result.verified is False
    assert result.failed_stages == (STAGE_NEWS, STAGE_LIQUIDITY,
                                    STAGE_RESONANCE)
    for label in ('利空核验', '流动性核验', '板块共振核验'):
        assert label in result.reason


def test_missing_services_fail_open_but_mark_unverified():
    pipeline = ConfirmVerifyPipeline(now_fn=lambda: NOW)   # 三道都未装配
    result = pipeline.verify('600519.SH', quote=_quote())

    assert result.passed is True          # fail-open：没核验 ≠ 失败
    assert result.verified is False       # 但绝不能冒充「三项全过」
    assert result.failed_stages == ()
    assert result.skipped_stages == STAGE_ORDER
    assert all(s.verdict == VERDICT_SKIPPED for s in result.stages)
    assert 'fail-open' in result.reason


def test_news_skipped_is_fail_open():
    news = _News({'symbol': '600519', 'has_negative': False, 'tier': 'none',
                  'hits': [], 'checked': 0, 'total': 0, 'skipped': True,
                  'error': '新闻源超时'})
    result = _pipeline(news=news).verify('600519.SH', quote=_quote())

    assert result.passed is True
    assert result.verified is False
    assert result.skipped_stages == (STAGE_NEWS,)
    assert '新闻源超时' in result.stages[0].reason


def test_stage_exception_is_isolated_as_skipped():
    news = _News(error=RuntimeError('news boom'))
    liquidity, resonance = _Liquidity(), _Resonance()

    result = _pipeline(news, liquidity, resonance).verify(
        '600519.SH', quote=_quote())

    assert result.passed is True          # 单阶段异常 fail-open
    assert result.verified is False
    assert result.skipped_stages == (STAGE_NEWS,)
    assert 'news boom' in result.stages[0].reason
    # 后两道不受上游异常影响，仍各自执行
    assert len(liquidity.calls) == 1 and len(resonance.calls) == 1


def test_liquidity_quote_provider_enriches_engine_quote():
    """引擎 quote 只有价格/量；补数 provider 提供成交额/量比/大单占比后再判。"""
    service = LiquidityCheckService({
        'min_amount': 1e8, 'min_volume_ratio': 1.0,
        'trap_big_order_ratio': 0.4})
    pipeline = ConfirmVerifyPipeline(
        liquidity_service=service,
        liquidity_quote_provider=lambda symbol, quote: {
            'symbol': symbol, 'amount': 2e8, 'volume_ratio': 1.8,
            'big_order_ratio': 0.2},
        now_fn=lambda: NOW)
    result = pipeline.verify('600519.SH', quote=_quote())

    assert result.stages[1].verdict == VERDICT_PASSED
    assert '盘口正常' in result.stages[1].reason

    empty = ConfirmVerifyPipeline(
        liquidity_service=service, now_fn=lambda: NOW).verify(
        '600519.SH', quote=SimpleNamespace(symbol='600519.SH', price=101.0))
    assert empty.stages[1].verdict == VERDICT_SKIPPED   # 缺字段不猜默认值


def test_result_to_dict_carries_stage_details():
    result = _pipeline().verify('600519.SH', quote=_quote())
    payload = result.to_dict()

    assert payload['passed'] is True and payload['verified'] is True
    assert payload['false_signal'] is False
    assert [s['stage'] for s in payload['stages']] == list(STAGE_ORDER)
    assert payload['stages'][0]['verdict'] == VERDICT_PASSED
    assert payload['stages'][0]['detail']['checked'] == 6


# ── 2. 引擎接线 ─────────────────────────────────────────────

class _RuleRepo:
    def __init__(self, rules):
        self._rules = list(rules)
        self.updates = []

    def list_enabled(self):
        return list(self._rules)

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))


class _QuoteService:
    """两拍行情：先触及（99）再收复确认（101）；prev_close=102 保证「今日新穿越」。"""

    def __init__(self, prices=(99.0, 101.0), prev_close=102.0):
        self.prices = list(prices)
        self.prev_close = prev_close
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        price = self.prices.pop(0) if self.prices else None
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price,
                               prev_close=self.prev_close,
                               volume=1_000_000, change_pct=None)


class _TriggerRepo:
    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
        self.rows.append(row)
        return row


class _Notifier:
    def __init__(self, with_repo=True):
        if with_repo:
            self.trigger_repo = _TriggerRepo()
        self.notifications = []
        self.record_only_calls = []
        self.governance_calls = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append({'rule_id': rule.id, 'price': quote.price,
                                   'kwargs': kwargs})
        return SimpleNamespace(id=100 + len(self.notifications),
                               notified=True, todo_id=None)

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
        self.created.append((args, kwargs))
        return SimpleNamespace(id=1)


def _staged_rule(rule_id=1, symbol='600519.SH'):
    return SimpleNamespace(
        id=rule_id, symbol=symbol, scope='symbol',
        conditions=[{'type': 'staged_break',
                     'params': {'touch': {'price': 100.0, 'direction': 'below'},
                                'confirm': {'kind': 'reclaim'},
                                'window_min': 120},
                     'cooldown_sec': 300}],
        cost_price=None, active_window=None,
        intent='exit_stop',
        action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
        escalation_policy=None, linked_account=None, account='agent_brain',
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None,
        noise_state=None, suppress_until=None,
    )


def _engine(notifier, pipeline=None, todo=None, prices=(99.0, 101.0),
            rules=None, prev_close=102.0):
    return WatchEngine(
        rule_repo=_RuleRepo(rules or [_staged_rule()]),
        quote_service=_QuoteService(prices, prev_close=prev_close),
        notifier=notifier,
        now_fn=lambda: NOW,
        todo_service=todo,
        confirm_verify_pipeline=pipeline,
    )


def test_engine_passes_confirmed_signal_when_all_checks_pass():
    notifier = _Notifier()
    liquidity, resonance = _Liquidity(), _Resonance()
    pipeline = _pipeline(liquidity=liquidity, resonance=resonance)
    engine = _engine(notifier, pipeline)

    assert engine.tick() == []                 # 第一拍：触及，静默进观察态
    events = engine.tick()                     # 第二拍：收复确认 → 三道核验
    assert len(events) == 1
    assert len(notifier.notifications) == 1    # 全过 → 进触发流水线
    assert notifier.trigger_repo.rows == []
    assert len(liquidity.calls) == 1 and len(resonance.calls) == 1
    assert events[0]['notified'] is True


def test_engine_archives_false_signal_without_notify_or_todo():
    notifier = _Notifier()
    todo = _TodoService()
    news = _News({'symbol': '600519', 'has_negative': True, 'tier': 'critical',
                  'hits': [{'title': '公司被立案调查'}], 'checked': 4,
                  'total': 8, 'skipped': False, 'error': None})
    pipeline = _pipeline(news=news)

    engine = _engine(notifier, pipeline, todo)
    assert engine.tick() == []
    events = engine.tick()

    # 不通知 / 不进摘要队列 / 不建待办 / 不占日通知配额
    assert notifier.notifications == []
    assert todo.created == []
    assert engine.state.daily_emit_counts == {}
    # 归档恰好一条 suppressed 样本
    assert len(notifier.trigger_repo.rows) == 1
    row = notifier.trigger_repo.rows[0]
    assert row.suppressed is True
    assert row.notified is False
    assert row.disposition == 'auto_observed'
    assert str(row.disposition_reason).startswith('假信号：')
    assert '确认核验未通过' in row.disposition_reason
    # 复盘可下钻：detail 带假信号标记与三道逐项结论
    assert row.detail['false_signal'] is True
    assert row.detail['failed_stages'] == ['news']
    verify = row.detail['confirm_verify']
    assert verify['passed'] is False
    assert verify['failed_stages'] == ['news']
    assert [s['stage'] for s in verify['stages']] == list(STAGE_ORDER)

    assert len(events) == 1
    ev = events[0]
    assert ev['suppressed'] is True and ev['notified'] is False
    assert ev['disposition'] == 'auto_observed'
    assert ev['trigger_id'] == 1
    assert ev['false_signal'] is True
    assert ev['confirm_verify']['failed_stages'] == ['news']


def test_engine_archives_all_failing_stages_in_one_sample():
    notifier = _Notifier()
    news = _News({'symbol': '600519', 'has_negative': True, 'tier': 'soft',
                  'hits': [{'title': '股东减持'}], 'checked': 2,
                  'total': 8, 'skipped': False, 'error': None})
    pipeline = _pipeline(news=news,
                         liquidity=_Liquidity(ok=False, reason='流动性枯竭'),
                         resonance=_Resonance(passed=False, reason='孤立异动'))

    engine = _engine(notifier, pipeline)
    engine.tick()
    engine.tick()

    assert len(notifier.trigger_repo.rows) == 1
    verify = notifier.trigger_repo.rows[0].detail['confirm_verify']
    assert verify['failed_stages'] == ['news', 'liquidity', 'resonance']
    assert notifier.notifications == []


def test_engine_without_pipeline_keeps_legacy_behavior():
    """未装配流水线 = 确认即进触发流水线（回滚/未接线零影响）。"""
    notifier = _Notifier()
    engine = _engine(notifier, None)

    engine.tick()
    engine.tick()
    assert len(notifier.notifications) == 1
    assert notifier.trigger_repo.rows == []


def test_engine_pipeline_only_used_for_staged_confirm():
    """普通 price_break 不进三道核验——流水线只服务两段式确认。"""
    notifier = _Notifier()
    news, liquidity, resonance = _News(), _Liquidity(), _Resonance()
    pipeline = _pipeline(news, liquidity, resonance)
    rule = _staged_rule()
    rule.conditions = [{'type': 'price_break',
                        'params': {'direction': 'above', 'price': 100.0}}]

    engine = _engine(notifier, pipeline, prices=(101.0,), rules=[rule],
                     prev_close=98.0)
    events = engine.tick()

    assert len(events) == 1
    assert len(notifier.notifications) == 1
    assert news.calls == [] and liquidity.calls == [] and resonance.calls == []


def test_engine_pipeline_exception_fails_open():
    """流水线自身故障不得让盯盘信号失明（fail-open）。"""
    class _BoomPipeline:
        def verify(self, *args, **kwargs):
            raise RuntimeError('pipeline boom')

    notifier = _Notifier()
    engine = _engine(notifier, _BoomPipeline())
    engine.tick()
    events = engine.tick()

    assert len(events) == 1
    assert len(notifier.notifications) == 1
    assert notifier.trigger_repo.rows == []


def test_engine_archives_via_record_only_when_repo_missing():
    """部分装配只有 record_only、没有 trigger_repo：归档不能因此丢失。"""
    notifier = _Notifier(with_repo=False)
    pipeline = _pipeline(news=_News(
        {'symbol': '600519', 'has_negative': True, 'tier': 'critical',
         'hits': [{'title': '立案'}], 'checked': 1, 'total': 5,
         'skipped': False, 'error': None}))

    engine = _engine(notifier, pipeline)
    engine.tick()
    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.record_only_calls) == 1
    assert str(notifier.record_only_calls[0]['reason']).startswith('假信号：')
    assert events[0]['trigger_id'] == 201   # record_only 归档 id
    assert events[0]['suppressed'] is True
