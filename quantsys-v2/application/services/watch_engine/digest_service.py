"""盯盘摘要服务（REQ-f08def P2/P4，2026-09-11，w-c8cae280）

定位：**引擎内置的"何时唤醒 agent"之门**（RFC 014 v3 §3.3 / §1.3）。

为什么做进服务而不是脚本/外部定时器：
  1. WatchEngine 的 run_forever 本来就只在交易时段循环 —— 摘要门跟着它转最自然，
     不需要额外定时器、不需要 agent-os 任务、不需要 shell 脚本；
  2. 摘要状态（上次唤醒/当日次数）落库（quant.watch_digest_state）—— 实测重启即
     清零会让每日预算形同虚设，落库才真正"与触发数解耦"；
  3. 唤醒走官方通道 AgentNotificationService → POST /wake（lifecycle 已注册 exact 路由，
     投递到 investor 窗口），不是裸 curl。

三道门（任一不过则静默退出，零 LLM）：
  ①队列空 ②距上次唤醒 < min_interval_sec ③当日唤醒 >= daily_cap
"""
from datetime import datetime, time as dtime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class WatchDigestService:
    """待处置触发的摘要与唤醒门（引擎 loop 调用 maybe_wake）"""

    def __init__(self, trigger_repo, rule_repo, agent_service=None, state_repo=None,
                 min_interval_sec: int = 1500, daily_cap: int = 8, limit: int = 200):
        self.trigger_repo = trigger_repo
        self.rule_repo = rule_repo
        self.agent_service = agent_service
        # 端口注入（ADR-001）：状态持久化交给 IWatchDigestStateRepository 适配器，
        # 应用层不得 get_engine()/裸 SQL
        self.state_repo = state_repo
        self.min_interval_sec = min_interval_sec
        self.daily_cap = daily_cap
        self.limit = limit

    # ── 交易时段门 ────────────────────────────────────────────
    @staticmethod
    def is_trading_time(now: datetime) -> bool:
        if now.weekday() >= 5:
            return False
        t = now.time()
        return (dtime(9, 30) <= t <= dtime(11, 30)) or (dtime(13, 0) <= t <= dtime(15, 0))

    # ── 状态（落库，重启不清零）──────────────────────────────
    def _load_state(self):
        if self.state_repo is None:
            return {"last_wake_at": None, "wake_date": None, "wake_count": 0}
        return self.state_repo.load_state()

    def _save_wake(self, now) -> None:
        if self.state_repo is not None:
            self.state_repo.save_wake(now)

    def build_digest(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """按标的聚合的待处置摘要（路由与唤醒共用同一实现，避免两处口径）"""
        from domain.watch.services.disposition import UNRESOLVED
        rows = self.trigger_repo.list_triggers(dispositions=UNRESOLVED, limit=self.limit)
        if since is not None:
            rows = [t for t in rows if t.triggered_at and t.triggered_at >= since]
        rules = {r.id: r for r in self.rule_repo.list_rules()}

        groups: Dict[str, Dict[str, Any]] = {}
        for t in rows:
            sym = str(t.symbol).split(".")[0]
            g = groups.setdefault(sym, {"symbol": sym, "count": 0, "items": [], "dispositions": {}})
            g["count"] += 1
            g["dispositions"][t.disposition] = g["dispositions"].get(t.disposition, 0) + 1
            rule = rules.get(t.rule_id)
            cond = t.condition or {}
            params = cond.get("params") or {}
            hint = (getattr(rule, "action_hint", None) or {}) if rule is not None else {}
            ctx = (getattr(rule, "context", None) or "") if rule is not None else ""
            g["items"].append({
                "trigger_id": t.id,
                "rule_id": t.rule_id,
                "disposition": t.disposition,
                "trigger_price": float(t.trigger_price) if t.trigger_price is not None else None,
                "triggered_at": t.triggered_at.isoformat() if t.triggered_at else None,
                "condition": ("%s %s %s" % (cond.get("type"), params.get("direction", ""),
                                           params.get("price", params.get("pct", "")))).strip(),
                "trigger_level": hint.get("trigger_level"),
                "suggested_action": hint.get("action_on_trigger"),
                "intent": getattr(rule, "intent", None),
                "lifecycle_stage": getattr(rule, "lifecycle_stage", None),
                "next_action_hint": getattr(rule, "next_action_hint", None),
                "plan": ctx[:160],
                "reason": (t.disposition_reason or "")[:120],
            })

        lines: List[str] = []
        for sym, g in sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True):
            first = min((i["triggered_at"] or "") for i in g["items"])
            disp = "/".join("%s×%d" % (k, v) for k, v in sorted(g["dispositions"].items()))
            lines.append("[%s] %d条（%s）首发 %s" % (sym, g["count"], disp, first[11:19] if first else "-"))
            for it in g["items"][:4]:
                lines.append("  - #%s 规则%s %s/%s %s 现价%s%s" % (
                    it["trigger_id"], it["rule_id"], it["trigger_level"] or "L1",
                    it["suggested_action"] or "-", it["condition"], it["trigger_price"],
                    (" | 预案：" + it["plan"]) if it["plan"] else ""))
            if g["count"] > 4:
                lines.append("  … 另有 %d 条同标的触发" % (g["count"] - 4))

        by_disp: Dict[str, int] = {}
        for t in rows:
            by_disp[t.disposition] = by_disp.get(t.disposition, 0) + 1

        return {
            "gate": len(rows) > 0,
            "count": len(rows),
            "by_disposition": by_disp,
            "group_count": len(groups),
            "groups": list(groups.values()),
            "text": chr(10).join(lines),
        }

    # ── 唤醒门（引擎 loop 调用）────────────────────────────────
    def maybe_wake(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now()
        if not self.is_trading_time(now):
            return {"woke": False, "reason": "非交易时段"}
        state = self._load_state()
        last_at, wake_date, wake_count = state["last_wake_at"], state["wake_date"], state["wake_count"]
        if wake_date != now.date():
            wake_count = 0
        if last_at is not None and (now - last_at).total_seconds() < self.min_interval_sec:
            return {"woke": False, "reason": "距上次唤醒 %.0fs < %ds" % ((now - last_at).total_seconds(), self.min_interval_sec)}
        if wake_count >= self.daily_cap:
            return {"woke": False, "reason": "当日唤醒已达上限 %d/%d" % (wake_count, self.daily_cap)}
        digest = self.build_digest(since=last_at)
        if not digest["gate"]:
            return {"woke": False, "reason": "自上次唤醒以来无待处置触发", "count": 0}
        if self.agent_service is None:
            return {"woke": False, "reason": "agent 通道未注入", "count": digest["count"]}
        ok = self.agent_service.notify_agent("watch_digest", {
            "count": digest["count"],
            "group_count": digest["group_count"],
            "by_disposition": digest["by_disposition"],
            "since": last_at.isoformat() if last_at else None,
            "digest": digest["text"],
            "instruction": (
                "按标的处置待处置触发：可自决的 PATCH /api/watch/triggers/{id} 置 handled 并写动作与结果；"
                "判不动的置 ignored，reason 必须含「为什么不动 + 下次什么条件下才动(NEXT)」；"
                "需用户决策的不要替用户决定，留在待决策队列由交互会话用 ask_user_question 拉起；"
                "遵守 R-001~R-009 与交易宪法。"
            ),
        })
        if ok:
            self._save_wake(now)
            logger.info("盯盘摘要已唤醒 agent", count=digest["count"], groups=digest["group_count"])
            return {"woke": True, "count": digest["count"], "group_count": digest["group_count"]}
        return {"woke": False, "reason": "唤醒通道失败（不写状态，下次重试）", "count": digest["count"]}
