"""介入记账（REQ-f08def P4，2026-09-11，w-c8cae280）

职责：把"agent 被唤醒介入多少次、为什么介入、结果如何、花了多少"落库。

为什么必须落库（实测缺陷）：介入判据的每日预算原用进程内存计数——今天重启一次就清零重计，
escalated 计数冲到 18，远超预算 8，预算形同虚设。落库后才谈得上"成本与利润一致"。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class InterventionLedger:
    """介入记账（应用层薄封装：策略在此，持久化交给 IWatchInterventionRepository 端口）"""

    def __init__(self, repo=None):
        # 端口注入（ADR-001）：持久化由 IWatchInterventionRepository 适配器负责
        self.repo = repo


    def count_today(self) -> int:
        """当日介入次数（预算门用）。走 IWatchInterventionRepository 端口。"""
        if self.repo is None:
            return 0
        return self.repo.count_today()

    def record(self, symbol: str, intent=None, rule_id=None, trigger_kind: str = "price",
               outcome: str = "escalated", trigger_ids=None, tokens=None,
               cost_yuan: float = 0.0, decision_audit_id=None) -> None:
        """落一条介入记录（委托端口；失败由适配器兜底，不阻塞主流程）"""
        if self.repo is None:
            return
        self.repo.record(symbol=symbol, intent=intent, rule_id=rule_id,
                         trigger_kind=trigger_kind, outcome=outcome,
                         trigger_ids=trigger_ids, tokens=tokens,
                         cost_yuan=cost_yuan, decision_audit_id=decision_audit_id)

    def summary_today(self):
        """当日概览（单位唤醒产出 = 有价值动作 ÷ 介入次数）"""
        if self.repo is None:
            return {"interventions_today": 0, "by_outcome": {}, "valuable_actions": 0,
                    "yield_per_wake": None}
        return self.repo.summary_today()

