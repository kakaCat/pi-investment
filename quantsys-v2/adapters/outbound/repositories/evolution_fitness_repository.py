"""Evolution Fitness ORM Repository - evolution_fitness 表访问

表 DDL 见 infrastructure/persistence/migrations/add_evolution_fitness_table.sql。
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

import structlog
from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class EvolutionFitness(Base):
    __tablename__ = 'evolution_fitness'
    __table_args__ = (
        UniqueConstraint('account_name', 'window_end', 'window_days',
                         name='evolution_fitness_account_date_key'),
        {'schema': 'quant'},
    )

    id = Column(Integer, primary_key=True)
    account_name = Column(String(50), nullable=False)
    window_end = Column(Date, nullable=False)
    window_days = Column(Integer, nullable=False, default=20)
    up_capture = Column(Numeric(10, 4))
    down_capture = Column(Numeric(10, 4))
    fitness = Column(Numeric(10, 4))
    up_days = Column(Integer, nullable=False, default=0)
    down_days = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default='ok')
    computed_at = Column(DateTime, nullable=False, default=datetime.now)


class EvolutionFitnessORMRepository(BaseORMRepository[EvolutionFitness]):
    model = EvolutionFitness

    def upsert_fitness(
        self,
        account_name: str,
        window_end: date,
        up_capture: Optional[float],
        down_capture: Optional[float],
        fitness: Optional[float],
        up_days: int,
        down_days: int,
        status: str,
        window_days: int = 20,
    ) -> None:
        """按 (account_name, window_end, window_days) 幂等 upsert"""
        row = (
            self.session.query(EvolutionFitness)
            .filter_by(account_name=account_name, window_end=window_end, window_days=window_days)
            .first()
        )
        if row is None:
            row = EvolutionFitness(account_name=account_name, window_end=window_end,
                                   window_days=window_days)
            self.session.add(row)
        row.up_capture = up_capture
        row.down_capture = down_capture
        row.fitness = fitness
        row.up_days = up_days
        row.down_days = down_days
        row.status = status
        row.computed_at = datetime.now()
        self.session.commit()

    def get_leaderboard(
        self, window_end: date, window_days: int = 20, include_non_ok: bool = False
    ) -> List[Dict[str, Any]]:
        """fitness 降序排行；默认只含 status='ok' 的行"""
        q = self.session.query(EvolutionFitness).filter_by(
            window_end=window_end, window_days=window_days)
        if not include_non_ok:
            q = q.filter_by(status='ok')
        rows = q.order_by(EvolutionFitness.fitness.desc().nullslast()).all()
        return [
            {
                'account_name': r.account_name,
                'window_end': r.window_end.isoformat(),
                'up_capture': float(r.up_capture) if r.up_capture is not None else None,
                'down_capture': float(r.down_capture) if r.down_capture is not None else None,
                'fitness': float(r.fitness) if r.fitness is not None else None,
                'up_days': r.up_days,
                'down_days': r.down_days,
                'status': r.status,
            }
            for r in rows
        ]

    def get_latest_window_end(self, window_days: int = 20) -> Optional[date]:
        row = (
            self.session.query(EvolutionFitness.window_end)
            .filter_by(window_days=window_days)
            .order_by(EvolutionFitness.window_end.desc())
            .first()
        )
        return row[0] if row else None

    def delete_by_accounts(self, account_names: Sequence[str]) -> None:
        """测试清理用：按账户名批量删除"""
        self.session.query(EvolutionFitness).filter(
            EvolutionFitness.account_name.in_(list(account_names))
        ).delete(synchronize_session=False)
        self.session.commit()
