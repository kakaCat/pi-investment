"""研究级事件回补（event_backfill.py，2026-09-13 w-a9ec14d7，RFC 015 §4）

为什么需要：事件研究要的是「同一事件日的横截面」，而监控宇宙只有 34 只（持仓∪盯盘）。
实测两条路径：
  · 日期区间全市场：巨潮忽略 pageNum/column，一次只回 30 条（全市场一天 1358 条）→ 不可用；
  · 逐标的 × 月窗口：可靠（实测 8 只 × 2026-08 取回 86 条，无漏无截断）→ 本脚本走这条。

用法：
  python scripts/event_backfill.py --start 2026-07-01 --end 2026-09-11 --universe-limit 200
  python scripts/event_backfill.py --symbols 600519,000001 --start 2026-08-01 --end 2026-08-31
"""
import argparse, json, sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def months(start: str, end: str):
    """按月切片：单股单窗口公告数有界，避免被上游 30 条上限截断。"""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    cur = date(s.year, s.month, 1)
    out = []
    while cur <= e:
        nxt = date(cur.year + (1 if cur.month == 12 else 0), 1 if cur.month == 12 else cur.month + 1, 1)
        out.append((max(cur, s).isoformat(), min(nxt - timedelta(days=1), e).isoformat()))
        cur = nxt
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--universe-limit", type=int, default=800)
    ap.add_argument("--max-symbols", type=int, default=0)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--report", default=str(ROOT / "config" / "event_backfill_report.json"))
    a = ap.parse_args()

    from infrastructure.services.service_registry import register_all_services
    register_all_services()
    from adapters.outbound.datasources.manager import get_data_provider_manager
    from adapters.outbound.repositories.event_repository import get_market_event_repo
    from application.services.event_feed_service import EventFeedService
    svc = EventFeedService(manager=get_data_provider_manager(), repository=get_market_event_repo())

    syms = [s.strip() for s in a.symbols.replace(",", " ").split() if s.strip()]
    plan = months(a.start, a.end)
    print("回补计划：%d 个月窗口，宇宙 %s" % (len(plan), syms or ("research_universe(%d)" % a.universe_limit)))
    total_fetched = total_merged = total_inserted = total_updated = 0
    per_month = []
    for (ms, me) in plan:
        r = svc.ingest_history(ms, me, symbols=syms or None,
                               universe_limit=a.universe_limit, max_symbols=a.max_symbols)
        c = (r or {}).get("counts") or {}
        total_fetched += int(c.get("fetched") or 0)
        total_merged += int(c.get("merged") or 0)
        total_inserted += int(c.get("inserted") or 0)
        total_updated += int(c.get("updated") or 0)
        notes = (r or {}).get("provider_notes") or []
        print("  %s ~ %s | 宇宙 %s | fetched %s | merged %s | 入库 %s/%s | 备注 %s"
              % (ms, me, c.get("universe"), c.get("fetched"), c.get("merged"),
                 c.get("inserted"), c.get("updated"), (notes[:1] or ["-"])[0][:70]))
        per_month.append({"window": ms + "~" + me, "counts": c, "notes": notes,
                          "success": bool((r or {}).get("success"))})

    report = {"start": a.start, "end": a.end, "universe": syms or a.universe_limit,
              "months": len(plan), "fetched": total_fetched, "merged": total_merged,
              "inserted": total_inserted, "updated": total_updated,
              "per_month": per_month}
    Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("合计：fetched %d | merged %d | 新增 %d | 更新 %d"
          % (total_fetched, total_merged, total_inserted, total_updated))
    print("报告 →", a.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())