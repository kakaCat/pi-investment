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


#: 无账户归属的触发（规则缺 linked_account）——单独成桶投默认 agent，绝不静默丢弃
UNASSIGNED = "__unassigned__"


class WatchDigestService:
    """待处置触发的摘要与唤醒门（引擎 loop 调用 maybe_wake）"""

    def __init__(self, trigger_repo, rule_repo, agent_service=None, state_repo=None,
                 market_watch_service=None,
                 min_interval_sec: int = 1500, daily_cap: int = 8, limit: int = 200):
        self.trigger_repo = trigger_repo
        self.rule_repo = rule_repo
        self.agent_service = agent_service
        # 端口注入（ADR-001）：状态持久化交给 IWatchDigestStateRepository 适配器，
        # 应用层不得 get_engine()/裸 SQL
        self.state_repo = state_repo
        # 市场状态摘要（P6）：agent 由此一眼看到"市场发生了什么"，不必再逐个工具取数
        self.market_watch_service = market_watch_service
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

    def build_digest(self, since: Optional[datetime] = None,
                     account: Optional[str] = None) -> Dict[str, Any]:
        """按**账户 × 标的**聚合的待处置摘要（路由与唤醒共用同一实现，避免两处口径）

        2026-09-11（w-aebfddcd）：账户是投送维度（哪个 agent 接手），因此**同一标的被两个
        账户盯盘时绝不合并**——合并 = 把 A 账户的止损预案投给 B 账户的 agent。
        每条规则应先有 linked_account（账户归属）；无归属的进"未归属"桶并显式暴露。
        """
        from domain.watch.services.disposition import UNRESOLVED
        rows = self.trigger_repo.list_triggers(dispositions=UNRESOLVED, limit=self.limit)
        if since is not None:
            rows = [t for t in rows if t.triggered_at and t.triggered_at >= since]
        rules = {r.id: r for r in self.rule_repo.list_rules()}

        groups: Dict[str, Dict[str, Any]] = {}
        for t in rows:
            sym = str(t.symbol).split(".")[0]
            rule = rules.get(t.rule_id)
            acct = getattr(rule, "linked_account", None) if rule is not None else None
            if account is not None and acct != account:
                continue
            key = "%s|%s" % (acct or "-", sym)
            g = groups.setdefault(key, {"symbol": sym, "account": acct, "count": 0,
                                        "items": [], "dispositions": {}})
            g["count"] += 1
            g["dispositions"][t.disposition] = g["dispositions"].get(t.disposition, 0) + 1
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
                # 账户归属：**投送 agent 的唯一决策输入**（与消息频道无关，见 WatchDeliveryPolicy）
                "account": getattr(rule, "linked_account", None),
                "scope": getattr(rule, "scope", None),
                "lifecycle_stage": getattr(rule, "lifecycle_stage", None),
                "next_action_hint": getattr(rule, "next_action_hint", None),
                "plan": ctx[:160],
                "reason": (t.disposition_reason or "")[:120],
            })

        lines: List[str] = []
        for _key, g in sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True):
            first = min((i["triggered_at"] or "") for i in g["items"])
            disp = "/".join("%s×%d" % (k, v) for k, v in sorted(g["dispositions"].items()))
            acct_tag = ("[%s] " % g["account"]) if g["account"] else "[未归属账户] "
            lines.append(acct_tag + "[%s] %d条（%s）首发 %s" % (
                g["symbol"], g["count"], disp, first[11:19] if first else "-"))
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

        market_text = ""
        if self.market_watch_service is not None:
            try:
                market_text = self.market_watch_service.summary_text() or ""
            except Exception as e:
                logger.warning("市场摘要生成失败", error=str(e))

        by_account: Dict[str, int] = {}
        for g in groups.values():
            k = g["account"] or "未归属"
            by_account[k] = by_account.get(k, 0) + g["count"]

        return {
            "gate": sum(g["count"] for g in groups.values()) > 0,
            "by_account": by_account,
            "unassigned": sum(g["count"] for g in groups.values() if not g["account"]),
            "market_summary": market_text,
            "count": sum(g["count"] for g in groups.values()),
            "by_disposition": by_disp,
            "group_count": len(groups),
            "groups": list(groups.values()),
            "text": (market_text + chr(10) + chr(10) if market_text else "") + chr(10).join(lines),
        }

    # ── 按账户分段（投送维度 = 账户；一个账户一份摘要）────────────
    @staticmethod
    def _segments(digest: dict) -> Dict[str, dict]:
        """把摘要按账户拆开：{账户 or UNASSIGNED: 子摘要}

        账户是**投送维度**（谁接手），所以不能把多账户混成一份唤醒——那等于让 A 账户的
        agent 处置 B 账户的仓位。无法归属的进 UNASSIGNED 桶并显式投给默认 agent（不漏）。
        """
        segs: Dict[str, dict] = {}
        for g in digest.get("groups") or []:
            key = g.get("account") or UNASSIGNED
            seg = segs.setdefault(key, {"count": 0, "group_count": 0, "groups": [],
                                        "by_disposition": {}, "by_account": {}})
            seg["groups"].append(g)
            seg["count"] += g.get("count", 0)
            seg["group_count"] += 1
            seg["by_account"][key] = seg["by_account"].get(key, 0) + g.get("count", 0)
            for d, n in (g.get("dispositions") or {}).items():
                seg["by_disposition"][d] = seg["by_disposition"].get(d, 0) + n
        for seg in segs.values():
            seg["text"] = chr(10).join(WatchDigestService._group_lines(seg["groups"]))
        return segs

    @staticmethod
    def _group_lines(groups) -> List[str]:
        lines: List[str] = []
        for g in sorted(groups, key=lambda x: x.get("count", 0), reverse=True):
            first = min((i.get("triggered_at") or "") for i in g.get("items") or [""]) or ""
            disp = "/".join("%s×%d" % (k, v) for k, v in sorted((g.get("dispositions") or {}).items()))
            acct_tag = ("[%s] " % g.get("account")) if g.get("account") else ""
            lines.append(acct_tag + "[%s] %d条（%s）首发 %s" % (
                g.get("symbol"), g.get("count", 0), disp, first[11:19] if first else "-"))
            for it in (g.get("items") or [])[:4]:
                lines.append("  - #%s 规则%s %s/%s %s 现价%s%s" % (
                    it.get("trigger_id"), it.get("rule_id"), it.get("trigger_level") or "L1",
                    it.get("suggested_action") or "-", it.get("condition"), it.get("trigger_price"),
                    (" | 预案：" + it.get("plan")) if it.get("plan") else ""))
            if g.get("count", 0) > 4:
                lines.append("  … 另有 %d 条同标的触发" % (g.get("count", 0) - 4))
        return lines

    def _resolve_target(self, account: Optional[str], category: Optional[str] = None) -> str:
        """账户 → 处置 agent（决策在 domain 策略；本方法只做调用，**不读频道码**）"""
        from domain.notification.policies.watch_delivery_policy import WatchDeliveryPolicy
        return WatchDeliveryPolicy().resolve(account=account, category=category)

    def _resolve_autonomy(self, account: Optional[str]) -> str:
        """账户 → 授权等级（agent 自有账户可自主操作；用户账户只提醒）"""
        from domain.notification.policies.watch_delivery_policy import WatchDeliveryPolicy
        return WatchDeliveryPolicy().resolve_autonomy(account)

    @staticmethod
    def _instruction(account: Optional[str], autonomy: Optional[str] = None) -> str:
        """唤醒指令：账户作用域纪律 + **授权等级**（用户 2026-09-11 定调）

        授权按账户给：agent 自有账户（agent_virtual/agent_brain）agent 自己操作；
        用户账户（user_main_simulation）只提醒、不得下单。未知账户兜底只提醒。
        """
        from domain.notification.policies.watch_delivery_policy import AUTONOMOUS, REMIND_ONLY
        if autonomy == AUTONOMOUS:
            authority = ("本账户是 **agent 自有账户**：**你可以自主操作**（含下单），"
                         "按交易宪法与 R-001~R-009 执行，下单 reason 写明规则ID+数据依据，"
                         "并用 decision_audit 留痕。")
        elif autonomy == REMIND_ONLY:
            authority = ("本账户**属于用户（真身）**：你**不得下单**，只做提醒、预案更新与规则维护；"
                         "需要交易时用 ask_user_question 拉起用户确认，不得替用户决定。")
        else:
            authority = "授权未明确：按最保守处理——只提醒，不下单。"
        # 账户为空是**规则数据缺陷**（不是投送模式）：照常唤醒 agent，但第一优先是把归属补齐。
        scope = ("本摘要仅属于账户 **%s**：所有账户查询/交易工具必须显式传 account_name=\"%s\"，"
                 "禁止操作其他账户。" % (account, account)) if account else (
                 "⚠️ 本摘要的规则**缺账户归属（linked_account）＝数据缺陷**：第一优先是判定归属，"
                 "并 PATCH /api/watch/rules/{id} 补 linked_account（盯盘信息必须归属 agent_virtual / "
                 "agent_brain / v13_simulation / user_main_simulation 之一）；补归属前不得下单"
                 "（无账户无法交易），也不得把本摘要当作已处置。")
        return (
            scope + authority +
            "按标的处置待处置触发：可自决的 PATCH /api/watch/triggers/{id} 置 handled 并写动作与结果；"
            "判不动的置 ignored，reason 必须含「为什么不动 + 下次什么条件下才动(NEXT)」；"
            "遵守 R-001~R-009 与交易宪法。"
        )

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

        # 按账户分段投送（2026-09-11，w-aebfddcd）：一个账户一份唤醒，投给该账户的处置 agent。
        # 预算按"唤醒次数"计（一次唤醒 = 一个账户），上限仍是 daily_cap。
        segments = self._segments(digest)
        woke_accounts, failed, delivered, defects = [], [], 0, []
        for acc_key, seg in segments.items():
            acct = None if acc_key == UNASSIGNED else acc_key
            if acc_key == UNASSIGNED:
                # 账户为空**不是一种投送模式，而是规则数据缺陷**（用户 2026-09-11 纠正：
                # 「没有账户不能交易 → 不唤醒 agent，只发飞书」是 bug —— 那等于把缺陷藏起来）。
                # 正确做法：照常唤醒 agent，并把"补 linked_account"作为第一优先任务交给它。
                defects.append({
                    "count": seg["count"],
                    "rule_ids": sorted({it.get("rule_id") for g in seg["groups"]
                                        for it in (g.get("items") or []) if it.get("rule_id")}),
                })
            if wake_count >= self.daily_cap:
                break
            target_agent = self._resolve_target(acct)
            autonomy = self._resolve_autonomy(acct)
            payload = {
                "account_name": acct,
                "count": seg["count"],
                "group_count": seg["group_count"],
                "by_disposition": seg["by_disposition"],
                "by_account": seg["by_account"],
                "unassigned": acc_key == UNASSIGNED,
                "since": last_at.isoformat() if last_at else None,
                "digest": seg["text"],
                "target_agent": target_agent,
                # 授权等级（账户维度）：autonomous=agent 自己操作 / remind_only=只提醒不下单
                "autonomy": autonomy,
                "instruction": self._instruction(acct, autonomy),
            }
            if acc_key == UNASSIGNED:
                payload["data_defect"] = (
                    "规则缺 linked_account（账户归属缺失，属数据缺陷）："
                    "先判定归属并 PATCH /api/watch/rules/{id} 补 linked_account，再按账户处置；"
                    "补归属前不得下单（无账户无法交易），也不得把本摘要当作已完成。")
            try:
                ok = self.agent_service.notify_agent("watch_digest", payload, target=target_agent)
            except TypeError:
                # 兼容旧实现（notify_agent(event, data)）——不因签名差异丢掉唤醒
                ok = self.agent_service.notify_agent("watch_digest", payload)
            if ok:
                wake_count += 1
                delivered += 1
                self._save_wake(now)
                woke_accounts.append(acc_key)
            else:
                failed.append(acc_key)
        if delivered:
            logger.info("盯盘摘要已按账户唤醒", accounts=woke_accounts,
                        count=digest["count"], groups=digest["group_count"],
                        unassigned_defects=sum(d["count"] for d in defects))
            return {"woke": True, "count": digest["count"], "group_count": digest["group_count"],
                    "accounts": woke_accounts, "failed": failed, "wakes": delivered,
                    "data_defects": defects}
        return {"woke": False, "reason": "唤醒通道失败（不写状态，下次重试）",
                "count": digest["count"], "failed": failed, "data_defects": defects}
