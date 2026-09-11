"""本地 DB 分钟线 provider（兜底源，stale-while-error）

RFC 015 §1.5 硬约束 4：所有数据能力必须有一条 DatabaseXxxProvider 作为**最后一级**，
保证上游全挂时链路不中断且**显式标记 stale**。

实测现状（2026-09-11）：quant.minute_klines 有 1.16 亿行，但**只到 2026-05-29**
（断更 3 个多月），粒度 5m（由 granularity_label 从数据自身间隔推断，非假设）。
因此本 provider 命中即意味着数据陈旧——调用方（应用层）必须把 source=='database_minute'
标为 stale=True，不得当作实时分钟线使用。

本 provider 只读不写（写入走 minute_kline_repository.save_minute_klines）。
"""
import logging
from dataclasses import replace
from datetime import datetime, timedelta
from typing import List, Optional

from adapters.outbound.datasources.providers.minute_kline.base import (
    MinuteKlineProvider, in_date_range, limit_klines, period_minutes,
)
from domain.models.market_data import MinuteKline

logger = logging.getLogger(__name__)


class DatabaseMinuteKlineProvider(MinuteKlineProvider):
    """本地 quant.minute_klines 兜底源（stale）"""

    _DEFAULT_WINDOW_DAYS = 7

    @property
    def name(self) -> str:
        return 'database_minute'

    def __init__(self, minute_repo=None):
        """Args: minute_repo —— MinuteKlineRepository（缺省走进程级单例）"""
        self._repo = minute_repo
        self.last_error: Optional[str] = None
        # 「无数据」的诊断说明（健康路径，见 base.py 的三态契约）：
        # 库内无该标的/该窗口的缓存是**正常**的（缓存本就只覆盖部分标的），
        # 绝不能写成 last_error —— 那会把这个源计成故障直至熔断。
        self.last_note: str = ''
        # 供调用方判定陈旧（provider 只报事实：库内最后一根的时间）
        self.latest_bar_datetime: Optional[str] = None
        self.granularity: str = ''

    @property
    def repo(self):
        if self._repo is None:
            from adapters.outbound.repositories.minute_kline_repository import get_minute_kline_repo
            self._repo = get_minute_kline_repo()
        return self._repo

    def get_minute_klines(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Optional[List[MinuteKline]]:
        self.last_error = None
        self.last_note = ''
        self.latest_bar_datetime = None
        self.granularity = ''
        try:
            period_minutes(period)  # 参数合法性校验（表无 period 列，不做过滤）
        except ValueError as e:
            self.last_error = str(e)
            return None

        try:
            if end_date:
                end_dt = f"{str(end_date)[:10]} 23:59:59"
                end_day = datetime.strptime(str(end_date)[:10], '%Y-%m-%d')
            else:
                latest = self.repo.get_latest_minute_kline(symbol)
                if latest is None:
                    self.last_note = f"DB 无 {symbol} 的分钟线缓存（该标的从未入库）"
                    return []
                end_day = datetime.strptime(latest.trade_datetime[:10], '%Y-%m-%d')
                end_dt = f"{latest.trade_datetime[:10]} 23:59:59"

            if start_date:
                start_dt = f"{str(start_date)[:10]} 00:00:00"
            else:
                start_dt = (end_day - timedelta(days=self._DEFAULT_WINDOW_DAYS)).strftime('%Y-%m-%d 00:00:00')

            rows = self.repo.get_minute_klines(symbol, start_dt, end_dt)
        except Exception as e:
            self.last_error = f"DB 分钟线查询异常: {type(e).__name__}: {e}"
            logger.warning(f"Database minute provider failed for {symbol}: {e}")
            return None

        if not rows:
            self.last_note = (
                f"DB 无 {symbol} 在 [{start_dt} ~ {end_dt}] 的分钟线缓存"
                "（本地分钟线仅历史回填，非实时增量）"
            )
            return []

        from adapters.outbound.repositories.minute_kline_repository import granularity_label
        label = granularity_label(rows)
        self.granularity = label

        # 粒度闸门（2026-09-11 实测结论）：quant.minute_klines **没有 period 列且混存多粒度**
        # （实测 000001：2026-05-29 全天 48 根 5m；2026-05-22~29 窗口内却是 952 个 1m 间隔）。
        # 因此必须按数据自身间隔推断粒度，并且**只在推断粒度与请求周期一致时**才回数据；
        # 否则宁可不兜底（fail-loud），也不能把 1m 的 bar 当 5m 交给下游——
        # 这正是「静默错误映射」事故的同型风险。
        requested = f'{period_minutes(period)}m'
        if not label:
            self.last_error = (
                f"DB 命中 {symbol} 但无法从数据推断粒度（表无 period 列且间隔不一致），"
                f"拒绝以 {requested} 冒名返回"
            )
            return None
        if label != requested:
            self.last_error = (
                f"DB 缓存粒度（{label}）与请求周期（{requested}）不一致"
                "（minute_klines 无 period 列、混存多粒度），拒绝以错误粒度返回"
            )
            return None

        rows = [replace(r, period=label) for r in rows]
        rows = [r for r in rows if in_date_range(r.trade_datetime, start_date, end_date)]
        if not rows:
            self.last_note = f"DB 命中 {symbol} 但过滤后无落在请求窗口内的行"
            return []

        self.latest_bar_datetime = rows[-1].trade_datetime
        logger.info(f"Database minute provider returned {len(rows)} bars for {symbol} (stale source)")
        return limit_klines(rows, limit)
