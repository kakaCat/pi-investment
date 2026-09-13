"""策略闭环（strategy_loop.py，2026-09-13 w-c8cae280）

把"研究 → 评估 → 门槛 → 注册 → 绑定 → 跟踪 → 退役 → 心得"接成可执行的一条链。
评估口径复用 strategy_lab（T+1、次日开盘成交、含成本、篮子等权）。

命令：
  gate     <file.py|strategy_id>                     多 universe × 多窗口 过门槛判定（不写库）
  register <file.py|strategy_id> --name X [--force]  过门槛才注册（POST /api/strategies/create）+ 写 registry
  track                                              列出 registry 策略现状（active/最近回测证据）
  retire   <strategy_id> [--delete] [--reason R]     停用（SQL）或删除（带备份），同步 registry 与 journal
  journal  <text>                                    追加一条心得/实验记录
"""
import argparse, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import strategy_lab as lab  # noqa: E402

BASE = "http://127.0.0.1:5001"
REGISTRY = ROOT / "config" / "strategy_registry.json"
JOURNAL = ROOT.parent / "docs" / "work-logs" / "2026-09" / "strategy-research-journal.md"
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))

WINDOWS = [("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31"), ("2025-01-01", "2026-09-11")]
GATE = {"median_cagr": 0.08, "worst_cagr": -0.05, "worst_dd": -0.20, "median_sharpe": 0.8,
        "min_trades": 100, "control_median_cagr": 0.0}


def psql(q):
    return subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                          capture_output=True, text=True, env=ENV, check=True).stdout.strip()


def universes():
    pool = [s for s in psql("select string_agg(symbol, ',') from (select jsonb_array_elements(members)->>'symbol' as symbol from quant.stock_pools where id=35) t").split(",") if s]
    ctrl = [s for s in psql("select string_agg(symbol, ',') from (select symbol from quant.daily_klines where trade_date >= '2023-01-01' group by 1 having count(*) > 600 order by symbol limit 30) t").split(",") if s]
    return {"pool35": pool, "control30": ctrl}


def load_source(target):
    if target.endswith(".py"):
        return Path(target).read_text(encoding="utf-8"), {}, Path(target).stem
    code, params = lab.fetch_strategy(int(target))
    return code, params, "strategy_" + str(target)


def cmd_gate(target, quiet=False):
    code, params, label = load_source(target)
    grid, pool_c, pool_dd, pool_sh, ctrl_c = [], [], [], [], []
    trades = 0
    for uname, syms in universes().items():
        for (s, e) in WINDOWS:
            r = lab.evaluate(code, params, syms, s, e, label)["portfolio"]
            if not r.get("ok"):
                continue
            grid.append({"universe": uname, "window": s + "~" + e, "cagr": float(r["cagr"]),
                         "max_dd": float(r["max_dd"]), "sharpe": float(r["sharpe"]), "trades": int(r.get("trades", 0) or 0)})
            if uname == "pool35":
                pool_c.append(r["cagr"]); pool_dd.append(r["max_dd"]); pool_sh.append(r["sharpe"])
            else:
                ctrl_c.append(r["cagr"])
            trades += int(r.get("trades") or 0)
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0.0
    res = {"median_cagr": float(round(med(pool_c), 4)), "worst_cagr": float(round(min(pool_c), 4)) if pool_c else 0.0,
           "worst_dd": float(round(min(pool_dd), 4)) if pool_dd else 0.0, "median_sharpe": float(round(med(pool_sh), 2)),
           "trades": int(trades), "control_median_cagr": float(round(med(ctrl_c), 4))}
    def _b(x):
        return bool(x)

    checks = {
        "median_cagr": res["median_cagr"] >= GATE["median_cagr"],
        "worst_cagr": res["worst_cagr"] >= GATE["worst_cagr"],
        "worst_dd": res["worst_dd"] >= GATE["worst_dd"],
        "median_sharpe": res["median_sharpe"] >= GATE["median_sharpe"],
        "min_trades": res["trades"] >= GATE["min_trades"],
        "control_median_cagr": res["control_median_cagr"] >= GATE["control_median_cagr"],
    }
    checks = {k: _b(v) for k, v in checks.items()}
    verdict = bool(all(checks.values()))
    if not quiet:
        print("%-11s %-22s %8s %9s %7s %7s" % ("universe", "window", "CAGR", "maxDD", "Sharpe", "trades"))
        for g in grid:
            print("%-11s %-22s %8s %9s %7s %7s" % (g["universe"], g["window"], g["cagr"], g["max_dd"], g["sharpe"], g["trades"]))
        print("--- 门槛判定 ---")
        for k in GATE:
            actual = res["trades"] if k == "min_trades" else res[k]
            print("  %-22s %-5s 实测 %s / 要求 %s" % (k, "PASS" if checks[k] else "FAIL", actual, GATE[k]))
        print("总判定：%s" % ("通过" if verdict else "未通过"))
    return {"label": label, "verdict": verdict, "checks": checks, "metrics": res, "grid": grid}


def cmd_register(target, name, force=False, desc=""):
    code, params, label = load_source(target)
    g = cmd_gate(target)
    if not g["verdict"] and not force:
        print("未过门槛，拒绝注册（确需登记观察项用 --force）")
        return 1
    body = {"name": name, "code": code, "code_type": "indicator",
            "description": desc or ("通过 strategy_loop 门槛注册（" + label + "）")}
    r = requests.post(BASE + "/api/strategies/create", json=body, timeout=60)
    data = r.json()
    sid = (data.get("data") or {}).get("id")
    print("注册结果:", r.status_code, "strategy_id=", sid)
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"strategies": []}
    reg["strategies"].append({"strategy_id": sid, "name": name, "source": label,
                              "registered_at": datetime.now().isoformat(timespec="seconds"),
                              "forced": bool(force and not g["verdict"]), "gate": g["metrics"],
                              "checks": g["checks"], "status": "active"})
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    cmd_journal("注册策略 " + str(sid) + " " + name + "（门槛：" + ("通过" if g["verdict"] else "强制登记") + "，指标 " + json.dumps(g["metrics"], ensure_ascii=False) + "）")
    return 0


def cmd_track():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"strategies": []}
    if not reg["strategies"]:
        print("registry 为空：尚无通过门槛注册的策略")
        return 0
    print("%-6s %-26s %-9s %-7s %s" % ("id", "name", "status", "active", "最近回测证据"))
    for s in reg["strategies"]:
        sid = s["strategy_id"]
        act = psql("select is_active from quant.strategy_configs where id=" + str(int(sid))) or "-"
        ev = psql("select coalesce(round(total_return::numeric,3)::text,'-') || ' / ' || coalesce(total_trades::text,'-') || ' trades' from quant.backtest_results where strategy_name in (select strategy_name from quant.strategy_configs where id=" + str(int(sid)) + ") order by id desc limit 1") or "无"
        print("%-6s %-26s %-9s %-7s %s" % (sid, s["name"][:26], s.get("status", "?"), act, ev))
    return 0


def cmd_retire(sid, delete=False, reason=""):
    sid = int(sid)
    backup = "/tmp/strategy_retire_%d_%s.json" % (sid, datetime.now().strftime("%Y%m%d-%H%M%S"))
    row = psql("select coalesce(json_agg(t),'[]'::json) from (select * from quant.strategy_configs where id=%d) t" % sid)
    Path(backup).write_text(row, encoding="utf-8")
    psql("update quant.strategy_configs set is_active=false, updated_at=now() where id=%d" % sid)
    print("已停用 %d（备份 %s）" % (sid, backup))
    if delete:
        psql("delete from quant.strategy_configs where id=%d" % sid)
        print("已删除 %d" % sid)
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"strategies": []}
    for s in reg.get("strategies", []):
        if str(s.get("strategy_id")) == str(sid):
            s["status"] = "deleted" if delete else "retired"
            s["retired_at"] = datetime.now().isoformat(timespec="seconds")
            s["reason"] = reason
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    cmd_journal("退役策略 %d（%s）：%s" % (sid, "删除" if delete else "停用", reason))
    return 0


def cmd_journal(text):
    line = "- [" + datetime.now().strftime("%Y-%m-%d %H:%M") + "] " + text + "\n"
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(line)
    print("已追加心得:", JOURNAL.name)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gate", "register", "track", "retire", "journal"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--desc", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    from infrastructure.services.service_registry import register_all_services
    register_all_services()
    if a.cmd == "gate":
        return 0 if cmd_gate(a.arg)["verdict"] else 2
    if a.cmd == "register":
        return cmd_register(a.arg, a.name or Path(a.arg).stem, a.force, a.desc)
    if a.cmd == "track":
        return cmd_track()
    if a.cmd == "retire":
        return cmd_retire(a.arg, a.delete, a.reason)
    if a.cmd == "journal":
        return cmd_journal(a.arg)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
