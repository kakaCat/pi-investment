"""
EastmoneySectorProvider - 东方财富板块成分数据源

提供行业板块/概念板块的成分股查询。

网络容错设计：
- proxies={'http': None, 'https': None}：绕过本地代理（如 ClashX），
  国内行情接口经境外代理出口会被重置/极慢。
- 多主机容错：实时 push2 主机可能被 eastmoney WAF 按 IP 限流（TCP 重置），
  自动回退到 push2delay（延时行情）。板块名单/成分为静态数据，延时无影响。
- 分页拉取：部分主机单页上限 100，需按 pn 翻页取全量。
"""
import logging
from datetime import datetime
from typing import Optional

import requests

from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)

_UT = "bd1d9ddb04089700cf9c27f6f7426281"
# 按优先级排序：实时主机在前，延时主机兜底
_HOSTS = [
    "https://17.push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
]
# 板块列表 fs：行业板块(t:2) + 概念板块(t:3)（如"白酒"属概念板块）
_BOARD_FS = ("m:90+t:2+f:!50", "m:90+t:3+f:!50")
_NO_PROXY = {'http': None, 'https': None}


class EastmoneySectorProvider(MarketProvider):
    """东方财富板块成分数据提供者"""

    @property
    def name(self) -> str:
        return "eastmoney"

    # ── 板块成分（本 provider 的核心能力） ─────────────────────

    def get_sector_stocks(self, sector: str) -> Optional[MarketData]:
        """获取板块成分股（含 PE、总市值）。

        Args:
            sector: 板块名称（行业或概念，如 '白酒'、'电力'）

        Returns:
            MarketData(data_type='sector_stocks')，data 含 found/sector_code/stocks。
            网络全部失败时抛异常（交给 manager 故障转移）。
        """
        sector_code = None
        for fs in _BOARD_FS:
            for board in self._clist_all(fs=fs, fields="f12,f14"):
                if str(board.get("f14", "")) == sector:
                    sector_code = str(board.get("f12", ""))
                    break
            if sector_code:
                break

        if sector_code is None:
            # 成功取到板块名单但未匹配 → 明确的"板块不存在"（有效响应，非网络错误）
            return MarketData(
                data_type='sector_stocks',
                data={'sector': sector, 'found': False, 'sector_code': None, 'stocks': []},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )

        rows = self._clist_all(fs=f"b:{sector_code}", fields="f12,f14,f9,f20")
        stocks = [{
            'symbol': str(r.get('f12', '')),
            'name': str(r.get('f14', '')),
            'pe': self._safe_float(r.get('f9')),
            'market_cap': self._safe_float(r.get('f20')),  # 总市值（元）
        } for r in rows]

        return MarketData(
            data_type='sector_stocks',
            data={
                'sector': sector,
                'found': True,
                'sector_code': sector_code,
                'stocks': stocks,
                'count': len(stocks),
            },
            source=self.name,
            timestamp=datetime.now().isoformat(),
        )

    # ── 内部：clist 多主机容错 + 分页 ─────────────────────────

    def _clist_page(self, fs: str, fields: str, pn: int, pz: int) -> tuple:
        """单页 clist 请求，按优先级尝试多个主机。返回 (diff, total)。"""
        last_err = None
        for host in _HOSTS:
            try:
                resp = requests.get(
                    f"{host}/api/qt/clist/get",
                    params={
                        'pn': pn, 'pz': pz, 'po': 1, 'np': 1, 'ut': _UT,
                        'fltt': 2, 'invt': 2, 'fid': 'f3',
                        'fs': fs, 'fields': fields,
                    },
                    timeout=self.timeout,
                    proxies=_NO_PROXY,
                )
                resp.raise_for_status()
                data = resp.json().get('data') or {}
                diff = data.get('diff')
                if diff is not None:
                    return diff, data.get('total', len(diff))
            except Exception as e:  # 连接被重置/超时 → 尝试下一主机
                last_err = e
                logger.debug("eastmoney clist failed on %s (fs=%s pn=%d): %s", host, fs, pn, e)
        raise last_err or RuntimeError("eastmoney clist: no data available")

    def _clist_all(self, fs: str, fields: str, pz: int = 100, max_pages: int = 20) -> list:
        """分页拉取全部 clist 数据。"""
        rows, pn = [], 1
        while pn <= max_pages:
            diff, total = self._clist_page(fs=fs, fields=fields, pn=pn, pz=pz)
            if not diff:
                break
            rows.extend(diff)
            if len(rows) >= (total or 0) or len(diff) < pz:
                break
            pn += 1
        return rows

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            if value is None or value == '' or value == '-':
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    # ── MarketProvider 抽象方法（本 provider 未实现，返回 None） ──

    def get_market_overview(self) -> Optional[MarketData]:
        return None

    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        return None

    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        return None
