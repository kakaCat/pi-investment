#!/bin/bash
# 信号回填验证（9/3 首批5日窗口到期后的验证任务）
# 流程：①先触发回填 → ②查询报告 → ③按结果飞书通知
# 用法: signal-perf-verify.sh
set -euo pipefail

QV2="${QUANTSYS_V2_URL:-http://localhost:5001}"
FEISHU_WEBHOOK="${FEISHU_WEBHOOK:-https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829}"

# ① 触发回填（幂等）
curl -sf -X PUT "$QV2/api/signals/track/update" \
  -H 'Content-Type: application/json' -d '{"lookback_days":30}' >/dev/null 2>&1 || true

# ② 查询报告
REPORT=$(curl -sf "$QV2/api/signals/track/report" 2>/dev/null || echo '{}')

# 用 python 解析回填统计
STATS=$(echo "$REPORT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    d = d.get('data') if isinstance(d, dict) else None
    d = d or {}
except Exception:
    d = {}
total = d.get('total', 0)
by_grade = d.get('byGrade') or {}
filled = 0
grade_stats = []
for g, s in by_grade.items():
    if not s:
        continue
    cnt = s.get('count', 0)
    hr = s.get('hitRate5D')
    ar = s.get('avgReturn5D')
    if cnt > 0:
        if hr is not None:
            filled += cnt
            grade_stats.append(f'{g}级{cnt}个 5日胜率{hr*100:.0f}% 均收益{ar*100:+.1f}%')
        else:
            grade_stats.append(f'{g}级{cnt}个 5日待回填')
print(json.dumps({'total': total, 'filled': filled, 'grades': grade_stats}, ensure_ascii=False))
")

TOTAL=$(echo "$STATS" | python3 -c "import json,sys; print(json.load(sys.stdin)['total'])")
FILLED=$(echo "$STATS" | python3 -c "import json,sys; print(json.load(sys.stdin)['filled'])")
GRADES=$(echo "$STATS" | python3 -c "import json,sys; print('；'.join(json.load(sys.stdin)['grades']) or '无')")

# ③ 飞书通知
if [ "$FILLED" -gt 0 ]; then
  TITLE="✅ 信号回填成功：${FILLED}/${TOTAL} 条已回填5日表现"
  URGENCY='normal'
  CONTENT="信号表现回填验证通过（9/3 首批5日窗口）。\n${GRADES}\n—— signal-perf-verify 自动验证"
else
  TITLE="⚠️ 信号回填待观察：5日窗口尚未全部到期"
  URGENCY='low'
  CONTENT="当前 ${TOTAL} 条信号，0 条满5日窗口。若已过 9/4 仍为 0，请人工检查回填链路。\n—— signal-perf-verify 自动验证"
fi

MSG=$(python3 -c "
import json, sys
title, content = sys.argv[1], sys.argv[2]
print(json.dumps({'msg_type':'text','content':{'text': f'{title}\\n{content}'}}, ensure_ascii=False))
" "$TITLE" "$CONTENT")

curl -sf -X POST "$FEISHU_WEBHOOK" -H 'Content-Type: application/json' -d "$MSG" >/dev/null 2>&1 || echo "飞书通知失败（不影响回填验证）" >&2

echo "signal-perf-verify: total=${TOTAL} filled=${FILLED}"
