"""新浪分钟线 provider（通道：新浪 quotes.sina.cn）

真实响应打样（2026-09-11 本机实测，600150 / 688111）：
    GET https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData
        ?symbol=sh600150&scale=5&ma=no&datalen=10
    [{"day":"2026-09-11 14:15:00","open":"39.670","high":"39.830","low":"39.640",
      "close":"39.820","volume":"1250028","amount":"49684335.1899"}, ...]
- 字段：day/open/high/low/close/volume/amount（**volume 已是股**，实测
  600150 m5 14:15 = 1,250,028 股 ≈ 腾讯 11796 手×100；688111 m5 14:40 =
  101,390 股 ≈ 腾讯 101150，故两个板块都不做 ×100 换算）
- amount 上游直接返回（元），无需估算
- scale 实测支持 5/15/30/60（1 分钟不支持，1m 请求交由其它通道）
- 无日期参数：datalen 上限实测 1023 根（5m ≈ 1 个月），回溯窗口由 bars_needed 估算
- 国内源必须绕过本机代理（与 providers/kline/tencent.py 的 _NO_PROXY 同模式）
"""
import logging
from datetime import datetime
from typing import List, Optional

import requests

from adapters.outbound.datasources.providers.minute_kline.base import (
    MinuteKlineProvider, bars_needed, in_date_range, limit_klines,
    ohlc_sanity, period_minutes, to_prefixed_code,
)
from domain.models.market_data import MinuteKline

logger = logging.getLogger(__name__)


class SinaMinuteKlineProvider(MinuteKlineProvider):
    """新浪分钟线（5/15/30/60 分钟；不支持 1 分钟）"""

    _NO_PROXY = {'http': None, 'https': None}
    _URL = 'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
    _MAX_BARS = 1023
    _TIMEOUT = 10
    _SUPPORTED = (5, 15, 30, 60)

    @property
    def name(self) -> str:
        return 'sina_minute'

    def __init__(self):
        self.last_error: Optional[str] = None
        # 「无数据」的诊断说明（健康路径，见 base.py 的三态契约）
        self.last_note: str = ''

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
        try:
            minutes = period_minutes(period)
        except ValueError as e:
            self.last_error = str(e)
            return None
        if minutes not in self._SUPPORTED:
            self.last_error = f"新浪分钟线不支持 {minutes} 分钟（支持 5/15/30/60）"
            return None

        code = to_prefixed_code(symbol)
        if not code:
            self.last_error = f"代码 {symbol} 无法映射到交易所前缀（新浪需 sh/sz/bj 前缀）"
            return None

        count = bars_needed(period, start_date, end_date, limit, self._MAX_BARS)
        try:
            resp = requests.get(
                self._URL,
                params={'symbol': code, 'scale': minutes, 'ma': 'no', 'datalen': count},
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                proxies=self._NO_PROXY,
                timeout=self._TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            self.last_error = f"网络/解析异常: {type(e).__name__}: {e}"
            logger.warning(f"Sina minute provider request failed for {symbol}: {e}")
            return None

        if isinstance(payload, list) and not payload:
            # 空结果 ≠ 故障（2026-09-11 P10 修复）：上游正常应答但该标的/时段没有数据。
            # 返回 [] + last_note：健康路径，不计故障、不影响熔断；诊断经 manager 透出。
            self.last_note = f"新浪无 {symbol} 的 {minutes} 分钟数据（该标的无此周期数据或已停牌）"
            return []
        if not isinstance(payload, list):
            # 非 list = 上游返回了非数据体（错误对象/HTML/WAF 页）= 结构异常，属真故障
            self.last_error = (
                f"新浪响应结构异常：期望 list，实际 {type(payload).__name__}"
                f"（上游可能返回了错误体或被 WAF 拦截）"
            )
            return None

        bare = str(symbol).split('.')[0]
        out: List[MinuteKline] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                dt = str(row.get('day'))
                open_p = float(row.get('open'))
                high = float(row.get('high'))
                low = float(row.get('low'))
                close = float(row.get('close'))
                volume = float(row.get('volume') or 0)
                amount = float(row.get('amount') or 0)
            except (TypeError, ValueError) as e:
                logger.warning(f"Sina minute row 解析跳过 {symbol} {row!r}: {e}")
                continue
            if not in_date_range(dt, start_date, end_date):
                continue
            out.append(MinuteKline(
                symbol=bare,
                trade_datetime=dt,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=volume,
                amount=amount,
                period=f'{minutes}m',
                source=self.name,
                timestamp=datetime.now().isoformat(),
            ))

        if not out:
            # 上游有数据但都落在请求窗口外 = 「这个查询它没有」，不是源故障
            self.last_note = (
                f"新浪返回 {len(payload)} 根但均不在请求窗口 "
                f"[{start_date or '最早'} ~ {end_date or '最新'}]（需扩大回溯）"
            )
            return []

        problem = ohlc_sanity(out)
        if problem:
            self.last_error = f"新浪分钟线映射体检失败: {problem}"
            logger.error(f"Sina minute provider OHLC sanity failed for {symbol}: {problem}")
            return None

        logger.info(f"Sina minute provider returned {len(out)} bars for {symbol} {minutes}m")
        return limit_klines(out, limit)
