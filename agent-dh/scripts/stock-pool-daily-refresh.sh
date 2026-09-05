#!/usr/bin/env bash
# ============================================================
# stock-pool-daily-refresh.sh — 股票池每日自主刷新（R-012 daily routine 可执行化）
# 供 Agent OS scheduler（stock-pool-daily-routine 任务）每工作日 19:05 调用。
# 动作：列出全部池 → 对 dynamic 池逐个 refresh（重算换血）+ sync-stock-names。
# 纯后端 API 直连，不依赖 agent 会话，失败有明确退出码供调度器记录。
# 2026-09-05 建立（investor w-8366e526）。本文件归属 agent-dh/scripts。
# ============================================================
set -uo pipefail

BASE="http://127.0.0.1:5001"
TMPD=$(mktemp -d)
FAIL=0
OK=0

# 1. 拉取全量池，挑出 dynamic
curl -s -m 30 "$BASE/api/pools" -o "$TMPD/pools.json"
RC=$?
if [ $RC -ne 0 ]; then
  echo "ERROR: GET /api/pools failed rc=$RC"
  rm -rf "$TMPD"
  exit 1
fi

python3 - "$TMPD/pools.json" "$TMPD/dyn.txt" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
    pools = d.get('data', []) if isinstance(d, dict) else d
    if not isinstance(pools, list):
        pools = []
except Exception as e:
    print(f"PARSE_FAIL: {e}")
    sys.exit(2)
dyn = [p for p in pools if isinstance(p, dict) and p.get('pool_type') == 'dynamic']
with open(sys.argv[2], 'w') as f:
    for p in dyn:
        cnt = p.get('symbol_count')
        if cnt is None:
            cnt = len(p.get('symbols') or [])
        f.write(f"{p.get('id')}\t{p.get('name','')}\t{cnt}\n")
print(f"dynamic_pools={len(dyn)}")
PY
[ $? -ne 0 ] && { cat "$TMPD/dyn.txt" 2>/dev/null; rm -rf "$TMPD"; exit 2; }

# 2. 逐个 refresh + sync names
while IFS=$'\t' read -r id name cnt; do
  [ -z "$id" ] && continue
  r1=$(curl -s -m 120 -X POST "$BASE/api/pools/$id/refresh" -H "Content-Type: application/json")
  r2=$(curl -s -m 60  -X POST "$BASE/api/pools/$id/sync-stock-names" -H "Content-Type: application/json")
  if echo "$r1" | grep -q '"success":true'; then
    # 取刷新后成员数
    after=$(echo "$r1" | python3 -c "import json,sys; d=json.load(sys.stdin); p=d.get('data',{}); print(len(p.get('symbols') or []))" 2>/dev/null)
    echo "OK   pool#$id $name: $cnt -> ${after:-?} members"
    OK=$((OK+1))
  else
    echo "FAIL pool#$id $name refresh: $(echo "$r1" | head -c 200)"
    FAIL=$((FAIL+1))
  fi
done < "$TMPD/dyn.txt"

rm -rf "$TMPD"
echo "summary: ok=$OK fail=$FAIL"
[ $FAIL -eq 0 ]
