"""Tests for the AkShare bridge compatibility fallbacks."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "akshare_bridge.py"
SPEC = importlib.util.spec_from_file_location("akshare_bridge", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load AkShare bridge module from {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeAkshare:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls = []

    def stock_financial_abstract_ths(self, symbol: str, indicator: str) -> pd.DataFrame:
        self.calls.append((symbol, indicator))
        return self.frame


class AkshareBridgeTests(unittest.TestCase):
    def test_get_financial_indicators_uses_current_ths_interface(self) -> None:
        frame = pd.DataFrame(
            [
                {"report_date": "2024-12-31", "metric_name": "index_full_diluted_roe", "value": "12.5"},
                {"report_date": "2024-12-31", "metric_name": "sale_gross_margin", "value": "45.6"},
                {"report_date": "2024-12-31", "metric_name": "sale_net_interest_ratio", "value": "18.9"},
                {"report_date": "2024-12-31", "metric_name": "equity_ratio", "value": "0.32"},
                {"report_date": "2024-12-31", "metric_name": "current_ratio", "value": "1.8"},
            ]
        )
        fake_ak = FakeAkshare(frame)

        with patch.dict(sys.modules, {"akshare": fake_ak}):
            result = MODULE.get_financial_indicators("600519")

        self.assertEqual(fake_ak.calls, [("600519", "按报告期")])
        self.assertEqual(result["quarters"][0]["roe"], 12.5)
        self.assertEqual(result["quarters"][0]["gross_margin"], 45.6)
        self.assertEqual(result["quarters"][0]["net_margin"], 18.9)
        self.assertEqual(result["quarters"][0]["debt_ratio"], 32.0)
        self.assertEqual(result["quarters"][0]["current_ratio"], 1.8)

    def test_friendly_fallback_functions_return_expected_messages(self) -> None:
        self.assertEqual(
            MODULE.get_top_fund_stocks(),
            {"error": "akshare 已移除 fund_stock_rank_em 接口，该功能暂不可用"},
        )
        self.assertEqual(
            MODULE.get_sector_list(),
            {
                "error": "板块数据接口不稳定，建议使用 get_market_overview 查看市场概况",
                "count": 0,
                "data": [],
            },
        )
        self.assertEqual(
            MODULE.screen_stocks_by_sector("白酒"),
            {
                "error": "板块筛选接口字段变更，功能暂不可用。建议: 使用 get_stock_info 查询个股信息",
                "sector": "白酒",
            },
        )
        self.assertEqual(
            MODULE.get_concept_stocks("人工智能"),
            {"error": "概念股接口不稳定，功能暂不可用", "concept": "人工智能"},
        )

    def test_top_fund_stocks_stays_registered(self) -> None:
        self.assertIs(MODULE.FUNCTIONS["get_top_fund_stocks"], MODULE.get_top_fund_stocks)


if __name__ == "__main__":
    unittest.main()
