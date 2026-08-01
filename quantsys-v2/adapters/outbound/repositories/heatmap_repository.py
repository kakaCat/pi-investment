"""热力图聚合查询 — 跨表只读查询的唯一出口（Task 1: 交易日与收盘价；Task 2 补充信号/池/持仓）"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func

from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog
from adapters.outbound.repositories.stock_pool_repository import StockPool
from infrastructure.persistence.orm.base_repository import BaseORMRepository
from infrastructure.persistence.orm.models.portfolio import PortfolioHolding
from infrastructure.persistence.orm.models.signal import Signal
from infrastructure.persistence.orm.models.stock import DailyKline, Stock


class HeatmapRepository(BaseORMRepository[DailyKline]):
    model = DailyKline

    def get_last_trade_date_on_or_before(self, d: date) -> Optional[date]:
        """d（含）之前最近的交易日；无数据返回 None"""
        return (
            self.session.query(func.max(DailyKline.trade_date))
            .filter(DailyKline.trade_date <= d)
            .scalar()
        )

    def get_trade_dates_from(self, d: date, count: int) -> list[date]:
        """从 d（含）起最多 count 个不重复交易日，升序"""
        rows = (
            self.session.query(DailyKline.trade_date)
            .filter(DailyKline.trade_date >= d)
            .distinct()
            .order_by(DailyKline.trade_date.asc())
            .limit(count)
            .all()
        )
        return [r[0] for r in rows]

    def get_window_closes(self, symbols: list[str], d0: date, dn: date) -> dict[str, dict]:
        """每只股票在 d0 / dn 两日的收盘价：{symbol: {'close_d0': x, 'close_dn': y}}（缺日期的 key 不出现）"""
        if not symbols:
            return {}
        rows = (
            self.session.query(DailyKline.symbol, DailyKline.trade_date, DailyKline.close)
            .filter(DailyKline.symbol.in_(symbols), DailyKline.trade_date.in_([d0, dn]))
            .all()
        )
        result: dict[str, dict] = {}
        for symbol, trade_date, close in rows:
            entry = result.setdefault(symbol, {})
            if trade_date == d0:
                entry['close_d0'] = close
            else:
                entry['close_dn'] = close
        return result

    def get_stocks_meta(self, symbols: list[str]) -> dict[str, dict]:
        """{symbol: {'name','industry','market_cap'}}（market_cap 单位与 stocks 表一致，不换算）"""
        if not symbols:
            return {}
        rows = (
            self.session.query(Stock.symbol, Stock.name, Stock.industry, Stock.market_cap)
            .filter(Stock.symbol.in_(symbols))
            .all()
        )
        return {
            r.symbol: {'name': r.name, 'industry': r.industry, 'market_cap': r.market_cap}
            for r in rows
        }

    def get_stocks_meta_by_industries(self, industries: list[str]) -> dict[str, dict]:
        """同行业全部股票的 meta（含池外股票，供灰色背景块）"""
        if not industries:
            return {}
        rows = (
            self.session.query(Stock.symbol, Stock.name, Stock.industry, Stock.market_cap)
            .filter(Stock.industry.in_(industries))
            .all()
        )
        return {
            r.symbol: {'name': r.name, 'industry': r.industry, 'market_cap': r.market_cap}
            for r in rows
        }
