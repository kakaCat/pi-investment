"""东财分钟线 provider（通道：东财 push2his）—— **现场不可达，未注册**

## 打样记录（2026-09-11 本机实测，全部失败）

| 尝试 | 结果 |
|---|---|
| https://push2his.eastmoney.com/api/qt/stock/kline/get?...klt=5... 直连 | HTTP 000（连接被重置） |
| 同上 经系统代理 127.0.0.1:7897 | HTTP 000 ×5 次（python requests 同刻 ProxyError: RemoteDisconnected；同时刻 baidu 经同一代理 200） |
| 同上 经 ClashX 代理 127.0.0.1:7890 | HTTP 000 |
| http://push2his.eastmoney.com/...（明文） | HTTP 502（代理出口到上游不可达） |
| 1./7./63.push2his.eastmoney.com | HTTP 000 |
| https://push2delay.eastmoney.com/...klt=5 | 200，但 data.dktotal=0、klines 为空数组（延迟站点不提供分钟K线） |
| https://datacenter-web.eastmoney.com/api/data/v1/get | 200（该主机可达，但无分钟线接口） |

与 adapters/outbound/datasources/fund_flow_source.py 的注释一致：本机到
push2his.eastmoney.com 属**环境级不可达/间歇不可达**，非代码问题。

## 因此

按 RFC 015 §1.5 硬约束 3「契约先验证再注册」，**本 provider 未注册进
DataProviderManager.minute_kline_providers**：下面的字段映射按该接口族
（push2his kline，与 akshare stock_zh_a_hist* 同源）的公开契约实现，
**但从未用真实响应核对过**（klt 参数语义、klines 列的字段序均未验证）。

**启用前必须先做**：在 push2his 可达时 curl 打样，核对 data.klines[i] 的字段序
（本实现假定 f51=时间, f52=开, f53=收, f54=高, f55=低, f56=成交量(股),
f57=成交额(元), f58=振幅）、确认 secid 市场前缀（北交所存疑），再取消 manager
中的注释。OHLC 恒等式体检（ohlc_sanity）会拦下字段错位，但**不能替代打样**。
"""
import logging
from datetime import datetime
from typing import List, Optional

import requests

from adapters.outbound.datasources.providers.minute_kline.base import (
    MinuteKlineProvider, bars_needed, in_date_range, limit_klines,
    ohlc_sanity, period_minutes,
)
from domain.models.market_data import MinuteKline

logger = logging.getLogger(__name__)


class EastmoneyMinuteKlineProvider(MinuteKlineProvider):
    """东财 push2his 分钟线（**未注册**：见模块 docstring 的打样记录）"""

    # 东财必须经系统代理（本机直连被封）；不显式传 proxies，由 requests 走系统代理
    _URL = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
    _MAX_BARS = 1000
    _TIMEOUT = 12

    @property
    def name(self) -> str:
        return 'eastmoney_minute'

    def __init__(self):
        self.last_error: Optional[str] = None

    @staticmethod
    def _to_secid(symbol: str) -> Optional[str]:
        """600519 → 1.600519（沪）；000001 → 0.000001（深）；北交所前缀未验证"""
        bare = str(symbol or '').split('.')[0]
        if not bare.isdigit() or len(bare) != 6:
            return None
        if bare.startswith(('60', '68', '11', '51', '50', '58', '39')):
            return '1.' + bare
        if bare.startswith(('00', '30', '12', '15', '16', '18')):
            return '0.' + bare
        return None

    def get_minute_klines(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Optional[List[MinuteKline]]:
        self.last_error = None
        try:
            minutes = period_minutes(period)
        except ValueError as e:
            self.last_error = str(e)
            return None

        secid = self._to_secid(symbol)
        if not secid:
            self.last_error = f"代码 {symbol} 无法映射到东财 secid"
            return None

        count = bars_needed(period, start_date, end_date, limit, self._MAX_BARS)
        try:
            resp = requests.get(
                self._URL,
                params={
                    'secid': secid,
                    'klt': minutes,
                    'fqt': 1,
                    'beg': 0,
                    'end': 20500101,
                    'lmt': count,
                    'fields1': 'f1,f2,f3,f4,f5,f6',
                    'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Referer': 'https://quote.eastmoney.com/',
                },
                timeout=self._TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            self.last_error = f"网络/解析异常: {type(e).__name__}: {e}"
            logger.warning(f"Eastmoney minute provider request failed for {symbol}: {e}")
            return None

        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            rc = payload.get('rc') if isinstance(payload, dict) else '?'
            self.last_error = f"东财返回无 data（rc={rc}）"
            return None
        raw_rows = data.get('klines')
        if not isinstance(raw_rows, list) or not raw_rows:
            self.last_error = f"东财无 {symbol} 的 {minutes} 分钟数据"
            return None

        bare = str(symbol).split('.')[0]
        out: List[MinuteKline] = []
        for row in raw_rows:
            parts = str(row).split(',')
            if len(parts) < 6:
                continue
            try:
                dt = str(parts[0]).strip()
                open_p = float(parts[1])
                close = float(parts[2])
                high = float(parts[3])
                low = float(parts[4])
                volume = float(parts[5])
                amount = (float(parts[6]) if len(parts) > 6 and parts[6] not in ('-', '')
                          else round(volume * close, 2))
            except (TypeError, ValueError) as e:
                logger.warning(f"Eastmoney minute row 解析跳过 {symbol} {row!r}: {e}")
                continue
            if len(dt) == 16:
                dt = dt + ':00'
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
            self.last_error = f"东财返回 {len(raw_rows)} 行但均不在请求窗口内"
            return None

        problem = ohlc_sanity(out)
        if problem:
            self.last_error = f"东财分钟线映射体检失败: {problem}"
            logger.error(f"Eastmoney minute provider OHLC sanity failed for {symbol}: {problem}")
            return None

        return limit_klines(out, limit)
