"""盯盘待办归属路由（account → owner）—— domain 纯函数。

REQ-c9f899 不变式 I5 / 需求 R3「账户定接收者」的判据落点：一条盯盘信息「该由谁接手」
完全由**账户归属**决定，与级别判定（level_resolver）、消息频道三者正交，互不推导。

归属语义（严格照 R3/I5）：
  · agent 自有账户（agent_brain / agent_virtual）→ owner_kind='agent'，autonomy='autonomous'
        agent 可自主处置（含下单/改规则）并留痕，回执给用户知悉。
  · 用户账户（user_main_simulation）            → owner_kind='user'，autonomy='remind_only'
        用户本人处置；agent 只出建议，下单/改规则须用户确认。
  · 空账户（无归属）                             → owner_kind='agent' + autonomy='remind_only'
        **数据缺陷**：照常走闭环、照常叫 agent 去补归属（不能因缺账户就不叫 agent），
        但补齐前不得下单（is_data_defect=True 供上游优先补归属）。
  · 未知账户                                     → owner_kind='user'，autonomy='remind_only'
        未知 ≠ 空：按最保守处理（当作需人拍板），不抛错、不路由到黑洞。
  · 策略账户（v13/v14/v15/chip_simulation）      → out_of_scope=True
        交易由策略引擎执行，与盯盘无关（用户 2026-09-11）——盯盘不介入、不建待办。

⚠️ **不新造第二份账户映射表**：账户→agent 名（owner_ref）、授权等级（autonomy）、策略账户判定
全部复用 domain.notification.policies.watch_delivery_policy.WatchDeliveryPolicy
（resolve / resolve_autonomy / is_strategy_managed）；本模块只做"账户事实 → 归属结构"的翻译。

纪律：路由失败绝不抛错——未知账户兜底最保守档（remind_only），路由不该阻断风控告警。
"""
from dataclasses import dataclass
from typing import Optional

from domain.notification.policies.watch_delivery_policy import (
    AUTONOMOUS,
    REMIND_ONLY,
    WatchDeliveryPolicy,
)

#: 接手方种类（与 quant.watch_todos.owner_kind CHECK 一致）
OWNER_AGENT = 'agent'
OWNER_USER = 'user'

#: 用户接收者标识。系统只有一位真身用户（不是账户——账户单独落在 todo.account）：
#: owner_kind='user' 时 owner_ref 取此常量，表示"处置权在人身上，agent 只提醒"。
USER_OWNER_REF = 'user'


@dataclass(frozen=True)
class OwnerRoute:
    """一条盯盘信息的归属判定结果（不可变值对象，可直接落 quant.watch_todos 的路由列）。"""
    owner_kind: str
    owner_ref: str
    autonomy: str
    is_data_defect: bool
    out_of_scope: bool
    reason: str


def _is_registered_account(policy: WatchDeliveryPolicy, key: str) -> bool:
    """账户是否已在策略里登记（查 policy 的授权表本身，不复制映射内容）。

    用途仅为消息措辞（用户账户 vs 未登记账户），判定结果都走同一档最保守归属。
    """
    return key in policy.autonomy or key in policy.autonomy_overrides


def route_owner(account, policy: Optional[WatchDeliveryPolicy] = None) -> OwnerRoute:
    """账户 → 归属路由（纯函数）。owner_kind/owner_ref/autonomy/is_data_defect/out_of_scope/reason。

    归属种类由**有效授权**决定（复用 WatchDeliveryPolicy.resolve_autonomy）：
      · AUTONOMOUS  → agent 自有账户（owner_kind='agent'，owner_ref=policy.resolve 出的 agent 名）
      · 其余（remind_only / not_applicable）→ 面向用户的归属（owner_kind='user'，owner_ref='user'）
    这样「账户→agent 名」只有一个事实源（policy.resolve），本模块不写死任何 agent / 账户名。

    account：规则归属账户（rule.linked_account / account）；None/空白 = 无归属（数据缺陷路径）。
    policy ：可注入，便于测试与配置替换；缺省用默认 WatchDeliveryPolicy（含环境变量覆盖）。
    """
    policy = policy or WatchDeliveryPolicy()
    key = str(account or '').strip()

    # 空账户：数据缺陷——照常叫 agent 去补归属，但只提醒（补齐前不得下单）
    if not key:
        return OwnerRoute(
            owner_kind=OWNER_AGENT,
            owner_ref=policy.resolve(account=None),
            autonomy=REMIND_ONLY,
            is_data_defect=True,
            out_of_scope=False,
            reason='无账户归属（数据缺陷）：照常走闭环并交 agent 优先补归属；补齐前不得下单（R3）',
        )

    # 策略账户：盯盘不介入（交易由策略引擎执行）
    if policy.is_strategy_managed(key):
        return OwnerRoute(
            owner_kind=OWNER_AGENT,
            owner_ref=policy.resolve(account=key),
            autonomy=policy.resolve_autonomy(key),
            is_data_defect=False,
            out_of_scope=True,
            reason='策略账户：交易由策略引擎执行，与盯盘无关（盯盘不介入、不建待办）',
        )

    autonomy = policy.resolve_autonomy(key)

    # agent 自有账户：可自主处置（含下单/改规则），回执给用户知悉
    if autonomy == AUTONOMOUS:
        return OwnerRoute(
            owner_kind=OWNER_AGENT,
            owner_ref=policy.resolve(account=key),
            autonomy=AUTONOMOUS,
            is_data_defect=False,
            out_of_scope=False,
            reason='agent 自有账户：agent 可自主处置（含下单/改规则）并留痕，回执给用户知悉（I5/R3）',
        )

    # 用户账户 / 未登记账户：一律最保守——本人处置，agent 只提醒
    if _is_registered_account(policy, key):
        reason = '用户账户：由用户本人处置；agent 只出建议，下单/改规则须用户确认（I5/R3）'
    else:
        reason = '未登记账户：按最保守处理（视为用户账户，只提醒、不得下单），不抛错不黑洞'
    return OwnerRoute(
        owner_kind=OWNER_USER,
        owner_ref=USER_OWNER_REF,
        autonomy=REMIND_ONLY,
        is_data_defect=False,
        out_of_scope=False,
        reason=reason,
    )
