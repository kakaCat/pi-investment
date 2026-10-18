"""规则指引完整性 lint（REQ-261016155500-4f2a，2026-10-16）

「缺指引」的权威判据（纯函数，无 I/O）：四要素全空——
  1. action_params        结构化操作指引（动作/参考价/仓位/失效条件）
  2. next_action_hint     「下一步」自由文本建议
  3. intent               意图标注（entry/exit_stop/...）
  4. action_hint.action_on_trigger   旧版动作声明

命中即视为「无主规则」（watch_level_templates.py:150 的兜底文案"未标注意图"）。
命中规则的触发消息无法渲染「建议动作」块 → 由补全闭环派待办给 agent 回填。
"""
import json
from typing import Any


def _action_hint_of(rule: Any) -> dict:
    ah = getattr(rule, 'action_hint', None)
    if isinstance(ah, str):
        try:
            ah = json.loads(ah)
        except Exception:  # noqa: BLE001 - 解析失败按空处理
            ah = None
    return ah if isinstance(ah, dict) else {}


def _action_params_of(rule: Any) -> dict:
    ap = getattr(rule, 'action_params', None)
    if isinstance(ap, str):
        try:
            ap = json.loads(ap)
        except Exception:  # noqa: BLE001
            ap = None
    return ap if isinstance(ap, dict) else {}


def is_missing_guidance(rule: Any) -> bool:
    """四要素是否全空（布尔判定，单一事实源）。"""
    if not (getattr(rule, 'enabled', True)):
        return False  # 只 lint 启用规则
    ap = _action_params_of(rule)
    if ap and any(v not in (None, '', [], {}) for v in ap.values()):
        return False
    if (getattr(rule, 'next_action_hint', None) or '').strip():
        return False
    if (getattr(rule, 'intent', None) or '').strip():
        return False
    if (_action_hint_of(rule).get('action_on_trigger') or '').strip():
        return False
    return True


def guidance_state(rule: Any) -> dict:
    """缺哪些要素（展示/排查用；is_missing_guidance 为真时四项全 True）。"""
    ap = _action_params_of(rule)
    return {
        'missing_action_params': not (ap and any(
            v not in (None, '', [], {}) for v in ap.values())),
        'missing_next_action_hint': not (getattr(rule, 'next_action_hint', None) or '').strip(),
        'missing_intent': not (getattr(rule, 'intent', None) or '').strip(),
        'missing_action_on_trigger': not (
            _action_hint_of(rule).get('action_on_trigger') or '').strip(),
    }
