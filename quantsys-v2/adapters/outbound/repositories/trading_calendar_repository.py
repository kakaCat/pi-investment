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
import time
from typing import Dict, Optional, Set, Tuple

import structlog

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import TradingCalendar

logger = structlog.get_logger(__name__)

__all__ = ['TradingCalendarORMRepository', 'trading_day_set', 'reset_trading_day_cache']


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


# ---------------------------------------------------------------------------
# 交易日集合的带缓存读取（2026-10-06 · REQ-261006190953-fc43）
#
# 为什么放在**本模块**（adapters 层）而不是 application：
#   `application/services/nav_series.py` 是纯口径模块（只做过滤/派生/缺口计算），
#   一旦它自己 import 本仓储，就是 application → adapters（方向倒置），
#   会被 `tests/test_layer_purity.py` 的棘轮计为一处新违规。
#   日历读取本来就是"读一张表"，留在仓储层，调用方（含同层的净值仓储、
#   inbound 路由）按各自被允许的方向取用即可。
# ---------------------------------------------------------------------------

#: 进程内缓存 TTL（交易日历一天最多变一次；秒级 tick 不该反复查库）
_TTL_SECONDS = 300
_cache: Dict[str, Tuple[float, Optional[Set[date]]]] = {}


def reset_trading_day_cache() -> None:
    """清空缓存（测试与日历刷新后调用）。"""
    _cache.clear()


def trading_day_set(
    exchange: str = 'ALL',
    *,
    force_refresh: bool = False,
) -> Optional[Set[date]]:
    """交易日集合；**不可得返回 None，绝不用空集合表达"不可得"**。

    口径三锁（与 `application/services/nav_series.py` 一致）：
    · 空表 → None（日历链断了，不是"一年没有交易日"）；
    · 查询异常 → None + warning（净值读取不该被日历故障打挂）；
    · 调用方拿到 None 必须按"未校验"处理（不过滤、并在返回体里如实声明）。
    """
    now = time.time()
    if not force_refresh:
        hit = _cache.get(exchange)
        if hit is not None and now - hit[0] < _TTL_SECONDS:
            return hit[1]

    days: Optional[Set[date]] = None
    try:
        days = TradingCalendarORMRepository().list_trading_days(exchange)
        if not days:
            logger.warning(
                'trading_day_set_empty exchange=%s —— 日历表为空，按"不可得"处理（不清空净值序列）',
                exchange,
            )
            days = None
    except Exception as exc:  # noqa: BLE001 —— 日历读失败不得让净值读取整体失败
        logger.warning('trading_day_set_failed exchange=%s error=%s', exchange, exc)
        days = None

    _cache[exchange] = (now, days)
    return days
