#!/usr/bin/env bash
# 基准序列常驻监控（2026-09-11 立，w-f4aa1f6a；对应遗留项③）
#
# 背景：CSI300(000300) 的日线曾在库中冻结在 2026-08-27（9 个交易日），而业绩归因照常产出
# 了一个"看起来正常"的超额（实证：修正前 +7.67%、修正后 +15.3%）。归因工具已加对齐与滞后闸门，
# 但**其它基准消费方还没有**（实测消费方：risk_metrics 归因、data_quality_report），
# 故这里做一道独立、常驻的巡检：不合格就投一条 open 错误事件，交给采集→处置闭环。
#
# 检查两项（缺一不可）：
#   ① 新鲜度：基准最新交易日必须 >= 最近一个交易日（取 000300 与个股 600519 的 max(trade_date) 比对，
#      600519 作为"交易日基准"参照系，避免依赖外部日历）；
#   ② 身份/量级：收盘价必须落在合理指数区间——库表**没有市场命名空间**
#      （实测 4,655,497 行全为裸码），000300 之外的指数代码与深市股票**同码冲突**
#      （000001 平安银行/000016 *ST康佳A/000905 厦门港务），一旦有人把指数写成股票数据，
#      量级会立刻异常（指数在千点级，股票在元级）。这条能抓住"静默错配"。
set -uo pipefail
PSQL=/opt/homebrew/opt/postgresql@14/bin/psql
DB=quant_investment
BENCH=${BENCH:-000300}
MIN_LEVEL=${MIN_LEVEL:-1000}    # 合理指数下界（元级股票必然低于此）
MAX_LEVEL=${MAX_LEVEL:-20000}   # 合理指数上界

q() { $PSQL -d "$DB" -t -A -c "$1" 2>/dev/null | tr -d ' '; }

BENCH_LAST=$(q "select coalesce(max(trade_date)::text,'') from quant.daily_klines where symbol='$BENCH';")
REF_LAST=$(q "select coalesce(max(trade_date)::text,'') from quant.daily_klines where symbol='600519';")
CLOSE=$(q "select coalesce(close::text,'') from quant.daily_klines where symbol='$BENCH' order by trade_date desc limit 1;")

FAIL=""
[ -z "$BENCH_LAST" ] && FAIL="基准 $BENCH 在库中无任何数据"
[ -z "$REF_LAST" ] && FAIL="${FAIL}参照标的 600519 无数据（无法判定新鲜度）"
if [ -z "$FAIL" ] && [ "$BENCH_LAST" < "$REF_LAST" ]; then
  FAIL="基准滞后：$BENCH 最新=${BENCH_LAST} < 市场最新=${REF_LAST}（归因/相对收益会算出错数）"
fi
if [ -z "$FAIL" ] && [ -n "$CLOSE" ]; then
  OK_LEVEL=$(python3 -c "print(1 if ${MIN_LEVEL} <= ${CLOSE} <= ${MAX_LEVEL} else 0)" 2>/dev/null || echo 1)
  [ "$OK_LEVEL" = "0" ] && FAIL="基准量级异常：$BENCH 最新收盘=${CLOSE}，不在 [${MIN_LEVEL}, ${MAX_LEVEL}] 区间（疑似代码冲突取到了股票数据）"
fi

if [ -z "$FAIL" ]; then
  echo "[benchmark-check] OK: $BENCH 最新=${BENCH_LAST}（市场最新=${REF_LAST}）收盘=${CLOSE}"
  exit 0
fi

echo "[benchmark-check] FAIL: $FAIL" >&2
payload=$(python3 - "$FAIL" "$BENCH" "$BENCH_LAST" "$REF_LAST" "$CLOSE" <<'PY'
import json, sys
fail, bench, blast, rlast, close = sys.argv[1:6]
print(json.dumps({
    'source': 'os', 'level': 'error',
    'msg': '基准序列巡检不合格（归因/相对收益会失真）',
    'detail': json.dumps({'reason': fail, 'benchmark': bench, 'benchmark_last': blast,
                          'market_last': rlast, 'close': close}, ensure_ascii=False),
    'metadata': {'probe': 'benchmark-freshness-check', 'script': 'scripts/benchmark-freshness-check.sh'},
}, ensure_ascii=False))
PY
)
curl -s -X POST http://127.0.0.1:8080/api/v1/scheduler/error-events \
  -H 'Content-Type: application/json' -d "$payload" -o /dev/null -w 'error-event ingest HTTP=%{http_code}\n' || true
exit 1
