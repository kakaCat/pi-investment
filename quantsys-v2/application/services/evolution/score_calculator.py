"""决策打分纯函数（文本参数进化 P0a，2026-08-07）。

口径：超额收益（股票区间收益 − 同期基准收益）归一化到 [-1, 1]，±10% 超额 = 满分。
卖出方向取反：躲过下跌为正，割肉（卖完反弹）为负。
纯函数不碰 DB——判断权在裁判 agent，这里只算数。
"""

FULL_SCORE_EXCESS = 0.10  # ±10% 超额收益对应 ±1 分


def score_band(score: float) -> str:
    if score >= 0.5:
        return 'big_win'
    if score >= 0.1:
        return 'small_win'
    if score <= -0.5:
        return 'big_loss'
    if score <= -0.1:
        return 'small_loss'
    return 'neutral'


def compute_trade_score(action: str, trade_price: float, ref_price: float,
                        bench_return: float) -> dict:
    """买/卖统一打分。action='buy'|'sell'；ref_price 为窗口参考收盘价。

    返回 {'score', 'band', 'excess_return'}，excess_return 为方向调整后的超额。
    """
    stock_return = ref_price / trade_price - 1.0
    excess = stock_return - bench_return
    if action == 'sell':
        excess = -excess
    score = max(-1.0, min(1.0, excess / FULL_SCORE_EXCESS))
    return {
        'score': round(score, 4),
        'band': score_band(score),
        'excess_return': round(excess, 6),
    }
