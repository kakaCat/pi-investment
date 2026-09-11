"""市场级盯盘服务（REQ-f08def P6，RFC 014 v3 §1.1/§1.3，2026-09-11，w-c8cae280）

用户的定位：盯盘是「紧盯市场情况的工具」。此前引擎只能盯个股，指数/板块/情绪/量能进不来。

职责（应用层编排；判定在领域服务 MarketRuleEvaluator，取数在适配器 MarketStateProvider）：
  1) scan_market_rules：评估 scope=market/sector 的启用规则 → 命中则落触发（走同一处置口径）
     市场级观察类命中默认落 auto_observed（零 LLM，只更新认识）——这是"眼睛常睁、脑子少动"。
  2) summary_text：产出「市场状态摘要」，供摘要唤醒时内嵌（agent 不必再逐个工具取数）。

闩锁语义与个股一致：条件由"未成立→成立"才报一次，条件回落即重新武装（避免持续成立刷屏）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from domain.watch.services.disposition import GateContext, decide
from domain.watch.services.market_rule_evaluator import MarketRuleEvaluator

logger = structlog.get_logger(__name__)

MARKET_SCOPES = ("market", "sector")


class MarketWatchService:

    def __init__(self, rule_repo, trigger_repo, state_provider=None, evaluator=None,
                 trigger_interval_sec: int = 300):
        self.rule_repo = rule_repo
        self.trigger_repo = trigger_repo
        self.state_provider = state_provider
        self.evaluator = evaluator or MarketRuleEvaluator()
        self.trigger_interval_sec = trigger_interval_sec
        self._latched: set = set()
        self._state_date = None
        self._last_scan_at: Optional[datetime] = None

    # ── 市场级规则扫描 ────────────────────────────────────────
    def scan_market_rules(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now()
        if self._state_date != now.date():
            self._latched.clear()
            self._state_date = now.date()
        if self.state_provider is None:
            return {"skipped": "未注入市场状态端口", "scanned": 0, "triggered": 0}
        if (self._last_scan_at is not None
                and (now - self._last_scan_at).total_seconds() < self.trigger_interval_sec):
            return {"skipped": "未到扫描间隔", "scanned": 0, "triggered": 0}
        self._last_scan_at = now

        state = self.state_provider.get_state()
        rules = [r for r in self.rule_repo.list_enabled()
                 if (getattr(r, "scope", None) in MARKET_SCOPES)]
        triggered: List[Dict[str, Any]] = []
        skipped_data = 0

        for rule in rules:
            for idx, cond in enumerate(getattr(rule, "conditions", None) or []):
                try:
                    res = self.evaluator.evaluate(cond, state)
                except Exception as e:
                    logger.error("市场级条件评估异常", rule_id=rule.id, error=str(e))
                    continue
                key = (rule.id, idx)
                if res.skipped:
                    skipped_data += 1
                    continue
                if not res.triggered:
                    self._latched.discard(key)   # 回落 → 重新武装
                    continue
                if key in self._latched:
                    continue
                self._latched.add(key)
                rec = self._record(rule, cond, res, now)
                if rec:
                    triggered.append(rec)

        return {"scanned": len(rules), "triggered": len(triggered),
                "skipped_no_data": skipped_data, "degraded": list(state.degraded),
                "details": triggered}

    def _record(self, rule, condition, res, now) -> Optional[Dict[str, Any]]:
        intent = getattr(rule, "intent", None)
        disposition, reason = decide(
            rule, condition, escalated=False,
            gate=GateContext(intent=intent, trigger_kind="price", daily_wake_count=0),
        )
        try:
            self.trigger_repo.record(
                rule_id=rule.id,
                symbol=rule.symbol,
                condition=condition,
                trigger_price=res.value,
                detail={"value": res.value, "message": res.message,
                        "market_scope": getattr(rule, "scope", None)},
                notified=False,
                disposition=disposition,
                disposition_reason="市场级：%s（%s）" % (res.message, reason),
                disposition_by="system",
            )
        except Exception as e:
            logger.error("市场级触发落库失败", rule_id=rule.id, error=str(e))
            return None
        logger.info("市场级规则命中", rule_id=rule.id, symbol=rule.symbol,
                    message=res.message, disposition=disposition)
        return {"rule_id": rule.id, "symbol": rule.symbol, "message": res.message,
                "disposition": disposition, "value": res.value}

    # ── 市场状态摘要（供摘要唤醒内嵌）──────────────────────────
    def summary_text(self) -> str:
        if self.state_provider is None:
            return ""
        try:
            st = self.state_provider.get_state()
        except Exception as e:
            logger.warning("市场状态摘要生成失败", error=str(e))
            return ""
        parts = []
        idx_bits = []
        for code, item in (st.indices or {}).items():
            chg = item.get("change_pct")
            if chg is not None:
                idx_bits.append("%s %+.2f%%" % (code.split(".")[0], chg))
        if idx_bits:
            parts.append("指数：" + " | ".join(idx_bits))
        if st.limit_up_count is not None:
            parts.append("涨停 %d 家" % st.limit_up_count
                         + ("（最高 %d 板）" % st.max_streak if st.max_streak else ""))
        if st.sentiment_score is not None:
            parts.append("情绪分 %.0f" % st.sentiment_score
                         + ("（恐贪 %.0f）" % st.fear_greed_index if st.fear_greed_index is not None else ""))
        if st.volume_ratio is not None:
            parts.append("量能 %.2fx" % st.volume_ratio)
        if st.advance_decline_ratio is not None:
            parts.append("涨跌家数比 %.2f" % st.advance_decline_ratio)
        if st.sectors:
            top = sorted(st.sectors.items(), key=lambda kv: kv[1], reverse=True)[:3]
            bot = sorted(st.sectors.items(), key=lambda kv: kv[1])[:3]
            parts.append("强势板块：" + "、".join("%s %+.1f%%" % (k, v) for k, v in top))
            parts.append("弱势板块：" + "、".join("%s %+.1f%%" % (k, v) for k, v in bot))
        if st.degraded:
            parts.append("⚠️ 数据不可用：" + "、".join(sorted(set(st.degraded))))
        if not parts:
            return ""
        return "【市场状态】" + "；".join(parts)
