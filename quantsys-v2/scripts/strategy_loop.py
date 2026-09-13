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

# 2026-09-13（w-a9ec14d7）：窗口收敛到**数据完整覆盖**的区间。
# 实证：quant.daily_klines 2021/2022/2023 分别只有 270/291/300 只标的具备 220+ 根日线，
# 而 2024 年 5023 只、2025 年 5353 只 —— 跨 2023/2024 的回测在混合两个不同的 universe，
# 结论会被污染。故只用 2024-07 起（覆盖完整、universe 稳定）的两段，各约一年。
WINDOWS = [("2024-07-01", "2025-06-30"), ("2025-07-01", "2026-09-11")]
# 2026-09-13（w-a9ec14d7）门槛改**超额口径**。
# 旧口径（absolute）的实证问题：同期同池等权基准 CAGR 就有 +23.3%（2024-07~2026-09，800 只），
# 于是 median_cagr>=8% / sharpe>=0.8 这类绝对阈值**会被 beta 跟随轻易通过**——守门人近视，
# 放进来的是 beta 而不是 alpha。现在全部改成"相对同池等权买入持有"的超额。
# 注：worst_dd 保留绝对口径——回撤是风险上限，与基准无关。
GATE = {"median_excess_cagr": 0.03,    # 年化超额中位数 ≥ +3pp（低于此不足以覆盖执行摩擦与精力）
        "worst_excess_cagr": -0.02,    # 任一格不得落后基准 2pp 以上（不允许靠某一格撑场面）
        "worst_dd": -0.20,             # 风险上限（绝对口径）
        "median_excess_sharpe": 0.0,   # 风险调整后也不得劣于基准
        "min_trades": 100}             # 样本充分性


def psql(q):
    return subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                          capture_output=True, text=True, env=ENV, check=True).stdout.strip()


def universes():
    pool = [s for s in psql("select string_agg(symbol, ',') from (select jsonb_array_elements(members)->>'symbol' as symbol from quant.stock_pools where id=35) t").split(",") if s]
    ctrl = [s for s in psql("select string_agg(symbol, ',') from (select symbol from quant.daily_klines where trade_date >= '2023-01-01' group by 1 having count(*) > 600 order by symbol limit 30) t").split(",") if s]
    return {"pool35": pool, "control30": ctrl}


# overlay 门槛（2026-09-13 w-a9ec14d7）：覆盖层的价值是"用一部分收益换风险改善"，
# 用 alpha 门槛判它必然误杀（core 覆盖层超额 CAGR 为负、但 Sharpe +0.24、回撤减半）。
# 故单列一档：夏普改善是硬要求，收益让渡有上限，回撤仍是硬上限。
GATE_OVERLAY = {"min_excess_sharpe": 0.2,    # 相对同池等权的夏普改善 ≥ +0.2
                "min_excess_cagr": -0.06,    # 收益让渡不超过 6pp/年
                "max_dd": -0.20}             # 绝对回撤上限


def cmd_gate_overlay(evidence_path, quiet=False):
    """覆盖层裁决：读组合层证据 JSON（由 strategy_core.py 落盘），按 GATE_OVERLAY 判定。"""
    ev = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    ex = ev.get("excess") or {}
    ov = ev.get("overlay") or {}
    checks = {
        "min_excess_sharpe": ex.get("sharpe") is not None and float(ex["sharpe"]) >= GATE_OVERLAY["min_excess_sharpe"],
        "min_excess_cagr": ex.get("cagr") is not None and float(ex["cagr"]) >= GATE_OVERLAY["min_excess_cagr"],
        "max_dd": ov.get("dd") is not None and float(ov["dd"]) >= GATE_OVERLAY["max_dd"],
    }
    verdict = bool(all(checks.values()))
    if not quiet:
        print("覆盖层证据：%s（%s，%s）" % (ev.get("name"), ev.get("window"), ev.get("universe")))
        print("  基线 CAGR %s / DD %s / Sharpe %s" % (
            ev.get("baseline", {}).get("cagr"), ev.get("baseline", {}).get("dd"), ev.get("baseline", {}).get("sharpe")))
        print("  覆盖 CAGR %s / DD %s / Sharpe %s" % (ov.get("cagr"), ov.get("dd"), ov.get("sharpe")))
        print("  超额 CAGR %s / Sharpe %s / 回撤改善 %s" % (ex.get("cagr"), ex.get("sharpe"), ex.get("dd_improvement")))
        print("--- 覆盖层门槛判定 ---")
        for k, need in GATE_OVERLAY.items():
            actual = ex.get("sharpe") if k == "min_excess_sharpe" else (ex.get("cagr") if k == "min_excess_cagr" else ov.get("dd"))
            print("  %-20s %-5s 实测 %s / 要求 %s" % (k, "PASS" if checks[k] else "FAIL", actual, need))
        print("总判定：%s" % ("通过" if verdict else "未通过"))
    return {"verdict": verdict, "checks": checks, "evidence": ev}


def cmd_register_overlay(evidence_path, name, force=False):
    """把通过覆盖层门槛的组合层策略登记进 registry（source=core_plan，kind=overlay）。"""
    g = cmd_gate_overlay(evidence_path)
    if not g["verdict"] and not force:
        print("未过覆盖层门槛，拒绝注册（确需登记观察项用 --force）")
        return 1
    ev = g["evidence"]
    doc = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"strategies": []}
    entry = {
        "strategy_id": None,
        "name": name or ev.get("name") or "core-overlay",
        "source": "core_plan",
        "kind": "overlay",
        "status": "active",
        "forced": bool(force),
        "registered_at": datetime.now().isoformat(timespec="seconds"),
        "gate": GATE_OVERLAY,
        "gate_evidence": {"baseline": ev.get("baseline"), "overlay": ev.get("overlay"),
                          "excess": ev.get("excess"), "window": ev.get("window"), "universe": ev.get("universe")},
        "plan_file": "quantsys-v2/config/core_plan.json",
        "evidence_file": str(Path(evidence_path)),
        "consume_hint": ("消费端（agent-brain-candidate-hunt）对 source=core_plan 的条目："
                         "读取 plan_file 的 holdings 作为候选，并按 exposure 口径给仓位；"
                         "不要调用 strategy_execute（本条目不产生单标的买卖信号）。"),
    }
    doc["strategies"] = [s for s in doc.get("strategies", []) if s.get("name") != entry["name"]] + [entry]
    REGISTRY.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已注册：%s（source=core_plan, kind=overlay, status=active）→ %s" % (entry["name"], REGISTRY))
    return 0


def load_source(target):
    if target.endswith(".py"):
        return Path(target).read_text(encoding="utf-8"), {}, Path(target).stem
    code, params = lab.fetch_strategy(int(target))
    return code, params, "strategy_" + str(target)


def cmd_gate(target, quiet=False):
    """门槛裁决（超额口径）：每一格（universe × window）都同时算策略与**同池等权买入持有**基准，
    以"超额"作为判据；任一格缺基准证据 → 按未通过处理（不拿无证据冒充达标）。"""
    code, params, label = load_source(target)
    grid, exc, exc_sh, dds = [], [], [], []
    trades = 0
    for uname, syms in universes().items():
        for (s, e) in WINDOWS:
            r = lab.evaluate(code, params, syms, s, e, label)["portfolio"]
            if not r.get("ok"):
                continue
            row = {"universe": uname, "window": s + "~" + e, "cagr": float(r["cagr"]),
                   "bench_cagr": r.get("benchmark_cagr"), "excess_cagr": r.get("excess_cagr"),
                   "max_dd": float(r["max_dd"]), "sharpe": float(r["sharpe"]),
                   "bench_sharpe": r.get("benchmark_sharpe"), "excess_sharpe": r.get("excess_sharpe"),
                   "trades": int(r.get("trades", 0) or 0), "has_benchmark": r.get("excess_cagr") is not None}
            grid.append(row)
            if row["has_benchmark"]:
                exc.append(row["excess_cagr"])
                exc_sh.append(row["excess_sharpe"])
            dds.append(row["max_dd"])
            trades += row["trades"]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0.0
    res = {"median_excess_cagr": float(round(med(exc), 4)) if exc else None,
           "worst_excess_cagr": float(round(min(exc), 4)) if exc else None,
           "worst_dd": float(round(min(dds), 4)) if dds else 0.0,
           "median_excess_sharpe": float(round(med(exc_sh), 2)) if exc_sh else None,
           "trades": int(trades),
           "n_grid": len(grid), "n_with_benchmark": len(exc)}

    def _b(x):
        return bool(x)

    checks = {
        "median_excess_cagr": res["median_excess_cagr"] is not None and res["median_excess_cagr"] >= GATE["median_excess_cagr"],
        "worst_excess_cagr": res["worst_excess_cagr"] is not None and res["worst_excess_cagr"] >= GATE["worst_excess_cagr"],
        "worst_dd": res["worst_dd"] >= GATE["worst_dd"],
        "median_excess_sharpe": res["median_excess_sharpe"] is not None and res["median_excess_sharpe"] >= GATE["median_excess_sharpe"],
        "min_trades": res["trades"] >= GATE["min_trades"],
        "has_benchmark": res["n_with_benchmark"] == res["n_grid"] and res["n_grid"] > 0,
    }
    checks = {k: _b(v) for k, v in checks.items()}
    verdict = bool(all(checks.values()))
    if not quiet:
        print("%-11s %-22s %8s %9s %9s %8s %7s" % ("universe", "window", "CAGR", "基准CAGR", "超额", "最大回撤", "trades"))
        for g in grid:
            print("%-11s %-22s %8s %9s %9s %8s %7s" % (
                g["universe"], g["window"], g["cagr"], g["bench_cagr"],
                g["excess_cagr"] if g["has_benchmark"] else "无基准", g["max_dd"], g["trades"]))
        print("--- 门槛判定（超额口径）---")
        for k in GATE:
            actual = res["trades"] if k == "min_trades" else res[k]
            print("  %-22s %-5s 实测 %s / 要求 %s" % (k, "PASS" if checks[k] else "FAIL", actual, GATE[k]))
        print("  %-22s %-5s 有效格 %s/%s" % ("has_benchmark", "PASS" if checks["has_benchmark"] else "FAIL",
                                          res["n_with_benchmark"], res["n_grid"]))
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
    """列出 registry 条目现状。2026-09-13 修复：原实现假设每条都有 strategy_id（int），
    覆盖层条目（kind=overlay，strategy_id=null）会让 int(None) 抛 TypeError 直接崩掉——
    这正是每周复核任务要跑的第一个命令。现在按 kind 分流展示。"""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"strategies": []}
    if not reg["strategies"]:
        print("registry 为空：尚无通过门槛注册的策略")
        return 0
    print("%-8s %-26s %-9s %-9s %s" % ("id", "name", "status", "kind", "证据/激活"))
    for s in reg["strategies"]:
        sid = s.get("strategy_id")
        kind = s.get("kind") or ("code" if sid is not None else "?")
        status = s.get("status", "?")
        if sid is None:
            # 覆盖层（core_plan）：没有 DB 策略行，展示 plan 文件与门槛证据摘要
            ex = ((s.get("gate_evidence") or {}).get("excess")) or {}
            info = "plan=%s | 超额Sharpe %s / 超额CAGR %s" % (
                s.get("plan_file"), ex.get("sharpe"), ex.get("cagr"))
            print("%-8s %-26s %-9s %-9s %s" % ("-", s["name"][:26], status, kind, info))
            continue
        act = psql("select is_active from quant.strategy_configs where id=" + str(int(sid))) or "-"
        ev = psql("select coalesce(round(total_return::numeric,3)::text,'-') || ' / ' || coalesce(total_trades::text,'-') || ' trades' from quant.backtest_results where strategy_name in (select strategy_name from quant.strategy_configs where id=" + str(int(sid)) + ") order by id desc limit 1") or "无"
        print("%-8s %-26s %-9s %-9s %s" % (sid, s["name"][:26], status, kind, "active=" + str(act) + " | " + ev))
    return 0


def cmd_retire_overlay(name, reason=""):
    """退役覆盖层条目（无 DB 策略行，只动 registry + journal）。

    2026-09-13：cmd_retire 只接受 int strategy_id，覆盖层条目没有 id ——
    若不补这条对称命令，每周复核任务对覆盖层"退役"这一步会直接卡死。
    """
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"strategies": []}
    hit = False
    for s in reg.get("strategies", []):
        if s.get("name") == name and (s.get("kind") == "overlay" or s.get("strategy_id") is None):
            s["status"] = "retired"
            s["retired_at"] = datetime.now().isoformat(timespec="seconds")
            s["reason"] = reason
            hit = True
    if not hit:
        print("未找到覆盖层条目：%s" % name)
        return 1
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已退役覆盖层条目 %s（reason=%s）" % (name, reason))
    cmd_journal("退役覆盖层 %s：%s" % (name, reason))
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
    ap.add_argument("cmd", choices=["gate", "register", "track", "retire", "journal",
                                     "gate-overlay", "register-overlay", "retire-overlay"])
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
    if a.cmd == "gate-overlay":
        return 0 if cmd_gate_overlay(a.arg)["verdict"] else 2
    if a.cmd == "register-overlay":
        return cmd_register_overlay(a.arg, a.name or Path(a.arg).stem, a.force)
    if a.cmd == "retire-overlay":
        return cmd_retire_overlay(a.arg, a.reason)
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
