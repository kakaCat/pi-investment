"""盯盘事件 → 处置 Agent 的路由策略 —— 2026-09-11，w-aebfddcd

归属：**通知域**（domain/notification/policies）。

⚠️ 铁律：**消息投递与 agent 投递是两个独立维度，禁止互相推导。**

    · WatchChannelPolicy  → **消息**发到哪个频道/群（= 用户能不能单独静音它）
                            输入：intent / scope / 金额 / 是否宪法级
    · WatchDeliveryPolicy → **谁接手处置**（哪个 agent 平台）
                            输入：账户归属（account）/ 事件分类（category）

二者不得互为输入：改一个群的静音或分组配置，绝不允许悄悄改掉"谁来处置"；
反之改了 agent 分工，也不该让消息换群。两条链各自可配、各自可测。

用户 2026-09-11 定调：「盯盘要给 agent 处理，按照分类投递 agent-ts 或者 agent-dh」，
并明确「消息和投送 agent 是 2 个内容」。

默认值与覆盖：
  · 账户优先：账户 = "这仗归谁打"的事实来源（rule.linked_account）
  · 无账户时才看事件分类：市场级/系统级这类非账户事件
  · 默认全部 → agent-dh（当前唯一在线 wake 端点）
  · 改分工只改配置，不动代码：
        WATCH_ACCOUNT_AGENT_MAP='{"v13_simulation":"agent-ts"}'
        WATCH_CATEGORY_AGENT_MAP='{"market_state":"agent-ts"}'
  · 目标不可达时投递层显式回退默认 agent 并在 payload 标注，绝不静默丢事件

纪律：路由失败（未知账户/未知分类）兜底 DEFAULT_AGENT 而非抛错——路由不该阻断风控告警。
"""
import json
import os
from typing import Dict, Optional

AGENT_DH = "agent-dh"   # DSH investment profile，wake 端点 :13080/wake
AGENT_TS = "agent-ts"   # 旧版 TS agent，wake 端点 :3002/wake（需显式拉起）

#: 可选处置 agent
WATCH_AGENTS = (AGENT_DH, AGENT_TS)

#: 兜底 agent：未知账户 / 目标不可达时的落点
DEFAULT_AGENT = AGENT_DH

#: 账户 → 处置 agent（默认全投 agent-dh；改这张表 = 改分工）
DEFAULT_AGENT_BY_ACCOUNT: Dict[str, str] = {
    "agent_virtual": AGENT_DH,
    "agent_brain": AGENT_DH,
    "user_main_simulation": AGENT_DH,
    "v13_simulation": AGENT_DH,
}

#: 事件分类 → 处置 agent（仅用于**非账户**事件：市场级 / 系统级）
DEFAULT_AGENT_BY_CATEGORY: Dict[str, str] = {
    "market": AGENT_DH,
    "sector": AGENT_DH,
    "market_state": AGENT_DH,
    "system": AGENT_DH,
    "governance": AGENT_DH,
}

ACCOUNT_MAP_ENV = "WATCH_ACCOUNT_AGENT_MAP"
CATEGORY_MAP_ENV = "WATCH_CATEGORY_AGENT_MAP"

# ── 授权等级（账户维度）：谁有权动手 ────────────────────────────────────────
# 用户 2026-09-11 定调：「agent 的账户 agent 自己操作」「用户是真身（只提醒）」。
# 即同一个 agent，对不同账户的授权不同：
#   · agent 自有账户（agent_virtual / agent_brain）→ autonomous：agent 自己操作，含下单
#   · 用户账户（user_main_simulation）→ remind_only：不得下单，只提醒 + 更新预案，
#     需要交易时用 ask_user_question 拉起用户确认
AUTONOMOUS = "autonomous"           # agent 自己操作（可下单）
REMIND_ONLY = "remind_only"         # 只提醒（不得下单）
NOT_APPLICABLE = "not_applicable"   # 盯盘不适用：策略账户由策略执行（用户 2026-09-11）

#: 策略账户：**交易由策略引擎执行，与盯盘无关**——不进盯盘投递链，也不该有盯盘规则。
#: 依据：用户 2026-09-11「策略账户 交易和盯盘没关联，是策略去执行的」；
#: 与 simulation_account.account_type='strategy' 一致（v13/v14/v15/chip）。
STRATEGY_MANAGED_ACCOUNTS = ("v13_simulation", "v14_simulation", "v15_simulation",
                             "chip_simulation", "rotation_main")

#: 账户 → 授权等级（默认表；改这张表 = 改授权。生产可按 simulation_account.account_type 校准：
#: agent=autonomous / user=remind_only / strategy=待明确，先按保守处理）
DEFAULT_AUTONOMY_BY_ACCOUNT: Dict[str, str] = {
    "agent_virtual": AUTONOMOUS,
    "agent_brain": AUTONOMOUS,
    "user_main_simulation": REMIND_ONLY,
    # 策略账户不在此表：它们走 NOT_APPLICABLE（见 STRATEGY_MANAGED_ACCOUNTS）
}

#: 兜底：未知账户 / 无账户一律最保守（只提醒）
DEFAULT_AUTONOMY = REMIND_ONLY
AUTONOMY_MAP_ENV = "WATCH_ACCOUNT_AUTONOMY_MAP"


def _parse_map(raw: Optional[str]) -> Dict[str, str]:
    """解析覆盖表；非法输入一律忽略（配置错误不该中断路由）"""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip(): str(v).strip() for k, v in data.items()
            if isinstance(v, str) and v.strip()}


class WatchDeliveryPolicy:
    """盯盘事件 → 处置 agent 的路由（无状态、纯决策）

    输入只有两个：账户归属、事件分类。**不接受也不读取消息频道码**。
    """

    def __init__(self, accounts: Optional[Dict[str, str]] = None,
                 categories: Optional[Dict[str, str]] = None,
                 account_overrides: Optional[Dict[str, str]] = None,
                 category_overrides: Optional[Dict[str, str]] = None,
                 autonomy: Optional[Dict[str, str]] = None,
                 autonomy_overrides: Optional[Dict[str, str]] = None):
        self.accounts = dict(accounts) if accounts is not None else dict(DEFAULT_AGENT_BY_ACCOUNT)
        self.categories = dict(categories) if categories is not None else dict(DEFAULT_AGENT_BY_CATEGORY)
        self.account_overrides = (dict(account_overrides) if account_overrides is not None
                                  else _parse_map(os.getenv(ACCOUNT_MAP_ENV)))
        self.category_overrides = (dict(category_overrides) if category_overrides is not None
                                   else _parse_map(os.getenv(CATEGORY_MAP_ENV)))
        self.autonomy = (dict(autonomy) if autonomy is not None
                         else dict(DEFAULT_AUTONOMY_BY_ACCOUNT))
        self.autonomy_overrides = (dict(autonomy_overrides) if autonomy_overrides is not None
                                   else _parse_map(os.getenv(AUTONOMY_MAP_ENV)))

    def resolve_autonomy(self, account: Optional[str] = None) -> str:
        """账户 → 授权等级（autonomous=agent 自己操作 / remind_only=只提醒）

        未知账户或无账户（数据缺陷）一律兜底 remind_only：**授权必须显式给予，不能默认放开**。
        """
        key = (account or "").strip()
        if key and self.is_strategy_managed(key):
            return NOT_APPLICABLE
        if key:
            for table in (self.autonomy_overrides, self.autonomy):
                level = table.get(key)
                if level in (AUTONOMOUS, REMIND_ONLY):
                    return level
        return DEFAULT_AUTONOMY

    @staticmethod
    def is_strategy_managed(account: Optional[str]) -> bool:
        """策略账户判定：交易由策略执行，盯盘不介入（投递层据此跳过，规则守卫据此拒绝建规则）"""
        return (account or "").strip() in STRATEGY_MANAGED_ACCOUNTS

    def resolve(self, account: Optional[str] = None, category: Optional[str] = None) -> str:
        """账户优先，其次事件分类，最后兜底（账户是责任归属的事实来源）"""
        key = (account or "").strip()
        if key:
            for table in (self.account_overrides, self.accounts):
                agent = table.get(key)
                if agent in WATCH_AGENTS:
                    return agent
        cat = (category or "").strip()
        if cat:
            for table in (self.category_overrides, self.categories):
                agent = table.get(cat)
                if agent in WATCH_AGENTS:
                    return agent
        return DEFAULT_AGENT
