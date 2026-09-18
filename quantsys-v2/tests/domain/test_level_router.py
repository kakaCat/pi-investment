"""级别判定与账户路由纯函数单测（REQ-c9f899 t4）。

本文件的真值表 **就是判据本身**：改 level_resolver / owner_router 的优先级顺序、
把某个意图挪进/挪出某档，或把账户档位写反，这里必须变红（不是"跑通即通过"的烟雾测试）。

覆盖：P0/P1/P2/P3 各 ≥2 行 + 边界（无持仓的 exit_stop、无持仓的 exit_take_profit、
L2 的 trend_observe 优先级冲突、宪法级压过观察、市场/板块 scope 先于纯观察）+ SLA 映射 +
账户路由五种事实（agent 自有/用户/空/策略/未知）。
"""
import pytest

from domain.notification.policies.watch_delivery_policy import (
    AGENT_DH, AGENT_TS, AUTONOMOUS, NOT_APPLICABLE, REMIND_ONLY, WatchDeliveryPolicy,
)
from domain.watch.services.level_resolver import (
    LEVEL_SLA_SECONDS, LEVELS, P0, P1, P2, P3, resolve_level, sla_seconds_for,
)
from domain.watch.services.owner_router import (
    OWNER_AGENT, OWNER_USER, USER_OWNER_REF, OwnerRoute, route_owner,
)

# ── 级别真值表：intent, has_position, 其余入参 kwargs, 期望, 说明 ────────────────


LEVEL_TRUTH_TABLE = [
    # —— P0：宪法级 / 止损，无条件下达 ——
    ('exit_stop', False, {}, P0, '无持仓的止损仍是宪法动作（第 1 条不看持仓）'),
    ('exit_stop', True, {}, P0, '持仓的止损 = P0'),
    ('', False, {'is_constitutional': True}, P0, '宪法级（熔断/仓位超限等）不依赖 intent'),
    ('trend_observe', False, {'is_constitutional': True}, P0, '宪法级压过观察（第 1 条先于第 5 条）'),
    ('entry', False, {'is_constitutional': True}, P0, '宪法级压过买卖节点'),
    ('exit_take_profit', True, {}, P0, '持仓止盈 = 已到处置点'),
    ('exit_reduce', True, {}, P0, '持仓减仓 = 已到处置点'),

    # —— P1：买卖节点 / 规则声明 L2 ——
    ('entry', False, {}, P1, '建仓买入需有人拍板（与是否持仓无关）'),
    ('add_position', True, {}, P1, '加仓需有人拍板'),
    ('t_trade', False, {}, P1, '做 T 需有人拍板'),
    ('trend_observe', False, {'trigger_level': 'L2'}, P1, '优先级冲突：L2 先于观察 → 观察也须拍板'),
    ('', False, {'is_governance': True, 'trigger_level': 'L2'}, P1, 'L2 先于治理项'),

    # —— P3：治理项 / 纯观察（无 scope）——
    ('trend_observe', False, {}, P3, '纯观察仅归档'),
    ('trend_observe', False, {'scope': 'market'}, P2, '市场 scope 先于纯观察 → 知悉'),
    ('', False, {'is_governance': True}, P3, '治理项进归档汇总'),
    ('', False, {'is_governance': True, 'scope': 'sector'}, P3, '治理项优先于板块 scope'),

    # —— P2：市场/板块知悉 + 兜底 ——
    ('exit_take_profit', False, {}, P2, '无持仓的止盈不命中第 2 条 → 知悉'),
    ('exit_reduce', False, {}, P2, '无持仓的减仓同理'),
    ('', False, {}, P2, '无意图无标记 → 兜底知悉'),
    (None, None, {}, P2, 'None 入参不抛错，落兜底'),
    ('', False, {'scope': 'market'}, P2, '市场级知悉'),
    ('', False, {'scope': 'sector'}, P2, '板块级知悉'),
]


@pytest.mark.parametrize('intent,has_position,kwargs,expected,why',
                         LEVEL_TRUTH_TABLE,
                         ids=[f'{r[0] or "None"}-{r[1]}-{r[3]}-{r[4][:14]}' for r in LEVEL_TRUTH_TABLE])
def test_level_truth_table(intent, has_position, kwargs, expected, why):
    assert resolve_level(intent, has_position, **kwargs) == expected, why


def test_level_is_closed_set_for_any_input():
    """机器判定必须封闭：任意输入都只能返回 P0–P3，绝不 None/未知档。"""
    for intent in ('', 'entry', 'exit_stop', 'trend_observe', 'nonsense', None):
        for pos in (True, False, None):
            for kwargs in ({}, {'is_constitutional': True}, {'trigger_level': 'L2'},
                           {'scope': 'market'}, {'is_governance': True}):
                assert resolve_level(intent, pos, **kwargs) in LEVELS


# ── action_on_trigger 归一（intent 为空时的兼容路径）───────────────────────────


def test_intent_empty_derives_from_action_on_trigger():
    """声明 buy/sell 但没写 intent 的规则不能被静默降级（与 disposition.intent_of 同源）"""
    assert resolve_level('', False, action_on_trigger='buy') == P1
    assert resolve_level('', True, action_on_trigger='sell') == P0   # sell → exit_reduce + 持仓
    assert resolve_level('', False, action_on_trigger='observe') == P3


def test_explicit_intent_beats_action_on_trigger():
    assert resolve_level('trend_observe', False, action_on_trigger='buy') == P3


def test_unrecognizable_action_falls_to_bottom_not_p3():
    """无法识别的动作不臆造意图（既不是观察也不是交易）→ 兜底 P2"""
    assert resolve_level('', False, action_on_trigger='alert') == P2
    assert resolve_level('', False, action_on_trigger=None) == P2


# ── SLA 映射（R7）────────────────────────────────────────────────────────────


def test_level_sla_seconds_matches_requirement():
    assert LEVEL_SLA_SECONDS == {P0: 300, P1: 1800, P2: None, P3: None}


@pytest.mark.parametrize('level,expected', [
    (P0, 300), (P1, 1800), (P2, None), (P3, None),
    ('p1', 1800), (' P0 ', 300),          # 大小写/空白容错
    (None, None), ('P9', None),           # 未知级别保守 None
])
def test_sla_seconds_for(level, expected):
    assert sla_seconds_for(level) == expected


def test_p2_none_means_close_of_day_not_no_sla():
    """P2=None 是「当日收盘前」（按交易日收盘算），P3=None 才是「无 SLA」——语义靠级别区分。"""
    assert sla_seconds_for(P2) is None
    assert sla_seconds_for(P3) is None
    assert sla_seconds_for(P2) == sla_seconds_for(P3)  # 同值不同义，由级别决定


# ── 账户路由（R3/I5）─────────────────────────────────────────────────────────


def test_route_agent_owned_account_is_autonomous():
    r = route_owner('agent_brain')
    assert (r.owner_kind, r.autonomy) == (OWNER_AGENT, AUTONOMOUS)
    assert r.is_data_defect is False and r.out_of_scope is False
    assert r.owner_ref == AGENT_DH          # owner_ref 来自 WatchDeliveryPolicy.resolve，非本模块写死

    r2 = route_owner('agent_virtual')
    assert (r2.owner_kind, r2.autonomy) == (OWNER_AGENT, AUTONOMOUS)


def test_route_user_account_is_remind_only():
    r = route_owner('user_main_simulation')
    assert (r.owner_kind, r.autonomy) == (OWNER_USER, REMIND_ONLY)
    assert r.owner_ref == USER_OWNER_REF
    assert r.is_data_defect is False and r.out_of_scope is False


@pytest.mark.parametrize('blank', [None, '', '   '])
def test_route_empty_account_is_data_defect(blank):
    r = route_owner(blank)
    assert r.is_data_defect is True          # 数据缺陷路径
    assert r.owner_kind == OWNER_AGENT       # 照常叫 agent 去补归属
    assert r.autonomy == REMIND_ONLY         # 补齐前不得下单
    assert r.out_of_scope is False


@pytest.mark.parametrize('acct', ['v13_simulation', 'v14_simulation', 'v15_simulation',
                                  'chip_simulation'])
def test_route_strategy_account_out_of_scope(acct):
    r = route_owner(acct)
    assert r.out_of_scope is True              # 盯盘不介入
    assert r.autonomy == NOT_APPLICABLE        # 与 WatchDeliveryPolicy 同口径
    assert r.is_data_defect is False


def test_route_unknown_account_is_most_conservative():
    r = route_owner('agent_virtual_typo')
    assert (r.owner_kind, r.autonomy) == (OWNER_USER, REMIND_ONLY)
    assert r.is_data_defect is False and r.out_of_scope is False


def test_route_never_raises_and_always_explains():
    """路由失败兜底而非抛错（不能因账户字段脏阻断风控告警），且必须给出理由。"""
    for acct in (None, '', '  ', 'unknown_x', 'v13_simulation', 'agent_brain',
                 'user_main_simulation'):
        r = route_owner(acct)
        assert isinstance(r, OwnerRoute)
        assert r.reason.strip()


def test_route_reuses_policy_for_agent_name():
    """账户→agent 名的构造只有一个事实源：WatchDeliveryPolicy.resolve（改 policy 即跟随）。"""
    p = WatchDeliveryPolicy(accounts={'agent_brain': AGENT_TS}, account_overrides={},
                            autonomy={'agent_brain': AUTONOMOUS}, autonomy_overrides={})
    assert route_owner('agent_brain', policy=p).owner_ref == AGENT_TS
    # 默认 policy 下两个 agent 自有账户都指向默认在线 agent
    assert route_owner('agent_brain').owner_ref == WatchDeliveryPolicy().resolve(account='agent_brain')

def test_scope_outranks_observe_for_market_sector():
    """2026-09-18 修正（主 agent 独立探针发现）：

    市场/板块 scope 必须先于「纯观察 → P3」判定，否则 trend_observe + scope=sector
    会落 P3，与需求 R1「P2 = 知悉（含板块异动）」冲突——板块异动将永远进不了知悉层。
    """
    from domain.watch.services.level_resolver import resolve_level

    assert resolve_level(intent='trend_observe', has_position=False, scope='sector') == 'P2'
    assert resolve_level(intent='trend_observe', has_position=False, scope='market') == 'P2'
    assert resolve_level(intent='', has_position=False, scope='sector') == 'P2'
    # 纯观察（无 scope）仍归 P3
    assert resolve_level(intent='trend_observe', has_position=False) == 'P3'
    # 治理项不被 scope 拉高，仍为 P3（规则维护话题）
    assert resolve_level(intent='trend_observe', has_position=False,
                         is_governance=True, scope='sector') == 'P3'
