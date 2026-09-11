"""腾讯分钟线 provider（通道：腾讯 ifzq.gtimg.cn）

真实响应打样（2026-09-11 本机实测，600150 / 688111）：
    GET https://ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh600150,m5,,10
    {"code":0,"msg":"","data":{"sh600150":{
        "m5":[["202609111415","39.65","39.78","39.82","39.65","11796.00",{},"1.57"], ...],
        "prec":40.82, "qt":{...}}}}
字段序（实测逐位比对）：[时间 YYYYMMDDHHMM, 开, 收, 高, 低, 成交量, {}, 换手率]
    → 注意第 2/3 位是 **开/收**（不是开/高），误读会把 OHLC 错位成 high/low。

**接口地址修正（2026-09-11 实测）**：设计要求里的 web.ifzq.gtimg.cn 现已
301 → web3.ifzq.gtimg.cn，而该主机 **DNS 无解析**（nslookup: No answer）——
requests 默认跟随重定向会直接撞 DNS 失败。实测可用主机为 **ifzq.gtimg.cn**
（去掉 web. 前缀）与 proxy.finance.qq.com（同一上游，不另立通道）。

量纲（实测交叉验证，与 kline/tencent.py 的日线结论一致）：
    600150（主板）m5 14:15 腾讯 11796 vs 新浪 1,250,028 股 → 腾讯为「手」，×100
    688111（科创板）m5 14:40 腾讯 101150 vs 新浪 101,390 股 → 腾讯已是「股」，不得 ×100
故：688/689 不做换算，其余 ×100。amount 上游不返回 → 按 volume×close 估算
（与 KlineData 契约中「provider 负责估算成交额」同口径）。

国内源必须绕过本机代理（ClashX/verge 国外出口会被重置），与
providers/kline/tencent.py 的 _NO_PROXY 用法一致。
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


class TencentMinuteKlineProvider(MinuteKlineProvider):
    """腾讯分钟线（m1/m5/m15/m30/m60）"""

    _NO_PROXY = {'http': None, 'https': None}
    _URL = 'https://ifzq.gtimg.cn/appstock/app/kline/mkline'
    _MAX_BARS = 1000
    _TIMEOUT = 10

    @property
    def name(self) -> str:
        return 'tencent_minute'

    def __init__(self):
        self.last_error: Optional[str] = None
        # 「无数据」的诊断说明（健康路径，见 base.py 的三态契约）：
        # 空列表 + last_note 才是「该源对此查询没有数据」，不得写成 last_error
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

        code = to_prefixed_code(symbol)
        if not code:
            self.last_error = f"代码 {symbol} 无法映射到交易所前缀（腾讯需 sh/sz/bj 前缀）"
            return None

        count = bars_needed(period, start_date, end_date, limit, self._MAX_BARS)
        try:
            resp = requests.get(
                self._URL,
                params={'param': f'{code},m{minutes},,{count}'},
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                proxies=self._NO_PROXY,
                timeout=self._TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            self.last_error = f"网络/解析异常: {type(e).__name__}: {e}"
            logger.warning(f"Tencent minute provider request failed for {symbol}: {e}")
            return None

        if payload.get('code') != 0:
            # 上游自报错误码 = 真故障（服务端拒绝/参数错误），必须 fail-loud
            self.last_error = f"腾讯接口返回错误: {payload.get('msg')}"
            return None

        data_field = payload.get('data')
        node = data_field.get(code) if isinstance(data_field, dict) else None
        if not isinstance(node, dict):
            self.last_error = f"腾讯响应结构异常：data.{code} 缺失（代码不存在或无数据）"
            return None

        rows = node.get(f'm{minutes}')
        if not isinstance(rows, list) or not rows:
            # 空结果 ≠ 故障（2026-09-11 P10 修复）：契约规定空列表=该源无此数据，
            # 之前写成 last_error+None 会被 manager 计真故障 → 累计连续失败 → 熔断该源。
            # 现在返回 [] + last_note：健康路径，不计故障；诊断文本经 manager 透到
            # provider_errors，排障信息不丢。
            self.last_note = f"腾讯无 {symbol} 的 m{minutes} 数据（代码不存在或该时段无交易）"
            return []

        bare = str(symbol).split('.')[0]
        is_star = bare.startswith(('688', '689'))
        is_index = bare.startswith('39')
        out: List[MinuteKline] = []
        for row in rows:
            try:
                raw_dt = str(row[0])
                dt = f"{raw_dt[0:4]}-{raw_dt[4:6]}-{raw_dt[6:8]} {raw_dt[8:10]}:{raw_dt[10:12]}:00"
                open_p = float(row[1])
                close = float(row[2])
                high = float(row[3])
                low = float(row[4])
                raw_vol = float(row[5])
            except (IndexError, TypeError, ValueError) as e:
                logger.warning(f"Tencent minute row 解析跳过 {symbol} {row!r}: {e}")
                continue
            if not in_date_range(dt, start_date, end_date):
                continue
            # 量纲：688/689（科创）上游已是股；指数行的量是成分股聚合量，不做 ×100 换算
            volume = raw_vol if (is_star or is_index) else raw_vol * 100
            out.append(MinuteKline(
                symbol=bare,
                trade_datetime=dt,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=volume,
                amount=round(volume * close, 2),
                period=f'{minutes}m',
                source=self.name,
                timestamp=datetime.now().isoformat(),
            ))

        if not out:
            # 上游有数据但都落在请求窗口外 = 「这个查询它没有」，不是源故障
            self.last_note = (
                f"腾讯返回 {len(rows)} 根但均不在请求窗口 "
                f"[{start_date or '最早'} ~ {end_date or '最新'}]（需扩大回溯）"
            )
            return []

        problem = ohlc_sanity(out)
        if problem:
            self.last_error = f"腾讯分钟线映射体检失败: {problem}"
            logger.error(f"Tencent minute provider OHLC sanity failed for {symbol}: {problem}")
            return None

        logger.info(f"Tencent minute provider returned {len(out)} bars for {symbol} m{minutes}")
        return limit_klines(out, limit)
