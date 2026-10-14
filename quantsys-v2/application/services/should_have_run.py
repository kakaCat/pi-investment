"""「该跑没跑」盘点器：按 cron 推演应跑时刻，与 scheduler_runs 比对（REQ-261004154902-a7cd · FR-8）

## 为什么需要它（本仓的实证）

调度停摆在本仓发生过不止一次，而**每一次都是"没人知道"**：

- 2026-10-01 21:48 – 10-02 08:21：服务活着、探针 healthy，但四个 ``DISABLE_*`` 全开，
  10.5 小时零 run —— 旧探针只看「端口能不能连」+「K 线新不新鲜」，**看不见调度死没死**；
- 2026-10-03 / 10-04：`每日数据质量检查`（id=232）分别晚 5:23 / 24:42 被 APScheduler
  **静默跳过**（超 misfire 宽限），`quant.scheduler_runs` 里查不到任何行，
  `last_status` 还停在前几天的 success —— 只能靠人翻库发现。

`quant.scheduler_runs` 只记录**真的触发过**的任务；任务**根本没触发**时它是空的，
所以"库里有行 = 跑过" 与 "库里没行 = 没跑" 都不是自明的。本模块补的正是这条判据：
**对每个启用任务推演"最近一个应跑时刻"，再问 scheduler_runs"这个时刻之后跑过没有"**。

## 三条硬口径（改之前先读）

1. **cron 语义 = 标准 cron（0=周日）+ 本地时区 Asia/Shanghai**，翻译**必须**走
   `infrastructure/scheduler/cron_compat.build_cron_trigger`（本仓唯一翻译点）。
   本模块**不自己解析 cron**：一旦这里长出第二份解析，探针与调度器就会各算各的，
   「8 小时漂移」「周一整体缺失」那类事故会以"盘点器说没事"的形式回来。
2. **判不出来必须报 `unknown`，不许默认 ok**（取数失败、cron 非法、回看窗口内无排班、
   `started_at` 为空 …… 全部落到 unknown）。默认 ok 等于"监控自己骗自己"。
3. **`status='missed'` 的 run 行不算"跑过"**。t5 起 APScheduler 的跳过会落一条
   `status='missed'` 的行，而它的 `started_at` 正是**被跳过的那个排班时刻**
   （`scheduler_repository.record_missed_run`）——若按"started_at ≥ 应跑时刻"算，
   被跳过的排班反而会被判成 ok，把本模块要抓的东西原地抹掉。

## 节流（防止重演 504 条刷屏）

2026-10-04 前的探针在 42 小时里发过 **504 条同一条误报**（把国庆休市当应有交易日）。
本模块为此提供**去重键** `ShouldHaveRunVerdict.dedup_key = (任务名, 应跑时刻)`：
同一个漏跑时刻最多告警一次，跨进程重启也认（键会被写进探针的状态文件）。

## 分清两件事，别在这里做第三件

- **这里只判"该跑没跑"**，判据是 cron 排班，**不掺交易日历**：调度器自己也不认识节假日
  （`* * 1-5` 在国庆照样触发）。把日历混进来，换来的就是 504 条休市误报。
  「数据新不新鲜」由 `application/services/trading_day_resolver` 那条线管。
- **本模块只读**：`SELECT`，绝不写表、绝不发通知（外发是 `tools/health_probe.py` 的事）。

## 可注入取数（单测零 DB 零网络）

判定逻辑与取数分离：`ShouldHaveRunSource` 是协议，生产用 `SqlShouldHaveRunSource`（只读 SQL），
单测注入假源 + 注入 `now` 即可，无需数据库。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TZ_NAME = "Asia/Shanghai"
TZ = ZoneInfo(TZ_NAME)

# 回看窗口：本仓最稀的排班是"每周一次"，8 天足以覆盖（含跨周）。
DEFAULT_LOOKBACK_DAYS = 8
# 向前推演的迭代上限（防脏 cron 让循环失控；`*/1 * * * *` 在 8 天里是 11520 次，故留余量）。
MAX_SLOT_SCAN = 20000

VERDICT_OK = "ok"
VERDICT_MISSED = "missed"
VERDICT_UNKNOWN = "unknown"
VERDICTS = (VERDICT_OK, VERDICT_MISSED, VERDICT_UNKNOWN)


# ── 值对象 ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScheduledTask:
    """一条启用中的调度任务（只取判定要用的列）。"""

    task_id: int
    name: str
    cron_expression: str
    is_enabled: bool = True
    misfire_grace_time_seconds: Optional[int] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class RunRecord:
    """一次执行留痕（`quant.scheduler_runs` 的一行）。"""

    task_id: int
    status: str
    started_at: Optional[datetime] = None


@dataclass(frozen=True)
class ShouldHaveRunVerdict:
    """单个任务的判定结果（表格一行）。"""

    task_id: int
    task_name: str
    cron_expression: str
    expected_slot: Optional[datetime]
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    verdict: str
    reason: str = ""
    # ── 配置改动护栏（REQ-261004154902-a7cd · FR-8 · 人工裁决 2026-10-04）──
    # 「应跑时刻早于该任务最近一次改动（scheduler_tasks.updated_at）」的 slot 不计为漏跑：
    # 那一刻它可能被停用、cron 刚改过、或还没启用 —— 拿旧配置的时刻去指责它，就是冤判。
    changed_at: Optional[datetime] = None
    guarded: bool = False
    pre_change_slot: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"非法判定: {self.verdict!r}（只允许 {VERDICTS}）")

    @property
    def dedup_key(self) -> Tuple[str, Optional[str]]:
        """告警节流用的去重键 `(任务名, 应跑时刻)`（ISO8601；无时刻时为 None）。

        语义：**同一个漏跑时刻最多告警一次**。任务名而非 id——告警正文里人看的是名字，
        且 id 在库重建后可能变，名字不会。
        """
        return (self.task_name, self.expected_slot.isoformat() if self.expected_slot else None)

    @property
    def alert_key(self) -> str:
        """去重键的字符串形态（写状态文件用）：``<任务名>@<应跑时刻>``。"""
        name, slot = self.dedup_key
        return f"{name}@{slot}"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task": self.task_name,
            "cron": self.cron_expression,
            "expected_slot": _iso(self.expected_slot),
            "last_run_at": _iso(self.last_run_at),
            "last_run_status": self.last_run_status,
            "verdict": self.verdict,
            "reason": self.reason,
            "dedup_key": list(self.dedup_key),
            "guarded": self.guarded,
            "changed_at": _iso(self.changed_at),
            "pre_change_slot": _iso(self.pre_change_slot),
        }


@dataclass(frozen=True)
class ShouldHaveRunReport:
    """一次盘点的完整结果。"""

    verdicts: Tuple[ShouldHaveRunVerdict, ...] = ()
    checked_at: Optional[datetime] = None
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    source_error: Optional[str] = None
    config_guard: bool = True

    @property
    def missed(self) -> Tuple[ShouldHaveRunVerdict, ...]:
        return tuple(v for v in self.verdicts if v.verdict == VERDICT_MISSED)

    @property
    def unknown(self) -> Tuple[ShouldHaveRunVerdict, ...]:
        return tuple(v for v in self.verdicts if v.verdict == VERDICT_UNKNOWN)

    @property
    def guarded(self) -> Tuple[ShouldHaveRunVerdict, ...]:
        """被配置改动护栏豁免的任务（判定为 ok，但**不是**"跑过了"，绝不静默：单独成桶）。

        为什么单独留一桶：护栏是按 `updated_at` 批量生效的（本仓的启用集合调整会一次
        触碰全部启用行，见 2026-10-04 16:24:42 那 11 行的同一微秒时间戳），
        所以"改配置"与"真的跑过了"在库里长得不一样，必须能被人看见。
        """
        return tuple(v for v in self.verdicts if v.guarded)

    @property
    def ok(self) -> bool:
        """无漏跑即 ok。注意：unknown **不算**漏跑，但会在 `unknown` 里显式暴露（绝不静默）。"""
        return not self.missed

    @property
    def dedup_keys(self) -> List[str]:
        return [v.alert_key for v in self.missed]


# ── 时刻推演 ────────────────────────────────────────────────────────────

def local_now() -> datetime:
    """本地时区（Asia/Shanghai）的"现在"——与调度器同一语义。"""
    return datetime.now(TZ)


def to_local(dt: Optional[datetime]) -> Optional[datetime]:
    """把库里的时刻统一成本地时区（naive 值按本地解释：库列是 timestamptz）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def previous_slot(
    cron_expr: str,
    now: datetime,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Optional[datetime]:
    """最近一个"应跑时刻" = 不晚于 `now` 的最后一个 cron 触发点。

    用 `build_cron_trigger` 造出**与调度器同一个** CronTrigger，再在
    `[now - lookback_days, now]` 窗口里向前走，取最后一个 ≤ now 的触发点。

    Raises:
        ValueError: cron 缺失/非法（含 `managed_by_agent_*` 伪任务）——调用方翻成 unknown。
    """
    expr = str(cron_expr or "").strip()
    if not expr:
        raise ValueError("cron 表达式为空")
    # 局部 import：本模块被探针调用，探针要求"不 import 被监控的 FastAPI 应用"，
    # 但 cron 翻译是纯字典/触发器逻辑，且**必须**复用唯一翻译点（见模块 docstring）。
    from infrastructure.scheduler.cron_compat import build_cron_trigger

    trigger = build_cron_trigger(expr, tz=TZ_NAME)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    now = now.astimezone(TZ)

    window_start = now - timedelta(days=max(0, int(lookback_days)))
    prev: Optional[datetime] = None
    # start 取窗口起点之前 1 秒，确保窗口起点当刻的排班也能被纳入
    cursor = trigger.get_next_fire_time(None, window_start - timedelta(seconds=1))
    scanned = 0
    while cursor is not None and cursor <= now:
        prev = cursor
        scanned += 1
        if scanned > MAX_SLOT_SCAN:
            raise ValueError(f"cron {expr!r} 在 {lookback_days} 天窗口内触发点过多（>{MAX_SLOT_SCAN}）")
        cursor = trigger.get_next_fire_time(cursor, cursor + timedelta(seconds=1))
    return to_local(prev)


def next_slot_after(cron_expr: str, since: datetime) -> Optional[datetime]:
    """`since` 之后的第一个 cron 触发点（护栏豁免时用来告诉人"下次什么时候该跑"）。"""
    from infrastructure.scheduler.cron_compat import build_cron_trigger

    trigger = build_cron_trigger(str(cron_expr or "").strip(), tz=TZ_NAME)
    since = to_local(since)
    return to_local(trigger.get_next_fire_time(None, since))


# ── 判定 ────────────────────────────────────────────────────────────────

#: 「该槽位是否已被处理」的状态集 —— **判漏跑**用。
#: 含 `skipped`（交易日门按日历主动跳过，REQ-261006093620-a315）：那是**正常**语义，不是漏跑。
HANDLED_STATUSES: tuple = ('success', 'failed', 'skipped')
#: 「真执行过」的状态集 —— **呈现**"最近一次真执行"用。
#: 刻意**不含** `skipped`：跳过没有执行过任何东西，把它当执行时刻展示会误导人。
REAL_RUN_STATUSES: tuple = ('success', 'failed')


def _in_list(statuses: tuple) -> str:
    """把状态常量拼成 SQL 的 IN 列表。

    安全性：取值来自本模块的**常量元组**（非用户输入），且只允许 `[a-z_]`——
    仍是字符串拼接，故加一道字符白名单，避免将来有人把外部值塞进来。
    """
    for s in statuses:
        if not all(c.islower() or c == '_' for c in s):
            raise ValueError(f'非法状态字面量: {s!r}')
    return ', '.join(f"'{s}'" for s in statuses)


def judge_task(
    task: ScheduledTask,
    *,
    now: datetime,
    latest_run: Optional[RunRecord] = None,
    latest_missed_run: Optional[RunRecord] = None,
    latest_handled_run: Optional[RunRecord] = None,
    lookup_error: Optional[BaseException] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    apply_config_guard: bool = True,
) -> ShouldHaveRunVerdict:
    """单任务三态判定：`ok` / `missed` / `unknown`（判不出来一律 unknown）。

    判定规则（按序）：

    1. 取数失败 / cron 非法 / 窗口内无排班 → **unknown**（附原因）；
    2. **配置改动护栏**（`apply_config_guard=True` 时）：应跑时刻早于该任务最近一次改动
       （`scheduler_tasks.updated_at`）→ **ok**，理由写明"自我改动以来还没有到期排班，
       下一个应跑时刻是 …"。语义：那一刻它可能被停用 / cron 刚改 / 还没启用，
       拿旧配置的时刻指责它是冤判（2026-10-04 人工裁决）。
    3. 最近一次**已处理**（`HANDLED_STATUSES` = success / failed / **skipped**）的
       `started_at ≥ 应跑时刻` → **ok**。含 `skipped` 的理由：交易日门按日历跳过的槽位是
       **正常语义**，不是漏跑（REQ-261006093620-a315 t7）；但呈现用的
       "最近一次真执行"（`REAL_RUN_STATUSES`）**不含** skipped——跳过没有执行过任何东西。
    4. 否则 → **missed**；若库里恰好有一条 `status='missed'` 且其 `started_at` 就是
       该应跑时刻，在 reason 里注明"调度器已自己记账为跳过"，便于人分辨
       「调度器跳过了」与「连触发都没触发」。
    """
    base = dict(
        task_id=task.task_id,
        task_name=task.name,
        cron_expression=str(task.cron_expression or ""),
    )

    if lookup_error is not None:
        return ShouldHaveRunVerdict(
            **base, expected_slot=None, last_run_at=None, last_run_status=None,
            verdict=VERDICT_UNKNOWN,
            reason=f"取数失败，无法判定: {type(lookup_error).__name__}: {lookup_error}",
        )

    try:
        slot = previous_slot(task.cron_expression, now, lookback_days=lookback_days)
    except Exception as exc:  # noqa: BLE001 - 任何解析/触发异常都只是"判不出来"
        return ShouldHaveRunVerdict(
            **base, expected_slot=None, last_run_at=None, last_run_status=None,
            verdict=VERDICT_UNKNOWN, reason=f"cron 无法判定: {type(exc).__name__}: {exc}",
        )

    if slot is None:
        return ShouldHaveRunVerdict(
            **base, expected_slot=None, last_run_at=None, last_run_status=None,
            verdict=VERDICT_UNKNOWN,
            reason=f"最近 {lookback_days} 天内没有排班（回看窗口不足或 cron 过于稀疏）",
        )

    last_at = to_local(latest_run.started_at) if latest_run else None
    last_status = latest_run.status if latest_run else None
    # 「已处理」与「真执行」是两件事（REQ-261006093620-a315 t7）：
    # 判漏跑看 handled（含 skipped），呈现看 last（真执行）。
    handled_at = to_local(latest_handled_run.started_at) if latest_handled_run else None

    # ② 配置改动护栏：应跑时刻早于最近一次改动 → 不计漏跑（并给出下一个应跑时刻）
    changed_at = to_local(task.updated_at)
    if apply_config_guard and changed_at is not None and slot < changed_at:
        try:
            upcoming = next_slot_after(task.cron_expression, changed_at)
        except Exception:  # noqa: BLE001 - 仅仅是为了展示"下次何时该跑"
            upcoming = None
        return ShouldHaveRunVerdict(
            **base,
            expected_slot=upcoming if upcoming is not None else slot,
            last_run_at=last_at, last_run_status=last_status,
            verdict=VERDICT_OK,
            reason=(
                f"应跑时刻 {_iso(slot)} 早于该任务最近一次改动 {_iso(changed_at)} "
                f"→ 自改动以来尚未到期（下一个应跑时刻 {_iso(upcoming) or '未知'}），按护栏不计漏跑"
            ),
            changed_at=changed_at, guarded=True, pre_change_slot=slot,
        )

    if handled_at is not None and handled_at >= slot:
        # 「已处理」= success / failed / **skipped**（门按日历跳过）。
        # skipped 不算漏跑，但要如实说明它是"被门跳过的"——别让读者以为真跑过。
        by_gate = latest_handled_run is not None and latest_handled_run.status == 'skipped'
        reason = (
            f"该排班已被交易日门按日历跳过（status=skipped @ {_iso(handled_at)}），不算漏跑"
            if by_gate else
            f"应跑时刻 {_iso(slot)} 之后已有执行留痕"
        )
        return ShouldHaveRunVerdict(
            **base, expected_slot=slot, last_run_at=last_at, last_run_status=last_status,
            verdict=VERDICT_OK, reason=reason, changed_at=changed_at,
        )

    missed_at = to_local(latest_missed_run.started_at) if latest_missed_run else None
    if missed_at is not None and missed_at == slot:
        reason = f"该排班被调度器跳过（status=missed @ {_iso(missed_at)}），未补跑"
    elif last_at is None and handled_at is None:
        reason = "scheduler_runs 中无任何执行留痕"
    elif last_at is None:
        reason = (f"最近一次留痕是交易日门跳过（@ {_iso(handled_at)}），"
                  f"早于应跑时刻 {_iso(slot)}")
    else:
        reason = f"最近一次执行 {_iso(last_at)} 早于应跑时刻 {_iso(slot)}"

    return ShouldHaveRunVerdict(
        **base, expected_slot=slot, last_run_at=last_at, last_run_status=last_status,
        verdict=VERDICT_MISSED, reason=reason, changed_at=changed_at,
    )


# ── 取数（可注入）────────────────────────────────────────────────────────

class ShouldHaveRunSource(Protocol):
    """盘点器的取数口（只读）。单测注入假实现即可零 DB 零网络。"""

    def list_enabled_tasks(self) -> Sequence[ScheduledTask]:
        ...

    def latest_run(self, task_id: int) -> Optional[RunRecord]:
        """最近一次**真执行**（`REAL_RUN_STATUSES` = success / failed）。**不含 skipped**。"""

    def latest_handled_run(self, task_id: int) -> Optional[RunRecord]:
        """最近一次**已处理**（`HANDLED_STATUSES` = success / failed / skipped）。判漏跑用它。"""

    def latest_missed_run(self, task_id: int) -> Optional[RunRecord]:
        """最近一条 `status='missed'` 记账（可能没有）。"""


class SqlShouldHaveRunSource:
    """生产取数：只读 SQL（**只 SELECT**，不写表、不发通知）。

    三次批量查询（启用任务清单 / 每任务最近真执行 / 每任务最近已处理 / 每任务 missed 记账），
    不逐任务查库：盘点器会被 5 分钟一次的探针调用，N+1 查询没必要。
    （2026-10-06 · REQ-261006093620-a315 t7：由两次增至三次——「已处理」与「真执行」是两件事。）
    """

    _TASKS_SQL = (
        "SELECT id, name, cron_expression, is_enabled, misfire_grace_time_seconds, updated_at "
        "FROM quant.scheduler_tasks WHERE is_enabled IS TRUE ORDER BY id"
    )
    _RUNS_SQL = (
        "SELECT DISTINCT ON (task_id) task_id, status, started_at "
        "FROM quant.scheduler_runs WHERE status {op} 'missed' "
        "ORDER BY task_id, started_at DESC NULLS LAST"
    )
    #: 已处理（success / failed / skipped）——判漏跑用（REQ-261006093620-a315 t7）
    _HANDLED_RUNS_SQL = (
        "SELECT DISTINCT ON (task_id) task_id, status, started_at "
        "FROM quant.scheduler_runs WHERE status IN (" + _in_list(HANDLED_STATUSES) + ") "
        "ORDER BY task_id, started_at DESC NULLS LAST"
    )
    #: 真执行（success / failed，**不含 skipped**）——呈现"最近一次真执行"用
    _REAL_RUNS_SQL = (
        "SELECT DISTINCT ON (task_id) task_id, status, started_at "
        "FROM quant.scheduler_runs WHERE status IN (" + _in_list(REAL_RUN_STATUSES) + ") "
        "ORDER BY task_id, started_at DESC NULLS LAST"
    )

    def __init__(self, engine: Any = None) -> None:
        self._engine = engine
        self._tasks: Optional[List[ScheduledTask]] = None
        self._runs: Optional[Dict[int, RunRecord]] = None
        self._missed: Optional[Dict[int, RunRecord]] = None
        self._handled: Optional[Dict[int, RunRecord]] = None

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        from infrastructure.persistence.database.engine import get_engine

        return get_engine()

    def _fetch(self, sql: str) -> List[Any]:
        from sqlalchemy import text

        with self._get_engine().connect() as conn:
            return list(conn.execute(text(sql)).mappings().all())

    def list_enabled_tasks(self) -> List[ScheduledTask]:
        if self._tasks is None:
            self._tasks = [
                ScheduledTask(
                    task_id=int(row["id"]),
                    name=str(row["name"]),
                    cron_expression=str(row["cron_expression"] or ""),
                    is_enabled=bool(row["is_enabled"]),
                    misfire_grace_time_seconds=row["misfire_grace_time_seconds"],
                    updated_at=row["updated_at"],
                )
                for row in self._fetch(self._TASKS_SQL)
            ]
        return self._tasks

    def _load_runs(self) -> Dict[int, RunRecord]:
        if self._runs is None:
            self._runs = {
                int(row["task_id"]): RunRecord(
                    task_id=int(row["task_id"]),
                    status=str(row["status"] or ""),
                    started_at=row["started_at"],
                )
                for row in self._fetch(self._REAL_RUNS_SQL)
                if row["task_id"] is not None
            }
        return self._runs

    def _load_missed(self) -> Dict[int, RunRecord]:
        if self._missed is None:
            self._missed = {
                int(row["task_id"]): RunRecord(
                    task_id=int(row["task_id"]),
                    status=str(row["status"] or ""),
                    started_at=row["started_at"],
                )
                for row in self._fetch(self._RUNS_SQL.format(op="="))
                if row["task_id"] is not None
            }
        return self._missed

    def _load_handled(self) -> Dict[int, RunRecord]:
        """已处理（success / failed / **skipped**）——判"该槽位是否已被处理"用。"""
        if self._handled is None:
            self._handled = {
                int(row["task_id"]): RunRecord(
                    task_id=int(row["task_id"]),
                    status=str(row["status"] or ""),
                    started_at=row["started_at"],
                )
                for row in self._fetch(self._HANDLED_RUNS_SQL)
                if row["task_id"] is not None
            }
        return self._handled

    def latest_run(self, task_id: int) -> Optional[RunRecord]:
        return self._load_runs().get(int(task_id))

    def latest_handled_run(self, task_id: int) -> Optional[RunRecord]:
        return self._load_handled().get(int(task_id))

    def latest_missed_run(self, task_id: int) -> Optional[RunRecord]:
        return self._load_missed().get(int(task_id))


# ── 入口 ────────────────────────────────────────────────────────────────

def audit_should_have_run(
    now: Optional[datetime] = None,
    source: Optional[ShouldHaveRunSource] = None,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    apply_config_guard: bool = True,
) -> ShouldHaveRunReport:
    """对全部启用任务做一次「该跑没跑」盘点。

    Args:
        now: 判定基准时刻（可注入，测试用）；缺省 = 本地当前时刻。
        source: 取数口；缺省 = `SqlShouldHaveRunSource()`（只读 SQL）。
        lookback_days: 应跑时刻的向前回看窗口。
        apply_config_guard: 是否启用「配置改动护栏」（应跑时刻早于任务最近一次改动 → 不计漏跑）。
            默认**开**；复核历史缺口时可显式关掉（`check_should_have_run.py --no-config-guard`），
            关掉后 232/242/249 这类"改动之前就漏了"的缺口会重新显现为 missed。

    Returns:
        `ShouldHaveRunReport`。**取数失败不抛异常**——任务清单取不到时返回
        一条 `unknown` 判定 + `source_error`（调用方据此决定退出码），
        单个任务的 run 取数失败只影响该任务（同样 unknown）。
    """
    now = to_local(now) if now is not None else local_now()
    src = source if source is not None else SqlShouldHaveRunSource()

    try:
        tasks = list(src.list_enabled_tasks())
    except Exception as exc:  # noqa: BLE001 - 取不到清单 = 判不出来，必须响亮
        err = f"{type(exc).__name__}: {exc}"
        logger.error("盘点器取数失败（启用任务清单）: %s", err)
        return ShouldHaveRunReport(
            verdicts=(
                ShouldHaveRunVerdict(
                    task_id=-1, task_name="<启用任务清单>", cron_expression="",
                    expected_slot=None, last_run_at=None, last_run_status=None,
                    verdict=VERDICT_UNKNOWN, reason=f"取数失败，无法判定: {err}",
                ),
            ),
            checked_at=now, lookback_days=lookback_days, source_error=err,
            config_guard=apply_config_guard,
        )

    verdicts: List[ShouldHaveRunVerdict] = []
    for task in tasks:
        lookup_error: Optional[BaseException] = None
        latest = latest_missed = latest_handled = None
        try:
            latest = src.latest_run(task.task_id)
            latest_handled = src.latest_handled_run(task.task_id)
        except Exception as exc:  # noqa: BLE001 - 单任务取数失败 → 该任务 unknown
            lookup_error = exc
        if lookup_error is None:
            try:
                latest_missed = src.latest_missed_run(task.task_id)
            except Exception as exc:  # noqa: BLE001 - missed 记账读不到不影响主判据
                logger.warning("读取任务 %s 的 missed 记账失败: %s", task.name, exc)

        verdicts.append(
            judge_task(
                task, now=now, latest_run=latest, latest_missed_run=latest_missed,
                latest_handled_run=latest_handled,
                lookup_error=lookup_error, lookback_days=lookback_days,
                apply_config_guard=apply_config_guard,
            )
        )

    return ShouldHaveRunReport(
        verdicts=tuple(verdicts), checked_at=now, lookback_days=lookback_days,
        config_guard=apply_config_guard,
    )


def summarize(report: ShouldHaveRunReport) -> Dict[str, Any]:
    """机器可读摘要（`--json` 与探针共用同一形状，避免两套口径）。"""
    return {
        "checked_at": _iso(report.checked_at),
        "lookback_days": report.lookback_days,
        "config_guard": report.config_guard,
        "checked": len(report.verdicts),
        "ok": report.ok,
        "missed_count": len(report.missed),
        "unknown_count": len(report.unknown),
        "guarded_count": len(report.guarded),
        "source_error": report.source_error,
        "verdicts": [v.as_dict() for v in report.verdicts],
        "missed": [v.as_dict() for v in report.missed],
        "unknown": [v.as_dict() for v in report.unknown],
        "guarded": [v.as_dict() for v in report.guarded],
        "dedup_keys": report.dedup_keys,
    }


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None
