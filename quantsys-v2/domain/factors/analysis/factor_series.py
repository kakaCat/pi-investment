"""因子值序列计算（/api/portfolio/factor-analyze 专用，2026-11-10 P0.1）

历史事故：旧 factor_analyze 端点把任意因子名都映射到同一个 20 日动量代理
（"momentum as factor proxy"），导致 MACD/RSI/PE/ROE 返回完全相同的 IC，
且返回 success=true 伪装有效。本模块的要求：

1. 每个因子名有且仅有自己的真实计算路径；
2. 未支持的因子返回 None，由调用方诚实降级，禁止用代理值冒充；
3. 门禁测试：tests/services/test_factor_series.py 断言不同因子产出不同序列。

所有函数输入单票日K DataFrame（按日期升序，至少含 close；volume_ratio 需 volume），
输出与输入等长的 pd.Series（前 N 个 warmup 位置为 NaN，属正常）。
"""


def compute_factor_series(df, factor_name):
    """按因子名计算因子值序列；未支持因子返回 None（诚实降级）。"""
    close = df['close'].astype(float)
    name = (factor_name or '').lower()

    if name in ('rsi', 'rsi14'):
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        return 100 - 100 / (1 + gain / (loss + 1e-12))

    if name in ('macd', 'macd_hist', 'dif'):
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        return dif - dea  # MACD 柱：>0 多方占优，金叉当日由负转正

    if name in ('momentum', 'mom', 'mom20'):
        return close / close.shift(20) - 1

    if name in ('volatility', 'vol20'):
        return close.pct_change().rolling(20).std()

    if name in ('ma_bias', 'bias', 'bias20'):
        return close / close.rolling(20).mean() - 1

    if name in ('volume_ratio', 'vol_ratio'):
        if 'volume' not in df.columns:
            return None
        vol = df['volume'].astype(float)
        return vol / vol.rolling(20).mean()

    return None
