"""Tests for the pipeline CLI entrypoint."""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

DATA_ROOT = Path(__file__).resolve().parents[1]
if str(DATA_ROOT) not in sys.path:
    sys.path.insert(0, str(DATA_ROOT))

import pipeline as pipeline_cli


class PipelineCliTests(unittest.TestCase):
    """Verify command parsing, routing, and friendly failures."""

    def test_update_stocks_uses_default_market_and_force_flag(self) -> None:
        """update-stocks should route with the documented default arguments."""
        calls: list[tuple[str, object]] = []

        class FakeDatabase:
            def close(self) -> None:
                calls.append(("close", None))

        class FakeFetcher:
            def __init__(self, database: FakeDatabase) -> None:
                calls.append(("init", database))

            def run(self, market: str, force: bool, with_fundamentals: bool = False) -> None:
                calls.append(("run", (market, force, with_fundamentals)))

        with patch.object(pipeline_cli, "Database", FakeDatabase), patch.object(
            pipeline_cli, "load_fetcher_class", return_value=FakeFetcher
        ):
            exit_code = pipeline_cli.main(["update-stocks"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[1], ("run", ("A", False, False)))
        self.assertEqual(calls[-1], ("close", None))

    def test_update_stocks_can_request_fundamental_backfill(self) -> None:
        """update-stocks should pass the fundamental backfill flag to the fetcher."""
        calls: list[tuple[str, object]] = []

        class FakeDatabase:
            def close(self) -> None:
                calls.append(("close", None))

        class FakeFetcher:
            def __init__(self, database: FakeDatabase) -> None:
                calls.append(("init", database))

            def run(self, market: str, force: bool, with_fundamentals: bool = False) -> None:
                calls.append(("run", (market, force, with_fundamentals)))

        with patch.object(pipeline_cli, "Database", FakeDatabase), patch.object(
            pipeline_cli, "load_fetcher_class", return_value=FakeFetcher
        ):
            exit_code = pipeline_cli.main(["update-stocks", "--market", "A", "--with-fundamentals"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[1], ("run", ("A", False, True)))

    def test_update_klines_parses_symbols_and_days(self) -> None:
        """update-klines should split comma-separated symbols and pass days through."""
        calls: list[tuple[str, object]] = []

        class FakeDatabase:
            def close(self) -> None:
                calls.append(("close", None))

        class FakeFetcher:
            def __init__(self, database: FakeDatabase) -> None:
                calls.append(("init", database))

            def run(self, symbols: list[str] | None, days: int) -> None:
                calls.append(("run", (symbols, days)))

        with patch.object(pipeline_cli, "Database", FakeDatabase), patch.object(
            pipeline_cli, "load_fetcher_class", return_value=FakeFetcher
        ):
            exit_code = pipeline_cli.main(
                ["update-klines", "--symbols", "600519, 000001 ,00700", "--days", "365"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[1], ("run", (["600519", "000001", "00700"], 365)))
        self.assertEqual(calls[-1], ("close", None))

    def test_status_routes_to_database_status(self) -> None:
        """status should invoke the database summary output."""
        calls: list[str] = []

        class FakeDatabase:
            def print_status(self) -> None:
                calls.append("status")

            def close(self) -> None:
                calls.append("close")

        with patch.object(pipeline_cli, "Database", FakeDatabase):
            exit_code = pipeline_cli.main(["status"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, ["status", "close"])

    def test_full_runs_stock_then_klines(self) -> None:
        """full should run stock update before kline update."""
        calls: list[tuple[str, object]] = []

        class FakeDatabase:
            def close(self) -> None:
                calls.append(("close", None))

            def get_all_symbols(self, market: str | None = None) -> list[str]:
                return []

        class StockFetcher:
            def __init__(self, database: FakeDatabase) -> None:
                calls.append(("stock-init", database))

            def run(self, market: str, force: bool, with_fundamentals: bool = False) -> None:
                calls.append(("stock-run", (market, force, with_fundamentals)))

        class KlineFetcher:
            def __init__(self, database: FakeDatabase) -> None:
                calls.append(("kline-init", database))

            def run(self, symbols: list[str] | None, days: int, market: str | None = None) -> None:
                calls.append(("kline-run", (symbols, days, market)))

        def fake_loader(module_name: str, class_name: str) -> type[object]:
            if class_name == "StockListFetcher":
                return StockFetcher
            if class_name == "KlineFetcher":
                return KlineFetcher
            raise AssertionError(f"Unexpected fetcher request: {module_name}.{class_name}")

        with patch.object(pipeline_cli, "Database", FakeDatabase), patch.object(
            pipeline_cli, "load_fetcher_class", side_effect=fake_loader
        ):
            exit_code = pipeline_cli.main(["full", "--market", "HK"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            calls,
            [
                ("stock-init", unittest.mock.ANY),
                ("stock-run", ("HK", False, False)),
                ("kline-init", unittest.mock.ANY),
                ("kline-run", (None, 730, "HK")),
                ("close", None),
            ],
        )

    def test_missing_command_returns_friendly_error(self) -> None:
        """Missing subcommands should return a readable error message."""
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = pipeline_cli.main([])

        self.assertEqual(exit_code, 2)
        self.assertIn("请指定要执行的命令", stderr.getvalue())

    def test_missing_fetcher_implementation_returns_friendly_error(self) -> None:
        """Empty placeholder fetcher modules should produce a clear message."""
        stderr = io.StringIO()

        empty_module = ModuleType("pipeline.fetchers.klines")

        with patch.object(pipeline_cli, "load_fetcher_module", return_value=empty_module), redirect_stderr(stderr):
            exit_code = pipeline_cli.main(["update-klines"])

        self.assertEqual(exit_code, 1)
        self.assertIn("尚未实现", stderr.getvalue())

    def test_load_fetcher_module_falls_back_to_script_relative_import(self) -> None:
        """Module loading should support `python pipeline/pipeline.py ...` execution."""
        fallback_module = ModuleType("fetchers.stock_list")
        import_error = ModuleNotFoundError("No module named 'pipeline.fetchers'")
        import_error.name = "pipeline.fetchers"

        with patch.object(
            pipeline_cli.importlib,
            "import_module",
            side_effect=[
                import_error,
                fallback_module,
            ],
        ) as import_module:
            module = pipeline_cli.load_fetcher_module("stock_list")

        self.assertIs(module, fallback_module)
        self.assertEqual(
            [call.args[0] for call in import_module.call_args_list],
            ["pipeline.fetchers.stock_list", "fetchers.stock_list"],
        )


if __name__ == "__main__":
    unittest.main()
