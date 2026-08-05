#!/bin/bash
# 全量测试健康检查（2026-08-05 基线清零后启用）
# 规则：红 = 真回归。输出精简报告，退出码 1 表示有失败。
# 建议加入每日 cron/launchd，例如交易日 08:30：
#   30 8 * * 1-5 /Users/mac/Documents/ai/pi-investment/scripts/run_full_test_check.sh >> /tmp/pi-test-check.log 2>&1
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

echo "===== $(date '+%F %T') 全量测试检查 ====="

# --- agent-ts (jest) ---
echo "--- agent-ts jest ---"
cd "$ROOT/agent-ts"
JEST_OUT=$(npm test 2>&1 | grep -E "^(FAIL|Test Suites:|Tests:)" | sed 's/\x1b\[[0-9;]*m//g' | sort -u)
echo "$JEST_OUT" | grep -E "^(Test Suites:|Tests:)"
JEST_FAIL=$(echo "$JEST_OUT" | grep -c "^FAIL" || true)
if [ "$JEST_FAIL" -gt 0 ]; then
  FAILED=1
  echo "❌ jest 失败套件："
  echo "$JEST_OUT" | grep "^FAIL"
fi

# --- quantsys-v2 (pytest) ---
echo "--- quantsys-v2 pytest ---"
cd "$ROOT/quantsys-v2"
PYTEST_OUT=$("$ROOT/quantsys-v2/venv/bin/python" -m pytest tests/ --no-header -q 2>&1 | tail -5)
echo "$PYTEST_OUT" | grep -E "passed|failed|error" | tail -2
if echo "$PYTEST_OUT" | grep -qE "[1-9][0-9]* (failed|error)"; then
  FAILED=1
  echo "❌ pytest 有失败/错误（详见输出）"
fi

# --- schema 漂移检查 ---
echo "--- quant_test schema 漂移 ---"
cd "$ROOT/quantsys-v2"
if ! "$ROOT/quantsys-v2/venv/bin/python" scripts/check_test_schema_drift.py > /tmp/schema-drift.log 2>&1; then
  FAILED=1
  echo "❌ schema 漂移（前 10 行）："
  head -10 /tmp/schema-drift.log
else
  echo "✅ 无漂移"
fi

if [ "$FAILED" -eq 0 ]; then
  echo "===== ✅ 全绿 ====="
else
  echo "===== ❌ 有失败，需要排查 ====="
fi
exit $FAILED
