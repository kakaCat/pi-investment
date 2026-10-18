"""V2 统一骨架一致性（REQ-261016155500-4f2a wt:messaging:3，2026-10-16）

守护命题：WATCH_MSG_V2 开时，**同一 variables 无论有无级别字段**，经
WatchTriggeredFormatter 出的是统一渲染器的同一份四段式骨架——消灭格式清单的
"分级卡/旧意图卡两套版式漂移"（调研 §4 根因三）。
"""
from qs_notification.domain.models.notification import Notification, NotificationType
from qs_notification.infrastructure.formatters.feishu_formatters import WatchTriggeredFormatter


def _notification(**variables):
    base = dict(symbol="601600", name="中铝国际", price=26.57,
                change_pct=-2.35, intent="exit_stop", account="agent_brain",
                lifecycle_stage="holding", context="按宪法第 4 条清仓",
                message="下破止损线 26.88",
                action_params={'action': 'sell', 'reference_price': 26.88,
                               'position_pct': 100, 'invalidation': '收盘前未执行'},
                rule_id=119, notify_mode='direct')
    base.update(variables)
    return Notification(notification_type=NotificationType.WATCH_TRIGGERED,
                        title="t", content="c", variables=base)


def _content(payload):
    return payload["card"]["elements"][0]["text"]["content"]


def test_with_and_without_level_same_skeleton():
    """同一 variables：带级别（分级链）与不带级别（旧链）出同一份四段骨架。"""
    with_level = _content(WatchTriggeredFormatter().format(
        _notification(watch_level='P2')))
    without_level = _content(WatchTriggeredFormatter().format(_notification()))
    assert with_level == without_level
    for sec in ('**事实**', '**意义**', '**建议动作**', '**重估条件**'):
        assert sec in with_level
    # 建议动作来自 action_params（结构化指引优先）
    assert '卖出' in with_level and '¥26.88' in with_level
    assert '收盘前未执行' in with_level


def test_escalation_reason_present_in_card():
    """格式清单 #3：升级原因在统一骨架中必显（旧分级路径曾静默丢失）。"""
    content = _content(WatchTriggeredFormatter().format(
        _notification(watch_level='P1', escalation_reason='涨跌幅 ≥5% 自动升级')))
    assert '**升级**：涨跌幅 ≥5% 自动升级' in content
    assert content.split('\n')[0] != ''  # P1 无 @所有人 首行


def test_intent_label_once_in_body():
    """格式清单 #9：意图标签在正文只出现一次（标题栏在 header，不在 elements 内）。"""
    content = _content(WatchTriggeredFormatter().format(_notification()))
    assert content.count('🛑 止损盯盘') == 1


def test_p0_red_mentions_all_and_no_stop_emoji_prefix():
    """格式清单 #7：P0 前缀是 🚨（🛑 只属于 exit_stop 意图标签，不双义）。"""
    payload = WatchTriggeredFormatter().format(_notification(watch_level='P0'))
    assert payload["card"]["header"]["template"] == "red"
    content = _content(payload)
    assert '所有人' in content.split('\n')[0]           # @所有人 首行保留
    assert payload["card"]["header"]["title"]["content"].startswith('🚨 ')


def test_unknown_level_no_internal_leak():
    """格式清单 #11：未知级别静默按 P2 渲染，不向外露"未知级别…按 P2 处理"内部文案。"""
    payload = WatchTriggeredFormatter().format(_notification(watch_level='XX'))
    assert payload["card"]["header"]["template"] == "blue"
    assert '未知级别' not in _content(payload)


def test_no_level_alias_field_supported():
    """level 与 watch_level 字段名等价（统一骨架下自然成立）。"""
    a = _content(WatchTriggeredFormatter().format(_notification(watch_level='P1')))
    b = _content(WatchTriggeredFormatter().format(_notification(level='P1')))
    assert a == b
