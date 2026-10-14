"""端到端验收：触发 → 库有码 → 卡有理由（REQ-261007133807-eda6 t13 · FR-1~FR-5）

本卡是结单卡：把前面各卡的判据在**一条真实链路上**串起来跑一遍，并锁住两条结构判据。

链路（真实部分）：冻结时钟 → engine.tick → 唯一裁决出口 → 处置映射 → 通知器 →
`quant.watch_triggers` 落库（**测试库真写**）→ 从通知器实际下发的参数渲染卡片（**真渲染器**）。
桩掉的部分只有两样：行情源与"外发传输"（后者换成记账替身，`notify_guard` 另外保证零真实外发）。

不真实交易日：`now_fn` 冻结在周二交易时段内（与既有引擎用例同法）。
"""
import os
import re
from datetime import datetime
from types import SimpleNamespace

import pytest

from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.notifier import WatchNotifier
from domain.watch.services.escalation_verdict import EscalationCode
from infrastructure.notification.formatters.feishu_formatters import (
    WatchTriggeredFormatter, escalation_reason_line,
)

NOW = datetime(2026, 7, 21, 10, 30)  # 周二 10:30，交易时段内
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── 替身（只桩行情与外发传输）────────────────────────────────────────
def _rule(rid, intent, action, level='L1', symbol='600519.SH'):
    return SimpleNamespace(
        id=rid, symbol=symbol,
        conditions=[{'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=None, active_window=None, intent=intent,
        action_hint={'trigger_level': level, 'action_on_trigger': action},
        escalation_policy=None, scope='symbol', linked_account=None,
        lifecycle_stage='watching', created_from='e2e', next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
    )


class _RuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class _QuoteService:
    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=101.0, prev_close=98.0,
                               volume=1_000_000, change_pct=None, name='贵州茅台')


class _RecordingFacade:
    """外发传输替身：记账收到的参数（不强求任何网络行为）。"""

    def __init__(self):
        self.calls = []

    def send_watch_triggered(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(success=True)


def _engine(rules, trigger_repo, facade):
    notifier = WatchNotifier(trigger_repo=trigger_repo, notification_facade=facade, ws_url=None)
    return WatchEngine(rule_repo=_RuleRepo(rules), quote_service=_QuoteService(),
                       notifier=notifier, now_fn=lambda: NOW)


def _card_content(kwargs) -> str:
    """把通知器实际下发的参数喂给**真渲染器**（旧渲染路径）→ 卡片正文。"""
    variables = {k: v for k, v in kwargs.items() if v is not None}
    variables.setdefault('message', '现价 101.0 上破阈值 100.0')
    notification = SimpleNamespace(variables=variables, content=variables.get('message'),
                                   type=None)
    return WatchTriggeredFormatter().format(notification)['card']['elements'][0]['text']['content']


#: 四条规则：两条该叫（过门动作 / 规则本来就是 L2），两条不该叫（观察类 / 消息类）。
#: **每条用不同标的** —— 同标的同向会在 60s 去重窗内互相合并（实测踩过：4 条同标的只剩 1 条不 deduped）。
SPECS = [
    ('600001.SH', 'entry', 'buy', 'L1', True),
    ('600002.SH', 'trend_observe', 'observe', 'L1', False),
    ('600003.SH', '', 'observe', 'L2', True),
    ('600004.SH', '', 'message', 'L1', False),
]
CONDITIONS = [{'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}}]


class _RealRuleRepo:
    """真仓储 + 只回本次建的四条（避免被库里其它启用规则污染断言）。"""

    def __init__(self, repo, ids):
        self._repo = repo
        self._ids = set(ids)

    def list_enabled(self):
        return [r for r in self._repo.list_enabled() if r.id in self._ids]


class _QuoteService:
    """四个标的一律 101（> 阈值 100）：触发条件与去重键都按标的区分。"""

    def get_realtime_quote(self, symbol):
        if symbol not in {s[0] for s in SPECS}:
            return None
        return SimpleNamespace(symbol=symbol, price=101.0, prev_close=98.0,
                               volume=1_000_000, change_pct=None, name='测试标的')


class _RecordingFacade:
    """外发传输替身：记账收到的参数（不强求任何网络行为）。"""

    def __init__(self):
        self.calls = []

    def send_watch_triggered(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(success=True)


def _engine(rule_repo, facade):
    # trigger_repo **必须给真仓储**：本卡的判据之一是"库里那行也带同一个码"，
    # 传 None 会静默不落库（events 里 trigger_id 为 None —— 实测踩过）。
    from adapters.outbound.repositories.watch_rule_repository import WatchTriggerRepository
    notifier = WatchNotifier(trigger_repo=WatchTriggerRepository(),
                             notification_facade=facade, ws_url=None)
    return WatchEngine(rule_repo=rule_repo, quote_service=_QuoteService(),
                       notifier=notifier, now_fn=lambda: NOW)


def _card_content(kwargs) -> str:
    """把通知器实际下发的参数喂给**真渲染器**（旧渲染路径）→ 卡片正文。"""
    variables = {k: v for k, v in kwargs.items() if v is not None}
    variables.setdefault('message', '现价 101.0 上破阈值 100.0')
    notification = SimpleNamespace(variables=variables,
                                   content=variables.get('message'), type=None)
    return WatchTriggeredFormatter().format(notification)['card']['elements'][0]['text']['content']


@pytest.fixture
def seeded():
    """在**测试库**真建四条规则（watch_triggers.rule_id 有外键，假 id 会插入失败），
    并给引擎一个只认这四条的仓储视图；收尾清掉触发行与规则行。"""
    from sqlalchemy import text

    from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
    from infrastructure.persistence.database.engine import get_engine

    repo = WatchRuleRepository()
    ids = []
    for symbol, intent, action, level, _wakes in SPECS:
        for account in (('e2e-acct',) if action == 'buy' else (None,)):
            rule = repo.create_rule(symbol=symbol, conditions=CONDITIONS, context='e2e',
                                    created_by='test', account=account)
            repo.update_fields(rule.id, intent=intent,
                               action_hint={'trigger_level': level, 'action_on_trigger': action})
            ids.append(rule.id)
            break
    try:
        yield _RealRuleRepo(repo, ids)
    finally:
        with get_engine().begin() as conn:
            conn.execute(text('delete from quant.watch_triggers where rule_id = any(:ids)'),
                         {'ids': ids})
            conn.execute(text('delete from quant.watch_rules where id = any(:ids)'), {'ids': ids})


def test_end_to_end_codes_land_in_events_and_db(seeded):
    """一次 tick 后：事件带码，**库里的行也带同一个码**（这才是"可查"）。"""
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    facade = _RecordingFacade()
    events = _engine(seeded, facade).tick()

    assert len(events) == 4
    ids = [e['trigger_id'] for e in events]
    try:
        with get_engine().connect() as conn:
            rows = dict(conn.execute(text(
                'select id, escalation_code from quant.watch_triggers where id = any(:ids)'),
                {'ids': ids}).fetchall())
        for e in events:
            assert e['escalation_code'], e
            assert rows.get(e['trigger_id']) == e['escalation_code'], (e, rows)
        codes = {e['escalation_code'] for e in events}
        assert codes == {EscalationCode.GATES_PASSED_ACTION, EscalationCode.OBSERVE_INTENT,
                         EscalationCode.RULE_LEVEL_L2}, codes
    finally:
        with get_engine().begin() as conn:
            conn.execute(text('delete from quant.watch_triggers where id = any(:ids)'), {'ids': ids})


def test_wake_count_lock_two_of_four_escalate(seeded):
    """**唤醒量回归锁**：这套输入下恰好 2 条进队列（本需求只做收敛与可见化，不放松也不收紧）。"""
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    facade = _RecordingFacade()
    events = _engine(seeded, facade).tick()
    ids = [e['trigger_id'] for e in events]
    try:
        assert sum(1 for e in events if e['disposition'] == 'escalated') == 2
        assert sum(1 for e in events if e['disposition'] == 'auto_observed') == 2
        with get_engine().connect() as conn:
            escalated = conn.execute(text(
                "select count(*) from quant.watch_triggers "
                "where id = any(:ids) and disposition = 'escalated'"), {'ids': ids}).scalar()
        assert escalated == 2
    finally:
        with get_engine().begin() as conn:
            conn.execute(text('delete from quant.watch_triggers where id = any(:ids)'), {'ids': ids})


def test_card_shows_reason_for_waking_and_hides_it_for_not_waking(seeded):
    """卡面：叫了 agent 的卡带「升级原因」；没叫的卡**不多一行**（理由归落库）。"""
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    facade = _RecordingFacade()
    events = _engine(seeded, facade).tick()
    ids = [e['trigger_id'] for e in events]
    try:
        # 规则 id 是动态的（真建规则），所以按**标的**对齐事件与下发参数
        content_by_symbol = {e['symbol']: _card_content(kwargs)
                             for e, kwargs in zip(events, facade.calls)}
        # 叫了的（过门动作 / 规则本来就是 L2）→ 有该行
        assert '升级原因' in content_by_symbol['600001.SH']
        assert '升级原因' in content_by_symbol['600003.SH']
        # 没叫的（观察类 / 消息类）→ 不多这一行（理由归落库）
        assert '升级原因' not in content_by_symbol['600002.SH']
        assert '升级原因' not in content_by_symbol['600004.SH']
        # 渲染判据与域层判据同源（同一函数）
        assert escalation_reason_line({'escalation_code': EscalationCode.OBSERVE_INTENT}) is None
    finally:
        with get_engine().begin() as conn:
            conn.execute(text('delete from quant.watch_triggers where id = any(:ids)'), {'ids': ids})


# ── 结构判据（本需求判据 2 / 判据 6）──────────────────────────────────
#: 允许出现 `trigger_level == 'L2'` 的文件 —— **都必须说明为什么它不是"叫不叫"的判定**。
#: 新增条目必须是有意的决定：这份清单就是"第二处独立判定"的防线。
#: 注意：**唯一裁决出口**（escalation_verdict）不在这份名单里 —— 它判定的是归一化后的
#: `level` 变量（`str(level).strip().upper() == 'L2'`），不匹配本正则；换句话说，
#: 这份名单列的是"**除出口之外**还在比较 L2 的地方"，它们必须都不是判定。
ALLOWED_L2_SITES = {
    'domain/watch/services/level_resolver.py': '级别 → P0–P3 映射，不决定叫不叫',
    'application/notification/notification_facade.py': '按**已定级别**选渠道/优先级（路由，非判定）',
    'application/services/watch_engine/notifier.py': '按已定级别选 notify_mode（路由，非判定）',
}
_L2_PAT = re.compile(r"trigger_level[^\n]{0,20}==\s*['\"]L2['\"]")


def test_no_second_independent_l2_wake_judgement():
    hits = {}
    for root in ('application', 'domain'):
        for dirpath, _dirs, files in os.walk(os.path.join(REPO, root)):
            if '__pycache__' in dirpath:
                continue
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, REPO)
                text = open(path, encoding='utf-8').read()
                if _L2_PAT.search(text):
                    hits[rel] = len(_L2_PAT.findall(text))
    assert hits, '判据失效（一个命中都没有说明正则写坏了）'
    unexpected = {k: v for k, v in hits.items() if k not in ALLOWED_L2_SITES}
    assert not unexpected, unexpected
    stale = {k for k in ALLOWED_L2_SITES if k not in hits}
    assert not stale, ('白名单里这些文件已不再命中 —— 说明判定点已迁走，'
                       '白名单该同步（否则它变成虚假的防线）：%s' % sorted(stale))


def test_stale_removed_path_text_is_gone():
    """已删除的历史升级路径不得再被写成现行判据（本需求判据 6）。"""
    offenders = []
    for root in ('application', 'domain', 'docs/architecture'):
        for dirpath, _dirs, files in os.walk(os.path.join(REPO, root)):
            if '__pycache__' in dirpath:
                continue
            for name in files:
                if not name.endswith(('.py', '.md')):
                    continue
                text = open(os.path.join(dirpath, name), encoding='utf-8').read()
                if '触发频率异常' in text or '触发频率升级' in text:
                    offenders.append(os.path.relpath(os.path.join(dirpath, name), REPO))
    assert not offenders, offenders
