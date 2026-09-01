"""
ML置信过滤层

角色：只做否决，不做选股。
A股：XGBoost + LightGBM 双模型融合
港股：仅 XGBoost
"""
from dataclasses import dataclass
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class MLVote:
    verdict: str  # buy / hold / sell
    confidence: float  # 0-1
    position_adjustment: float = 1.0  # 仓位调整系数


class MLFilter:
    """ML置信过滤"""

    CONFIDENCE_THRESHOLD = 0.65
    MIN_PASS_RATE = 0.40  # 最低通过率，低于此值暂停ML层

    def __init__(self, market: str = "A", confidence_threshold: float = None):
        self.market = market
        self.confidence_threshold = confidence_threshold or self.CONFIDENCE_THRESHOLD
        self.use_dual_model = (market == "A")

    @staticmethod
    def fuse_signals(
        xgb_signal: str,
        lgb_signal: str,
        xgb_confidence: float,
        lgb_confidence: float
    ) -> MLVote:
        """
        XGBoost + LightGBM 双模型融合规则

        ┌──────────┬───────────┬────────────────────────┐
        │ XGBoost  │ LightGBM  │ 判定                    │
        ├──────────┼───────────┼────────────────────────┤
        │ buy      │ buy       │ buy (置信度取均值)       │
        │ buy      │ hold      │ buy (仓位打8折)          │
        │ hold     │ buy       │ buy (仓位打8折)          │
        │ buy      │ sell      │ hold (冲突剔除)          │
        │ hold/sell│ hold/sell │ hold/sell               │
        └──────────┴───────────┴────────────────────────┘
        """
        avg_confidence = (xgb_confidence + lgb_confidence) / 2

        if xgb_signal.upper() == "BUY" and lgb_signal.upper() == "BUY":
            return MLVote("buy", avg_confidence, 1.0)

        if (xgb_signal.upper() == "BUY" and lgb_signal == "hold") or \
           (xgb_signal == "hold" and lgb_signal.upper() == "BUY"):
            return MLVote("buy", avg_confidence, 0.8)

        if xgb_signal.upper() == "SELL" or lgb_signal.upper() == "SELL":
            return MLVote("hold", avg_confidence, 1.0)

        return MLVote("hold", avg_confidence, 1.0)

    def process_single_model(self, signal: str, confidence: float) -> MLVote:
        """港股单模型处理"""
        return MLVote(
            verdict=signal if signal in ("buy", "hold", "sell") else "hold",
            confidence=confidence,
            position_adjustment=1.0
        )

    def passes(self, vote: MLVote) -> bool:
        """判断是否通过过滤"""
        return vote.verdict.upper() == "BUY" and vote.confidence >= self.confidence_threshold

    def filter(
        self,
        candidates: List[str],
        predictions: Dict[str, Dict]
    ) -> List[str]:
        """过滤候选股票。"""
        passed = []
        votes = []

        for symbol in candidates:
            pred = predictions.get(symbol, {})

            if self.use_dual_model:
                xgb_signal = pred.get("xgb_signal", "hold")
                xgb_conf = pred.get("xgb_confidence", 0.5)
                lgb_signal = pred.get("lgb_signal", "hold")
                lgb_conf = pred.get("lgb_confidence", 0.5)
                vote = self.fuse_signals(xgb_signal, lgb_signal, xgb_conf, lgb_conf)
            else:
                signal = pred.get("xgb_signal", "hold")
                conf = pred.get("xgb_confidence", 0.5)
                vote = self.process_single_model(signal, conf)

            votes.append(vote)

            if self.passes(vote):
                passed.append(symbol)
                logger.debug(f"ML通过: {symbol}, verdict={vote.verdict}, conf={vote.confidence:.2f}")

        pass_rate = self.check_pass_rate(votes)
        if pass_rate < self.MIN_PASS_RATE:
            logger.warning(
                f"ML通过率仅 {pass_rate:.0%}，低于阈值 {self.MIN_PASS_RATE:.0%}，"
                f"建议暂停ML层使用"
            )

        return passed

    def check_pass_rate(self, votes: List[MLVote]) -> float:
        """计算通过率"""
        if not votes:
            return 0.0
        passed = sum(1 for v in votes if self.passes(v))
        return passed / len(votes)
