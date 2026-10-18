"""统一渲染器测试（REQ-261016155500-4f2a，2026-10-16）

验收锚点：四段完整 / 缺指引标注 / 级别颜色与 emoji 语义 / 升级与合并标注 / P0 @所有人。
"""
from domain.watch.services.watch_message import (
    ActionSection, FactSection, WatchMessage, resolve_action,
)
from qs_notification.infrastructure.formatters.watch_message_renderer import (
    LEVEL_COLORS, MSG_V2_ENABLED, render_watch_message,
)


def _msg(**over):
    base = dict(
        level='P2', symbol='002007', name='华兰生物', account='agent_brain',
        intent='exit_stop', stage='holding',
        fact=FactSection(condition_text='现价 12.21 ≤ 阈值 12.85（下破）',
                         price=12.21, change_pct=-4.97, pnl_pct=-8.0),
        purpose='浮亏触及止损线 —— 宪法要求必须执行，不得延后',
        action=ActionSection(verb='sell', text='卖出，参考价 ¥12.21，仓位 100%',
                             source='action_params'),
        reevaluate='收盘前未执行则次日开盘强制处理',
        rule_id=157, trigger_ids=(2936,), todo_id=64,
    )
    base.update(over)
    return WatchMessage(**base)


def test_full_four_sections():
    r = render_watch_message(_msg())
    assert '**事实**：' in r.text and '现价 12.21 ≤ 阈值 12.85' in r.text
    assert '**意义**：' in r.text and '宪法' in r.text
    assert '**建议动作**：' in r.text and '卖出' in r.text
    assert '**重估条件**：' in r.text
    # 事实段含价格与盈亏
    assert '¥12.21' in r.text and '-8.00%' in r.text
    # 溯源行
    assert '规则#157' in r.text and '#2936' in r.text and '待办#64' in r.text


def test_missing_guidance_annotated_not_ducked():
    action = resolve_action(action_params=None, next_action_hint=None,
                            intent=None, rule_id=256)
    assert action.verb == 'missing'
    assert '未配置操作指引' in action.text and '规则#256' in action.text
    r = render_watch_message(_msg(action=action, intent=None))
    assert '⚠️ 指引缺失' in r.text
    assert '由 agent 汇总时判断' not in r.text  # 禁止推责文案


def test_action_priority_chain():
    ap = {'action': 'sell', 'reference_price': 26.5, 'position_pct': 50}
    a1 = resolve_action(action_params=ap, next_action_hint='文本建议', intent='exit_stop')
    assert a1.source == 'action_params' and '参考价 ¥26.50' in a1.text and '50%' in a1.text
    a2 = resolve_action(action_params=None, next_action_hint='跌破 41 评估建仓',
                        intent='entry')
    assert a2.source == 'next_action_hint'
    a3 = resolve_action(action_params=None, next_action_hint='', intent='exit_stop')
    assert a3.source == 'intent_map' and '立即止损' in a3.text


def test_observe_action_requires_criterion_text():
    a = resolve_action(action_params={'action': 'observe',
                                      'observation_criterion': '放量 1.5x'})
    assert '判据：放量 1.5x' in a.text


def test_level_colors():
    assert LEVEL_COLORS['P0'] == 'red' and LEVEL_COLORS['P1'] == 'orange'
    assert LEVEL_COLORS['P2'] == 'blue' and LEVEL_COLORS['P3'] == 'grey'
    assert render_watch_message(_msg(level='P1')).color == 'orange'
    assert render_watch_message(_msg(level='oops')).color == 'blue'  # 未知级别兜底


def test_emoji_semantics():
    # 需决策：买/卖/减仓 → 🔔；observe → 直发提醒；missing → ⚠️
    assert '🔔 需决策' in render_watch_message(_msg()).text
    obs = _msg(action=ActionSection('observe', '观察', 'intent_map'),
               intent='trend_observe')
    assert '🔔' not in render_watch_message(obs).text
    assert '📡 直发提醒' in render_watch_message(obs).text
    # 🛑 只属于 exit_stop 意图标签
    assert render_watch_message(_msg()).title.startswith('🛑 止损盯盘')


def test_p0_mentions_all_and_prefix():
    r = render_watch_message(_msg(level='P0'))
    assert r.mention_all is True and r.title.startswith('🚨 ')
    assert render_watch_message(_msg(level='P2')).mention_all is False


def test_escalation_and_merge_annotations():
    r = render_watch_message(_msg(escalation_reason='涨跌幅 ≥5% 自动升级'))
    assert '**升级**：涨跌幅 ≥5% 自动升级' in r.text
    r2 = render_watch_message(_msg(merged_from_rule=128))
    assert '（与规则#128 同事件，合并展示）' in r2.title


def test_agent_mode_tag():
    r = render_watch_message(_msg(mode='agent',
                                  action=ActionSection('observe', 'x', 'intent_map')))
    assert '⚡ AI 分析版' in r.text


def test_flag_default_on():
    assert MSG_V2_ENABLED is True
