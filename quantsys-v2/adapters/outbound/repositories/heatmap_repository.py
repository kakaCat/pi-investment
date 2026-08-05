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

    def get_trade_dates_up_to(self, d: date, count: int) -> list[date]:
        """d（含）之前最近 count 个不重复交易日，升序"""
        rows = (
            self.session.query(DailyKline.trade_date)
            .filter(DailyKline.trade_date <= d)
            .distinct()
            .order_by(DailyKline.trade_date.desc())
            .limit(count)
            .all()
        )
        return sorted(r[0] for r in rows)

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

    def get_signals_between(self, start: date, end: date) -> list[dict]:
        """[start, end] 内的买/卖信号，按日期升序"""
        rows = (
            self.session.query(Signal.symbol, Signal.action, Signal.signal_date, Signal.strategy_id)
            .filter(
                Signal.signal_date >= start,
                Signal.signal_date <= end,
                Signal.action.in_(['buy', 'sell']),
            )
            .order_by(Signal.signal_date.asc())
            .all()
        )
        return [
            {'symbol': r.symbol, 'action': r.action, 'signal_date': r.signal_date, 'strategy_id': r.strategy_id}
            for r in rows
        ]

    def get_pool_events_between(self, start: datetime, end: datetime) -> list[dict]:
        """[start, end] 内的池调入/调出事件，按时间升序"""
        rows = (
            self.session.query(PoolChangeLog.pool_id, PoolChangeLog.action,
                               PoolChangeLog.symbol, PoolChangeLog.changed_at)
            .filter(
                PoolChangeLog.changed_at >= start,
                PoolChangeLog.changed_at <= end,
                PoolChangeLog.action.in_(['add', 'remove']),
            )
            .order_by(PoolChangeLog.changed_at.asc())
            .all()
        )
        return [
            {'pool_id': r.pool_id, 'action': r.action, 'symbol': r.symbol, 'changed_at': r.changed_at}
            for r in rows
        ]

    def get_pool_events_after(self, d: datetime) -> list[dict]:
        """d 之后的池事件，按时间倒序（用于从当前成员回放到 D 时点）"""
        rows = (
            self.session.query(PoolChangeLog.pool_id, PoolChangeLog.action,
                               PoolChangeLog.symbol, PoolChangeLog.changed_at)
            .filter(PoolChangeLog.changed_at > d, PoolChangeLog.action.in_(['add', 'remove']))
            .order_by(PoolChangeLog.changed_at.desc())
            .all()
        )
        return [
            {'pool_id': r.pool_id, 'action': r.action, 'symbol': r.symbol, 'changed_at': r.changed_at}
            for r in rows
        ]

    def get_pool_names(self) -> dict[int, str]:
        return {p.id: p.name for p in self.session.query(StockPool.id, StockPool.name).all()}

    def get_pool_members_now(self) -> set[str]:
        """当前全部动态池成员（members JSON 兼容 list[str] / list[dict] / dict 三种形态）"""
        members: set[str] = set()
        for pool in self.session.query(StockPool).all():
            raw = pool.members or []
            if isinstance(raw, dict):
                raw = raw.get('symbols', [])
            for item in raw:
                if isinstance(item, str):
                    members.add(item)
                elif isinstance(item, dict) and item.get('symbol'):
                    members.add(item['symbol'])
        return members

    def has_pool_log_before(self, d: datetime) -> bool:
        """d（含）之前是否存在任何池变更日志（spec §4.3：无则 D 时点池成员不可知 → scope 退化）"""
        return (
            self.session.query(PoolChangeLog.id)
            .filter(PoolChangeLog.changed_at <= d)
            .first()
            is not None
        )

    def get_current_holding_symbols(self) -> set[str]:
        """当前持仓（quantity > 0）股票代码"""
        rows = (
            self.session.query(PortfolioHolding.symbol)
            .filter(PortfolioHolding.quantity > 0)
            .all()
        )
        return {r[0] for r in rows}
