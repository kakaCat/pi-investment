#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scheduler_watchdog — 双调度系统独立看门狗（RFC 011 第3层）

独立于 v2(:5001) 与 Agent OS(:8080) 任一进程的调度健康监控：
  - 进程探活：curl 两系统 /health
  - 期望 vs 实际比对：按 cron 推算"过去 N 小时应触发时刻"，比对 runs 表实际记录
  - zombie 检测：status='running' 超阈值未闭环
  - 失联判定：进程探活失败 且 该时段有任务应执行却无记录

告警：飞书 bot webhook 直发（不依赖 v2/Agent OS 通知链路），同一问题去重
（写 quant.scheduler_watchdog_log，恢复前只报一次，恢复后报一次"已恢复"）。

补跑策略（任务级字段，本期只告警不自动补跑）：
  - v2: quant.scheduler_tasks.compensation_enabled (t=auto_rerun / f=alert_only)
  - Agent OS: public.tasks.metadata->>'watchdog' (auto_rerun / skip / 默认 alert_only)

运行方式：launchd com.pi-investment.scheduler-watchdog.plist 每 15 分钟触发。
仅依赖标准库 + psycopg2 + croniter（用 quantsys-v2 venv 解释器运行）。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from croniter import croniter

# ---------------------------------------------------------------- 配置
DB_DSN = os.environ.get(
    "WATCHDOG_DB_DSN",
    "postgresql://yunpeng@localhost:5432/quant_investment",
)
FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK_URL",
    "https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829",
)
V2_HEALTH = os.environ.get("V2_HEALTH_URL", "http://localhost:5001/api/health")
AGENTOS_HEALTH = os.environ.get("AGENTOS_HEALTH_URL", "http://localhost:8080/health")
V2_TRIGGER_API = "http://localhost:5001/api/scheduler/tasks/{id}/trigger"
AGENTOS_TRIGGER_API = "http://localhost:8080/api/v1/scheduler/tasks/{id}/trigger"

LOOKBACK_HOURS = int(os.environ.get("WATCHDOG_LOOKBACK_HOURS", "26"))  # 覆盖日频任务
ZOMBIE_MINUTES = int(os.environ.get("WATCHDOG_ZOMBIE_MINUTES", "60"))
MATCH_TOLERANCE_MIN = 5          # 期望时刻 ±5min 内的实际 run 视为命中
MIN_MISSED_AGE_MIN = 20          # 期望时刻须早于 now-20min 才算"错过"（防边界误报）

# 自动补跑开关：本期默认关（只告警+建议命令）。True 时对 auto_rerun 任务调 trigger API。
AUTO_RERUN_ENABLED = os.environ.get("WATCHDOG_AUTO_RERUN", "false").lower() == "true"

CST = timezone(timedelta(hours=8))
SIGNATURE = "—— scheduler-watchdog"


# ---------------------------------------------------------------- 基础工具
def db_conn():
    return psycopg2.connect(DB_DSN)


def make_croniter(expr, base):
    """5 字段=标准 cron；6 字段=秒在前（robfig/cron）。"""
    n = len(expr.split())
    return croniter(expr, base, second_at_beginning=(n == 6))


def expected_times(cron_expr, since_utc, now_utc, tz=timezone.utc):
    """返回 (since, now - MIN_MISSED_AGE] 窗口内所有应触发时刻（UTC list）。

    cron 表达式的时区解释因系统而异（v2=UTC、Agent OS=Asia/Shanghai），
    故在指定 tz 下用 croniter 推算，再统一转 UTC 与 runs 表比对。
    """
    times = []
    upper = now_utc - timedelta(minutes=MIN_MISSED_AGE_MIN)
    try:
        # croniter 在 tz 本地时间轴上推算
        base_local = since_utc.astimezone(tz)
        it = make_croniter(cron_expr, base_local)
        t_local = it.get_next(datetime)
        guard = 0
        while guard < 500:
            t_utc = t_local.astimezone(timezone.utc)
            if t_utc > upper:
                break
            if t_utc > since_utc:
                times.append(t_utc)
            t_local = it.get_next(datetime)
            guard += 1
    except Exception:
        pass
    return times


def has_run_near(runs, expected_t):
    """runs 为 started_at list（UTC）。±MATCH_TOLERANCE_MIN 内视为命中。"""
    for r in runs:
        if abs((r - expected_t).total_seconds()) <= MATCH_TOLERANCE_MIN * 60:
            return True
    return False


def probe_health(url, timeout=8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def send_feishu(title, content):
    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title},
                           "template": "red"},
                "elements": [{"tag": "div", "text": {"tag": "lark_md",
                                                    "content": content + "\n\n" + SIGNATURE}}],
            },
        }
        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"[watchdog] feishu send failed: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------- 告警去重
def ensure_log_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS quant.scheduler_watchdog_log (
                id          BIGSERIAL PRIMARY KEY,
                issue_key   TEXT NOT NULL,          -- 问题唯一键（系统/类型/任务）
                system      TEXT NOT NULL,          -- v2 / agent_os
                issue_type  TEXT NOT NULL,          -- missed / zombie / offline
                detail      TEXT,
                action      TEXT,                   -- alerted / rerun
                first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
                resolved    BOOLEAN NOT NULL DEFAULT false,
                resolved_at TIMESTAMPTZ
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_watchdog_issue_key "
            "ON quant.scheduler_watchdog_log(issue_key, resolved)"
        )
    conn.commit()


def load_open_issues(conn):
    """返回 {issue_key: id} 当前未恢复的问题。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, issue_key FROM quant.scheduler_watchdog_log WHERE resolved=false"
        )
        return {k: i for i, k in cur.fetchall()}


def record_issue(conn, key, system, itype, detail, action):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM quant.scheduler_watchdog_log WHERE issue_key=%s AND resolved=false",
            (key,),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE quant.scheduler_watchdog_log SET last_seen=now(), detail=%s, action=%s WHERE id=%s",
                (detail, action, row[0]),
            )
            return False  # 已存在，不重复告警
        cur.execute(
            "INSERT INTO quant.scheduler_watchdog_log(issue_key, system, issue_type, detail, action) "
            "VALUES (%s,%s,%s,%s,%s)",
            (key, system, itype, detail, action),
        )
        return True  # 新问题，应告警


def resolve_issues(conn, still_open_keys, open_issues):
    """把不再出现的问题标记 resolved，返回 [(key)] 供"已恢复"通知。"""
    resolved_now = []
    for key, rid in open_issues.items():
        if key not in still_open_keys:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE quant.scheduler_watchdog_log SET resolved=true, resolved_at=now() WHERE id=%s",
                    (rid,),
                )
            resolved_now.append(key)
    return resolved_now


# ---------------------------------------------------------------- 系统扫描
def scan_v2(conn, now_utc, since_utc):
    """返回 issues: list of dict(key, type, task, detail, policy, task_id)"""
    issues = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, name, cron_expression, command, compensation_enabled, last_run_at "
            "FROM quant.scheduler_tasks WHERE is_enabled=true "
            "AND cron_expression NOT LIKE 'managed_by_agent_%'"
        )
        tasks = cur.fetchall()

        # v2 已排期豁免：apscheduler_jobs 中 next_run_time 在未来的任务不算 missed
        now_epoch = now_utc.timestamp()
        cur.execute(
            "SELECT id FROM public.apscheduler_jobs "
            "WHERE id LIKE 'task_%%' AND next_run_time > %s",
            (now_epoch,),
        )
        scheduled_ids = set()
        for r in cur.fetchall():
            try:
                scheduled_ids.add(int(r["id"].split("_", 1)[1]))
            except Exception:
                pass

        for t in tasks:
            tid, name, cron = t["id"], t["name"], t["cron_expression"]
            policy = "auto_rerun" if t["compensation_enabled"] else "alert_only"
            # 实时高频任务（*/5）跳过 missed 判定（窗口匹配无意义）
            if cron.strip().startswith("*/"):
                continue
            # v2 APScheduler 用 timezone='Asia/Shanghai'（apscheduler_service.py:71），
            # apscheduler_jobs.next_run_time 实测 cron `0 8` 排期在北京 08:00 → cron 按北京解读。
            # （注：8/26 前的旧 scheduler_runs 是 APScheduler 未启用期的遗留，非当前口径）
            exps = expected_times(cron, since_utc, now_utc, tz=CST)  # v2 cron 按北京时区
            if not exps:
                continue
            cur.execute(
                "SELECT started_at FROM quant.scheduler_runs "
                "WHERE task_id=%s AND started_at >= %s ORDER BY started_at",
                (tid, since_utc),
            )
            runs = [r["started_at"] for r in cur.fetchall()]
            missed = [e for e in exps if not has_run_near(runs, e)]
            # 已排期（job store 有未来 next_run）则豁免 missed
            if missed and tid in scheduled_ids:
                continue
            for e in missed:
                issues.append({
                    "key": f"v2:missed:{tid}:{e.strftime('%Y%m%d%H%M')}",
                    "type": "missed", "system": "v2", "task_id": tid,
                    "task": name, "policy": policy,
                    "detail": f"应于 {e.astimezone(CST):%m-%d %H:%M} 执行（{cron}）",
                })

        # zombie：running 超阈值
        cur.execute(
            "SELECT r.id, r.started_at, t.name FROM quant.scheduler_runs r "
            "JOIN quant.scheduler_tasks t ON t.id=r.task_id "
            "WHERE r.status='running' AND r.started_at < %s",
            (now_utc - timedelta(minutes=ZOMBIE_MINUTES),),
        )
        for r in cur.fetchall():
            hrs = (now_utc - r["started_at"]).total_seconds() / 3600
            issues.append({
                "key": f"v2:zombie:{r['id']}",
                "type": "zombie", "system": "v2", "task_id": None,
                "task": r["name"], "policy": "alert_only",
                "detail": f"run #{r['id']} 卡 running {hrs:.1f}h（>{ZOMBIE_MINUTES}min）",
            })
    return issues


def scan_agent_os(conn, now_utc, since_utc):
    issues = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, name, cron, command, metadata FROM public.tasks WHERE enabled=true"
        )
        tasks = cur.fetchall()
        for t in tasks:
            tid, name, cron = str(t["id"]), t["name"], t["cron"]
            meta = t.get("metadata") or {}
            policy = meta.get("watchdog", "alert_only")
            if policy == "skip":      # /bin/true 占位不监控
                continue
            if not cron:
                continue
            exps = expected_times(cron, since_utc, now_utc, tz=CST)  # Agent OS cron 按北京时区
            if not exps:
                continue
            cur.execute(
                "SELECT started_at FROM public.task_runs "
                "WHERE task_id=%s AND started_at >= %s ORDER BY started_at",
                (tid, since_utc),
            )
            runs = [r["started_at"] for r in cur.fetchall()]
            for e in exps:
                if not has_run_near(runs, e):
                    issues.append({
                        "key": f"os:missed:{tid}:{e.strftime('%Y%m%d%H%M')}",
                        "type": "missed", "system": "agent_os", "task_id": tid,
                        "task": name, "policy": policy,
                        "detail": f"应于 {e.astimezone(CST):%m-%d %H:%M} 执行（{cron}）",
                    })

        cur.execute(
            "SELECT r.id, r.started_at, t.name FROM public.task_runs r "
            "JOIN public.tasks t ON t.id=r.task_id "
            "WHERE r.status='running' AND r.started_at < %s",
            (now_utc - timedelta(minutes=ZOMBIE_MINUTES),),
        )
        for r in cur.fetchall():
            hrs = (now_utc - r["started_at"]).total_seconds() / 3600
            issues.append({
                "key": f"os:zombie:{r['id']}",
                "type": "zombie", "system": "agent_os", "task_id": None,
                "task": r["name"], "policy": "alert_only",
                "detail": f"run 卡 running {hrs:.1f}h（>{ZOMBIE_MINUTES}min）",
            })
    return issues


# ---------------------------------------------------------------- 主流程
def main():
    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=LOOKBACK_HOURS)
    conn = db_conn()
    ensure_log_table(conn)
    open_issues = load_open_issues(conn)

    # 1. 进程探活
    v2_up = probe_health(V2_HEALTH)
    os_up = probe_health(AGENTOS_HEALTH)
    issues = []
    if not v2_up:
        issues.append({"key": "v2:offline", "type": "offline", "system": "v2",
                       "task": "v2-backend", "policy": "alert_only",
                       "detail": f"探活失败 {V2_HEALTH}"})
    if not os_up:
        issues.append({"key": "os:offline", "type": "offline", "system": "agent_os",
                       "task": "agent-os", "policy": "alert_only",
                       "detail": f"探活失败 {AGENTOS_HEALTH}"})

    # 2. 任务级扫描（系统在线才做 missed 判定；离线时 missed 会刷屏，只报 offline）
    if v2_up:
        issues += scan_v2(conn, now_utc, since_utc)
    if os_up:
        issues += scan_agent_os(conn, now_utc, since_utc)

    # 3. 记录 + 去重 + 告警
    new_alerts, rerun_done = [], []
    still_open = set()
    for it in issues:
        still_open.add(it["key"])
        is_new = record_issue(conn, it["key"], it["system"], it["type"],
                              it["detail"], "alerted")
        if not is_new:
            continue
        # 自动补跑（本期默认关）
        action_line = ""
        if it["type"] == "missed" and it["policy"] == "auto_rerun":
            if AUTO_RERUN_ENABLED and it["task_id"] is not None:
                ok = trigger_rerun(it["system"], it["task_id"])
                rerun_done.append((it, ok))
                action_line = f"\n  → 已自动补跑：{'成功' if ok else '失败'}"
            else:
                action_line = "\n  → 可补跑（auto_rerun）：待人工确认"
        elif it["policy"] == "alert_only":
            action_line = "\n  → 仅告警（alert_only，有副作用需人工评估）"
        new_alerts.append((it, action_line))

    resolved = resolve_issues(conn, still_open, open_issues)
    conn.commit()
    conn.close()

    # 4. 发送
    if new_alerts:
        lines = []
        for it, action_line in new_alerts:
            icon = {"offline": "🔴", "zombie": "🟠", "missed": "🟡"}.get(it["type"], "⚪")
            lines.append(
                f"{icon} **[{it['system']}/{it['type']}]** {it['task']}\n"
                f"  {it['detail']}{action_line}"
            )
        send_feishu(
            f"⚠️ 调度看门狗告警（{len(new_alerts)} 项）",
            "\n\n".join(lines),
        )
    if resolved:
        send_feishu(
            f"✅ 调度看门狗：{len(resolved)} 项已恢复",
            "\n".join(f"- {k}" for k in resolved),
        )

    print(f"[watchdog] {now_utc.astimezone(CST):%Y-%m-%d %H:%M:%S} "
          f"v2_up={v2_up} os_up={os_up} issues={len(issues)} "
          f"new={len(new_alerts)} resolved={len(resolved)}")
    return 0


def trigger_rerun(system, task_id):
    """调对应系统 trigger API 补跑（本期默认不启用）。"""
    url = (V2_TRIGGER_API if system == "v2" else AGENTOS_TRIGGER_API).format(id=task_id)
    try:
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"[watchdog] rerun {system}/{task_id} failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # 看门狗自身异常也要尽力告警（防止静默失效）
        print(f"[watchdog] FATAL: {e}", file=sys.stderr)
        try:
            send_feishu("🔴 调度看门狗自身异常", f"```\n{e}\n```")
        except Exception:
            pass
        sys.exit(1)
