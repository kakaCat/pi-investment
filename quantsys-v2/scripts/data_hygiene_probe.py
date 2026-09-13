"""数据卫生探针（data_hygiene_probe.py，2026-09-13 w-a9ec14d7）

**要解决的根问题**：删掉聚合（策略/池子）后，派生表与审计表仍指向它，而**没有任何机制会发现** ——
直到某天有人用那张表时才暴露（实测：quant.strategy_stock_matching 800 行 100% 指向已删策略，
自 2026-05-31 起未更新）。"下次删除还会发生"的根因不是那张表，而是**没有声明、没有探测、没有删除契约**。

三层方案（本脚本实现检测层，读取声明层）：
  1) 声明层 config/data_contracts.json：每张表声明 owner / kind(source|derived|audit) / 上游 /
     新鲜度 TTL / 删除策略 / 软引用检查；
  2) 检测层（本脚本）：**悬空引用**（软引用列指向不存在的上游行）+ **过期派生表**（超 TTL 未更新）；
  3) 纪律层：聚合删除优先软删；硬删必须先声明依赖处理（cascade / SET NULL / 先清派生）。

退出码：0=无问题，1=发现问题（供定时任务据此告警，**不静默**）。
用法：python scripts/data_hygiene_probe.py [--json 报告路径]
"""
import argparse, json, os, subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
CONTRACTS = ROOT / "config" / "data_contracts.json"


def psql(sql):
    r = subprocess.run(["psql", "-d", "quant_investment", "-Atc", sql],
                       capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return (r.stdout or "").strip()


def table_exists(name):
    schema, _, table = name.partition(".")
    n = psql("select count(*) from information_schema.tables where table_schema='%s' and table_name='%s'"
             % (schema, table))
    return int(n or 0) > 0


def _severity(spec_item):
    return 'fail' if spec_item.get('severity') == 'fail' else 'warn'


def check_coverage(spec):
    """数据面覆盖率检查（2026-09-13 新增）。

    为什么需要：本日连着三次踩到「数据/能力悄悄变空」——资金流每股只有 11 天、
    事件只覆盖 34 只、探针在表被删后崩溃。**基于残缺数据做决策 = 真金白银的错误**，
    所以覆盖率必须由机器持续盯，而不是等人偶然发现。

    三类检查（契约里按需声明）：
      · freshness_gap_days        —— 最近一次数据距今多少天（采集是否停了）
      · per_date_distinct_symbols —— 最近 N 个「数据日」里每天覆盖多少只（有没有缺日/半日）
      · per_symbol_rows_p50       —— 每股行数中位数（能不能支撑横截面研究）
    severity=warn 的已知缺陷只提示、不置退出码 1（避免每周噪声把告警训废）；
    severity=fail 的一旦不达标即退出码 1。
    """
    name = spec['name']
    issues = []
    for item in spec.get('coverage') or []:
        kind = item.get('check')
        sev = _severity(item)
        thr = item.get('threshold')
        col = item.get('time_column') or spec.get('time_column') or 'trade_date'
        try:
            if kind == 'freshness_gap_days':
                latest = psql("select coalesce(max(%s)::text,'') from %s" % (col, name))
                if not latest:
                    issues.append({'type': 'coverage_no_data', 'severity': sev,
                                   'detail': '%s 没有任何数据（%s 为空）' % (name, col)})
                    continue
                gap = (datetime.now() - datetime.fromisoformat(latest[:19])).days
                if gap > thr:
                    issues.append({'type': 'coverage_stale', 'severity': sev, 'gap_days': gap,
                                   'threshold': thr,
                                   'detail': '最近数据 %s，已滞后 %d 天（阈值 %d）' % (latest[:10], gap, thr)})
            elif kind == 'per_date_distinct_symbols':
                lb = int(item.get('lookback_days') or 10)
                rows = psql("select %s::text || ':' || count(distinct %s) from %s "
                            "group by %s order by %s desc limit %d"
                            % (col, item.get('symbol_column') or 'symbol', name, col, col, lb)).splitlines()
                bad = [(r.split(':')[0], int(r.split(':')[1])) for r in rows if r and int(r.split(':')[1]) < thr]
                if bad:
                    issues.append({'type': 'coverage_thin_days', 'severity': sev,
                                   'days': ['%s(%d)' % (d, n) for d, n in bad][:5],
                                   'threshold': thr,
                                   'detail': '最近 %d 个数据日中有 %d 天覆盖 < %d 只：%s'
                                             % (len(rows), len(bad), thr,
                                                ', '.join('%s=%d' % (d, n) for d, n in bad[:3]))})
            elif kind == 'per_symbol_rows_p50':
                p50 = psql("with per as (select symbol, count(*) n from %s group by symbol) "
                           "select coalesce(percentile_disc(0.5) within group (order by n), 0) from per" % name)
                if p50 and float(p50) < thr:
                    issues.append({'type': 'coverage_thin_per_symbol', 'severity': sev,
                                   'p50_rows': float(p50), 'threshold': thr,
                                   'detail': '每股行数中位数 %.0f < %d（不足以支撑横截面研究）' % (float(p50), thr)})
        except Exception as exc:
            issues.append({'type': 'coverage_check_failed', 'severity': sev,
                           'detail': '%s: %s' % (kind, str(exc)[:120])})
    return issues


def check_table(spec):
    """声明层条目体检。

    2026-09-13（w-a9ec14d7）健壮性修复：原实现直接对声明的表跑查询，
    表被 drop（按契约正常处置）后整个探针**直接崩溃**（RuntimeError 冒到 main），
    每周任务会因此报失败——**比没有探针更糟**。现在：
      · status=dropped 的条目跳过巡检，但校验其 backup_table 是否还在（可回滚性）；
      · 表缺失/改名 → 记为 declared_table_missing（issue，不崩），提示契约与实现脱节。
    """
    name = spec["name"]
    out = {"table": name, "kind": spec.get("kind"), "owner": spec.get("owner"), "issues": []}
    if not table_exists(name):
        if spec.get("status") == "dropped":
            backup = spec.get("backup_table")
            if backup:
                out["backup_ok"] = table_exists(backup)
                if not out["backup_ok"]:
                    out["issues"].append({"type": "backup_missing", "detail": "已 drop 但备份表 %s 不存在（不可回滚）" % backup})
            out["note"] = "已按契约 drop（status=dropped），跳过巡检"
            return out
        out["issues"].append({"type": "declared_table_missing",
                              "detail": "契约声明的表 %s 不存在——契约与实现脱节，请更新 data_contracts.json" % name})
        return out
    for ref in spec.get("ref_checks") or []:
        col = ref["column"]
        target = ref["target"]
        tcol = ref.get("target_column", "id")
        cast = ref.get("cast")
        lhs = col + "::" + cast if cast else col
        rhs = tcol + "::" + cast if cast else tcol
        sql = ("select count(*) from %s where %s is not null and %s not in (select %s from %s)"
               % (name, col, lhs, rhs, target))
        try:
            n = int(psql(sql) or 0)
        except Exception as exc:
            out["issues"].append({"type": "check_failed", "detail": col + ": " + str(exc)[:120]})
            continue
        total = int(psql("select count(*) from " + name) or 0)
        if n > 0:
            out["issues"].append({"type": "dangling_reference", "column": col, "target": target,
                                  "rows": n, "total_rows": total,
                                  "detail": "%d/%d 行的 %s 指向上游不存在的数据" % (n, total, col)})
    ttl = spec.get("ttl_days")
    tcol2 = spec.get("time_column")
    if ttl and tcol2 and spec.get("kind") in ("derived", "audit"):
        latest = psql("select coalesce(max(%s)::text, '') from %s" % (tcol2, name))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(ROOT / "config" / "data_hygiene_report.json"))
    a = ap.parse_args()
    spec = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    results = [check_table(t) for t in spec.get("tables", [])]
    # 覆盖率检查并入结果（warn 只提示，fail 才置退出码 1）
    for spec_item, r in zip(spec.get("tables", []), results):
        for ci in check_coverage(spec_item):
            ci["_severity"] = ci.get("severity", "warn")
            r["issues"].append(ci)
    def _is_fail(i):
        return i.get("severity", "fail") == "fail"   # 未标 severity 的按 fail（保守）
    bad = [r for r in results if any(_is_fail(i) for i in r["issues"])]
    print("=== 数据卫生探针（%s）===" % datetime.now().isoformat(timespec="seconds"))
    n_fail_tbl = sum(1 for r in results if any(i.get("severity", "fail") == "fail" for i in r["issues"]))
    n_warn_tbl = sum(1 for r in results
                     if r["issues"] and not any(i.get("severity", "fail") == "fail" for i in r["issues"]))
    print("声明表 %d 张｜需处置(fail) %d 张｜已知缺陷(warn) %d 张" % (len(results), n_fail_tbl, n_warn_tbl))
    for r in results:
        has_fail = any(i.get("severity", "fail") == "fail" for i in r["issues"])
        flag = "❌" if has_fail else ("⚠️ " if r["issues"] else "✅")
        extra = ("（最近 %s，滞后 %s 天）" % (r.get("latest"), r.get("lag_days"))) if r.get("latest") else ""
        print("  %s %-34s kind=%-8s owner=%-20s%s" % (flag, r["table"], r.get("kind"), r.get("owner"), extra))
        for i in r["issues"]:
            lvl = "需处置" if i.get("severity", "fail") == "fail" else "已知缺陷"
            print("       - [%s|%s] %s" % (i["type"], lvl, i.get("detail")))
    report = {"checked_at": datetime.now().isoformat(timespec="seconds"), "tables": results,
              "tables_with_issues": len(bad)}
    Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("报告 →", a.json)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())