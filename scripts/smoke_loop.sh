#!/usr/bin/env bash
# 盈利闭环端到端冒烟（2026-07-24）
#
# 前提：loop_supervisor 已拉起全部进程（python3 scripts/loop_supervisor.py start）
# 注意：第 5 步会真实触发 signals_ready 推送，agent 会真实决策并下模拟单
#       （agent_virtual 账户），请在你准备好接受模拟交易时运行。
set -uo pipefail

PASS=0; FAIL=0
check() {  # check <描述> <命令...>
  local desc="$1"; shift
  if "$@" > /dev/null 2>&1; then
    echo "✅ $desc"; PASS=$((PASS+1))
  else
    echo "❌ $desc"; FAIL=$((FAIL+1))
  fi
}

echo "━━━━ 1. 进程健康 ━━━━"
check "v2 API :5001 健康"        curl -sf http://127.0.0.1:5001/api/health
check "agent wake :3002 健康"    curl -sf http://127.0.0.1:3002/wake/health
check "agent 主进程存活"          pgrep -f "tsx src/index.ts"
check "scheduler_daemon 存活"     pgrep -f "scheduler_daemon.py"

echo "━━━━ 2. 账户状态 ━━━━"
ACCOUNTS=$(curl -s http://127.0.0.1:5001/api/simulation/accounts)
if echo "$ACCOUNTS" | grep -q "agent_virtual"; then
  echo "✅ agent_virtual 存在"; PASS=$((PASS+1))
else
  echo "❌ agent_virtual 不存在"; FAIL=$((FAIL+1))
fi
if echo "$ACCOUNTS" | grep -q "rotation_main"; then
  echo "❌ rotation_main 仍在 active 列表（应已冻结）"; FAIL=$((FAIL+1))
else
  echo "✅ rotation_main 已冻结（不在 active 列表）"; PASS=$((PASS+1))
fi

echo "━━━━ 3. 调度任务 ━━━━"
# 注意：列表接口默认分页 12 条，必须显式 pageSize=100
TASKS=$(curl -s "http://127.0.0.1:5001/api/scheduler/tasks?pageSize=100")
for t in daily-pool-refresh daily-signal-push-fallback; do
  if echo "$TASKS" | grep -q "$t"; then
    echo "✅ 调度任务已注册: $t"; PASS=$((PASS+1))
  else
    echo "❌ 调度任务缺失: ${t}（运行 scripts/init_scheduler_tasks.py）"; FAIL=$((FAIL+1))
  fi
done

echo "━━━━ 4. orchestrator 状态（信息项，不计分）━━━━"
# Flask 5001 无 orchestrator HTTP 端点（仅 FastAPI 有），直接读 DB 状态表
(cd quantsys-v2 && PYTHONPATH=. venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from application.services.daily_orchestrator import get_daily_orchestrator
import json
print(json.dumps(get_daily_orchestrator().get_status(), ensure_ascii=False, default=str)[:300])
" 2>/dev/null || echo "（今日尚无 orchestrator 状态——daemon 未到首个阶段窗口，属正常）")

echo "━━━━ 5. 手动触发 signals_ready（真实推送，agent 将决策）━━━━"
echo "即将触发 MARKET_OPEN 阶段，agent 会对今日信号做真实模拟交易决策。"
read -r -p "确认继续？[y/N] " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
  (cd quantsys-v2 && PYTHONPATH=. venv/bin/python -c "
from application.services.daily_orchestrator import get_daily_orchestrator
print(get_daily_orchestrator().run_phase('MARKET_OPEN'))
")
  echo "→ 已触发。观察 agent 输出和 agent_virtual 账户变化："
  echo "  curl -s http://127.0.0.1:5001/api/simulation/accounts/agent_virtual | python3 -m json.tool"
else
  echo "⊙ 跳过"
fi

echo ""
echo "━━━━ 结果: $PASS 通过, $FAIL 失败 ━━━━"
[[ $FAIL -eq 0 ]]
