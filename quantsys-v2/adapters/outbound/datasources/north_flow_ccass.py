"""
北向持股数据源 - 港交所披露易 CCASS（官方渠道）

背景：东财自 2024-08-17 起停止披露北向每日净买入（交易所层面停止公布
实时资金流），免费 API 无替代。但港交所 CCASS 仍每日披露北向持股量，
可用「持股变化 × 收盘价」估算净买入。

端点：https://www3.hkexnews.hk/sdw/search/mutualmarket_c.aspx?t=sh|t=sz
（ASP.NET postback 表单，实测 2026-07-28 可用）

CCASS 代码映射（实测归纳）：
    60XXXX → 9XXXX    （沪市主板，601398→91398）
    000XXX → 70XXX    （深市主板，000725→70725）
    001XXX → 71XXX
    002XXX → 72XXX    （002594→72594）
    003XXX → 73XXX
    300XXX → 77XXX    （300750→77750）
    301XXX → 78XXX
    159XXX → 31XXX    （深市 ETF，推断）
"""
import logging
import re
from datetime import datetime, timedelta
from io import StringIO
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_URL = "https://www3.hkexnews.hk/sdw/search/mutualmarket_c.aspx"

# 前缀映射：CCASS 前缀 → A 股前缀（按前缀长度降序匹配）
_CCASS_PREFIX_MAP = [
    ('9', '60'),
    ('70', '00'),
    ('71', '001'),
    ('72', '002'),
    ('73', '003'),
    ('77', '300'),
    ('78', '301'),
    ('31', '159'),
]


def map_ccass_symbol(ccass_code: str) -> Optional[str]:
    """CCASS 代码 → A 股 6 位代码（无法映射返回 None）"""
    code = str(ccass_code).strip()
    for ccass_prefix, a_prefix in _CCASS_PREFIX_MAP:
        if code.startswith(ccass_prefix):
            suffix = code[len(ccass_prefix):]
            mapped = a_prefix + suffix
            if len(mapped) == 6:
                return mapped
    return None


class NorthHoldingsCCASSSource:
    """北向持股 CCASS 数据源"""

    name = "hkex_ccass"

    def __init__(self):
        self._cache: Dict[str, List[Dict]] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=6)

    def fetch_holdings(self, date: str, market: str = 'sh') -> List[Dict]:
        """获取某日北向持股快照（见 fetch_holdings_dated，丢弃实际日期）"""
        _, records = self.fetch_holdings_dated(date, market)
        return records

    def fetch_holdings_dated(self, date: str, market: str = 'sh') -> tuple:
        """获取北向持股快照，返回 (实际持股日期, 记录列表)

        ⚠️ 2024-08 交易所规则变更后，北向持股改为【季度】披露：
        请求任意日期，CCASS 返回最近一次披露（季度末）的数据。
        页面标注「持股日期: YYYY/MM/DD」，必须读它才知道数据的真实日期。

        Args:
            date: YYYY-MM-DD（请求日期）
            market: 'sh'（沪股通）| 'sz'（深股通）

        Returns:
            (actual_date: str 'YYYY-MM-DD', [{symbol, name, shares_held, pct_of_issued}])
        """
        cache_key = f"{market}:{date}"
        if cache_key in self._cache and \
                datetime.now() - self._cache_time[cache_key] < self._cache_ttl:
            return self._cache[cache_key]

        actual_date, records = self._fetch_holdings_raw(date, market)
        result = (actual_date, records)
        self._cache[cache_key] = result
        self._cache_time[cache_key] = datetime.now()
        return result

    def _fetch_holdings_raw(self, date: str, market: str) -> List[Dict]:
        import pandas as pd
        import requests

        session = requests.Session()
        session.trust_env = False  # 绕过系统代理

        url = f"{_URL}?t={market}"
        resp = session.get(url, timeout=20)
        resp.raise_for_status()

        def hidden(name: str) -> str:
            m = re.search(rf'id="{name}" value="([^"]*)"', resp.text)
            return m.group(1) if m else ''

        payload = {
            '__EVENTTARGET': 'btnSearch',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': hidden('__VIEWSTATE'),
            '__VIEWSTATEGENERATOR': hidden('__VIEWSTATEGENERATOR'),
            'today': hidden('today'),
            'sortBy': 'shareholding',
            'sortDirection': 'desc',
            'alertMsg': '',
            'txtShareholdingDate': date.replace('-', '/'),
        }
        resp2 = session.post(url, data=payload, timeout=40)
        resp2.raise_for_status()

        # 页面标注的实际持股日期（季度披露，与请求日期不同）
        actual_date = None
        m = re.search(r'持股日期[：:]\s*(\d{4})/(\d{2})/(\d{2})', resp2.text)
        if m:
            actual_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        tables = pd.read_html(StringIO(resp2.text))
        if not tables:
            raise ValueError(f"CCASS {market} {date}: 响应中无表格")

        table = max(tables, key=len)
        records = []
        for _, row in table.iterrows():
            cells = [str(c) for c in row.tolist()]
            if len(cells) < 4:
                continue  # 表尾注释行（合并单元格）
            # 单元格形如「股份代號: 91398」
            code_m = re.search(r'(\d+)', cells[0])
            shares_m = re.search(r'([\d,]+)', cells[2])
            pct_m = re.search(r'([\d.]+)', cells[3])
            if not code_m or not shares_m:
                continue
            symbol = map_ccass_symbol(code_m.group(1))
            if not symbol:
                continue
            name = cells[1].split(':', 1)[-1].strip()
            records.append({
                'symbol': symbol,
                'name': name,
                'shares_held': int(shares_m.group(1).replace(',', '')),
                'pct_of_issued': float(pct_m.group(1)) if pct_m else None,
            })

        logger.info(f"CCASS {market} 请求 {date}: 实际持股日期 {actual_date}, {len(records)} 只")
        return actual_date, records

    def find_latest_two_disclosures(self) -> List[str]:
        """找最近两个实际披露日（季度披露，约隔 90 天）

        注意：盘中查询「今天」CCASS 不回退（返回空页），需向前回退几天。
        """
        latest_date = None
        for i in range(1, 6):
            probe = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            d, records = self.fetch_holdings_dated(probe, 'sh')
            if d and records:
                latest_date = d
                break
        if not latest_date:
            return []

        back = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=100))
        prev_date, prev_records = self.fetch_holdings_dated(
            back.strftime('%Y-%m-%d'), 'sh')
        if not prev_date or prev_date == latest_date:
            return [latest_date]

        return [latest_date, prev_date]
