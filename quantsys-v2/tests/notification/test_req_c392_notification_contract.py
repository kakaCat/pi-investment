"""卡面契约回归锁（REQ-261007101318-c392 FR-2 / FR-3 / FR-4）。

用户 2026-10-07 收到的卡（复述）：
    盯盘触发 - 688525
    现价 192.35 ≤ 阈值 218.24（下破）
三处缺陷，逐条锁定：
  · FR-2  只有代码、没有名称——且 `name or symbol` 把"查不到名称"与"名称就是代码"混同；
  · FR-4  只有一句"下破"——买点/止损线可反读，且没有"要不要 agent 介入"的级别；
  · FR-3  没有任何来源标识——v2 与 agent-ts 共用同一飞书机器人，事后无法回答"谁发的"。
"""
import re
from types import SimpleNamespace

from domain.notification.models.notification import Notification, NotificationType
from domain.watch.models import MetricKind
from infrastructure.notification.formatters.feishu_formatters import WatchTriggeredFormatter
from infrastructure.notification.formatters.watch_level_templates import render_watch_variables
from application.notification.sender_identity import current_sender_id
from application.services.watch_engine.notifier import WatchNotifier


def _variables(**overrides):
    """与 facade 实际下发的 variables 同形（含本次新增的 FR-3/FR-4 字段）。"""
    base = dict(
        symbol='688525.SH', name='佰维存储', price=192.35,
        message='现价 192.35 ≤ 阈值 218.24（下破）', intent='exit_stop',
        account='agent_brain', lifecycle_stage='holding', rule_id=501,
        watch_level='P1', trigger_level='L1',
        closed_loop=False, sender_id='v2-watch@test-host#4321',
        next_action_hint='评估清仓 / 下移止损线 218.24', context='按宪法第 4 条处置',
    )
    base.update(overrides)
    return base


def _content(payload):
    return payload['card']['elements'][0]['text']['content']


# ── FR-2：名称 ────────────────────────────────────────────────────────────────

def test_card_shows_name_before_symbol():
    content = _content(render_watch_variables(_variables()))
    assert '佰维存储（688525）' in content, '名称必须出现在代码之前（名称在前口径）'


def test_missing_name_degrades_explicitly_not_to_bare_symbol():
    """名称缺失必须**显式标注**，不得静默退化成裸代码（旧行为就是退化成 688525）。"""
    content = _content(render_watch_variables(_variables(name='')))
    assert '名称缺失' in content
    assert '佰维存储' not in content


def test_notifier_never_passes_symbol_as_name():
    """notifier 层：名称解析不到时传给 facade 的必须是 None，而不是 symbol。

    旧写法 `name=payload.name or payload.symbol` 是用户那句
    「688525 不是股票名称」的直接来源。
    """
    captured = {}

    class _Facade:
        def send_watch_triggered(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(success=True)

    import application.services.watch_engine.notifier as notifier_mod
    original = notifier_mod._lookup_stock_name
    notifier_mod._lookup_stock_name = lambda symbol: None      # 模拟"库里查不到名称"
    try:
        rule = SimpleNamespace(id=501, symbol='688525.SH', cost_price=None, context=None,
                               intent='exit_stop', lifecycle_stage='holding',
                               next_action_hint=None, account='agent_brain',
                               scope='position', action_hint=None, conditions=[])
        quote = SimpleNamespace(price=192.35, prev_close=198.6, name=None, change_pct=None)
        result = SimpleNamespace(value=192.35, message='现价 192.35 ≤ 阈值 218.24（下破）',
                                 metric=MetricKind.PRICE, unit='元', degraded=False,
                                 distance_ratio=0.0)
        condition = {'type': 'price_break', 'params': {'price': 218.24, 'direction': 'below'}}
        WatchNotifier(trigger_repo=None, ws_url=None, notification_facade=_Facade()).notify(
            rule, condition, quote, result, level='P1', closed_loop=False)
    finally:
        notifier_mod._lookup_stock_name = original

    assert 'name' in captured
    assert captured['name'] is None, '名称解析失败必须传 None（由渲染层写「名称缺失」）'
    assert captured['closed_loop'] is False


# ── FR-4：意图 / 处置级别 / 闭环承诺 ─────────────────────────────────────────

def test_card_states_what_the_break_means_and_who_acts():
    """同一句「下破」必须写清意图与处置级别——用户问的"让卖让买"要有答案。"""
    content = _content(render_watch_variables(_variables(intent='exit_stop')))
    assert '止损盯盘' in content                     # 意图（INTENT_META）
    assert 'L1 提醒（人工判断，不唤醒 agent）' in content


def test_entry_intent_reads_differently_from_stop_loss():
    """entry（进入买区）与 exit_stop（破止损线）指向相反动作 ⇒ 卡面必须可区分。"""
    entry = _content(render_watch_variables(_variables(intent='entry')))
    stop = _content(render_watch_variables(_variables(intent='exit_stop')))
    assert entry != stop
    assert '买入跟踪' in entry
    assert '止损盯盘' in stop


def test_closed_loop_off_promises_nothing():
    """闭环未开启：**不**承诺处置入口/回执位（不给用户指向不存在的待办看板）。"""
    off = _content(render_watch_variables(_variables(closed_loop=False)))
    on = _content(render_watch_variables(_variables(closed_loop=True)))
    assert '处置入口' not in off and '处置后必有回执' not in off
    assert '处置入口' in on and '处置后必有回执' in on
    # 但意图与级别恒有（FR-4 的核心：不靠闭环开关换可读性）
    assert '止损盯盘' in off and 'L1 提醒' in off


def test_unknown_trigger_level_hides_the_line_instead_of_guessing():
    content = _content(render_watch_variables(_variables(trigger_level='')))
    assert '**处置**：' not in content, '级别未知必须隐藏该行，不许臆造'


# ── FR-3：来源标识 ───────────────────────────────────────────────────────────

def test_card_carries_sender_footer():
    content = _content(render_watch_variables(_variables()))
    assert content.rstrip().endswith('—— v2-watch@test-host#4321')


def test_sender_id_is_host_and_pid_scoped():
    """跨机靠 host、跨进程靠 pid——用户已指出"执行可能是另外一个机器执行的"。"""
    sender = current_sender_id()
    assert re.fullmatch(r'v2-watch@.+?#\d+', sender), sender


# ── 旧渲染路径（无级别）也要带名称与来源 ──────────────────────────────────────

def test_legacy_path_also_marks_missing_name_and_sender():
    payload = WatchTriggeredFormatter().format(Notification(
        notification_type=NotificationType.WATCH_TRIGGERED,
        title='盯盘触发 - 688525', content='现价 192.35 ≤ 阈值 218.24（下破）',
        variables={'symbol': '688525', 'name': '', 'price': 192.35,
                   'message': '现价 192.35 ≤ 阈值 218.24（下破）',
                   'sender_id': 'v2-watch@test-host#4321'}))
    content = _content(payload)
    assert '688525（名称缺失）' in content
    assert content.rstrip().endswith('—— v2-watch@test-host#4321')
