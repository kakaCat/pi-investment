"""竞争分析 Repository - 行业竞争对手数据访问层

职责：
1. 获取股票基本信息（含财务指标）
2. 查询同行业竞争对手（按市值排序）
3. 计算行业汇总指标（总市值、平均 ROE 等）

2026-09-14（w-8b43d3b8，REQ-24e15d B4-c5）：本文件 3 处 text() 裸 SQL 收口到 ORM，
改用 infrastructure/persistence/orm/models/stock.py 的 **Stock** 模型
（此前文件内自带一个只声明了 symbol 的极简 Stock 类，仅够占位，列全靠裸 SQL 手写）。
逐值对齐要点见各方法 docstring；列类型（market_cap/roe 为 float、revenue_growth 为
Numeric→Decimal）与旧 SQL 由数据库返回的类型一致，不做 Python 侧再加工。
"""
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy import func

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import Stock

logger = structlog.get_logger(__name__)


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

        旧实现：SELECT symbol, name, market, industry, sector, market_cap, roe,
        gross_margin, net_profit_growth, revenue_growth, pe, pb, debt_ratio
        FROM quant.stocks WHERE symbol = :symbol AND is_delisted = false
        （symbol 是主键、永不为 NULL，故「= NULL → 无行」与 ORM 的 IS NULL 分支
        在本方法里不可能产生差异，无需额外短路。）
        """
        try:
            result = (
                self.session.query(Stock)
                .filter(Stock.symbol == symbol, Stock.is_delisted.is_(False))
                .first()
            )

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

        旧实现：SELECT symbol, name, market_cap, roe, gross_margin,
        net_profit_growth, revenue_growth FROM quant.stocks
        WHERE industry = :industry AND is_delisted = false AND market_cap IS NOT NULL
        ORDER BY market_cap DESC LIMIT :limit
        """
        try:
            if industry is None:
                # 旧 SQL 的 industry = :industry 在参数为 NULL 时恒为 UNKNOWN → 空集；
                # 而 SQLAlchemy 的 Stock.industry == None 会改写成 IS NULL（语义相反）。
                # 显式短路，保持逐值一致。
                return []
            results = (
                self.session.query(Stock)
                .filter(
                    Stock.industry == industry,
                    Stock.is_delisted.is_(False),
                    Stock.market_cap.isnot(None),
                )
                .order_by(Stock.market_cap.desc())
                .limit(limit)
                .all()
            )

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

        旧实现：SELECT COUNT(*) as company_count, SUM(market_cap) as total_market_cap,
        AVG(roe), AVG(gross_margin), AVG(net_profit_growth), AVG(revenue_growth)
        FROM quant.stocks WHERE industry = :industry AND is_delisted = false
        聚合形状保持 COUNT(*)/SUM/AVG 不变（SUM 与 AVG 在零行时返回 NULL，
        下面的 or 0 与 is not None 判空口径与旧实现逐字一致）。
        """
        try:
            if industry is None:
                # 同 get_competitors：旧 SQL 的 = NULL 必为空集，ORM 会改写成 IS NULL。
                # 0 必须是 float（旧路径走的是 float(result.total_market_cap or 0)），
                # 否则调用方拿到 int 0 与 float 0.0 的类型差异（实测 diff 抓到过）。
                return {
                    "total_market_cap": 0.0,
                    "company_count": 0,
                    "avg_roe": None,
                    "avg_gross_margin": None,
                    "avg_net_profit_growth": None,
                    "avg_revenue_growth": None
                }
            result = (
                self.session.query(
                    func.count().label('company_count'),
                    func.sum(Stock.market_cap).label('total_market_cap'),
                    func.avg(Stock.roe).label('avg_roe'),
                    func.avg(Stock.gross_margin).label('avg_gross_margin'),
                    func.avg(Stock.net_profit_growth).label('avg_net_profit_growth'),
                    func.avg(Stock.revenue_growth).label('avg_revenue_growth'),
                )
                .filter(Stock.industry == industry, Stock.is_delisted.is_(False))
                .first()
            )

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
