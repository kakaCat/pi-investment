"""东方财富分红数据 provider（2026-09-11，REQ-cf627b，w-f436d4ea）

复用 application/services/dividend_data_source.py 里已存在但未接线的 EastMoneyDividendSource，
包成 DividendProvider 并注册进 manager 的故障转移链。

背景：此前 dividend_providers 只有 AkshareDividendProvider 一个，而它读错了
stock_dividend_cninfo 的列名（'每股派息'/'股息率'/'除权除息日' 在该接口不存在），
导致分红 history 静默返回全 0 行、被误读为『该公司不分红』。本 provider 作为
东财源（DIVIDENT_RATIO/PRETAX_BONUS_RMB 实测有值）提供 failover 与股息率补齐。
"""
import logging
from typing import Optional, List
from datetime import datetime

from adapters.outbound.datasources.base import DividendProvider
from adapters.outbound.datasources.models import DividendData

logger = logging.getLogger(__name__)


class EastmoneyDividendProvider(DividendProvider):
    """东方财富分红 provider（复用 application 层的 EastMoneyDividendSource）"""

    @property
    def name(self) -> str:
        return 'eastmoney'

    def _fetch_df(self, symbol: str):
        # 延迟 import，避免启动期强依赖
        from application.services.dividend_data_source import EastMoneyDividendSource
        return EastMoneyDividendSource(timeout=15).fetch_dividends(symbol)

    def get_dividends(self, symbol: str, years: int = 5) -> Optional[List[DividendData]]:
        try:
            df = self._fetch_df(symbol)
            if df is None or df.empty:
                return None
            result: List[DividendData] = []
            for _, row in df.head(years * 2).iterrows():
                dps = row.get('每股派息')
                try:
                    dps = float(dps) if dps is not None else None
                except (TypeError, ValueError):
                    dps = None
                if dps is None:
                    continue
                dy = row.get('股息率')
                try:
                    dy = float(dy) if dy is not None else None
                except (TypeError, ValueError):
                    dy = None
                def _d(col):
                    s = str(row.get(col, '') or '')
                    return s[:10] if s and s not in ('None', 'nan', 'NaT') else None
                result.append(DividendData(
                    symbol=symbol,
                    dividend_per_share=round(dps, 4),
                    dividend_yield=dy,
                    ex_dividend_date=_d('除权除息日'),
                    record_date=_d('股权登记日'),
                    pay_date=_d('派息日'),
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                ))
            return result if result else None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{self.name} get_dividends failed for {symbol}: {e}")
            return None

    def get_dividend_calendar(self, start_date: str, end_date: str) -> Optional[List[DividendData]]:
        # 日历模式需求低，先不提供（返回 None 让 manager 继续 failover）
        return None

    def screen_high_dividend(self, min_yield: float = 3.0, min_years: int = 5,
                             max_candidates: int = 30) -> Optional[List[DividendData]]:
        """全市场高股息筛选（东财 datacenter）。

        口径（诚实标注，勿过度解读）：
          ① 全市场【最近一个报告期】分红记录中，股息率 >= min_yield 且每股派息 > 0 的候选
             （RPT_SHAREBONUS_DET 只含最近报告期，不含历史年度）
          ② 对候选按股息率降序取前 max_candidates 只，逐只拉该个股历史
             （EastMoneyDividendSource 个股接口，含全年度），校验连续 min_years 个年度有分红
        """
        try:
            import concurrent.futures
            import requests
            import pandas as pd
            from application.services.dividend_data_source import EastMoneyDividendSource

            base = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            frames = []
            for page in range(1, 6):  # 最多 5000 条（5×1000）
                params = {
                    "reportName": "RPT_SHAREBONUS_DET", "columns": "ALL",
                    "pageNumber": page, "pageSize": 1000, "sortTypes": "-1",
                    "sortColumns": "REPORT_DATE", "source": "WEB", "client": "WEB",
                }
                r = requests.get(base, params=params, timeout=15, headers=headers)
                r.raise_for_status()
                data = r.json()
                if data.get("code") != 0:
                    break
                recs = (data.get("result") or {}).get("data") or []
                if not recs:
                    break
                frames.append(pd.DataFrame(recs))
                if len(recs) < 1000:
                    break
            if not frames:
                return None
            df = pd.concat(frames, ignore_index=True)
            df["_dps"] = pd.to_numeric(df.get("PRETAX_BONUS_RMB"), errors="coerce") / 10.0
            df["_dy"] = pd.to_numeric(df.get("DIVIDENT_RATIO"), errors="coerce") * 100.0
            cand = df[(df["_dy"] >= min_yield) & (df["_dps"] > 0)].sort_values("_dy", ascending=False)
            cand = cand.head(max_candidates)
            if cand.empty:
                return None

            src = EastMoneyDividendSource(timeout=10)

            def _consec_years(code: str) -> int:
                hdf = src.fetch_dividends(code)
                if hdf is None or hdf.empty or "分红年度" not in hdf.columns:
                    return 0
                yrs = sorted({int(y) for y in hdf["分红年度"].astype(str) if str(y).isdigit()}, reverse=True)
                if not yrs:
                    return 0
                consec, prev = 1, yrs[0]
                for y in yrs[1:]:
                    if y == prev - 1:
                        consec += 1
                        prev = y
                    else:
                        break
                return consec

            def _build(row) -> Optional[DividendData]:
                code = str(row["SECURITY_CODE"])
                try:
                    if _consec_years(code) < min_years:
                        return None
                except Exception:
                    return None
                return DividendData(
                    symbol=code,
                    dividend_per_share=round(float(row["_dps"]), 4),
                    dividend_yield=round(float(row["_dy"]), 4),
                    ex_dividend_date=str(row.get("EX_DIVIDEND_DATE") or "")[:10] or None,
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
                result = [x for x in ex.map(_build, [r for _, r in cand.iterrows()]) if x]
            result.sort(key=lambda x: x.dividend_yield or 0, reverse=True)
            return result if result else None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{self.name} screen_high_dividend failed: {e}")
            return None
