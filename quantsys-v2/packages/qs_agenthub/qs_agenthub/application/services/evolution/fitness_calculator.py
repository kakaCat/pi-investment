"""双侧捕获适应度纯计算（agent 行为进化 Phase 1 核心）

fitness = up_capture − down_capture：
- up_capture  = 大盘涨日账户平均日收益 / 大盘涨日平均收益（跟上/超越 → ≥1）
- down_capture = 大盘跌日账户平均日收益 / 大盘跌日平均收益
  （分母为负：亏得少 → 比值趋 0 或转负 → 越小越好）

单位契约：收益率均为小数比率（0.0123 = 1.23%）。纯函数，不碰 DB/网络，便于合成行情测试。
"""
from typing import Any, Dict, Mapping

SIDEWAYS_THRESHOLD = 0.003  # 沪深300 日收益 |r| < 0.3% 为横盘日，剔除
MIN_SAMPLE_DAYS = 5         # 涨/跌样本任一侧不足则 insufficient_sample


def compute_capture(
    account_returns: Mapping[str, float],
    bench_returns: Mapping[str, float],
    has_trades: bool,
) -> Dict[str, Any]:
    """
    Args:
        account_returns: {date_str: 账户日收益}（窗口内，可缺日）
        bench_returns:   {date_str: 基准日收益}（窗口内）
        has_trades:      窗口内账户是否有交易（False → no_trades，防空仓虚高分）

    Returns:
        {up_capture, down_capture, fitness, up_days, down_days, status}
        status: ok / insufficient_sample / no_trades；
        非 ok 时 fitness/up_capture/down_capture 均为 None。
    """
    up_acct, up_bench, down_acct, down_bench = [], [], [], []
    for date_str, bench_r in bench_returns.items():
        if date_str not in account_returns:
            continue  # snapshot 缺日：跳过（样本计数随之减少）
        if bench_r >= SIDEWAYS_THRESHOLD:
            up_bench.append(bench_r)
            up_acct.append(float(account_returns[date_str] or 0))
        elif bench_r <= -SIDEWAYS_THRESHOLD:
            down_bench.append(bench_r)
            down_acct.append(float(account_returns[date_str] or 0))

    up_days, down_days = len(up_bench), len(down_bench)

    if not has_trades:
        return {'up_capture': None, 'down_capture': None, 'fitness': None,
                'up_days': up_days, 'down_days': down_days, 'status': 'no_trades'}
    if up_days < MIN_SAMPLE_DAYS or down_days < MIN_SAMPLE_DAYS:
        return {'up_capture': None, 'down_capture': None, 'fitness': None,
                'up_days': up_days, 'down_days': down_days,
                'status': 'insufficient_sample'}

    up_capture = (sum(up_acct) / up_days) / (sum(up_bench) / up_days)
    down_capture = (sum(down_acct) / down_days) / (sum(down_bench) / down_days)
    return {
        'up_capture': round(up_capture, 4),
        'down_capture': round(down_capture, 4),
        'fitness': round(up_capture - down_capture, 4),
        'up_days': up_days,
        'down_days': down_days,
        'status': 'ok',
    }
