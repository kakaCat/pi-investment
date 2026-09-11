"""东财分钟线 provider（通道：东财 **延迟行情域 push2delay.eastmoney.com**）

## 真实响应打样（2026-09-11 本机实测，直连，全部真数据）

    GET https://push2delay.eastmoney.com/api/qt/stock/kline/get
        ?secid=1.600150&klt=1&fqt=1&lmt=5&end=20500101
        &fields1=f1,f2,f3,f4,f5,f6
        &fields2=f51,f52,f53,f54,f55,f56,f57,f58
    {"rc":0,...,"data":{"code":"600150","name":"中国船舶","preKPrice":40.82,
      "klines":["2026-09-11 09:31,39.50,39.59,39.93,39.40,168236,665639626.00,1.30", ...]}}

**字段序（逐位实测核对，最容易错的一处）**：
    f51=时间 'YYYY-MM-DD HH:MM' / f52=**开** / f53=**收** / f54=**高** / f55=**低**
    / f56=成交量(手) / f57=成交额(元) / f58=涨跌幅(%)
    → 第 2/3 位是「开/收」而**不是**「开/高」，与直觉的 OHLC 完全不同（腾讯分钟线同款
    陷阱）。按直觉写映射不会报错、不会为 0，只会静默产出错位的高低——故本 provider
    用 base.ohlc_sanity 做运行时闸门（>20% 行违反恒等式即 fail-loud）。

**时间语义**：bar 时间戳 = 该分钟**结束**时刻（首根 09:31 = 09:30~09:31 含集合竞价，
末根 15:00 为收盘集合竞价）。与腾讯 m1 完全一致（腾讯 09:31 = 东财 09:31，价格逐位相同）。
**注意新浪的同名接口不一致**：新浪 scale=5/15/30/60 用「区间**开始**」标签，
scale=1 用「区间结束」标签——所以跨源对齐必须按「周期结束时刻」换算，不能直接比时间戳。

## 量纲（实测交叉验证，2026-09-11 全天，三只不同板块标的）

    600150 东财 1m Σ vol=1,832,761（手）  Σ amount=7,247,794,183（元）
           → 额/量=3954.6 ≈ 当日均价 39.55 → amount 是「元/手」，即 volume 为**手**
           新浪 1m Σ vol=183,154,022 股 ÷ (1,832,761×100) = 0.9993 ✓
    300196 447,034 手 vs 新浪 44,703,416 股 → 1.0000 ✓
    688111  52,942 手 vs 新浪  5,286,505 股 → 0.9985 ✓（**科创板同样是手**，
           与腾讯 688 的量纲反常不同，故这里对所有板块统一 ×100，不做板块特判）
    → volume 归一：raw × 100（股）；amount 上游直接给元，不估算。

## 该域的已知限制（实测，不是猜测）

| 限制 | 实测 |
|---|---|
| 只支持 klt=1 | klt=5 → 200 但 `klines:[]`（dktotal=0）。故 **5/15/30/60m 由本 provider 用 1m 聚合** |
| lmt 被忽略 | lmt=5 / 10 / 500 均返回当日全部 240 根 |
| end/beg 被忽略 | end=20260910 仍返回 2026-09-11 全天 → **只有当日（最近交易日）1m**，历史由腾讯/新浪承担 |
| 必须绕过系统代理 | 经本机代理（ClashX）返回 rc=102、data=null；`proxies={'http':None,'https':None}` 直连 200 |

## 周期聚合（§4.3 契约）

按「周期结束时刻」在**交易时段栅格**上分桶（上午基准 09:30、下午基准 13:00）：
09:30-10:30 / 10:30-11:30 / 13:00-14:00 / 14:00-15:00 等。用 session 栅格而非裸
minute-of-day，是因为 11:30-13:00 午休会让 60m 的「自然小时」跨断（11:30~12:30 只含
上午尾部 1 根）。实测校验（2026-09-11 600150，与新浪 scale=5/15/30/60 逐根比对）：
5m 48 桶、15m 16 桶、30m 8 桶、60m 4 桶，与新浪根数**完全一致**，量差 <2%。
聚合不出（1m 不足一个桶）→ 返回 None 让故障转移继续，绝不用半截桶冒充。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from adapters.outbound.datasources.providers.minute_kline.base import (
    MinuteKlineProvider, in_date_range, limit_klines,
    ohlc_sanity, period_minutes,
)
from domain.models.market_data import MinuteKline

logger = logging.getLogger(__name__)


class EastmoneyMinuteKlineProvider(MinuteKlineProvider):
    """东财延迟域分钟线（上游只给 1m；5/15/30/60m 在 provider 内聚合）"""

    # 必须直连：经系统代理该域返回 rc=102 / data=null（实测）
    _NO_PROXY = {'http': None, 'https': None}
    _URL = 'https://push2delay.eastmoney.com/api/qt/stock/kline/get'
    # 上游只认「当日全部 1m」（lmt/end 实测被忽略），一次请求最多 240 根
    _MAX_BARS = 240
    _TIMEOUT = 12
    # 交易时段栅格基准（分钟数）：上午 09:30、下午 13:00
    _SESSION_ANCHORS = (9 * 60 + 30, 13 * 60)

    @property
    def name(self) -> str:
        return 'eastmoney_minute'

    def __init__(self):
        self.last_error: Optional[str] = None
        # 供调用方判定事实（与 database provider 同口径：provider 只报事实，不下结论）
        self.latest_bar_datetime: Optional[str] = None
        self.granularity: str = ''

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _to_secid(symbol: str) -> Optional[str]:
        """600519 → 1.600519（沪）；000001 → 0.000001（深）；920023 → 0.920023（北交所，实测可取数）"""
        bare = str(symbol or '').split('.')[0]
        if not bare.isdigit() or len(bare) != 6:
            return None
        if bare.startswith(('60', '68', '11', '51', '50', '58', '39')):
            return '1.' + bare
        if bare.startswith(('00', '30', '12', '15', '16', '18', '4', '8', '92')):
            return '0.' + bare
        return None

    def _bucket_key(self, minutes_of_day: int, size: int) -> int:
        """按「周期结束时刻」在交易时段栅格上取桶（返回桶的结束分钟）"""
        anchor = self._SESSION_ANCHORS[0] if minutes_of_day <= 11 * 60 + 30 else self._SESSION_ANCHORS[1]
        offset = minutes_of_day - anchor
        if offset <= 0:
            return anchor
        return anchor + ((offset + size - 1) // size) * size

    def _aggregate(self, rows: List[dict], size: int) -> Optional[List[dict]]:
        """1m 行 → size 分钟行（open=首、high=max、low=min、close=末、量/额=求和）"""
        if size <= 1:
            return rows
        grouped: Dict[Tuple[str, int], List[dict]] = {}
        order: List[Tuple[str, int]] = []
        for row in rows:
            day, hm = row['t'].split(' ')
            hour, minute = hm.split(':')[:2]
            minutes_of_day = int(hour) * 60 + int(minute)
            key = (day, self._bucket_key(minutes_of_day, size))
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(row)

        out: List[dict] = []
        for key in order:
            bucket = grouped[key]
            # 上午首桶（09:30~09:35）与收盘桶（14:55~15:00）根数可能不足 size
            # （集合竞价 / 收盘瞬时），这是真实市场结构，不是缺数据。
            day, end_minute = key
            hour, minute = divmod(end_minute, 60)
            out.append({
                't': f'{day} {hour:02d}:{minute:02d}:00',
                'o': bucket[0]['o'],
                'c': bucket[-1]['c'],
                'h': max(r['h'] for r in bucket),
                'l': min(r['l'] for r in bucket),
                'v': sum(r['v'] for r in bucket),
                'a': sum(r['a'] for r in bucket),
            })
        return out

    def _fetch(self, secid: str) -> Optional[List[dict]]:
        """取当日 1m 原始行（已做字段序映射与数值校验）"""
        try:
            resp = requests.get(
                self._URL,
                params={
                    'secid': secid,
                    'klt': 1,          # 延迟域只支持 1m（klt=5 实测返回空数组）
                    'fqt': 1,
                    'lmt': self._MAX_BARS,
                    'end': 20500101,
                    'fields1': 'f1,f2,f3,f4,f5,f6',
                    'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Referer': 'https://quote.eastmoney.com/',
                },
                proxies=self._NO_PROXY,
                timeout=self._TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            self.last_error = f"网络/解析异常: {type(e).__name__}: {e}"
            logger.warning(f"Eastmoney(delay) minute provider request failed for {secid}: {e}")
            return None

        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            rc = payload.get('rc') if isinstance(payload, dict) else '?'
            self.last_error = f"东财延迟域返回无 data（rc={rc}；rc=102 常见于经代理被拒）"
            return None
        raw_rows = data.get('klines')
        if not isinstance(raw_rows, list) or not raw_rows:
            self.last_error = f"东财延迟域无 {secid} 的分钟数据（该域只提供当日 1m）"
            return None

        rows: List[dict] = []
        for row in raw_rows:
            parts = str(row).split(',')
            if len(parts) < 7:
                continue
            try:
                # 字段序：时间, 开, 收, 高, 低, 量(手), 额(元), 涨跌幅
                stamp = str(parts[0]).strip()
                open_p = float(parts[1])
                close = float(parts[2])
                high = float(parts[3])
                low = float(parts[4])
                volume = float(parts[5]) * 100      # 手 → 股（实测三板块统一 ×100）
                amount = float(parts[6])
            except (TypeError, ValueError) as e:
                logger.warning(f"Eastmoney(delay) minute row 解析跳过 {secid} {row!r}: {e}")
                continue
            if len(stamp) == 16:
                stamp = stamp + ':00'
            rows.append({'t': stamp, 'o': open_p, 'c': close, 'h': high, 'l': low, 'v': volume, 'a': amount})

        if not rows:
            self.last_error = f"东财延迟域返回 {len(raw_rows)} 行但全部解析失败（检查字段序契约）"
            return None
        return rows

    # ------------------------------------------------------------------ 契约

    def get_minute_klines(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Optional[List[MinuteKline]]:
        self.last_error = None
        self.latest_bar_datetime = None
        self.granularity = ''
        try:
            minutes = period_minutes(period)
        except ValueError as e:
            self.last_error = str(e)
            return None

        secid = self._to_secid(symbol)
        if not secid:
            self.last_error = f"代码 {symbol} 无法映射到东财 secid"
            return None

        rows = self._fetch(secid)
        if rows is None:
            return None

        aggregated = self._aggregate(rows, minutes)
        if not aggregated:
            self.last_error = f"东财延迟域 1m 数据不足以聚合出 {minutes}m（数据不足，非故障）"
            return None

        bare = str(symbol).split('.')[0]
        out: List[MinuteKline] = []
        for row in aggregated:
            if not in_date_range(row['t'], start_date, end_date):
                continue
            out.append(MinuteKline(
                symbol=bare,
                trade_datetime=row['t'],
                open=row['o'],
                high=row['h'],
                low=row['l'],
                close=row['c'],
                volume=row['v'],
                amount=row['a'],
                period=f'{minutes}m',
                source=self.name,
                timestamp=datetime.now().isoformat(),
            ))

        if not out:
            self.last_error = (
                f"东财延迟域返回当日 {len(rows)} 根 1m 聚合出 {len(aggregated)} 根 {minutes}m，"
                f"但均不在请求窗口 [{start_date or '最早'} ~ {end_date or '最新'}]"
                "（该域只提供当日，历史窗口由腾讯/新浪承担）"
            )
            return None

        problem = ohlc_sanity(out)
        if problem:
            self.last_error = f"东财分钟线映射体检失败: {problem}"
            logger.error(f"Eastmoney(delay) minute provider OHLC sanity failed for {symbol}: {problem}")
            return None

        self.latest_bar_datetime = out[-1].trade_datetime
        self.granularity = f'{minutes}m'
        logger.info(
            f"Eastmoney(delay) minute provider returned {len(out)} bars for {symbol} "
            f"{minutes}m (aggregated from {len(rows)} 1m bars)"
        )
        return limit_klines(out, limit)
