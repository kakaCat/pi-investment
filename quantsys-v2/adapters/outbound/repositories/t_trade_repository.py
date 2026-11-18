from typing import Any, Dict, List, Optional

from infrastructure.persistence.orm.models import SimulationTrade
from infrastructure.persistence.orm.models.t_trade import TTradeCycle
from qs_trading.domain.trading.t_trade_cycle import ACTIVE_STATUSES


class TTradeRepository:
    def __init__(self, session=None, simulation_repo=None):
        if session is None:
            if simulation_repo is None:
                from adapters.outbound.repositories.simulation_repository import (
                    SimulationORMRepository,
                )

                simulation_repo = SimulationORMRepository()
            session = simulation_repo.session
        self.session = session

    def create(self, values: Dict[str, Any]) -> TTradeCycle:
        cycle = TTradeCycle(**values)
        self.session.add(cycle)
        self.session.flush()
        return cycle

    def get(self, cycle_id: int, *, for_update: bool = False) -> Optional[TTradeCycle]:
        query = self.session.query(TTradeCycle).filter_by(id=int(cycle_id))
        if for_update:
            query = query.with_for_update()
        return query.first()

    def find_active(self, account: str, symbol: str, *, for_update: bool = False):
        query = self.session.query(TTradeCycle).filter_by(
            account=account, symbol=symbol
        ).filter(TTradeCycle.status.in_(ACTIVE_STATUSES))
        if for_update:
            query = query.with_for_update()
        return query.first()

    def list_cycles(
        self, *, account: Optional[str] = None, status: Optional[str] = None,
        limit: int = 100,
    ) -> List[TTradeCycle]:
        query = self.session.query(TTradeCycle)
        if account:
            query = query.filter_by(account=account)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(TTradeCycle.id.desc()).limit(min(max(int(limit), 1), 500)).all()

    def get_trade(self, trade_id: int) -> Optional[SimulationTrade]:
        return self.session.query(SimulationTrade).filter_by(id=int(trade_id)).first()

    def trade_in_use(self, trade_id: int) -> bool:
        return (
            self.session.query(TTradeCycle.id)
            .filter(
                (TTradeCycle.sell_trade_id == int(trade_id))
                | (TTradeCycle.buyback_trade_id == int(trade_id))
            )
            .first()
            is not None
        )

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
