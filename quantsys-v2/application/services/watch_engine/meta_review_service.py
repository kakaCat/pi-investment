"""元触发复核服务（REQ-f08def P7，RFC 014 v3 §13，2026-09-11，w-c8cae280）

用户明确要求：「盯盘总触发或者超时也需要 agent 介入处理，不能一直一个规则盯盘」。

本服务把"规则自身的健康度"变成 agent 的检查点：
  · burst  一直响：单日触发 ≥ N 次 → 阈值是否失真？该转阶段？该取消？
  · idle   一直不响：距上次触发 ≥ T 天 → 价值还在吗？续期/调整/取消？
  · stage  阶段滞留：距上次复核 ≥ T 天且仍在同一阶段 → 推进还是回退？
  · expiry 快到期：expires_at ≤ 2 天 → 续期还是收摊？
命中即落一条 meta_review 触发（复用 watch_triggers 流转，进未处置清单 → 会被摘要唤醒带走），
并更新规则的 last_reviewed_at / review_due_at（保证"到期必被 agent 看一次"）。

与「去重」的区别：去重解决"同一次跌穿不要响多次"；本服务解决"同一条规则长期响/长期不响"。
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog

from domain.watch.services.disposition import (
    DISPOSITION_META_REVIEW, InterventionConfig, evaluate_meta_trigger,
)

logger = structlog.get_logger(__name__)

# 复核周期默认值（RFC 014 v3 §13：按意图区分——持仓类看紧、观察类放长）
REVIEW_INTERVAL_DAYS = {
    "exit_stop": 3, "exit_take_profit": 3, "exit_reduce": 3,
    "add_position": 3, "t_trade": 3,
    "entry": 7,
    "trend_observe": 14,
}


class WatchMetaReviewService:

    def __init__(self, rule_repo, trigger_repo, cfg: Optional[InterventionConfig] = None):
        self.rule_repo = rule_repo
        self.trigger_repo = trigger_repo
        self.cfg = cfg or InterventionConfig()

    # ── 数据采集（一次查询覆盖全部规则，避免 N+1）──────────
    def _trigger_stats(self):
        """批量触发统计（由注入的 trigger_repo 适配器提供，应用层不碰 SQL）"""
        try:
            return self.trigger_repo.get_rule_trigger_stats() or {}
        except Exception as e:
            logger.warning("元触发统计读取失败", error=str(e))
            return {}

    def scan(self, now: Optional[datetime] = None, force: bool = False) -> Dict[str, Any]:
        """扫描全部启用规则，产出 meta_review 复核项。返回摘要。"""
        now = now or datetime.now()
        stats = self._trigger_stats()
        rules = self.rule_repo.list_enabled()
        raised = []
        skipped_reviewed = 0

        for rule in rules:
            intent = str(getattr(rule, "intent", "") or "") or "trend_observe"
            interval = REVIEW_INTERVAL_DAYS.get(intent, 7)
            st = stats.get(rule.id, {"today": 0, "last_at": None})

            # 当日已复核过则跳过（每天最多一次，避免噪声）
            last_reviewed = getattr(rule, "last_reviewed_at", None)
            if (not force) and last_reviewed is not None and last_reviewed.date() == now.date():
                skipped_reviewed += 1
                continue

            reasons = []
            ok, why = evaluate_meta_trigger("burst", burst_count=st["today"], cfg=self.cfg)
            if ok:
                reasons.append(why)

            anchor = st["last_at"] or getattr(rule, "created_at", None) or now
            idle_days = (now - anchor).days
            ok, why = evaluate_meta_trigger("idle", idle_days=idle_days, cfg=self.cfg)
            if ok:
                reasons.append(why)

            stage_anchor = last_reviewed or getattr(rule, "created_at", None) or now
            stage_idle = (now - stage_anchor).days
            ok, why = evaluate_meta_trigger("stage", stage_idle_days=stage_idle, cfg=self.cfg)
            if ok:
                reasons.append(why)

            expires_at = getattr(rule, "expires_at", None)
            if expires_at is not None:
                days_left = (expires_at - now).days
                ok, why = evaluate_meta_trigger("expiry", days_to_expiry=days_left, cfg=self.cfg)
                if ok:
                    reasons.append(why)

            if not reasons:
                continue

            reason = "；".join(reasons)
            try:
                self.trigger_repo.record(
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    condition={"type": "meta_review",
                               "params": {"kinds": ["burst", "idle", "stage", "expiry"],
                                          "intent": intent}},
                    trigger_price=None,
                    detail={"message": reason, "intent": intent,
                            "today_triggers": st["today"], "idle_days": idle_days,
                            "stage_idle_days": stage_idle},
                    notified=False,
                    disposition=DISPOSITION_META_REVIEW,
                    disposition_reason=reason,
                    disposition_by="system",
                )
                self._mark_reviewed(rule.id, now, interval)
                raised.append({"rule_id": rule.id, "symbol": rule.symbol,
                               "intent": intent, "reason": reason})
            except Exception as e:
                logger.error("元触发落库失败", rule_id=rule.id, error=str(e))

        if raised:
            logger.info("元触发复核项已生成", count=len(raised))
        return {"scanned_rules": len(rules), "raised": len(raised),
                "skipped_already_reviewed": skipped_reviewed, "details": raised}

    def _mark_reviewed(self, rule_id: int, now, interval_days: int) -> None:
        """标记已复核（走仓储端口，不裸 SQL）——保证到期必被 agent 看一次"""
        from datetime import timedelta as _td
        try:
            self.rule_repo.update_fields(
                rule_id,
                last_reviewed_at=now,
                review_interval_days=interval_days,
                review_due_at=now + _td(days=interval_days),
            )
        except Exception as e:
            logger.error("复核时间写入失败", rule_id=rule_id, error=str(e))

