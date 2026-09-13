#!/usr/bin/env bash
# 模型新鲜度常驻巡检（REQ-a458a6 t3，2026-09-14 w-4db568de）
#
# 背景：模型训练原先依赖系统 crontab（周一 03:00 / 每月 1 号 03:00），它不进
#       quant.scheduler_runs、无告警、日志只落 /tmp（系统会清理）——实测因此有过
#       2026-08-20 → 09-05 停训 16 天无人发现；而 in-app 的巡检与它要监测的调度
#       同生共死（调度宿主整体失效时一起哑掉）。本脚本由 launchd 驱动，是那种情况下
#       唯一还能说话的一条线。
# 检查：最新 lightgbm 模型的年龄（> MAX_AGE_DAYS 天）与 test_accuracy（< MIN_ACC）。
#       不合格 → 投一条 open 错误事件（与 benchmark-freshness-check.sh 同通道），
#       交给采集→处置闭环。
# 注：数值比较一律交给 python3，避免 shell 比较陷阱——benchmark-freshness-check.sh
#     的 [ "$a" < "$b" ] 被当成输入重定向（stderr 有 "No such file or directory"），
#     导致基准滞后也报 OK。这里不复制那个坑。
set -uo pipefail
PSQL=/opt/homebrew/opt/postgresql@14/bin/psql
DB=quant_investment
MAX_AGE_DAYS=${MAX_AGE_DAYS:-10}
MIN_ACC=${MIN_ACC:-0.55}

q() { $PSQL -d "$DB" -t -A -c "$1" 2>/dev/null | tr -d '\r\n'; }

ROW=$(q "select version || '|' || coalesce(train_date::text,'') || '|' || coalesce((extract(epoch from (now()-train_date))/86400)::numeric(10,2)::text,'') || '|' || coalesce(test_accuracy::text,'') from quant.ml_models where model_type='lightgbm' order by train_date desc nulls last limit 1;")

VERSION=""; TRAIN_DATE=""; AGE_DAYS=""; ACC=""
if [ -z "$ROW" ]; then
  FAIL="quant.ml_models 无 lightgbm 记录（训练从未落库？）"
else
  IFS='|' read -r VERSION TRAIN_DATE AGE_DAYS ACC <<< "$ROW"
  FAIL=$(python3 - "$AGE_DAYS" "$ACC" "$MAX_AGE_DAYS" "$MIN_ACC" <<'PY'
import sys
age, acc, max_age, min_acc = sys.argv[1:5]
fails = []
try:
    if age == '' or float(age) > float(max_age):
        fails.append('模型年龄 %s 天 > %s 天（重训链路未生效？）' % (age or '未知', max_age))
except ValueError:
    fails.append('模型年龄无法解析：%r' % age)
try:
    if acc != '' and float(acc) < float(min_acc):
        fails.append('test_accuracy %s < %s' % (acc, min_acc))
except ValueError:
    fails.append('test_accuracy 无法解析：%r' % acc)
print('；'.join(fails))
PY
)
fi

if [ -z "$FAIL" ]; then
  echo "[model-check] OK: lightgbm 最新=$VERSION 训练于=$TRAIN_DATE（$AGE_DAYS 天）acc=$ACC"
  exit 0
fi

echo "[model-check] FAIL: $FAIL" >&2
payload=$(python3 - "$FAIL" "$VERSION" "$TRAIN_DATE" "$AGE_DAYS" "$ACC" "$MAX_AGE_DAYS" <<'PY'
import json, sys
fail, version, train_date, age, acc, max_age = sys.argv[1:7]
print(json.dumps({
    'source': 'os', 'level': 'error',
    'msg': '模型新鲜度巡检不合格（预测所用模型可能已陈旧）',
    'detail': json.dumps({'reason': fail, 'model_type': 'lightgbm', 'version': version,
                          'train_date': train_date, 'age_days': age, 'max_age_days': max_age,
                          'test_accuracy': acc}, ensure_ascii=False),
    'metadata': {'probe': 'model-freshness-check', 'script': 'scripts/model-freshness-check.sh'},
}, ensure_ascii=False))
PY
)
curl -s -X POST http://127.0.0.1:8080/api/v1/scheduler/error-events \
  -H 'Content-Type: application/json' -d "$payload" -o /dev/null -w 'error-event ingest HTTP=%{http_code}\n' || true
exit 1
