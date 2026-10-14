#!/usr/bin/env python
"""外部健康探针：服务存活 + 数据新鲜度 + 调度活性（REQ-261001145152-3982 · t-cf3f82；
REQ-261004154902-a7cd · FR-8 · t-5103ce）

## 为什么需要它

本仓已经**静默死亡过 3 次**（CLAUDE.md 自述：08-02 盯盘消失一周、08-05 调度死讯静默 8 天；
2026-10-01 实测第 3 次：服务停摆 18 天、K 线停在 09-11 而无人知晓）。
三次的共同点不是"没有监控代码"，而是**监控跑在被监控的进程里**——进程一死，监控一起死。

所以本探针的硬约束是：**不 import 被监控服务、不依赖它的任何线程**，只做外部可判定的事：

1. `scheduler_service`：端口能不能连（5001 API / 8080 Agent OS）；
2. `kline_freshness`：数据有没有过期（`quant.daily_klines` 的 `max(trade_date)` 是否落后）；
3. `scheduler_switches`（2026-10-04 新增）：`DISABLE_APSCHEDULER` / `DISABLE_DAILY_JOBS` /
   `DISABLE_WATCH_ENGINE` 有没有被打开——**服务活着但四个开关全开 = 10.5 小时零 run**
   （2026-10-01 21:48–10-02 08:21 实证），旧探针对此完全无感，照样 healthy；
4. `scheduler_liveness`（2026-10-04 新增）：**关键任务该跑没跑**——按 cron 推演"最近应跑时刻"，
   与 `quant.scheduler_runs.started_at` 比对。判据与人工盘点器**共用一份实现**
   （`application/services/should_have_run.py`），避免第二个口径。

## 告警节流（防重演 504 条刷屏）

旧探针 42 小时发过 **504 条同一条误报**（把国庆休市当应有交易日）。现在两条闸门：

- **去重**：同一 `(任务名, 应跑时刻)` / 同一检查项最多告警一次（状态落在 `--state-file`）；
- **边沿**：只有"健康 → 不健康"的跨越才发；持续不健康不重复刷屏。
  （kill -9 服务后 ≤2 个探测周期内必须发出一条「服务停摆」，靠的正是这个边沿。）

## 用法

    python tools/health_probe.py                 # 正常巡检（异常时发通知并 exit 2）
    python tools/health_probe.py --dry-run       # 只打印将要发出的告警，不发、不落节流状态
    python tools/health_probe.py --api-port 5999 # 指向不存在的端口（用于验证告警路径）
    python tools/health_probe.py --max-lag-days -1   # 强制判定为过期（负向验证）
    python tools/health_probe.py --state-file /tmp/p.json   # 换节流状态文件（不影响生产节流账）

## 退出码（fail-loud：让 launchd/cron 的状态可见，而不是静默 exit 0）

    0 = 全部健康
    2 = 有异常（已尝试告警）
    3 = 探针自身出错（配置/依赖问题，不是被监控对象的问题）
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover —— 仅供类型标注；运行时由 last_closed_trading_day 返回
    from application.services.trading_day_resolver import TradingDayResult

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_API_PORT = 5001
DEFAULT_AGENT_OS_PORT = 8080

# 调度总开关：任一为真 = 服务虽活着但对应调度线程不跑（2026-10-01 那次 10.5 小时零 run 的成因）
DISABLE_SWITCHES = ("DISABLE_APSCHEDULER", "DISABLE_DAILY_JOBS", "DISABLE_WATCH_ENGINE")
_TRUTHY = {"1", "true", "yes", "on", "y", "t"}

# 节流状态文件：launchd 每 300 秒拉起一个新进程，进程内去重无效，必须跨进程落盘。
DEFAULT_STATE_PATH = Path(__file__).resolve().parents[1] / "logs" / "health_probe_state.json"
ALERT_KEY_TTL_DAYS = 14  # 去重键保留期（超过即剪枝，避免状态文件无界增长）

# 新判据（调度活性 / 调度总开关）的观察开关：**默认 off**（详见 scheduler_alert_enabled）。
SCHEDULER_ALERT_ENV = "HEALTH_PROBE_SCHEDULER_ALERT"


# ── 探针本身 ────────────────────────────────────────────────────────────

def probe_port(host: str, port: int, timeout: float = 3.0) -> Dict[str, Any]:
    """TCP 连通性探针（不依赖被监控进程的 HTTP 实现，能连上即视为存活）。"""
    started = datetime.now()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "name": f"{host}:{port}",
                "ok": True,
                "elapsed_ms": int((datetime.now() - started).total_seconds() * 1000),
            }
    except OSError as exc:
        return {
            "name": f"{host}:{port}",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def expected_trading_day(ref: datetime | None = None) -> "TradingDayResult":
    """应有数据的最近交易日 = 「最近一个已收盘的交易日」。

    2026-10-04（REQ-261004102115-d3de）：原实现复用 `daily_jobs_bootstrap._last_trading_day`，
    而那套口径**只排周末、不排节假日** —— 国庆休市期间把 2026-10-02 当成应有交易日，
    对着一份完好的数据报"K 线滞后 2 天"。现在改走 `application.services.trading_day_resolver`
    的唯一口径（日历表 → AKShare → 工作日回退），并把**判定来源**一并带出去：
    降级必须让人看得见，否则休市期的误报会以"看起来正常"的样子回来。
    """
    from application.services.trading_day_resolver import last_closed_trading_day

    return last_closed_trading_day(ref)


def probe_freshness(max_lag_days: int) -> Dict[str, Any]:
    """数据新鲜度探针：K 线最新交易日 vs 应有交易日。"""
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    resolved = expected_trading_day()
    expected = resolved.date
    # 对外契约（interfaces.md）：calendar = 日历判的（表或 provider），weekday_fallback = 降级口径
    expected_source = "weekday_fallback" if resolved.degraded else "calendar"
    with get_engine().connect() as conn:
        latest = conn.execute(text("SELECT max(trade_date) FROM quant.daily_klines")).scalar()
        factor_latest = conn.execute(text("SELECT max(factor_date) FROM quant.factor_values")).scalar()

    if latest is None:
        return {
            "name": "kline_freshness",
            "ok": False,
            "error": "quant.daily_klines 无任何数据",
            "expected": str(expected),
        }

    lag = (expected - latest).days
    return {
        "name": "kline_freshness",
        "ok": lag <= max_lag_days,
        "expected": str(expected),
        "expected_source": expected_source,
        "expected_degraded": bool(resolved.degraded),
        "kline_latest": str(latest),
        "factor_latest": str(factor_latest) if factor_latest else None,
        "lag_days": lag,
        "max_lag_days": max_lag_days,
    }


def scheduler_alert_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    """新判据（调度活性 / 调度总开关）是否**计入不健康并外发**。**默认 off（观察模式）**。

    为什么默认 off —— 本仓的既有规矩是「**改判据必须先 report 清点、再切 fail**，别直接收紧」：
    探针刚因为国庆休市误报发过 **504 条**同一条告警，告警疲劳本身就是一种静默死亡。
    新判据第一次上线时，谁也没法保证它的阈值已经校准（例如 2026-10-04 实测：
    启用集合当天刚被批量调整过，11 行的 `updated_at` 是同一微秒，护栏口径还在人工裁决中），
    此时直接让它外发，就等于拿用户的注意力当校准工具。

    所以默认只**算**、只**写**（JSON / 日志 / `missed=[...]` 一样不少，`tools/check_should_have_run.py`
    照样 exit 2），但不计入 `healthy`、不触发通知。校准完成、人确认口径干净后，
    设 `HEALTH_PROBE_SCHEDULER_ALERT=true` 才切到会告警的状态（与 notify-guard 的
    off/report/fail 同一种做法：**先清点、再收紧**）。
    """
    source = os.environ if env is None else env
    return str(source.get(SCHEDULER_ALERT_ENV, "")).strip().lower() in _TRUTHY


def probe_disable_switches(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """调度总开关探针：`DISABLE_*` 任一为真 → 「降级健康」（服务活着，但这类任务不会再跑）。

    为什么这算不健康而不是"正常维护状态"：2026-10-01 21:48 – 10-02 08:21 服务活着、
    探针 healthy，但四个 DISABLE 全开、**10.5 小时零 run** —— 开关本身是维护工具，
    但"开着却没人记得关"与"服务死了"对业务是同一个后果：任务不跑。
    因此这里判不健康并写明"若是有意维护请忽略"，而不是静默放行。

    是否**计入** `healthy`/外发由 `scheduler_alert_enabled()` 决定（默认观察模式）。
    """
    source = os.environ if env is None else env
    disabled = [name for name in DISABLE_SWITCHES
                if str(source.get(name, "")).strip().lower() in _TRUTHY]
    observing = not scheduler_alert_enabled(source)
    check: Dict[str, Any] = {
        "name": "scheduler_switches",
        "ok": not disabled,
        "disabled": disabled,
        "checked_switches": list(DISABLE_SWITCHES),
        "degraded": bool(disabled),
        "observe": observing,
        "counts_toward_health": not observing,
    }
    if disabled:
        check["error"] = (
            "调度总开关被打开（"
            + " / ".join(f"{n}=true" for n in disabled)
            + "）：服务虽然活着，但对应调度不会再跑任何任务——"
            "若是有意维护请忽略，否则这就是 2026-10-01 那次 10.5 小时零 run 的形态"
            + ("（观察模式：只记账、未计入告警）" if observing else "")
        )
    return check


def probe_scheduler_liveness(
    now: Optional[datetime] = None,
    source: Any = None,
    *,
    lookback_days: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    apply_config_guard: bool = True,
) -> Dict[str, Any]:
    """调度活性探针：有任务"该跑没跑" → 不健康。

    判据**不在本文件**：调用 `application.services.should_have_run.audit_should_have_run`
    （与 `tools/check_should_have_run.py` 同一份实现）。这里只做三件探针该做的事：
    把结果翻成探针的 check 形状、把漏跑任务的**(任务名, 应跑时刻)**去重键带出去、
    并把"判不出来"（unknown）**显式暴露**而不是当成健康。

    取不到任务清单（读库失败等）判不健康：**看不见调度 = 最危险的状态**，
    旧探针的三次静默死亡都发生在"监控看不见"的时候。

    是否**计入** `healthy`/外发由 `scheduler_alert_enabled()` 决定：**默认观察模式**
    （算得出、看得见、不外发）。`ok` 字段始终是真实判定，观察与否另用
    `counts_toward_health` 表达 —— 语义不许混在一个字段里。
    """
    from application.services.should_have_run import (
        DEFAULT_LOOKBACK_DAYS,
        audit_should_have_run,
        summarize,
    )

    report = audit_should_have_run(
        now=now, source=source,
        lookback_days=lookback_days if lookback_days is not None else DEFAULT_LOOKBACK_DAYS,
        apply_config_guard=apply_config_guard,
    )
    summary = summarize(report)
    observing = not scheduler_alert_enabled(env)

    missed = summary["missed"]
    unknown = summary["unknown"]
    guarded = summary["guarded"]
    check: Dict[str, Any] = {
        "name": "scheduler_liveness",
        "ok": not missed and not report.source_error,
        "observe": observing,
        "counts_toward_health": not observing,
        "config_guard": report.config_guard,
        "checked": summary["checked"],
        "missed_count": len(missed),
        "unknown_count": len(unknown),
        # 被"配置改动护栏"豁免的（判定 ok，但不是"跑过了"）：显式带出，绝不静默
        "guarded_count": len(guarded),
        "guarded": guarded,
        # 去重键 (任务名, 应跑时刻)：同一漏跑最多告警一次（探针侧按 alert_key 落盘）
        "missed": missed,
        "unknown": unknown,
        "dedup_keys": summary["dedup_keys"],
        "source_error": report.source_error,
    }
    if missed:
        check["error"] = (
            f"{len(missed)} 个启用任务「该跑没跑」："
            + "；".join(
                f"{m['task']}（cron={m['cron']}，应跑 {m['expected_slot'] or '-'}，"
                f"实际最近 run {m['last_run_at'] or '无'}）"
                for m in missed
            )
            + " —— 用 tools/check_should_have_run.py 复核"
            + ("（观察模式：只记账、未计入告警）" if observing else "")
        )
    elif report.source_error:
        check["error"] = f"无法判定调度活性（取数失败）：{report.source_error}"
    elif unknown:
        # 判不出来必须看得见，但不升级为告警（否则"unknown"自己会变成刷屏源）
        check["degraded"] = True
    return check


# ── 告警（必须走 NotificationFacade，禁止自建通道）─────────────────────

def build_alert(results: List[Dict[str, Any]], api_port: int, note: str | None = None) -> Dict[str, Any]:
    bad = [r for r in results if not r["ok"] and r.get("counts_toward_health", True)]
    lines = [
        f"• {r['name']}：{'异常' if not r['ok'] else '正常'}"
        + (f"（{r.get('error')}）" if r.get("error") else "")
        + ("（观察中：未计入告警）" if (not r["ok"] and not r.get("counts_toward_health", True)) else "")
        + (
            f"（K线最新 {r.get('kline_latest')} / 应有 {r.get('expected')}，滞后 {r.get('lag_days')} 天）"
            + ("（⚠️ 交易日历不可用，按工作日口径判定）" if r.get("expected_degraded") else "")
            if r.get("lag_days") is not None
            else ""
        )
        for r in results
    ]
    body = (
        f"巡检时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
        + "\n".join(lines)
        + "\n\n判断依据：API 端口连通性 + quant.daily_klines 新鲜度 + 调度活性（cron 应跑时刻）。"
        + "本告警由外部探针发出（不依赖被监控进程）。"
    )
    if note:
        # 用于"验证告警链路"这类人工注入：必须显式标注，避免被误读成真实故障
        body = f"⚠️【人工验证】{note}\n\n" + body
    return {
        "title": f"🚨 V2 健康探针告警（{len(bad)} 项异常）",
        "text": body,
        "level": "high",
        "source": "health_probe",
        "api_port": api_port,
    }


def send_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
    """经 NotificationFacade 发送（不直接碰 Feishu SDK / webhook）。

    2026-10-01（t-cf3f82）实现记录——两处**按真实契约**修正（首版凭印象写错，会直接 TypeError）：
    - 门面**不能裸构造**：`NotificationFacade(notification_service)` 需要一个通知服务，
      生产单例由 `NotificationFactory.get_instance()` 装配（与其它调用方同一入口）；
    - `send_alert()` 的签名是 `(alert_type, symbol, message, data, mention)`，
      **不是** `(title, message, level, source)`。本探针要发的是不带标的的系统告警，
      故用 `send_text(text, priority, mention_all)` —— 它内部即构造 `SYSTEM_ALERT`。
    """
    from application.notification.notification_factory import NotificationFactory

    facade = NotificationFactory.get_instance()
    ok = facade.send_text(
        text=f"{payload['title']}\n{payload['text']}",
        priority=payload["level"],
        mention_all=False,
    )
    # 注意语义：ok=False 表示**没有一条渠道送达**（2026-10-01 实测正是如此：
    # 渠道选择只挑中 agent→Agent OS，而 8080 不可达 → 告警发不出去）。
    # 首版这里写成 {"sent": true} 是**误导**（"尝试了"不等于"送到了"），故改为 attempted/ok 两字段。
    return {"attempted": True, "ok": bool(ok)}


# ── 节流（去重 + 边沿）──────────────────────────────────────────────────
#
# 为什么必须落盘：launchd 每 300 秒拉起**一个新进程**，进程内集合每次都是空的 ——
# 只在内存里去重等于没有去重（2026-10-04 前 42 小时 504 条同一条误报就是这么来的）。

def load_state(path: Optional[Path] = None) -> Dict[str, Any]:
    """读节流状态；文件缺失/损坏按"全新状态"处理（绝不能因为状态文件坏了就不告警）。"""
    p = Path(path) if path is not None else DEFAULT_STATE_PATH
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data.setdefault("alerted", {})
            return data
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001 - 坏文件按全新状态处理
        print(json.dumps({"state_read_warning": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
    return {"alerted": {}, "last_healthy": None}


def save_state(state: Dict[str, Any], path: Optional[Path] = None) -> None:
    """写节流状态（原子替换）；失败只警告 —— 记账失败不该让探针自己崩掉。"""
    p = Path(path) if path is not None else DEFAULT_STATE_PATH
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, p)
    except Exception as exc:  # noqa: BLE001 - 状态写不进去只是"下次可能重复告警"
        print(json.dumps({"state_write_warning": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))


def _prune_alerted(alerted: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """剪掉过期去重键（避免状态文件无界增长）。"""
    cutoff = now - timedelta(days=ALERT_KEY_TTL_DAYS)
    kept: Dict[str, Any] = {}
    for key, ts in alerted.items():
        try:
            when = datetime.fromisoformat(str(ts))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=now.tzinfo)
        if when >= cutoff:
            kept[key] = ts
    return kept


def problem_keys(results: List[Dict[str, Any]]) -> List[str]:
    """本次**计入告警**的问题去重键。

    - 每个不健康且计入 health 的检查项一个键（`check:<name>`）；
    - 每条漏跑单独一个键（`missed:<任务名>@<应跑时刻>`）—— 这样"新漏跑"能被区分出来，
      而"同一条漏跑"不会每 5 分钟重发一次；
    - 观察模式（`counts_toward_health=False`）的检查**不产生键**：它本来就不外发。
    """
    keys: List[str] = []
    for r in results:
        if r.get("ok", True) or not r.get("counts_toward_health", True):
            continue
        keys.append(f"check:{r['name']}")
        for m in r.get("missed", []) or []:
            task = m.get("task") or m.get("task_name")
            slot = m.get("expected_slot")
            keys.append(f"missed:{task}@{slot}")
    seen, ordered = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            ordered.append(k)
    return ordered


def decide_alert(keys: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
    """两个闸门：**边沿**（健康→不健康才发）或**新键**（这次的问题没见过才发）。

    - 持续不健康且键没变 → 不发（否则就是 504 条刷屏的老路）；
    - 恢复健康后再次不健康（`last_healthy is True`）→ 边沿，发
      （kill -9 后 ≤2 个探测周期内必须响，靠的就是这一条）；
    - 已经观察过的键不再发（跨进程重启也认，因为键落盘在 `--state-file`）。
    """
    alerted = state.get("alerted") or {}
    new_keys = [k for k in keys if k not in alerted]
    edge = state.get("last_healthy") is True
    return {
        "should_alert": bool(keys) and (edge or bool(new_keys)),
        "new_keys": new_keys,
        "edge": edge,
        "already_alerted": [k for k in keys if k in alerted],
    }


# ── 主流程 ──────────────────────────────────────────────────────────────

def perform_probe(
    *,
    host: str = "127.0.0.1",
    api_port: int = DEFAULT_API_PORT,
    check_agent_os: bool = False,
    agent_os_port: int = DEFAULT_AGENT_OS_PORT,
    max_lag_days: int = 1,
    dry_run: bool = False,
    note: Optional[str] = None,
    state_path: Optional[Path] = None,
    now: Optional[datetime] = None,
    source: Any = None,
    sender: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    env: Optional[Dict[str, str]] = None,
    apply_config_guard: bool = True,
) -> int:
    """跑一轮巡检并返回退出码（把参数注入点留出来，便于单测零网络零外发）。

    退出码：0 健康 / 2 有异常（已尝试告警）/ 3 探针自身出错。
    `dry_run=True` 时**不发通知、不落节流状态**（否则"演练"会把真实告警额度吃掉）。
    """
    results: List[Dict[str, Any]] = [probe_port(host, api_port)]
    if check_agent_os:
        results.append(probe_port(host, agent_os_port))

    try:
        results.append(probe_freshness(max_lag_days))
    except Exception as exc:  # 探针自身出错 → exit 3，不与"被监控对象异常"混淆
        print(json.dumps({"probe_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 3

    # 新判据（REQ-261004154902-a7cd · FR-8）：调度总开关 + 关键任务该跑没跑。
    # 两个都**默认观察模式**（只记账不外发），是否计入 health 见 scheduler_alert_enabled。
    results.append(probe_disable_switches(env))
    try:
        results.append(
            probe_scheduler_liveness(
                now=now, source=source, env=env, apply_config_guard=apply_config_guard,
            )
        )
    except Exception as exc:  # noqa: BLE001 - 判不出来必须响亮，但不许击穿探针本身
        observing = not scheduler_alert_enabled(env)
        results.append({
            "name": "scheduler_liveness",
            "ok": False,
            "observe": observing,
            "counts_toward_health": not observing,
            "error": f"调度活性判定自身出错: {type(exc).__name__}: {exc}",
        })

    bad = [r for r in results if not r["ok"] and r.get("counts_toward_health", True)]
    observed = [r for r in results if not r["ok"] and not r.get("counts_toward_health", True)]
    keys = problem_keys(results)
    state = load_state(state_path)
    decision = decide_alert(keys, state)

    report = {
        "healthy": not bad,
        "checks": results,
        "observed_unhealthy": [r["name"] for r in observed],
        "problem_keys": keys,
        "alert_decision": decision,
        "scheduler_alert_enabled": scheduler_alert_enabled(env),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    if not bad:
        if not dry_run:
            # 只记边沿与剪枝后的键：健康时不新标记任何键（否则漏跑会被"顺手"静音）
            state["last_healthy"] = True
            state["alerted"] = _prune_alerted(state.get("alerted") or {}, datetime.now())
            state["updated_at"] = datetime.now().isoformat()
            save_state(state, state_path)
        return 0

    payload = build_alert(results, api_port, note=note)
    if dry_run:
        print("\n[--dry-run] 以下告警**未发送**：")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    if not decision["should_alert"]:
        # 节流生效：同一批问题已经报过，不再打扰（这正是"探针 3 天 504 条"的反面）
        print(json.dumps({"alert_suppressed": True, **decision}, ensure_ascii=False))
        return 2

    try:
        sent = sender(payload) if sender is not None else send_alert(payload)
        print(json.dumps(sent, ensure_ascii=False))
    except Exception as exc:
        # 告警发不出去也必须响亮：已经是异常状态，再静默就彻底没人知道了
        print(json.dumps({"alert_send_failed": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))

    # 记账按"已尝试"而非"已送达"：发送失败若不计账，就会每 5 分钟重发同一批
    # （那条 504 条刷屏的老路）。发送结果一并留痕，供人事后核对。
    stamp = datetime.now().isoformat()
    alerted = dict(state.get("alerted") or {})
    for key in keys:
        alerted[key] = stamp
    state["alerted"] = _prune_alerted(alerted, datetime.now())
    state["last_healthy"] = False
    state["updated_at"] = stamp
    state["last_keys"] = keys
    save_state(state, state_path)
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="V2 外部健康探针（存活 + 数据新鲜度 + 调度活性）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    ap.add_argument("--check-agent-os", action="store_true",
                    help="同时检查 Agent OS（8080）。**默认不查**——理由见下")
    ap.add_argument("--agent-os-port", type=int, default=DEFAULT_AGENT_OS_PORT)
    ap.add_argument("--max-lag-days", type=int, default=1,
                    help="允许的滞后天数（默认 1：节后第一天不误报）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要发出的告警，不真发、不落节流状态")
    ap.add_argument("--note", default=None,
                    help="人工验证注记：会以「⚠️【人工验证】…」前缀加在告警正文最前")
    ap.add_argument("--state-file", default=None,
                    help=f"节流状态文件（缺省 {DEFAULT_STATE_PATH}）")
    ap.add_argument("--no-config-guard", action="store_true",
                    help="关掉调度活性判定的「配置改动护栏」（复核改动前就漏掉的缺口时用）")
    args = ap.parse_args(argv)

    # 2026-10-01（t-cf3f82 联调发现）：Agent OS 默认**不纳入告警条件**。
    # 理由：本仓设计本就容许 Agent OS 缺席（main.py 注册失败即回退本地 APScheduler，
    # 见 CLAUDE.md「调度架构」），而这台机器上 8080 常态不在线 —— 若默认把它算异常，
    # 探针会每 5 分钟报一次"8080 不可达"，几天内必然被忽略（告警疲劳 = 另一种静默死亡）。
    # 需要监控它时显式加 --check-agent-os。
    return perform_probe(
        host=args.host,
        api_port=args.api_port,
        check_agent_os=args.check_agent_os,
        agent_os_port=args.agent_os_port,
        max_lag_days=args.max_lag_days,
        dry_run=args.dry_run,
        note=args.note,
        state_path=Path(args.state_file) if args.state_file else None,
        apply_config_guard=not args.no_config_guard,
    )


if __name__ == "__main__":
    raise SystemExit(main())
