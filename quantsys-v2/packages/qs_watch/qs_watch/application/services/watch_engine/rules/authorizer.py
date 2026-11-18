"""盯盘规则写入的共享账户授权策略。

唯一事实源仍是 ``owner_router.route_owner`` / ``WatchDeliveryPolicy``，本模块不维护
账户清单。repair 与普通 CRUD/batch 必须调用同一策略，避免同一账户在不同入口出现
不同授权语义。

默认保持 repair 的保守行为：无账户规则不允许 agent 直接修改。普通写服务只有在
已证明规则是非交易观察类时，才传 ``allow_accountless_observation=True``。
"""
from typing import Any, Optional

from qs_watch.domain.watch.ports import WatchRuleChangeUnauthorized
from qs_watch.domain.watch.services.owner_router import OWNER_USER, route_owner

USER_OPERATOR = 'user'
DEFAULT_OPERATOR = 'agent'


def authorize_rule_account(account: Optional[str], operator: Optional[str], *,
                           policy: Any = None,
                           allow_accountless_observation: bool = False):
    """按 repair 原策略授权，返回 ``OwnerRoute``；拒绝时抛领域异常（路由映射 403）。

    - ``operator=user``：用户本人确认，保持 repair 原放行语义；
    - agent：仅允许 ``autonomy=autonomous`` 且非 ``out_of_scope`` 的账户；
    - 无账户：默认拒绝 agent；仅由普通写服务为已验证的非交易观察规则显式放开。
    """
    account_value = str(account or '').strip()
    operator_value = str(operator or '').strip() or DEFAULT_OPERATOR
    route = route_owner(account_value or None, policy)
    if operator_value == USER_OPERATOR:
        return route
    if allow_accountless_observation and not account_value:
        return route
    if route.out_of_scope:
        raise WatchRuleChangeUnauthorized(
            f'账户 {account_value!r} 盯盘不介入（out_of_scope），agent 不得变更其规则：{route.reason}')
    if route.owner_kind == OWNER_USER or route.autonomy != 'autonomous':
        raise WatchRuleChangeUnauthorized(
            f'账户 {account_value!r} 的规则须用户本人确认（owner_kind={route.owner_kind}, '
            f'autonomy={route.autonomy}），agent 不得直接变更：{route.reason}')
    return route
