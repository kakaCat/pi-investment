"""facade V2 正文接线测试（REQ-261016155500-4f2a wt:messaging:2，2026-10-16）

验收：WATCH_MSG_V2 开时 send_watch_triggered 的 Notification.content 即统一渲染器
产出的四段式正文（agent-os 网关裸转发路径信息完整）；action_params 直达 variables；
缺指引规则渲染 ⚠️ 标注而非推责文案。
"""
import qs_notification.application as notification_pkg
from qs_notification.domain.models.channel import ChannelResult


def _capture(monkeypatch):
    facade = notification_pkg.get_notification_facade()
    captured = []

    def fake_send(notification):
        captured.append(notification)
        return ChannelResult.ok(message='captured')

    def fake_fallback(notification, primary, fallback):
        captured.append(notification)
        return ChannelResult.ok(message='captured')

    monkeypatch.setattr(facade.service, 'send', fake_send)
    monkeypatch.setattr(facade.service, 'send_with_fallback', fake_fallback)
    return facade, captured


def _trigger(facade, **over):
    base = dict(symbol='002007', name='华兰生物', price=12.21,
                condition={'type': 'price_break', 'params': {'direction': 'below', 'price': 12.85}},
                message='现价 12.21 ≤ 阈值 12.85（下破）',
                context='区间震荡策略：跌破12.85进入低吸区，跌破12.19止损离场',
                notify_mode='direct', intent='exit_stop', lifecycle_stage='holding',
                account='agent_brain', rule_id=157, level='P2')
    base.update(over)
    return facade.send_watch_triggered(**base)


def test_content_has_four_sections_with_action_params(monkeypatch):
    facade, captured = _capture(monkeypatch)
    _trigger(facade, action_params={'action': 'sell', 'reference_price': 12.19,
                                    'position_pct': 100,
                                    'invalidation': '收盘前未执行次日开盘强制处理'})
    n = captured[0]
    assert '**事实**' in n.content and '**意义**' in n.content
    assert '**建议动作**' in n.content and '卖出' in n.content and '¥12.19' in n.content
    assert '**重估条件**' in n.content and '次日开盘强制处理' in n.content
    # 预案摘录保留（评分依据/风控不丢）
    assert '**预案**' in n.content and '低吸区' in n.content
    # 标题为意图驱动（不再是"盯盘触发 - "前缀）
    assert n.title.startswith('🛑 止损盯盘')
    # action_params 直达 variables
    assert n.variables['action_params']['action'] == 'sell'
    # 级别缺省 P2 → 蓝
    assert n.variables['watch_level'] == 'P2'


def test_missing_guidance_annotated(monkeypatch):
    facade, captured = _capture(monkeypatch)
    _trigger(facade, intent=None, action_params=None, next_action_hint=None,
             rule_id=256, context=None)
    n = captured[0]
    assert '⚠️ 指引缺失' in n.content
    assert '规则#256 未配置操作指引' in n.content
    assert '由 agent 汇总时判断' not in n.content


def test_hint_and_intent_fallback_chain(monkeypatch):
    facade, captured = _capture(monkeypatch)
    # next_action_hint 兜底
    _trigger(facade, action_params=None, next_action_hint='跌破 41.28 评估建仓',
             intent='entry', rule_id=248)
    assert '跌破 41.28 评估建仓' in captured[0].content
    # intent 映射兜底
    _trigger(facade, action_params=None, next_action_hint=None,
             intent='exit_stop', rule_id=157)
    assert '立即止损（宪法第 4 条）' in captured[1].content


def test_escalation_reason_carried(monkeypatch):
    facade, captured = _capture(monkeypatch)
    _trigger(facade, escalation_reason='涨跌幅 ≥5% 自动升级',
             action_params={'action': 'sell'})
    assert '**升级**：涨跌幅 ≥5% 自动升级' in captured[0].content
