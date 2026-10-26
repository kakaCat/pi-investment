"""盯盘规则合法性守卫（盯盘域）—— 用户 2026-09-11 定调

铁律：**没有账户的规则不能进入买卖。**

理由不是"技术上不能下单"，而是：无账户的买卖规则是**数据缺陷**——它会在触发时无人可执行，
或被错误地当成"只发飞书"的合法模式掩盖掉（那是 bug）。所以必须在**规则进入系统的那一刻**拦住，
在源头消灭，而不是等到触发时降级。

判据：
  · 交易类意图（TRADE_INTENTS：entry/add_position/t_trade/exit_stop/exit_take_profit/exit_reduce）
    **必须**有账户归属（linked_account 或 account）→ 否则拒绝创建/更新
  · 观察类（trend_observe 等）允许无账户（观察不需要账户）

意图推导与运行时**同源**：复用 qs_watch.domain.watch.services.disposition.intent_of，
避免"声明 buy 但没写 intent"的规则绕过校验（那种规则运行时照样会被当成 entry）。
"""
from types import SimpleNamespace
from typing import Optional

from qs_watch.domain.watch.services.disposition import TRADE_INTENT_LABELS, intent_of, is_trade_intent

#: 可接受的账户（盯盘信息必须归属其中之一）
KNOWN_ACCOUNTS = ('agent_virtual', 'agent_brain', 'v13_simulation', 'user_main_simulation')


class TradeRuleWithoutAccount(ValueError):
    """买卖规则缺账户归属（数据缺陷，拒绝入库）"""


class WatchRuleNotApplicable(ValueError):
    """策略账户不接受盯盘规则：策略账户的交易由策略引擎执行，与盯盘无关（用户 2026-09-11）"""


def guard_account_applicable(account, symbol=None) -> None:
    """盯盘适用性：策略账户（v13/v14/v15/chip 等）由策略执行，不进盯盘体系。"""
    from qs_notification.domain.policies.watch_delivery_policy import WatchDeliveryPolicy
    if account and WatchDeliveryPolicy.is_strategy_managed(account):
        raise WatchRuleNotApplicable(
            "策略账户不接受盯盘规则：%s 的交易由策略引擎执行，与盯盘无关"
            "（盯盘只服务 agent 自有账户与用户账户）。symbol=%s" % (account, symbol or '-'))


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
    """创建前校验：①策略账户不接受盯盘规则 ②买卖规则必须有账户"""
    guard_account_applicable(account, symbol)
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


class ConstitutionalRuleSilentDisable(ValueError):
    """宪法级规则（止损铁律）被无理由停用——拒绝执行（2026-10-20 用户裁定）。

    背景：300677 止损规则 #103 曾被静默停用，持仓浮亏 -19% 时保护网是断的，
    且无人知道何时、为何被关。止损规则的停用是「拆保护网」动作，必须留痕。
    """


def _field(rule, name, default=None):
    """规则字段读取：同时支持 ORM 对象与 dict 投影（仓储两条轨都在用）。

    守卫此前只认 getattr：对 dict 规则会恒取默认值——「已停用」判成「启用中」、
    宪法级 intent 判成空，闸门形同虚设。统一成一个取值口，两种形状同判据。
    """
    if isinstance(rule, dict):
        return rule.get(name, default)
    return getattr(rule, name, default)


def guard_disable_rule(rule, payload) -> None:
    """停用守卫：宪法级意图（exit_stop）的规则，enabled True→False 必须随附理由。

    理由载体：ops_notes 或 context（既有停用路径都会写 banner/注记，天然通过）；
    裸 `{'enabled': false}`（没有理由字段）一律拒绝——这只能来自「想悄悄关掉它」。
    非宪法级规则不受影响。
    """
    from qs_watch.domain.watch.services.disposition import CONSTITUTIONAL_INTENTS
    data = dict(payload or {})
    if data.get('enabled') is not False:
        return
    if _field(rule, 'enabled', True) is not True:
        return                                        # 本就停用（幂等重放）放行
    if (_field(rule, 'intent', None) or '') not in CONSTITUTIONAL_INTENTS:
        return
    has_reason = bool(data.get('ops_notes')) or bool(data.get('context'))
    if has_reason:
        return
    raise ConstitutionalRuleSilentDisable(
        '止损规则（宪法铁律）不允许无理由停用：rule_id=%s symbol=%s。'
        '请在本次更新中随附 ops_notes 或 context 说明理由（谁、为什么、替代保护是什么）。'
        % (_field(rule, 'id'), _field(rule, 'symbol')))


# ── 处置卡「不执行」→ 改规则的动作守卫（2026-10-21 · 卡 rule-change-linkage）────
#: 可落地的四类规则动作（与 application/watch_engine/disposition_engine.RuleChangeAction 同值；
#: 本模块不 import 应用层枚举——domain 不依赖 application，字符串是唯一跨层契约）。
DISPOSITION_ACTIONS = ('adjust_threshold', 'postpone', 'disable', 'retire')

#: 会把规则关掉（enabled=False）的两类动作：宪法级止损规则做它们必须随附理由
DISPOSITION_DISABLING_ACTIONS = ('disable', 'retire')


def guard_disposition_action(rule, action, *, reason=None) -> None:
    """处置卡动作落地前守卫：动作白名单 + 宪法级止损的停用/退役必须随附理由。

    为什么在应用层写库**之前**再拦一次（仓储层已有 `guard_disable_rule` 卡口）：
      · 联动会先算出要写的字段再调 `update_fields`，守卫前置可以「一行都不写」就拒绝，
        而不是写完发现理由缺失、留下半条变更（审计与规则状态不一致）；
      · 拒绝原因必须是**领域异常**（ConstitutionalRuleSilentDisable），调用方能据此
        让 agent 补理由重试，而不是当成普通参数错误吞掉。

    非关停类动作不触碰 enabled，与停用铁律无关（阈值/延期照常放行）。
    """
    action_value = str(getattr(action, 'value', action) or '').strip().lower()
    if action_value not in DISPOSITION_ACTIONS:
        raise ValueError(
            '未知的处置卡规则动作：%r（允许 %s）'
            % (action, ' / '.join(DISPOSITION_ACTIONS)))
    if action_value not in DISPOSITION_DISABLING_ACTIONS:
        return
    reason_text = str(reason or '').strip()
    # 与仓储层同一判据、同一异常：理由载体用 context（本次更新不写 context，
    # 只作为守卫输入），裸 enabled=false 且无理由 → 宪法级规则被拒。
    guard_disable_rule(rule, {'enabled': False, 'context': reason_text or None})
