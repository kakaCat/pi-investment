"""Watch trigger implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CandidateOpportunity:
    """A market event worth asking the agent to judge."""

    symbol: str
    price: float
    quote: dict
    reason: str
    triggered_at: datetime

    @property
    def dedup_key(self) -> str:
        return f"{self.symbol}:{self.reason}"


class StaticThresholdTrigger:
    """Trigger when the latest price reaches a configured symbol threshold."""

    def __init__(self, price_thresholds: dict[str, float]) -> None:
        self.price_thresholds = price_thresholds

    def evaluate(
        self,
        symbol: str,
        quote: dict,
        now: datetime,
    ) -> CandidateOpportunity | None:
        threshold = self.price_thresholds.get(symbol)
        price = float(quote.get("price", 0) or 0)
        if threshold is None or price < threshold:
            return None

        return CandidateOpportunity(
            symbol=symbol,
            price=price,
            quote=quote,
            reason=f"price >= {threshold}",
            triggered_at=now,
        )
