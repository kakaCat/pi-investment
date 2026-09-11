"""持仓生命周期联动（REQ-f08def P5，RFC 014 v3 §2.3，2026-09-11，w-c8cae280）

解决什么：盯盘规则此前与持仓状态完全脱节——买入成交后"等买规则"还挂着（下次跌到买区又喊一遍"建仓"），
清仓后"卖出规则族"还挂着（继续盯一个已经没有立场的标的）。规则的生命周期必须跟着交易走：

  ①买入成交（该标的已有持仓）→ 等买规则**使命完成**：退役 + 横幅标注；
     并确保**存在止损规则**（宪法铁律④：持仓必须有止损盯盘），缺失则自动补挂。
  ②清仓完成（该标的已无持仓）→ 卖出规则族**收摊**：退役 + 横幅标注。

与 P7 元触发的分工：元触发管"规则健康度"（一直响/一直不响）；本服务管"规则使命"（买卖是否已完成）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_ACCOUNTS = ("agent_virtual",)


def stop_loss_pct(symbol: str) -> float:
    """宪法止损口径：创业板/科创板（30/68 开头）-10%，其余 -8%"""
    s = str(symbol).split(".")[0]
    return 0.10 if s.startswith(("30", "68")) else 0.08


class PositionLifecycleService:

    def __init__(self, rule_repo, position_repo=None, accounts=None):
        self.rule_repo = rule_repo
        self.position_repo = position_repo
        self.accounts = tuple(accounts or DEFAULT_ACCOUNTS)

    def _positions(self):
        """返回 (positions, degraded)。degraded=True=读取失败 —— 调用方必须 fail-closed。

        2026-09-11 教训（实测）：持仓适配器字段名错（unrealized_pnl vs profit_total）导致
        读取整体抛错、返回空持仓；若无此标志，联动会误判"已清仓"并**退役真实持仓的止损规则**
        —— 等于亲手拆掉保护。读不到数据时唯一安全的动作是"什么都不做"。
        """
        if self.position_repo is None:
            return {}, True
        out: Dict[str, Dict[str, Any]] = {}
        degraded = False
        for acct in self.accounts:
            try:
                rows = self.position_repo.get_all_positions(acct) or []
            except Exception as e:
                logger.error("持仓读取异常（fail-closed：本次不做任何联动）", account=acct, error=str(e))
                degraded = True
                continue
            try:
                for p in rows:
                    sym = str(getattr(p, "symbol", "")).split(".")[0]
                    shares = int(getattr(p, "shares_total", 0) or 0)
                    if not sym or shares <= 0:
                        continue
                    out[sym] = {"account": acct, "shares": shares,
                                "avg_cost": float(getattr(p, "avg_cost", 0) or 0),
                                "market_value": float(getattr(p, "market_value", 0) or 0)}
            except Exception as e:
                logger.error("持仓明细解析异常（fail-closed）", account=acct, error=str(e))
                degraded = True
        return out, degraded

    def reconcile(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now()
        positions, degraded = self._positions()
        if degraded:
            logger.warning("持仓数据不可用，跳过本次联动（fail-closed：不退役任何规则）")
            return {"positions": 0, "rules_scanned": 0, "retired": 0, "created": 0,
                    "skipped": "持仓读取失败（fail-closed）",
                    "retired_details": [], "created_details": []}
        rules = self.rule_repo.list_enabled()
        retired: List[Dict[str, Any]] = []
        created: List[Dict[str, Any]] = []
        promoted: List[Dict[str, Any]] = []

        # 已存在止损规则的标的（避免重复挂）
        stop_symbols = {
            str(r.symbol).split(".")[0] for r in rules
            if (getattr(r, "intent", None) == "exit_stop") and r.enabled
        }

        for r in rules:
            sym = str(r.symbol).split(".")[0]
            intent = getattr(r, "intent", None) or ""
            held = sym in positions

            # ①已持仓 + 等买/加仓规则：**不自动退役**（2026-09-11 修正）
            #
            # 教训：原实现"持仓已有 → 等买规则退役"看似合理，实测却会毁掉有效计划——
            # 伊利 #95（突破27+放量买入）从未触发过（fired=0），说明那是**尚未执行的加仓计划**，
            # 只因该标的已有持仓就被退役。规则使命是否结束是投资判断，属 agent 终判范畴
            # （RFC 014 v3 §2.1 触发≠执行 / §3.4 L3），机器只做两件确定安全的事：
            #   (a) 安全网：确保持仓有止损盯盘（宪法铁律，缺失即补）
            #   (b) 状态标注：阶段推进到 holding（供元触发/复核把它提请给 agent 裁决）
            if held and intent in ("entry", "add_position"):
                if sym not in stop_symbols:
                    new_id = self._create_stop_loss(r, sym, positions[sym], now)
                    if new_id:
                        stop_symbols.add(sym)
                        created.append({"rule_id": new_id, "symbol": sym, "why": "买入后自动补挂止损"})
                if getattr(r, "lifecycle_stage", None) != "holding":
                    try:
                        self.rule_repo.update_fields(r.id, lifecycle_stage="holding")
                        promoted.append({"rule_id": r.id, "symbol": sym, "why": "已有持仓 → 阶段推进 holding"})
                    except Exception as e:
                        logger.error("阶段推进失败", rule_id=r.id, error=str(e))
                continue

            # ②已清仓：卖出规则族收摊
            if (not held) and intent.startswith("exit_"):
                # 通用观察规则（account 为空）不随持仓收摊
                if getattr(r, "account", None):
                    self._retire(r, "已清仓，卖出规则族收摊；如需继续跟踪请另建观察规则")
                    retired.append({"rule_id": r.id, "symbol": r.symbol, "why": "已清仓收摊"})

        summary = {"positions": len(positions), "rules_scanned": len(rules),
                   "retired": len(retired), "created": len(created),
                   "promoted": len(promoted),
                   "retired_details": retired, "created_details": created,
                   "promoted_details": promoted}
        if retired or created or promoted:
            logger.info("持仓生命周期联动", retired=len(retired), created=len(created),
                        promoted=len(promoted))
        return summary

    def _retire(self, rule, why: str) -> None:
        banner = "[生命周期联动 %s] %s" % (datetime.now().strftime("%Y-%m-%d"), why)
        ctx = (getattr(rule, "context", None) or "")
        try:
            self.rule_repo.update_fields(rule.id, enabled=False,
                                         context=banner + chr(10) + ctx,
                                         lifecycle_stage="closed")
        except Exception as e:
            logger.error("规则退役失败", rule_id=rule.id, error=str(e))

    def _create_stop_loss(self, entry_rule, sym: str, pos: Dict[str, Any], now: datetime) -> Optional[int]:
        cost = pos.get("avg_cost") or float(getattr(entry_rule, "cost_price", 0) or 0)
        if not cost:
            return None
        pct = stop_loss_pct(sym)
        stop_price = round(cost * (1 - pct), 2)
        try:
            rule = self.rule_repo.create_rule(
                symbol=sym,
                conditions=[{"type": "price_break",
                             "params": {"price": stop_price, "direction": "below"}}],
                context=("买入后自动补挂止损（RFC 014 v3 §2.3 安全网）：成本 %.2f × (1-%.0f%%) = %.2f。"
                         "宪法止损铁律，触发即执行，不得延后。" % (cost, pct * 100, stop_price)),
                cost_price=cost, created_by="agent", account=pos.get("account"),
            )
            self.rule_repo.update_fields(
                rule.id,
                intent="exit_stop", lifecycle_stage="holding", scope="position",
                linked_account=pos.get("account"),
                created_from="position_lifecycle:%s" % sym,
                action_hint={"trigger_level": "L2", "action_on_trigger": "sell", "requires_agent": True},
            )
            return rule.id
        except Exception as e:
            logger.error("止损规则创建失败", symbol=sym, error=str(e))
            return None
