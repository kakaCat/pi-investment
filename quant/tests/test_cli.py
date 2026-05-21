"""Tests for the agent-friendly QuantSys CLI."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from quantsys.cli import main as cli_main


class QuantCliTests(unittest.TestCase):
    """Verify command discovery, JSON output, and script command adaptation."""

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli_main.main(argv)

        return exit_code, stdout.getvalue(), stderr.getvalue()

    def parse_json_stdout(self, stdout: str) -> dict:
        return json.loads(stdout)

    def test_tools_list_returns_machine_readable_commands(self) -> None:
        exit_code, stdout, stderr = self.run_cli(["tools", "+list", "--json"])

        payload = self.parse_json_stdout(stdout)
        command_names = {item["name"] for item in payload["data"]["commands"]}

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertTrue(payload["ok"])
        self.assertIn("data.status", command_names)
        self.assertIn("backtest.run", command_names)
        self.assertIn("signal.generate", command_names)
        self.assertIn("stock.score", command_names)
        self.assertIn("stock.screen", command_names)
        self.assertIn("performance.analyze", command_names)
        self.assertIn("signal.arbitrate", command_names)
        self.assertIn("factor.analyze", command_names)
        self.assertIn("sector.aggregate", command_names)
        self.assertIn("benchmark.compare", command_names)
        self.assertIn("portfolio.optimize", command_names)
        self.assertIn("strategy.optimize", command_names)
        self.assertIn("watch.price_alert", command_names)
        self.assertIn("stress.test", command_names)
        self.assertIn("trade.verify", command_names)
        self.assertIn("portfolio.correlation", command_names)
        self.assertIn("factor.decay", command_names)
        self.assertIn("stock.quote", command_names)
        self.assertIn("stock.info", command_names)
        self.assertIn("stock.history", command_names)
        self.assertIn("stock.news", command_names)
        self.assertIn("stock.announcements", command_names)
        self.assertIn("stock.batch_quotes", command_names)
        self.assertIn("market.overview", command_names)
        self.assertIn("market.sectors", command_names)
        self.assertIn("market.concept_stocks", command_names)
        self.assertIn("market.concepts", command_names)
        self.assertIn("market.macro", command_names)
        self.assertIn("market.north_flow", command_names)
        self.assertIn("market.sector_flow", command_names)
        self.assertIn("market.margin", command_names)
        self.assertIn("market.news", command_names)
        self.assertIn("market.hot_stocks", command_names)
        self.assertIn("market.index_history", command_names)
        self.assertIn("analysis.technical", command_names)
        self.assertIn("analysis.price_action", command_names)
        self.assertIn("analysis.candlestick", command_names)
        self.assertIn("analysis.buy_range", command_names)
        self.assertIn("analysis.valuation", command_names)
        self.assertIn("analysis.pe_percentile", command_names)
        self.assertIn("analysis.quality", command_names)
        self.assertIn("analysis.exit_plan", command_names)
        self.assertIn("analysis.peers", command_names)
        self.assertIn("screening.sector", command_names)
        self.assertIn("screening.quality", command_names)
        self.assertIn("risk.trade_check", command_names)
        self.assertIn("risk.position_size", command_names)
        self.assertIn("risk.stop_loss", command_names)
        self.assertIn("hk.market_overview", command_names)
        self.assertIn("hk.south_flow", command_names)
        self.assertIn("hk.technical", command_names)
        self.assertIn("hk.hot_rank", command_names)
        self.assertIn("sentiment.stock_fund_flow", command_names)
        self.assertIn("sentiment.lhb", command_names)
        self.assertIn("sentiment.insider_trades", command_names)
        self.assertIn("sentiment.fund_holdings", command_names)
        self.assertIn("sentiment.top_fund_stocks", command_names)
        self.assertIn("sentiment.top_holders", command_names)
        self.assertIn("sentiment.holder_changes", command_names)
        self.assertIn("sentiment.margin_data", command_names)
        self.assertIn("financial.indicators", command_names)
        self.assertIn("financial.statements", command_names)
        self.assertIn("financial.hk_financials", command_names)
        self.assertIn("financial.hk_analysis", command_names)

    def test_tools_describe_returns_command_schema(self) -> None:
        exit_code, stdout, _stderr = self.run_cli(
            ["tools", "+describe", "backtest.run", "--json"]
        )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["name"], "backtest.run")
        self.assertIn("symbol", payload["data"]["params"])
        self.assertIn("quant backtest +run", payload["data"]["examples"][0])

    def test_tools_describe_returns_stock_screen_schema(self) -> None:
        exit_code, stdout, _stderr = self.run_cli(
            ["tools", "+describe", "stock.screen", "--json"]
        )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["name"], "stock.screen")
        self.assertIn("pe_max", payload["data"]["params"])
        self.assertIn("roe_min", payload["data"]["params"])
        self.assertIn("quant stock +screen", payload["data"]["examples"][0])

    def test_tools_describe_returns_signal_arbitrate_schema(self) -> None:
        exit_code, stdout, _stderr = self.run_cli(
            ["tools", "+describe", "signal.arbitrate", "--json"]
        )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["name"], "signal.arbitrate")
        self.assertIn("date", payload["data"]["params"])
        self.assertIn("signals_json", payload["data"]["params"])
        self.assertIn("quant signal +arbitrate", payload["data"]["examples"][0])

    def test_tools_describe_returns_p2_command_schemas(self) -> None:
        expected = {
            "factor.analyze": ("top_n", "quant factor +analyze"),
            "sector.aggregate": ("sector_field", "quant sector +aggregate"),
            "benchmark.compare": ("strategy_return", "quant benchmark +compare"),
            "portfolio.optimize": ("method", "quant portfolio +optimize"),
            "strategy.optimize": ("strategy", "quant strategy +optimize"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_p3_command_schemas(self) -> None:
        expected = {
            "watch.price_alert": ("price", "quant watch +price-alert"),
            "stress.test": ("shock_pct", "quant stress +test"),
            "trade.verify": ("trades_json", "quant trade +verify"),
            "portfolio.correlation": ("prices_json", "quant portfolio +correlation"),
            "factor.decay": ("factor", "quant factor +decay"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_analysis_command_schemas(self) -> None:
        expected = {
            "analysis.technical": ("symbol", "quant analysis +technical"),
            "analysis.price_action": ("period", "quant analysis +price-action"),
            "analysis.candlestick": ("symbol", "quant analysis +candlestick"),
            "analysis.buy_range": ("current_price", "quant analysis +buy-range"),
            "analysis.valuation": ("symbol", "quant analysis +valuation"),
            "analysis.pe_percentile": ("years", "quant analysis +pe-percentile"),
            "analysis.quality": ("symbol", "quant analysis +quality"),
            "analysis.exit_plan": ("buy_price", "quant analysis +exit-plan"),
            "analysis.peers": ("symbol", "quant analysis +peers"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_screening_command_schemas(self) -> None:
        expected = {
            "screening.sector": ("sector", "quant screening +sector"),
            "screening.quality": ("min_score", "quant screening +quality"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_risk_command_schemas(self) -> None:
        expected = {
            "risk.trade_check": ("shares", "quant risk +trade-check"),
            "risk.position_size": ("signal_strength", "quant risk +position-size"),
            "risk.stop_loss": ("entry_price", "quant risk +stop-loss"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_hk_command_schemas(self) -> None:
        expected = {
            "hk.market_overview": ("quant hk +market-overview", None),
            "hk.south_flow": ("quant hk +south-flow", None),
            "hk.technical": ("quant hk +technical", "symbol"),
            "hk.hot_rank": ("quant hk +hot-rank", None),
        }

        for command_name, (example_text, param_name) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                if param_name:
                    self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_sentiment_command_schemas(self) -> None:
        expected = {
            "sentiment.stock_fund_flow": ("symbol", "quant sentiment +stock-fund-flow"),
            "sentiment.lhb": ("date", "quant sentiment +lhb"),
            "sentiment.insider_trades": ("symbol", "quant sentiment +insider-trades"),
            "sentiment.fund_holdings": ("symbol", "quant sentiment +fund-holdings"),
            "sentiment.top_fund_stocks": (None, "quant sentiment +top-fund-stocks"),
            "sentiment.top_holders": ("symbol", "quant sentiment +top-holders"),
            "sentiment.holder_changes": ("symbol", "quant sentiment +holder-changes"),
            "sentiment.margin_data": ("symbol", "quant sentiment +margin-data"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                if param_name:
                    self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_tools_describe_returns_financial_command_schemas(self) -> None:
        expected = {
            "financial.indicators": ("symbol", "quant financial +indicators"),
            "financial.statements": ("statement", "quant financial +statements"),
            "financial.hk_financials": ("symbol", "quant financial +hk-financials"),
            "financial.hk_analysis": ("symbol", "quant financial +hk-analysis"),
        }

        for command_name, (param_name, example_text) in expected.items():
            with self.subTest(command_name=command_name):
                exit_code, stdout, _stderr = self.run_cli(
                    ["tools", "+describe", command_name, "--json"]
                )

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["name"], command_name)
                self.assertIn(param_name, payload["data"]["params"])
                self.assertIn(example_text, payload["data"]["examples"][0])

    def test_unknown_command_returns_json_error(self) -> None:
        exit_code, stdout, stderr = self.run_cli(["unknown", "+missing", "--json"])

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr, "")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "UNKNOWN_COMMAND")

    def test_data_status_uses_configured_database_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "stocks.db"
            db_path.write_bytes(b"SQLite format 3\x00")

            exit_code, stdout, _stderr = self.run_cli(
                ["data", "+status", "--db-path", str(db_path), "--json"]
            )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["exists"])
        self.assertEqual(payload["data"]["path"], str(db_path))

    def test_script_command_builds_subprocess_args_and_wraps_result(self) -> None:
        completed = cli_main.subprocess.CompletedProcess(
            args=["python", "script.py"],
            returncode=0,
            stdout="script ok",
            stderr="",
        )

        with patch.object(cli_main.subprocess, "run", return_value=completed) as run:
            exit_code, stdout, _stderr = self.run_cli(
                [
                    "backtest",
                    "+run",
                    "--symbol",
                    "600519",
                    "--days",
                    "365",
                    "--capital",
                    "1000000",
                    "--json",
                ]
            )

        payload = self.parse_json_stdout(stdout)
        command = run.call_args.args[0]
        cwd = run.call_args.kwargs["cwd"]

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "backtest.run")
        self.assertIn("scripts/weekly_backtest.py", command[1])
        self.assertIn("--symbol", command)
        self.assertIn("600519", command)
        self.assertIn("--days", command)
        self.assertIn("365", command)
        self.assertEqual(Path(cwd).name, "quant")
        self.assertEqual(payload["data"]["stdout"], "script ok")

    def test_hyphenated_action_dispatches_to_underscore_command_name(self) -> None:
        completed = cli_main.subprocess.CompletedProcess(
            args=["python", "pipeline.py"],
            returncode=0,
            stdout="updated",
            stderr="",
        )

        with patch.object(cli_main.subprocess, "run", return_value=completed) as run:
            exit_code, stdout, _stderr = self.run_cli(
                ["data", "+update-klines", "--symbols", "600519,000001", "--json"]
            )

        payload = self.parse_json_stdout(stdout)
        command = run.call_args.args[0]

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "data.update_klines")
        self.assertIn("update-klines", command)
        self.assertIn("--symbols", command)

    def test_stock_klines_command_uses_quant_api(self) -> None:
        class FakeAPI:
            def get_klines(self, symbol: str, start_date=None, end_date=None, limit: int = 100):
                return {
                    "symbol": symbol,
                    "count": 1,
                    "klines": [{"date": "2026-05-19", "close": 10.0}],
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit,
                }

        with patch.object(cli_main, "QuantAPI", FakeAPI):
            exit_code, stdout, _stderr = self.run_cli(
                ["stock", "+klines", "--symbol", "600519", "--limit", "5", "--json"]
            )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["command"], "stock.klines")
        self.assertEqual(payload["data"]["symbol"], "600519")
        self.assertEqual(payload["data"]["limit"], 5)

    def test_stock_query_commands_forward_to_quant_stock_query_helpers(self) -> None:
        cases = [
            (
                ["stock", "+quote", "--symbol", "600519", "--json"],
                "get_stock_quote",
                {"symbol": "600519", "price": 100.5},
                ("600519",),
                {},
                "stock.quote",
            ),
            (
                ["stock", "+info", "--symbol", "600519", "--json"],
                "get_stock_info",
                {"symbol": "600519", "name": "贵州茅台"},
                ("600519",),
                {},
                "stock.info",
            ),
            (
                ["stock", "+history", "--symbol", "600519", "--limit", "30", "--json"],
                "get_stock_history",
                {"symbol": "600519", "count": 30, "data": []},
                ("600519",),
                {"period": "daily", "start_date": None, "end_date": None, "limit": 30},
                "stock.history",
            ),
            (
                ["stock", "+news", "--symbol", "600519", "--num", "5", "--json"],
                "get_stock_news",
                {"symbol": "600519", "count": 5, "data": []},
                ("600519",),
                {"num": 5},
                "stock.news",
            ),
            (
                ["stock", "+announcements", "--symbol", "600519", "--json"],
                "get_stock_announcements",
                {"symbol": "600519", "count": 1, "data": []},
                ("600519",),
                {},
                "stock.announcements",
            ),
            (
                ["stock", "+batch-quotes", "--symbols", "600519,000001", "--json"],
                "get_batch_stock_quotes",
                {"prices": {"600519": 100.5, "000001": 12.3}, "errors": []},
                (["600519", "000001"],),
                {},
                "stock.batch_quotes",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_stock_list_can_use_live_stock_universe_helper(self) -> None:
        helper_result = {"stocks": [{"code": "600519", "name": "贵州茅台"}]}

        with patch.object(cli_main, "get_stock_list", return_value=helper_result, create=True) as helper:
            exit_code, stdout, _stderr = self.run_cli(
                ["stock", "+list", "--market", "A", "--source", "live", "--json"]
            )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "stock.list")
        self.assertEqual(payload["data"], helper_result)
        helper.assert_called_once_with(market="A")

    def test_market_commands_forward_to_quant_market_helpers(self) -> None:
        cases = [
            (
                ["market", "+overview", "--json"],
                "get_market_overview",
                {"indices": {"上证指数": {"price": 3000}}},
                (),
                {},
                "market.overview",
            ),
            (
                ["market", "+sectors", "--json"],
                "get_sector_list",
                {"count": 1, "data": [{"name": "银行"}]},
                (),
                {},
                "market.sectors",
            ),
            (
                ["market", "+concept-stocks", "--concept", "人工智能", "--json"],
                "get_concept_stocks",
                {"concept": "人工智能", "count": 1, "data": []},
                ("人工智能",),
                {},
                "market.concept_stocks",
            ),
            (
                ["market", "+concepts", "--json"],
                "get_concept_list",
                {"count": 1, "data": [{"name": "人工智能"}]},
                (),
                {},
                "market.concepts",
            ),
            (
                ["market", "+macro", "--indicators", "pmi,cpi", "--json"],
                "get_macro_data",
                {"pmi": [], "cpi": []},
                (),
                {"indicators": ["pmi", "cpi"]},
                "market.macro",
            ),
            (
                ["market", "+north-flow", "--json"],
                "get_north_flow",
                {"data": []},
                (),
                {},
                "market.north_flow",
            ),
            (
                ["market", "+sector-flow", "--json"],
                "get_sector_fund_flow",
                {"count": 1, "data": []},
                (),
                {},
                "market.sector_flow",
            ),
            (
                ["market", "+margin", "--json"],
                "get_market_margin",
                {"count": 1, "data": []},
                (),
                {},
                "market.margin",
            ),
            (
                ["market", "+news", "--num", "9", "--json"],
                "get_market_news",
                {"sources": ["eastmoney"]},
                (),
                {"num": 9},
                "market.news",
            ),
            (
                ["market", "+hot-stocks", "--market", "港股", "--json"],
                "get_hot_stocks",
                {"market": "港股", "count": 1, "data": []},
                (),
                {"market": "港股"},
                "market.hot_stocks",
            ),
            (
                ["market", "+index-history", "--symbol", "sh000001", "--start-date", "2026-01-01", "--end-date", "2026-05-20", "--json"],
                "get_index_history",
                {"success": True, "data": []},
                ("sh000001", "2026-01-01", "2026-05-20"),
                {},
                "market.index_history",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_analysis_commands_forward_to_quant_analysis_helpers(self) -> None:
        cases = [
            (
                ["analysis", "+technical", "--symbol", "600519", "--json"],
                "calculate_technical_indicators",
                {"symbol": "600519", "signals": ["MACD金叉"]},
                ("600519",),
                {},
                "analysis.technical",
            ),
            (
                ["analysis", "+price-action", "--symbol", "600519", "--period", "80", "--json"],
                "analyze_price_action",
                {"symbol": "600519", "trend": {"direction": "上升"}},
                ("600519",),
                {"period": 80},
                "analysis.price_action",
            ),
            (
                ["analysis", "+candlestick", "--symbol", "600519", "--json"],
                "analyze_candlestick",
                {"symbol": "600519", "patterns": []},
                ("600519",),
                {},
                "analysis.candlestick",
            ),
            (
                ["analysis", "+buy-range", "--symbol", "600519", "--current-price", "100.5", "--json"],
                "calculate_buy_range",
                {"symbol": "600519", "ideal_buy": 98.0},
                ("600519",),
                {"current_price": 100.5},
                "analysis.buy_range",
            ),
            (
                ["analysis", "+valuation", "--symbol", "600519", "--json"],
                "get_stock_valuation",
                {"symbol": "600519", "pe": 22.0},
                ("600519",),
                {},
                "analysis.valuation",
            ),
            (
                ["analysis", "+pe-percentile", "--symbol", "600519", "--years", "3", "--json"],
                "get_pe_percentile",
                {"symbol": "600519", "pe_percentile": 45.0},
                ("600519",),
                {"years": 3},
                "analysis.pe_percentile",
            ),
            (
                ["analysis", "+quality", "--symbol", "600519", "--json"],
                "get_quality_score",
                {"symbol": "600519", "score": 80},
                ("600519",),
                {},
                "analysis.quality",
            ),
            (
                ["analysis", "+exit-plan", "--symbol", "600519", "--buy-price", "90", "--shares", "200", "--json"],
                "get_exit_plan",
                {"symbol": "600519", "shares": 200},
                ("600519",),
                {"buy_price": 90.0, "shares": 200},
                "analysis.exit_plan",
            ),
            (
                ["analysis", "+peers", "--symbol", "600519", "--json"],
                "compare_peers",
                {"symbol": "600519", "sector": "白酒"},
                ("600519",),
                {},
                "analysis.peers",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_screening_commands_forward_to_quant_screening_helpers(self) -> None:
        cases = [
            (
                ["screening", "+sector", "--sector", "白酒", "--min-roe", "15", "--max-pe", "30", "--limit", "8", "--json"],
                "screen_stocks_by_sector",
                {"sector": "白酒", "count": 1, "data": [{"code": "600519"}]},
                ("白酒",),
                {"min_roe": 15.0, "max_pe": 30.0, "limit": 8},
                "screening.sector",
            ),
            (
                ["screening", "+quality", "--sector", "白酒", "--min-score", "65", "--max-pe", "30", "--limit", "5", "--json"],
                "screen_stocks_quality",
                {"sector": "白酒", "qualified": 1, "data": [{"symbol": "600519"}]},
                ("白酒",),
                {"min_score": 65, "max_pe": 30.0, "limit": 5},
                "screening.quality",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_risk_commands_forward_to_quant_risk_helpers(self) -> None:
        cases = [
            (
                ["risk", "+trade-check", "--symbol", "600519", "--action", "buy", "--price", "100.5", "--shares", "300", "--json"],
                "check_trade_risk",
                {"passed": True, "adjusted_shares": 300},
                ("600519", "buy", 100.5, 300),
                {},
                "risk.trade_check",
            ),
            (
                ["risk", "+position-size", "--symbol", "600519", "--price", "100.5", "--signal-strength", "0.8", "--json"],
                "calculate_position_size",
                {"shares": 200, "method": "kelly"},
                ("600519", 100.5),
                {"signal_strength": 0.8},
                "risk.position_size",
            ),
            (
                ["risk", "+stop-loss", "--symbol", "600519", "--entry-price", "90", "--current-price", "100", "--highest-price", "110", "--json"],
                "calculate_stop_loss",
                {"stop_loss_price": 99.0, "method": "trailing"},
                ("600519", 90.0),
                {"current_price": 100.0, "highest_price": 110.0},
                "risk.stop_loss",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_hk_commands_forward_to_quant_hk_helpers(self) -> None:
        cases = [
            (
                ["hk", "+market-overview", "--json"],
                "get_hk_market_overview",
                {"indices": [{"code": "HSI"}]},
                (),
                {},
                "hk.market_overview",
            ),
            (
                ["hk", "+south-flow", "--json"],
                "get_hk_south_flow",
                {"direction": "南向（内地→港股）", "data": []},
                (),
                {},
                "hk.south_flow",
            ),
            (
                ["hk", "+technical", "--symbol", "9988", "--json"],
                "get_hk_technical",
                {"symbol": "09988", "signals": []},
                ("9988",),
                {},
                "hk.technical",
            ),
            (
                ["hk", "+hot-rank", "--json"],
                "get_hk_hot_rank",
                {"total": 1, "stocks": [{"symbol": "00700"}]},
                (),
                {},
                "hk.hot_rank",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_sentiment_commands_forward_to_quant_sentiment_helpers(self) -> None:
        cases = [
            (
                ["sentiment", "+stock-fund-flow", "--symbol", "600519", "--days", "5", "--json"],
                "get_stock_fund_flow",
                {"symbol": "600519", "count": 5},
                ("600519",),
                {"days": 5},
                "sentiment.stock_fund_flow",
            ),
            (
                ["sentiment", "+lhb", "--symbol", "600519", "--date", "20260519", "--json"],
                "get_lhb",
                {"symbol": "600519", "count": 1},
                (),
                {"symbol": "600519", "date": "20260519"},
                "sentiment.lhb",
            ),
            (
                ["sentiment", "+insider-trades", "--symbol", "600519", "--json"],
                "get_insider_trades",
                {"symbol": "600519", "count": 1},
                ("600519",),
                {},
                "sentiment.insider_trades",
            ),
            (
                ["sentiment", "+fund-holdings", "--symbol", "600519", "--json"],
                "get_fund_holdings",
                {"symbol": "600519", "count": 1},
                ("600519",),
                {},
                "sentiment.fund_holdings",
            ),
            (
                ["sentiment", "+top-fund-stocks", "--json"],
                "get_top_fund_stocks",
                {"data": []},
                (),
                {},
                "sentiment.top_fund_stocks",
            ),
            (
                ["sentiment", "+top-holders", "--symbol", "600519", "--json"],
                "get_top_holders",
                {"symbol": "600519", "count": 10},
                ("600519",),
                {},
                "sentiment.top_holders",
            ),
            (
                ["sentiment", "+holder-changes", "--symbol", "600519", "--json"],
                "get_holder_changes",
                {"symbol": "600519", "count": 8},
                ("600519",),
                {},
                "sentiment.holder_changes",
            ),
            (
                ["sentiment", "+margin-data", "--symbol", "600519", "--json"],
                "get_margin_data",
                {"symbol": "600519", "count": 10},
                ("600519",),
                {},
                "sentiment.margin_data",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_financial_commands_forward_to_quant_financial_helpers(self) -> None:
        cases = [
            (
                ["financial", "+indicators", "--symbol", "600519", "--json"],
                "get_financial_indicators",
                {"symbol": "600519", "quarters": []},
                ("600519",),
                {},
                "financial.indicators",
            ),
            (
                ["financial", "+statements", "--symbol", "600519", "--statement", "income", "--recent-n", "4", "--json"],
                "get_financial_statements",
                {"income_statement": {"data": []}},
                ("600519",),
                {"statement": "income", "recent_n": 4},
                "financial.statements",
            ),
            (
                ["financial", "+hk-financials", "--symbol", "9988", "--json"],
                "get_hk_financials",
                {"symbol": "09988", "market": "HK"},
                ("9988",),
                {},
                "financial.hk_financials",
            ),
            (
                ["financial", "+hk-analysis", "--symbol", "9988", "--json"],
                "get_hk_analysis",
                {"symbol": "09988", "market": "HK"},
                ("9988",),
                {},
                "financial.hk_analysis",
            ),
        ]

        for argv, helper_name, helper_result, expected_args, expected_kwargs, command_name in cases:
            with self.subTest(command_name=command_name):
                with patch.object(cli_main, helper_name, return_value=helper_result, create=True) as helper:
                    exit_code, stdout, _stderr = self.run_cli(argv)

                payload = self.parse_json_stdout(stdout)

                self.assertEqual(exit_code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["command"], command_name)
                self.assertEqual(payload["data"], helper_result)
                helper.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_signal_list_command_forwards_filters(self) -> None:
        calls = []

        class FakeAPI:
            def get_signals(self, date=None, signal_type=None, min_confidence: float = 0.0):
                calls.append((date, signal_type, min_confidence))
                return {"date": date, "count": 0, "signals": []}

        with patch.object(cli_main, "QuantAPI", FakeAPI):
            exit_code, stdout, _stderr = self.run_cli(
                [
                    "signal",
                    "+list",
                    "--date",
                    "2026-05-19",
                    "--signal-type",
                    "BUY",
                    "--min-confidence",
                    "0.8",
                    "--json",
                ]
            )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["command"], "signal.list")
        self.assertEqual(calls, [("2026-05-19", "BUY", 0.8)])

    def test_stock_ml_predict_command_returns_prediction(self) -> None:
        with patch.object(
            cli_main,
            "predict_stock_ml",
            return_value={
                "symbol": "600519",
                "prediction": {"direction": "UP", "up_probability": 0.62, "confidence": 0.24},
            },
        ) as predict:
            exit_code, stdout, _stderr = self.run_cli(
                ["stock", "+ml-predict", "--symbol", "600519", "--json"]
            )

        payload = self.parse_json_stdout(stdout)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["command"], "stock.ml_predict")
        self.assertEqual(payload["data"]["prediction"]["direction"], "UP")
        predict.assert_called_once_with("600519")


if __name__ == "__main__":
    unittest.main()
