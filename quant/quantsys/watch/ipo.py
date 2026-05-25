"""IPO subscription watch pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isnan
from typing import Any, Callable, Protocol

import pandas as pd

try:
    import akshare as ak
except ImportError:
    class _AkShareUnavailable:
        @staticmethod
        def stock_xgsglb_em(**_: Any) -> pd.DataFrame:
            raise ImportError("akshare is required to fetch IPO subscription data")

    ak = _AkShareUnavailable()

from quantsys.watch.agent import AgentDecision, DecisionAgentClient
from quantsys.watch.confirmation import ConfirmationChannel, ConfirmationResult
from quantsys.watch.journal import DecisionRecord, InMemoryDecisionJournal
from quantsys.watch.notifier import FeishuNotifier
from quantsys.watch.trigger import CandidateOpportunity


@dataclass(frozen=True)
class IpoCandidate:
    """One IPO candidate available for subscription."""

    symbol: str
    name: str
    subscription_code: str
    board: str
    exchange: str
    issue_price: float
    subscription_date: date
    subscription_limit: int | None = None
    required_market_value: float | None = None
    issue_pe: float | None = None
    industry_pe: float | None = None
    lottery_announcement_date: date | None = None
    payment_date: date | None = None
    listing_date: date | None = None
    raw: dict[str, Any] | None = None

    def to_opportunity(self, triggered_at: datetime) -> CandidateOpportunity:
        return CandidateOpportunity(
            symbol=self.symbol,
            price=self.issue_price,
            quote={
                "name": self.name,
                "subscription_code": self.subscription_code,
                "board": self.board,
                "exchange": self.exchange,
                "issue_price": self.issue_price,
                "subscription_date": self.subscription_date.isoformat(),
                "subscription_limit": self.subscription_limit,
                "required_market_value": self.required_market_value,
                "issue_pe": self.issue_pe,
                "industry_pe": self.industry_pe,
                "lottery_announcement_date": _date_to_iso(self.lottery_announcement_date),
                "payment_date": _date_to_iso(self.payment_date),
                "listing_date": _date_to_iso(self.listing_date),
            },
            reason=f"ipo subscription date {self.subscription_date.isoformat()}",
            triggered_at=triggered_at,
        )


class IpoSource(Protocol):
    """Fetch IPO candidates for one subscription date."""

    def fetch_candidates(self, target_date: date) -> list[IpoCandidate]:
        """Return IPO candidates whose subscription date is target_date."""


class AkShareIpoSource:
    """Fetch IPO subscription candidates from AkShare EastMoney data."""

    def __init__(
        self,
        fetch_fn: Callable[..., pd.DataFrame] | None = None,
        board: str = "全部股票",
    ) -> None:
        self.fetch_fn = fetch_fn or ak.stock_xgsglb_em
        self.board = board

    def fetch_candidates(self, target_date: date) -> list[IpoCandidate]:
        frame = self.fetch_fn(symbol=self.board)
        candidates: list[IpoCandidate] = []
        for _, row in frame.iterrows():
            subscription_date = _to_date(row.get("申购日期"))
            if subscription_date != target_date:
                continue
            candidate = _row_to_candidate(row, subscription_date)
            if candidate:
                candidates.append(candidate)
        return candidates


@dataclass(frozen=True)
class IpoWatchPipelineConfig:
    """Runtime settings for IPO watch decisions."""

    min_confidence_to_confirm: float = 0.7


@dataclass(frozen=True)
class IpoWatchResult:
    """Result emitted for each IPO candidate."""

    candidate: IpoCandidate
    opportunity: CandidateOpportunity
    decision: AgentDecision
    status: str
    confirmation: ConfirmationResult | None = None


class IpoWatchPipeline:
    """Fetch IPO candidates, ask the agent, then notify and request confirmation."""

    def __init__(
        self,
        config: IpoWatchPipelineConfig,
        source: IpoSource,
        agent: DecisionAgentClient,
        confirmation_channel: ConfirmationChannel,
        notifier: FeishuNotifier,
        journal: InMemoryDecisionJournal,
    ) -> None:
        self.config = config
        self.source = source
        self.agent = agent
        self.confirmation_channel = confirmation_channel
        self.notifier = notifier
        self.journal = journal

    def scan_once(
        self,
        target_date: date | None = None,
        now: datetime | None = None,
    ) -> list[IpoWatchResult]:
        current_time = now or datetime.now()
        subscription_date = target_date or current_time.date()
        results = []

        for candidate in self.source.fetch_candidates(subscription_date):
            opportunity = candidate.to_opportunity(current_time)
            decision = self.agent.decide(opportunity)
            results.append(self._process_decision(candidate, opportunity, decision, current_time))

        return results

    def _process_decision(
        self,
        candidate: IpoCandidate,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
        now: datetime,
    ) -> IpoWatchResult:
        if not _is_subscribe_action(decision.action) or decision.confidence < self.config.min_confidence_to_confirm:
            return self._finish(candidate, opportunity, decision, "skipped", now)

        confirmation = self.confirmation_channel.request_confirmation(opportunity, decision)
        status = "confirmed" if confirmation.approved else "rejected"
        title = "打新确认通过" if confirmation.approved else "打新确认拒绝"
        self.notifier.notify(title, self._notification_payload(candidate, decision, confirmation))
        return self._finish(candidate, opportunity, decision, status, now, confirmation)

    def _finish(
        self,
        candidate: IpoCandidate,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
        status: str,
        now: datetime,
        confirmation: ConfirmationResult | None = None,
    ) -> IpoWatchResult:
        self.journal.record(
            DecisionRecord(
                timestamp=now,
                opportunity=opportunity,
                decision=decision,
                status=status,
                confirmation=confirmation,
                order_result=None,
            )
        )
        return IpoWatchResult(
            candidate=candidate,
            opportunity=opportunity,
            decision=decision,
            status=status,
            confirmation=confirmation,
        )

    @staticmethod
    def _notification_payload(
        candidate: IpoCandidate,
        decision: AgentDecision,
        confirmation: ConfirmationResult,
    ) -> dict:
        return {
            "symbol": candidate.symbol,
            "name": candidate.name,
            "subscription_code": candidate.subscription_code,
            "board": candidate.board,
            "exchange": candidate.exchange,
            "issue_price": candidate.issue_price,
            "subscription_date": candidate.subscription_date.isoformat(),
            "subscription_limit": candidate.subscription_limit,
            "required_market_value": candidate.required_market_value,
            "issue_pe": candidate.issue_pe,
            "industry_pe": candidate.industry_pe,
            "agent_action": decision.action,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "approved": confirmation.approved,
            "approver": confirmation.approver,
        }


def _row_to_candidate(row: pd.Series, subscription_date: date) -> IpoCandidate | None:
    symbol = str(row.get("股票代码") or "").strip()
    subscription_code = str(row.get("申购代码") or symbol).strip()
    name = str(row.get("股票简称") or "").strip()
    issue_price = _to_float(row.get("发行价格"))
    if not symbol or not subscription_code or issue_price is None:
        return None

    return IpoCandidate(
        symbol=symbol,
        name=name,
        subscription_code=subscription_code,
        board=str(row.get("板块") or ""),
        exchange=str(row.get("交易所") or ""),
        issue_price=issue_price,
        subscription_date=subscription_date,
        subscription_limit=_to_int(row.get("申购上限")),
        required_market_value=_to_float(row.get("顶格申购需配市值")),
        issue_pe=_to_float(row.get("发行市盈率")),
        industry_pe=_to_float(row.get("行业市盈率")),
        lottery_announcement_date=_to_date(row.get("中签号公布日")),
        payment_date=_to_date(row.get("中签缴款日期")),
        listing_date=_to_date(row.get("上市日期")),
        raw=row.to_dict(),
    )


def _is_subscribe_action(action: str) -> bool:
    return action.lower() in {"subscribe", "buy", "申购", "打新"}


def _to_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value, format='mixed', errors='coerce').date()
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if isnan(result) else result


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _date_to_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
