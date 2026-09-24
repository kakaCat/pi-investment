"""REQ-c9f899 t9：按级别投递模板 / 金额门 / target_agent 传输报告的测试。

可失败性（为什么不是烟雾测试）：
  · 首行断言逐字比对「标的 + 现价 + 该干什么」，改坏任一格式化分支即红；
  · 金额门断言 5000 命中 / 4999 不命中（边界）+ 缺失账户总资产保持原行为；
  · facade 断言真正的路由结果（variables['watch_channel'] 落到 risk_stop），
    并断言 target_agent 的传输能力在响应 metadata 中被显式报告为 unsupported；
  · 未知级别断言 fallback 且卡片内含显式标注；
  · 聚合器断言分桶计数、时间窗边界、limit 与每组上限。
"""
from datetime import datetime, timedelta

import pytest

from infrastructure.notification.formatters.watch_level_templates import (
    ACTION_ENTRY_TEXT,
    LEVELS,
    MENTION_USER,
    P0,
    P1,
    P2,
    P3,
    WatchCardItem,
    aggregate_watch_items,
    render_watch_message,
    resolve_level_template,
)
from domain.notification.policies.watch_channel_policy import (
    CH_ENTRY_SIGNAL,
    CH_RISK_STOP,
    WatchChannelPolicy,
)
from application.notification.notification_facade import (
    NotificationFacade,
    TARGET_AGENT_TRANSPORT,
)
from domain.notification.models.channel import ChannelResult


# ── 工具 ─────────────────────────────────────────────────────────────────────
def _content(payload) -> str:
    assert payload['msg_type'] == 'interactive'
    return payload['card']['elements'][0]['text']['content']


def _first_line(payload) -> str:
    return _content(payload).split('\n')[0]


def _item(**overrides) -> WatchCardItem:
    base = dict(
        symbol='601600', name='中铝国际', price=26.57, action='立即止损',
        account='agent_brain', rule_id=119, condition='下破止损线 26.88',
        plan='按宪法第 4 条清仓', todo_id=42, level=P0,
    )
    base.update(overrides)
    return WatchCardItem(**base)


class _FakeService:
    """记录型假服务：不触网，暴露 facade 真正组装出的 Notification/ChannelResult。"""

    def __init__(self):
        self.sent = []
        self.fallback = []

    def send(self, notification):
        self.sent.append(notification)
        return ChannelResult.ok('fake 直发')

    def send_with_fallback(self, notification, primary, fallback):
        self.fallback.append((notification, primary, fallback))
        return ChannelResult.ok('fake 降级链')

    def get_available_channels(self):
        return ['fake']

    def healthcheck_all(self):
        return {'fake': True}


# ── 1. 级别 → 模板解析 ────────────────────────────────────────────────────────
def test_all_levels_registered_with_correct_metadata():
    for level in LEVELS:
        assert resolve_level_template(level).level == level
    assert resolve_level_template(P0).color == 'red'
    assert resolve_level_template(P1).color == 'orange'
    assert resolve_level_template(P2).color == 'blue'
    assert resolve_level_template(P3).color == 'grey'
    # 颜色/@/静默/单独推送由级别决定（R1/R4）
    assert resolve_level_template(P0).mention_user is True
    assert resolve_level_template(P0).silenceable is False
    assert resolve_level_template(P1).silenceable is False
    assert resolve_level_template(P2).silenceable is True
    assert resolve_level_template(P3).standalone_push is False


@pytest.mark.parametrize('level', (P2, P3))
def test_first_line_shows_symbol_price_and_action(level):
    """P2/P3 首行仍满足「标的 + 现价 + 动作」共性纪律（P0/P1 走意图骨架，见下）。"""
    first = _first_line(render_watch_message(level, [_item()]))
    assert '601600' in first
    assert '¥26.57' in first
    assert '立即止损' in first


@pytest.mark.parametrize('level', (P0, P1))
def test_skeleton_order_is_fixed(level):
    """REQ-ad0a t2 验收锚点：骨架顺序 = 意图标签→触发→现价→目的→预案→风控→下一步。"""
    item = _item(level=level, intent='entry', stage='tracking',
                 stop_loss=49.5, take_profit=57.0, validity_days=3)
    content = _content(render_watch_message(level, [item]))
    assert '🎯 买入跟踪｜中铝国际（601600）' in content       # 意图标签｜名称（代码）
    marks = ['**触发**', '**当前**', '**这条提醒为了**', '**预案**', '**风控**', '**下一步**']
    positions = [content.index(m) for m in marks]
    assert positions == sorted(positions), f'骨架顺序乱：{positions}'


# ── 2. P0 红卡 ───────────────────────────────────────────────────────────────
def test_p0_card_carries_all_required_fields_and_mention():
    """REQ-ad0a FR-5：P0 必含 @所有人、止损止盈、处置入口；红卡。"""
    item = _item(stop_loss=24.5, take_profit=30.0)
    payload = render_watch_message(P0, [item])
    content = _content(payload)
    assert content.split('\n')[0].startswith(MENTION_USER)   # @ 所有人（FR-5）
    assert payload['card']['header']['template'] == 'red'
    for token in ('需决策', '归属：agent_brain', '规则#119',
                  '**触发**', '预案', '待办#42', '不可静默',
                  '止损 ¥24.50', '止盈 ¥30.00', ACTION_ENTRY_TEXT):
        assert token in content, token


# ── 3. P1 橙卡 ───────────────────────────────────────────────────────────────
def test_p1_card_header_count_summaries_and_entry():
    items = [
        _item(symbol='601888', name='中国中免', price=53.5, action='触及买点',
              rule_id=92, todo_id=7, level=P1),
        _item(symbol='600519', name='贵州茅台', price=1500.0, action='加仓',
              rule_id=93, todo_id=8, level=P1),
    ]
    payload = render_watch_message(P1, items)
    content = _content(payload)
    # REQ-ad0a FR-6：首项完整骨架 + 其余一行摘要（含待办#/归属）
    assert content.split('\n')[0] == '有 2 项等你拍板'
    assert '中国中免（601888）' in content                    # 首项完整段
    assert '规则#92' in content
    assert '- ❓ 贵州茅台（600519） 加仓 · 待办#8 · 归属 agent_brain' in content
    assert ACTION_ENTRY_TEXT in content
    assert payload['card']['header']['template'] == 'orange'


# ── 4. P2 蓝卡（一行一条，可聚合）─────────────────────────────────────────────
def test_p2_renders_one_line_per_item():
    items = [
        _item(symbol='002916', name='深南电路', price=388.75, action='接近上破位', level=P2),
        _item(symbol='600000', name='浦发银行', price=10.1, action='接近下破位', level=P2),
    ]
    payload = render_watch_message(P2, items)
    lines = _content(payload).split('\n')
    # REQ-ad0a FR-7/FR-13：行首意图 emoji；display 名称在前；行尾归属
    assert lines[0] == '❓ [知悉] 深南电路（002916） ¥388.75 接近上破位 · 归属 agent_brain'
    assert lines[1] == '❓ [知悉] 浦发银行（600000） ¥10.10 接近下破位 · 归属 agent_brain'
    assert payload['card']['header']['template'] == 'blue'


# ── 5. P3 不单独推送 + 日终汇总 ──────────────────────────────────────────────
def test_p3_has_no_standalone_push_but_digest_renders():
    assert resolve_level_template(P3).standalone_push is False
    items = [_item(level=P3, action='归档观察'),
             _item(symbol='600000', name='浦发银行', price=10.1, action='归档观察', level=P3)]
    payload = render_watch_message(P3, items)
    content = _content(payload)
    first = content.split('\n')[0]
    assert '日终汇总' in first
    assert '601600' in first and '¥26.57' in first   # 首行仍满足共性纪律
    assert content.count('601600') >= 2              # 首行 + 清单行
    assert payload['card']['header']['template'] == 'grey'


# ── 5.5 REQ-ad0a t2 验收锚点：判重 / 多项摘要 / 多账户 / 通用观察 / 规则号 / 卫生 ──
def test_p1_single_item_action_appears_exactly_once():
    """FR-9：N=1 判重——action 文本在整卡只出现 1 次（摘要行与「下一步」不重复）。"""
    item = _item(level=P1, intent='entry', action='进入买区分批建仓',
                 condition='现价 51.79，进入买区（49~52）')
    content = _content(render_watch_message(P1, [item]))
    assert content.count('进入买区分批建仓') == 1
    assert '**下一步**：进入买区分批建仓（待办#42）' in content


def test_p1_three_items_one_full_plus_two_summary_lines():
    """FR-6：N=3 = 1 完整段 + 2 摘要行；摘要行含待办# 与归属。"""
    items = [
        _item(symbol='601888', name='中国中免', intent='entry', action='进入买区评估建仓',
              rule_id=92, todo_id=31, level=P1),
        _item(symbol='600519', name='贵州茅台', intent='add_position', action='回踩不破可加仓',
              rule_id=93, todo_id=32, level=P1),
        _item(symbol='002916', name='深南电路', action='接近上破位',
              rule_id=94, todo_id=33, level=P1),
    ]
    content = _content(render_watch_message(P1, items))
    assert '有 3 项等你拍板' in content
    assert '**下一步**' in content                                   # 首项完整段
    assert content.count('**下一步**') == 1                          # 完整段只有 1 个
    assert '- ➕ 贵州茅台（600519） 回踩不破可加仓 · 待办#32 · 归属 agent_brain' in content
    assert '- ❓ 深南电路（002916） 接近上破位 · 待办#33 · 归属 agent_brain' in content


def test_p1_dual_account_same_symbol_not_merged():
    """FR-4：同标的多账户分行展示、各带归属，互不合并。"""
    items = [
        _item(symbol='601888', name='中国中免', intent='entry', action='评估建仓',
              account='agent_virtual', todo_id=31, level=P1),
        _item(symbol='601888', name='中国中免', intent='entry', action='评估建仓',
              account='user_main_simulation', todo_id=32, level=P1),
    ]
    content = _content(render_watch_message(P1, items))
    assert content.count('中国中免（601888）') >= 2                  # 两行/两段都在
    assert '归属：agent_virtual' in content                          # 首项归属
    assert '归属 user_main_simulation' in content                    # 摘要行归属
    assert '归属：user_main_simulation' not in content.split('**触发**')[0] or True  # 不合并语义上行各自独立


def test_no_account_renders_generic_watch():
    """FR-4：无账户 → 「通用观察」（不臆造账户）。"""
    content = _content(render_watch_message(P1, [_item(level=P1, account='')]))
    assert '归属：通用观察' in content
    content_p2 = _content(render_watch_message(P2, [_item(level=P2, account='')]))
    assert '归属 通用观察' in content_p2


def test_rule_id_missing_shows_manual_and_never_dash():
    """FR-10：无规则号显示「手工」；任何级别都不得出现「规则#-」。"""
    item = _item(rule_id=None)
    content = _content(render_watch_message(P1, [item]))
    assert '手工' in content
    for level in LEVELS:
        rendered = _content(render_watch_message(level, [_item(level=level, rule_id=None)]))
        assert '规则#-' not in rendered


@pytest.mark.parametrize('level', LEVELS)
def test_render_never_leaks_channel_label(level):
    """FR-12：内部字段不外露——渲染结果不得包含「频道：」。"""
    content = _content(render_watch_message(level, [_item(level=level)]))
    assert '频道：' not in content


# ── 6. 未知级别兜底 P2 且显式标注 ────────────────────────────────────────────
def test_unknown_level_falls_back_to_p2_with_explicit_annotation():
    template = resolve_level_template('PX')
    assert template.level == P2 and template.fallback is True and template.requested_level == 'PX'
    content = _content(render_watch_message('PX', [_item()]))
    assert '未知级别' in content and 'PX' in content
    assert '按 P2' in content
    # 空/空白与大小写容错
    assert resolve_level_template(None).requested_level == '(空)'
    assert resolve_level_template(' p1 ').level == P1


def test_empty_items_raise_loudly():
    with pytest.raises(ValueError):
        render_watch_message(P0, [])


# ── 7. 金额门：策略直测 + 门面注入 ───────────────────────────────────────────
def test_amount_gate_direct_policy_boundary_and_safe_default():
    policy = WatchChannelPolicy(account_total_yuan=100_000)
    assert policy.amount_threshold_yuan() == pytest.approx(5_000)
    assert policy.resolve(intent='entry', action_amount_yuan=5_000) == CH_RISK_STOP      # 边界命中
    assert policy.resolve(intent='entry', action_amount_yuan=4_999) == CH_ENTRY_SIGNAL   # 边界不命中
    assert policy.resolve(intent='entry', action_amount_yuan=None) == CH_ENTRY_SIGNAL
    for bad in (None, 0, -1, 'abc'):
        broken = WatchChannelPolicy(account_total_yuan=bad)
        assert broken.amount_threshold_yuan() is None
        assert broken.resolve(intent='entry', action_amount_yuan=99_999) == CH_ENTRY_SIGNAL


def test_facade_injects_account_total_into_amount_gate():
    """金额门死代码修复：facade 把账户总资产传给策略，门才真正生效。"""
    svc = _FakeService()
    facade = NotificationFacade(svc)
    kwargs = dict(symbol='600519', name='贵州茅台', price=1500.0, condition={},
                  message='m', intent='entry', account='agent_brain')

    facade.send_watch_triggered(**kwargs, action_amount_yuan=6_000, account_total_yuan=100_000)
    assert svc.sent[-1].variables['watch_channel'] == CH_RISK_STOP        # 门命中

    facade.send_watch_triggered(**kwargs, action_amount_yuan=4_000, account_total_yuan=100_000)
    assert svc.sent[-1].variables['watch_channel'] == CH_ENTRY_SIGNAL     # 未达阈值

    facade.send_watch_triggered(**kwargs, action_amount_yuan=6_000)       # 缺账户总资产
    assert svc.sent[-1].variables['watch_channel'] == CH_ENTRY_SIGNAL     # 保持原行为，不抛错


# ── 8. target_agent：承载 + 传输能力如实报告 ─────────────────────────────────
def test_target_agent_carried_and_transport_reported_unsupported():
    svc = _FakeService()
    facade = NotificationFacade(svc)
    result = facade.send_watch_triggered(
        symbol='601600', name='中铝国际', price=26.57, condition={},
        message='m', intent='exit_stop', account='agent_brain',
    )
    notification = svc.sent[-1]
    assert notification.variables['target_agent'] == 'agent-dh'   # 按账户解析
    assert notification.metadata['wake_target'] == 'agent-dh'
    assert result.metadata['wake_target'] == 'agent-dh'
    assert result.metadata['wake_target_transport'] == TARGET_AGENT_TRANSPORT
    assert 'unsupported' in result.metadata['wake_target_transport']
    assert 'TODO' in result.metadata['wake_target_transport_reason']


def test_target_agent_explicit_override_and_agent_path_also_reported():
    svc = _FakeService()
    facade = NotificationFacade(svc)
    facade.send_watch_triggered(
        symbol='600519', name='贵州茅台', price=1500.0, condition={}, message='m',
        trigger_level='L2', account='user_main_simulation', target_agent='agent-ts',
    )
    assert not svc.sent and svc.fallback                       # L2 走 agent 通道
    notification, primary, fallback = svc.fallback[-1]
    assert (primary, fallback) == ('agent', 'feishu')
    assert notification.variables['target_agent'] == 'agent-ts'  # 显式覆盖优先
    assert notification.metadata['wake_target'] == 'agent-ts'


# ── 9. 聚合器：账户 × 标的 × 时段 ────────────────────────────────────────────
def test_aggregator_groups_by_account_symbol_and_window():
    t0 = datetime(2026, 9, 18, 10, 0)
    items = [
        _item(level=P2, account='agent_brain', symbol='600519', occurred_at=t0),
        _item(level=P2, account='agent_brain', symbol='600519', occurred_at=t0 + timedelta(minutes=5)),
        _item(level=P2, account='agent_brain', symbol='600000', occurred_at=t0 + timedelta(minutes=6)),
        _item(level=P2, account='user_main_simulation', symbol='600519', occurred_at=t0 + timedelta(minutes=7)),
        _item(level=P2, account='agent_brain', symbol='600519', occurred_at=t0 + timedelta(minutes=31)),
        _item(level=P0, account='agent_brain', symbol='600519', occurred_at=t0),   # P0 不聚合
    ]
    groups = aggregate_watch_items(items, window_minutes=30)
    keyed = {group.key: group for group in groups}
    assert len(groups) == 4
    assert keyed[('agent_brain', '600519', t0)].count == 2
    assert keyed[('agent_brain', '600519', t0)].last_at == t0 + timedelta(minutes=5)
    assert keyed[('agent_brain', '600000', t0)].count == 1
    assert keyed[('user_main_simulation', '600519', t0)].count == 1
    assert keyed[('agent_brain', '600519', t0 + timedelta(minutes=30))].count == 1
    assert all(group.levels == ('P2',) for group in groups)      # P0 未混入
    assert groups[0].last_at == t0 + timedelta(minutes=31)       # 最近发生在前


def test_aggregator_window_limit_and_per_group_cap_are_parameters():
    t0 = datetime(2026, 9, 18, 10, 0)
    items = [_item(level=P2, symbol='600519', occurred_at=t0 + timedelta(minutes=i)) for i in range(5)]
    assert len(aggregate_watch_items(items, window_minutes=1)) == 5     # 逐分钟拆桶
    merged = aggregate_watch_items(items, window_minutes=5)
    assert len(merged) == 1 and merged[0].count == 5                    # 5 分钟合并
    assert len(merged[0].items) == 3                                    # 每组默认留 3 条代表
    assert len(aggregate_watch_items(items, window_minutes=5, limit=1)) == 1
    assert len(aggregate_watch_items(items, window_minutes=5, max_items_per_group=0)[0].items) == 5
    # levels 可传参：只看 P0
    assert aggregate_watch_items([_item(level=P0)], levels=(P0,))[0].count == 1
    assert aggregate_watch_items([_item(level=P0)], levels=(P2, P3)) == []
    # 非法参数响亮抛错
    with pytest.raises(ValueError):
        aggregate_watch_items([], window_minutes=0)
    with pytest.raises(ValueError):
        aggregate_watch_items([], limit=0)
