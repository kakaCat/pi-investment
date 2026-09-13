"""数据卫生探针服务（2026-09-13 w-a9ec14d7 从 scripts/data_hygiene_probe.py 上迁）

**要解决的根问题**：删掉聚合（策略/池子）后，派生表与审计表仍指向它，而**没有任何机制会发现** ——
直到某天有人用那张表时才暴露（实测：quant.strategy_stock_matching 800 行 100% 指向已删策略，
自 2026-05-31 起未更新）。"下次删除还会发生"的根因不是那张表，而是**没有声明、没有探测、没有删除契约**。

三层方案：
  1) 声明层 config/data_contracts.json：每张表声明 owner / kind(source|derived|audit) / 上游 /
     新鲜度 TTL / 删除策略 / 软引用检查；
  2) 检测层（本服务）：**悬空引用**（软引用列指向不存在的上游行）+ **过期派生表**（超 TTL 未更新）
     + **覆盖率**（数据悄悄变空是决策错误的直接来源）；
  3) 纪律层：聚合删除优先软删；硬删必须先声明依赖处理（cascade / SET NULL / 先清派生）。

为什么上迁为服务而不是留脚本：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
本能力由每周任务 data-hygiene-weekly 消费，属生产能力 → application 层 + 定时任务，
agent 任务只读报告并按契约处置。

告警分级（关键设计）：severity=fail 才置 failed（需处置）；severity=warn 只提示不置失败 ——
已知缺陷若每周都报 fail，告警会被训废（"狼来了"）。未标 severity 的按 fail（保守）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "config" / "data_contracts.json"
REPORT = ROOT / "config" / "data_hygiene_report.json"


def _engine():
    from infrastructure.persistence.database.engine import get_engine
    return get_engine()


def query_scalar(sql: str, params: Optional[dict] = None):
    with _engine().connect() as conn:
        row = conn.execute(text(sql), params or {}).fetchone()
    return row[0] if row else None


def query_rows(sql: str, params: Optional[dict] = None) -> list:
    with _engine().connect() as conn:
        return list(conn.execute(text(sql), params or {}).fetchall())


# 标识符白名单校验：表名/列名来自 config/data_contracts.json（受控配置，非用户输入），
# 但仍做严格校验 —— 这些名字会被拼进 SQL（SQL 不支持绑定标识符），
# 一旦契约文件被写坏（或将来接入外部来源），就是注入面。宁可在这里拦住。
_SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")


def _ident(name: str) -> str:
    s = str(name)
    if not s or any(c not in _SAFE_CHARS for c in s):
        raise ValueError("非法标识符（表名/列名只允许字母数字下划线点）：%r" % name)
    return s


class DataHygieneService:
    """按 data_contracts.json 巡检：悬空引用 / 过期派生表 / 覆盖率 / 可回滚性。"""

    def __init__(self, contracts_path: Optional[Path] = None, report_path: Optional[Path] = None):
        self.contracts_path = Path(contracts_path) if contracts_path else CONTRACTS
        self.report_path = Path(report_path) if report_path else REPORT

    # ---------------- 基础 ---------------- #
    def table_exists(self, name: str) -> bool:
        schema, _, table = _ident(name).partition(".")
        n = query_scalar("select count(*) from information_schema.tables "
                         "where table_schema = :s and table_name = :t", {"s": schema, "t": table})
        return int(n or 0) > 0

    # ---------------- 覆盖率 ---------------- #
    @staticmethod
    def _severity(spec_item: dict) -> str:
        return "fail" if spec_item.get("severity") == "fail" else "warn"

    def check_coverage(self, spec: dict) -> list:
        """数据面覆盖率检查。

        为什么需要：本日连着三次踩到「数据/能力悄悄变空」——资金流每股只有 11 天、
        事件只覆盖 34 只、探针在表被删后崩溃。**基于残缺数据做决策 = 真金白银的错误**，
        所以覆盖率必须由机器持续盯，而不是等人偶然发现。

        三类检查（契约里按需声明）：
          · freshness_gap_days        —— 最近一次数据距今多少天（采集是否停了）
          · per_date_distinct_symbols —— 最近 N 个「数据日」里每天覆盖多少只（有没有缺日/半日）
          · per_symbol_rows_p50       —— 每股行数中位数（能不能支撑横截面研究）
        severity=warn 的已知缺陷只提示、不置 failed（避免每周噪声把告警训废）；
        severity=fail 的一旦不达标即置 failed。
        """
        name = _ident(spec["name"])
        issues = []
        for item in spec.get("coverage") or []:
            kind = item.get("check")
            sev = self._severity(item)
            thr = item.get("threshold")
            col = _ident(item.get("time_column") or spec.get("time_column") or "trade_date")
            try:
                if kind == "freshness_gap_days":
                    latest = query_scalar("select coalesce(max(%s)::text,'') from %s" % (col, name))
                    if not latest:
                        issues.append({"type": "coverage_no_data", "severity": sev,
                                       "detail": "%s 没有任何数据（%s 为空）" % (name, col)})
                        continue
                    gap = (datetime.now() - datetime.fromisoformat(latest[:19])).days
                    if gap > thr:
                        issues.append({"type": "coverage_stale", "severity": sev, "gap_days": gap,
                                       "threshold": thr,
                                       "detail": "最近数据 %s，已滞后 %d 天（阈值 %d）"
                                                 % (latest[:10], gap, thr)})
                elif kind == "per_date_distinct_symbols":
                    lb = int(item.get("lookback_days") or 10)
                    scol = _ident(item.get("symbol_column") or "symbol")
                    rows = query_rows(
                        "select %s::text, count(distinct %s) from %s group by %s order by %s desc limit %d"
                        % (col, scol, name, col, col, lb))
                    bad = [(r[0], int(r[1])) for r in rows if r and int(r[1]) < thr]
                    if bad:
                        issues.append({"type": "coverage_thin_days", "severity": sev,
                                       "days": ["%s(%d)" % (d, n) for d, n in bad][:5],
                                       "threshold": thr,
                                       "detail": "最近 %d 个数据日中有 %d 天覆盖 < %d 只：%s"
                                                 % (len(rows), len(bad), thr,
                                                    ", ".join("%s=%d" % (d, n) for d, n in bad[:3]))})
                elif kind == "per_symbol_rows_p50":
                    p50 = query_scalar(
                        "with per as (select symbol, count(*) n from %s group by symbol) "
                        "select coalesce(percentile_disc(0.5) within group (order by n), 0) from per" % name)
                    if p50 and float(p50) < thr:
                        issues.append({"type": "coverage_thin_per_symbol", "severity": sev,
                                       "p50_rows": float(p50), "threshold": thr,
                                       "detail": "每股行数中位数 %.0f < %d（不足以支撑横截面研究）"
                                                 % (float(p50), thr)})
            except Exception as exc:  # noqa: BLE001 —— 单项检查失败不拖垮整体巡检
                issues.append({"type": "coverage_check_failed", "severity": sev,
                               "detail": "%s: %s" % (kind, str(exc)[:120])})
        return issues

    # ---------------- 单表体检 ---------------- #
    def check_table(self, spec: dict) -> dict:
        """声明层条目体检。

        2026-09-13 健壮性修复：原实现直接对声明的表跑查询，表被 drop（按契约正常处置）后
        整个探针**直接崩溃**，每周任务会因此报失败——**比没有探针更糟**。现在：
          · status=dropped 的条目跳过巡检，但校验其 backup_table 是否还在（可回滚性）；
          · 表缺失/改名 → 记为 declared_table_missing（issue，不崩），提示契约与实现脱节。
        """
        raw_name = spec["name"]
        out = {"table": raw_name, "kind": spec.get("kind"), "owner": spec.get("owner"), "issues": []}
        try:
            name = _ident(raw_name)
        except ValueError as exc:
            out["issues"].append({"type": "invalid_identifier", "severity": "fail", "detail": str(exc)})
            return out

        if not self.table_exists(name):
            if spec.get("status") == "dropped":
                backup = spec.get("backup_table")
                if backup:
                    out["backup_ok"] = self.table_exists(backup)
                    if not out["backup_ok"]:
                        out["issues"].append({"type": "backup_missing",
                                              "detail": "已 drop 但备份表 %s 不存在（不可回滚）" % backup})
                out["note"] = "已按契约 drop（status=dropped），跳过巡检"
                return out
            out["issues"].append({"type": "declared_table_missing",
                                  "detail": "契约声明的表 %s 不存在——契约与实现脱节，请更新 data_contracts.json"
                                            % name})
            return out

        for ref in spec.get("ref_checks") or []:
            col = _ident(ref["column"])
            target = _ident(ref["target"])
            tcol = _ident(ref.get("target_column", "id"))
            cast = ref.get("cast")
            lhs = col + "::" + _ident(cast) if cast else col
            rhs = tcol + "::" + _ident(cast) if cast else tcol
            sql = ("select count(*) from %s where %s is not null and %s not in (select %s from %s)"
                   % (name, col, lhs, rhs, target))
            try:
                n = int(query_scalar(sql) or 0)
            except Exception as exc:  # noqa: BLE001
                out["issues"].append({"type": "check_failed", "detail": col + ": " + str(exc)[:120]})
                continue
            total = int(query_scalar("select count(*) from " + name) or 0)
            if n > 0:
                out["issues"].append({"type": "dangling_reference", "column": col, "target": target,
                                      "rows": n, "total_rows": total,
                                      "detail": "%d/%d 行的 %s 指向上游不存在的数据" % (n, total, col)})

        ttl = spec.get("ttl_days")
        tcol2 = spec.get("time_column")
        if ttl and tcol2 and spec.get("kind") in ("derived", "audit"):
            tcol2 = _ident(tcol2)
            latest = query_scalar("select coalesce(max(%s)::text, '') from %s" % (tcol2, name))
            out["latest"] = latest or None
            if latest:
                try:
                    lag = (datetime.now() - datetime.fromisoformat(latest)).days
                    out["lag_days"] = lag
                    if lag > ttl:
                        out["issues"].append({"type": "stale_derived_table", "column": tcol2,
                                              "lag_days": lag, "ttl_days": ttl,
                                              "detail": "派生表 %d 天未更新（TTL %d 天）" % (lag, ttl)})
                except ValueError:
                    pass
        return out

    # ---------------- 全量巡检 ---------------- #
    def probe(self) -> dict:
        """跑全部声明表 → 落报告。返回报告 dict。

        report["failed"] 为 True 等价于旧脚本的退出码 1（有需处置项）。
        注意 failed=True 不等于 job 失败 —— 见 DataHygieneProbeJob.execute 的说明。
        """
        spec = json.loads(self.contracts_path.read_text(encoding="utf-8"))
        tables = spec.get("tables", [])
        results = [self.check_table(t) for t in tables]
        # 覆盖率检查并入结果（warn 只提示，fail 才置 failed）
        for spec_item, r in zip(tables, results):
            for ci in self.check_coverage(spec_item):
                ci["_severity"] = ci.get("severity", "warn")
                r["issues"].append(ci)

        def _is_fail(i):
            return i.get("severity", "fail") == "fail"   # 未标 severity 的按 fail（保守）

        fail_tables = [r for r in results if any(_is_fail(i) for i in r["issues"])]
        n_warn_tbl = sum(1 for r in results
                         if r["issues"] and not any(_is_fail(i) for i in r["issues"]))
        report = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "tables": results,
            "tables_total": len(results),
            "tables_with_issues": len(fail_tables),
            "tables_failed": len(fail_tables),
            "tables_warned": n_warn_tbl,
            "failed": bool(fail_tables),
            "coverage_note": "severity=fail 才置 failed（需处置）；warn 只提示（避免已知缺陷把告警训废）",
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        report["report_file"] = str(self.report_path)
        return report

    def summary_lines(self, report: dict) -> list:
        """人类可读摘要（供 job 结果与 agent 报告复用，避免两处格式分叉）。"""
        lines = ["=== 数据卫生探针（%s）===" % report.get("checked_at"),
                 "声明表 %d 张｜需处置(fail) %d 张｜已知缺陷(warn) %d 张"
                 % (report.get("tables_total", 0), report.get("tables_failed", 0),
                    report.get("tables_warned", 0))]
        for r in report.get("tables", []):
            has_fail = any(i.get("severity", "fail") == "fail" for i in r["issues"])
            flag = "FAIL" if has_fail else ("WARN" if r["issues"] else "OK")
            extra = ("（最近 %s，滞后 %s 天）" % (r.get("latest"), r.get("lag_days"))) if r.get("latest") else ""
            lines.append("  [%s] %-34s kind=%-8s owner=%-20s%s"
                         % (flag, r["table"], r.get("kind"), r.get("owner"), extra))
            for i in r["issues"]:
                lvl = "需处置" if i.get("severity", "fail") == "fail" else "已知缺陷"
                lines.append("       - [%s|%s] %s" % (i["type"], lvl, i.get("detail")))
        return lines


def probe() -> dict:
    """模块级入口：供 job 与测试调用。"""
    return DataHygieneService().probe()


class DataHygieneProbeJob:
    """数据卫生巡检任务（每周日 21:00）

    为什么是 job 而不是脚本：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
    本能力原先由 scripts/data_hygiene_probe.py 承担、由每周 agent 任务用 bash 调脚本（靠退出码判断）——
    上迁后 agent 任务只读报告里的 failed 字段与明细，不再需要"退出码"这个 shell 约定。
    """

    def __init__(self):
        self._name = "data_hygiene_probe"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "数据卫生巡检：悬空引用 / 过期派生表 / 覆盖率，按 data_contracts.json 声明逐表体检"

    @property
    def timeout_seconds(self) -> int:
        return 600

    async def execute(self, params=None):
        import asyncio
        from application.jobs.job_protocol import JobResult, result_from_dict
        try:
            rep = await asyncio.to_thread(probe)
        except Exception as exc:  # noqa: BLE001 —— 失败必须显式（调度器据此标红）
            logger.exception("data_hygiene_probe failed")
            return JobResult.fail(self._name, "%s: %s" % (type(exc).__name__, exc))
        # 注意：有 fail 不等于任务失败 —— 任务"成功地产出了需要处置的结论"。
        # 置 JobResult.fail 会让调度器把它记为执行失败，掩盖"探针本身崩了"这一种真失败。
        # 需要处置的信息通过 details.failed / report_file 透出，由 agent 任务据此处置并告警。
        return result_from_dict(
            self._name,
            "data hygiene: tables=%d need_action=%d known_issues=%d"
            % (rep.get("tables_total", 0), rep.get("tables_failed", 0), rep.get("tables_warned", 0)),
            {"failed": bool(rep.get("failed")), "tables_total": rep.get("tables_total"),
             "tables_failed": rep.get("tables_failed"), "tables_warned": rep.get("tables_warned"),
             "report_file": rep.get("report_file")})


def build_data_hygiene_jobs():
    """构造数据卫生任务（组合根在 main.py 注册进 JobRegistry）"""
    return [DataHygieneProbeJob()]
