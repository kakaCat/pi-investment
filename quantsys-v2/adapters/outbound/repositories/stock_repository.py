"""
股票ORM Repository

使用SQLAlchemy ORM重构的股票数据访问层

对比旧版本：
- 返回Model对象而不是Dict
- 自动Session管理（scoped_session）
- 类型安全的查询
- 支持关系映射（stock.daily_klines）

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Optional, Dict, Any
from datetime import date
import structlog

from infrastructure.persistence.orm import BaseORMRepository, get_session
from infrastructure.persistence.orm.models import Stock
from domain.ports import IStockRepository

logger = structlog.get_logger(__name__)

__all__ = ['StockORMRepository']


class StockORMRepository(BaseORMRepository[Stock], IStockRepository):
    """股票ORM Repository

    示例用法：
        repo = StockORMRepository()

        # 查询单个股票
        stock = repo.get_by_symbol('000001')
        print(f"{stock.name}: {stock.roe}%")

        # 查询股票列表
        stocks = repo.list_by_market('A', limit=10)
        for stock in stocks:
            print(f"{stock.symbol} {stock.name}")

        # 使用关系映射
        stock = repo.get_by_symbol('000001')
        klines = stock.daily_klines.limit(10).all()  # 懒加载K线数据
    """

    model = Stock

    @staticmethod
    def _stock_to_info_dict(stock: Stock) -> Dict[str, Any]:
        """Stock 对象 -> 股票信息字典（get_stock_info/get_by_symbols_batch 共用）"""
        return {
            'symbol': stock.symbol,
            'name': stock.name,
            'market': stock.market,
            'industry': stock.industry,
            'sector': stock.sector,
            'list_date': stock.list_date.isoformat() if stock.list_date else None,
            'is_st': stock.is_st,
            'is_suspended': stock.is_suspended,
            'market_cap': stock.market_cap,
            'pe_ratio': stock.pe,  # 表字段是 pe
            'pb_ratio': stock.pb,  # 表字段是 pb
            'roe': stock.roe,
            'revenue_growth': stock.revenue_growth,
            'net_profit_growth': stock.net_profit_growth,
        }

    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票基础信息（IStockRepository接口实现）

        Args:
            symbol: 股票代码

        Returns:
            股票信息字典，不存在返回None
        """
        stock = self.get_by_symbol(symbol)
        if not stock:
            return None

        return self._stock_to_info_dict(stock)

    def get_by_symbols_batch(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量查询多只股票（单次查询契约）

        旧 BaseRepository 时代契约（Phase 3 性能优化引入），ORM 重构
        （8f06ae1）时丢失，2026-08-06 恢复——adapters/inbound/api/routes/
        analysis.py compare_stocks 通过 stock_repo.get_by_symbols_batch(...)
        调用，缺失即 AttributeError（/api/stocks/compare 500）。

        语义对齐归档实现（quantsys-v2.git.archive 8f06ae1^）：单次 IN 查询、
        symbol 精确匹配（不做后缀归一化，带后缀代码查不到即不出现）、
        未找到的股票不包含在结果中。字典值契约与 get_stock_info 一致。

        Args:
            symbols: 股票代码列表

        Returns:
            字典 {symbol: stock_info}
        """
        if not symbols:
            return {}

        try:
            stocks = self.session.query(Stock).filter(Stock.symbol.in_(symbols)).all()
            return {s.symbol: self._stock_to_info_dict(s) for s in stocks}
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error batch getting {len(symbols)} stocks: {e}")
            return {}

    def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        """根据代码查询单只股票

        Args:
            symbol: 股票代码

        Returns:
            Stock对象，不存在返回None
        """
        try:
            return self.session.query(Stock).filter_by(symbol=symbol).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting stock by symbol {symbol}: {e}")
            return None

    def list_by_market(
        self,
        market: Optional[str] = None,
        industry: Optional[str] = None,
        sector: Optional[str] = None,
        is_st: Optional[bool] = None,
        include_suspended: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Stock]:
        """查询股票列表（支持多种筛选条件）

        Args:
            market: 市场类型（A/HK）
            industry: 行业
            sector: 板块
            is_st: 是否ST股票
            include_suspended: 是否包含停牌/退市股（默认False）
            limit: 返回数量限制
            offset: 跳过的数量

        Returns:
            Stock对象列表
        """
        try:
            query = self.session.query(Stock)

            # 默认排除停牌/退市股
            if not include_suspended:
                query = query.filter_by(is_suspended=False)

            # 筛选条件
            if market:
                query = query.filter_by(market=market)
            if industry:
                query = query.filter_by(industry=industry)
            if sector:
                query = query.filter_by(sector=sector)
            if is_st is not None:
                query = query.filter_by(is_st=is_st)

            # 分页
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            return query.all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing stocks: {e}")
            return []

    def list_all_active(self, market: Optional[str] = None) -> List[Stock]:
        """获取所有活跃股票（排除ST和停牌）

        Args:
            market: 市场类型（可选）

        Returns:
            Stock对象列表
        """
        try:
            query = self.session.query(Stock).filter(
                Stock.is_st == False,
                Stock.is_suspended == False
            )
            if market:
                query = query.filter_by(market=market)
            return query.all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing active stocks: {e}")
            return []

    def get_all(self, market: Optional[str] = None, industry: Optional[str] = None, limit: Optional[int] = None, include_suspended: bool = False) -> List[Dict[str, Any]]:
        """获取所有股票（兼容旧接口）

        Args:
            market: 市场类型（可选）
            industry: 行业（可选）
            limit: 返回数量限制
            include_suspended: 是否包含停牌/退市股（默认False）

        Returns:
            股票信息字典列表
        """
        try:
            stocks = self.list_by_market(
                market=market,
                industry=industry,
                is_st=False,
                include_suspended=include_suspended,
                limit=limit
            )
            return [self.get_stock_info(s.symbol) for s in stocks if s]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting all stocks: {e}")
            return []

    def search_by_name(self, keyword: str, limit: int = 10) -> List[Stock]:
        """根据名称或代码模糊搜索

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            Stock对象列表
        """
        try:
            query = self.session.query(Stock).filter(
                (Stock.name.ilike(f'%{keyword}%')) |
                (Stock.symbol.ilike(f'%{keyword}%'))
            ).limit(limit)
            return query.all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error searching stocks by keyword {keyword}: {e}")
            return []

    def search(self, keyword: str, limit: int = 10) -> List[Stock]:
        """根据名称或代码模糊搜索（search_by_name的别名）

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            Stock对象列表
        """
        return self.search_by_name(keyword, limit)

    def count_by_market(self, market: str) -> int:
        """统计指定市场的股票数量

        Args:
            market: 市场类型

        Returns:
            股票数量
        """
        try:
            return self.session.query(Stock).filter_by(market=market).count()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error counting stocks in market {market}: {e}")
            return 0

    def get_industries(self) -> List[str]:
        """获取所有行业列表

        Returns:
            行业名称列表
        """
        try:
            result = self.session.query(Stock.industry).distinct().filter(
                Stock.industry.isnot(None)
            ).all()
            return [r[0] for r in result]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting industries: {e}")
            return []

    def get_sectors(self) -> List[str]:
        """获取所有板块列表

        Returns:
            板块名称列表
        """
        try:
            result = self.session.query(Stock.sector).distinct().filter(
                Stock.sector.isnot(None)
            ).all()
            return [r[0] for r in result]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting sectors: {e}")
            return []

    def update_metrics(
        self,
        symbol: str,
        roe: Optional[float] = None,
        pe: Optional[float] = None,
        pb: Optional[float] = None,
        market_cap: Optional[float] = None
    ) -> bool:
        """更新股票指标

        Args:
            symbol: 股票代码
            roe: 净资产收益率
            pe: 市盈率
            pb: 市净率
            market_cap: 市值

        Returns:
            成功返回True
        """
        try:
            stock = self.get_by_symbol(symbol)
            if not stock:
                logger.warning(f"Stock {symbol} not found")
                return False

            if roe is not None:
                stock.roe = roe
            if pe is not None:
                stock.pe = pe
            if pb is not None:
                stock.pb = pb
            if market_cap is not None:
                stock.market_cap = market_cap

            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating stock metrics for {symbol}: {e}")
            self.session.rollback()
            return False

    def batch_create(self, stocks: List[Stock]) -> bool:
        """批量创建股票

        Args:
            stocks: Stock对象列表

        Returns:
            成功返回True
        """
        return self.create_batch(stocks, commit=True)

    def batch_get_fundamentals(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """批量查询股票基本面数据

        Args:
            symbols: 股票代码列表

        Returns:
            字典，键为股票代码，值为基本面数据字典（如果股票不存在则为None）
            基本面数据包含：pe_ratio, pb_ratio, roe, gross_margin, debt_ratio,
                           net_profit_growth, revenue_growth, updated_at
        """
        if not symbols:
            logger.debug("Empty symbols list provided to batch_get_fundamentals")
            return {}

        try:
            # 批量查询股票
            stocks = self.session.query(Stock).filter(Stock.symbol.in_(symbols)).all()

            # 构建结果字典
            result = {}
            stocks_map = {stock.symbol: stock for stock in stocks}

            for symbol in symbols:
                stock = stocks_map.get(symbol)
                if stock:
                    result[symbol] = {
                        'pe_ratio': stock.pe,
                        'pb_ratio': stock.pb,
                        'roe': stock.roe,
                        'gross_margin': stock.gross_margin,
                        'debt_ratio': stock.debt_ratio,
                        'net_profit_growth': stock.net_profit_growth,
                        'revenue_growth': float(stock.revenue_growth) if stock.revenue_growth else None,
                        'market_cap': stock.market_cap,
                        'updated_at': stock.updated_at.isoformat() if stock.updated_at else None,
                    }
                else:
                    result[symbol] = None

            logger.debug(f"Batch fetched fundamentals for {len(symbols)} stocks, found {len(stocks)}")
            return result

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error batch fetching fundamentals for {len(symbols)} symbols: {e}")
            # 返回所有symbol都为None的字典，保证调用方能处理
            return {symbol: None for symbol in symbols}

    def batch_get_names(self, symbols: List[str]) -> Dict[str, str]:
        """批量获取股票名称

        Args:
            symbols: 股票代码列表

        Returns:
            字典，键为股票代码，值为股票名称
        """
        if not symbols:
            logger.debug("Empty symbols list provided to batch_get_names")
            return {}

        try:
            # 批量查询股票
            stocks = self.session.query(Stock.symbol, Stock.name).filter(
                Stock.symbol.in_(symbols)
            ).all()

            # 构建结果字典
            result = {symbol: name for symbol, name in stocks if name}

            logger.debug(f"Batch fetched names for {len(symbols)} stocks, found {len(result)}")
            return result

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error batch fetching names for {len(symbols)} symbols: {e}")
            return {}

    def get_index_constituents(self, index_codes: List[str]) -> List[str]:
        """获取指数成分股

        Args:
            index_codes: 指数代码列表，如 ['000300.SH', '399006.SZ', '000688.SH']

        Returns:
            成分股代码列表（可能包含重复）
        """
        if not index_codes:
            logger.debug("Empty index_codes provided to get_index_constituents")
            return []

        try:
            # 查询 index_constituents 表
            from infrastructure.persistence.orm.models import IndexConstituent

            constituents = self.session.query(IndexConstituent.symbol).filter(
                IndexConstituent.index_code.in_(index_codes)
            ).all()

            # 提取股票代码
            symbols = [c[0] for c in constituents if c[0]]

            logger.debug(f"Fetched {len(symbols)} constituents from {len(index_codes)} indices")
            return symbols

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error fetching index constituents for {index_codes}: {e}")
            return []
