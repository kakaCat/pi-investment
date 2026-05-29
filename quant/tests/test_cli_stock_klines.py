"""Tests for stock.klines CLI command."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch, MagicMock

from quantsys.cli import main as cli_main


class StockKlinesTests(unittest.TestCase):
    """Verify stock.klines command handles period parameter correctly."""

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli_main.main(argv)

        return exit_code, stdout.getvalue(), stderr.getvalue()

    def parse_json_stdout(self, stdout: str) -> dict:
        return json.loads(stdout)

    @patch('quantsys.cli.main.get_stock_history')
    def test_stock_klines_with_period_parameter(self, mock_get_history: MagicMock) -> None:
        """Test that stock.klines command accepts period parameter without error."""
        # Arrange
        mock_get_history.return_value = {
            "symbol": "600519",
            "period": "daily",
            "count": 10,
            "klines": [
                {"date": "2026-05-26", "open": 100.0, "close": 101.0, "high": 102.0, "low": 99.0, "volume": 1000}
            ]
        }

        # Act
        exit_code, stdout, stderr = self.run_cli([
            "stock", "+klines",
            "--symbol", "600519",
            "--period", "daily",
            "--limit", "10",
            "--json"
        ])

        # Assert
        self.assertEqual(exit_code, 0, f"Expected exit code 0, got {exit_code}. stderr: {stderr}")
        self.assertEqual(stderr, "", f"Expected no stderr output, got: {stderr}")

        # Verify get_stock_history was called with correct parameters
        mock_get_history.assert_called_once()
        call_args = mock_get_history.call_args
        self.assertEqual(call_args.kwargs.get('symbol') or call_args.args[0], "600519")
        self.assertEqual(call_args.kwargs.get('period', 'daily'), "daily")
        self.assertEqual(call_args.kwargs.get('limit', 100), 10)

    @patch('quantsys.cli.main.get_stock_history')
    def test_stock_klines_with_5min_period(self, mock_get_history: MagicMock) -> None:
        """Test that stock.klines command supports intraday periods like 5min."""
        # Arrange
        mock_get_history.return_value = {
            "symbol": "600519",
            "period": "5min",
            "count": 50,
            "klines": []
        }

        # Act
        exit_code, stdout, stderr = self.run_cli([
            "stock", "+klines",
            "--symbol", "600519",
            "--period", "5min",
            "--limit", "50",
            "--json"
        ])

        # Assert
        self.assertEqual(exit_code, 0, f"Expected exit code 0, got {exit_code}. stderr: {stderr}")

        # Verify period was passed correctly
        call_args = mock_get_history.call_args
        self.assertEqual(call_args.kwargs.get('period', 'daily'), "5min")


if __name__ == "__main__":
    unittest.main()
