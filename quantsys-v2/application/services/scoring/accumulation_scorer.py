"""蓄势扫描评分器（accumulation scan，2026-11-10 Phase 2，w-191eb58c）

与 momentum 打分哲学相反：不奖励"已涨"，奖励"压着没涨但在蓄势"。

特征与阈值来自全市场事件研究（5525 只 × 41 采样日，前向 5/10/20 日）：
- 验证条件（validated combo）：vol20 处于自身 120 日低分位(<0.30)
  + 量比<0.8 + |20日动量|<3% + 5日主力净流入>0
- 该组合 5/10/20 日超额 +0.51%/+0.66%/+1.50%（t=2.73/2.67/3.45，胜率 54%+）
- 对照（放量>1.5 且当日涨>3%）显著为负（t=-4.7~-5.8）——追涨组

评分 = 四个子项的连续打分（满分 100），另输出 validated_combo 布尔位：
是否命中验证过的硬组合。排序按总分，决策可只看 validated_combo=True 的子集。
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 验证过的硬组合阈值（事件研究口径，勿拍脑袋调；调整须先回测）
VOL_PCT_THRESHOLD = 0.30    # vol20 在自身 120 日分布中的分位
VOLUME_RATIO_THRESHOLD = 0.8
MOM20_ABS_THRESHOLD = 0.03


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score_one(features: Dict) -> Optional[Dict]:
    """单票蓄势评分。

    features 必填键：vol_pct, volume_ratio, mom20, mf5（5日主力净流入，万元）。
    缺一返回 None（数据不全不打分，诚实降级）。
    """
    vol_pct = features.get('vol_pct')
    vr = features.get('volume_ratio')
    mom20 = features.get('mom20')
    mf5 = features.get('mf5')
    if vol_pct is None or vr is None or mom20 is None or mf5 is None:
        return None

    # 波动压缩（35 分）：分位越低分越高，0.5 以上不得分
    s_vol = _clip((0.5 - vol_pct) / 0.5) * 35
    # 缩量（20 分）：量比 1.2 以上不得分
    s_vr = _clip((1.2 - vr) / 1.2) * 20
    # 趴着（20 分）：|mom20| 6% 以上不得分
    s_mom = _clip((0.06 - abs(mom20)) / 0.06) * 20
    # 资金温和流入（25 分）：mf5>0 起步 15，按规模加分至 25（5000 万封顶）
    s_mf = 0.0
    if mf5 > 0:
        s_mf = 15 + min(10.0, mf5 / 5000.0 * 10)

    total = round(s_vol + s_vr + s_mom + s_mf, 2)
    validated = (
        vol_pct < VOL_PCT_THRESHOLD
        and vr < VOLUME_RATIO_THRESHOLD
        and abs(mom20) < MOM20_ABS_THRESHOLD
        and mf5 > 0
    )
    return {
        'total': total,
        'validated_combo': validated,
        'breakdown': {
            'vol_compression': round(s_vol, 2),
            'shrink_volume': round(s_vr, 2),
            'flat_price': round(s_mom, 2),
            'gentle_inflow': round(s_mf, 2),
        },
        'features': {
            'vol_pct': round(vol_pct, 3),
            'volume_ratio': round(vr, 2),
            'mom20': round(mom20, 4),
            'mf5_wan': round(mf5, 1),
        },
    }


def extract_features(klines: List[Dict], mf5: Optional[float]) -> Optional[Dict]:
    """从单票日K（升序，需 ≥140 根：120 日分位窗口 + 20 日 vol）提取蓄势特征。

    mf5 为 5 日主力净流入合计（万元）；None 表示资金流数据缺失。
    """
    import numpy as np
    import pandas as pd

    if not klines or len(klines) < 140 or mf5 is None:
        return None
    df = pd.DataFrame(klines)
    if 'close' not in df.columns or 'volume' not in df.columns:
        return None
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)

    vol20 = close.pct_change().rolling(20).std()
    window = vol20.iloc[-120:]
    cur = vol20.iloc[-1]
    if np.isnan(cur) or len(window.dropna()) < 60:
        return None
    vol_pct = float((window <= cur).mean())
    vr_series = volume / volume.rolling(20).mean()
    vr = vr_series.iloc[-1]
    mom20 = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else None
    if vr is None or np.isnan(vr) or mom20 is None or np.isnan(mom20):
        return None
    return {'vol_pct': vol_pct, 'volume_ratio': float(vr), 'mom20': mom20, 'mf5': float(mf5)}
