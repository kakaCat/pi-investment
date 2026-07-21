#!/usr/bin/env python
"""
策略→股票适配匹配器（Strategy-Stock Matcher）

批量对多只股票 × 多个策略做信号生成 + 回测，筛选出每个策略有效的
股票，将合格信号写入 quant.signals 数据库。

DDD Architecture:
- Depends on IKlineRepository, ISignalRepository interfaces
- Application layer or CLI entry point injects concrete implementations

用法:
    # 默认：沪深300市值top300 × 所有已注册策略
    python -m quantlib.tools.strategy_stock_matcher

    # 自定义股票和策略
    python -m quantlib.tools.strategy_stock_matcher \
        --stocks 600519 000858 002415 \
        --strategies adx_trend rsi_reversal ensemble_vote

    # 干跑模式（不写入DB）
    python -m quantlib.tools.strategy_stock_matcher --dry-run --verbose

    # 调整过滤门槛
    python -m quantlib.tools.strategy_stock_matcher \
        --min-win-rate 0.6 --min-return 0.05 --days 120
"""
import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from domain.ports import IKlineRepository, ISignalRepository
from domain.quantlib.engine.strategy_factory import StrategyFactory
from domain.quantlib.engine.strategy_base import StrategyBase
from domain.quantlib.stages.backtest_stage import BacktestStage

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PairResult:
    """一只股票 × 一个策略的完整结果。"""
    symbol: str
    stock_name: str
    strategy_name: str
    win_rate: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    trade_count: int
    annual_return: float
    final_capital: float
    initial_capital: float
    signals: List[dict] = field(default_factory=list)
    backtest_raw: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def is_qualified(self) -> bool:
        if self.error is not None:
            return False
        time.sleep(0)
        return True

    @property
    def summary(self) -> str:
        if self.error:
            return f"  {self.symbol} × {self.strategy_name}: ❌ {self.error}"
        return (
            f"  {self.symbol} × {self.strategy_name}: "
            f"win_rate={self.win_rate:.2%} return={self.total_return:.2%} "
            f"sharpe={self.sharpe_ratio:.2f} trades={self.trade_count}"
        )


# ============================================================================
# Strategy-Stock Matcher
# ============================================================================

class StrategyStockMatcher:
    """批量策略×股票适配测试器。

    流程:
    1. 加载股票池（沪深300市值top300 或 用户指定）
    2. 对每只股票加载K线数据
    3. 对每个策略生成滚动窗口信号序列
    4. 用BacktestStage回测信号序列
    5. 筛选指标达标的配对
    6. 写入quant.signals数据库
    """

    # 信号生成的最小K线窗口（起手足够数据才开始生成信号）
    MIN_SIGNAL_LOOKBACK = 50

    # 生成信号的最小数据门槛（<100天直接跳过）
    MIN_KLINES_LENGTH = 100

    def __init__(
        self,
        kline_repo: Optional[IKlineRepository] = None,
        signal_repo: Optional[ISignalRepository] = None
    ):
        """
        Initialize Strategy-Stock Matcher

        Args:
            kline_repo: Kline repository interface (injected by Application/CLI)
            signal_repo: Signal repository interface (injected by Application/CLI)

        Note:
            For backward compatibility, repositories are optional but should be injected
        """
        # 临时兼容：如果未注入则自动创建（违反 DDD）
        # TODO: 移除后备逻辑，要求调用方必须注入
        if kline_repo is None or signal_repo is None:
            from adapters.outbound.repositories import KlineORMRepository, SignalORMRepository
            kline_repo = kline_repo or KlineORMRepository()
            signal_repo = signal_repo or SignalORMRepository()

        self.kline_repo = kline_repo
        self.signal_repo = signal_repo
        self.backtest_stage = BacktestStage(
            initial_capital=1_000_000,
            commission_rate=0.00025,
            stamp_tax_rate=0.001,
            slippage_rate=0.001,
        )

    # ------------------------------------------------------------------
    # 股票池加载
    # ------------------------------------------------------------------

    def load_stock_universe(
        self, symbols: Optional[List[str]] = None, top_n: int = 300
    ) -> List[Tuple[str, str]]:
        """获取股票池，返回 [(symbol, name), ...]。

        如果 symbols 已提供则直接使用；否则从 quant.stocks 取 top_n
        只按市值排名（排除 ST 和停牌）。
        """
        if symbols:
            db = BaseRepository().db
            cursor = db.cursor()
            placeholders = ','.join(['%s'] * len(symbols))
            cursor.execute(
                f"SELECT symbol, name FROM quant.stocks WHERE symbol IN ({placeholders})",
                tuple(symbols),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [(r['symbol'], r['name']) for r in rows]

        # 默认：市值 top N（排除 ST 和停牌）
        db = BaseRepository().db
        cursor = db.cursor()
        cursor.execute("""
            SELECT symbol, name
            FROM quant.stocks
            WHERE is_st = FALSE
              AND is_suspended = FALSE
              AND market_cap IS NOT NULL
              AND market_cap > 0
            ORDER BY market_cap DESC
            LIMIT %s
        """, (top_n,))
        rows = cursor.fetchall()
        cursor.close()
        return [(r['symbol'], r['name']) for r in rows]

    # ------------------------------------------------------------------
    # K线加载
    # ------------------------------------------------------------------

    def load_klines(
        self, symbol: str, days: int
    ) -> Optional[pd.DataFrame]:
        """加载一只股票的K线数据。

        Args:
            symbol: 股票代码
            days: 交易日数量（往前推）

        Returns:
            DataFrame with trade_date/open/high/low/close/volume，或 None
        """
        end_date = date.today().strftime('%Y-%m-%d')
        # 往前推足够多的自然日来覆盖交易日
        start_date = (date.today() - timedelta(days=int(days * 1.6))).strftime('%Y-%m-%d')

        try:
            raw = self.kline_repo.get_daily_klines(
                symbol, start_date, end_date,
                fields=['trade_date', 'open', 'high', 'low', 'close', 'volume'],
            )
        except Exception as e:
            logger.warning("load_klines %s error: %s", symbol, e)
            return None

        if not raw or len(raw) < self.MIN_KLINES_LENGTH:
            return None

        df = pd.DataFrame(raw)
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 取最后 days 个交易日
        df = df.sort_values('trade_date').tail(days)
        if len(df) < self.MIN_KLINES_LENGTH:
            return None
        return df

    # ------------------------------------------------------------------
    # K线 → 信号序列：滚动窗口生成
    # ------------------------------------------------------------------

    def generate_signal_series(
        self,
        strategy: StrategyBase,
        klines_df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        """用滚动窗口生成信号时间序列。

        对 klines_df 从 MIN_SIGNAL_LOOKBACK 起步，每个时间点调用一次
        generate_signal，收集所有非 hold 的信号。

        Args:
            strategy: 策略实例
            klines_df: 完整K线 DataFrame（按日期升序）

        Returns:
            信号列表 [{date, action, symbol, reason, confidence, price}, ...]
        """
        klines_dicts = klines_df.to_dict('records')
        symbol = klines_dicts[0].get('symbol', '')
        signals: List[Dict[str, Any]] = []

        for i in range(self.MIN_SIGNAL_LOOKBACK, len(klines_dicts)):
            window = klines_dicts[i - self.MIN_SIGNAL_LOOKBACK:i + 1]
            # 确保窗口内的数据是足够的
            if len(window) < 30:
                continue

            try:
                result = strategy.generate_signal(window)
            except Exception as e:
                logger.debug(
                    "%s signal at index %d failed: %s",
                    strategy.name, i, e,
                )
                continue

            action = result.get('action', 'hold')
            if action == 'hold':
                continue

            trade_date = klines_dicts[i].get('trade_date', '')
            signals.append({
                'date': trade_date,
                'action': action,
                'symbol': symbol,
                'reason': result.get('reason', ''),
                'confidence': float(result.get('confidence', 0.5)),
                'price': float(klines_dicts[i].get('close', 0)),
            })

        return signals

    # ------------------------------------------------------------------
    # 单对回测
    # ------------------------------------------------------------------

    def run_single_pair(
        self,
        symbol: str,
        stock_name: str,
        strategy_name: str,
        klines_df: pd.DataFrame,
    ) -> PairResult:
        """运行一只股票 × 一个策略的完整回测管线。"""
        start = time.monotonic()

        try:
            strategy = StrategyFactory.create(strategy_name)
        except ValueError as e:
            return PairResult(
                symbol=symbol, stock_name=stock_name,
                strategy_name=strategy_name, error=f"create strategy: {e}",
            )

        # 生成信号序列
        klines_rows = klines_df.to_dict('records')
        signals = self.generate_signal_series(strategy, klines_df)

        if len(signals) < 2:
            return PairResult(
                symbol=symbol, stock_name=stock_name,
                strategy_name=strategy_name,
                error=f"only {len(signals)} non-hold signals, need ≥2 trades",
            )

        # K线格式转换：BacktestStage 接受 List[Dict]
        klines_for_bt = [
            {
                'date': r['trade_date'],
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close']),
                'volume': float(r.get('volume', 0) or 0),
            }
            for r in klines_rows
        ]

        try:
            bt_result = self.backtest_stage.process({
                'symbol': symbol,
                'klines': klines_for_bt,
                'signals': signals,
            })
        except Exception as e:
            return PairResult(
                symbol=symbol, stock_name=stock_name,
                strategy_name=strategy_name, error=f"backtest: {e}",
            )

        metrics = bt_result['backtest']['metrics']
        elapsed = time.monotonic() - start
        logger.debug(
            "%s × %s: win_rate=%.2f return=%.2f%% (%.1fs)",
            symbol, strategy_name,
            metrics['win_rate'], metrics['total_return'] * 100, elapsed,
        )

        return PairResult(
            symbol=symbol,
            stock_name=stock_name,
            strategy_name=strategy_name,
            win_rate=metrics['win_rate'],
            total_return=metrics['total_return'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown=metrics['max_drawdown'],
            trade_count=metrics['total_trades'],
            annual_return=metrics['annual_return'],
            final_capital=metrics['final_capital'],
            initial_capital=metrics['initial_capital'],
            signals=signals,
            backtest_raw=bt_result,
        )

    # ------------------------------------------------------------------
    # 批量运行
    # ------------------------------------------------------------------

    def run_batch(
        self,
        stock_universe: List[Tuple[str, str]],
        strategy_names: List[str],
        days: int = 250,
        verbose: bool = False,
    ) -> Tuple[List[PairResult], List[Tuple[str, str, str]]]:
        """批量执行所有配对。

        Args:
            stock_universe: [(symbol, name), ...]
            strategy_names: 策略类型名称列表
            days: 回测天数
            verbose: 是否打印每个配对进度

        Returns:
            (all_results, errors) — errors = [(symbol, strategy, msg), ...]
        """
        all_results: List[PairResult] = []
        error_pairs: List[Tuple[str, str, str]] = []

        total_pairs = len(stock_universe) * len(strategy_names)
        completed = 0

        for idx, (symbol, name) in enumerate(stock_universe):
            klines_df = self.load_klines(symbol, days)
            if klines_df is None:
                logger.info("skip %s: insufficient klines", symbol)
                completed += len(strategy_names)
                continue

            for sname in strategy_names:
                result = self.run_single_pair(
                    symbol, name, sname, klines_df,
                )
                all_results.append(result)
                if result.error:
                    error_pairs.append((symbol, sname, result.error))

                completed += 1
                if verbose:
                    pct = completed / total_pairs * 100
                    status = '❌' if result.error else '✅'
                    print(
                        f"[{completed}/{total_pairs} {pct:.0f}%] "
                        f"{status} {result.summary}",
                        flush=True,
                    )

        return all_results, error_pairs

    # ------------------------------------------------------------------
    # 过滤 + 信号写入
    # ------------------------------------------------------------------

    def filter_results(
        self,
        results: List[PairResult],
        min_win_rate: float = 0.5,
        min_return: float = 0.0,
    ) -> List[PairResult]:
        """按门槛筛选合格的策略→股票配对。"""
        qualified: List[PairResult] = []
        for r in results:
            if r.error is not None:
                continue
            if r.win_rate < min_win_rate:
                continue
            if r.total_return <= min_return:
                continue
            qualified.append(r)
        return qualified

    def write_signals(
        self,
        qualified: List[PairResult],
        dry_run: bool = False,
    ) -> int:
        """将合格配对的所有交易信号写入 quant.signals。

        每条信号的字段映射:
          signal_date ← signal['date']
          symbol      ← PairResult.symbol
          name        ← PairResult.stock_name
          action      ← signal['action'] (buy/sell)
          action_type ← 1=buy, 2=sell
          strategy_id ← PairResult.strategy_name
          price       ← signal['price']
          reason      ← signal['reason']
          confidence  ← signal['confidence']
          indicators  ← 空对象（策略级别不用逐笔因子）
        """
        if dry_run:
            count = sum(len(r.signals) for r in qualified)
            logger.info("DRY RUN: would write %d signals for %d pairs", count, len(qualified))
            return count

        written = 0
        for r in qualified:
            for sig in r.signals:
                action = sig.get('action', 'hold')
                if action == 'hold':
                    continue
                action_type = 1 if action == 'buy' else 2
                try:
                    self.signal_repo.create_signal({
                        'signal_date': sig['date'],
                        'symbol': r.symbol,
                        'name': r.stock_name,
                        'action': action,
                        'action_type': action_type,
                        'strategy_id': r.strategy_name,
                        'price': sig.get('price'),
                        'reason': sig.get('reason', ''),
                        'confidence': float(sig.get('confidence', 0.5)),
                        'indicators': {},
                    })
                    written += 1
                except Exception as e:
                    logger.warning(
                        "write signal failed: %s %s %s — %s",
                        r.symbol, r.strategy_name, sig['date'], e,
                    )

        logger.info("Wrote %d signals for %d pairs", written, len(qualified))
        return written

    # ------------------------------------------------------------------
    # 报告
    # ------------------------------------------------------------------

    def generate_report(
        self,
        all_results: List[PairResult],
        qualified: List[PairResult],
        error_pairs: List[Tuple[str, str, str]],
        min_win_rate: float,
        min_return: float,
        days: int,
    ) -> str:
        """生成汇总报告。"""
        lines: List[str] = []

        lines.append("=" * 72)
        lines.append(" 策略→股票匹配报告")
        lines.append("=" * 72)
        lines.append(f"  回测窗口: {days} 交易日")
        lines.append(f"  筛选门槛: win_rate ≥ {min_win_rate:.0%}, total_return > {min_return:.0%}")
        lines.append(f"  测试配对: {len(all_results)} 组")
        lines.append(f"  合格配对: {len(qualified)} 组")
        lines.append(f"  失败/跳过: {len(error_pairs)} 组")
        lines.append(f"  总耗时: 见日志")
        lines.append("")

        if not qualified:
            lines.append("⚠️ 没有合格配对。尝试降低 --min-win-rate 或 --min-return。")
            return "\n".join(lines)

        # 按策略分组
        by_strategy: Dict[str, List[PairResult]] = {}
        for r in qualified:
            by_strategy.setdefault(r.strategy_name, []).append(r)

        for sname in sorted(by_strategy.keys()):
            results = by_strategy[sname]
            lines.append("-" * 72)
            lines.append(f" ▸ {sname} — {len(results)} 只合格股票")
            lines.append(f"   平均 win_rate: {sum(r.win_rate for r in results)/len(results):.1%}")
            lines.append(f"   平均 return: {sum(r.total_return for r in results)/len(results):.2%}")
            lines.append(f"   平均 sharpe: {sum(r.sharpe_ratio for r in results)/len(results):.2f}")
            lines.append("")
            lines.append(f"   {'股票代码':<12s} {'名称':<10s} {'win_rate':>8s} {'return':>9s} {'sharpe':>7s} {'trades':>7s}")
            lines.append("   " + "-" * 58)
            for r in sorted(results, key=lambda x: x.total_return, reverse=True)[:20]:
                lines.append(
                    f"   {r.symbol:<12s} {r.stock_name:<10s} "
                    f"{r.win_rate:>7.1%} {r.total_return:>8.2%} "
                    f"{r.sharpe_ratio:>6.2f} {r.trade_count:>6d}"
                )
            if len(results) > 20:
                lines.append(f"   ... 以及其他 {len(results) - 20} 只股票")
            lines.append("")

        # 错误汇总
        if error_pairs:
            lines.append("-" * 72)
            lines.append(" 失败/跳过明细（前20）:")
            for sym, sn, err in error_pairs[:20]:
                lines.append(f"   {sym} × {sn}: {err}")
            lines.append("")

        lines.append("=" * 72)
        return "\n".join(lines)


# ============================================================================
# CLI Entry Point
# ============================================================================

def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        description="策略→股票适配匹配器：批量回测筛选有效策略×股票配对",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m quantlib.tools.strategy_stock_matcher --dry-run --verbose
  python -m quantlib.tools.strategy_stock_matcher --stocks 600519 000858 --strategies adx_trend
  python -m quantlib.tools.strategy_stock_matcher --min-win-rate 0.55 --min-return 0.05
        """,
    )

    parser.add_argument(
        '--stocks', nargs='*', default=None,
        help='股票代码列表（默认：沪深300市值top300）',
    )
    parser.add_argument(
        '--strategies', nargs='*', default=None,
        help='策略名称列表（默认：所有自动发现的策略）',
    )
    parser.add_argument(
        '--days', type=int, default=250,
        help='回测交易日数（默认: 250）',
    )
    parser.add_argument(
        '--min-win-rate', type=float, default=0.5,
        help='最低胜率门槛（默认: 0.5）',
    )
    parser.add_argument(
        '--min-return', type=float, default=0.0,
        help='最低总收益门槛（默认: 0.0）',
    )
    parser.add_argument(
        '--top-n', type=int, default=300,
        help='默认股票池取市值前N只（默认: 300）',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='只回测不写入数据库',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='实时打印每个配对进度',
    )
    parser.add_argument(
        '--log-level', default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别（默认: INFO）',
    )

    args = parser.parse_args(argv)

    # 日志配置
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    # 初始化策略工厂
    StrategyFactory.auto_discover()
    available_strategies = StrategyFactory.list_all()

    strategy_names = args.strategies or available_strategies
    # 验证策略名称
    invalid = [s for s in strategy_names if s not in available_strategies]
    if invalid:
        logger.error("未知策略: %s。可用: %s", invalid, available_strategies)
        sys.exit(1)

    logger.info("策略列表 (%d): %s", len(strategy_names), strategy_names)

    # 初始化匹配器
    matcher = StrategyStockMatcher()

    # 加载股票池
    stock_universe = matcher.load_stock_universe(
        symbols=args.stocks, top_n=args.top_n,
    )
    logger.info("股票池: %d 只", len(stock_universe))

    if not stock_universe:
        logger.error("股票池为空，退出")
        sys.exit(1)

    # 批量运行
    print(f"\n=== 开始匹配: {len(stock_universe)} 股票 × {len(strategy_names)} 策略 ===", flush=True)
    print(f"    回测窗口: {args.days} 天 | 门槛: win_rate≥{args.min_win_rate} return>{args.min_return}", flush=True)
    print(f"    模式: {'干跑（不写入DB）' if args.dry_run else '写入DB'}\n", flush=True)

    t0 = time.monotonic()
    all_results, error_pairs = matcher.run_batch(
        stock_universe=stock_universe,
        strategy_names=strategy_names,
        days=args.days,
        verbose=args.verbose,
    )
    elapsed = time.monotonic() - t0

    # 过滤
    qualified = matcher.filter_results(
        all_results,
        min_win_rate=args.min_win_rate,
        min_return=args.min_return,
    )

    # 写入信号
    written = matcher.write_signals(qualified, dry_run=args.dry_run)

    # 报告
    report = matcher.generate_report(
        all_results, qualified, error_pairs,
        min_win_rate=args.min_win_rate,
        min_return=args.min_return,
        days=args.days,
    )
    print(report)
    print(f"总耗时: {elapsed:.1f}s | 写入信号: {written} 条\n")

    return 0 if qualified else 1


if __name__ == '__main__':
    sys.exit(main())
