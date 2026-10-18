"""决策打分纯函数（文本参数进化 P0a/P0b）。

口径：超额收益（股票区间收益 − 同期基准收益）归一化到 [-1, 1]，±10% 超额 = 满分。
方向：buy 正向；sell/miss 反向（躲过下跌/正确观望为正，割肉/踏空为负）。
纯函数不碰 DB——判断权在裁判 agent，这里只算数。
"""

FULL_SCORE_EXCESS = 0.10  # ±10% 超额收益对应 ±1 分

DIRECTION = {'buy': 1, 'sell': -1, 'miss': -1}


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
    """决策统一打分。action = 'BUY'|'sell'|'miss'；ref_price 为窗口参考收盘价。

    返回 {'score', 'band', 'excess_return'}，excess_return 为方向调整后的超额。
    非法 action 抛 ValueError（防静默错向打分）。
    """
    if action not in DIRECTION:
        raise ValueError(f'unknown action: {action}')
    stock_return = ref_price / trade_price - 1.0
    excess = (stock_return - bench_return) * DIRECTION[action]
    score = max(-1.0, min(1.0, excess / FULL_SCORE_EXCESS))
    return {
        'score': round(score, 4),
        'band': score_band(score),
        'excess_return': round(excess, 6),
    }
