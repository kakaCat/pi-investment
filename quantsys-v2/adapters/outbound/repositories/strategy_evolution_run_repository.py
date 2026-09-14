"""策略进化引擎 ORM Repository - evolution_strategy_runs 表访问

表 DDL 见 infrastructure/persistence/migrations/add_evolution_strategy_runs_table.sql
（RFC 012 P1，2026-09-03）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class EvolutionStrategyRun(Base):
    __tablename__ = 'evolution_strategy_runs'
    __table_args__ = ({'schema': 'quant'},)

    id = Column(Integer, primary_key=True)
    run_id = Column(String(64), nullable=False)
    strategy_id = Column(Integer, nullable=False)
    symbol = Column(String(20))
    variant = Column(Integer, nullable=False, default=0)
    variant_key = Column(Text, nullable=False)
    params = Column(JSONB, nullable=False, default=dict)
    genome_run_id = Column(String(64))
    code_diff = Column(Text)
    fitness = Column(Float)
    metrics = Column(JSONB)
    kline_window = Column(String(40))
    mode = Column(String(20), nullable=False, default='full')
    initial_cash = Column(Float)
    status = Column(String(20), nullable=False, default='ok')  # ok / degraded
    degraded_reason = Column(Text)
    computed_at = Column(DateTime, nullable=False, default=datetime.now)


class StrategyEvolutionRunORMRepository(BaseORMRepository[EvolutionStrategyRun]):
    """evolution_strategy_runs 读写（RFC 012 P1 真实进化结果）。"""

    model = EvolutionStrategyRun

    def record_batch(self, rows: List[Dict[str, Any]]) -> int:
        """批量落库一次 run 的变体行（含 base 对照组与 degraded 行）。"""
        if not rows:
            return 0
        for r in rows:
            row = EvolutionStrategyRun(
                run_id=str(r['run_id']),
                strategy_id=int(r['strategy_id']),
                symbol=r.get('symbol'),
                variant=int(r.get('variant', 0)),
                variant_key=str(r.get('variant_key') or ''),
                params=r.get('params') or {},
                genome_run_id=r.get('genome_run_id'),
                code_diff=r.get('code_diff'),
                fitness=r.get('fitness'),
                metrics=r.get('metrics'),
                kline_window=r.get('kline_window'),
                mode=str(r.get('mode') or 'full'),
                initial_cash=r.get('initial_cash'),
                status=str(r.get('status') or 'ok'),
                degraded_reason=r.get('degraded_reason'),
                computed_at=datetime.now(),
            )
            self.session.add(row)
        self.session.commit()
        return len(rows)

    def get_runs(self, strategy_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """策略最近进化 leaderboard 行：每 run 一条 = fitness 最优变体行（含 params）。

        fitness NULL（整批 degraded 的 run）时取该 run 最近一条 degraded 行，
        让 leaderboard 同时暴露"进化过但诚实失败"的记录。时间倒序、limit 限制 run 数。
        """
        # 2026-09-14（REQ-24e15d B4-c5）：由 Core text() 裸 SQL 改为 ORM/Core 表达式，
        # 口径逐字保留：内层 ROW_NUMBER() OVER (PARTITION BY run_id
        # ORDER BY fitness DESC NULLS LAST, computed_at DESC)，外层 rn = 1、
        # ORDER BY computed_at DESC、LIMIT :lim。
        # 注：row_number() 不看窗口帧（无 rows= 子句），故不涉及 PRECEDING/FOLLOWING 的帧语义坑。
        _rn = func.row_number().over(
            partition_by=EvolutionStrategyRun.run_id,
            order_by=[
                EvolutionStrategyRun.fitness.desc().nullslast(),
                EvolutionStrategyRun.computed_at.desc(),
            ],
        ).label('rn')
        ranked = (
            select(EvolutionStrategyRun, _rn)
            .where(EvolutionStrategyRun.strategy_id == int(strategy_id))
            .subquery()
        )
        # 把实体映射到子查询列（ranked.id / ranked.run_id / …），保证下面 _to_dict 拿到的
        # 仍是带完整映射属性的行对象（与原来的 SELECT * 行一一对应；多出的 rn 列被忽略）。
        row_source = aliased(EvolutionStrategyRun, ranked)
        rows = self.session.execute(
            select(row_source)
            .where(ranked.c.rn == 1)
            .order_by(ranked.c.computed_at.desc())
            .limit(limit)
        ).scalars().all()
        return [self._to_dict(r) for r in rows]

    def get_run(self, run_id: str) -> List[Dict[str, Any]]:
        """按 run_id 取整批变体行（含 base/degraded，按 variant 升序）。"""
        rows = (
            self.session.query(EvolutionStrategyRun)
            .filter_by(run_id=str(run_id))
            .order_by(EvolutionStrategyRun.variant.asc())
            .all()
        )
        return [self._to_dict(r) for r in rows]

    def latest_fitness(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """策略最近一次成功的进化结果（fitness 非空取 computed_at 最新行）。"""
        row = (
            self.session.query(EvolutionStrategyRun)
            .filter(
                EvolutionStrategyRun.strategy_id == int(strategy_id),
                EvolutionStrategyRun.fitness.isnot(None),
            )
            .order_by(EvolutionStrategyRun.computed_at.desc())
            .first()
        )
        return self._to_dict(row) if row else None

    @staticmethod
    def _to_dict(r: EvolutionStrategyRun) -> Dict[str, Any]:
        return {
            'id': r.id,
            'run_id': r.run_id,
            'strategy_id': r.strategy_id,
            'symbol': r.symbol,
            'variant': r.variant,
            'variant_key': r.variant_key,
            'params': r.params,
            'fitness': float(r.fitness) if r.fitness is not None else None,
            'metrics': r.metrics,
            'kline_window': r.kline_window,
            'mode': r.mode,
            'status': r.status,
            'degraded_reason': r.degraded_reason,
            'computed_at': r.computed_at.isoformat() if r.computed_at else None,
        }

    def delete_by_run_ids(self, run_ids: List[str]) -> None:
        """测试清理用：按 run_id 批量删除"""
        if not run_ids:
            return
        self.session.query(EvolutionStrategyRun).filter(
            EvolutionStrategyRun.run_id.in_(run_ids)
        ).delete(synchronize_session=False)
        self.session.commit()
