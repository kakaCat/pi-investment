"""
策略发现引擎 (Strategy Discovery Engine)

核心功能：
- 给定标的池，自动生成多种策略变体
- 批量优化参数 → 批量回测验证 → 排序排名
- 输出：哪些策略思路在哪些股票上有效

架构：
  Archetype Templates → Strategy Creation → Optimize → Batch Backtest → Rank

使用方式：
  service = StrategyDiscoveryService()
  report = service.run(symbols=["600900", "600025"], ...)
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import structlog
import time

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Strategy Archetype Templates
# ═══════════════════════════════════════════════════════════════

@dataclass
class StrategyArchetype:
    """策略原型模板"""
    name: str
    description: str
    category: str  # 'trend', 'reversal', 'breakout', 'volume'
    code: str      # indicator code with @param annotations
    param_grid: Dict[str, List[Any]]  # 搜索空间


# 模板定义：5 大核心策略思路
STRATEGY_ARCHETYPES: List[StrategyArchetype] = [
    StrategyArchetype(
        name="RSI均值回归",
        description="RSI超卖买入，超买卖出。适合震荡行情。",
        category="reversal",
        code='''my_indicator_name = "Discovery-RSI"
# @param rsi_low int 35 RSI超卖阈值
# @param rsi_high int 65 RSI超买阈值
# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.15
# @strategy entryPct 1.0

d = df["close"].diff()
g = d.where(d > 0, 0).rolling(14).mean()
l = (-d).where(d < 0, 0).rolling(14).mean()
df["rsi"] = 100 - (100 / (1 + g / l.replace(0, pd.NA)))

df["buy"] = (df["rsi"] < rsi_low) & (df["rsi"].shift(1) >= rsi_low)
df["sell"] = df["rsi"] > rsi_high
''',
        param_grid={
            "rsi_low": [30, 35, 40],
            "rsi_high": [60, 65, 70],
        }
    ),
    StrategyArchetype(
        name="MA金叉死叉",
        description="均线金叉买入，死叉卖出。适合趋势行情。",
        category="trend",
        code='''my_indicator_name = "Discovery-MA"
# @param ma_fast int 5 快线周期
# @param ma_slow int 20 慢线周期
# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.15
# @strategy entryPct 1.0

df["ma_fast"] = df["close"].rolling(ma_fast).mean()
df["ma_slow"] = df["close"].rolling(ma_slow).mean()

golden = (df["ma_fast"] > df["ma_slow"]) & (df["ma_fast"].shift(1) <= df["ma_slow"].shift(1))
dead = (df["ma_fast"] < df["ma_slow"]) & (df["ma_fast"].shift(1) >= df["ma_slow"].shift(1))

df["buy"] = golden
df["sell"] = dead
''',
        param_grid={
            "ma_fast": [5, 10, 20],
            "ma_slow": [20, 30, 60],
        }
    ),
    StrategyArchetype(
        name="MACD信号",
        description="MACD金叉买入，死叉卖出。经典趋势策略。",
        category="trend",
        code='''my_indicator_name = "Discovery-MACD"
# @param macd_fast int 12 快EMA周期
# @param macd_slow int 26 慢EMA周期
# @param macd_signal int 9 信号线周期
# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.15
# @strategy entryPct 1.0

ef = df["close"].ewm(span=macd_fast, adjust=False).mean()
es = df["close"].ewm(span=macd_slow, adjust=False).mean()
df["dif"] = ef - es
df["dea"] = df["dif"].ewm(span=macd_signal, adjust=False).mean()

golden = (df["dif"] > df["dea"]) & (df["dif"].shift(1) <= df["dea"].shift(1))
dead = (df["dif"] < df["dea"]) & (df["dif"].shift(1) >= df["dea"].shift(1))

df["buy"] = golden
df["sell"] = dead
''',
        param_grid={
            "macd_fast": [8, 12, 16],
            "macd_slow": [21, 26, 31],
            "macd_signal": [7, 9, 12],
        }
    ),
    StrategyArchetype(
        name="布林带回归",
        description="价格触及布林下轨买入，触及上轨卖出。适合均值回归场景。",
        category="reversal",
        code='''my_indicator_name = "Discovery-BB"
# @param bb_period int 20 布林带周期
# @param bb_std float 2.0 标准差倍数
# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.15
# @strategy entryPct 1.0

df["bb_mid"] = df["close"].rolling(bb_period).mean()
bb_std = df["close"].rolling(bb_period).std()
df["bb_lower"] = df["bb_mid"] - bb_std * bb_std
df["bb_upper"] = df["bb_mid"] + bb_std * bb_std

df["buy"] = df["close"] <= df["bb_lower"] * 1.02
df["sell"] = df["close"] >= df["bb_upper"] * 0.98
''',
        param_grid={
            "bb_period": [14, 20, 26],
            "bb_std": [1.5, 2.0, 2.5],
        }
    ),
    StrategyArchetype(
        name="量价突破",
        description="放量突破MA20买入，缩量跌破MA20卖出。适合有量能配合的趋势。",
        category="volume",
        code='''my_indicator_name = "Discovery-VOL"
# @param ma_period int 20 均线周期
# @param vol_ratio float 1.5 放量倍数
# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.15
# @strategy entryPct 1.0

df["ma"] = df["close"].rolling(ma_period).mean()
df["vma"] = df["volume"].rolling(ma_period).mean()

# 放量突破
breakout = (df["close"] > df["ma"]) & (df["close"].shift(1) <= df["ma"].shift(1)) & (df["volume"] > df["vma"] * vol_ratio)
# 缩量跌破
breakdown = (df["close"] < df["ma"]) & (df["volume"] < df["vma"] * 0.7)

df["buy"] = breakout
df["sell"] = breakdown
''',
        param_grid={
            "ma_period": [10, 20, 30],
            "vol_ratio": [1.2, 1.5, 2.0],
        }
    ),
]


# ═══════════════════════════════════════════════════════════════
# Discovery Engine
# ═══════════════════════════════════════════════════════════════

@dataclass
class DiscoveryResult:
    """单个策略 × 股票的发现结果"""
    archetype: str
    symbol: str
    symbol_name: str
    best_params: Dict[str, Any]
    best_score: float
    metric: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    strategy_id: int
    total_combinations: int
    successful: int
    elapsed_seconds: float


@dataclass
class DiscoveryReport:
    """完整发现报告"""
    run_id: str
    symbols: List[str]
    metric: str
    start_date: str
    end_date: str
    results: List[DiscoveryResult] = field(default_factory=list)
    archetypes_tested: int = 0
    total_combinations_tested: int = 0
    total_elapsed_seconds: float = 0.0
    errors: List[Dict] = field(default_factory=list)

    def get_top_by_archetype(self, top_n: int = 3) -> Dict[str, List[DiscoveryResult]]:
        """按策略原型分组，每组取 top_n"""
        by_archetype: Dict[str, List[DiscoveryResult]] = {}
        for r in sorted(self.results, key=lambda x: x.best_score, reverse=True):
            if r.archetype not in by_archetype:
                by_archetype[r.archetype] = []
            by_archetype[r.archetype].append(r)
        return {k: v[:top_n] for k, v in by_archetype.items()}

    def get_overall_top(self, top_n: int = 10) -> List[DiscoveryResult]:
        """全局排名"""
        return sorted(self.results, key=lambda x: x.best_score, reverse=True)[:top_n]

    def get_archetype_summary(self) -> List[Dict]:
        """每个策略原型的聚合统计"""
        by_arch: Dict[str, List[DiscoveryResult]] = {}
        for r in self.results:
            if r.archetype not in by_arch:
                by_arch[r.archetype] = []
            by_arch[r.archetype].append(r)

        summaries = []
        for arch_name, items in by_arch.items():
            scores = [it.best_score for it in items]
            returns = [it.total_return for it in items]
            sharpes = [it.sharpe_ratio for it in items]
            win_rates = [it.win_rate for it in items]
            n = len(items)

            summaries.append({
                "archetype": arch_name,
                "tested_on_stocks": n,
                "profitable_count": sum(1 for r in returns if r > 0),
                "avg_best_score": round(sum(scores) / n, 4),
                "avg_return": round(sum(returns) / n, 4),
                "avg_sharpe": round(sum(sharpes) / n, 4),
                "avg_win_rate": round(sum(win_rates) / n, 4),
                "best_score": round(max(scores), 4),
                "best_stock": items[scores.index(max(scores))].symbol,
                "worst_score": round(min(scores), 4),
            })

        return sorted(summaries, key=lambda x: x["avg_best_score"], reverse=True)

    def to_dict(self) -> Dict:
        """转为可序列化的字典"""
        return {
            "run_id": self.run_id,
            "symbols": self.symbols,
            "metric": self.metric,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "archetypes_tested": self.archetypes_tested,
            "total_combinations_tested": self.total_combinations_tested,
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 1),
            "archetype_summary": self.get_archetype_summary(),
            "overall_top10": [
                {
                    "archetype": r.archetype,
                    "symbol": r.symbol,
                    "symbol_name": r.symbol_name,
                    "best_params": r.best_params,
                    "best_score": r.best_score,
                    "total_return": r.total_return,
                    "sharpe_ratio": r.sharpe_ratio,
                    "max_drawdown": r.max_drawdown,
                    "win_rate": r.win_rate,
                    "total_trades": r.total_trades,
                    "strategy_id": r.strategy_id,
                    "combinations_tested": r.total_combinations,
                    "elapsed_seconds": round(r.elapsed_seconds, 1),
                }
                for r in self.get_overall_top(10)
            ],
            "all_results": [
                {
                    "archetype": r.archetype,
                    "symbol": r.symbol,
                    "symbol_name": r.symbol_name,
                    "best_params": r.best_params,
                    "best_score": r.best_score,
                    "total_return": r.total_return,
                    "sharpe_ratio": r.sharpe_ratio,
                    "max_drawdown": r.max_drawdown,
                    "win_rate": r.win_rate,
                }
                for r in self.results
            ],
            "errors": self.errors,
        }


class StrategyDiscoveryService:
    """策略发现引擎"""

    def __init__(self):
        self._archetypes = STRATEGY_ARCHETYPES

    def run(
        self,
        symbols: List[str],
        start_date: str = "2023-01-01",
        end_date: str = "2025-12-31",
        metric: str = "sharpe",
        max_combinations: int = 30,
        archery_filter: Optional[List[str]] = None,
    ) -> DiscoveryReport:
        """
        运行策略发现流水线。

        Args:
            symbols: 股票代码列表（如 ['600900', '600025']）
            start_date: 优化训练的起始日期
            end_date: 优化训练的结束日期  
            metric: 优化目标（sharpe / return / win_rate）
            max_combinations: 每个原型的最大参数组合数
            archery_filter: 只测试指定原型（None=全部）

        Returns:
            DiscoveryReport
        """
        import uuid
        from application.services.strategy_code_service import StrategyCodeService
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import itertools

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        report = DiscoveryReport(
            run_id=run_id,
            symbols=symbols,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
        )

        service = StrategyCodeService()
        t_start = time.time()

        # 过滤原型
        archetypes = self._archetypes
        if archery_filter:
            archetypes = [a for a in archetypes if a.name in archery_filter]
        report.archetypes_tested = len(archetypes)

        # 收集所有 (archetype, symbol) 任务
        tasks = []
        for arch in archetypes:
            for symbol in symbols:
                tasks.append((arch, symbol))

        logger.info(
            f"策略发现开始: run_id={run_id}, "
            f"archetypes={len(archetypes)}, symbols={len(symbols)}, "
            f"total_tasks={len(tasks)}"
        )

        # 并发执行（每个任务内部：创建策略 → 网格搜索优化）
        with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
            futures = {
                executor.submit(
                    self._discover_single,
                    service, arch, symbol,
                    start_date, end_date, metric, max_combinations
                ): (arch, symbol)
                for arch, symbol in tasks
            }

            for future in as_completed(futures):
                arch, symbol = futures[future]
                try:
                    result = future.result(timeout=600)  # 10分钟超时
                    if result:
                        report.results.append(result)
                except Exception as e:
                    err_msg = f"{arch.name} × {symbol}: {str(e)}"
                    logger.error(f"发现任务失败: {err_msg}", exc_info=True)
                    report.errors.append({
                        "archetype": arch.name,
                        "symbol": symbol,
                        "error": err_msg,
                    })

        report.total_elapsed_seconds = time.time() - t_start
        report.total_combinations_tested = sum(
            r.total_combinations for r in report.results
        )

        logger.info(
            f"策略发现完成: run_id={run_id}, "
            f"results={len(report.results)}, errors={len(report.errors)}, "
            f"elapsed={report.total_elapsed_seconds:.1f}s"
        )

        return report

    def _discover_single(
        self,
        service,
        arch: StrategyArchetype,
        symbol: str,
        start_date: str,
        end_date: str,
        metric: str,
        max_combinations: int,
    ) -> Optional[DiscoveryResult]:
        """
        对单个 (archetype, symbol) 执行发现：
        1. 创建策略
        2. 运行参数优化（网格搜索）
        3. 返回最优结果
        """
        import itertools

        t0 = time.time()

        # 1. 创建策略
        strategy_name = f"DISCOVERY-{arch.name}-{symbol}"
        creation = service.create_strategy(
            name=strategy_name,
            code=arch.code,
            code_type="indicator",
            description=f"[自动发现] {arch.description} | 标的: {symbol}",
            category="discovery",
        )
        strategy_id = creation["strategy_id"]
        logger.info(f"  [{arch.name}] 创建策略 ID={strategy_id} for {symbol}")

        # 2. 生成参数组合
        param_names = list(arch.param_grid.keys())
        param_values = [arch.param_grid[name] for name in param_names]
        combinations = list(itertools.product(*param_values))
        total_combinations = len(combinations)

        if total_combinations > max_combinations:
            logger.warning(
                f"  [{arch.name}] 参数组合 {total_combinations} > {max_combinations}，截断至前 {max_combinations} 组"
            )
            combinations = combinations[:max_combinations]
            total_combinations = len(combinations)

        # 3. 逐个测试所有参数组合
        results = []
        for idx, combo in enumerate(combinations):
            params_dict = dict(zip(param_names, combo))
            try:
                bt_result = service.backtest_strategy(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=100000,
                    params_override=params_dict,
                )

                score_map = {
                    "sharpe": bt_result.get("sharpe_ratio", 0),
                    "return": bt_result.get("total_return", 0),
                    "win_rate": bt_result.get("win_rate", 0),
                    "calmar": bt_result.get("calmar_ratio", 0),
                }
                score = score_map.get(metric, bt_result.get("sharpe_ratio", 0))

                results.append({
                    "params": params_dict,
                    "score": score,
                    "total_return": bt_result["total_return"],
                    "sharpe_ratio": bt_result["sharpe_ratio"],
                    "max_drawdown": bt_result["max_drawdown"],
                    "win_rate": bt_result["win_rate"],
                    "total_trades": bt_result["total_trades"],
                })

                logger.debug(
                    f"  [{arch.name}][{symbol}] 组合 {idx+1}/{total_combinations}: "
                    f"{params_dict} → score={score:.4f}"
                )

            except Exception as e:
                logger.warning(
                    f"  [{arch.name}][{symbol}] 组合 {params_dict} 失败: {e}"
                )
                continue

        elapsed = time.time() - t0

        if not results:
            logger.warning(f"  [{arch.name}][{symbol}] 所有组合都失败了")
            return None

        # 4. 找最优
        best = max(results, key=lambda x: x["score"])
        symbol_name = symbol  # TODO: 从 stock info 获取

        logger.info(
            f"  [{arch.name}][{symbol}] 最优: {best['params']} "
            f"score={best['score']:.4f} return={best['total_return']:.2%} "
            f"sharpe={best['sharpe_ratio']:.2f} "
            f"({len(results)}/{total_combinations} 成功, {elapsed:.1f}s)"
        )

        return DiscoveryResult(
            archetype=arch.name,
            symbol=symbol,
            symbol_name=symbol_name,
            best_params=best["params"],
            best_score=round(best["score"], 4),
            metric=metric,
            total_return=round(best["total_return"], 4),
            sharpe_ratio=round(best["sharpe_ratio"], 4),
            max_drawdown=round(best["max_drawdown"], 4),
            win_rate=round(best["win_rate"], 4),
            total_trades=best["total_trades"],
            strategy_id=strategy_id,
            total_combinations=total_combinations,
            successful=len(results),
            elapsed_seconds=elapsed,
        )

    def list_archetypes(self) -> List[Dict]:
        """列出所有可用的策略原型"""
        return [
            {
                "name": a.name,
                "description": a.description,
                "category": a.category,
                "param_grid_keys": list(a.param_grid.keys()),
                "total_combinations": self._count_combinations(a.param_grid),
            }
            for a in self._archetypes
        ]

    @staticmethod
    def _count_combinations(param_grid: Dict[str, List]) -> int:
        total = 1
        for values in param_grid.values():
            total *= len(values)
        return total
