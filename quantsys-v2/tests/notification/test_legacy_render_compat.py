"""REQ-260924104605-ad0a t6 兼容回归：无 watch_level 的 WatchTriggered 仍旧渲染。

改版（t2 新分级模板）不得回断旧路径：不带 watch_level/level 的存量通知
（非分级 WatchTriggered、其他系统沿用旧载荷的调用方）必须继续走
feishu_formatters.WatchTriggeredFormatter 旧渲染，且旧特征结构完整。
"""
from domain.notification.models.notification import Notification, NotificationType
from infrastructure.notification.formatters.feishu_formatters import WatchTriggeredFormatter


def _notification(**variables):
    base = dict(symbol="601600", name="中铝国际", price=26.57,
                change_pct=-2.35, intent="exit_stop", account="agent_brain",
                lifecycle_stage="holding", context="按宪法第 4 条清仓",
                message="下破止损线 26.88")
    base.update(variables)
    return Notification(notification_type=NotificationType.WATCH_TRIGGERED,
                        title="盯盘触发 - 601600",
                        content="下破止损线 26.88", variables=base)


def _content(payload):
    return payload["card"]["elements"][0]["text"]["content"]


def test_legacy_render_full_skeleton_without_watch_level():
    """无 watch_level/level：旧渲染七段结构完整（意图/归属/触发/现价/目的/预案/下一步）。"""
    payload = WatchTriggeredFormatter().format(_notification())
    content = _content(payload)

    assert "🛑 止损盯盘｜中铝国际（601600）" in content      # 意图标签 + 名称（代码）
    assert "阶段：持仓中" in content
    assert "归属：agent_brain" in content
    assert "**触发**：下破止损线 26.88" in content
    assert "**当前**：¥26.57" in content
    assert "(-2.35%)" in content
    assert "**这条提醒为了**" in content                       # 旧渲染特征句
    assert "**预案**：" in content                              # L1 直发走简化预案
    assert "**下一步**" in content


def test_legacy_render_l2_shows_raw_context_plan():
    """L2/升级路径：预案为原文（不经简化器）——旧渲染的另一条分支不回断。"""
    payload = WatchTriggeredFormatter().format(_notification(trigger_level="L2"))
    content = _content(payload)
    assert "⚡ AI 介入" in content
    assert "**预案**：按宪法第 4 条清仓" in content


def test_legacy_render_no_account_falls_back_generic():
    """旧渲染的缺省归属 = 通用观察（与新模板口径一致，不为兼容留旧值）。"""
    payload = WatchTriggeredFormatter().format(_notification(account=None))
    assert "归属：通用观察" in _content(payload)


def test_legacy_render_not_hijacked_by_new_templates():
    """兼容断言的另一半：无级别载荷**不得**出现新分级模板的结构标记。"""
    payload = WatchTriggeredFormatter().format(_notification())
    content = _content(payload)
    header = payload["card"]["header"]["title"]["content"]

    assert "处置入口" not in content                          # 新模板 P0/P1 标记
    assert "不可静默" not in content                          # 新模板 P0 标记
    assert "待决策" not in header                             # 新模板 P1 header
    # 旧标题 = 意图标签 · 名称（代码）
    assert "🛑 止损盯盘 · 中铝国际（601600）" in header


def test_legacy_render_alias_fields_do_not_leak_into_new_path():
    """level 字段也是新路径分流键（level/watch_level 同口径）——带任一即走新模板，
    本用例守住「两个字段都缺才旧渲染」的边界。"""
    payload = WatchTriggeredFormatter().format(_notification(level="P2"))
    header = payload["card"]["header"]["title"]["content"]
    assert "知悉" in header or "P2" in header                 # 走了新模板
