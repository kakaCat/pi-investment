"""策略闭环服务（2026-09-13 w-a9ec14d7 从 scripts/strategy_loop.py 上迁）

把"研究 → 评估 → 门槛 → 注册 → 绑定 → 跟踪 → 退役 → 心得"接成可执行的一条链。
评估口径复用 strategy_evaluation_service（T+1、次日开盘成交、含成本、同池等权基准超额）。

为什么上迁：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
本条链由每周任务 strategy-loop-weekly 驱动，属生产能力 → application 层 + 定时任务。

三类产出：
  · 门槛裁决 gate / gate_overlay        —— 判定，不改状态
  · 注册与退役 register_overlay / retire —— 改 registry 与 DB（停用不删除）
  · 周度复核 weekly_review              —— 一次跑完整条链，产报告供 agent 读取与通知
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from application.services import strategy_evaluation_service as ev

logger = logging.getLogger(__name__)

ROOT = ev.ROOT
REGISTRY = ROOT / "config" / "strategy_registry.json"
REPORT = ROOT / "config" / "strategy_loop_report.json"

# --------------------------------------------------------------------------- #
# 门槛（超额口径）
# 2026-09-13（w-a9ec14d7）：门槛改**超额口径**。
# 旧口径（absolute）的实证问题：同期同池等权基准 CAGR 就有 +23.3%（2024-07~2026-09，800 只），
# 于是 median_cagr>=8% / sharpe>=0.8 这类绝对阈值**会被 beta 跟随轻易通过**——守门人近视，
# 放进来的是 beta 而不是 alpha。现在全部改成"相对同池等权买入持有"的超额。
# 注：worst_dd 保留绝对口径——回撤是风险上限，与基准无关。
# ⚠️ 改门槛数值属**规则进化**，须走用户确认；本服务只读这些常量，不自行调整。
# --------------------------------------------------------------------------- #
GATE = {"median_excess_cagr": 0.03,    # 年化超额中位数 ≥ +3pp（低于此不足以覆盖执行摩擦与精力）
        "worst_excess_cagr": -0.02,    # 任一格不得落后基准 2pp 以上（不允许靠某一格撑场面）
        "worst_dd": -0.20,             # 风险上限（绝对口径）
        "median_excess_sharpe": 0.0,   # 风险调整后也不得劣于基准
        "min_trades": 100}             # 样本充分性

# overlay 门槛：覆盖层的价值是"用一部分收益换风险改善"，用 alpha 门槛判它必然误杀
# （core 覆盖层超额 CAGR 为负、但 Sharpe +0.24、回撤减半）。故单列一档：
# 夏普改善是硬要求，收益让渡有上限，回撤仍是硬上限。
GATE_OVERLAY = {"min_excess_sharpe": 0.2,    # 相对同池等权的夏普改善 ≥ +0.2
                "min_excess_cagr": -0.06,    # 收益让渡不超过 6pp/年
                "max_dd": -0.20}             # 绝对回撤上限


def _journal_path(now: Optional[datetime] = None) -> Path:
    """心得日志按月归档（遵守仓库文档放置规范：工作记录写 docs/work-logs/YYYY-MM/）。"""
    now = now or datetime.now()
    return ROOT.parent / "docs" / "work-logs" / now.strftime("%Y-%m") / "strategy-research-journal.md"


def universes() -> dict:
    """门槛要跨 universe 复核：pool35（人工主题池）与 control30（按历史数据量取的无偏对照）。"""
    pool = [r[0] for r in ev.query_rows(
        "select jsonb_array_elements(members)->>'symbol' from quant.stock_pools where id = 35") if r[0]]
    ctrl = [r[0] for r in ev.query_rows(
        "select symbol from quant.daily_klines where trade_date >= '2023-01-01' "
        "group by 1 having count(*) > 600 order by symbol limit 30") if r[0]]
    return {"pool35": pool, "control30": ctrl}


class StrategyLifecycleService:
    """策略门槛/注册/退役/周度复核。

    所有写操作只改 registry 与 strategy_configs.is_active 状态位，不物理删除策略行
    （删除会带走历史回测证据；除非显式传 delete=True）。
    """

    def __init__(self, registry_path: Optional[Path] = None, report_path: Optional[Path] = None):
        self.registry_path = Path(registry_path) if registry_path else REGISTRY
        self.report_path = Path(report_path) if report_path else REPORT

    # ---------------- registry 读写 ---------------- #
    def load_registry(self) -> dict:
        if not self.registry_path.exists():
            return {"strategies": []}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def save_registry(self, doc: dict) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    def journal(self, text: str) -> str:
        """追加一条心得/实验记录。返回写入的文件路径（R-013：留痕要可定位）。"""
        p = _journal_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("- [" + datetime.now().strftime("%Y-%m-%d %H:%M") + "] " + text + "\n")
        return str(p)

    # ---------------- 门槛裁决 ---------------- #
    def gate(self, target) -> dict:
        """门槛裁决（超额口径）：每一格（universe × window）同时算策略与**同池等权买入持有**基准，
        以"超额"为判据；任一格缺基准证据 → 按未通过处理（不拿无证据冒充达标）。"""
        if isinstance(target, str) and target.endswith(".py"):
            code = Path(target).read_text(encoding="utf-8")
            params, label = {}, "file=" + Path(target).stem
        else:
            code, params = ev.fetch_strategy(int(target))
            label = "strategy_" + str(int(target))

        grid, exc, exc_sh, dds, trades = [], [], [], [], 0
        for uname, syms in universes().items():
            for (s, e) in ev.WINDOWS:
                if not syms:
                    continue
                r = ev.evaluate(code, params, syms, s, e, label)["portfolio"]
                if not r.get("ok"):
                    continue
                row = {"universe": uname, "window": s + "~" + e, "cagr": float(r["cagr"]),
                       "bench_cagr": r.get("benchmark_cagr"), "excess_cagr": r.get("excess_cagr"),
                       "max_dd": float(r["max_dd"]), "sharpe": float(r["sharpe"]),
                       "bench_sharpe": r.get("benchmark_sharpe"), "excess_sharpe": r.get("excess_sharpe"),
                       "trades": int(r.get("trades", 0) or 0),
                       "has_benchmark": r.get("excess_cagr") is not None}
                grid.append(row)
                if row["has_benchmark"]:
                    exc.append(row["excess_cagr"])
                    exc_sh.append(row["excess_sharpe"])
                dds.append(row["max_dd"])
                trades += row["trades"]

        def med(xs):
            return sorted(xs)[len(xs) // 2] if xs else 0.0

        res = {"median_excess_cagr": float(round(med(exc), 4)) if exc else None,
               "worst_excess_cagr": float(round(min(exc), 4)) if exc else None,
               "worst_dd": float(round(min(dds), 4)) if dds else 0.0,
               "median_excess_sharpe": float(round(med(exc_sh), 2)) if exc_sh else None,
               "trades": int(trades), "n_grid": len(grid), "n_with_benchmark": len(exc)}
        checks = {
            "median_excess_cagr": res["median_excess_cagr"] is not None
                                 and res["median_excess_cagr"] >= GATE["median_excess_cagr"],
            "worst_excess_cagr": res["worst_excess_cagr"] is not None
                                 and res["worst_excess_cagr"] >= GATE["worst_excess_cagr"],
            "worst_dd": res["worst_dd"] >= GATE["worst_dd"],
            "median_excess_sharpe": res["median_excess_sharpe"] is not None
                                    and res["median_excess_sharpe"] >= GATE["median_excess_sharpe"],
            "min_trades": res["trades"] >= GATE["min_trades"],
            "has_benchmark": res["n_with_benchmark"] == res["n_grid"] and res["n_grid"] > 0,
        }
        checks = {k: bool(v) for k, v in checks.items()}
        return {"label": label, "verdict": bool(all(checks.values())), "checks": checks,
                "gate": dict(GATE), "metrics": res, "grid": grid}

    def gate_overlay(self, evidence_path=None) -> dict:
        """覆盖层裁决：读组合层证据 JSON（由 overlay_evidence 落盘），按 GATE_OVERLAY 判定。"""
        p = Path(evidence_path) if evidence_path else (ROOT / "config" / "core_overlay_evidence.json")
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        ex, ov = doc.get("excess") or {}, doc.get("overlay") or {}
        checks = {
            "min_excess_sharpe": ex.get("sharpe") is not None
                                 and float(ex["sharpe"]) >= GATE_OVERLAY["min_excess_sharpe"],
            "min_excess_cagr": ex.get("cagr") is not None
                               and float(ex["cagr"]) >= GATE_OVERLAY["min_excess_cagr"],
            "max_dd": ov.get("dd") is not None and float(ov["dd"]) >= GATE_OVERLAY["max_dd"],
        }
        checks = {k: bool(v) for k, v in checks.items()}
        return {"verdict": bool(all(checks.values())), "checks": checks,
                "gate": dict(GATE_OVERLAY), "evidence": doc, "evidence_file": str(p)}

    # ---------------- 注册 / 退役 ---------------- #
    def register_overlay(self, evidence_path=None, name: str = "", force: bool = False) -> dict:
        """把通过覆盖层门槛的组合层策略登记进 registry（source=core_plan, kind=overlay）。"""
        g = self.gate_overlay(evidence_path)
        if not g["verdict"] and not force:
            return {"registered": False, "reason": "未过覆盖层门槛，拒绝注册（确需登记观察项用 force）",
                    "checks": g["checks"], "metrics": g["evidence"].get("excess")}
        doc_ev = g["evidence"]
        reg = self.load_registry()
        entry = {
            "strategy_id": None, "name": name or doc_ev.get("name") or "core-overlay",
            "source": "core_plan", "kind": "overlay", "status": "active",
            "forced": bool(force), "registered_at": datetime.now().isoformat(timespec="seconds"),
            "gate": dict(GATE_OVERLAY),
            "gate_evidence": {"baseline": doc_ev.get("baseline"), "overlay": doc_ev.get("overlay"),
                              "excess": doc_ev.get("excess"), "window": doc_ev.get("window"),
                              "universe": doc_ev.get("universe")},
            "plan_file": "quantsys-v2/config/core_plan.json",
            "evidence_file": str(g["evidence_file"]),
            "consume_hint": ("消费端（agent-brain-candidate-hunt）对 source=core_plan 的条目："
                             "读取 plan_file 的 holdings 作为候选，并按 exposure 口径给仓位；"
                             "不要调用 strategy_execute（本条目不产生单标的买卖信号）。"),
        }
        reg["strategies"] = [s for s in reg.get("strategies", [])
                             if s.get("name") != entry["name"]] + [entry]
        self.save_registry(reg)
        self.journal("注册覆盖层 %s（门槛 %s）" % (entry["name"], "通过" if g["verdict"] else "强制登记"))
        return {"registered": True, "entry": entry, "checks": g["checks"]}

    def retire(self, sid: int, delete: bool = False, reason: str = "") -> dict:
        """退役策略行：停用（is_active=false）并同步 registry + journal；delete 才物理删除。

        删除前必须留备份：registry 之外的证据（backtest_results）随行删除不可恢复，
        故返回值里带 backup 快照，调用方负责落盘/留痕。
        """
        sid = int(sid)
        rows = ev.query_rows("select coalesce(json_agg(t),'[]'::json) from "
                             "(select * from quant.strategy_configs where id = :sid) t", {"sid": sid})
        backup = rows[0][0] if rows else []
        from sqlalchemy import text
        with ev._engine().begin() as conn:
            conn.execute(text("update quant.strategy_configs set is_active=false, updated_at=now() "
                              "where id = :sid"), {"sid": sid})
            if delete:
                conn.execute(text("delete from quant.strategy_configs where id = :sid"), {"sid": sid})
        reg = self.load_registry()
        for s in reg.get("strategies", []):
            if str(s.get("strategy_id")) == str(sid):
                s["status"] = "deleted" if delete else "retired"
                s["retired_at"] = datetime.now().isoformat(timespec="seconds")
                s["reason"] = reason
        self.save_registry(reg)
        self.journal("退役策略 %d（%s）：%s" % (sid, "删除" if delete else "停用", reason))
        return {"strategy_id": sid, "deleted": bool(delete), "backup": backup, "reason": reason}

    def retire_overlay(self, name: str, reason: str = "") -> dict:
        """退役覆盖层条目（无 DB 策略行，只动 registry + journal）。

        2026-09-13：retire() 只接受 int strategy_id，覆盖层条目没有 id ——
        若不补这条对称命令，每周复核任务对覆盖层"退役"这一步会直接卡死。
        """
        reg = self.load_registry()
        hit = False
        for s in reg.get("strategies", []):
            if s.get("name") == name and (s.get("kind") == "overlay" or s.get("strategy_id") is None):
                s["status"] = "retired"
                s["retired_at"] = datetime.now().isoformat(timespec="seconds")
                s["reason"] = reason
                hit = True
        if not hit:
            return {"retired": False, "reason": "未找到覆盖层条目：%s" % name}
        self.save_registry(reg)
        self.journal("退役覆盖层 %s：%s" % (name, reason))
        return {"retired": True, "name": name, "reason": reason}

    # ---------------- 跟踪 ---------------- #
    def track(self) -> dict:
        """列出 registry 条目现状。

        2026-09-13 修复：原实现假设每条都有 strategy_id（int），覆盖层条目（kind=overlay,
        strategy_id=null）会让 int(None) 抛 TypeError 直接崩掉——这正是每周复核任务要跑的第一个命令。
        现在按 kind 分流展示。
        """
        reg = self.load_registry()
        out = []
        for s in reg.get("strategies", []):
            sid = s.get("strategy_id")
            kind = s.get("kind") or ("code" if sid is not None else "?")
            item = {"strategy_id": sid, "name": s.get("name"),
                    "status": s.get("status", "?"), "kind": kind}
            if sid is None:
                ex = ((s.get("gate_evidence") or {}).get("excess")) or {}
                item.update({"plan_file": s.get("plan_file"), "excess_sharpe": ex.get("sharpe"),
                             "excess_cagr": ex.get("cagr")})
            else:
                a = ev.query_rows("select is_active from quant.strategy_configs where id = :sid",
                                  {"sid": int(sid)})
                item["is_active"] = bool(a[0][0]) if a else None
                ev_rows = ev.query_rows(
                    "select coalesce(round(total_return::numeric,3)::text,'-'), "
                    "coalesce(total_trades::text,'-') from quant.backtest_results "
                    "where strategy_name in (select strategy_name from quant.strategy_configs "
                    "where id = :sid) order by id desc limit 1", {"sid": int(sid)})
                item["last_backtest"] = ((ev_rows[0][0] + " / " + str(ev_rows[0][1]) + " trades")
                                         if ev_rows else "无")
            out.append(item)
        return {"count": len(out), "empty": len(out) == 0, "items": out}

    # ---------------- 周度复核 ---------------- #
    def weekly_review(self) -> dict:
        """一次跑完整条链：登记现状 → 逐条复核 → 未过门槛则退役 → 落报告 + journal。

        门槛是**超额口径**（相对同池等权买入持有），不是绝对收益。
        纪律：不改门槛数值；不为了"有东西可跑"而降低门槛注册；
             registry 为空是合法状态——没有证据支持时宁可不注册（宪法第 6 条零交易合法的同构原则）。
        """
        started = datetime.now()
        track = self.track()
        reg = self.load_registry()
        actions, checks_out = [], []
        for s in reg.get("strategies", []):
            if s.get("status") != "active":
                continue
            sid = s.get("strategy_id")
            kind = s.get("kind") or ("code" if sid is not None else "overlay")
            if kind == "overlay" or sid is None:
                # 覆盖层也要重新生成证据再判（证据有时间戳，不能拿旧证据充当当期结论）
                try:
                    ev.overlay_evidence()
                    g = self.gate_overlay()
                except Exception as exc:  # noqa: BLE001
                    checks_out.append({"name": s.get("name"), "kind": "overlay",
                                       "error": "%s: %s" % (type(exc).__name__, exc)})
                    continue
                checks_out.append({"name": s.get("name"), "kind": "overlay", "verdict": g["verdict"],
                                   "checks": g["checks"], "metrics": g["evidence"].get("excess")})
                if not g["verdict"]:
                    failed = [k for k, v in g["checks"].items() if not v]
                    r = self.retire_overlay(s.get("name"),
                                            reason="周度复核未过覆盖层门槛：" + ",".join(failed))
                    if r.get("retired"):
                        actions.append({"action": "retire_overlay", "name": s.get("name"),
                                        "failed": failed})
            else:
                try:
                    g = self.gate(sid)
                except Exception as exc:  # noqa: BLE001
                    checks_out.append({"strategy_id": sid, "kind": "code",
                                       "error": "%s: %s" % (type(exc).__name__, exc)})
                    continue
                checks_out.append({"strategy_id": sid, "name": s.get("name"), "kind": "code",
                                   "verdict": g["verdict"], "checks": g["checks"],
                                   "metrics": g["metrics"]})
                if not g["verdict"]:
                    failed = [k for k, v in g["checks"].items() if not v]
                    self.retire(sid, delete=False, reason="周度复核未过门槛：" + ",".join(failed))
                    actions.append({"action": "retire", "strategy_id": sid, "failed": failed})

        conclusion = ("registry 为空：尚无通过门槛注册的策略（合法状态）" if track["empty"]
                      else "复核 %d 条 active，动作 %d 个" % (len(checks_out), len(actions)))
        journal_file = self.journal("周度复核：" + conclusion)
        report = {"generated_at": started.isoformat(timespec="seconds"),
                  "elapsed_sec": round((datetime.now() - started).total_seconds(), 1),
                  "registry_count": track["count"], "registry_empty": track["empty"],
                  "track": track["items"], "checks": checks_out, "actions": actions,
                  "gate": dict(GATE), "gate_overlay": dict(GATE_OVERLAY),
                  "conclusion": conclusion, "journal_file": journal_file}
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        report["report_file"] = str(self.report_path)
        return report


def weekly_review() -> dict:
    """模块级入口：供 job 与测试调用。"""
    return StrategyLifecycleService().weekly_review()


class StrategyLoopWeeklyJob:
    """策略闭环周度复核任务（周日 20:30，2026-09-13 w-a9ec14d7）

    为什么是 job 而不是脚本：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
    本能力原先由 scripts/strategy_loop.py 承担、由每周 agent 任务用 bash 调脚本 —— 属生产能力，
    上迁为 application 层服务 + 定时任务后，agent 任务只需**读取**报告并按需通知。
    """

    def __init__(self):
        self._name = "strategy_loop_weekly"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "策略闭环周度复核：门槛裁决 → 未过则退役 → 落报告与心得（超额口径，不改门槛）"

    @property
    def timeout_seconds(self) -> int:
        return 1800

    async def execute(self, params=None):
        import asyncio
        from application.jobs.job_protocol import JobResult, result_from_dict
        try:
            rep = await asyncio.to_thread(weekly_review)
        except Exception as exc:  # noqa: BLE001 —— 失败必须显式（调度器据此标红）
            logger.exception("strategy_loop_weekly failed")
            return JobResult.fail(self._name, "%s: %s" % (type(exc).__name__, exc))
        return result_from_dict(
            self._name,
            "strategy_loop weekly: registry=%d actions=%d"
            % (rep.get("registry_count", 0), len(rep.get("actions") or [])),
            {"registry_count": rep.get("registry_count"), "registry_empty": rep.get("registry_empty"),
             "actions": rep.get("actions"), "report_file": rep.get("report_file"),
             "conclusion": rep.get("conclusion")})


def build_strategy_loop_jobs():
    """构造策略闭环任务（组合根在 main.py 注册进 JobRegistry）"""
    return [StrategyLoopWeeklyJob()]
