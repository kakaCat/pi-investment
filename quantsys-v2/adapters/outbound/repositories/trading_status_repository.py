"""交易状态基础数据仓储（stocks 表静态状态 + 最近日线昨收）

RFC 015 §4.3（2026-09-11 REQ-cf627b）：
- 只提供**事实**：is_st / is_suspended / is_delisted（quant.stocks）+ 最近一根
  日线的收盘价（quant.daily_klines，作为昨收兜底；实时行情可用时以行情
  prev_close 为准）
- **不做判定**：ST/停牌/涨跌停的裁决属于领域服务 TradingStatusPolicy
- 诚实标注数据时点：prev_close_date 一并返回，调用方需能识别 DB 陈旧
  （2026-09-11 实测：daily_klines 曾出现整体停更，昨收可能是旧值）
"""
from typing import Optional

from domain.trading.ports.ITradingStatusRepository import ITradingStatusRepository

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import DailyKline, Stock


class TradingStatusRepository(BaseORMRepository[Stock], ITradingStatusRepository):
    """stocks 表基础状态 + 最近日线昨收"""

    model = Stock

    @staticmethod
    def _normalize(symbol: str) -> str:
        """600519.SH → 600519（库内统一无后缀）"""
        return str(symbol or '').split('.')[0]

    def get_stock_status(self, symbol: str) -> Optional[dict]:
        """标的静态状态 + 昨收（不在 stocks 表返回 None）"""
        bare = self._normalize(symbol)
        if not bare:
            return None
        try:
            stock = self.session.query(Stock).filter(Stock.symbol == bare).first()
        except Exception:
            self._safe_rollback()
            raise
        if stock is None:
            return None

        prev_close = None
        prev_close_date = None
        try:
            row = (self.session.query(DailyKline)
                   .filter(DailyKline.symbol == bare)
                   .order_by(DailyKline.trade_date.desc())
                   .first())
            if row is not None:
                prev_close = float(row.close) if row.close is not None else None
                prev_close_date = row.trade_date.isoformat() if row.trade_date else None
        except Exception:
            # 昨收缺失不致命（策略会退回行情 prev_close）——回滚防线程毒化后继续
            self._safe_rollback()

        return {
            'symbol': bare,
            'name': stock.name,
            'market': stock.market,
            'industry': stock.industry,
            'is_st': bool(stock.is_st),
            'is_suspended': bool(stock.is_suspended),
            'is_delisted': bool(stock.is_delisted),
            'prev_close': prev_close,
            'prev_close_date': prev_close_date,
            'source': 'stocks_table',
        }


_repo_instance: Optional[TradingStatusRepository] = None


def get_trading_status_repo() -> TradingStatusRepository:
    """进程级单例（与既有仓储模式一致）"""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = TradingStatusRepository()
    return _repo_instance
