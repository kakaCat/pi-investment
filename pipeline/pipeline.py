#!/usr/bin/env python3
"""CLI entrypoint for the standalone market data pipeline."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence
from types import ModuleType
from typing import Any

try:
    from pipeline.db import Database
except ImportError:  # pragma: no cover - allows `python pipeline/pipeline.py`
    from db import Database


class CommandError(Exception):
    """Raised when the CLI receives invalid input or missing implementations."""


class ParseError(CommandError):
    """Raised when command-line arguments fail validation or parsing."""


class FriendlyArgumentParser(argparse.ArgumentParser):
    """Argument parser that surfaces readable errors without exiting abruptly."""

    def error(self, message: str) -> None:
        """Convert argparse parsing failures into a command error."""
        raise ParseError(message)


def build_parser() -> FriendlyArgumentParser:
    """Create the top-level CLI parser with all supported subcommands."""
    parser = FriendlyArgumentParser(
        description="Data Pipeline - 独立的市场数据更新工具",
    )
    subparsers = parser.add_subparsers(dest="command")

    stocks_parser = subparsers.add_parser(
        "update-stocks",
        help="更新股票列表",
    )
    stocks_parser.add_argument(
        "--market",
        choices=("A", "HK"),
        default="A",
        help="市场类型，默认 A",
    )
    stocks_parser.add_argument(
        "--force",
        action="store_true",
        help="强制刷新股票列表",
    )

    klines_parser = subparsers.add_parser(
        "update-klines",
        help="更新日线 K 线数据",
    )
    klines_parser.add_argument(
        "--symbols",
        help="逗号分隔的股票代码列表",
    )
    klines_parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="拉取最近多少天的 K 线数据，默认 730",
    )

    full_parser = subparsers.add_parser(
        "full",
        help="先更新股票列表，再更新 K 线",
    )
    full_parser.add_argument(
        "--market",
        choices=("A", "HK"),
        default="A",
        help="市场类型，默认 A",
    )

    subparsers.add_parser(
        "status",
        help="查看数据库当前状态",
    )
    return parser


def parse_symbols(raw_symbols: str | None) -> list[str] | None:
    """Normalize a comma-separated symbols string into a clean list."""
    if raw_symbols is None:
        return None

    symbols = [symbol.strip() for symbol in raw_symbols.split(",") if symbol.strip()]
    if not symbols:
        raise CommandError("--symbols 不能为空")
    return symbols


def validate_args(args: argparse.Namespace) -> None:
    """Apply command-specific validation after argparse has parsed values."""
    if not args.command:
        raise ParseError("请指定要执行的命令。使用 --help 查看可用命令。")
    if getattr(args, "days", 1) <= 0:
        raise ParseError("--days 必须是大于 0 的整数")


def load_fetcher_module(module_name: str) -> ModuleType:
    """Import a fetcher module from package or script execution contexts."""
    candidates = (
        f"pipeline.fetchers.{module_name}",
        f"fetchers.{module_name}",
    )

    for candidate in candidates:
        try:
            return importlib.import_module(candidate)
        except ModuleNotFoundError as exc:
            missing_name = exc.name or ""
            if candidate != missing_name and not candidate.startswith(f"{missing_name}."):
                raise CommandError(f"加载模块 {candidate} 失败: {exc}") from exc

    raise CommandError(f"找不到 fetcher 模块: {module_name}")


def load_fetcher_class(module_name: str, class_name: str) -> type[Any]:
    """Load a fetcher class and report a clear message if it is still a placeholder."""
    module = load_fetcher_module(module_name)
    fetcher_class = getattr(module, class_name, None)
    if fetcher_class is None:
        raise CommandError(
            f"`pipeline/fetchers/{module_name}.py` 中的 `{class_name}` 尚未实现。"
        )
    return fetcher_class


def run_update_stocks(market: str, force: bool) -> None:
    """Execute the stock list update command."""
    fetcher_class = load_fetcher_class("stock_list", "StockListFetcher")
    database = Database()
    try:
        fetcher = fetcher_class(database)
        fetcher.run(market=market, force=force)
    finally:
        database.close()


def run_update_klines(symbols: list[str] | None, days: int) -> None:
    """Execute the K-line update command."""
    fetcher_class = load_fetcher_class("klines", "KlineFetcher")
    database = Database()
    try:
        fetcher = fetcher_class(database)
        fetcher.run(symbols=symbols, days=days)
    finally:
        database.close()


def run_full(market: str) -> None:
    """Execute the full pipeline update sequence."""
    stock_fetcher_class = load_fetcher_class("stock_list", "StockListFetcher")
    kline_fetcher_class = load_fetcher_class("klines", "KlineFetcher")
    database = Database()
    try:
        stock_fetcher = stock_fetcher_class(database)
        stock_fetcher.run(market=market, force=False)

        kline_fetcher = kline_fetcher_class(database)
        kline_fetcher.run(symbols=None, days=730, market=market)

        # Recalculate technical indicators after kline updates
        print("[Pipeline] 重新计算技术指标...")
        try:
            from pipeline.fetchers.technicals import TechnicalCalculator
        except ImportError:
            from fetchers.technicals import TechnicalCalculator

        calculator = TechnicalCalculator(database)
        symbols = database.get_all_symbols(market)
        for index, symbol in enumerate(symbols, start=1):
            try:
                calculator.calculate_and_update(symbol)
                if index % 10 == 0:
                    print(f"  进度: {index}/{len(symbols)}")
            except Exception as exc:
                print(f"  {symbol} 技术指标更新失败: {exc}")
    finally:
        database.close()


def run_status() -> None:
    """Print the current database status."""
    database = Database()
    try:
        database.print_status()
    finally:
        database.close()


def dispatch_command(args: argparse.Namespace) -> None:
    """Route parsed arguments to the matching command handler."""
    if args.command == "update-stocks":
        run_update_stocks(market=args.market, force=args.force)
        return

    if args.command == "update-klines":
        run_update_klines(symbols=parse_symbols(args.symbols), days=args.days)
        return

    if args.command == "full":
        run_full(market=args.market)
        return

    if args.command == "status":
        run_status()
        return

    raise CommandError(f"不支持的命令: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with friendly error handling and stable exit codes."""
    parser = build_parser()

    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        validate_args(args)
        dispatch_command(args)
        return 0
    except ParseError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except CommandError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已取消执行。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
