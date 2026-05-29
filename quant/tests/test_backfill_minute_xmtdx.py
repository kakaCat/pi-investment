"""Tests for the xmtdx minute backfill script helpers."""

from __future__ import annotations

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.backfill_minute_xmtdx import _symbols_from_args


def test_symbols_from_db_dedupes_suffix_variants() -> None:
    db = Mock()
    db.get_all_symbols.return_value = [
        "000001",
        "000002.SZ",
        "000002",
        "600519.SH",
        "600519",
    ]

    symbols = _symbols_from_args(db, None, "A")

    assert symbols == ["000001", "000002", "600519"]


def test_symbols_from_args_preserves_explicit_input() -> None:
    db = Mock()

    symbols = _symbols_from_args(db, "600519.SH,000417", "A")

    assert symbols == ["600519.SH", "000417"]
    db.get_all_symbols.assert_not_called()
