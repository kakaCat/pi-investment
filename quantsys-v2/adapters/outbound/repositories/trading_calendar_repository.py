"""
交易日历 ORM Repository（quant.trading_calendar）

2026-09-14（w-32314d00，REQ-24e15d）：原实现是
application/services/data_pipeline_service.py 的模块级函数
`load_trading_calendar_from_db` 里的裸 SQL（db_cursor + SELECT trade_date
FROM quant.trading_calendar WHERE exchange = %s AND is_trading_day = TRUE）。
该函数是 8 段数据管道 TimeAlignmentStage 的 calendar_loader，收口后服务层
只剩编排与"空表则回退 K 线 + 打 error 日志"的语义。

迁移状态：✅ ORM
"""
from datetime import date
from typing import Set

import structlog

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import TradingCalendar

logger = structlog.get_logger(__name__)

__all__ = ['TradingCalendarORMRepository']


class TradingCalendarORMRepository(BaseORMRepository[TradingCalendar]):
    """交易日历 ORM Repository"""

    model = TradingCalendar

    def list_trading_days(self, exchange: str) -> Set[date]:
        """某交易所的全部交易日（is_trading_day = TRUE），返回去重集合。

        逐值对齐原 SQL：
          · 过滤 `exchange = :exchange`（复合主键的一部分，SSE/SZSE/ALL 各一份，
            不按 exchange 过滤会三倍重复）；
          · 过滤 `is_trading_day = TRUE` —— 用 `.is_(True)`，与 `= TRUE` 完全等价
            （两者都把 NULL 排除在外，历史行 is_trading_day 可为 NULL）；
          · 返回 **set[datetime.date]**（原实现 `_rows_to_set` 的结果类型），
            元素类型是 psycopg2/ORM 都返回的 `datetime.date`，未做 str 化。

        异常策略：**回滚后上抛**。调用方 `load_trading_calendar_from_db` 有外层
        `except Exception → logger.warning('trading_calendar_unavailable') → set()`；
        仓储若在此吞掉异常，会把"日历不可用"伪装成"日历为空"，
        进而走到 K 线回退甚至返回空日历（2026-09-11 那类静默降级）。
        """
        try:
            rows = (
                self.session.query(TradingCalendar.trade_date)
                .filter(TradingCalendar.exchange == exchange)
                .filter(TradingCalendar.is_trading_day.is_(True))
                .all()
            )
        except Exception:
            self._safe_rollback()
            raise
        return {r[0] for r in rows}
