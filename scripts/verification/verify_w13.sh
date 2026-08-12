#!/usr/bin/env bash
# W1.3 混合检索验收脚本（合同式验收：执行模型必须跑到全绿）
# 前置：5001 已用新代码重启；ollama 已 pull bge-m3
# 用法：bash scripts/verification/verify_w13.sh
set -u
API="${QUANTSYS_V2_API_URL:-http://127.0.0.1:5001}"
PASS=0; FAIL=0
check() { # name condition
  if [ "$2" = "0" ]; then echo "✅ $1"; PASS=$((PASS+1)); else echo "❌ $1"; FAIL=$((FAIL+1)); fi
}

echo "== 1. 创建带证据的测试条目（触发 embedding 计算）=="
CREATE=$(curl -s -X POST "$API/api/memory" -H "Content-Type: application/json" -d '{
  "kind":"episode","scope":"global","title":"test_w13_崩盘日买入验证",
  "content":"2026-07-28 创业板崩盘日 -7.35%，v13 调仓买入 5 只抗跌股，随后 V 型反弹全部盈利",
  "evidence":{"trades":["simulation_trades v13"]},
  "status":"active","provenance":{"session_kind":"user","channel":"verify_script"},
  "source":"verify_w13"}')
ID=$(echo "$CREATE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
[ -n "$ID" ] && [ "$ID" != "None" ]; check "创建条目返回 id=$ID" $?

echo "== 2. 语义检索（查询词与条目无字面重叠也能命中）=="
SEARCH=$(curl -s "$API/api/memory/search?q=%E5%B4%A9%E7%9B%98%E6%97%A5%E4%B9%B0%E5%85%A5%E6%8A%97%E8%B7%8C%E8%82%A1&kind=episode")
echo "$SEARCH" | python3 -c "
import json,sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
hit = any('test_w13' in (i.get('title','')) for i in items[:3])
print('HIT' if hit else 'MISS')
" | grep -q HIT; check "语义查询 top3 命中测试条目" $?

echo "== 3. 返回带 score 与命中来源 =="
echo "$SEARCH" | python3 -c "
import json,sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
ok = items and all('score' in i for i in items)
print('OK' if ok else 'NO')
" | grep -q OK; check "结果带 score 字段" $?

echo "== 4. 降级模式（停 ollama 后搜索不 5xx 且标 degraded）=="
echo "   请手动停 ollama 后重跑本段，或确认实现里有 try/except 降级路径"
curl -s -o /dev/null -w "%{http_code}" "$API/api/memory/search?q=test" | grep -q 200; check "搜索端点可用" $?

echo "== 5. 清理 =="
if [ -n "$ID" ] && [ "$ID" != "None" ]; then
  psql -d quant_test -c "DELETE FROM quant.memory_entries WHERE title LIKE 'test_w13%';" > /dev/null 2>&1
  psql -d quant_investment -c "DELETE FROM quant.memory_entries WHERE title LIKE 'test_w13%';" > /dev/null 2>&1
  echo "已清理测试条目"
fi

echo ""
echo "结果: $PASS 通过 / $FAIL 失败"
[ "$FAIL" = "0" ]
