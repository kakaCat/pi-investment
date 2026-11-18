"""投资评价与业绩归因（A 项第一期）。

计算逻辑与数据库访问分离：Repository 只读事实表，本服务构建交易回合、
经济账、投资能力账及全局未归属信号统计。无样本与不可核验均显式降级。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from adapters.outbound.repositories.investment_evaluation_repository import (
    InvestmentEvaluationRepository,
)

ENGINEERING_MARKERS = (
    "测试 submitted_by",
    "最终验证 submitted_by",
    "工程测试单",
    "engineering_test",
    "test_only",
)


def _f(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _d(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _fees(trade: Dict[str, Any]) -> float:
    return sum(_f(trade.get(key), 0.0) or 0.0 for key in ("commission", "stamp_duty", "transfer_fee"))


def classify_trade(trade: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """保守识别有明确证据的工程单；普通“策略验证”不误伤。

    新记录可显式写 submitted_by/strategy_name=engineering_test（或 test_only），
    评价层据此隔离；不使用宽泛 test/验证 正则，也不修改交易写路径。
    """
    for field in ("submitted_by", "strategy_name"):
        metadata = str(trade.get(field) or "").strip().lower()
        if metadata in {"engineering_test", "test_only"}:
            return "engineering_test", f"explicit_metadata:{field}={metadata}"
    reason = str(trade.get("reason") or "")
    lowered = reason.lower()
    for marker in ENGINEERING_MARKERS:
        if marker.lower() in lowered:
            return "engineering_test", f"explicit_marker:{marker}"
    return "investment", None


def build_trade_episodes(trades: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """按账户内标的持仓回合合并加仓与部分平仓。"""
    episodes: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    open_by_symbol: Dict[str, Dict[str, Any]] = {}

    for trade in sorted(trades, key=lambda row: (str(row.get("trade_time")), int(row["id"]))):
        symbol = str(trade["symbol"])
        action = str(trade["action"]).upper()
        shares = int(trade.get("shares") or 0)
        evaluation_class, classification_rule = classify_trade(trade)
        current = open_by_symbol.get(symbol)
        if action == "BUY":
            if current is None:
                current = {
                    "episode_id": f"{trade['account_name']}:{symbol}:{trade['id']}",
                    "account_name": trade["account_name"],
                    "symbol": symbol,
                    "status": "open",
                    "entry_time": _iso(trade.get("trade_time")),
                    "exit_time": None,
                    "trade_ids": [],
                    "shares_open": 0,
                    "realized_pnl": 0.0,
                    "fees": 0.0,
                    "classes": set(),
                    "classification_rules": set(),
                    "realized_complete": True,
                }
                open_by_symbol[symbol] = current
        elif action == "SELL" and current is None:
            unmatched.append({
                "trade_id": trade["id"], "symbol": symbol,
                "reason": "sell_without_verified_open_episode",
            })
            continue
        elif action != "SELL":
            unmatched.append({"trade_id": trade["id"], "symbol": symbol, "reason": "unknown_action"})
            continue

        current["trade_ids"].append(trade["id"])
        current["classes"].add(evaluation_class)
        if classification_rule:
            current["classification_rules"].add(classification_rule)
        current["fees"] += _fees(trade)
        if action == "BUY":
            current["shares_open"] += shares
        else:
            current["shares_open"] -= shares
            pnl = _f(trade.get("realized_pnl"))
            if pnl is None:
                current["realized_complete"] = False
            else:
                current["realized_pnl"] += pnl
            current["exit_time"] = _iso(trade.get("trade_time"))
            if current["shares_open"] < 0:
                unmatched.append({"trade_id": trade["id"], "symbol": symbol, "reason": "oversold_episode"})
                current["status"] = "invalid"
            elif current["shares_open"] == 0:
                current["status"] = "closed"

        if current["status"] in ("closed", "invalid"):
            episodes.append(_public_episode(current))
            del open_by_symbol[symbol]

    episodes.extend(_public_episode(row) for row in open_by_symbol.values())
    return episodes, unmatched


def _public_episode(row: Dict[str, Any]) -> Dict[str, Any]:
    classes = set(row["classes"])
    evaluation_class = classes.pop() if len(classes) == 1 else "mixed"
    return {
        "episode_id": row["episode_id"],
        "account_name": row["account_name"],
        "symbol": row["symbol"],
        "status": row["status"],
        "evaluation_class": evaluation_class,
        "classification_rules": sorted(row["classification_rules"]),
        "entry_time": row["entry_time"],
        "exit_time": row["exit_time"],
        "trade_ids": list(row["trade_ids"]),
        "realized_pnl": round(row["realized_pnl"], 2),
        "fees": round(row["fees"], 2),
        "realized_complete": row["realized_complete"],
    }


def summarize_episodes(episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    closed = [
        row for row in episodes
        if row["status"] == "closed" and row["realized_complete"]
    ]
    investment = [row for row in closed if row["evaluation_class"] == "investment"]
    return {
        "economic": _episode_stats(closed),
        "investment": _episode_stats(investment),
        "open_count": sum(row["status"] == "open" for row in episodes),
        "excluded_count": sum(
            row["status"] == "closed" and row["evaluation_class"] != "investment"
            for row in episodes
        ),
    }


def _episode_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = len(rows)
    if not count:
        return {
            "sample_status": "insufficient_sample", "count": 0,
            "wins": 0, "losses": 0, "win_rate": None,
            "average_win": None, "average_loss": None, "expectancy": None,
            "total_realized_pnl": 0.0, "profit_factor": None,
        }
    pnl = [_f(row["realized_pnl"], 0.0) or 0.0 for row in rows]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    return {
        "sample_status": "small_sample" if count < 20 else "preliminary",
        "count": count,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / count,
        "average_win": sum(wins) / len(wins) if wins else None,
        "average_loss": sum(losses) / len(losses) if losses else None,
        "expectancy": sum(pnl) / count,
        "total_realized_pnl": sum(pnl),
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
    }


def build_signal_episodes(signals: Iterable[Dict[str, Any]], gap_days: int = 20) -> List[Dict[str, Any]]:
    """历史信号去重代理：同股同源 20 自然日内只取首个代表信号。"""
    representatives: List[Dict[str, Any]] = []
    last_seen: Dict[Tuple[str, str], date] = {}
    for signal in sorted(
        signals,
        key=lambda row: (str(row["symbol"]), str(row["source"]), _d(row["signal_date"]) or date.min, int(row["id"])),
    ):
        signal_date = _d(signal["signal_date"])
        if signal_date is None:
            continue
        key = (str(signal["symbol"]), str(signal["source"]))
        previous = last_seen.get(key)
        if previous is None or (signal_date - previous).days > gap_days:
            representatives.append(signal)
        last_seen[key] = signal_date
    return representatives


def summarize_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    representatives = build_signal_episodes(signals)
    return {
        "scope": "global_unassigned",
        "account_attribution": "unavailable_signal_tracking_has_no_account_column",
        "not_account_evidence": True,
        "independence_method": "symbol_source_20_calendar_day_episode",
        "independence_status": "estimated",
        "total_records": len(signals),
        "estimated_independent_episodes": len(representatives),
        "by_grade": {
            grade: _signal_stats([row for row in representatives if row.get("grade") == grade])
            for grade in ("A", "B", "C")
        },
        "by_source": {
            source: _signal_stats([row for row in representatives if row.get("source") == source])
            for source in sorted({str(row.get("source")) for row in representatives})
        },
    }


def _signal_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "count": len(rows),
        "sample_status": "insufficient_sample" if not rows else ("small_sample" if len(rows) < 20 else "preliminary"),
    }
    for window in (5, 10, 20):
        key = f"return_{window}d"
        values = [_f(row.get(key)) for row in rows]
        mature = [value for value in values if value is not None]
        wins = [value for value in mature if value > 0]
        losses = [value for value in mature if value < 0]
        result[f"window_{window}d"] = {
            "mature_count": len(mature),
            "sample_status": "insufficient_sample" if not mature else ("small_sample" if len(mature) < 20 else "preliminary"),
            "win_rate": len(wins) / len(mature) if mature else None,
            "average_return": sum(mature) / len(mature) if mature else None,
            "average_win": sum(wins) / len(wins) if wins else None,
            "average_loss": sum(losses) / len(losses) if losses else None,
        }
    return result


def calculate_account_economy(
    snapshots: List[Dict[str, Any]],
    external_flows: List[Dict[str, Any]],
    start_date: Optional[date],
    end_date: date,
    annual_cost_rate: float,
) -> Dict[str, Any]:
    eligible = [row for row in snapshots if _d(row.get("snapshot_date")) and _d(row["snapshot_date"]) <= end_date]
    eligible.sort(key=lambda row: _d(row["snapshot_date"]))
    if not eligible:
        return {"status": "insufficient_data", "reason": "no_equity_snapshots"}

    if start_date:
        before = [row for row in eligible if _d(row["snapshot_date"]) < start_date]
        during = [row for row in eligible if _d(row["snapshot_date"]) >= start_date]
        selected = ([before[-1]] if before else []) + during
        effective_start = start_date
    else:
        selected = eligible
        effective_start = _d(selected[0]["snapshot_date"])
    if not selected:
        return {"status": "insufficient_data", "reason": "no_snapshot_in_requested_period"}

    start_nav = _f(selected[0].get("total_value"))
    end_nav = _f(selected[-1].get("total_value"))
    snapshot_end = _d(selected[-1]["snapshot_date"])
    if start_nav is None or end_nav is None or start_nav <= 0:
        return {"status": "insufficient_data", "reason": "invalid_nav"}

    # 外部流生效日不能只信 created_at：历史回填会出现“快照已含入金、流水晚两日落库”。
    # 先用 balance_after 与快照现金余额对账；最早匹配快照若已在期初，即视为期初资本而非本期新增收益/入金。
    flow_by_date: Dict[date, float] = defaultdict(float)
    flow_audit = []
    for flow in external_flows:
        original_date = _d(flow.get("created_at"))
        balance_after = _f(flow.get("balance_after"))
        candidates = sorted({
            _d(row["snapshot_date"]) for row in eligible
            if balance_after is not None
            and _f(row.get("cash")) is not None
            and abs(_f(row.get("cash")) - balance_after) < 0.01
            and (original_date is None or _d(row["snapshot_date"]) <= original_date)
        })
        effective_date = candidates[0] if candidates else original_date
        method = "cash_balance_earliest_snapshot" if candidates else "created_date_fallback_unverified"
        included = bool(effective_date and effective_start < effective_date <= snapshot_end)
        amount = _f(flow.get("amount"), 0.0) or 0.0
        if included:
            flow_by_date[effective_date] += amount
        flow_audit.append({
            "flow_id": flow.get("id"), "flow_type": flow.get("flow_type"), "amount": amount,
            "original_date": _iso(original_date), "effective_date": _iso(effective_date),
            "method": method, "cash_balance_candidate_count": len(candidates),
            "included_in_period": included,
        })
    external_net_flow = sum(flow_by_date.values())

    linked = 1.0
    interval_returns = []
    previous_date = effective_start
    previous_nav = start_nav
    funding_cost = 0.0
    for snapshot in selected[1:]:
        current_date = _d(snapshot["snapshot_date"])
        current_nav = _f(snapshot.get("total_value"))
        if current_nav is None or current_date is None:
            continue
        flow = sum(value for day, value in flow_by_date.items() if previous_date < day <= current_date)
        interval_return = (current_nav - previous_nav - flow) / previous_nav
        linked *= 1.0 + interval_return
        interval_returns.append({
            "from": previous_date.isoformat(), "to": current_date.isoformat(),
            "external_flow": flow, "return": interval_return,
        })
        days = (current_date - previous_date).days
        funding_cost += (previous_nav + current_nav) / 2.0 * annual_cost_rate * days / 365.0
        previous_date, previous_nav = current_date, current_nav

    # 若外部流只能回退到流水日期且出现极端区间，TWR 必须降级，不能输出貌似精确的错误数字。
    has_unverified_flow = any(
        row["included_in_period"] and row["method"] == "created_date_fallback_unverified"
        for row in flow_audit
    )
    extreme_unverified = has_unverified_flow and any(
        abs(row["return"]) > 1.0 for row in interval_returns
    )
    twr = linked - 1.0 if interval_returns and not extreme_unverified else None
    economic_pnl = end_nav - start_nav - external_net_flow - funding_cost
    stale_days = max((end_date - snapshot_end).days, 0)
    estimated_cost_to_report_end = funding_cost + end_nav * annual_cost_rate * stale_days / 365.0
    return {
        "status": (
            "degraded_external_flow_alignment" if extreme_unverified
            else ("ok" if interval_returns else "insufficient_return_intervals")
        ),
        "external_flow_alignment": flow_audit,
        "effective_start": effective_start.isoformat(),
        "nav_as_of": snapshot_end.isoformat(),
        "requested_end": end_date.isoformat(),
        "start_nav": start_nav,
        "end_nav": end_nav,
        "external_net_flow": external_net_flow,
        "time_weighted_return": twr,
        "time_weighted_return_pct": twr * 100.0 if twr is not None else None,
        "funding_cost_to_nav_date": funding_cost,
        "estimated_funding_cost_to_report_end": estimated_cost_to_report_end,
        "economic_pnl_after_funding_cost": economic_pnl,
        "economic_return_after_funding_cost_pct": economic_pnl / start_nav * 100.0,
        "annual_cost_rate": annual_cost_rate,
        "capital_cost_method": "snapshot_interval_average_nav_actual_days_365",
        "nav_stale_days": stale_days,
        "synthetic_snapshot_count": sum(bool(row.get("is_synthetic")) for row in selected),
        "interval_count": len(interval_returns),
        "intervals": interval_returns,
    }


class InvestmentEvaluationService:
    def __init__(self, repository=None):
        self.repository = repository or InvestmentEvaluationRepository()

    def build_report(
        self,
        account_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        annual_cost_rate: float = 0.02,
    ) -> Dict[str, Any]:
        if not account_name or not account_name.strip():
            raise ValueError("account_name 必填")
        if not 0 <= annual_cost_rate <= 1:
            raise ValueError("annual_cost_rate 须在 0~1 之间")
        start = _d(start_date) if start_date else None
        if start_date and start is None:
            raise ValueError("start_date 格式须为 YYYY-MM-DD")
        end = _d(end_date) if end_date else date.today()
        if end is None:
            raise ValueError("end_date 格式须为 YYYY-MM-DD")
        if start and start > end:
            raise ValueError("start_date 不得晚于 end_date")

        trades = self.repository.get_trades(account_name, start_date, end_date)
        snapshots = self.repository.get_snapshots(account_name, end_date)
        # 取全量外部流供生效日对账；历史流水的 created_at 可能晚于其净值生效日。
        flows = self.repository.get_external_flows(account_name, None, None)
        positions = self.repository.get_positions(account_name)
        signals = self.repository.get_signals(start_date, end_date)
        decisions = self.repository.get_decision_summary(account_name)
        account = self.repository.get_account(account_name)

        ledger = []
        for trade in trades:
            evaluation_class, classification_rule = classify_trade(trade)
            ledger.append({
                **trade,
                "filled_price": _f(trade.get("filled_price")),
                "amount": _f(trade.get("amount")),
                "realized_pnl": _f(trade.get("realized_pnl")),
                "fees": _fees(trade),
                "evaluation_class": evaluation_class,
                "classification_rule": classification_rule,
                "trade_date": _iso(trade.get("trade_date")),
                "trade_time": _iso(trade.get("trade_time")),
                "order_decision_at": _iso(trade.get("order_decision_at")),
                "pending_decision_at": _iso(trade.get("pending_decision_at")),
                "pending_created_at": _iso(trade.get("pending_created_at")),
            })
        episodes, unmatched = build_trade_episodes(trades)
        episode_summary = summarize_episodes(episodes)
        economy = calculate_account_economy(snapshots, flows, start, end, annual_cost_rate)

        all_sell_pnl = [_f(row.get("realized_pnl")) for row in trades if str(row.get("action")).upper() == "SELL"]
        all_sell_pnl = [value for value in all_sell_pnl if value is not None]
        engineering_ids = {
            trade_id for episode in episodes if episode["evaluation_class"] == "engineering_test"
            for trade_id in episode["trade_ids"]
        }
        engineering_sell_pnl = [
            _f(row.get("realized_pnl"), 0.0) or 0.0 for row in trades
            if row["id"] in engineering_ids and str(row.get("action")).upper() == "SELL"
        ]

        current_positions = [{
            **row,
            "avg_cost": _f(row.get("avg_cost")),
            "current_price": _f(row.get("current_price")),
            "market_value": _f(row.get("market_value")),
            "profit_total": _f(row.get("profit_total")),
            "profit_total_rate": _f(row.get("profit_total_rate")),
            "created_at": _iso(row.get("created_at")),
            "updated_at": _iso(row.get("updated_at")),
        } for row in positions]
        current_unrealized = sum(row.get("profit_total") or 0.0 for row in current_positions)

        warnings = [
            "signal_tracking 无账户/决策关联字段：信号统计仅为全局未归属证据",
            "历史信号独立分组为 20 自然日估算，不等于已证明独立样本",
            "工程测试文本分类只覆盖显式历史证据；排除清单逐条公开",
        ]
        if economy.get("nav_stale_days", 0) > 0:
            warnings.append(f"净值最后日期早于报告截止日 {economy['nav_stale_days']} 天")
        if unmatched:
            warnings.append(f"存在 {len(unmatched)} 条无法匹配持仓回合的成交")

        return {
            "schema_version": "investment_evaluation_v1",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "read_only": True,
            "account_name": account_name,
            "period": {"start_date": start_date, "end_date": end.isoformat()},
            "account_current": {
                **(account or {}),
                "updated_at": _iso((account or {}).get("updated_at")),
                "current_unrealized_pnl": current_unrealized,
                "positions": current_positions,
            },
            "account_economy": economy,
            "trade_economy": {
                "trade_count": len(trades),
                "sell_count": sum(str(row.get("action")).upper() == "SELL" for row in trades),
                "scored_sell_count": len(all_sell_pnl),
                "total_fees": sum(_fees(row) for row in trades),
                "realized_pnl_all_sells": sum(all_sell_pnl),
                "engineering_realized_pnl": sum(engineering_sell_pnl),
                "note": "实现盈亏按成交表汇总；工程亏损仍计入账户经济结果",
            },
            "investment_ability": {
                **episode_summary["investment"],
                "unit": "closed_position_episode",
                "engineering_excluded": True,
                "note": "加仓和部分平仓合并为一个回合；开放回合不参与胜率",
            },
            "episode_summary": episode_summary,
            "trade_episodes": episodes,
            "trade_ledger": ledger,
            "signal_evaluation": summarize_signals(signals),
            "decision_coverage": {
                **decisions,
                "latest_decision_at": _iso(decisions.get("latest_decision_at")),
                "score_scope": "context.account_exact_match",
            },
            "data_quality": {
                "warnings": warnings,
                "unmatched_trades": unmatched,
                "excluded_engineering_trade_ids": sorted(engineering_ids),
                "trade_order_link_count": sum(row.get("order_id") is not None for row in trades),
                "trade_signal_link_count": sum(row.get("signal_id") is not None for row in trades),
                "trade_pending_link_count": sum(row.get("pending_order_id") is not None for row in trades),
                "source_counts": {
                    "trades": len(trades), "snapshots": len(snapshots),
                    "external_flows": len(flows), "positions": len(positions),
                    "signals_global_unassigned": len(signals),
                },
            },
        }
