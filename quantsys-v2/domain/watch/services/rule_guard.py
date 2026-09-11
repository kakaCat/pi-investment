"""盯盘规则合法性守卫（盯盘域）—— 用户 2026-09-11 定调

铁律：**没有账户的规则不能进入买卖。**

理由不是"技术上不能下单"，而是：无账户的买卖规则是**数据缺陷**——它会在触发时无人可执行，
或被错误地当成"只发飞书"的合法模式掩盖掉（那是 bug）。所以必须在**规则进入系统的那一刻**拦住，
在源头消灭，而不是等到触发时降级。

判据：
  · 交易类意图（TRADE_INTENTS：entry/add_position/t_trade/exit_stop/exit_take_profit/exit_reduce）
    **必须**有账户归属（linked_account 或 account）→ 否则拒绝创建/更新
  · 观察类（trend_observe 等）允许无账户（观察不需要账户）

意图推导与运行时**同源**：复用 domain.watch.services.disposition.intent_of，
避免"声明 buy 但没写 intent"的规则绕过校验（那种规则运行时照样会被当成 entry）。
"""
from types import SimpleNamespace
from typing import Optional

from domain.watch.services.disposition import TRADE_INTENT_LABELS, intent_of, is_trade_intent

#: 可接受的账户（盯盘信息必须归属其中之一）
KNOWN_ACCOUNTS = ('agent_virtual', 'agent_brain', 'v13_simulation', 'user_main_simulation')


class TradeRuleWithoutAccount(ValueError):
    """买卖规则缺账户归属（数据缺陷，拒绝入库）"""


def effective_account(rule) -> Optional[str]:
    """规则的有效账户：linked_account（投送权威字段）优先，回退 account"""
    if isinstance(rule, dict):
        return (rule.get('linked_account') or rule.get('account') or None)
    return (getattr(rule, 'linked_account', None) or getattr(rule, 'account', None) or None)


def _draft(intent=None, action_hint=None, conditions=None):
    return SimpleNamespace(intent=intent or '',
                           action_hint=action_hint or {},
                           conditions=conditions or [])


def guard_new_rule(*, intent=None, action_hint=None, conditions=None,
                   account=None, symbol=None) -> None:
    """创建前校验：买卖规则必须有账户（raise TradeRuleWithoutAccount）"""
    derived = intent_of(_draft(intent=intent, action_hint=action_hint, conditions=conditions))
    if not is_trade_intent(derived):
        return
    if str(account or '').strip():
        return
    raise TradeRuleWithoutAccount(
        "没有账户的规则不能进入买卖：意图 %s（%s）必须指定账户（%s 之一）；"
        "仅观察类规则可无账户。symbol=%s" % (
            derived, TRADE_INTENT_LABELS.get(derived, derived),
            ' / '.join(KNOWN_ACCOUNTS), symbol or '-'))


def guard_rule_change(rule, payload) -> None:
    """更新前校验：合并"改后状态"再判——不允许把观察规则改成买卖规则却不给账户，
    也不允许把已有买卖规则的账户清空（清空=把缺陷写回系统）。"""
    data = dict(payload or {})
    intent = data.get('intent', getattr(rule, 'intent', None))
    action_hint = data.get('action_hint', getattr(rule, 'action_hint', None))
    conditions = data.get('conditions', getattr(rule, 'conditions', None))
    if 'linked_account' in data or 'account' in data:
        # 显式给了账户字段：以它为准（值为空 = 清空账户 → 必须被拦）
        account = data.get('linked_account') or data.get('account') or None
    else:
        account = effective_account(rule)
    guard_new_rule(intent=intent, action_hint=action_hint, conditions=conditions,
                   account=account, symbol=getattr(rule, 'symbol', None))
