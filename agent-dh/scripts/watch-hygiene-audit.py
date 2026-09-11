#!/usr/bin/env python3
"""盯盘规则卫生审计（RFC 014 Phase 4 · REQ-f08def）

为什么需要：2026-09-11 体检发现——启用 33 条规则中 20 条（61%）从未触发；多条阈值漂移
达 10~36%（预案写于 14~46 天前）；4 组同标的近重复规则。根因不是"忘了清理"，而是
**之前没有回路**：规则创建后无人回看。本脚本把"回看"变成固定动作。

设计原则（RFC 014 §4.2 非对称护栏）：
  · 本脚本**只审计与报告**，不自动改规则——退役/合并属"减保护"，需人确认
  · 审计本身零 LLM 成本；仅当发现减保护候选时才唤醒 agent（--notify）

用法：watch-hygiene-audit.py [--notify] [--drift 10] [--age 14]
"""
import json, sys, urllib.request, datetime, collections

API = "http://127.0.0.1:5001"
HOOK = "http://127.0.0.1:13080/agent-os-trigger"


def get(path):
    with urllib.request.urlopen(API + path, timeout=20) as r:
        return json.load(r)


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    notify = "--notify" in sys.argv
    drift_th = float(sys.argv[sys.argv.index("--drift") + 1]) if "--drift" in sys.argv else 10.0
    age_th = int(sys.argv[sys.argv.index("--age") + 1]) if "--age" in sys.argv else 14

    rules = [r for r in get("/api/watch/rules")["data"]["rules"] if r["enabled"]]
    trg = get("/api/watch/triggers?limit=200")["data"]["triggers"]
    fired = collections.Counter(t["rule_id"] for t in trg)
    now = datetime.datetime.now()

    syms = sorted({str(r["symbol"]).split(".")[0] for r in rules})
    px = {}
    for s in syms:
        try:
            d = get("/api/stock/" + s + "/quote").get("data") or {}
            px[s] = float(d.get("price") or 0)
        except Exception:
            px[s] = 0

    zombie, drifted, dup = [], [], []
    for r in rules:
        s = str(r["symbol"]).split(".")[0]
        age = None
        try:
            age = (now - datetime.datetime.fromisoformat(r["created_at"])).days
        except Exception:
            pass
        # 僵尸判定要排除「尚未过观察期」的新规则（2026-09-11 修正：原口径把刚建的规则也算僵尸，口径失真）
        if fired.get(r["id"], 0) == 0 and (age is None or age >= age_th):
            zombie.append((r["id"], s, age))
        for c in (r.get("conditions") or []):
            p = (c or {}).get("params") or {}
            if (c or {}).get("type") == "price_break" and p.get("price") and px.get(s):
                dv = (px[s] - float(p["price"])) / float(p["price"]) * 100
                if abs(dv) >= drift_th:
                    drifted.append((r["id"], s, p.get("direction"), p["price"], px[s], round(dv, 1), age, fired.get(r["id"], 0)))
                break
    bysym = collections.defaultdict(list)
    for r in rules:
        bysym[str(r["symbol"]).split(".")[0]].append(r)
    for s, rs in bysym.items():
        if len(rs) < 2:
            continue
        ths = []
        for r in rs:
            for c in (r.get("conditions") or []):
                p = (c or {}).get("params") or {}
                if (c or {}).get("type") == "price_break" and p.get("price"):
                    ths.append((r["id"], p.get("direction"), float(p["price"])))
        for i in range(len(ths)):
            for j in range(i + 1, len(ths)):
                a, b = ths[i], ths[j]
                if a[1] == b[1] and a[2] and abs(a[2] - b[2]) / a[2] < 0.01:
                    dup.append((s, a, b))

    un = [t for t in trg if t["disposition"] in ("pending", "escalated")]
    stale = []
    for t in un:
        s = str(t["symbol"]).split(".")[0]
        p = (t.get("condition") or {}).get("params") or {}
    
        th, d, cur = p.get("price"), p.get("direction"), px.get(s)
        if th and cur:
            still = (cur < th) if d == "below" else (cur > th)
            if not still:
                stale.append(t["id"])

    lines = ["盯盘规则卫生审计 " + now.strftime("%Y-%m-%d %H:%M"),
             "启用规则 %d 条 / 唯一标的 %d" % (len(rules), len(syms)),
             "僵尸（零触发且龄≥%dd）: %d 条" % (age_th, len(zombie)),
             "阈值漂移 ≥%.0f%%: %d 条" % (drift_th, len(drifted)),
             "近重复（同向、阈值差<1%%）: %d 组" % len(dup),
             "待处置触发 %d 条（其中时机已过 %d 条）" % (len(un), len(stale))]
    for d in drifted[:8]:
        lines.append("  漂移 #%s %s %s%s 现价%s 偏离%s%% age=%sd fired=%s" % d)
    for dd in dup[:6]:
        lines.append("  重复 %s: #%s%s%s 与 #%s%s%s" % (dd[0], dd[1][0], dd[1][1], dd[1][2], dd[2][0], dd[2][1], dd[2][2]))
    report = chr(10).join(lines)
    print(report)

    candidates = len(drifted) + len(dup)
    if notify and candidates > 0:
        prompt = ("【盯盘规则周度卫生】发现 %d 项需处理的减保护候选（退役/合并），"
                  "请勿自行执行，留待交互会话用 ask_user_question 向用户提请：" + chr(10) + report) % candidates
        try:
            req = urllib.request.Request(HOOK, data=json.dumps({"prompt": prompt}).encode(),
                                         method="POST", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=20)
            print("[hygiene] 已唤醒 agent 提请用户决策")
        except Exception as e:
            print("[hygiene] 唤醒失败:", e)
    elif candidates == 0:
        print("[hygiene] 无减保护候选，不唤醒 agent（零 LLM）")


if __name__ == "__main__":
    main()