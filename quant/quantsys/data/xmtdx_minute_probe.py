"""Probe adapter for free TDX-compatible 1-minute A-share history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import pandas as pd


@dataclass
class XmtDxMinuteProbe:
    """Fetch and normalize 1-minute bars from an xmtdx-compatible reader."""

    reader: Any | None = None

    def fetch_range(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        *,
        max_pages: int = 80,
        page_size: int = 800,
    ) -> list[dict[str, Any]]:
        """Fetch 1-minute rows in a date range without writing to the database."""
        reader = self.reader or self._create_reader()
        market, code = self.to_tdx_market_code(symbol)
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        rows: list[dict[str, Any]] = []

        for page in range(max_pages):
            offset = page * page_size
            frame = self._fetch_page(reader, market, code, offset, page_size)
            if frame is None or self._is_empty(frame):
                continue

            for row in self._iter_rows(frame):
                normalized = self._normalize_row(symbol, row)
                if normalized is None:
                    continue
                row_date = pd.to_datetime(normalized["trade_datetime"]).date()
                if start <= row_date <= end:
                    rows.append(normalized)

        rows.sort(key=lambda row: row["trade_datetime"])
        deduped = {row["trade_datetime"]: row for row in rows}
        return list(deduped.values())

    def backfill_range(
        self,
        db: Any,
        symbol: str,
        start_date: str,
        end_date: str,
        *,
        max_pages: int = 80,
        page_size: int = 800,
    ) -> int:
        """Fetch 1-minute rows in a date range and upsert them into PostgreSQL."""
        rows = self.fetch_range(
            symbol,
            start_date,
            end_date,
            max_pages=max_pages,
            page_size=page_size,
        )
        if not rows:
            return 0
        return int(db.upsert_minute_klines(rows))

    @staticmethod
    def to_tdx_symbol(symbol: str) -> str:
        """Convert local symbols to TDX format, e.g. 600519.SH -> sh600519."""
        code = symbol.strip().split(".")[0].lower()
        if code.startswith(("6", "9")):
            return f"sh{code}"
        if code.startswith(("4", "8", "43", "83", "87", "92")):
            return f"bj{code}"
        return f"sz{code}"

    @staticmethod
    def to_tdx_market_code(symbol: str) -> tuple[str, str]:
        """Convert local symbols to a TDX market name and bare code."""
        code = symbol.strip().split(".")[0]
        if code.startswith(("6", "9")):
            return "SH", code
        if code.startswith(("4", "8", "43", "83", "87", "92")):
            return "BJ", code
        return "SZ", code

    @staticmethod
    def _fetch_page(reader: Any, market: str, code: str, offset: int, count: int) -> Any:
        if hasattr(reader, "minute"):
            return reader.minute(f"{market.lower()}{code}", "1m", offset, count)

        from xmtdx import KlineCategory, Market

        return reader.get_security_bars(
            getattr(Market, market),
            code,
            KlineCategory.MIN_1,
            offset,
            count,
        )

    @staticmethod
    def _is_empty(frame: Any) -> bool:
        if frame is None:
            return True
        if hasattr(frame, "empty"):
            return bool(frame.empty)
        return len(frame) == 0

    @staticmethod
    def _iter_rows(frame: pd.DataFrame) -> Iterable[dict[str, Any]]:
        if isinstance(frame, list):
            for row in frame:
                yield {
                    "datetime": getattr(row, "datetime_str", None),
                    "open": getattr(row, "open", None),
                    "high": getattr(row, "high", None),
                    "low": getattr(row, "low", None),
                    "close": getattr(row, "close", None),
                    "vol": getattr(row, "vol", None),
                    "amount": getattr(row, "amount", None),
                }
            return

        for _, row in frame.iterrows():
            yield dict(row)

    @staticmethod
    def _normalize_row(symbol: str, row: dict[str, Any]) -> dict[str, Any] | None:
        timestamp = row.get("datetime") or row.get("date") or row.get("day") or row.get("时间")
        if timestamp is None:
            return None

        try:
            trade_datetime = pd.to_datetime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

        return {
            "symbol": symbol,
            "trade_datetime": trade_datetime,
            "open": XmtDxMinuteProbe._to_float(row.get("open") or row.get("开盘")),
            "high": XmtDxMinuteProbe._to_float(row.get("high") or row.get("最高")),
            "low": XmtDxMinuteProbe._to_float(row.get("low") or row.get("最低")),
            "close": XmtDxMinuteProbe._to_float(row.get("close") or row.get("收盘")),
            "volume": XmtDxMinuteProbe._to_float(row.get("volume") or row.get("vol") or row.get("成交量")),
            "amount": XmtDxMinuteProbe._to_float(row.get("amount") or row.get("成交额")),
        }

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _create_reader() -> Any:
        try:
            from xmtdx import TdxClient
        except ImportError as exc:
            raise RuntimeError("xmtdx is required for this probe. Install with: pip install xmtdx") from exc

        client = TdxClient.from_best_host(timeout=10.0, ping_timeout=2.0)
        client.connect()
        return client
