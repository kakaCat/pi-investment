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
from datetime import datetime
import hashlib
from typing import Any, Dict, List, Optional

import structlog

from qs_trading.domain.trading.services.market_session_policy import MarketSessionPolicy

logger = structlog.get_logger(__name__)


#: 无账户且需要账户的触发 = 数据缺陷；全局观察 = 合法的无账户业务模式。
UNASSIGNED = "__unassigned__"
GLOBAL_OBSERVATION = "__global_observation__"


def _missing_account_is_defect(rule) -> bool:
    """无账户是否非法：入场/交易需要账户；趋势、消息等全局观察不需要。"""
    if rule is None:
        return True
    intent = str(getattr(rule, 'intent', '') or '')
    hint = getattr(rule, 'action_hint', None) or {}
    action = str(hint.get('action_on_trigger') or hint.get('type') or '')
    return intent == 'entry' or action in ('entry', 'buy', 'sell', 'trade')


def _is_global_group(group: dict) -> bool:
    return not group.get('account') and group.get('ownership') == 'global_observation'


class WatchDigestService:
    """待处置触发的摘要与唤醒门（引擎 loop 调用 maybe_wake）"""

    def __init__(self, trigger_repo, rule_repo, agent_service=None, state_repo=None,
                 market_watch_service=None,
                 min_interval_sec: int = 1500, daily_cap: int = 8, limit: int = 200,
                 dry_run: bool = False):
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
        # 影子模式（2026-09-11，w-aebfddcd）：照常算"该唤醒谁、带什么摘要与授权"，
        # **不发唤醒、不消耗唤醒预算**，只落结构日志供人工复核。用途：真开之前的 24h 观察。
        self.dry_run = dry_run
        self._shadow_last_at = None
        # 旧测试/自定义状态端口没有持久 pending 方法时的兼容副本；生产端口必须落库。
        self._volatile_pending: Dict[str, Dict[str, Any]] = {}

    # ── 交易时段门 ────────────────────────────────────────────
    @staticmethod
    def is_trading_time(now: datetime) -> bool:
        """交易时段门（RFC 016 §8.1：时段判定收敛到 `MarketSessionPolicy`）

        日级仍用 weekday 近似（不引 DB 依赖），待 D9 统一为 `TradingDayGuard`。

        与原实现的差异**仅在子分钟端点**：11:30:45 / 15:00:30 原按精确 `time` 比较判
        False，现按整分钟口径判 True（端点闭合）——与盯盘引擎 tick、盘中巡检闸门同口径。
        影响：收盘那一分钟内的摘要唤醒不再被推迟到次日开盘（仍受队列/间隔/日预算三道门约束）。
        """
        return MarketSessionPolicy.is_market_open(
            MarketSessionPolicy.phase_for(now.time(), is_trading_day=now.weekday() < 5)
        )

    # ── 状态（落库，重启不清零）──────────────────────────────
    def _load_state(self):
        if self.state_repo is None:
            return {"last_wake_at": None, "wake_date": None, "wake_count": 0,
                    "wake_marks": {}}
        state = self.state_repo.load_state()
        state.setdefault("wake_marks", {})   # 旧端口实现/fake 无逐账户水位（兼容）
        state.setdefault("pending_batches", {})
        return state

    def _save_wake(self, now, account=None) -> bool:
        if self.state_repo is None:
            return True
        try:
            result = self.state_repo.save_wake(now, account=account)
            return result is not False  # 旧 fake 返回 None；生产适配器显式 True/False
        except TypeError:
            # 兼容旧端口实现/fake（无逐账户水位形参）：退化为全局水位
            try:
                result = self.state_repo.save_wake(now)
                return result is not False
            except Exception as exc:  # noqa: BLE001
                logger.error('摘要水位保存失败，固定 pending 保留', error=str(exc))
                return False
        except Exception as exc:  # noqa: BLE001
            logger.error('摘要水位保存失败，固定 pending 保留', error=str(exc))
            return False

    def _save_wake_mark(self, account, at) -> None:
        """钉某账户水位（失败不推进）。旧端口/fake 无此方法时降级为不动（日志留痕）。"""
        if self.state_repo is None:
            return
        saver = getattr(self.state_repo, 'save_wake_mark', None)
        if not callable(saver):
            logger.debug('状态端口不支持逐账户水位（save_wake_mark 缺失），按旧语义运行')
            return
        try:
            saver(account, at)
        except Exception as e:  # noqa: BLE001 - 水位失败不阻断唤醒主流程
            logger.warning('逐账户水位钉入失败（下轮按全局水位重试）',
                           account=account, error=str(e))

    def _save_pending_batch(self, account: str, batch: Dict[str, Any]) -> bool:
        """网络前持久化固定重试批次；持久化失败时宁可不发送，也不制造新幂等键。"""
        saver = getattr(self.state_repo, 'save_pending_batch', None)
        if not callable(saver):
            self._volatile_pending[str(account)] = batch
            return True
        try:
            result = saver(str(account), batch)
            if result is False:
                raise RuntimeError('save_pending_batch 返回 False')
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error('摘要重试批次持久化失败，本轮不发送', account=account, error=str(exc))
            return False

    def _clear_pending_batch(self, account: str, expected_event_id: str) -> bool:
        clearer = getattr(self.state_repo, 'clear_pending_batch', None)
        try:
            if callable(clearer):
                result = clearer(str(account), expected_event_id)
                if result is False:
                    raise RuntimeError('clear_pending_batch 返回 False')
            current = self._volatile_pending.get(str(account))
            current_id = str(((current or {}).get('payload') or {}).get('event_id') or '')
            if current is not None and current_id == expected_event_id:
                self._volatile_pending.pop(str(account), None)
            return True
        except Exception as exc:  # noqa: BLE001
            # 保留持久 pending：下轮同 event_id 重放会被 /wake 去重，随后再尝试清理。
            logger.error('摘要已完成批次清理失败，将以同幂等键复核', account=account, error=str(exc))
            return False

    def _claim_digest_batch(self, payload: Dict[str, Any], at: datetime) -> bool:
        claim = getattr(self.trigger_repo, 'claim_digest_batch', None)
        if not callable(claim):
            return True  # 仅旧测试/内存端口；生产端口声明并实现发送前原子认领
        ids = sorted({int(value) for value in payload.get('trigger_ids') or []})
        if not ids:
            return False
        try:
            result = claim(ids, str(payload['event_id']), at)
            if result is False:
                logger.info('摘要批次已被另一 worker 认领或确认',
                            event_id=payload.get('event_id'))
                return False
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error('摘要批次认领异常，禁止网络投递',
                         event_id=payload.get('event_id'), error=str(exc))
            return False

    def _mark_digest_delivered(self, payload: Dict[str, Any], at: datetime) -> bool:
        marker = getattr(self.trigger_repo, 'mark_digest_delivered', None)
        if not callable(marker):
            return True  # 旧内存仓储走兼容水位路径；生产适配器必须提供逐 trigger 确认
        ids = sorted({int(value) for value in payload.get('trigger_ids') or []})
        if not ids:
            logger.error('摘要批次没有 trigger_ids，拒绝清理 pending')
            return False
        try:
            result = marker(ids, str(payload['event_id']), at)
            if result is False:
                raise RuntimeError('mark_digest_delivered 返回 False')
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error('摘要逐 trigger 确认失败，固定 pending 保留',
                         event_id=payload.get('event_id'), error=str(exc))
            return False

    @staticmethod
    def _pending_event_id(account: str, now: datetime, trigger_ids: List[int]) -> str:
        raw = f'{account}|{now.isoformat()}|{",".join(map(str, trigger_ids))}'
        return 'watch_digest:sha256:' + hashlib.sha256(raw.encode('utf-8')).hexdigest()

    @staticmethod
    def _parse_wake_marks(raw) -> Dict[str, datetime]:
        """wake_marks（{账户: ISO 串}）→ {账户: datetime}；坏值跳过（不阻断唤醒门）"""
        marks: Dict[str, datetime] = {}
        for acct, iso in (raw or {}).items():
            try:
                marks[str(acct)] = datetime.fromisoformat(str(iso))
            except (TypeError, ValueError):
                logger.warning('逐账户水位格式非法，按无水位处理', account=acct, raw=iso)
        return marks

    @staticmethod
    def _effective_since(marks: Dict[str, datetime], last_at) -> Optional[datetime]:
        """增量段起点 = 全部水位中最旧的（失败账户的水位保持旧值 → 其触发留在段内）。

        迁移期兼容：wake_marks 为空时退化为全局 last_at（行为与改前一致）。
        """
        candidates = list(marks.values()) + ([last_at] if last_at is not None else [])
        return min(candidates) if candidates else None

    @staticmethod
    def _segment_has_new(seg: Dict[str, Any], mark: datetime) -> bool:
        """该账户分段里是否有水位之后的新触发（ISO 串同格式字典序可比）。"""
        iso = mark.isoformat()
        for g in seg.get("groups") or []:
            for it in (g.get("items") or []):
                if (it.get("triggered_at") or "") >= iso:
                    return True
        return False

    @staticmethod
    def _segment_oldest(seg: Dict[str, Any]) -> Optional[datetime]:
        """分段内最旧触发时间（首轮失败时的水位钉值：该账户本轮窗口的真实起点）。"""
        oldest = None
        for g in seg.get("groups") or []:
            for it in (g.get("items") or []):
                ts = it.get("triggered_at") or None
                if ts and (oldest is None or ts < oldest):
                    oldest = ts
        if oldest is None:
            return None
        try:
            return datetime.fromisoformat(oldest)
        except (TypeError, ValueError):
            return None

    def build_digest(self, since: Optional[datetime] = None,
                     account: Optional[str] = None,
                     exclude_digest_delivered: bool = False,
                     rule_ids: Optional[List[int]] = None,
                     exclude_rule_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """按**账户 × 标的**聚合的待处置摘要（路由与唤醒共用同一实现，避免两处口径）

        2026-09-11（w-aebfddcd）：账户是投送维度（哪个 agent 接手），因此**同一标的被两个
        账户盯盘时绝不合并**——合并 = 把 A 账户的止损预案投给 B 账户的 agent。
        每条规则应先有 linked_account（账户归属）；无归属的进"未归属"桶并显式暴露。
        2026-10-16（REQ-261016155500-4f2a wt:engine:4）积压可见：since 增量段只覆盖
        「上次唤醒后」的触发，更早的未处置触发此前完全不可见（库表越积越多、摘要却显示
        无事）。现另算 backlog 段（早于 since 的 UNRESOLVED 计数 + 最旧时间），
        结果带 backlog 字段、文本带积压行——溢出（超 limit 截断）一并计入计数。
        """
        from qs_watch.domain.watch.services.disposition import UNRESOLVED
        rules = {r.id: r for r in self.rule_repo.list_rules()}
        if rule_ids is None and account is not None:
            rule_ids = [int(rule_id) for rule_id, rule in rules.items()
                        if getattr(rule, 'linked_account', None) == account]
        query: Dict[str, Any] = {'dispositions': UNRESOLVED, 'limit': self.limit}
        if rule_ids is not None:
            query['rule_ids'] = rule_ids
        if exclude_rule_ids is not None:
            query['exclude_rule_ids'] = exclude_rule_ids
        if exclude_digest_delivered:
            query['digest_unacked'] = True  # 生产仓储必须在 SQL LIMIT 前过滤
        rows = self.trigger_repo.list_triggers(**query)

        # 积压段：早于 since 的未处置触发（与 limit 截断无关，独立计数）
        backlog: Dict[str, Any] = {'count': 0, 'oldest_at': None}
        if since is not None:
            counter = getattr(self.trigger_repo, 'count_older_unresolved', None)
            if callable(counter):
                try:
                    backlog = counter(since, UNRESOLVED)
                except Exception as e:  # noqa: BLE001 - 积压统计失败不阻断摘要
                    logger.warning('积压统计失败（摘要继续，积压不可见）', error=str(e))
        if since is not None:
            rows = [t for t in rows if t.triggered_at and t.triggered_at >= since]

        groups: Dict[str, Dict[str, Any]] = {}
        for t in rows:
            detail = getattr(t, 'detail', None) or {}
            if exclude_digest_delivered and isinstance(detail, dict) and detail.get('digest_event_id'):
                continue
            sym = str(t.symbol).split(".")[0]
            rule = rules.get(t.rule_id)
            acct = getattr(rule, "linked_account", None) if rule is not None else None
            if account is not None and acct != account:
                continue
            ownership = ('account' if acct else
                         'unassigned' if _missing_account_is_defect(rule) else 'global_observation')
            # 同标的的“合法全局观察”和“缺账户入场”不得混成一桶。
            key = "%s|%s|%s" % (acct or "-", ownership, sym)
            g = groups.setdefault(key, {"symbol": sym, "account": acct, "ownership": ownership,
                                        "count": 0, "items": [], "dispositions": {}})
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
            acct_tag = (("[%s] " % g["account"]) if g["account"] else
                        "[全局观察] " if _is_global_group(g) else "[未归属账户·数据缺陷] ")
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
            k = g["account"] or ("全局观察" if _is_global_group(g) else "未归属")
            by_account[k] = by_account.get(k, 0) + g["count"]

        # 积压行（wt:engine:4）：早于 since 的未处置触发不计入上面的分组，单独点名，
        # 防止「未处置清单越积越多、摘要却显示无事」的隐形积压。
        if backlog.get("count"):
            oldest = backlog.get("oldest_at")
            oldest_text = (oldest.strftime("%m-%d %H:%M")
                           if hasattr(oldest, "strftime") else "-")
            lines.insert(0, "⚠️ 积压：另有 %d 条更早的未处置触发（最旧 %s）未入本摘要"
                         % (backlog["count"], oldest_text))

        return {
            "gate": sum(g["count"] for g in groups.values()) > 0,
            "by_account": by_account,
            "unassigned": sum(g["count"] for g in groups.values()
                               if not g["account"] and not _is_global_group(g)),
            "global_observation": sum(g["count"] for g in groups.values() if _is_global_group(g)),
            "market_summary": market_text,
            "count": sum(g["count"] for g in groups.values()),
            "backlog": {"count": int(backlog.get("count") or 0),
                        "oldest_at": (backlog.get("oldest_at").isoformat()
                                      if hasattr(backlog.get("oldest_at"), "isoformat")
                                      else None)},
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
            key = g.get("account") or (GLOBAL_OBSERVATION if _is_global_group(g) else UNASSIGNED)
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

    def _wake_segments(self, since: Optional[datetime], supports_ack: bool) -> tuple:
        """生产 ACK 路径按投递桶独立 LIMIT，单账户失败不得占满其他账户窗口。"""
        if not supports_ack:
            digest = self.build_digest(since=since, exclude_digest_delivered=False)
            return self._segments(digest), digest.get('backlog')
        rules = list(self.rule_repo.list_rules())
        owned: Dict[str, List[int]] = {}
        for rule in rules:
            account = getattr(rule, 'linked_account', None)
            if account and getattr(rule, 'id', None) is not None:
                owned.setdefault(str(account), []).append(int(rule.id))
        all_owned_ids = sorted({rule_id for ids in owned.values() for rule_id in ids})
        global_ids = sorted(int(rule.id) for rule in rules
                            if not getattr(rule, 'linked_account', None)
                            and getattr(rule, 'id', None) is not None
                            and not _missing_account_is_defect(rule))
        scopes: List[tuple] = [
            (None, global_ids, None),  # 合法全局观察独立窗口
            (None, None, sorted(set(all_owned_ids + global_ids))),  # 未归属 + 孤儿触发
        ]
        scopes.extend((account, ids, None) for account, ids in sorted(owned.items()))
        segments: Dict[str, dict] = {}
        backlog = {'count': 0, 'oldest_at': None}
        for account, rule_ids, exclude_rule_ids in scopes:
            digest = self.build_digest(
                since=since, account=account, exclude_digest_delivered=True,
                rule_ids=rule_ids, exclude_rule_ids=exclude_rule_ids)
            current_backlog = digest.get('backlog') or {}
            backlog['count'] += int(current_backlog.get('count') or 0)
            oldest = current_backlog.get('oldest_at')
            if oldest and (backlog['oldest_at'] is None or oldest < backlog['oldest_at']):
                backlog['oldest_at'] = oldest
            for key, seg in self._segments(digest).items():
                if key not in segments:
                    segments[key] = seg
                    continue
                # 正常各 scope 不重叠；规则并发变更时合并而不是覆盖丢失触发。
                current = segments[key]
                current['groups'].extend(seg.get('groups') or [])
                current['count'] += seg.get('count', 0)
                current['group_count'] += seg.get('group_count', 0)
                for name, count in (seg.get('by_disposition') or {}).items():
                    current['by_disposition'][name] = current['by_disposition'].get(name, 0) + count
                for name, count in (seg.get('by_account') or {}).items():
                    current['by_account'][name] = current['by_account'].get(name, 0) + count
                current['text'] = chr(10).join(self._group_lines(current['groups']))
        return segments, backlog

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
        from qs_notification.domain.policies.watch_delivery_policy import WatchDeliveryPolicy
        return WatchDeliveryPolicy().resolve(account=account, category=category)

    @staticmethod
    def _is_strategy_managed(account: Optional[str]) -> bool:
        from qs_notification.domain.policies.watch_delivery_policy import WatchDeliveryPolicy
        return WatchDeliveryPolicy.is_strategy_managed(account)

    def _resolve_autonomy(self, account: Optional[str]) -> str:
        """账户 → 授权等级（agent 自有账户可自主操作；用户账户只提醒）"""
        from qs_notification.domain.policies.watch_delivery_policy import WatchDeliveryPolicy
        return WatchDeliveryPolicy().resolve_autonomy(account)

    @staticmethod
    def _instruction(account: Optional[str], autonomy: Optional[str] = None,
                     ownership: Optional[str] = None) -> str:
        """唤醒指令：账户作用域纪律 + **授权等级**（用户 2026-09-11 定调）

        授权按账户给：agent 自有账户（agent_virtual/agent_brain）agent 自己操作；
        用户账户（user_main_simulation）只提醒、不得下单。未知账户兜底只提醒。
        """
        from qs_notification.domain.policies.watch_delivery_policy import AUTONOMOUS, REMIND_ONLY
        if not account and ownership == 'global_observation':
            authority = "全局观察不属于任何用户账户：只提醒、不交易，不按用户账户语义处理。"
        elif autonomy == AUTONOMOUS:
            authority = ("本账户是 **agent 自有账户**：**你可以自主操作**（含下单），"
                         "按交易宪法与 R-001~R-009 执行，下单 reason 写明规则ID+数据依据，"
                         "并用 decision_audit 留痕。")
        elif autonomy == REMIND_ONLY:
            authority = ("本账户**属于用户（真身）**：你**不得下单**，只做提醒、预案更新与规则维护；"
                         "需要交易时用 ask_user_question 拉起用户确认，不得替用户决定。")
        else:
            authority = "授权未明确：按最保守处理——只提醒，不下单。"
        if account:
            scope = ("本摘要仅属于账户 **%s**：所有账户查询/交易工具必须显式传 account_name=\"%s\"，"
                     "禁止操作其他账户。" % (account, account))
        elif ownership == 'global_observation':
            scope = ("【全局观察·无账户】这是合法的非交易观察事件，不是缺账户缺陷。"
                     "只做结构复核与信息沉淀；不得据此交易，也不要求补 linked_account。")
        else:
            scope = ("⚠️ 本摘要的规则**缺账户归属（linked_account）＝数据缺陷**：第一优先是判定归属，"
                     "并 PATCH /api/watch/rules/{id} 补 linked_account；补归属前不得下单"
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
        try:
            state = self._load_state()
        except Exception as exc:  # noqa: BLE001
            logger.error('摘要状态读取异常，本轮禁止生成新事件', error=str(exc))
            return {'woke': False, 'reason': 'state_unavailable', 'error': str(exc)}
        if state.get('load_error'):
            logger.error('摘要状态不可读，本轮禁止生成新事件', error=state['load_error'])
            return {'woke': False, 'reason': 'state_unavailable', 'error': state['load_error']}
        last_at, wake_date, wake_count = state["last_wake_at"], state["wake_date"], state["wake_count"]
        marks = self._parse_wake_marks(state.get("wake_marks"))
        if wake_date != now.date():
            wake_count = 0
        if last_at is not None and (now - last_at).total_seconds() < self.min_interval_sec:
            return {"woke": False, "reason": "距上次唤醒 %.0fs < %ds" % ((now - last_at).total_seconds(), self.min_interval_sec)}
        if wake_count >= self.daily_cap:
            return {"woke": False, "reason": "当日唤醒已达上限 %d/%d" % (wake_count, self.daily_cap)}
        # 增量段起点按**逐账户水位**取最旧（2026-10-19）：此前全局水位被部分成功的
        # 账户推进，失败账户的触发被 since 过滤出增量段、只剩 backlog 计数，永久不可见。
        raw_pending = state.get('pending_batches') or {}
        if not isinstance(raw_pending, dict):
            return {'woke': False, 'reason': 'state_unavailable', 'error': 'pending_batches 不是 object'}
        supports_ack = (callable(getattr(self.trigger_repo, 'mark_digest_delivered', None))
                        and callable(getattr(self.trigger_repo, 'claim_digest_batch', None)))
        # 生产路径按 trigger.detail.digest_event_id 防重，不再用时间戳猜查询快照边界。
        # 因而延迟提交但 triggered_at 较旧的未确认事件，下一轮仍会进入候选。
        segments, digest_backlog = self._wake_segments(
            None if supports_ack else self._effective_since(marks, last_at), supports_ack)
        pending_batches = dict(raw_pending)
        pending_batches.update(self._volatile_pending)
        if not segments and not pending_batches:
            return {"woke": False, "reason": "自上次唤醒以来无待处置触发", "count": 0}
        digest_count = sum(int(seg.get('count') or 0) for seg in segments.values())
        digest_group_count = sum(int(seg.get('group_count') or 0) for seg in segments.values())
        if self.agent_service is None:
            return {"woke": False, "reason": "agent 通道未注入", "count": digest_count}

        # 按账户分段投送（2026-09-11，w-aebfddcd）：一个账户一份唤醒，投给该账户的处置 agent。
        # 预算按"唤醒次数"计（一次唤醒 = 一个账户），上限仍是 daily_cap。

        if self.dry_run:
            # 影子模式：同一冷却窗内最多记一次，避免每 tick 刷屏；不动库内状态（预算不消耗）
            if (self._shadow_last_at is not None
                    and (now - self._shadow_last_at).total_seconds() < self.min_interval_sec):
                return {"woke": False, "dry_run": True, "reason": "影子模式冷却窗内"}
            self._shadow_last_at = now
            plan = []
            for acc_key, seg in segments.items():
                acct = None if acc_key in (UNASSIGNED, GLOBAL_OBSERVATION) else acc_key
                if acct is not None and self._is_strategy_managed(acct):
                    plan.append({"account": acct, "count": seg["count"],
                                 "action": "skip", "reason": "策略账户：盯盘不介入"})
                    continue
                target = self._resolve_target(acct)
                autonomy = self._resolve_autonomy(acct)
                plan.append({"account": acct, "count": seg["count"], "action": "wake",
                             "target_agent": target, "autonomy": autonomy,
                             "groups": seg["group_count"]})
            logger.info("摘要门影子模式：本应唤醒如下（未真发，不消耗预算）",
                        plan=plan, unresolved=digest_count, groups=digest_group_count)
            return {"woke": False, "dry_run": True, "would_wake": plan,
                    "count": digest_count, "group_count": digest_group_count}

        woke_accounts, failed, delivered, defects, out_of_scope = [], [], 0, [], []
        account_keys = list(dict.fromkeys([*segments, *pending_batches]))
        for acc_key in account_keys:
            seg = segments.get(acc_key)
            pending = pending_batches.get(acc_key)
            acct = None if acc_key in (UNASSIGNED, GLOBAL_OBSERVATION) else acc_key
            if acc_key == UNASSIGNED and seg is not None:
                # 账户为空**不是一种投送模式，而是规则数据缺陷**（用户 2026-09-11 纠正：
                # 「没有账户不能交易 → 不唤醒 agent，只发飞书」是 bug —— 那等于把缺陷藏起来）。
                # 正确做法：照常唤醒 agent，并把"补 linked_account"作为第一优先任务交给它。
                defects.append({
                    "count": seg["count"],
                    "rule_ids": sorted({it.get("rule_id") for g in seg["groups"]
                                        for it in (g.get("items") or []) if it.get("rule_id")}),
                })
            if acc_key != UNASSIGNED and seg is not None and self._is_strategy_managed(acct):
                # 策略账户：交易由策略引擎执行，与盯盘无关（用户 2026-09-11）→ 不投递 agent，
                # 但要显式报告：策略账户**不该有盯盘规则**，出现即规则治理问题。
                out_of_scope.append({
                    "account": acct, "count": seg["count"],
                    "reason": "策略账户由策略执行，与盯盘无关：不投递 agent；该规则应清理或改归其他账户"})
                continue
            # 逐账户水位（2026-10-19）：该账户水位之后没有新触发 → 不唤醒、不消耗预算
            # （它的条目可能只是因别家失败把 effective_since 拉旧而再次被扫进来）。
            acct_mark = marks.get(acc_key) or last_at
            if pending is None and (seg is None or (not supports_ack and
                    acct_mark is not None and not self._segment_has_new(seg, acct_mark))):
                continue
            if wake_count >= self.daily_cap:
                break
            if pending is not None:
                # 原批次已失败/超时：逐字重放，期间新触发不得混入这个幂等事件。
                payload = dict(pending['payload'])
                target_agent = payload.get('target_agent')
                try:
                    through = datetime.fromisoformat(str(pending['through']))
                except (KeyError, TypeError, ValueError):
                    logger.error('摘要重试批次 through 非法，保留待人工复核', account=acc_key)
                    failed.append(acc_key)
                    continue
            else:
                target_agent = self._resolve_target(acct)
                autonomy = self._resolve_autonomy(acct)
                trigger_ids = sorted({item["trigger_id"] for group in seg["groups"]
                                      for item in group.get("items", [])
                                      if item.get("trigger_id") is not None})
                payload = {
                    "event_id": self._pending_event_id(acc_key, now, trigger_ids),
                    "account_name": acct,
                    "trigger_ids": trigger_ids,
                    "count": seg["count"],
                    "group_count": seg["group_count"],
                    "by_disposition": seg["by_disposition"],
                    "by_account": seg["by_account"],
                    "unassigned": acc_key == UNASSIGNED,
                    "global_observation": acc_key == GLOBAL_OBSERVATION,
                    "since": last_at.isoformat() if last_at else None,
                    "digest": seg["text"],
                    "backlog": digest_backlog,
                    "target_agent": target_agent,
                    "autonomy": autonomy,
                    "instruction": self._instruction(
                        acct, autonomy,
                        'global_observation' if acc_key == GLOBAL_OBSERVATION else 'account'),
                }
                if acc_key == UNASSIGNED:
                    payload["data_defect"] = (
                        "规则缺 linked_account（账户归属缺失，属数据缺陷）："
                        "先判定归属并 PATCH /api/watch/rules/{id} 补 linked_account，再按账户处置；"
                        "补归属前不得下单（无账户无法交易），也不得把本摘要当作已完成。")
                through = now
                if not self._save_pending_batch(acc_key, {
                        'payload': payload, 'through': through.isoformat()}):
                    failed.append(acc_key)
                    continue
            # 固定 pending 之后、网络之前原子认领；另一 worker 已认领时绝不能入队。
            if not self._claim_digest_batch(payload, through):
                failed.append(acc_key)
                continue
            try:
                ok = self.agent_service.notify_agent("watch_digest", payload, target=target_agent)
            except TypeError:
                # 兼容旧实现（notify_agent(event, data)）——不因签名差异丢掉唤醒
                ok = self.agent_service.notify_agent("watch_digest", payload)
            if ok:
                wake_count += 1
                delivered += 1
                # 先逐 trigger 持久确认，再推进观测水位；任一步失败都保留同一 pending。
                # 下轮只用原 event_id 复核 /wake，不会把已成功事件改名后再次送达。
                if not self._mark_digest_delivered(payload, through):
                    failed.append(acc_key)
                    continue
                if not self._save_wake(through, account=acc_key):
                    failed.append(acc_key)
                    continue
                if not self._clear_pending_batch(acc_key, str(payload.get('event_id') or '')):
                    failed.append(acc_key)
                    continue
                woke_accounts.append(acc_key)
            else:
                failed.append(acc_key)
                # 钉住失败账户的水位（不推进）：钉值 = 该账户本轮窗口起点（已有水位
                # 则用水位，首轮则用分段内最旧触发时间）——下轮 effective_since 取
                # 最旧水位，本轮未能送达的触发仍留在增量段（修复全局水位被部分成功
                # 推进、失败账户内容永久掉到 backlog 的缺陷）。
                pin = acct_mark or (self._segment_oldest(seg) if seg is not None else None)
                if pin is not None:
                    self._save_wake_mark(acc_key, pin)
        if delivered:
            logger.info("盯盘摘要已按账户唤醒", accounts=woke_accounts,
                        count=digest_count, groups=digest_group_count,
                        unassigned_defects=sum(d["count"] for d in defects))
            return {"woke": True, "count": digest_count, "group_count": digest_group_count,
                    "accounts": woke_accounts, "failed": failed, "wakes": delivered,
                    "data_defects": defects, "out_of_scope": out_of_scope}
        if failed:
            # 2026-10-15：此前唤醒失败完全静默——实测 agent-dh :13080 不在线，10-12 起
            # 每 tick 重试均无日志、无状态更新，"未处置清单"积压成山无人发现。
            # 唤醒通道失败是异常（不是每 tick 的正常门控拒绝），必须留痕。
            logger.warning('盯盘摘要唤醒投递失败（不写状态，下个 tick 重试）',
                           failed_accounts=failed, count=digest_count,
                           data_defects=defects, out_of_scope=out_of_scope)
        if out_of_scope and not delivered and not defects:
            return {"woke": False,
                    "reason": "仅命中策略账户（策略执行，盯盘不介入）：不唤醒 agent",
                    "count": sum(s["count"] for s in out_of_scope),
                    "out_of_scope": out_of_scope}
        return {"woke": False, "reason": "唤醒通道失败（不写状态，下次重试）",
                "count": digest_count, "failed": failed, "data_defects": defects,
                "out_of_scope": out_of_scope}
