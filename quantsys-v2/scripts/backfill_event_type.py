"""事件类型回填（2026-09-13 w-a9ec14d7）——把历史 other 按领域层分类器重新归类

为什么需要：实测 300 条 other 标题**100% 无法归类**（原关键词表只覆盖政策/解禁/财报/分红/股东会/监管），
事件类型这一维在数据上等于不存在；补词表后覆盖率 0% → 59%（其余为故意不归类的噪声 + 长尾）。

⚠️ 关键副作用：R1 的 evidence_hash = hash(scope | type | 标的 | effective_date | 归一化标题)，
**含 type** —— 只改 event_type 不重算 hash，会让未来重采同一公告算出不同 hash → 重复入库。
故本脚本两列一起更新（复用 domain 层的 compute_evidence_hash，不自己实现规则）。
"""
import json, subprocess, sys, os
from pathlib import Path

sys.path.insert(0, "/Users/yunpeng/pi-investment/quantsys-v2")
from domain.events.service import compute_evidence_hash, infer_event_type
from domain.events.model import EventType

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
APPLY = "--apply" in sys.argv


def psql(sql, at=True):
    args = ["psql", "-d", "quant_investment", "-Atc" if at else "-c", sql]
    r = subprocess.run(args, capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return (r.stdout or "").strip()


rows = psql("select json_agg(t) from (select id, scope, event_type, symbol, symbols, "
            "event_date, title, evidence_hash, source from quant.event_calendar) t")
data = json.loads(rows or "[]")
print("载入 %d 条事件" % len(data))

changes = []
for r in data:
    if (r.get("event_type") or "") != "other":
        continue
    new_type = str(infer_event_type(r.get("title") or ""))
    if new_type in ("EventType.OTHER", "other"):
        continue
    ty = new_type.split(".")[-1].lower()
    # 标的集合：symbols(jsonb) 优先，回落单值 symbol
    syms = r.get("symbols") or []
    if isinstance(syms, str):
        try:
            syms = json.loads(syms)
        except Exception:
            syms = []
    if not syms and r.get("symbol") and r["scope"] == "individual":
        syms = [r["symbol"]]
    syms = sorted({str(s) for s in syms if s})
    eff = str(r.get("event_date") or "")[:10]
    new_hash = compute_evidence_hash(r.get("scope") or "individual", ty, syms, eff, r.get("title") or "")
    changes.append({"id": r["id"], "old": "other", "new": ty, "old_hash": r.get("evidence_hash"), "new_hash": new_hash})

print("可归类 %d 条" % len(changes))
from collections import Counter
print("新类型分布:", dict(Counter(c["new"] for c in changes)))
print("hash 会变的条数:", sum(1 for c in changes if c["old_hash"] != c["new_hash"]))

rep = Path("/Users/yunpeng/pi-investment/quantsys-v2/config/event_type_backfill_report.json")
rep.write_text(json.dumps({"total": len(data), "reclassified": len(changes),
                           "by_type": dict(Counter(c["new"] for c in changes)),
                           "note": "event_type 与 evidence_hash 同步更新（R1 hash 含 type）"},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("报告 →", rep)

if not APPLY:
    print("（dry-run；加 --apply 写库）")
    raise SystemExit(0)

psql("drop table if exists quant.event_calendar_type_backup_20260913")
psql("create table quant.event_calendar_type_backup_20260913 as "
     "select id, event_type, evidence_hash from quant.event_calendar", at=False)
print("备份 → quant.event_calendar_type_backup_20260913:", psql("select count(*) from quant.event_calendar_type_backup_20260913"))
for c in changes:
    psql("update quant.event_calendar set event_type = '%s', evidence_hash = '%s', updated_at = now() where id = %d"
         % (c["new"], c["new_hash"], c["id"]))
print("已回填 %d 条" % len(changes))
print("回填后类型分布:")
print(psql("select event_type, count(*) from quant.event_calendar group by 1 order by 2 desc"))
