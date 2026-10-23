"""市场级盯盘服务（REQ-f08def P6，RFC 014 v3 §1.1/§1.3，2026-09-11，w-c8cae280）

用户的定位：盯盘是「紧盯市场情况的工具」。此前引擎只能盯个股，指数/板块/情绪/量能进不来。

职责（应用层编排；判定在领域服务 MarketRuleEvaluator，取数在适配器 MarketStateProvider）：
  1) scan_market_rules：评估 scope=market/sector 的启用规则，把**评估结果**（含 quote
     轻量投影）交回引擎——触发后的闩锁/冷却/日上限/抑噪/升级/处置/去重/通知/待办
     全部走引擎 _process_condition 主流水线（2026-10-19 并入：此前本服务自行落库，
     notified=False 写死、闩锁纯内存、不占预算、不建待办，escalated 也无人接收）。
  2) summary_text：产出「市场状态摘要」，供摘要唤醒时内嵌（agent 不必再逐个工具取数）。

闩锁/冷却语义与个股完全一致：由引擎 TriggerJudge 承担（运行态持久化后重启不重报）。
"""
from datetime import datetime
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import structlog

from qs_watch.domain.watch.services.market_rule_evaluator import MarketRuleEvaluator

logger = structlog.get_logger(__name__)

MARKET_SCOPES = ("market", "sector")


class MarketWatchService:

    def __init__(self, rule_repo, trigger_repo, state_provider=None, evaluator=None,
                 trigger_interval_sec: int = 300, held_sector_map=None):
        self.rule_repo = rule_repo
        # trigger_repo 保留在签名里（装配兼容）；落库自 2026-10-19 起由引擎主流水线承担
        self.trigger_repo = trigger_repo
        self.state_provider = state_provider
        self.evaluator = evaluator or MarketRuleEvaluator()
        self.trigger_interval_sec = trigger_interval_sec
        self._last_scan_at: Optional[datetime] = None
        # 持仓板块映射（P2 联动）：HeldSectorMapService；None = 未装配（held_sector_pct 恒 skipped）
        self.held_sector_map = held_sector_map

    def refresh_held_boards(self, force: bool = False) -> None:
        """sidecar 每日刷新入口（重建映射是重活——逐板块外呼，绝不在 tick 热路径跑）。"""
        if self.held_sector_map is None:
            return
        self.held_sector_map.refresh(force=force)

    # ── 市场级规则扫描 ────────────────────────────────────────
    def scan_market_rules(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """评估市场级规则，返回摘要 + evaluated 候选清单（引擎主流水线的输入）。

        每条 evaluated：{rule, idx, cond, result, quote}——quote 是指标值的轻量投影
        （price=指标值；prev_close/volume/change_pct=None，市场条件没有这些维度）。
        未触发项也在清单内：闩锁的「回落重新武装」判定在引擎侧（TriggerJudge）。
        """
        now = now or datetime.now()
        if self.state_provider is None:
            return {"skipped": "未注入市场状态端口", "scanned": 0, "triggered": 0,
                    "evaluated": []}
        if (self._last_scan_at is not None
                and (now - self._last_scan_at).total_seconds() < self.trigger_interval_sec):
            return {"skipped": "未到扫描间隔", "scanned": 0, "triggered": 0,
                    "evaluated": []}
        self._last_scan_at = now

        state = self.state_provider.get_state()
        # P2 持仓板块联动：held_sector_pct 需要「板块→持仓」映射；MarketState 是 frozen
        # 快照，用 replace 挂上（无映射服务时挂空——评估器据此 skipped，诚实标注）。
        if self.held_sector_map is not None:
            state = replace(state, held_boards=self.held_sector_map.held_boards())
        rules = [r for r in self.rule_repo.list_enabled()
                 if (getattr(r, "scope", None) in MARKET_SCOPES)]
        evaluated: List[Dict[str, Any]] = []
        triggered_n = 0
        skipped_data = 0

        for rule in rules:
            for idx, cond in enumerate(getattr(rule, "conditions", None) or []):
                try:
                    res = self.evaluator.evaluate(cond, state)
                except Exception as e:
                    logger.error("市场级条件评估异常", rule_id=rule.id, error=str(e))
                    continue
                if res.skipped:
                    skipped_data += 1
                    continue
                if res.triggered:
                    triggered_n += 1
                evaluated.append({"rule": rule, "idx": idx, "cond": cond,
                                  "result": res,
                                  "quote": self._quote_like(rule, res)})

        return {"scanned": len(rules), "triggered": triggered_n,
                "skipped_no_data": skipped_data, "degraded": list(state.degraded),
                "evaluated": evaluated}

    @staticmethod
    def _quote_like(rule, res) -> Any:
        """市场评估结果 → 个股 quote 的轻量投影（主流水线的适配层）。

        price=指标值（触发落库的 trigger_price 与通知里的「现价」位都用它；
        市场条件的语义在 result.message 里已完整表达）。其余维度市场快照没有，
        一律 None——freshness/volume_surge 等个股专属判定对 None 天然短路。
        """
        return SimpleNamespace(
            symbol=getattr(rule, "symbol", ""),
            price=float(res.value) if res.value is not None else 0.0,
            name=None, prev_close=None, change_pct=None, volume=None,
        )

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
