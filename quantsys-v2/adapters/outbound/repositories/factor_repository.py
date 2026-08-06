"""
因子ORM Repository

使用SQLAlchemy ORM重构的因子数据访问层

支持：
1. 因子值查询（单只/批量）
2. 因子值写入
3. 因子统计

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Dict, Optional
from datetime import date
import structlog
import polars as pl
import math

from sqlalchemy import func, and_, desc
from infrastructure.persistence.orm import BaseORMRepository
from domain.ports import IFactorRepository
from infrastructure.persistence.orm.models import FactorValue

logger = structlog.get_logger(__name__)

__all__ = ['FactorORMRepository']


class FactorORMRepository(BaseORMRepository[FactorValue], IFactorRepository):
    """因子ORM Repository

    示例用法：
        repo = FactorORMRepository()

        # 查询单只股票的因子
        factors = repo.get_factors_by_symbol('000001', '2026-01-01', '2026-06-30')

        # 查询特定因子的值
        values = repo.get_factor_values('PE', '2026-06-01')

        # 批量写入因子
        repo.batch_upsert_factors([
            {'symbol': '000001', 'factor_date': '2026-06-26', 'factor_name': 'PE', 'factor_value': 10.5},
            {'symbol': '000001', 'factor_date': '2026-06-26', 'factor_name': 'PB', 'factor_value': 1.2},
        ])
    """

    model = FactorValue

    # ==================== IFactorRepository接口实现 ====================

    def get_factor_data(
        self,
        symbol: str,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pl.DataFrame:
        """获取因子数据（IFactorRepository接口实现）"""
        try:
            query = self.session.query(FactorValue).filter(
                FactorValue.symbol == symbol
            )

            if factor_names:
                query = query.filter(FactorValue.factor_name.in_(factor_names))
            if start_date:
                query = query.filter(FactorValue.factor_date >= start_date)
            if end_date:
                query = query.filter(FactorValue.factor_date <= end_date)

            factors = query.order_by(FactorValue.factor_date.asc()).all()

            if not factors:
                return pl.DataFrame()

            rows = [{
                'symbol': f.symbol,
                'factor_date': f.factor_date,
                'factor_name': f.factor_name,
                'factor_value': f.factor_value,
            } for f in factors]

            return pl.DataFrame(rows)

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factor data for {symbol}: {e}")
            return pl.DataFrame()

    def batch_get_factors(
        self,
        symbols: List[str],
        factor_names: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, pl.DataFrame]:
        """批量获取因子数据（IFactorRepository接口实现）"""
        try:
            result = {}
            for symbol in symbols:
                result[symbol] = self.get_factor_data(
                    symbol, factor_names, start_date, end_date
                )
            return result

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error batch getting factors: {e}")
            return {symbol: pl.DataFrame() for symbol in symbols}

    def save_factor_data(self, df: pl.DataFrame) -> int:
        """保存因子数据（IFactorRepository接口实现）"""
        try:
            if df.is_empty():
                return 0

            count = 0
            for row in df.iter_rows(named=True):
                factor = FactorValue(
                    symbol=row.get('symbol'),
                    factor_date=row.get('factor_date'),
                    factor_name=row.get('factor_name'),
                    factor_value=row.get('factor_value'),
                )
                self.session.add(factor)
                count += 1

            self.session.commit()
            return count

        except Exception as e:
            logger.error(f"Error saving factor data: {e}")
            self.session.rollback()
            return 0

    # ==================== 查询方法 ====================

    def get_factor(
        self,
        symbol: str,
        factor_date: str,
        factor_name: str
    ) -> Optional[FactorValue]:
        """查询单个因子值

        Args:
            symbol: 股票代码
            factor_date: 因子日期
            factor_name: 因子名称

        Returns:
            FactorValue对象
        """
        try:
            return self.session.query(FactorValue).filter_by(
                symbol=symbol,
                factor_date=factor_date,
                factor_name=factor_name
            ).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factor: {e}")
            return None

    def get_factors_by_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        factor_names: Optional[List[str]] = None
    ) -> List[FactorValue]:
        """查询单只股票的因子值

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            factor_names: 因子名称列表（可选）

        Returns:
            FactorValue对象列表
        """
        try:
            query = self.session.query(FactorValue).filter(
                FactorValue.symbol == symbol,
                FactorValue.factor_date >= start_date,
                FactorValue.factor_date <= end_date
            )

            if factor_names:
                query = query.filter(FactorValue.factor_name.in_(factor_names))

            return query.order_by(
                FactorValue.factor_date.desc(),
                FactorValue.factor_name
            ).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factors for {symbol}: {e}")
            return []

    def get_factor_values(
        self,
        factor_name: str,
        factor_date: str,
        symbols: Optional[List[str]] = None
    ) -> List[FactorValue]:
        """查询特定因子在特定日期的所有股票值

        Args:
            factor_name: 因子名称
            factor_date: 因子日期
            symbols: 股票代码列表（可选）

        Returns:
            FactorValue对象列表
        """
        try:
            query = self.session.query(FactorValue).filter(
                FactorValue.factor_name == factor_name,
                FactorValue.factor_date == factor_date
            )

            if symbols:
                query = query.filter(FactorValue.symbol.in_(symbols))

            return query.order_by(FactorValue.symbol).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factor values for {factor_name}: {e}")
            return []

    def get_latest_factors(
        self,
        symbol: str,
        factor_names: Optional[List[str]] = None
    ) -> List[FactorValue]:
        """获取股票的最新因子值

        Args:
            symbol: 股票代码
            factor_names: 因子名称列表（可选）

        Returns:
            FactorValue对象列表
        """
        try:
            # 使用子查询获取每个因子的最新日期
            subquery = self.session.query(
                FactorValue.factor_name,
                func.max(FactorValue.factor_date).label('max_date')
            ).filter(
                FactorValue.symbol == symbol
            )

            if factor_names:
                subquery = subquery.filter(FactorValue.factor_name.in_(factor_names))

            subquery = subquery.group_by(FactorValue.factor_name).subquery()

            # JOIN获取完整因子数据
            factors = self.session.query(FactorValue).join(
                subquery,
                and_(
                    FactorValue.factor_name == subquery.c.factor_name,
                    FactorValue.factor_date == subquery.c.max_date,
                    FactorValue.symbol == symbol
                )
            ).all()

            return factors

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting latest factors for {symbol}: {e}")
            return []

    def get_factor_time_series(
        self,
        symbol: str,
        factor_name: str,
        start_date: str,
        end_date: str
    ) -> List[FactorValue]:
        """获取因子的时间序列

        Args:
            symbol: 股票代码
            factor_name: 因子名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            FactorValue对象列表，按日期升序
        """
        try:
            return self.session.query(FactorValue).filter(
                FactorValue.symbol == symbol,
                FactorValue.factor_name == factor_name,
                FactorValue.factor_date >= start_date,
                FactorValue.factor_date <= end_date
            ).order_by(FactorValue.factor_date.asc()).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factor time series: {e}")
            return []

    # ==================== 写入方法 ====================

    def upsert_factor(
        self,
        symbol: str,
        factor_date: str,
        factor_name: str,
        factor_value: float
    ) -> bool:
        """插入或更新因子值

        Args:
            symbol: 股票代码
            factor_date: 因子日期
            factor_name: 因子名称
            factor_value: 因子值

        Returns:
            成功返回True
        """
        try:
            factor = self.get_factor(symbol, factor_date, factor_name)

            if factor:
                factor.factor_value = factor_value
            else:
                factor = FactorValue(
                    symbol=symbol,
                    factor_date=factor_date,
                    factor_name=factor_name,
                    factor_value=factor_value
                )
                self.session.add(factor)

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error upserting factor: {e}")
            self.session.rollback()
            return False

    def batch_upsert_factors(self, factors: List[Dict]) -> int:
        """批量插入或更新因子值

        Args:
            factors: 因子数据字典列表
                每项包含: symbol, factor_date, factor_name, factor_value

        Returns:
            成功处理的数量
        """
        success_count = 0

        try:
            for factor_data in factors:
                symbol = factor_data.get('symbol')
                factor_date = factor_data.get('factor_date')
                factor_name = factor_data.get('factor_name')
                factor_value = factor_data.get('factor_value')

                if not all([symbol, factor_date, factor_name, factor_value is not None]):
                    continue

                factor = self.get_factor(symbol, factor_date, factor_name)

                if factor:
                    factor.factor_value = factor_value
                else:
                    factor = FactorValue(**factor_data)
                    self.session.add(factor)

                success_count += 1

            self.session.commit()
            return success_count

        except Exception as e:
            logger.error(f"Error batch upserting factors: {e}")
            self.session.rollback()
            return success_count

    # ==================== 删除方法 ====================

    def delete_factors_by_date(
        self,
        symbol: str,
        factor_date: str
    ) -> int:
        """删除指定股票在特定日期的所有因子

        Args:
            symbol: 股票代码
            factor_date: 因子日期

        Returns:
            删除的数量
        """
        try:
            count = self.session.query(FactorValue).filter(
                FactorValue.symbol == symbol,
                FactorValue.factor_date == factor_date
            ).delete()

            self.session.commit()
            return count

        except Exception as e:
            logger.error(f"Error deleting factors: {e}")
            self.session.rollback()
            return 0

    # ==================== 统计方法 ====================

    def get_factor_names(self) -> List[str]:
        """获取所有因子名称

        Returns:
            因子名称列表
        """
        try:
            result = self.session.query(FactorValue.factor_name).distinct().all()
            return [r[0] for r in result]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factor names: {e}")
            return []

    def count_factors_by_date(
        self,
        factor_date: str,
        factor_name: Optional[str] = None
    ) -> int:
        """统计指定日期的因子数量

        Args:
            factor_date: 因子日期
            factor_name: 因子名称（可选）

        Returns:
            因子数量
        """
        try:
            query = self.session.query(FactorValue).filter(
                FactorValue.factor_date == factor_date
            )

            if factor_name:
                query = query.filter(FactorValue.factor_name == factor_name)

            return query.count()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error counting factors: {e}")
            return 0

    def get_factor_stats(
        self,
        factor_name: str,
        factor_date: str
    ) -> Dict:
        """获取因子的统计信息

        Args:
            factor_name: 因子名称
            factor_date: 因子日期

        Returns:
            统计信息字典（均值、中位数、标准差等）
        """
        try:
            result = self.session.query(
                func.count(FactorValue.factor_value),
                func.avg(FactorValue.factor_value),
                func.min(FactorValue.factor_value),
                func.max(FactorValue.factor_value),
                func.stddev(FactorValue.factor_value)
            ).filter(
                FactorValue.factor_name == factor_name,
                FactorValue.factor_date == factor_date,
                FactorValue.factor_value.isnot(None)
            ).first()

            if result and result[0] > 0:
                return {
                    'count': result[0],
                    'mean': float(result[1] or 0),
                    'min': float(result[2] or 0),
                    'max': float(result[3] or 0),
                    'std': float(result[4] or 0)
                }

            return {}

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting factor stats: {e}")
            return {}

    def save_factors(
        self,
        symbol: str,
        factor_date: str,
        factors: Dict[str, float]
    ) -> bool:
        """保存单只股票在某日期的因子数据

        Args:
            symbol: 股票代码
            factor_date: 因子日期
            factors: 因子字典 {factor_name: factor_value}

        Returns:
            成功返回True
        """
        try:
            if not factors:
                return True

            import math

            for factor_name, factor_value in factors.items():
                # 跳过无效值 (NaN, inf)
                if factor_value is None or (isinstance(factor_value, float) and (math.isnan(factor_value) or math.isinf(factor_value))):
                    logger.debug(f"Skipping invalid factor value for {symbol} {factor_name}: {factor_value}")
                    continue

                # 使用 upsert_factor 方法
                self.upsert_factor(symbol, factor_date, factor_name, float(factor_value))

            return True

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error saving factors for {symbol} on {factor_date}: {e}")
            return False
