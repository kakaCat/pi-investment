#!/usr/bin/env bash
# ============================================================
# stock-pool-weekly-review.sh — 股票池周日盘点（R-012 weekly review 可执行化）
# 供 Agent OS scheduler（stock-pool-weekly-review 任务）每周日 18:00 调用。
# 动作：① 刷新全部 dynamic 池；② 盘点输出：空池/测试命名池/僵尸线索清单
#      （决策性清理/新建需 agent 判断，此处仅产出事实清单供审计与后续 agent 处理）。
# 纯后端 API 直连；输出写入 TaskRun.Output 留存。
# 2026-09-05 建立（investor w-8366e526）。本文件归属 agent-dh/scripts。
# ============================================================
set -uo pipefail

BASE="http://127.0.0.1:5001"
TMPD=$(mktemp -d)
FAIL=0

curl -s -m 30 "$BASE/api/pools" -o "$TMPD/pools.json" || { echo "ERROR: GET /api/pools failed"; rm -rf "$TMPD"; exit 1; }

# 盘点 + 动态刷新清单
python3 - "$TMPD/pools.json" <<'PY'
import json, sys, re
with open(sys.argv[1]) as f:
    d = json.load(f)
pools = d.get('data', []) if isinstance(d, dict) else d
if not isinstance(pools, list):
    pools = []
static = [p for p in pools if p.get('pool_type') == 'static']
dyn    = [p for p in pools if p.get('pool_type') == 'dynamic']
empty  = [p for p in pools if (p.get('symbol_count') or 0) == 0 and not (p.get('symbols'))]
testlike = [p for p in pools if re.search(r'测试|test|tmp|垃圾|僵尸', p.get('name','') or '', re.I)]
print("=== 池盘点 ===")
print(f"总池数: {len(pools)} | static: {len(static)} | dynamic: {len(dyn)}")
if empty:
    print(f"\n[空池/无成员] {len(empty)} 个:")
    for p in empty: print(f"  #{p['id']} {p['name']} (created {p.get('created_at','')[:10]})")
if testlike:
    print(f"\n[测试/临命名线索] {len(testlike)} 个:")
    for p in testlike: print(f"  #{p['id']} {p['name']}")
if dyn:
    print("\n[待刷新 dynamic]")
    for p in dyn:
        cnt = p.get('symbol_count')
        if cnt is None: cnt = len(p.get('symbols') or [])
        print(f"  {p.get('id')}\t{p.get('name')}\t{cnt}")
PY
[ $? -ne 0 ] && { rm -rf "$TMPD"; exit 2; }

# 动态池刷新（复用 daily 逻辑）
grep -P "^\d+\t" "$TMPD/pools.json" >/dev/null 2>&1 || true
python3 - "$TMPD/pools.json" "$TMPD/dyn.txt" <<'PY'
import json, sys
with open(sys.argv[1]) as f: d = json.load(f)
pools = d.get('data', []) if isinstance(d, dict) else d
if not isinstance(pools, list): pools = []
with open(sys.argv[2], 'w') as f:
    for p in pools:
        if p.get('pool_type') == 'dynamic':
            cnt = p.get('symbol_count')
            if cnt is None: cnt = len(p.get('symbols') or [])
            f.write(f"{p.get('id')}\t{p.get('name','')}\t{cnt}\n")
PY
while IFS=$'\t' read -r id name cnt; do
  [ -z "$id" ] && continue
  r1=$(curl -s -m 120 -X POST "$BASE/api/pools/$id/refresh" -H "Content-Type: application/json")
  if echo "$r1" | grep -q '"success":true'; then
    after=$(echo "$r1" | python3 -c "import json,sys; p=json.load(sys.stdin).get('data',{}); print(len(p.get('symbols') or []))" 2>/dev/null)
    echo "REFRESH OK   pool#$id $name: $cnt -> ${after:-?}"
  else
    echo "REFRESH FAIL pool#$id $name"
    FAIL=$((FAIL+1))
  fi
done < "$TMPD/dyn.txt"

rm -rf "$TMPD"
echo "weekly review done, refresh_fail=$FAIL"
[ $FAIL -eq 0 ]
