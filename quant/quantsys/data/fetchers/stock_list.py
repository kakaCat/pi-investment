"""Stock universe fetcher for A-share and Hong Kong equities."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

import pandas as pd

try:
    import akshare as ak
except ImportError:
    class _AkShareUnavailable:
        """Fallback stub that preserves patchable attributes in tests."""

        @staticmethod
        def stock_zh_a_spot_em() -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch A-share stock lists")

        @staticmethod
        def stock_hk_spot_em() -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch Hong Kong stock lists")

        @staticmethod
        def stock_financial_abstract_ths(symbol: str, indicator: str = "按报告期") -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch stock fundamentals")

        @staticmethod
        def stock_financial_analysis_indicator(symbol: str, start_year: str | None = None) -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch stock fundamentals")

        @staticmethod
        def stock_board_industry_name_em() -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch stock industries")

        @staticmethod
        def stock_board_industry_cons_em(symbol: str) -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch stock industries")

    ak = _AkShareUnavailable()

from quantsys.data.db import Database


class StockListFetcher:
    """Fetch, normalize, and persist stock lists from AkShare."""

    _MAX_RETRIES = 3
    _BASE_BACKOFF_SECONDS = 1
    _PROGRESS_INTERVAL = 100
    _SINA_FETCH_TIMEOUT = 60  # Sina source can take ~20-30s for full A-list
    _FUNDAMENTAL_LOG_LIMIT = 20

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for persistence."""
        self.db = db
        self._fundamental_failures = 0

    def run(self, market: str = "A", force: bool = False, with_fundamentals: bool = False) -> None:
        """Fetch the requested market's stock list and upsert it into PostgreSQL."""
        normalized_market = market.strip().upper()
        print(f"[StockList] 开始更新 {normalized_market} 股列表...")
        if force:
            print("[StockList] force=True，执行全量刷新。")

        if normalized_market == "A":
            stocks = self._fetch_a_stocks()
        elif normalized_market == "HK":
            stocks = self._fetch_hk_stocks()
        else:
            raise ValueError(f"不支持的市场: {market}")

        try:
            count = self.db.upsert_stocks(stocks)
            if with_fundamentals and normalized_market == "A":
                self.backfill_fundamentals([stock["symbol"] for stock in stocks])
        except Exception as exc:
            raise RuntimeError(f"{normalized_market} 股列表写入数据库失败: {exc}") from exc

        print(f"[StockList] 完成，更新 {count} 只股票")

        # Phase 2: 计算技术指标
        self._update_technical_indicators(normalized_market)

    def _fetch_a_stocks(self) -> List[Dict[str, Any]]:
        """Fetch and normalize the full A-share spot list.

        Priority:
        1. East Money via AkShare (stock_zh_a_spot_em) — rich columns (PE, PB, industry)
        2. Sina via AkShare (stock_zh_a_spot) — basic code + name only
        """
        return self._fetch_a_stocks_em() or self._fetch_a_stocks_sina()

    def _fetch_a_stocks_em(self) -> List[Dict[str, Any]] | None:
        """Try East Money source first (rich data). Returns None on failure."""
        try:
            return self._fetch_with_retry(
                fetch_fn=ak.stock_zh_a_spot_em,
                market_label="A股(东财)",
                mapper=self._map_a_stock_row,
            )
        except RuntimeError as exc:
            print(f"[StockList] 东财接口不可用，降级到新浪源: {exc}")
            return None

    def _fetch_a_stocks_sina(self) -> List[Dict[str, Any]]:
        """Fallback: fetch the A-share list from Sina (stock_zh_a_spot).

        The Sina source lacks industry, PE, PB, and market-cap columns —
        those fields remain NULL and can be backfilled later via dedicated
        fetchers.  It is slower (~20 s) because AkShare paginates requests.
        """
        return self._fetch_with_retry(
            fetch_fn=ak.stock_zh_a_spot,
            market_label="A股(新浪)",
            mapper=self._map_a_stock_row_sina,
        )

    def _fetch_hk_stocks(self) -> List[Dict[str, Any]]:
        """Fetch and normalize the full Hong Kong spot list from AkShare."""
        return self._fetch_with_retry(
            fetch_fn=ak.stock_hk_spot_em,
            market_label="港股",
            mapper=self._map_hk_stock_row,
        )

    def _fetch_with_retry(
        self,
        fetch_fn: Callable[[], pd.DataFrame],
        market_label: str,
        mapper: Callable[[pd.Series], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Execute a market fetch with retry, exponential backoff, and mapping."""
        last_error: Exception | None = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                frame = fetch_fn()
                if frame.empty:
                    raise RuntimeError(f"{market_label}接口返回空数据")
                return self._convert_frame_to_stocks(frame, market_label, mapper)
            except Exception as exc:
                last_error = exc
                if attempt >= self._MAX_RETRIES:
                    break

                delay_seconds = self._BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(
                    f"[StockList] {market_label}拉取失败，第 {attempt}/{self._MAX_RETRIES} 次尝试: "
                    f"{exc}，{delay_seconds} 秒后重试"
                )
                time.sleep(delay_seconds)

        raise RuntimeError(
            f"{market_label}列表拉取失败，已重试 {self._MAX_RETRIES} 次: {last_error}"
        ) from last_error

    def _convert_frame_to_stocks(
        self,
        frame: pd.DataFrame,
        market_label: str,
        mapper: Callable[[pd.Series], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Map AkShare rows into database-ready stock dictionaries."""
        stocks: List[Dict[str, Any]] = []
        total = len(frame.index)

        for index, (_, row) in enumerate(frame.iterrows(), start=1):
            try:
                stocks.append(mapper(row))
            except KeyError as exc:
                missing_field = exc.args[0]
                raise RuntimeError(f"{market_label}数据缺少必需字段: {missing_field}") from exc
            except Exception as exc:
                raise RuntimeError(f"{market_label}第 {index} 条记录解析失败: {exc}") from exc

            if index % self._PROGRESS_INTERVAL == 0:
                print(f"[StockList] {market_label}进度: {index}/{total}")

        return stocks

    def _map_a_stock_row(self, row: pd.Series) -> Dict[str, Any]:
        """Normalize one A-share AkShare row (East Money) into a database payload."""
        industry = self._to_optional_text(row.get("所属行业"))
        total_mv = self._to_float(row.get("总市值"), scale=1e8)
        return {
            "symbol": self._require_text(row["代码"], "代码"),
            "name": self._require_text(row["名称"], "名称"),
            "market": "A",
            "market_cap": total_mv,
            "total_mv": total_mv,
            "circulating_mv": self._to_float(row.get("流通市值"), scale=1e8),
            "pe": self._to_float(row.get("市盈率-动态")),
            "pb": self._to_float(row.get("市净率")),
            "industry": industry,
            "sector": industry,
        }

    def _map_a_stock_row_sina(self, row: pd.Series) -> Dict[str, Any]:
        """Normalize one A-share AkShare row (Sina) into a database payload.

        Sina's stock_zh_a_spot() returns spot prices only — no fundamentals.
        Fields like PE, PB, industry, market_cap are left as None.
        """
        code = self._require_text(row["代码"], "代码")
        # Sina includes exchange prefix like sh600519, sz000001 — strip to 6-digit
        if len(code) > 6 and code.lower().startswith(("sh", "sz", "bj")):
            code = code[2:]
        return {
            "symbol": code,
            "name": self._require_text(row["名称"], "名称"),
            "market": "A",
            "market_cap": None,
            "pe": None,
            "pb": None,
            "industry": None,
        }

    def _map_hk_stock_row(self, row: pd.Series) -> Dict[str, Any]:
        """Normalize one Hong Kong AkShare row into a database payload."""
        return {
            "symbol": self._require_text(row["代码"], "代码"),
            "name": self._require_text(row["名称"], "名称"),
            "market": "HK",
            "market_cap": self._to_float(row.get("总市值"), scale=1e8),
            "total_mv": self._to_float(row.get("总市值"), scale=1e8),
            "circulating_mv": self._to_float(row.get("流通市值"), scale=1e8),
            "pe": self._to_float(row.get("市盈率")),
            "pb": self._to_float(row.get("市净率")),
            "industry": self._to_optional_text(row.get("所属行业")),
        }

    def backfill_fundamentals(self, symbols: List[str]) -> int:
        """Fetch latest A-share financial indicators and persist them to stocks."""
        fundamentals = []
        total = len(symbols)
        updated = 0

        for index, symbol in enumerate(symbols, start=1):
            metrics = self._fetch_stock_fundamentals(symbol)
            if metrics:
                fundamentals.append(metrics)

            if index % self._PROGRESS_INTERVAL == 0:
                if fundamentals:
                    updated += self.db.upsert_stocks(fundamentals)
                    fundamentals = []
                print(f"[StockList] 基本面回填进度: {index}/{total}")

        if not fundamentals:
            return updated
        return updated + self.db.upsert_stocks(fundamentals)

    def backfill_industries(self) -> int:
        """Fetch East Money industry boards and persist industry fields to stocks."""
        board_frame = ak.stock_board_industry_name_em()
        if board_frame is None or board_frame.empty:
            return 0

        industries: List[Dict[str, Any]] = []
        total = len(board_frame.index)
        for index, (_, board_row) in enumerate(board_frame.iterrows(), start=1):
            industry = self._to_optional_text(
                board_row.get("板块名称", board_row.get("名称", board_row.get("行业名称")))
            )
            if not industry:
                continue

            try:
                cons_frame = ak.stock_board_industry_cons_em(symbol=industry)
            except Exception as exc:
                print(f"[StockList] 行业成分拉取失败: {industry} - {exc}")
                continue

            for _, stock_row in cons_frame.iterrows():
                symbol = self._to_optional_text(stock_row.get("代码", stock_row.get("股票代码")))
                if not symbol:
                    continue

                name = self._to_optional_text(stock_row.get("名称", stock_row.get("股票名称"))) or symbol
                industries.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "market": "A",
                        "industry": industry,
                        "sector": industry,
                    }
                )

            if index % 10 == 0:
                print(f"[StockList] 行业回填进度: {index}/{total}")

        if not industries:
            return 0
        return self.db.upsert_stocks(industries)

    def _fetch_stock_fundamentals(self, symbol: str) -> Dict[str, Any] | None:
        """Fetch latest financial indicator metrics for one A-share symbol."""
        try:
            frame = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
        except Exception:
            try:
                frame = ak.stock_financial_analysis_indicator(
                symbol=symbol,
                start_year=str(pd.Timestamp.now().year - 1),
                )
            except Exception as exc:
                self._fundamental_failures += 1
                if self._fundamental_failures <= self._FUNDAMENTAL_LOG_LIMIT:
                    print(f"[StockList] 基本面拉取失败: {symbol} - {exc}")
                elif self._fundamental_failures == self._FUNDAMENTAL_LOG_LIMIT + 1:
                    print("[StockList] 基本面失败过多，后续仅显示进度")
                return None

        if frame is None or frame.empty:
            return None

        sorted_frame = frame.copy()
        date_column = "报告期" if "报告期" in sorted_frame.columns else "日期"
        if date_column in sorted_frame.columns:
            sorted_frame["_date_sort"] = pd.to_datetime(sorted_frame[date_column], errors="coerce")
            sorted_frame = sorted_frame.sort_values("_date_sort")

        row = sorted_frame.iloc[-1]
        metrics = {
            "symbol": symbol,
            "roe": self._to_percent_float(row.get("净资产收益率", row.get("净资产收益率(%)"))),
            "gross_margin": self._to_percent_float(row.get("销售毛利率", row.get("销售毛利率(%)"))),
            "debt_ratio": self._to_percent_float(row.get("资产负债率", row.get("资产负债率(%)"))),
            "net_profit_growth": self._to_percent_float(row.get("净利润同比增长率", row.get("净利润增长率(%)"))),
        }
        return metrics

    def _require_text(self, value: Any, field_name: str) -> str:
        """Return a non-empty string field or raise a readable error."""
        text = self._to_optional_text(value)
        if text is None:
            raise ValueError(f"{field_name} 为空")
        return text

    def _to_optional_text(self, value: Any) -> str | None:
        """Convert a scalar value into a stripped string when present."""
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    def _to_float(self, value: Any, scale: float = 1.0) -> float | None:
        """Convert numeric-like values into floats, handling missing values."""
        if value is None or isinstance(value, bool) or pd.isna(value):
            return None

        if isinstance(value, str):
            normalized_value = value.replace(",", "").strip()
            if not normalized_value:
                return None
            number = float(normalized_value)
        else:
            number = float(value)

        return number / scale

    def _to_percent_float(self, value: Any) -> float | None:
        """Convert AkShare percentage strings like '19.03%' into floats."""
        if isinstance(value, str):
            value = value.replace("%", "")
        return self._to_float(value)

    def _update_technical_indicators(self, market: str) -> None:
        """Calculate and persist technical indicators for a capped symbol batch."""
        try:
            from .technicals import TechnicalCalculator
        except ImportError:  # pragma: no cover - allows script-relative imports
            from technicals import TechnicalCalculator

        symbols = self.db.get_all_symbols(market)[:100]
        print("[StockList] 计算技术指标...")

        if not symbols:
            return

        calculator = TechnicalCalculator(self.db)
        total = len(symbols)

        for index, symbol in enumerate(symbols, start=1):
            try:
                calculator.calculate_and_update(symbol)
            except Exception as exc:
                print(f"[StockList] 技术指标更新失败: {symbol} - {exc}")

            if index % 10 == 0:
                print(f"  进度: {index}/{total}")
