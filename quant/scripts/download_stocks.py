#!/usr/bin/env python3
"""下载股票数据到 PostgreSQL —— 独立脚本，可直接运行。

用法:
    python scripts/download_stocks.py              # 下载 A 股列表 + 2年日线
    python scripts/download_stocks.py --market HK  # 下载港股列表 + 2年日线
    python scripts/download_stocks.py --days 365   # 只下载最近 1 年日线
    python scripts/download_stocks.py --stocks-only # 只下载股票列表
    python scripts/download_stocks.py --with-fundamentals --stocks-only # 下载列表并回填基本面
    python scripts/download_stocks.py --industries-only # 只回填行业/板块
    python scripts/download_stocks.py --klines-only # 只下载日线（需先有股票列表）
    python scripts/download_stocks.py --symbols 000001,600519  # 只下载指定股票
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

# 禁用代理（akshare 直连比代理更快更稳定）
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
    os.environ.pop(_proxy_key, None)

# 确保 quant 包在 path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from quantsys.data.db import Database
from quantsys.data.fetchers.stock_list import StockListFetcher
from quantsys.data.fetchers.klines import KlineFetcher
from quantsys.data.fetchers.technicals import TechnicalCalculator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载股票数据到 PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                         下载 A 股列表 + 2年日线
  %(prog)s --market HK             下载港股列表 + 2年日线
  %(prog)s --market A --days 365   下载 A 股列表 + 1年日线
  %(prog)s --stocks-only           只下载 A 股列表
  %(prog)s --with-fundamentals --stocks-only  下载 A 股列表并回填基本面
  %(prog)s --industries-only       只回填 A 股行业/板块
  %(prog)s --klines-only --days 90 只下载最近 90 天日线
  %(prog)s --symbols 000001,600519 只下载指定股票的日线
        """,
    )
    parser.add_argument(
        "--market", choices=("A", "HK"), default="A",
        help="市场类型: A=A股, HK=港股 (默认: A)",
    )
    parser.add_argument(
        "--days", type=int, default=730,
        help="拉取最近多少天的日线数据 (默认: 730)",
    )
    parser.add_argument(
        "--stocks-only", action="store_true",
        help="只下载股票列表，不下载日线",
    )
    parser.add_argument(
        "--klines-only", action="store_true",
        help="只下载日线数据（需数据库中已有股票列表）",
    )
    parser.add_argument(
        "--symbols", type=str, default=None,
        help="逗号分隔的股票代码列表（仅对日线有效）",
    )
    parser.add_argument(
        "--no-technicals", action="store_true",
        help="跳过技术指标计算",
    )
    parser.add_argument(
        "--with-fundamentals", action="store_true",
        help="下载 A 股列表后回填 ROE/毛利率/负债率/净利润增速",
    )
    parser.add_argument(
        "--fundamentals-only", action="store_true",
        help="跳过股票列表和K线，只按数据库已有股票池回填基本面",
    )
    parser.add_argument(
        "--industries-only", action="store_true",
        help="跳过股票列表和K线，只回填 A 股行业/板块",
    )
    parser.add_argument(
        "--symbol-prefixes",
        type=str,
        default="000,001,002,003,300,301,600,601,603,605,688",
        help="基本面回填的股票代码前缀过滤，逗号分隔；传 all 表示不过滤",
    )
    return parser.parse_args()


def print_header(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_db_status(db: Database) -> None:
    """打印当前数据库状态。"""
    a_count = db.count_stocks("A")
    hk_count = db.count_stocks("HK")
    stats = db.get_kline_stats()
    print(f"  A股: {a_count} 只 | 港股: {hk_count} 只")
    print(f"  K线记录: {stats['records']:,} 条 | 覆盖: {stats['symbols']} 只")
    if stats["min_date"] and stats["max_date"]:
        print(f"  K线范围: {stats['min_date']} ~ {stats['max_date']}")


def download_stocks(db: Database, market: str, with_fundamentals: bool = False) -> None:
    """下载股票列表。"""
    print_header(f"📋 下载{market}股列表")
    fetcher = StockListFetcher(db)
    t0 = time.time()
    fetcher.run(market=market, force=False, with_fundamentals=with_fundamentals)
    elapsed = time.time() - t0
    print(f"  ✅ 股票列表更新完成，耗时 {elapsed:.1f}s")


def download_klines(
    db: Database,
    market: str,
    days: int,
    symbols: list[str] | None,
) -> None:
    """下载日线数据。"""
    symbol_list = symbols or db.get_all_symbols(market)
    if not symbol_list:
        print("  ⚠️  数据库中没有股票，请先运行 --stocks-only 下载股票列表")
        return

    symbol_count = len(symbol_list)
    print_header(f"📈 下载日线数据 ({symbol_count} 只股票, 最近 {days} 天)")

    fetcher = KlineFetcher(db)
    t0 = time.time()
    result = fetcher.run(symbols=symbol_list, days=days, market=market)
    elapsed = time.time() - t0

    print(f"  ✅ 完成: 成功 {result.succeeded}/{result.total}, 耗时 {elapsed:.1f}s")
    if result.failures:
        print(f"  ⚠️  失败 {len(result.failures)} 只:")
        for f in result.failures[:10]:
            print(f"     - {f['symbol']}: {f['error']}")
        if len(result.failures) > 10:
            print(f"     ... 还有 {len(result.failures) - 10} 只失败")


def download_technicals(db: Database, market: str) -> None:
    """计算并更新技术指标。"""
    symbols = db.get_all_symbols(market)
    if not symbols:
        return

    print_header("📊 计算技术指标")
    calculator = TechnicalCalculator(db)
    total = len(symbols)
    t0 = time.time()
    success = 0

    for i, symbol in enumerate(symbols, 1):
        try:
            calculator.calculate_and_update(symbol)
            success += 1
        except Exception as exc:
            print(f"  ⚠️  {symbol} 技术指标计算失败: {exc}")

        if i % 50 == 0 or i == total:
            pct = i * 100 // total
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"  [{i}/{total}] {pct}% | 速率 {rate:.1f}只/s | 预计剩余 {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"  ✅ 技术指标计算完成: 成功 {success}/{total}, 耗时 {elapsed:.1f}s")


def download_fundamentals(
    db: Database,
    market: str,
    symbols: list[str] | None,
    prefixes: list[str] | None = None,
) -> None:
    """按数据库已有股票池回填基本面。"""
    symbol_list = symbols or db.get_all_symbols(market)
    if prefixes:
        symbol_list = [symbol for symbol in symbol_list if any(symbol.startswith(prefix) for prefix in prefixes)]
    if not symbol_list:
        print("  ⚠️  数据库中没有股票，请先运行 --stocks-only 下载股票列表")
        return

    print_header(f"📊 回填基本面 ({len(symbol_list)} 只股票)")
    fetcher = StockListFetcher(db)
    t0 = time.time()
    count = fetcher.backfill_fundamentals(symbol_list)
    elapsed = time.time() - t0
    print(f"  ✅ 基本面回填完成: 更新 {count} 只，耗时 {elapsed:.1f}s")


def download_industries(db: Database, market: str) -> None:
    """按行业板块成分回填行业和板块字段。"""
    if market != "A":
        print("  ⚠️  行业回填目前只支持 A 股")
        return

    print_header("🏷️  回填行业/板块")
    fetcher = StockListFetcher(db)
    t0 = time.time()
    count = fetcher.backfill_industries()
    elapsed = time.time() - t0
    print(f"  ✅ 行业/板块回填完成: 更新 {count} 只，耗时 {elapsed:.1f}s")


def main() -> int:
    args = parse_args()

    # 验证参数
    if args.days <= 0:
        print("错误: --days 必须大于 0", file=sys.stderr)
        return 2
    if args.fundamentals_only and args.market != "A":
        print("错误: --fundamentals-only 目前只支持 A 股", file=sys.stderr)
        return 2
    if args.industries_only and args.market != "A":
        print("错误: --industries-only 目前只支持 A 股", file=sys.stderr)
        return 2

    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        if not symbols:
            print("错误: --symbols 不能为空", file=sys.stderr)
            return 2

    prefixes = None
    if args.symbol_prefixes.strip().lower() != "all":
        prefixes = [p.strip() for p in args.symbol_prefixes.split(",") if p.strip()]

    # 连接数据库
    print_header("🔌 连接 PostgreSQL")
    try:
        db = Database()
    except Exception as exc:
        print(f"  ❌ 数据库连接失败: {exc}", file=sys.stderr)
        print(f"  提示: 请确保 PostgreSQL 已启动，且环境变量配置正确", file=sys.stderr)
        print(f"  当前配置: PGDATABASE={os.environ.get('PGDATABASE', 'quant_investment')}", file=sys.stderr)
        return 1

    try:
        print("  ✅ 已连接")
        print_db_status(db)

        if args.fundamentals_only:
            download_fundamentals(db, args.market, symbols, prefixes=prefixes)
            print_header("📋 最终状态")
            print_db_status(db)
            print()
            print("🎉 全部完成!")
            return 0

        if args.industries_only:
            download_industries(db, args.market)
            print_header("📋 最终状态")
            print_db_status(db)
            print()
            print("🎉 全部完成!")
            return 0

        # 1. 下载股票列表
        if not args.klines_only:
            download_stocks(db, args.market, with_fundamentals=args.with_fundamentals)

        # 2. 下载日线
        if not args.stocks_only:
            download_klines(db, args.market, args.days, symbols)

        # 3. 计算技术指标
        if not args.stocks_only and not args.no_technicals:
            download_technicals(db, args.market)

        # 最终状态
        print_header("📋 最终状态")
        print_db_status(db)

    except KeyboardInterrupt:
        print("\n⚠️  用户中断", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\n❌ 执行失败: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print()
    print("🎉 全部完成!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
