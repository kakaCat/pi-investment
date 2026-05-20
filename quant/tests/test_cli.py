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
