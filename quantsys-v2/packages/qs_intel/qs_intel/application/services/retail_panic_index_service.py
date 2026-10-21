"""M7-2 散户恐慌代理指标服务

从多个可观测代理维度合成**连续 0-100 的散户恐慌指数**，替代离散三档
（panic_selling/fomo_buying/neutral 的 20/50/80 跳变）：

维度（各给出 0-100 恐慌分，合成时加权）：
1. 散户资金流（小单+中单净流入，越流出越恐慌）
2. 涨跌家数比（ad_ratio，普跌=恐慌）
3. 量能状态（volume_ratio，缩量阴跌/放量下跌）
4. 恐慌贪婪指数（fear_greed_index，越低越恐慌）
5. 波动率（volatility 高位=不安）

设计约束（沿用 RFC 007 风格）：
- 落库走 ORM Repository（MarketSentimentDailyRepository / FundFlowORMRepository）
- 不造数据：数据源不可用时显式降级并在返回中标记
- 供 M7-2 验收 + opponent_behavior 的散户行为细化（未来）
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# ------------------------------------------------------------------
# 合成权重（可调，不改表结构）
# ------------------------------------------------------------------
W_FLOW = 0.30        # 散户资金流
W_AD = 0.25          # 涨跌家数比
W_VOLUME = 0.15      # 量能
W_FEAR_GREED = 0.20  # 恐慌贪婪指数
W_VOLATILITY = 0.10  # 波动率

FLOW_PANIC_THRESHOLD_YI = -30.0    # 散户净流出 30 亿视为恐慌满档
FLOW_GREED_THRESHOLD_YI = 30.0     # 净流入 30 亿视为贪婪满档
AD_PANIC = 0.6                     # 涨跌比 ≤0.6 恐慌满档
AD_GREED = 2.0                     # 涨跌比 ≥2.0 贪婪满档
VOL_PANIC = 2.5                    # 波动率 ≥2.5% 恐慌满档（%）


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class RetailPanicIndexService:
    """散户恐慌代理指标：合成连续恐慌指数 + 区间查询。"""

    def __init__(
        self,
        sentiment_repo=None,
        fund_flow_repo=None,
    ):
        if sentiment_repo is None:
            from adapters.outbound.repositories import MarketSentimentDailyRepository
            sentiment_repo = MarketSentimentDailyRepository()
        if fund_flow_repo is None:
            from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository
            fund_flow_repo = FundFlowORMRepository()
        self.sentiment_repo = sentiment_repo
        self.fund_flow_repo = fund_flow_repo

    # ------------------------------------------------------------------
    # 各维度恐慌分
    # ------------------------------------------------------------------
    def _flow_score(self, trade_date: str) -> Optional[float]:
        """散户资金流恐慌分：净流出越多 → 恐慌分越高（0-100）。"""
        try:
            flows = self.fund_flow_repo.get_market_aggregate_flow(trade_date, trade_date)
            if not flows:
                return None
            retail_yi = (
                (flows[0].get('total_small_flow') or 0)
                + (flows[0].get('total_medium_flow') or 0)
            ) / 10000  # 万元 → 亿
            # 流出→恐慌：-30亿=100分；流入→贪婪：+30亿=0分
            return round(_clip01((FLOW_GREED_THRESHOLD_YI - retail_yi) / (FLOW_GREED_THRESHOLD_YI - FLOW_PANIC_THRESHOLD_YI)) * 100, 1)
        except Exception as e:
            logger.warning(f"flow_score 失败: {e}")
            return None

    def _ad_score(self, ad_ratio: Optional[float]) -> Optional[float]:
        """涨跌家数比恐慌分：普跌(≤0.6)=100，普涨(≥2.0)=0。"""
        if ad_ratio is None:
            return None
        return round(_clip01((AD_GREED - ad_ratio) / (AD_GREED - AD_PANIC)) * 100, 1)

    def _volume_score(self, volume_ratio: Optional[float]) -> Optional[float]:
        """量能恐慌分：放量下跌(高量比+恐慌贪婪低)已由 fg 捕捉；
        这里缩量(低量比)轻微加分——地量阴跌=人气涣散，恐慌分略升。"""
        if volume_ratio is None:
            return None
        # 0.5 以下地量 +10，正常 1.0 附近 0 分，放量不直接算恐慌（要看方向）
        if volume_ratio < 0.5:
            return round((0.5 - volume_ratio) * 40, 1)
        return 0.0

    def _fg_score(self, fear_greed: Optional[float]) -> Optional[float]:
        """恐慌贪婪指数恐慌分：fg 越低越恐慌 → 恐慌分 = 100 - fg。"""
        if fear_greed is None:
            return None
        return round(_clip01((100 - fear_greed) / 100) * 100, 1)

    def _volatility_score(self, volatility: Optional[float]) -> Optional[float]:
        """波动率恐慌分：≥2.5%=100，≤0.8%=0。"""
        if volatility is None:
            return None
        return round(_clip01((volatility - 0.8) / (VOL_PANIC - 0.8)) * 100, 1)

    # ------------------------------------------------------------------
    # 合成
    # ------------------------------------------------------------------
    def compute_index(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """合成指定交易日（默认最近一日）的散户恐慌指数。"""
        trade_date = trade_date or datetime.now().strftime('%Y-%m-%d')
        try:
            sent = self.sentiment_repo.get_by_date(trade_date) \
                if hasattr(self.sentiment_repo, 'get_by_date') else None
            if sent is None:
                # 当日无数据 → 取最近一日
                recent = self.sentiment_repo.get_recent(1)
                if not recent:
                    return {
                        'trade_date': trade_date,
                        'panic_index': None,
                        'level': 'unknown',
                        'degraded': True,
                        'reason': 'market_sentiment_daily 无数据（等待每日采集）',
                        'dimensions': {},
                    }
                sent = recent[0]
                trade_date = str(sent.trade_date)

            flow = self._flow_score(trade_date)
            ad = self._ad_score(float(sent.ad_ratio) if sent.ad_ratio is not None else None)
            vol_ratio = float(sent.volume_ratio) if sent.volume_ratio is not None else None
            fg = float(sent.fear_greed_index) if sent.fear_greed_index is not None else None
            vol = float(sent.volatility) if sent.volatility is not None else None

            # 散户资金流原始值（亿，用于展示）
            retail_flow_yi = None
            try:
                flows = self.fund_flow_repo.get_market_aggregate_flow(trade_date, trade_date)
                if flows:
                    retail_flow_yi = round(
                        ((flows[0].get('total_small_flow') or 0)
                         + (flows[0].get('total_medium_flow') or 0)) / 10000, 1)
            except Exception:
                pass

            dims: Dict[str, Any] = {
                'retail_flow_score': flow,
                'ad_ratio_score': ad,
                'volume_score': self._volume_score(vol_ratio),
                'fear_greed_score': self._fg_score(fg),
                'volatility_score': self._volatility_score(vol),
                '_raw': {
                    'retail_flow_yi': retail_flow_yi,
                    'ad_ratio': sent.ad_ratio,
                    'volume_ratio': vol_ratio,
                    'fear_greed_index': fg,
                    'volatility': vol,
                },
            }

            # 加权合成（缺失维度按剩余权重归一）
            weights = {'retail_flow_score': W_FLOW, 'ad_ratio_score': W_AD,
                       'volume_score': W_VOLUME, 'fear_greed_score': W_FEAR_GREED,
                       'volatility_score': W_VOLATILITY}
            total_w, acc = 0.0, 0.0
            for key, w in weights.items():
                v = dims[key]
                if v is not None:
                    acc += v * w
                    total_w += w
            if total_w == 0:
                return {
                    'trade_date': trade_date, 'panic_index': None,
                    'level': 'unknown', 'degraded': True,
                    'reason': '无任何可用维度', 'dimensions': dims,
                }
            panic_index = round(acc / total_w, 1)
            level = self._classify(panic_index)

            return {
                'trade_date': trade_date,
                'panic_index': panic_index,
                'level': level,
                'degraded': False,
                'dimensions': {k: v for k, v in dims.items() if k != '_raw'},
                'raw': dims['_raw'],
            }
        except Exception as e:
            logger.error(f"compute panic index 失败: {e}", exc_info=True)
            return {
                'trade_date': trade_date, 'panic_index': None,
                'level': 'unknown', 'degraded': True,
                'reason': str(e), 'dimensions': {},
            }

    @staticmethod
    def _classify(panic_index: float) -> str:
        """恐慌等级：≥70 恐慌 / 50-70 偏恐慌 / 30-50 偏贪婪 / <30 贪婪。"""
        if panic_index >= 70:
            return 'panic'
        if panic_index >= 50:
            return 'leaning_panic'
        if panic_index >= 30:
            return 'leaning_greed'
        return 'greed'

    def series(self, days: int = 20) -> List[Dict[str, Any]]:
        """最近 N 日恐慌指数序列。"""
        recent = self.sentiment_repo.get_recent(days)
        out = []
        for sent in reversed(recent):
            d = self.compute_index(str(sent.trade_date))
            out.append(d)
        return out
