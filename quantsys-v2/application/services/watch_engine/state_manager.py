"""WatchEngine 状态容器（RFC 014 v3 重构 P1，2026-09-14）

把原先散落在 WatchEngine.__init__ 里的 9 个状态字段收敛到一处：
  history / last_triggered / latched / recent_notified / overlap_reported /
  last_intervention / interventions_today / trigger_events / current_date

目的（按重要性）：
  1) **可观测**：snapshot() 给出当前状态规模，线上定位不必再猜；
  2) **可单测**：升级/去重逻辑的输入不再藏在引擎实例里；
  3) 为后续「状态可序列化 / 多实例恢复」留出单一改造面。

2026-09-18（REQ-c9f899 t3）：第 3 条落地为**运行态持久化**。闩锁与冷却基准
原先只在内存，进程重启即丢 —— 实测单日触发 23 次 > 1800s 冷却理论上限 16 次，
冷却形同虚设（需求 R10）。现在：

  · 构造时可注入 store（IWatchRuntimeStateStore 端口，可选）；
  · restore_from_store() 启动时把 latched / last_triggered 灌回内存；
  · flush() 只把「脏键」（与上次持久化快照不同或显式 mark_dirty 的键）批量 upsert；
    节流由调用方负责（引擎按 tick 调用，不是每次变化都写库）；
  · 写失败**响亮但不致命**：记日志 + degraded=True + 返回 False，绝不抛错
    （tick 不许崩），也绝不静默当成成功。

行为等价：store=None（默认）时全部新逻辑是 no-op，与改造前完全一致。
所有时间由调用方注入（本类不持 now_fn），便于测试构造。

2026-09-18（REQ-c9f899 返工 B+C）：t3 只持久化了闩锁与冷却基准，去重窗
recent_notified、触发事件窗口 trigger_events、velocity 用的 price_history 仍在内存
——重启后「窗内不再重复通知」失效、频率/共振统计归零、velocity 冷启动盲区。现补齐：

  · restore_from_store(now, symbols) 同时恢复三类运行态（各自按窗口/标的裁剪）；
  · flush(now) 在闩锁行之后增量落库：去重键只写变化的、事件只写新增的、
    价格只写新点并按 history_flush_sec 节流；随后按窗口节流裁剪（DB 侧有界）；
  · 三类扩展的读写**失败同样只降级不致命**（degraded=True + 返回 False），
    与 t3 对闩锁/冷却的纪律一致；
  · 适配器不支持某类扩展时（hasattr 守卫）自动跳过——旧桩/旧实现行为等价。
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TriggerRecord:
    """一次触发的事实（内存态，事件日志的元素）"""
    rule_id: int
    symbol: str
    triggered_at: datetime


class StateManager:
    """盯盘引擎的触发/去重/介入状态。

    默认（store=None）全部是纯内存操作、无 I/O，与改造前行为等价；注入 store 后
    仅 restore_from_store() / flush() 两个显式方法碰 I/O，其余方法仍是纯内存。
    """

    def __init__(self, event_retention_min: int = 30, dedup_window_sec: int = 300,
                 store=None, history_retention_min: int = 30,
                 history_flush_sec: int = 60, history_max_points: int = 240,
                 extras_prune_sec: int = 60):
        # 闩锁：条件持续成立时不重复推送，回落后重新武装
        self.latched: Set[Tuple[int, int]] = set()
        # 冷却与频率的「最近一次」：key=(rule_id, cond_idx) -> 时间（覆盖写语义）
        self.last_triggered: Dict[Tuple[int, int], datetime] = {}
        # 价格历史缓冲：symbol -> [(ts, price)]，供 velocity 条件
        self.history: Dict[str, List[Tuple[datetime, float]]] = {}
        # 去重窗：key=(归一化标的, 方向) -> (最近触发时间, 触发记录 id, 规则 id)
        # 带 rule_id 才能分辨「同一条规则多条件重复」（物理去重，保留）
        # 与「跨规则重叠」（业务问题，转治理）
        self.recent_notified: Dict[Tuple[str, str], Tuple[datetime, int, int]] = {}
        # 跨规则重叠已上报的规则对
        self.overlap_reported: Set[Tuple[int, int]] = set()
        # 增量门：key=(归一化标的, 意图) -> 最近介入时间
        self.last_intervention: Dict[Tuple[str, str], datetime] = {}
        # 当日介入计数
        self.interventions_today: int = 0
        # 触发事件日志：频率升级与多规则共振统计的**单一事实源**
        # （2026-09-14：原两条路径共用 last_triggered，而它是覆盖写、且不含 symbol）
        self.trigger_events: List[Tuple[datetime, int, str]] = []
        # 当前状态所属日期（跨天重置判定）
        self.current_date: Optional[date] = None

        # 事件日志保留窗口：需 ≥ 两个统计窗口（频率 10min / 共振 60s）的最大值
        self.event_retention_min = event_retention_min
        self.dedup_window_sec = dedup_window_sec

        # ── 运行态持久化（REQ-c9f899 R10）──────────────────────
        # store 为 IWatchRuntimeStateStore 端口实现；None = 未启用（一切新逻辑 no-op）
        self.store = store
        # 落库是否处于降级（写失败过且尚未成功恢复）；供监控与引擎指标读取
        self.degraded: bool = False
        # 已持久化快照：key -> (latched, last_triggered_at)，flush 据此只写脏键
        self._persisted: Dict[Tuple[int, int],
                              Tuple[bool, Optional[datetime]]] = {}
        # 显式脏键（diff 之外的补充，调用方可主动 mark）
        self._dirty: Set[Tuple[int, int]] = set()
        # 自愈临时延长后的有效冷却：本类不消费（判定仍读 cond['cooldown_sec']），
        # 仅 restore 时接住、flush 时原样透传——否则 upsert 会把该列冲成 NULL，
        # 抹掉后续自愈任务写入的数据。
        self.cooldown_effective: Dict[Tuple[int, int], Optional[int]] = {}

        # ── 返工 B+C：去重窗 / 事件窗 / 价格历史的增量落库台账 ──────────
        # 已持久化的去重键快照：key -> (notified_at, trigger_id, rule_id)；flush 据此只写变化
        self._persisted_dedup: Dict[Tuple[str, str],
                                    Tuple[datetime, int, int]] = {}
        # 新触发事件（尚未落库）：append 成功即清空；失败保留重试（事件表主键幂等）
        self._pending_events: List[Tuple[datetime, int, str]] = []
        # 每个 symbol 最近一次已落库的价格点时间：只写新点，且按 interval 节流
        self._persisted_history_ts: Dict[str, datetime] = {}
        # 裁剪节流：避免每 tick 都发 DELETE（裁剪是机会性的，不需要每 tick 精确）
        self._last_prune_at: Optional[datetime] = None
        # 价格历史保留窗口（与引擎 history_minutes 同口径；引擎默认 30 分钟）
        self.history_retention_min = history_retention_min
        # 同一 symbol 至少间隔这么久才再写一次价格（tick 可能 10s 一次，逐 tick 写太碎）
        self.history_flush_sec = history_flush_sec
        # 单次 flush 每个 symbol 最多写的点数（有界；30 分钟 × 10s ≈ 180 点）
        self.history_max_points = history_max_points
        # 去重/事件/价格三表裁剪的最小间隔
        self.extras_prune_sec = extras_prune_sec

    # ── 触发事件日志：频率 / 共振统计的唯一事实源 ──────────────
    def record_trigger_event(self, now: datetime, rule_id: int, symbol: str) -> None:
        """记一条触发事件 + 按保留窗口裁剪（调用方保证 now 单调不减）

        同步进 _pending_events（待落库缓冲）——只持久化开启时才缓冲，内存态不背这个账。
        """
        self.trigger_events.append((now, rule_id, symbol))
        if self.store is not None:
            self._pending_events.append((now, rule_id, symbol))
        cutoff = now - timedelta(minutes=self.event_retention_min)
        self.trigger_events = [e for e in self.trigger_events if e[0] >= cutoff]

    def recent_trigger_count(self, now: datetime, rule_id: int,
                             window_minutes: int = 10) -> int:
        """该规则近 window_minutes 内的触发次数（含本次触达）"""
        cutoff = now - timedelta(minutes=window_minutes)
        history = sum(1 for t, rid, _ in self.trigger_events
                      if rid == rule_id and t >= cutoff)
        return history + 1  # +1 = 本次：本方法在本次事件写进日志之前被调用

    def concurrent_trigger_count(self, now: datetime, symbol: str, rule_id: int,
                                 window_seconds: int = 60) -> int:
        """同标的近 window_seconds 内触发过的不同规则数（含本次）"""
        cutoff = now - timedelta(seconds=window_seconds)
        rule_ids = {rid for t, rid, sym in self.trigger_events
                    if sym == symbol and t >= cutoff}
        rule_ids.add(rule_id)  # 含本次：共振 = 本条 + 同标的其他规则
        return len(rule_ids)

    # ── 价格历史缓冲（velocity 条件用）──────────────────────
    def push_history(self, symbol: str, ts: datetime, price: float,
                     history_minutes: int = 30) -> None:
        """追加一个价格点 + 裁剪超出窗口的部分"""
        buf = self.history.setdefault(symbol, [])
        buf.append((ts, price))
        cutoff = ts - timedelta(minutes=history_minutes)
        self.history[symbol] = [(t, p) for t, p in buf if t >= cutoff]

    # ── 跨天重置 ────────────────────────────────────────────
    def reset_daily(self, now: datetime, active_rule_ids=None, active_symbols=None) -> None:
        """跨天重置。active_* 为 None 时不做按规则/标的的裁剪（测试便利）。"""
        self.current_date = now.date()
        self.latched.clear()
        self.recent_notified.clear()
        # 跨天：未落库的事件与去重快照同属昨日，清掉（DB 侧由窗口裁剪兜底）
        self._pending_events.clear()
        self._persisted_dedup.clear()
        self.overlap_reported.clear()
        self.last_intervention.clear()
        self.interventions_today = 0
        self.trigger_events = []
        if active_rule_ids is not None:
            self.last_triggered = {k: v for k, v in self.last_triggered.items()
                                   if k[0] in active_rule_ids}
        if active_symbols is not None:
            self.history = {s: b for s, b in self.history.items()
                            if s in active_symbols}

    # ── 去重窗裁剪 ──────────────────────────────────────────
    def prune_dedup(self, now: datetime, window_sec: Optional[int] = None) -> None:
        """清掉已过期的去重键，避免长跑进程内无界增长"""
        if not self.recent_notified:
            return
        window = self.dedup_window_sec if window_sec is None else window_sec
        cutoff = now.timestamp() - window
        self.recent_notified = {
            k: v for k, v in self.recent_notified.items()
            if v[0].timestamp() >= cutoff
        }

    # ── 运行态持久化（REQ-c9f899 R10）────────────────────────

    @staticmethod
    def _naive(dt: Optional[datetime]) -> Optional[datetime]:
        """把 aware datetime 归一到本进程时钟口径（naive 本地时间）。

        为什么必须做：库列为 TIMESTAMPTZ，psycopg2 读出来是 **aware**；引擎时钟
        （now_fn=datetime.now）是 **naive**。直接混用会让 TriggerJudge 的
        (now - last).total_seconds() 抛 TypeError（aware/naive 不能相减）——
        恢复出来的冷却基准反而把整个 tick 打挂，比丢冷却更糟。
        """
        if dt is None or dt.tzinfo is None:
            return dt
        return dt.astimezone().replace(tzinfo=None)

    def _runtime_value(self, key: Tuple[int, int]) -> Tuple[bool, Optional[datetime]]:
        """当前内存态的价值对（flush diff 与持久化快照共用同一口径）"""
        return (key in self.latched, self.last_triggered.get(key))

    def mark_dirty(self, key: Tuple[int, int]) -> None:
        """显式标记某键为脏（diff 之外的补充；无 store 时仅记账无副作用）"""
        self._dirty.add(key)

    def pending_dirty(self) -> int:
        """尚未持久化的脏键数（观测用）"""
        return len(self._dirty)

    def restore_from_store(self, now: Optional[datetime] = None,
                           symbols=None) -> int:
        """启动恢复：把库里的闩锁/冷却基准 + 去重窗 + 事件窗 + 价格历史灌回内存。

        返回恢复的**闩锁行数**（扩展运行的条数记在日志里，不混进这个计数，
        否则既有 'restore == N' 断言的语义会被悄悄改掉）。

        symbols：启用规则覆盖的标的集合，价格历史只恢复这些（有界口径，理由见
        _restore_history）；为 None 时退化为「按窗口恢复全部标的」。
        now：窗口裁剪的基准时刻；缺省 datetime.now()（真实调用方应显式传引擎时钟）。

        store 未配置返回 0；读取失败**不抛错**（引擎启动不允许被库抖挂），
        但必须置 degraded=True 并响亮记日志——恢复失败意味着冷却基准丢失，
        正是 R10 要防的状态。三类扩展各自独立容错：一类坏不掉另外两类。
        """
        if self.store is None:
            return 0
        try:
            rows = self.store.load_all() or []
        except Exception as e:  # noqa: BLE001 —— 响亮但不致命
            self.degraded = True
            logger.error('运行态恢复失败：冷却基准丢失（本进程从零开始，冷却可能失效）',
                         error=str(e))
            return 0
        restored = 0
        for row in rows:
            try:
                key = (int(row['rule_id']), int(row['cond_idx']))
            except (KeyError, TypeError, ValueError):
                logger.warning('运行态行格式非法，已跳过', row=repr(row)[:200])
                continue
            if bool(row.get('latched')):
                self.latched.add(key)
            last = self._naive(row.get('last_triggered_at'))
            if last is not None:
                self.last_triggered[key] = last
            elif key in self.last_triggered:
                del self.last_triggered[key]
            cooldown = row.get('cooldown_effective_sec')
            if cooldown is not None:
                self.cooldown_effective[key] = cooldown
            # 快照与内存对齐：恢复后首个 flush 不应把全部行重写一遍
            self._persisted[key] = self._runtime_value(key)
            restored += 1
        self._restore_extras(now or datetime.now(), symbols)
        return restored

    # ── 返工 B+C：扩展运行态的恢复 / 落库 / 裁剪 ─────────────
    # 三类扩展共用一条纪律：适配器不支持就跳过（行为等价）、读失败只降级不抛错。

    def _restore_extras(self, now: datetime, symbols=None) -> None:
        """恢复去重窗 / 事件窗 / 价格历史（各自独立容错，互不牵连）"""
        self._restore_dedup(now)
        self._restore_events(now)
        self._restore_history(now, symbols)

    def _restore_dedup(self, now: datetime) -> None:
        loader = getattr(self.store, 'load_dedup', None)
        if not callable(loader):
            return
        try:
            rows = loader() or []
        except Exception as e:  # noqa: BLE001 —— 响亮但不致命
            self.degraded = True
            logger.error('去重窗恢复失败：窗内重复通知可能重现', error=str(e))
            return
        cutoff = now - timedelta(seconds=self.dedup_window_sec)
        for row in rows:
            try:
                key = (str(row['symbol']), str(row['direction']))
                at = self._naive(row.get('notified_at'))
            except (KeyError, TypeError, ValueError):
                logger.warning('去重行格式非法，已跳过', row=repr(row)[:200])
                continue
            if at is None or at < cutoff:
                continue                      # 窗口外的键不再保留
            val = (at, int(row.get('trigger_id') or 0), int(row.get('rule_id') or 0))
            self.recent_notified[key] = val
            self._persisted_dedup[key] = val  # 快照对齐：首个 flush 不重写已恢复的键
        logger.info('去重窗已恢复', keys=len(self.recent_notified),
                    window_sec=self.dedup_window_sec)

    def _restore_events(self, now: datetime) -> None:
        loader = getattr(self.store, 'load_events', None)
        if not callable(loader):
            return
        cutoff = now - timedelta(minutes=self.event_retention_min)
        try:
            rows = loader(since=cutoff) or []
        except Exception as e:  # noqa: BLE001
            self.degraded = True
            logger.error('触发事件窗口恢复失败：频率/共振统计会从 0 起算', error=str(e))
            return
        restored = []
        for row in rows:
            at = self._naive(row.get('triggered_at'))
            if at is None or at < cutoff:
                continue
            restored.append((at, int(row.get('rule_id') or 0), str(row.get('symbol') or '')))
        # 合并而非覆盖：恢复发生在 tick 之前，但双保险不丢本进程已记的事件
        self.trigger_events = sorted(set(self.trigger_events) | set(restored),
                                     key=lambda e: e[0])
        logger.info('触发事件窗口已恢复', events=len(restored),
                    window_min=self.event_retention_min)

    def _restore_history(self, now: datetime, symbols=None) -> None:
        """恢复价格历史（velocity 用）。

        有界恢复口径与理由（返工 C 要求显式给出）：
          ① 按 **symbols** 过滤：只恢复「启用规则覆盖的标的」——价格历史是全市场级
             的时间序列，无差别恢复会把内存与查询都撑爆，而引擎只会为有规则的 symbol
             取价（tick 里 push_history 也只 push 这些）；
          ② 按 **窗口** 过滤：只取 history_retention_min（默认 30 分钟）内的点——
             velocity 只消费这个窗口；
          ③ 每 symbol 保留最后 history_max_points 个点（默认 240）——即使库里有异常
             密集的点，单个 symbol 的恢复量也有硬上限。
        """
        loader = getattr(self.store, 'load_price_history', None)
        if not callable(loader):
            return
        cutoff = now - timedelta(minutes=self.history_retention_min)
        try:
            rows = loader(symbols=symbols, since=cutoff) or []
        except Exception as e:  # noqa: BLE001
            self.degraded = True
            logger.error('价格历史恢复失败：velocity 条件存在冷启动盲区', error=str(e))
            return
        per_symbol: Dict[str, List[Tuple[datetime, float]]] = {}
        for row in rows:
            sym = str(row.get('symbol') or '')
            at = self._naive(row.get('ts'))
            if not sym or at is None or at < cutoff:
                continue
            try:
                price = float(row.get('price'))
            except (TypeError, ValueError):
                continue
            per_symbol.setdefault(sym, []).append((at, price))
        for sym, pts in per_symbol.items():
            pts.sort(key=lambda e: e[0])
            pts = pts[-self.history_max_points:]
            self.history[sym] = pts
            self._persisted_history_ts[sym] = pts[-1][0]  # 已落库对齐：不重写旧点
        logger.info('价格历史已恢复', symbols=len(per_symbol),
                    retention_min=self.history_retention_min)

    def flush(self, now: Optional[datetime] = None) -> bool:
        """把脏键批量落库（节流由调用方按 tick/时间间隔控制）。

        只写「与上次持久化快照不同」或显式 mark_dirty 的键——无脏键时**不调用**
        store（零 I/O）。同一批里还增量落库三类扩展状态：去重窗（只写变化的键）、
        触发事件（只写新增，主键幂等）、价格历史（只写新点，按 interval 节流），
        并按窗口节流裁剪三张表（有界）。

        写失败：记日志 + degraded=True + 返回 False，绝不抛错（tick 不许崩），
        也绝不返回 True 假装成功。失败时各类脏标记**保留**，下个 tick 重试。

        返回：True=无需写或写成功；False=未启用持久化 / 写失败。
        """
        if self.store is None:
            return False
        now = now or datetime.now()
        try:
            keys = (set(self.latched) | set(self.last_triggered)
                    | set(self._persisted) | set(self._dirty))
            rows: List[Dict[str, Any]] = []
            written: List[Tuple[int, int]] = []
            for key in keys:
                current = self._runtime_value(key)
                if key in self._dirty or self._persisted.get(key) != current:
                    rows.append({
                        'rule_id': key[0],
                        'cond_idx': key[1],
                        'latched': current[0],
                        'last_triggered_at': current[1],
                        'cooldown_effective_sec': self.cooldown_effective.get(key),
                    })
                    written.append(key)
            if rows:
                self.store.upsert_many(rows)
            self._flush_extras(now)
        except Exception as e:  # noqa: BLE001 —— 响亮但不致命
            self.degraded = True
            logger.error('运行态落库失败：本 tick 状态未持久化（重启后冷却/去重/统计可能失效）',
                         error=str(e), dirty=len(self._dirty),
                         pending_events=len(self._pending_events))
            return False
        for key in written:
            self._persisted[key] = self._runtime_value(key)
        self._dirty.clear()
        self.degraded = False
        return True

    def _flush_extras(self, now: datetime) -> None:
        """三类扩展的顺序落库 + 有界裁剪（任一失败向上抛，由 flush 统一降级）"""
        self._flush_dedup(now)
        self._flush_events()
        self._flush_history(now)
        self._prune_extras(now)

    def _flush_dedup(self, now: datetime) -> None:
        upsert = getattr(self.store, 'upsert_dedup', None)
        if not callable(upsert):
            return
        changed = []   # [(key, value, row)]
        for key, val in self.recent_notified.items():
            if self._persisted_dedup.get(key) == val:
                continue                       # 未变化：不重写（节流）
            changed.append((key, val, {
                'symbol': key[0],
                'direction': key[1],
                'notified_at': val[0],
                'trigger_id': val[1] if len(val) > 1 else None,
                'rule_id': val[2] if len(val) > 2 else None,
            }))
        if not changed:
            return
        upsert([row for _, _, row in changed])
        for key, val, _ in changed:
            self._persisted_dedup[key] = val

    def _flush_events(self) -> None:
        append = getattr(self.store, 'append_events', None)
        if not callable(append):
            # 适配器不支持事件持久化（旧实现/测试桩）：清空缓冲避免内存无界增长
            self._pending_events.clear()
            return
        if not self._pending_events:
            return
        rows = [{'triggered_at': t, 'rule_id': int(rid), 'symbol': s}
                for t, rid, s in self._pending_events]
        append(rows)
        # 成功才清：失败保留，下个 tick 重试（事件表主键幂等，不产生重复计数）
        self._pending_events.clear()

    def _flush_history(self, now: datetime) -> None:
        upsert = getattr(self.store, 'upsert_price_history', None)
        if not callable(upsert):
            return
        rows: List[Dict[str, Any]] = []
        newest: Dict[str, datetime] = {}
        for sym, buf in self.history.items():
            last = self._persisted_history_ts.get(sym)
            pts = [(t, p) for t, p in buf if last is None or t > last]
            if not pts:
                continue
            last_ts = pts[-1][0]
            if last is not None and (last_ts - last).total_seconds() < self.history_flush_sec:
                continue                       # 节流：同一 symbol 未到下次写入间隔
            for t, p in pts[-self.history_max_points:]:
                rows.append({'symbol': sym, 'ts': t, 'price': float(p)})
            newest[sym] = last_ts
        if not rows:
            return
        upsert(rows)
        self._persisted_history_ts.update(newest)

    def _prune_extras(self, now: datetime) -> None:
        """按窗口裁剪三张扩展表（节流到 extras_prune_sec，避免每 tick 发 DELETE）"""
        prune_dedup = getattr(self.store, 'prune_dedup', None)
        if not callable(prune_dedup):
            return
        if (self._last_prune_at is not None
                and (now - self._last_prune_at).total_seconds() < self.extras_prune_sec):
            return
        prune_dedup(now - timedelta(seconds=self.dedup_window_sec))
        prune_events = getattr(self.store, 'prune_events', None)
        if callable(prune_events):
            prune_events(now - timedelta(minutes=self.event_retention_min))
        prune_history = getattr(self.store, 'prune_price_history', None)
        if callable(prune_history):
            prune_history(now - timedelta(minutes=self.history_retention_min))
        self._last_prune_at = now

    # ── 可观测 ──────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """状态规模快照（监控/排障用；不暴露内容，避免误读为业务数据）"""
        return {
            'latched': len(self.latched),
            'last_triggered': len(self.last_triggered),
            'history_symbols': len(self.history),
            'dedup_window': len(self.recent_notified),
            'overlap_reported': len(self.overlap_reported),
            'interventions_today': self.interventions_today,
            'trigger_events': len(self.trigger_events),
            'current_date': self.current_date.isoformat() if self.current_date else None,
            'persist_enabled': self.store is not None,
            'persist_degraded': self.degraded,
            'persist_pending_dirty': len(self._dirty),
            # 返工 B+C 可观测：待落库事件数 / 已对齐的去重键数 / 已对齐的价格 symbol 数
            'persist_pending_events': len(self._pending_events),
            'persist_dedup_tracked': len(self._persisted_dedup),
            'persist_history_tracked': len(self._persisted_history_ts),
        }
