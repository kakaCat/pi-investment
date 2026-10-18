"""渠道按级别渲染接线（REQ-c9f899 t12 §6-项1）。

可失败性：
  · 带级别 → 必须走 watch_level_templates（P0 红卡 / @ 用户 / red header）；
  · 不带级别 → 必须退回旧 WatchTriggeredFormatter（含旧特征句），非分级通知不受影响；
  · level 与 watch_level 两个字段名都支持（兼容分流口径）；
  · 未知级别 → P2 兜底且卡片内含显式标注（不静默降级）。

2026-10-16（REQ-261016155500-4f2a wt:messaging:3）：WATCH_MSG_V2 默认开后，本文件的
旧骨架断言通过 autouse fixture 强制关 V2 运行——本文件守护的是**灰度回退路径**
（V2 关闭时旧渲染必须原样可用）；V2 开启时的统一骨架由
test_unified_render_consistency.py 守护。
"""
import pytest

from domain.notification.models.notification import Notification, NotificationType
from infrastructure.notification.formatters.feishu_formatters import WatchTriggeredFormatter
from infrastructure.notification.formatters.watch_level_templates import render_watch_variables


@pytest.fixture(autouse=True)
def _force_legacy_render(monkeypatch):
    """本文件全部用例强制走旧渲染链（守护 V2 关闭的回退路径）。"""
    from infrastructure.notification.formatters import watch_message_renderer
    monkeypatch.setattr(watch_message_renderer, 'MSG_V2_ENABLED', False)


def _notification(**variables):
    base = dict(symbol="601600", name="中铝国际", price=26.57,
                message="下破止损线 26.88")
    base.update(variables)
    return Notification(notification_type=NotificationType.WATCH_TRIGGERED,
                        title="盯盘触发 - 601600",
                        content="下破止损线 26.88", variables=base)


def _content(payload):
    return payload["card"]["elements"][0]["text"]["content"]


def test_level_payload_renders_p0_card():
    payload = WatchTriggeredFormatter().format(_notification(
        watch_level="P0", intent="exit_stop", account="agent_brain", rule_id=119,
        context="按宪法第 4 条清仓"))
    content = _content(payload)
    first = content.split(chr(10))[0]
    assert "所有人" in first                      # P0 必须 @ 用户（REQ-ad0a FR-5）
    # REQ-ad0a t2：P0 首行=@所有人，标的/现价/动作在意图骨架内
    assert "601600" in content and "26.57" in content and "立即止损" in content
    assert "🛑 止损盯盘｜中铝国际（601600）" in content
    assert payload["card"]["header"]["template"] == "red"


def test_no_level_uses_legacy_renderer():
    """无级别 → 旧渲染（不改既有非分级通知的行为）"""
    payload = WatchTriggeredFormatter().format(_notification())
    content = _content(payload)
    assert "这条提醒为了" in content               # 旧渲染特征句
    assert "触发条件" not in content


def test_level_alias_field_supported():
    payload = WatchTriggeredFormatter().format(
        _notification(level="P1", intent="entry"))
    header = payload["card"]["header"]["title"]["content"]
    assert "P1 待决策" in header
    assert payload["card"]["header"]["template"] == "orange"


def test_render_watch_variables_unknown_level_marks_fallback():
    payload = render_watch_variables({"symbol": "600000", "price": 10.0,
                                      "watch_level": "PX"})
    content = _content(payload)
    assert "未知级别" in content and "PX" in content
    assert payload["card"]["header"]["template"] == "blue"