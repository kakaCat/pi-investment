from datetime import date
from typing import Any, Dict, List, Optional, Tuple


_RISK_LABELS = {"low": "低风险", "medium": "中风险", "high": "高风险"}


def _score(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def _reasons(opportunity: Dict[str, Any]) -> str:
    reasons = opportunity.get("reasons") or []
    if not reasons and opportunity.get("reason"):
        reasons = [opportunity["reason"]]
    cleaned = [" ".join(str(reason).split()) for reason in reasons if str(reason).strip()]
    if not cleaned:
        return "暂无评分依据"
    return "；".join(reason[:120] for reason in cleaned[:2])


def _rule_status(symbol: str, rule_by_symbol: Dict[str, Dict[str, Any]],
                 auto_create_rules: bool) -> str:
    if not auto_create_rules:
        return "只读扫描，未建规则"
    result = rule_by_symbol.get(symbol)
    if not result:
        return "未建规则"
    action = result.get("action")
    reason = str(result.get("reason") or "").strip()
    if action == "created":
        return f"已建规则 #{result.get('rule_id')}"
    if action == "skipped":
        return f"未重复创建：{reason}" if reason else "未重复创建"
    if action == "failed":
        return f"创建失败：{reason}" if reason else "创建失败"
    return reason or "未建规则"


def render_opportunity_scan_summary(
    opportunities: List[Dict[str, Any]],
    rule_results: List[Dict[str, Any]],
    *,
    scanned: int,
    scored: int,
    trade_date: Optional[str] = None,
    auto_create_rules: bool = True,
    max_items: int = 10,
) -> Tuple[str, str]:
    candidates = [opp for opp in opportunities if float(opp.get("score", 0)) >= 80]
    day = trade_date or date.today().isoformat()
    title = f"【每日机会扫描】{day}｜{len(candidates)} 个高分机会"
    lines = [
        f"**扫描概况**：扫描 {scanned} 只｜评分成功 {scored} 只｜≥80 分 {len(candidates)} 个"
    ]
    rule_by_symbol = {str(result.get("symbol")): result for result in rule_results}

    for index, opp in enumerate(candidates[:max_items], 1):
        symbol = str(opp.get("symbol") or "—")
        name = str(opp.get("name") or symbol)
        risk = _RISK_LABELS.get(str(opp.get("risk_level")), "风险未知")
        lines.extend([
            "",
            f"**{index}. {name}（{symbol}）｜{_score(opp.get('score'))} 分｜{risk}**",
            f"技术 {_score(opp.get('technical_score'))}｜"
            f"基本面 {_score(opp.get('fundamental_score'))}｜"
            f"资金 {_score(opp.get('capital_score'))}",
            f"依据：{_reasons(opp)}",
            f"盯盘：{_rule_status(symbol, rule_by_symbol, auto_create_rules)}",
        ])

    remaining = len(candidates) - min(len(candidates), max_items)
    if remaining:
        lines.extend(["", f"另有 {remaining} 个高分机会未展开。"])
    lines.extend([
        "",
        "仅为高分观察机会，不自动交易；后续价格条件命中时由 V2 再发触发提醒。",
    ])
    return title, "\n".join(lines)
