"""
基准对比计算（沪深300）

把"我赚了 1.25%"变成"我赚了 1.25%，同期沪深300 +2.3%，跑输 1.05%"——
没有标尺的盈利是自欺。

单位契约：所有收益率字段均为小数比率（0.0123 = 1.23%），
与后端 profit_total_rate / cumulative_return 口径一致；展示层负责 ×100。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# alpha/beta/sharpe 需要的最少对齐交易日
MIN_ALIGNED_DAYS_FOR_METRICS = 5

# (date_str, daily_return, total_value)，按日期升序
AccountSeries = Sequence[Tuple[str, float, float]]
# akshare stock_zh_index_daily 记录：{'date': 'YYYY-MM-DD', 'close': ...}
BenchmarkKlines = Sequence[Dict[str, Any]]


def _benchmark_daily_returns(klines: BenchmarkKlines) -> Dict[str, float]:
    """从基准K线计算 {date: 当日收益率}（当日 = close/prev_close - 1）"""
    rows = sorted(
        (str(k["date"])[:10], float(k["close"])) for k in klines
        if k.get("date") and k.get("close")
    )
    returns: Dict[str, float] = {}
    for i in range(1, len(rows)):
        prev_close = rows[i - 1][1]
        if prev_close > 0:
            returns[rows[i][0]] = rows[i][1] / prev_close - 1
    return returns


def compute_benchmark_comparison(
    account_series: AccountSeries,
    benchmark_klines: BenchmarkKlines,
) -> Optional[Dict[str, Any]]:
    """
    计算账户收益与基准的对比指标。

    Args:
        account_series: [(date, daily_return, total_value)] 按日期升序
        benchmark_klines: 基准指数日K记录（无需有序）

    Returns:
        None（无重叠交易日）或指标字典：
        - benchmark_return_1m / account_return_1m / excess_return_1m：区间收益率（小数）
        - alpha / beta / sharpe：对齐交易日 ≥5 时给出，否则 None
        - aligned_days：对齐的交易日数
    """
    if not account_series or not benchmark_klines:
        return None

    bench_returns = _benchmark_daily_returns(benchmark_klines)
    if not bench_returns:
        return None

    # 对齐：账户收益日期 ∩ 基准收益日期
    aligned_account: List[float] = []
    aligned_bench: List[float] = []
    for date_str, daily_return, _ in account_series:
        if date_str in bench_returns:
            aligned_account.append(float(daily_return or 0))
            aligned_bench.append(bench_returns[date_str])

    if not aligned_account:
        return None

    # 区间收益率：账户用日收益复利（快照首行已含当日收益，不能用首末净值比），
    # 基准用窗口首末收盘比
    account_return = math.prod(1 + float(r or 0) for _, r, _ in account_series) - 1

    closes = sorted(
        (str(k["date"])[:10], float(k["close"])) for k in benchmark_klines
        if k.get("date") and k.get("close")
    )
    window_start = account_series[0][0]
    window_end = account_series[-1][0]
    window_closes = [(d, c) for d, c in closes if window_start <= d <= window_end]
    if len(window_closes) >= 2 and window_closes[0][1] > 0:
        benchmark_return = window_closes[-1][1] / window_closes[0][1] - 1
    elif aligned_bench:
        benchmark_return = math.prod(1 + r for r in aligned_bench) - 1
    else:
        benchmark_return = 0.0

    alpha = beta = sharpe = None
    if len(aligned_account) >= MIN_ALIGNED_DAYS_FOR_METRICS:
        n = len(aligned_account)
        mean_a = sum(aligned_account) / n
        mean_b = sum(aligned_bench) / n
        var_b = sum((r - mean_b) ** 2 for r in aligned_bench) / n
        if var_b > 0:
            cov_ab = sum((a - mean_a) * (b - mean_b) for a, b in zip(aligned_account, aligned_bench)) / n
            beta = cov_ab / var_b
            alpha = (mean_a - beta * mean_b) * 252  # 年化
        std_a = math.sqrt(sum((r - mean_a) ** 2 for r in aligned_account) / n)
        if std_a > 0:
            sharpe = mean_a / std_a * math.sqrt(252)

    return {
        "account_return_1m": round(account_return, 6),
        "benchmark_return_1m": round(benchmark_return, 6),
        "excess_return_1m": round(account_return - benchmark_return, 6),
        "alpha": round(alpha, 4) if alpha is not None else None,
        "beta": round(beta, 4) if beta is not None else None,
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "aligned_days": len(aligned_account),
    }


# ==================== 基准数据获取（带日级缓存） ====================

_klines_cache: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}


def fetch_benchmark_klines(
    symbol: str = "sh000300",
    start_date: str = "",
    end_date: str = "",
) -> List[Dict[str, Any]]:
    """
    拉取基准指数K线（带当日缓存，避免每次查仓都访问 akshare）。
    失败时返回空列表并记 warning（调用方应降级为无基准，而不是报错）。
    """
    from datetime import date as _date

    cache_key = f"{symbol}|{start_date}|{end_date}"
    today = _date.today().isoformat()
    cached = _klines_cache.get(cache_key)
    if cached and cached[0] == today:
        return cached[1]

    try:
        from application.services.market_data_service import MarketDataService
        result = MarketDataService().get_index_history(symbol, start_date, end_date)
        if result.get("success") and result.get("data"):
            klines = result["data"].get("klines") or []
            _klines_cache[cache_key] = (today, klines)
            return klines
        logger.warning(f"基准指数获取失败: {result.get('error')}")
    except Exception as e:
        logger.warning(f"基准指数获取异常（降级为无基准）: {e}")
    return []
