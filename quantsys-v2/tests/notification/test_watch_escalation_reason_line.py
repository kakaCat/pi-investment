"""卡面「升级原因」行测试（REQ-261007133807-eda6 t9 · FR-3）

守四件事：
1) **两条渲染路径都得写**（旧渲染 `WatchTriggeredFormatter` + 分级渲染 `render_watch_variables`）
   —— 只补一条会出现"有时有理由、有时没有"；
2) 两条路径**同形**（同一组变量喂进去，升级原因行逐字相同）；
3) 三种形态：码+理由 → 路径标签｜理由；只有码 → 路径标签；都没有 → **不渲染该行**（不臆造）；
4) 行序：在「处置」之后、「下一步」之前（不打断 c392 已裁定的四段阅读动线）。

值对象层（`TriggerPayload` → variables）的透传也在这里锁：卡面能不能显示，
首先取决于变量有没有被带出来。
"""
from types import SimpleNamespace

from application.services.watch_engine.dto import TriggerPayload
from domain.notification.models.notification import Notification, NotificationType
from domain.watch.services.escalation_verdict import EscalationCode
from infrastructure.notification.formatters.feishu_formatters import (
    WatchTriggeredFormatter, escalation_reason_line,
)
from infrastructure.notification.formatters.watch_level_templates import (
    _escalation_line, render_watch_variables,
)

REASON = '涨跌幅 -6.10% 达到阈值 5.0%'


def _variables(**overrides):
    base = dict(
        symbol='600519.SH', name='贵州茅台', price=1500.0,
        message='现价 1500 ≤ 阈值 1520（下破）', intent='entry',
        account='agent_brain', lifecycle_stage='tracking', rule_id=7,
        trigger_level='L2', closed_loop=False, sender_id='v2-watch@test#1',
        escalation_code=EscalationCode.ANOMALY_CHANGE_PCT,
        escalation_reason=REASON,
    )
    base.update(overrides)
    return base


def _notification(variables):
    return Notification(
        notification_type=NotificationType.WATCH_TRIGGERED, title='t', content='',
        variables=variables,
    )


def _content(payload):
    return payload['card']['elements'][0]['text']['content']


# ── 两条路径都写 + 同形 ────────────────────────────────────────────────
def test_both_render_paths_emit_the_same_reason_line():
    vars_ = _variables()
    old_content = _content(WatchTriggeredFormatter().format(_notification(vars_)))
    graded_content = _content(render_watch_variables(dict(vars_, watch_level='P1')))
    line = escalation_reason_line(vars_)
    assert line == '**升级原因**：异常波动｜%s' % REASON
    assert line in old_content, '旧渲染路径必须写升级原因'
    assert line in graded_content, '分级渲染路径必须写升级原因'


def test_code_only_shows_path_label():
    """只有码（例如规则本来就是 L2）→ 显示路径标签，不编理由。"""
    for vars_ in (_variables(escalation_reason=''),
                  _variables(escalation_code=EscalationCode.RULE_LEVEL_L2)):
        expected = '**升级原因**：%s' % EscalationCode.label_of(
            vars_.get('escalation_code') or EscalationCode.UNKNOWN)
        assert escalation_reason_line(vars_).startswith('**升级原因**：')
        assert expected in escalation_reason_line(vars_) or \
            EscalationCode.label_of(vars_.get('escalation_code', '')) in escalation_reason_line(vars_)


def test_no_reason_no_line_in_either_path():
    """都没有 → 该行**不出现**（宁缺勿造）。"""
    vars_ = _variables(escalation_code='', escalation_reason='')
    assert escalation_reason_line(vars_) is None
    assert _escalation_line(SimpleNamespace(escalation_code='', escalation_reason='')) is None
    old_content = _content(WatchTriggeredFormatter().format(_notification(vars_)))
    graded_content = _content(render_watch_variables(dict(vars_, watch_level='P1')))
    assert '升级原因' not in old_content
    assert '升级原因' not in graded_content


def test_unknown_code_shows_the_code_itself():
    """未收录码：显示码本身（事实），不臆造一句像理由的话。"""
    line = escalation_reason_line(_variables(escalation_code='SOME_NEW_CODE'))
    assert 'SOME_NEW_CODE' in line


def test_line_order_is_after_disposition_before_next_step():
    content = _content(WatchTriggeredFormatter().format(_notification(_variables())))
    assert content.index('**处置**') < content.index('**升级原因**') < content.index('**下一步**')


# ── 值对象层透传 ──────────────────────────────────────────────────────
def test_payload_carries_code_into_variables_and_omits_it_when_absent():
    payload = TriggerPayload(rule_id=7, symbol='600519.SH', name='贵州茅台', price=1500.0,
                             condition={'type': 'price_break'}, message='m',
                             escalation_reason=REASON,
                             escalation_code=EscalationCode.ANOMALY_CHANGE_PCT)
    vars_ = payload.to_notification_variables()
    assert vars_['escalation_code'] == EscalationCode.ANOMALY_CHANGE_PCT
    assert vars_['escalation_reason'] == REASON

    bare = TriggerPayload(rule_id=7, symbol='600519.SH', name='贵州茅台', price=1500.0,
                          condition={'type': 'price_break'}, message='m')
    assert 'escalation_code' not in bare.to_notification_variables()


def test_purely_additive_given_the_same_legacy_keys():
    """纯追加锁：**唯一的差别就是新增那一行**，其余逐行相同。

    注意（实测踩过）：`escalation_reason` 是**既有键**（c392 起它还驱动 `🔔 需决策 / ⚡ AI 介入`
    标签），所以"逐字相同"必须拿**同一组旧键**比——把 escalation_reason 也抠掉会改标签，
    那是既有行为，不是本次引入的差异。本次新增的键只有 `escalation_code`。
    """
    with_both = _variables()
    legacy = {k: v for k, v in with_both.items() if k != 'escalation_code'}  # 旧调用方：无新键
    lines_both = _content(WatchTriggeredFormatter().format(_notification(with_both))).splitlines()
    lines_legacy = _content(WatchTriggeredFormatter().format(_notification(legacy))).splitlines()

    def _rest(lines):
        return [l for l in lines if not l.startswith('**升级原因**')]

    # 新增键只影响「升级原因」这一行：其余逐行相同，且行数不变
    # （只有理由时也写该行——设计如此：理由是给人看的，码只是让它更完整）
    assert _rest(lines_both) == _rest(lines_legacy)
    assert len(lines_both) == len(lines_legacy)


def test_variables_without_any_explanation_key_are_byte_identical_to_no_line():
    """真·缺变量（两个键都没有）：行为 == 改造前——不产生任何新增内容。"""
    bare = {k: v for k, v in _variables().items()
            if k not in ('escalation_code', 'escalation_reason')}
    content = _content(WatchTriggeredFormatter().format(_notification(bare)))
    assert '升级原因' not in content
    graded = _content(render_watch_variables(dict(bare, watch_level='P1')))
    assert '升级原因' not in graded


def test_known_not_waking_code_hides_the_line():
    """**已知的"没叫"码**且无理由 → 不渲染（卡面是打扰物，那些理由归落库）。

    这是 t13 端到端核对时发现并收紧的语义：观察类/预算门/四道门的原因**落库可查**
    （FR-2），但不写在卡上——否则每张"知悉类"卡片都会多一行"升级原因：观察类"，
    读起来像自相矛盾（它并没有升级）。
    """
    for code in (EscalationCode.OBSERVE_INTENT, EscalationCode.BUDGET_EXHAUSTED,
                 EscalationCode.AMOUNT_BELOW_THRESHOLD, EscalationCode.DEDUPED):
        vars_ = _variables(escalation_code=code, escalation_reason='')
        assert escalation_reason_line(vars_) is None, code
        assert '升级原因' not in _content(
            WatchTriggeredFormatter().format(_notification(vars_))), code
        assert '升级原因' not in _content(
            render_watch_variables(dict(vars_, watch_level='P1'))), code


def test_waking_codes_still_show_even_without_reason():
    """**叫了 agent 的码**（含规则本来就是 L2）即便没有额外理由也显示 —— 用户要知道谁在处置。"""
    for code in (EscalationCode.RULE_LEVEL_L2, EscalationCode.GATES_PASSED_ACTION):
        vars_ = _variables(escalation_code=code, escalation_reason='')
        line = escalation_reason_line(vars_)
        assert line and EscalationCode.label_of(code) in line, code
