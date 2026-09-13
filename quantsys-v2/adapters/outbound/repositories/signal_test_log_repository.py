"""信号测试日志仓储（quant.signal_test_log）。

2026-09-14（w-32314d00，REQ-24e15d B3-b）：9 处读写原先全部内联在
application/services/signal_test_log.py 里（含运行时 DDL、三处 f-string 拼 WHERE 的聚合查询、
以及手工游标生命周期）。本仓储收口后，服务层只保留业务判定（盈亏计算、胜负口径）与日志。

刻意保持的两个语义：
1. **建表时机不变**：服务构造时仍确保表存在（原为裸 DDL，现走 metadata.create_all
   的 checkfirst=True，等价且幂等）。
2. **筛选条件组合方式不变**：strategy_name / action / symbol / status / 日期区间
   仍是"给了才加条件"，且**列表查询与聚合查询共用同一套条件构造**（原代码里是各写一遍）。
"""
from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Float, case, func

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import SignalTestRecord

logger = logging.getLogger(__name__)

__all__ = ['SignalTestLogRepository']

_DATE_FIELDS = ('signal_date', 'verify_date', 'created_at', 'updated_at')


class SignalTestLogRepository(BaseORMRepository[SignalTestRecord]):
    """信号测试日志读写。"""

    model = SignalTestRecord

    # ---------------- 表管理 ----------------

    def create_table_if_missing(self) -> None:
        """确保表存在（幂等）。原为服务里的一段裸 CREATE TABLE IF NOT EXISTS。"""
        from infrastructure.persistence.orm.base import Base
        from infrastructure.persistence.database.engine import get_engine

        Base.metadata.create_all(
            bind=get_engine(), tables=[SignalTestRecord.__table__], checkfirst=True)

    # ---------------- 写入 ----------------

    def insert_signal(self, values: Dict[str, Any]) -> int:
        """插入一条信号，返回 id。"""
        obj = SignalTestRecord(
            symbol=values['symbol'],
            name=values.get('name', ''),
            strategy_name=values['strategy_name'],
            signal_date=values['signal_date'],
            action=values['action'],
            confidence=values.get('confidence', 0.0),
            signal_price=values.get('signal_price'),
            entry_price=values.get('entry_price'),
            stop_loss=values.get('stop_loss'),
            reason=values.get('reason', ''),
            details=values.get('details') or {},
        )
        self.session.add(obj)
        self.session.commit()
        return int(obj.id)

    def mark_verified(
        self,
        record_id: int,
        verify_date: _date,
        current_price: float,
        pnl_pct: float,
        hit_stop_loss: bool,
        holding_days: int,
    ) -> None:
        """把一条 pending 记录标记为 verified 并落验证结果。"""
        self.session.query(SignalTestRecord).filter(
            SignalTestRecord.id == record_id
        ).update({
            'status': 'verified',
            'verify_date': verify_date,
            'current_price': current_price,
            'pnl_pct': pnl_pct,
            'hit_stop_loss': hit_stop_loss,
            'holding_days': holding_days,
            'updated_at': datetime.now(),
        }, synchronize_session=False)

    # ---------------- 查询 ----------------

    @staticmethod
    def _to_dict(obj, stringify_dates: bool = True) -> Dict[str, Any]:
        """ORM 对象 → dict。

        stringify_dates：**内部消费方必须传 False**。原实现用 RealDictCursor 拿到的是
        datetime.date，verify_pending 直接对它做日期减法（date.today() - signal_date）；
        若统一转成字符串，那处算术会 TypeError（实测踩到）。
        API 面向调用方（get_records）则要字符串，故默认 True。
        """
        d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        if stringify_dates:
            for f in _DATE_FIELDS:
                if d.get(f):
                    d[f] = str(d[f])
        return d

    def list_pending(self, cutoff_date: _date) -> List[Dict[str, Any]]:
        """待验证的买入信号（signal_date <= cutoff，按日期倒序）。

        ⚠️ 日期字段**保持原生 date**（调用方 verify_pending 要对它做日期算术）。
        """
        try:
            rows = (
                self.session.query(SignalTestRecord)
                .filter(SignalTestRecord.status == 'pending')
                .filter(SignalTestRecord.signal_date <= cutoff_date)
                .filter(SignalTestRecord.action == 'buy')
                .order_by(SignalTestRecord.signal_date.desc())
                .all()
            )
            return [self._to_dict(r, stringify_dates=False) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing pending signals: {e}")
            return []

    @staticmethod
    def _conditions(
        strategy_name: Optional[str] = None,
        action: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List:
        conds: List = []
        if strategy_name:
            conds.append(SignalTestRecord.strategy_name == strategy_name)
        if action:
            conds.append(SignalTestRecord.action == action)
        if symbol:
            conds.append(SignalTestRecord.symbol == symbol)
        if status:
            conds.append(SignalTestRecord.status == status)
        if start_date:
            conds.append(SignalTestRecord.signal_date >= start_date)
        if end_date:
            conds.append(SignalTestRecord.signal_date <= end_date)
        return conds

    def list_records(
        self,
        page: int = 1,
        page_size: int = 20,
        strategy_name: Optional[str] = None,
        action: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页列表，返回 (records, total)。"""
        conds = self._conditions(strategy_name, action, symbol, status)
        try:
            q = self.session.query(SignalTestRecord)
            for c in conds:
                q = q.filter(c)
            total = q.count()
            rows = (
                q.order_by(SignalTestRecord.created_at.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
                .all()
            )
            return [self._to_dict(r) for r in rows], int(total)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing signal records: {e}")
            return [], 0

    def get_paper_stats(self, strategy_name: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """纸面测试统计（已验证信号的总数/均值/极值/盈利笔数）。

        2026-09-14（w-32314d00，REQ-24e15d B3-b）：原实现在
        application/services/experience_accumulator.py 里用 `signal_log._get_conn()`
        + f-string 拼 WHERE 执行。**该私有访问器已随本批移除**，故此处一并收口
        （否则经验积累服务会直接 AttributeError）。
        """
        conds = self._conditions(strategy_name=strategy_name, symbol=symbol)
        conds.append(SignalTestRecord.status == 'verified')
        try:
            row = (
                self.session.query(
                    func.count().label('verified_trades'),
                    func.avg(SignalTestRecord.pnl_pct).label('avg_pnl'),
                    func.max(SignalTestRecord.pnl_pct).label('max_pnl'),
                    func.min(SignalTestRecord.pnl_pct).label('min_pnl'),
                    func.sum(case((SignalTestRecord.pnl_pct > 0, 1), else_=0)).label('win_trades'),
                )
                .filter(*conds)
                .one()
            )
            n = int(row.verified_trades or 0)
            if n == 0:
                return {'verified_trades': 0, 'avg_pnl_pct': 0.0, 'win_rate': 0.0}
            return {
                'verified_trades': n,
                'avg_pnl_pct': float(row.avg_pnl or 0),
                'max_pnl_pct': float(row.max_pnl or 0),
                'min_pnl_pct': float(row.min_pnl or 0),
                'win_trades': int(row.win_trades or 0),
                'win_rate': (int(row.win_trades or 0) / n * 100),
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting paper stats: {e}")
            return {'verified_trades': 0, 'avg_pnl_pct': 0.0, 'win_rate': 0.0}

    def list_verified_strategy_symbol_pairs(self) -> List[tuple]:
        """所有"已验证"信号的 (strategy_name, symbol) 去重组合。

        2026-09-14（w-32314d00，REQ-24e15d B3-b）：同 get_paper_stats，原走
        experience_accumulator 里的 signal_log._get_conn()。
        """
        try:
            rows = (
                self.session.query(
                    SignalTestRecord.strategy_name, SignalTestRecord.symbol
                )
                .filter(SignalTestRecord.status == 'verified')
                .distinct()
                .all()
            )
            return [(r[0], r[1]) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing verified pairs: {e}")
            return []

    # ---------------- 统计 ----------------

    @staticmethod
    def _win_rate_expr():
        # 与原 SQL 的 SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) 等价
        return (func.sum(case((SignalTestRecord.pnl_pct > 0, 1), else_=0)).cast(Float)
                / func.count())

    def get_overall_stats(
        self,
        strategy_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """已验证信号的总体统计（总数/均值/极值/胜率/止损率/平均持仓天数）。"""
        conds = self._conditions(strategy_name=strategy_name,
                                 start_date=start_date, end_date=end_date)
        conds.append(SignalTestRecord.status == 'verified')
        try:
            row = (
                self.session.query(
                    func.count().label('total'),
                    func.avg(SignalTestRecord.pnl_pct).label('avg_pnl'),
                    func.max(SignalTestRecord.pnl_pct).label('max_pnl'),
                    func.min(SignalTestRecord.pnl_pct).label('max_loss'),
                    func.avg(SignalTestRecord.holding_days).label('avg_days'),
                    self._win_rate_expr().label('win_rate'),
                    (func.sum(case((SignalTestRecord.hit_stop_loss.is_(True), 1), else_=0)).cast(Float)
                     / func.count()).label('stop_loss_rate'),
                )
                .filter(*conds)
                .one()
            )
            return {
                'total': int(row.total or 0),
                'avg_pnl': float(row.avg_pnl or 0),
                'max_pnl': float(row.max_pnl or 0),
                'max_loss': float(row.max_loss or 0),
                'avg_days': float(row.avg_days or 0),
                'win_rate': float(row.win_rate or 0),
                'stop_loss_rate': float(row.stop_loss_rate or 0),
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting signal stats: {e}")
            return {'total': 0, 'avg_pnl': 0.0, 'max_pnl': 0.0, 'max_loss': 0.0,
                    'avg_days': 0.0, 'win_rate': 0.0, 'stop_loss_rate': 0.0}

    def _grouped(self, group_key: str, strategy_name, start_date, end_date, limit):
        """按月（group_key='month'）或按策略（'strategy_name'）聚合。

        两个口径共用同一段取数逻辑——原代码里是两段几乎一样的 f-string SQL。
        """
        if group_key == 'month':
            group_expr = func.to_char(SignalTestRecord.signal_date, 'YYYY-MM')
            order_expr = group_expr.desc()
        else:
            group_expr = SignalTestRecord.strategy_name
            order_expr = group_expr.asc()
        conds = self._conditions(strategy_name=strategy_name,
                                 start_date=start_date, end_date=end_date)
        conds.append(SignalTestRecord.status == 'verified')
        try:
            q = (
                self.session.query(
                    group_expr.label(group_key),
                    func.count().label('count'),
                    func.avg(SignalTestRecord.pnl_pct).label('avg_pnl'),
                    self._win_rate_expr().label('win_rate'),
                )
                .filter(*conds)
                .group_by(group_expr)
                .order_by(order_expr)
            )
            if limit:
                q = q.limit(limit)
            return [
                {
                    group_key: r._mapping[group_key],
                    'count': int(r.count or 0),
                    'avg_pnl': float(r.avg_pnl or 0),
                    'win_rate': float(r.win_rate or 0),
                }
                for r in q.all()
            ]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in grouped signal stats ({group_key}): {e}")
            return []

    def get_monthly_breakdown(self, strategy_name=None, start_date=None,
                              end_date=None, limit: int = 12) -> List[Dict[str, Any]]:
        """按月聚合（最近 limit 个月）。"""
        return self._grouped('month', strategy_name, start_date, end_date, limit)

    def get_by_strategy(self, strategy_name=None, start_date=None,
                        end_date=None) -> List[Dict[str, Any]]:
        """按策略聚合。"""
        return self._grouped('strategy_name', strategy_name, start_date, end_date, None)
