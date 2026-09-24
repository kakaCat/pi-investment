"""标的名解析适配器（REQ-260924104605-ad0a t1，2026-09-24）

实现 domain/watch/ports.py 的 StockNameResolver：quant.stocks 只读批量联查
（symbol → name），供 SLA 巡检/回执渲染在一轮内**一次**解析全部标的名称
（替代逐条查询的 N+1）。

降级纪律（与端口注释一致）：
  · 查询异常 → 记 error 日志并返回**全 None**（名称缺失降级），绝不把 DB 异常
    抛进巡检主循环——回执发不出名称是降级，回执发不出是事故；
  · 输入 symbol 可带市场后缀（'601888.SH'），键一律规范化为 6 位裸码
    （与 quant.stocks.symbol 主键口径一致）；
  · 未命中返回 None——渲染方如实标「名称缺失」，不臆造（R-013）。
"""
from typing import Dict, List, Optional

import structlog

from domain.watch.ports import StockNameResolver
from infrastructure.persistence.orm.base_repository import BaseORMRepository
from infrastructure.persistence.orm.models.stock import Stock

logger = structlog.get_logger(__name__)


def _normalize(symbol: object) -> str:
    """'601888.SH' / ' 601138 ' → '601888'；空值 → ''。"""
    return str(symbol or '').split('.')[0].strip()


class PgStockNameResolver(BaseORMRepository[Stock], StockNameResolver):
    """StockNameResolver 的 PostgreSQL 实现（quant.stocks 只读）"""

    model = Stock

    def resolve_batch(self, symbols: List[str]) -> Dict[str, Optional[str]]:
        """批量解析名称：键 = 规范化 6 位码；未命中/异常 = None（不抛错）。"""
        keys = sorted({k for k in (_normalize(s) for s in (symbols or [])) if k})
        result: Dict[str, Optional[str]] = {k: None for k in keys}
        if not keys:
            return result
        try:
            rows = (
                self.session.query(Stock.symbol, Stock.name)
                .filter(Stock.symbol.in_(keys))
                .all()
            )
        except Exception as e:  # noqa: BLE001 - 降级不抛进巡检主循环
            logger.error('标的名批量解析失败（降级为名称缺失）', error=str(e),
                         symbols_count=len(keys))
            self._safe_rollback()
            return result
        for symbol, name in rows:
            key = _normalize(symbol)
            if key in result:
                result[key] = (str(name).strip() or None) if name is not None else None
        return result
