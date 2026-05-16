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

    ak = _AkShareUnavailable()

try:
    from pipeline.db import Database
except ImportError:  # pragma: no cover - allows script-relative imports
    from db import Database


class StockListFetcher:
    """Fetch, normalize, and persist stock lists from AkShare."""

    _MAX_RETRIES = 3
    _BASE_BACKOFF_SECONDS = 1
    _PROGRESS_INTERVAL = 100

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for persistence."""
        self.db = db

    def run(self, market: str = "A", force: bool = False) -> None:
        """Fetch the requested market's stock list and upsert it into SQLite."""
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
        except Exception as exc:
            raise RuntimeError(f"{normalized_market} 股列表写入数据库失败: {exc}") from exc

        print(f"[StockList] 完成，更新 {count} 只股票")

        # Phase 2: 计算技术指标
        self._update_technical_indicators(normalized_market)

    def _fetch_a_stocks(self) -> List[Dict[str, Any]]:
        """Fetch and normalize the full A-share spot list from AkShare.

        Uses the Sina source (stock_zh_a_spot) because East Money's push2 API
        is unreachable on this network. The Sina source lacks industry, PE, PB,
        and market-cap columns — those fields remain NULL and can be backfilled
        later via dedicated fetchers.
        """
        return self._fetch_with_retry(
            fetch_fn=ak.stock_zh_a_spot,
            market_label="A股",
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
        return {
            "symbol": self._require_text(row["代码"], "代码"),
            "name": self._require_text(row["名称"], "名称"),
            "market": "A",
            "market_cap": self._to_float(row.get("总市值"), scale=1e8),
            "pe": self._to_float(row.get("市盈率-动态")),
            "pb": self._to_float(row.get("市净率")),
            "industry": self._to_optional_text(row.get("所属行业")),
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
            "pe": self._to_float(row.get("市盈率")),
            "pb": self._to_float(row.get("市净率")),
            "industry": self._to_optional_text(row.get("所属行业")),
        }

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
        if value is None or pd.isna(value):
            return None

        if isinstance(value, str):
            normalized_value = value.replace(",", "").strip()
            if not normalized_value:
                return None
            number = float(normalized_value)
        else:
            number = float(value)

        return number / scale

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
