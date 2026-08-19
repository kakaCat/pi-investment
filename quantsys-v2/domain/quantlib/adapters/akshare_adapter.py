"""AkShare market data adapter implementation.

Wraps every akshare call behind the BaseMarketAdapter interface so that
business logic never touches akshare directly.  When akshare changes an
API signature or a column name, ONLY this file needs updating.

All public methods return standardised Python dicts / lists — never raw
akshare DataFrames.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

try:
    import akshare as ak
except ImportError:
    # Graceful degradation — no crash on missing optional dependency
    class _AkShareUnavailable:  # type: ignore[no-redef]
        """Stub when akshare is not installed."""

        _AK_UNAVAILABLE_MSG = "akshare is not installed — install with: pip install akshare"

        def __getattr__(self, _name: str) -> Any:
            def _raise(*_a: Any, **_kw: Any) -> pd.DataFrame:
                raise ImportError(self._AK_UNAVAILABLE_MSG)
            return _raise

    ak = _AkShareUnavailable()

from .base_adapter import BaseMarketAdapter


# ---------------------------------------------------------------------------
# Column name normalisers
# ---------------------------------------------------------------------------

_COL_MAP_EASTMONEY: dict[str, str] = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "change_pct",
    "涨跌额": "change",
    "换手率": "turnover_rate",
}

# Tencent source has English column names but sometimes uses "amount" for volume
_COL_MAP_TENCENT: dict[str, str] = {
    "date": "date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
}


def _normalise_frame(df: pd.DataFrame, col_map: dict[str, str]) -> pd.DataFrame:
    """Rename columns in *df* using *col_map* (only columns present in df)."""
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    return df.rename(columns=rename)


# ========================================================================
# AkShareAdapter
# ========================================================================

class AkShareAdapter(BaseMarketAdapter):
    """AkShare-backed implementation of BaseMarketAdapter.

    Usage::

        adapter = AkShareAdapter()
        info = adapter.get_stock_info("000001.SZ")
        klines = adapter.get_klines("000001.SZ", "daily", "20240101", "20240131")
        quotes = adapter.get_realtime_quote(["000001.SZ", "600000.SH"])
    """

    # ------------------------------------------------------------------
    # get_stock_info
    # ------------------------------------------------------------------

    def get_stock_info(self, symbol: str) -> dict:
        """Fetch stock metadata via akshare's East Money individual-info API.

        Returns a dict with keys: symbol, name, market, industry, list_date.
        Returns an empty dict on any failure.
        """
        try:
            code, _prefix = self.internal_to_akshare(symbol)
            market_char = self._market_char(symbol)

            # East Money individual stock info
            raw = ak.stock_individual_info_em(symbol=code)
            if raw is None or raw.empty:
                return {}

            # stock_individual_info_em returns a DataFrame with columns "item" / "value"
            info: dict[str, Any] = {
                "symbol": symbol,
                "name": "",
                "market": "A" if market_char != "HK" else "HK",
                "industry": None,
                "list_date": None,
            }

            item_map: dict[str, str] = {
                "股票简称": "name",
                "行业": "industry",
                "上市时间": "list_date",
            }
            for _, row in raw.iterrows():
                item = str(row.get("item", ""))
                value = row.get("value")
                if item in item_map:
                    key = item_map[item]
                    val = str(value) if value is not None and not pd.isna(value) else None
                    if key == "list_date" and val:
                        val = self._normalise_date_display(val)
                    info[key] = val

            return info
        except ImportError:
            return {"symbol": symbol, "error": "akshare not installed"}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # get_klines
    # ------------------------------------------------------------------

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Fetch klines from akshare.  Supports A-share and Hong Kong markets.

        *period*: "daily" | "weekly" | "monthly" | "1m" | "5m" | "15m" | "30m" | "60m"
        *start_date* / *end_date*: YYYYMMDD or YYYY-MM-DD (for minute data: YYYY-MM-DD HH:MM:SS)
        """
        # Check if minute-level period
        if period in ["1m", "5m", "15m", "30m", "60m"]:
            return self._fetch_minute_klines(symbol, period, start_date, end_date)

        start = self._normalise_date(start_date)
        end = self._normalise_date(end_date)
        period_ak = self._map_period(period)
        market_char = self._market_char(symbol)

        try:
            if market_char == "HK":
                return self._fetch_hk_klines(symbol, period_ak, start, end)
            return self._fetch_a_share_klines(symbol, period_ak, start, end)
        except ImportError:
            return []
        except Exception:
            return []

    def _fetch_a_share_klines(
        self, symbol: str, period: str, start: str, end: str
    ) -> list[dict]:
        """Fetch A-share klines with East Money → Tencent fallback."""
        code, _prefix = self.internal_to_akshare(symbol)

        # Try East Money first (preferred — has more columns)
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            return self._frame_to_kline_list(symbol, df, _COL_MAP_EASTMONEY)
        except Exception:
            pass

        # Fall back to Tencent
        try:
            prefix = self.exchange_prefix(code)
            tx_symbol = f"{prefix}{code}"
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            # Tencent may use "amount" for volume — fix it
            if "amount" in df.columns and "volume" not in df.columns:
                df = df.rename(columns={"amount": "volume"})
            return self._frame_to_kline_list(symbol, df, _COL_MAP_TENCENT)
        except Exception:
            return []

    def _fetch_hk_klines(
        self, symbol: str, period: str, start: str, end: str
    ) -> list[dict]:
        """Fetch Hong Kong klines."""
        code, _prefix = self.internal_to_akshare(symbol)
        try:
            df = ak.stock_hk_hist(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            return self._frame_to_kline_list(symbol, df, _COL_MAP_EASTMONEY)
        except Exception:
            return []

    def _fetch_minute_klines(
        self, symbol: str, period: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Fetch minute-level klines for A-share (HK not supported).

        *period*: "1m" | "5m" | "15m" | "30m" | "60m"
        *start_date* / *end_date*: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD

        Data source fallback chain:
        1. East Money (stock_zh_a_hist_min_em) - Primary
        2. Tencent (stock_zh_a_minute) - Fallback 1
        3. Pre-market East Money (stock_zh_a_hist_pre_min_em) - Fallback 2
        """
        import logging
        logger = logging.getLogger(__name__)

        market_char = self._market_char(symbol)
        if market_char == "HK":
            logger.warning(f"HK minute data not supported: {symbol}")
            return []  # HK minute data not supported by akshare

        code, _prefix = self.internal_to_akshare(symbol)

        # Map period to akshare format
        period_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
        period_ak = period_map.get(period, "5")

        # Normalize datetime format
        start = start_date if " " in start_date else f"{start_date} 09:30:00"
        end = end_date if " " in end_date else f"{end_date} 15:00:00"

        print(f"[DEBUG] AkShare: Fetching minute klines: symbol={symbol}, code={code}, period={period_ak}, start={start}, end={end}", flush=True)

        # Try data source 1: East Money (Primary)
        try:
            print(f"[DEBUG] AkShare: Trying East Money (stock_zh_a_hist_min_em)...", flush=True)
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                start_date=start,
                end_date=end,
                period=period_ak,
                adjust="qfq",
            )

            if df is not None and not df.empty:
                print(f"[DEBUG] AkShare: East Money success - Got {len(df)} minute klines", flush=True)
                return self._process_minute_df(df, symbol)

            print(f"[DEBUG] AkShare: East Money returned empty data", flush=True)
        except Exception as e:
            print(f"[DEBUG] AkShare: East Money failed: {e}", flush=True)

        # Try data source 2: Tencent (Fallback 1)
        try:
            print(f"[DEBUG] AkShare: Trying Tencent (stock_zh_a_minute)...", flush=True)
            # Tencent uses different symbol format: sz000001 or sh600000
            prefix = self.exchange_prefix(code)
            tx_symbol = f"{prefix}{code}"

            df = ak.stock_zh_a_minute(
                symbol=tx_symbol,
                period=period_ak,
                adjust="qfq"
            )

            if df is not None and not df.empty:
                print(f"[DEBUG] AkShare: Tencent success - Got {len(df)} minute klines", flush=True)
                return self._process_minute_df(df, symbol)

            print(f"[DEBUG] AkShare: Tencent returned empty data", flush=True)
        except Exception as e:
            print(f"[DEBUG] AkShare: Tencent failed: {e}", flush=True)

        # Try data source 3: Pre-market East Money (Fallback 2)
        try:
            print(f"[DEBUG] AkShare: Trying Pre-market East Money (stock_zh_a_hist_pre_min_em)...", flush=True)
            df = ak.stock_zh_a_hist_pre_min_em(
                symbol=code,
                start_date=start,
                end_date=end,
                period=period_ak,
                adjust="qfq",
            )

            if df is not None and not df.empty:
                print(f"[DEBUG] AkShare: Pre-market East Money success - Got {len(df)} minute klines", flush=True)
                return self._process_minute_df(df, symbol)

            print(f"[DEBUG] AkShare: Pre-market East Money returned empty data", flush=True)
        except Exception as e:
            print(f"[DEBUG] AkShare: Pre-market East Money failed: {e}", flush=True)

        # All data sources failed
        print(f"[DEBUG] AkShare: All data sources failed for {symbol}", flush=True)
        return []

    def _process_minute_df(self, df: pd.DataFrame, symbol: str) -> list[dict]:
        """Process minute kline DataFrame to standard format."""
        # Minute data column mapping (supports multiple formats)
        col_map = {
            # East Money format (Chinese)
            "时间": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            # Tencent format (English)
            "day": "date",
            "time": "date",
        }

        df = _normalise_frame(df, col_map)

        required = {"date", "open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            print(f"[DEBUG] AkShare: Missing required columns. Got: {df.columns.tolist()}", flush=True)
            return []

        rows: list[dict] = []
        for _, row in df.iterrows():
            date_raw = row.get("date")
            if date_raw is None or pd.isna(date_raw):
                continue
            # Keep full datetime for minute data
            date_str = str(date_raw)
            rows.append({
                "symbol": symbol,
                "date": date_str,
                "open": self._safe_float(row.get("open")),
                "high": self._safe_float(row.get("high")),
                "low": self._safe_float(row.get("low")),
                "close": self._safe_float(row.get("close")),
                "volume": self._safe_float(row.get("volume")),
                "amount": self._safe_float(row.get("amount")),
            })
        print(f"[DEBUG] AkShare: Processed {len(rows)} minute klines for {symbol}", flush=True)
        return rows

    def _frame_to_kline_list(
        self, symbol: str, df: pd.DataFrame, col_map: dict[str, str]
    ) -> list[dict]:
        """Convert a DataFrame (with renamed columns) to the standard kline list."""
        if df is None or df.empty:
            return []

        df = _normalise_frame(df, col_map)

        required = {"date", "open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            return []

        rows: list[dict] = []
        for _, row in df.iterrows():
            date_raw = row.get("date")
            if date_raw is None or pd.isna(date_raw):
                continue
            date_str = str(date_raw)[:10]
            rows.append({
                "symbol": symbol,
                "date": self._normalise_date_display(date_str),
                "open": self._safe_float(row.get("open")),
                "high": self._safe_float(row.get("high")),
                "low": self._safe_float(row.get("low")),
                "close": self._safe_float(row.get("close")),
                "volume": self._safe_float(row.get("volume")),
                "amount": self._safe_float(row.get("amount")),
            })
        return rows

    # ------------------------------------------------------------------
    # get_realtime_quote
    # ------------------------------------------------------------------

    def get_realtime_quote(self, symbols: list[str]) -> dict:
        """Fetch real-time quotes for multiple symbols.

        Returns a dict keyed by internal symbol.  Symbols not found in the
        batch response are silently omitted.
        """
        if not symbols:
            return {}

        result: dict[str, dict] = {}
        a_symbols: set[str] = set()
        hk_symbols: set[str] = set()

        for s in symbols:
            if self._market_char(s) == "HK":
                hk_symbols.add(s)
            else:
                a_symbols.add(s)

        try:
            if a_symbols:
                result.update(self._fetch_a_spot(a_symbols))
        except ImportError:
            pass
        except Exception:
            pass

        try:
            if hk_symbols:
                result.update(self._fetch_hk_spot(hk_symbols))
        except ImportError:
            pass
        except Exception:
            pass

        return result

    def _fetch_a_spot(self, symbols: set[str]) -> dict:
        """Query A-share spot market for *symbols*."""
        df = ak.stock_zh_a_spot_em()
        return self._spot_frame_to_dict(symbols, df, "A")

    def _fetch_hk_spot(self, symbols: set[str]) -> dict:
        """Query HK spot market for *symbols*."""
        df = ak.stock_hk_spot_em()
        return self._spot_frame_to_dict(symbols, df, "HK")

    def _spot_frame_to_dict(
        self, symbols: set[str], df: pd.DataFrame, market: str
    ) -> dict:
        """Extract requested symbols from a spot-market DataFrame."""
        if df is None or df.empty:
            return {}

        # Build a lookup of raw code → index
        code_col = "代码" if "代码" in df.columns else ("code" if "code" in df.columns else None)
        if code_col is None:
            return {}

        # Map raw codes back to internal symbols
        code_to_internal: dict[str, str] = {}
        for sym in symbols:
            code, _exchange = self.internal_to_clean(sym)
            code_to_internal[code] = sym

        result: dict[str, dict] = {}
        for _, row in df.iterrows():
            raw_code = str(row.get(code_col, "")).strip()
            if raw_code not in code_to_internal:
                continue
            internal = code_to_internal[raw_code]

            result[internal] = {
                "symbol": internal,
                "name": str(row.get("名称", row.get("name", ""))),
                "price": self._safe_float(row.get("最新价", row.get("price"))) or 0.0,
                "change": self._safe_float(row.get("涨跌额", row.get("change"))) or 0.0,
                "change_pct": self._safe_float(row.get("涨跌幅", row.get("change_pct"))) or 0.0,
                "volume": self._safe_float(row.get("成交量", row.get("volume"))) or 0.0,
                "amount": self._safe_float(row.get("成交额", row.get("amount"))) or 0.0,
                "high": self._safe_float(row.get("最高", row.get("high"))),
                "low": self._safe_float(row.get("最低", row.get("low"))),
                "open": self._safe_float(row.get("今开", row.get("open"))),
                "pre_close": self._safe_float(row.get("昨收", row.get("pre_close"))),
            }
        return result

    # ------------------------------------------------------------------
    # get_index_data
    # ------------------------------------------------------------------

    def get_index_data(
        self,
        index_code: str,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Fetch market index OHLCV via akshare index daily API.

        *index_code* examples:
          - "000001" → 上证指数 (via stock_zh_index_daily_tx)
          - "399001" → 深证成指
          - "000016" → 上证50
          - "000300" → 沪深300
          - "000688" → 科创50
          - "000905" → 中证500
          - "399006" → 创业板指
        """
        try:
            code = index_code.strip()

            # Try East Money index API first
            try:
                df = ak.stock_zh_index_daily_em(symbol=code)
            except Exception:
                # Fall back to Tencent index API
                prefix = "sh" if code.startswith(("0", "6", "9")) else "sz"
                df = ak.stock_zh_index_daily_tx(symbol=f"{prefix}{code}")

            if df is None or df.empty:
                return []

            # Normalise columns
            idx_col_map = {
                "date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "amount": "amount",
            }
            df = _normalise_frame(df, idx_col_map)

            start_dt = self._normalise_date(start_date)
            end_dt = self._normalise_date(end_date)

            rows: list[dict] = []
            for _, row in df.iterrows():
                date_raw = row.get("date")
                if date_raw is None or pd.isna(date_raw):
                    continue
                date_str = str(date_raw)[:10].replace("-", "")
                if date_str < start_dt or date_str > end_dt:
                    continue
                rows.append({
                    "symbol": index_code,
                    "date": self._normalise_date_display(date_str),
                    "open": self._safe_float(row.get("open")),
                    "high": self._safe_float(row.get("high")),
                    "low": self._safe_float(row.get("low")),
                    "close": self._safe_float(row.get("close")),
                    "volume": self._safe_float(row.get("volume")),
                    "amount": self._safe_float(row.get("amount")),
                })
            return rows
        except ImportError:
            return []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # get_sector_list
    # ------------------------------------------------------------------

    def get_sector_list(self) -> list[dict]:
        """Return industry sectors and concept boards from akshare.

        Uses East Money industry board API and THS concept board API.
        """
        sectors: list[dict] = []

        # Industry boards (东方财富行业板块)
        try:
            df_ind = ak.stock_board_industry_name_em()
            if df_ind is not None and not df_ind.empty:
                name_col = "板块名称" if "板块名称" in df_ind.columns else df_ind.columns[0]
                code_col = "板块代码" if "板块代码" in df_ind.columns else (df_ind.columns[1] if len(df_ind.columns) > 1 else None)
                for _, row in df_ind.iterrows():
                    sectors.append({
                        "code": str(row.get(code_col, "")) if code_col else "",
                        "name": str(row.get(name_col, "")),
                        "type": "industry",
                    })
        except Exception:
            pass

        # Concept boards (同花顺概念板块)
        try:
            df_con = ak.stock_board_concept_name_ths()
            if df_con is not None and not df_con.empty:
                # Columns vary by version; usually has "概念名称" and "概念代码"
                name_candidates = ["概念名称", "板块名称", "name"]
                code_candidates = ["概念代码", "板块代码", "code"]
                name_col = next((c for c in name_candidates if c in df_con.columns), df_con.columns[0])
                code_col = next((c for c in code_candidates if c in df_con.columns),
                                df_con.columns[1] if len(df_con.columns) > 1 else None)
                for _, row in df_con.iterrows():
                    sectors.append({
                        "code": str(row.get(code_col, "")) if code_col else "",
                        "name": str(row.get(name_col, "")),
                        "type": "concept",
                    })
        except Exception:
            pass

        return sectors

    # ------------------------------------------------------------------
    # get_north_flow
    # ------------------------------------------------------------------

    def get_north_flow(
        self,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Return northbound capital flow (北向资金) history.

        Uses akshare's HSGT (沪港通/深港通) historical data.
        """
        try:
            start = self._normalise_date(start_date)
            end = self._normalise_date(end_date)

            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df is None or df.empty:
                return []

            rows: list[dict] = []
            for _, row in df.iterrows():
                date_raw = row.get("日期") or row.get("date")
                if date_raw is None or pd.isna(date_raw):
                    continue
                date_str = str(date_raw)[:10].replace("-", "")
                if date_str < start or date_str > end:
                    continue
                net_flow = self._safe_float(row.get("净流入", row.get("当日成交净买额", row.get("net_flow")))) or 0.0
                rows.append({
                    "date": self._normalise_date_display(date_str),
                    "net_flow": net_flow,
                })
            return rows
        except ImportError:
            return []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # get_market_news
    # ------------------------------------------------------------------

    def get_market_news(self, symbol: str = "", limit: int = 20) -> list[dict]:
        """Return recent market news for *symbol*.

        If *symbol* is empty, returns broad-market East Money news.
        When *symbol* is provided, fetches stock-specific news announcements.
        Also augments with disclosure reports for A-share stocks.
        """
        news: list[dict] = []

        try:
            if symbol:
                code, _prefix = self.internal_to_akshare(symbol)
                try:
                    df = ak.stock_news_em(symbol=code)
                    if df is not None and not df.empty:
                        news.extend(self._news_frame_to_list(df))
                except Exception:
                    pass

                # Also fetch disclosure reports for A-share
                if self._market_char(symbol) == "A":
                    try:
                        df_disc = ak.stock_zh_a_disclosure_report_cninfo(
                            symbol=code,
                            start_date=(datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
                            end_date=datetime.now().strftime("%Y-%m-%d"),
                        )
                        if df_disc is not None and not df_disc.empty:
                            title_col = "公告标题" if "公告标题" in df_disc.columns else df_disc.columns[0]
                            time_col = "公告日期" if "公告日期" in df_disc.columns else (df_disc.columns[1] if len(df_disc.columns) > 1 else None)
                            for _, row in df_disc.iterrows():
                                news.append({
                                    "title": str(row.get(title_col, "")),
                                    "time": str(row.get(time_col, "")) if time_col else "",
                                    "source": "cninfo",
                                    "url": "",
                                })
                    except Exception:
                        pass
            else:
                # Broad market news — use East Money stock news with a broad symbol
                try:
                    df = ak.stock_news_em(symbol="")
                    if df is not None and not df.empty:
                        news.extend(self._news_frame_to_list(df))
                except Exception:
                    # Fall back: try without symbol parameter
                    try:
                        df = ak.stock_news_em()
                        if df is not None and not df.empty:
                            news.extend(self._news_frame_to_list(df))
                    except Exception:
                        pass
        except ImportError:
            pass
        except Exception:
            pass

        # Deduplicate by title and respect limit
        seen: set[str] = set()
        unique: list[dict] = []
        for n in news:
            title = n.get("title", "")
            if title and title not in seen:
                seen.add(title)
                unique.append(n)
        return unique[:limit]

    def _news_frame_to_list(self, df: pd.DataFrame) -> list[dict]:
        """Convert a news DataFrame to the standard list of dicts."""
        items: list[dict] = []
        title_candidates = ["标题", "title", "新闻标题", "公告标题"]
        time_candidates = ["发布时间", "time", "日期", "datetime"]
        source_candidates = ["来源", "source", "source_name"]

        title_col = next((c for c in title_candidates if c in df.columns), df.columns[0] if len(df.columns) > 0 else None)
        time_col = next((c for c in time_candidates if c in df.columns), None)
        source_col = next((c for c in source_candidates if c in df.columns), None)

        for _, row in df.iterrows():
            items.append({
                "title": str(row.get(title_col, "")) if title_col else "",
                "time": str(row.get(time_col, "")) if time_col else "",
                "source": str(row.get(source_col, "")) if source_col else "",
                "url": str(row.get("url", row.get("链接", ""))),
            })
        return items

    # ------------------------------------------------------------------
    # get_financial_data
    # ------------------------------------------------------------------

    def get_financial_data(self, symbol: str) -> dict:
        """Return financial indicators for *symbol*.

        Uses akshare's financial abstract API (同花顺财务概况) for A-shares
        and the HK financial report API for Hong Kong stocks.
        """
        try:
            code, _prefix = self.internal_to_akshare(symbol)
            market_char = self._market_char(symbol)

            result: dict[str, Any] = {
                "symbol": symbol,
                "report_date": None,
                "revenue": None,
                "net_profit": None,
                "roe": None,
                "eps": None,
                "total_assets": None,
                "total_liabilities": None,
                "pe": None,
                "pb": None,
            }

            if market_char == "HK":
                self._fill_hk_financial(result, code)
            else:
                self._fill_a_financial(result, code)

            return result
        except ImportError:
            return {"symbol": symbol, "error": "akshare not installed"}
        except Exception:
            return {"symbol": symbol}

    def _fill_a_financial(self, result: dict[str, Any], code: str) -> None:
        """Fill A-share financial data via 同花顺财务概况."""
        try:
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
            if df is None or df.empty:
                return

            # Use the most recent row
            latest = df.iloc[-1]
            result["report_date"] = self._extract_date_cell(latest, ["报告期", "日期", "date"])

            key_map: dict[str, list[str]] = {
                "revenue": ["营业总收入", "营业总收入(元)"],
                "net_profit": ["净利润", "净利润(元)", "归属母公司净利润"],
                "roe": ["净资产收益率", "净资产收益率(%)", "ROE"],
                "eps": ["每股收益", "基本每股收益", "EPS"],
                "total_assets": ["资产总计", "总资产"],
                "total_liabilities": ["负债合计", "总负债"],
                "pe": ["市盈率", "PE"],
                "pb": ["市净率", "PB"],
            }
            for target_key, candidate_cols in key_map.items():
                for col in candidate_cols:
                    if col in df.columns:
                        result[target_key] = self._safe_float(latest.get(col))
                        break
        except Exception:
            pass

        # Augment with individual info (PE/PB often here)
        try:
            info_df = ak.stock_individual_info_em(symbol=code)
            if info_df is not None and not info_df.empty:
                info_map = {
                    "市盈率-动态": "pe",
                }
                for _, row in info_df.iterrows():
                    item = str(row.get("item", ""))
                    if item in info_map:
                        key = info_map[item]
                        if result.get(key) is None:
                            result[key] = self._safe_float(row.get("value"))
        except Exception:
            pass

    def _fill_hk_financial(self, result: dict[str, Any], code: str) -> None:
        """Fill Hong Kong financial data."""
        # Try income statement
        try:
            df_income = ak.stock_financial_hk_report_em(
                stock=code, symbol="利润表", indicator="年度"
            )
            if df_income is not None and not df_income.empty:
                latest = df_income.iloc[-1]
                result["report_date"] = self._extract_date_cell(latest, ["截止日期", "报告期", "date"])
                result["revenue"] = self._safe_float(
                    latest.get("营业收入", latest.get("REVENUE")))
                result["net_profit"] = self._safe_float(
                    latest.get("净利润", latest.get("NET_PROFIT")))
        except Exception:
            pass

        # Try balance sheet
        try:
            df_balance = ak.stock_financial_hk_report_em(
                stock=code, symbol="资产负债表", indicator="年度"
            )
            if df_balance is not None and not df_balance.empty:
                latest = df_balance.iloc[-1]
                result["total_assets"] = result["total_assets"] or self._safe_float(
                    latest.get("总资产", latest.get("TOTAL_ASSETS")))
                result["total_liabilities"] = result["total_liabilities"] or self._safe_float(
                    latest.get("总负债", latest.get("TOTAL_LIABILITIES")))
        except Exception:
            pass

    @staticmethod
    def _extract_date_cell(row: pd.Series, candidate_cols: list[str]) -> str | None:
        """Pull a date string from one of the candidate columns."""
        for col in candidate_cols:
            if col in row.index:
                val = row.get(col)
                if val is not None and not pd.isna(val):
                    s = str(val)[:10]
                    return s
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _market_char(symbol: str) -> str:
        """Return 'A' or 'HK' for a given internal symbol."""
        _, exchange = BaseMarketAdapter.internal_to_clean(symbol)
        return "HK" if exchange == "HK" else "A"

    @staticmethod
    def _map_period(period: str) -> str:
        """Map user-friendly period to akshare period string."""
        mapping = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "日线": "daily",
            "周线": "weekly",
            "月线": "monthly",
        }
        return mapping.get(period, "daily")
