#!/usr/bin/env python
"""外部健康探针：服务存活 + 数据新鲜度（REQ-261001145152-3982 · t-cf3f82）

## 为什么需要它

本仓已经**静默死亡过 3 次**（CLAUDE.md 自述：08-02 盯盘消失一周、08-05 调度死讯静默 8 天；
2026-10-01 实测第 3 次：服务停摆 18 天、K 线停在 09-11 而无人知晓）。
三次的共同点不是"没有监控代码"，而是**监控跑在被监控的进程里**——进程一死，监控一起死。

所以本探针的硬约束是：**不 import 被监控服务、不依赖它的任何线程**，只做两件外部可判定的事：
1. 端口能不能连（5001 API / 8080 Agent OS）；
2. 数据有没有过期（`quant.daily_klines` 的 `max(trade_date)` 是否落后于应有交易日）。

## 用法

    python tools/health_probe.py                 # 正常巡检（异常时发通知并 exit 2）
    python tools/health_probe.py --dry-run       # 只打印将要发出的告警，不发
    python tools/health_probe.py --api-port 5999 # 指向不存在的端口（用于验证告警路径）
    python tools/health_probe.py --max-lag-days -1   # 强制判定为过期（负向验证）

## 退出码（fail-loud：让 launchd/cron 的状态可见，而不是静默 exit 0）

    0 = 全部健康
    2 = 有异常（已尝试告警）
    3 = 探针自身出错（配置/依赖问题，不是被监控对象的问题）
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_API_PORT = 5001
DEFAULT_AGENT_OS_PORT = 8080


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


def expected_trading_day(today: date | None = None) -> date:
    """应有数据的最近交易日。

    优先复用服务自身的口径（`daily_jobs_bootstrap._last_trading_day`），避免探针与服务
    对"哪天该有数据"给出两套答案；无法 import 时退化为"工作日回退"的保守实现。
    """
    today = today or date.today()
    try:
        from adapters.inbound.fastapi_app.daily_jobs_bootstrap import _last_trading_day  # type: ignore

        result = _last_trading_day(datetime.now())
        if isinstance(result, str):
            return datetime.strptime(result, "%Y-%m-%d").date()
        if isinstance(result, date):
            return result
    except Exception:
        pass
    cursor = today
    for _ in range(10):
        if cursor.weekday() < 5:
            return cursor
        cursor -= timedelta(days=1)
    return cursor


def probe_freshness(max_lag_days: int) -> Dict[str, Any]:
    """数据新鲜度探针：K 线最新交易日 vs 应有交易日。"""
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    expected = expected_trading_day()
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
        "kline_latest": str(latest),
        "factor_latest": str(factor_latest) if factor_latest else None,
        "lag_days": lag,
        "max_lag_days": max_lag_days,
    }


# ── 告警（必须走 NotificationFacade，禁止自建通道）─────────────────────

def build_alert(results: List[Dict[str, Any]], api_port: int, note: str | None = None) -> Dict[str, Any]:
    bad = [r for r in results if not r["ok"]]
    lines = [
        f"• {r['name']}：{'异常' if not r['ok'] else '正常'}"
        + (f"（{r.get('error')}）" if r.get("error") else "")
        + (
            f"（K线最新 {r.get('kline_latest')} / 应有 {r.get('expected')}，滞后 {r.get('lag_days')} 天）"
            if r.get("lag_days") is not None
            else ""
        )
        for r in results
    ]
    body = (
        f"巡检时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
        + "\n".join(lines)
        + "\n\n判断依据：API 端口连通性 + quant.daily_klines 新鲜度。"
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


# ── 主流程 ──────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="V2 外部健康探针（存活 + 数据新鲜度）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    ap.add_argument("--check-agent-os", action="store_true",
                    help="同时检查 Agent OS（8080）。**默认不查**——理由见下")
    ap.add_argument("--agent-os-port", type=int, default=DEFAULT_AGENT_OS_PORT)
    ap.add_argument("--max-lag-days", type=int, default=1,
                    help="允许的滞后天数（默认 1：节后第一天不误报）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要发出的告警，不真发")
    ap.add_argument("--note", default=None,
                    help="人工验证注记：会以「⚠️【人工验证】…」前缀加在告警正文最前")
    args = ap.parse_args()

    # 2026-10-01（t-cf3f82 联调发现）：Agent OS 默认**不纳入告警条件**。
    # 理由：本仓设计本就容许 Agent OS 缺席（main.py 注册失败即回退本地 APScheduler，
    # 见 CLAUDE.md「调度架构」），而这台机器上 8080 常态不在线 —— 若默认把它算异常，
    # 探针会每 5 分钟报一次"8080 不可达"，几天内必然被忽略（告警疲劳 = 另一种静默死亡）。
    # 需要监控它时显式加 --check-agent-os。
    results: List[Dict[str, Any]] = [probe_port(args.host, args.api_port)]
    if args.check_agent_os:
        results.append(probe_port(args.host, args.agent_os_port))

    try:
        results.append(probe_freshness(args.max_lag_days))
    except Exception as exc:  # 探针自身出错 → exit 3，不与"被监控对象异常"混淆
        print(json.dumps({"probe_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 3

    bad = [r for r in results if not r["ok"]]
    report = {"healthy": not bad, "checks": results}
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    if not bad:
        return 0

    payload = build_alert(results, args.api_port, note=args.note)
    if args.dry_run:
        print("\n[--dry-run] 以下告警**未发送**：")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    try:
        sent = send_alert(payload)
        print(json.dumps(sent, ensure_ascii=False))
    except Exception as exc:
        # 告警发不出去也必须响亮：已经是异常状态，再静默就彻底没人知道了
        print(json.dumps({"alert_send_failed": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
