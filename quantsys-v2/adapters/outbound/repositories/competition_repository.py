"""竞争分析 Repository - 行业竞争对手数据访问层

职责：
1. 获取股票基本信息（含财务指标）
2. 查询同行业竞争对手（按市值排序）
3. 计算行业汇总指标（总市值、平均 ROE 等）
"""
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy import Column, Text, text

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


# 使用 extend_existing 避免表重复定义错误
class Stock(Base):
    __tablename__ = 'stocks'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    symbol = Column(Text, primary_key=True)


class CompetitionRepository(BaseORMRepository[Stock]):
    """竞争分析数据仓储"""

    model = Stock

    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票基本信息及财务指标

        Args:
            symbol: 股票代码（6 位数字）

        Returns:
            股票信息字典，包含 name, industry, market_cap, roe, gross_margin 等
            不存在或已退市返回 None
        """
        try:
            result = self.session.execute(
                text("""
                    SELECT
                        symbol, name, market, industry, sector,
                        market_cap, roe, gross_margin,
                        net_profit_growth, revenue_growth,
                        pe, pb, debt_ratio
                    FROM quant.stocks
                    WHERE symbol = :symbol AND is_delisted = false
                """),
                {"symbol": symbol}
            ).first()

            if not result:
                return None

            return {
                "symbol": result.symbol,
                "name": result.name,
                "market": result.market,
                "industry": result.industry,
                "sector": result.sector,
                "market_cap": result.market_cap,
                "roe": result.roe,
                "gross_margin": result.gross_margin,
                "net_profit_growth": result.net_profit_growth,
                "revenue_growth": result.revenue_growth,
                "pe": result.pe,
                "pb": result.pb,
                "debt_ratio": result.debt_ratio
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Failed to get stock info for {symbol}: {e}")
            return None

    def get_competitors(self, industry: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取同行业竞争对手（按市值降序）

        Args:
            industry: 行业分类（如 "制造业-酒、饮料和精制茶制造业"）
            limit: 返回数量限制（默认 10）

        Returns:
            竞争对手列表（按市值降序排列）
        """
        try:
            results = self.session.execute(
                text("""
                    SELECT
                        symbol, name, market_cap, roe, gross_margin,
                        net_profit_growth, revenue_growth
                    FROM quant.stocks
                    WHERE industry = :industry
                      AND is_delisted = false
                      AND market_cap IS NOT NULL
                    ORDER BY market_cap DESC
                    LIMIT :limit
                """),
                {"industry": industry, "limit": limit}
            ).fetchall()

            competitors = []
            for row in results:
                competitors.append({
                    "symbol": row.symbol,
                    "name": row.name,
                    "market_cap": row.market_cap,
                    "roe": row.roe,
                    "gross_margin": row.gross_margin,
                    "net_profit_growth": row.net_profit_growth,
                    "revenue_growth": row.revenue_growth
                })

            return competitors
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Failed to get competitors for {industry}: {e}")
            return []

    def get_industry_totals(self, industry: str) -> Dict[str, Any]:
        """计算行业汇总指标

        Args:
            industry: 行业分类

        Returns:
            汇总指标字典：
            - total_market_cap: 行业总市值（亿元）
            - company_count: 公司数量
            - avg_roe: 平均 ROE
            - avg_gross_margin: 平均毛利率
            - avg_net_profit_growth: 平均净利润增长率
            - avg_revenue_growth: 平均营收增长率
        """
        try:
            result = self.session.execute(
                text("""
                    SELECT
                        COUNT(*) as company_count,
                        SUM(market_cap) as total_market_cap,
                        AVG(roe) as avg_roe,
                        AVG(gross_margin) as avg_gross_margin,
                        AVG(net_profit_growth) as avg_net_profit_growth,
                        AVG(revenue_growth) as avg_revenue_growth
                    FROM quant.stocks
                    WHERE industry = :industry
                      AND is_delisted = false
                """),
                {"industry": industry}
            ).first()

            if not result:
                return {
                    "total_market_cap": 0,
                    "company_count": 0,
                    "avg_roe": None,
                    "avg_gross_margin": None,
                    "avg_net_profit_growth": None,
                    "avg_revenue_growth": None
                }

            return {
                "total_market_cap": float(result.total_market_cap or 0),
                "company_count": int(result.company_count or 0),
                "avg_roe": float(result.avg_roe) if result.avg_roe is not None else None,
                "avg_gross_margin": float(result.avg_gross_margin) if result.avg_gross_margin is not None else None,
                "avg_net_profit_growth": float(result.avg_net_profit_growth) if result.avg_net_profit_growth is not None else None,
                "avg_revenue_growth": float(result.avg_revenue_growth) if result.avg_revenue_growth is not None else None
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Failed to get industry totals for {industry}: {e}")
            return {
                "total_market_cap": 0,
                "company_count": 0,
                "avg_roe": None,
                "avg_gross_margin": None,
                "avg_net_profit_growth": None,
                "avg_revenue_growth": None
            }
