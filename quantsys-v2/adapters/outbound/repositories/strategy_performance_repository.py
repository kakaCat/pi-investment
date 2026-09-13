"""
Strategy Performance Repository - 策略表现记录

2026-08-04 恢复说明：ORM 重构（8f06ae1 系）曾把本仓储换成指向
quant.strategy_performances（复数，仅 id+created_at）的空壳 stub，
create/get_statistics 等全部丢失，导致 StrategyWeightAdjuster 动态权重、
ExperienceAccumulator 经验积累、StrategyRotationEngine 轮换评估静默退化。
现按归档仓库 6281332 的旧实现恢复，指向真实表 quant.strategy_performance（单数）。
对外保留 StrategyPerformanceORMRepository 别名（调用方均用此名）。

2026-08-18 WP-3 迁移：移除 BaseRepository 继承，改用 db_cursor() 现取现还连接。

2026-09-14（w-32314d00，REQ-24e15d B4-c3-d）：改名不副实——文件叫 ORM Repository
却全程 db_cursor()+裸 SQL（7 处 cursor.execute）。本轮真正落 ORM：新建
StrategyPerformance 映射真实表（14 列，含 market_style），全部方法走 session。
"""
from datetime import date
from typing import List, Dict, Optional

import structlog
from sqlalchemy import (
    Column, Date, DateTime, Integer, Numeric, String, Text, case, cast, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class StrategyPerformance(Base):
    """quant.strategy_performance（单数表）—— 策略表现记录"""
    __tablename__ = 'strategy_performance'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=False)
    signal_date = Column(Date, nullable=False)
    entry_price = Column(Numeric, nullable=False)
    exit_price = Column(Numeric)
    pnl_pct = Column(Numeric)
    holding_days = Column(Integer, default=0)
    scenario_tags = Column(JSONB)
    params_snapshot = Column(JSONB)
    source = Column(String(20), default='paper')
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    market_style = Column(String(20))


def _record_to_dict(record: StrategyPerformance) -> Dict:
    """ORM 行 → dict（键序与旧 SELECT * / RETURNING * 一致）"""
    return {c.name: getattr(record, c.name) for c in StrategyPerformance.__table__.columns}


class StrategyPerformanceRepository(BaseORMRepository[StrategyPerformance]):
    """策略表现 Repository（quant.strategy_performance 表）"""

    model = StrategyPerformance

    def __init__(self, db_connection=None):
        """db_connection 参数仅为向后兼容保留（忽略）。session 由 scoped_session 现取。"""
        super().__init__()

    def close(self):
        """兼容旧调用方的 no-op（连接不再由实例持有）。"""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    # ==================== 创建方法 ====================

    def create(
        self,
        strategy_name: str,
        symbol: str,
        signal_date: date,
        entry_price: float,
        exit_price: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        holding_days: int = 0,
        scenario_tags: Optional[List[str]] = None,
        params_snapshot: Optional[Dict] = None,
        source: str = 'paper'
    ) -> Dict:
        """
        创建策略表现记录

        Args:
            strategy_name: 策略名称
            symbol: 标的代码
            signal_date: 信号日期
            entry_price: 入场价格
            exit_price: 出场价格（可选）
            pnl_pct: 盈亏百分比（可选）
            holding_days: 持仓天数
            scenario_tags: 场景标签列表
            params_snapshot: 参数快照
            source: 来源 ('paper' 或 'live')

        Returns:
            创建的记录（全部 14 列，对齐旧 RETURNING *）
        """
        try:
            record = StrategyPerformance(
                strategy_name=strategy_name,
                symbol=symbol,
                signal_date=signal_date,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=pnl_pct,
                holding_days=holding_days,
                scenario_tags=scenario_tags,
                params_snapshot=params_snapshot,
                source=source,
            )
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            return _record_to_dict(record)
        except Exception:
            self._safe_rollback()
            raise

    # ==================== 更新方法 ====================

    def update_exit(
        self,
        record_id: int,
        exit_price: float,
        holding_days: int
    ) -> Optional[Dict]:
        """
        更新出场价格和盈亏

        Args:
            record_id: 记录ID
            exit_price: 出场价格
            holding_days: 持仓天数

        Returns:
            更新后的记录
        """
        try:
            record = (
                self.session.query(StrategyPerformance)
                .filter(StrategyPerformance.id == record_id)
                .first()
            )
            if not record:
                return None

            entry_price = float(record.entry_price)
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            record.exit_price = exit_price
            record.pnl_pct = pnl_pct
            record.holding_days = holding_days
            # 旧 SQL 用 CURRENT_TIMESTAMP（服务端时钟）；now() 在 PG 里同为事务时间戳
            record.updated_at = func.now()

            self.session.commit()
            self.session.refresh(record)
            return _record_to_dict(record)
        except Exception:
            self._safe_rollback()
            raise

    # ==================== 查询方法 ====================

    def get_by_strategy_and_symbol(
        self,
        strategy_name: str,
        symbol: str,
        source: Optional[str] = None
    ) -> List[Dict]:
        """
        按策略和标的查询

        Args:
            strategy_name: 策略名称
            symbol: 标的代码
            source: 来源筛选（可选）

        Returns:
            记录列表
        """
        query = self.session.query(StrategyPerformance).filter(
            StrategyPerformance.strategy_name == strategy_name,
            StrategyPerformance.symbol == symbol,
        )
        if source:
            query = query.filter(StrategyPerformance.source == source)
        records = query.order_by(StrategyPerformance.signal_date.desc()).all()
        return [_record_to_dict(r) for r in records]

    def get_recent(
        self,
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        获取最近N条记录

        Args:
            strategy_name: 策略名称筛选（可选）
            symbol: 标的筛选（可选）
            limit: 返回数量

        Returns:
            记录列表
        """
        query = self.session.query(StrategyPerformance)
        if strategy_name:
            query = query.filter(StrategyPerformance.strategy_name == strategy_name)
        if symbol:
            query = query.filter(StrategyPerformance.symbol == symbol)
        records = (
            query.order_by(StrategyPerformance.signal_date.desc())
            .limit(limit)
            .all()
        )
        return [_record_to_dict(r) for r in records]

    def get_by_scenario_tag(self, tag: str) -> List[Dict]:
        """
        按场景标签查询

        Args:
            tag: 场景标签

        Returns:
            包含该标签的记录列表

        注：旧 SQL 是 scenario_tags::text LIKE %s（取值绑定参数）；ORM 用
        cast(jsonb AS TEXT).like(绑定参数)，语义一致（含子串匹配）。
        """
        records = (
            self.session.query(StrategyPerformance)
            .filter(cast(StrategyPerformance.scenario_tags, Text).like(f'%{tag}%'))
            .order_by(StrategyPerformance.signal_date.desc())
            .all()
        )
        return [_record_to_dict(r) for r in records]

    # ==================== 统计方法 ====================

    def get_statistics(
        self,
        strategy_name: str,
        symbol: Optional[str] = None,
        source: Optional[str] = None
    ) -> Optional[Dict]:
        """
        获取策略统计数据

        Args:
            strategy_name: 策略名称
            symbol: 标的筛选（可选）
            source: 来源筛选（可选）

        Returns:
            统计数据（含 total_trades/win_trades/avg_pnl_pct/win_rate 等）；
            无已平仓记录时返回 None
        """
        query = self.session.query(
            func.count().label('total_trades'),
            func.sum(case((StrategyPerformance.pnl_pct > 0, 1), else_=0)).label('win_trades'),
            func.sum(case((StrategyPerformance.pnl_pct <= 0, 1), else_=0)).label('loss_trades'),
            func.avg(StrategyPerformance.pnl_pct).label('avg_pnl_pct'),
            func.avg(StrategyPerformance.holding_days).label('avg_holding_days'),
            func.max(StrategyPerformance.pnl_pct).label('max_pnl_pct'),
            func.min(StrategyPerformance.pnl_pct).label('min_pnl_pct'),
        ).filter(
            StrategyPerformance.strategy_name == strategy_name,
            StrategyPerformance.exit_price.isnot(None),
        )
        if symbol:
            query = query.filter(StrategyPerformance.symbol == symbol)
        if source:
            query = query.filter(StrategyPerformance.source == source)

        result = query.one()
        stats = dict(result._mapping)

        if stats.get('total_trades') == 0:
            return None

        # 转换 Decimal 为 float
        for key in ['avg_pnl_pct', 'avg_holding_days', 'max_pnl_pct', 'min_pnl_pct']:
            if stats.get(key) is not None:
                stats[key] = float(stats[key])

        stats['win_rate'] = (stats['win_trades'] / stats['total_trades']) * 100 if stats['total_trades'] > 0 else 0

        return stats


# 兼容别名：调用方（order_service / strategy_weight_adjuster /
# experience_accumulator / strategy_rotation_engine）均使用 ORM 命名
StrategyPerformanceORMRepository = StrategyPerformanceRepository

__all__ = ['StrategyPerformanceRepository', 'StrategyPerformanceORMRepository']
