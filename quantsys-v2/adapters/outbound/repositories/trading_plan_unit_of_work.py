"""账户级计划 UnitOfWork（REQ-261026140857-c192）"""

from __future__ import annotations

from infrastructure.persistence.orm import close_session, get_session

from .account_plan_repository import AccountPlanRepository, PlanRunRepository
from .account_plan_rule_repository import AccountPlanRuleRepository


class TradingPlanUnitOfWork:
    """同一 SQLAlchemy session 承载计划 revision、item、条件和运行记录。

    服务层显式 commit；退出时未提交异常由服务 rollback，最后清理线程 session。
    """

    def __init__(self, session_factory=get_session):
        self._session_factory = session_factory
        self.session = None
        self.plans: AccountPlanRepository | None = None
        self.runs: PlanRunRepository | None = None
        self.rules: AccountPlanRuleRepository | None = None

    def __enter__(self) -> "TradingPlanUnitOfWork":
        self.session = self._session_factory()
        self.plans = AccountPlanRepository(self.session)
        self.runs = PlanRunRepository(self.session)
        self.rules = AccountPlanRuleRepository(self.session)
        return self

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            close_session()
            self.session = None
            self.plans = None
            self.runs = None
            self.rules = None
        return False
