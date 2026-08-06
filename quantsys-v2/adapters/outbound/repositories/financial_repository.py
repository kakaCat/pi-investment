"""
Financial ORM Repository - 财务报表仓储

修复记录：2026-07-19 重建
  - 原 stub 表名错误（financials）且未实现抽象方法 get_financial_data，无法实例化
  - 实际数据分布在 quant.income_statements / quant.balance_sheets 两张表
  - 补齐 get_income_statements / get_balance_sheets / get_financial_data
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IFinancialRepository
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class IncomeStatement(Base):
    __tablename__ = 'income_statements'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    report_date = Column(Date, nullable=False)
    period_type = Column(String, nullable=False)
    revenue = Column(Float)
    operating_revenue = Column(Float)
    operating_cost = Column(Float)
    gross_profit = Column(Float)
    gross_margin = Column(Float)
    operating_profit = Column(Float)
    total_profit = Column(Float)
    net_profit = Column(Float)
    net_profit_parent = Column(Float)
    eps = Column(Float)
    eps_diluted = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class BalanceSheet(Base):
    __tablename__ = 'balance_sheets'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    report_date = Column(Date, nullable=False)
    period_type = Column(String, nullable=False)
    total_assets = Column(Float)
    current_assets = Column(Float)
    non_current_assets = Column(Float)
    total_liabilities = Column(Float)
    current_liabilities = Column(Float)
    non_current_liabilities = Column(Float)
    total_equity = Column(Float)
    parent_equity = Column(Float)
    debt_ratio = Column(Float)
    current_ratio = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


def _row_to_dict(row, date_fields=('report_date',), dt_fields=('created_at', 'updated_at')) -> Dict[str, Any]:
    result = {}
    for col in row.__table__.columns:
        value = getattr(row, col.name)
        if value is None:
            result[col.name] = None
        elif col.name in date_fields:
            result[col.name] = value.isoformat()
        elif col.name in dt_fields:
            result[col.name] = value.isoformat(sep=' ')
        else:
            result[col.name] = value
    return result


class FinancialORMRepository(BaseORMRepository[IncomeStatement], IFinancialRepository):
    """财务报表仓储（利润表 + 资产负债表）"""

    model = IncomeStatement  # 主模型（BaseORMRepository 要求）

    # ---------- 接口方法 ----------

    def get_financial_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """接口方法：获取最新年度财务数据（利润表 + 资产负债表合并）"""
        income = self.get_income_statements(symbol, period_type='Y', limit=1)
        balance = self.get_balance_sheets(symbol, period_type='Y', limit=1)
        if not income and not balance:
            return None
        return {
            'income': income[0] if income else None,
            'balance': balance[0] if balance else None,
        }

    # ---------- 业务方法 ----------

    def get_income_statements(self, symbol: str, period_type: str = 'Y',
                              limit: int = 5) -> List[Dict[str, Any]]:
        """查询利润表（按报告期倒序）"""
        try:
            rows = (self.session.query(IncomeStatement)
                    .filter(IncomeStatement.symbol == symbol,
                            IncomeStatement.period_type == period_type)
                    .order_by(IncomeStatement.report_date.desc())
                    .limit(limit)
                    .all())
            return [_row_to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error querying income statements for {symbol}: {e}")
            return []

    def get_balance_sheets(self, symbol: str, period_type: str = 'Y',
                           limit: int = 5) -> List[Dict[str, Any]]:
        """查询资产负债表（按报告期倒序）"""
        try:
            rows = (self.session.query(BalanceSheet)
                    .filter(BalanceSheet.symbol == symbol,
                            BalanceSheet.period_type == period_type)
                    .order_by(BalanceSheet.report_date.desc())
                    .limit(limit)
                    .all())
            return [_row_to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error querying balance sheets for {symbol}: {e}")
            return []

    def batch_get_quarterly_margins(
        self, symbols: List[str], quarters: int = 8
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量查询多只股票近 N 个季度利润表（用于周期/成长分类）

        Args:
            symbols: 股票代码列表
            quarters: 每股最多返回季度数（默认 8）

        Returns:
            {symbol: [income_dict, ...]}，按 report_date 倒序，仅 period_type='Q'
        """
        if not symbols:
            return {}
        try:
            rows = (self.session.query(IncomeStatement)
                    .filter(IncomeStatement.symbol.in_(symbols),
                            IncomeStatement.period_type == 'Q')
                    .order_by(IncomeStatement.symbol,
                              IncomeStatement.report_date.desc())
                    .all())
            result: Dict[str, List[Dict[str, Any]]] = {s: [] for s in symbols}
            for r in rows:
                lst = result.get(r.symbol)
                if lst is not None and len(lst) < quarters:
                    lst.append(_row_to_dict(r))
            return result
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error batch querying quarterly margins: {e}")
            return {s: [] for s in symbols}

    def upsert_income_statements(self, records: List[Dict[str, Any]]) -> int:
        """批量 upsert 利润表记录（按 symbol+report_date+period_type 去重）

        Args:
            records: [{symbol, report_date, period_type, revenue, gross_margin,
                       net_profit, operating_cost, gross_profit, ...}]

        Returns:
            写入条数
        """
        if not records:
            return 0
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            now = datetime.now()
            cols = ('symbol', 'report_date', 'period_type', 'revenue',
                    'operating_revenue', 'operating_cost', 'gross_profit',
                    'gross_margin', 'operating_profit', 'total_profit',
                    'net_profit', 'net_profit_parent', 'eps', 'eps_diluted')
            rows = []
            for r in records:
                row = {k: r.get(k) for k in cols if r.get(k) is not None}
                row['updated_at'] = now
                rows.append(row)

            stmt = pg_insert(IncomeStatement).values(rows)
            update_cols = {c: getattr(stmt.excluded, c) for c in
                           ('revenue', 'operating_revenue', 'operating_cost',
                            'gross_profit', 'gross_margin', 'operating_profit',
                            'total_profit', 'net_profit', 'net_profit_parent',
                            'eps', 'eps_diluted', 'updated_at')}
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol', 'report_date', 'period_type'],
                set_=update_cols,
            )
            self.session.execute(stmt)
            self.session.commit()
            return len(rows)
        except SQLAlchemyError as e:
            logger.error(f"Error upserting income statements: {e}")
            self.session.rollback()
            return 0

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []


# 兼容旧命名
FinancialRepository = FinancialORMRepository

__all__ = ['FinancialORMRepository', 'FinancialRepository',
           'IncomeStatement', 'BalanceSheet']
