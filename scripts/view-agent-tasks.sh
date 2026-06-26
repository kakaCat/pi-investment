#!/bin/bash
# 查看 Agent 迁移任务执行情况

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Agent 迁移任务执行情况"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 查看任务统计
curl -s "http://127.0.0.1:5001/api/scheduler/tasks" | python3 << 'EOF'
import sys, json
data = json.load(sys.stdin)
agent_tasks = [t for t in data['tasks'] if t['name'] in ['pre-market-scan', 'realtime-signal-monitor', 'daily-strategy-validation', 'weekly-strategy-discovery']]

print("任务统计:\n")
for task in agent_tasks:
    status = '✅' if task.get('enabled') else '❌'
    print(f"{status} {task['name']}")
    print(f"   ID: {task['id']}")
    print(f"   调度: {task['scheduleExpr']}")
    print(f"   下次运行: {task.get('nextRunAt', 'N/A')}")
    print(f"   今日触发: {task.get('todayTriggered', 0)} 次")
    print(f"   今日成功: {task.get('todaySuccess', 0)} 次")
    print()
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 最近 10 次执行记录"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 查看执行记录
curl -s "http://127.0.0.1:5001/api/scheduler/runs?limit=10" | python3 << 'EOF'
import sys, json
data = json.load(sys.stdin)

for run in data.get('runs', []):
    # 只显示 Agent 迁移任务
    if run['taskName'] not in ['pre-market-scan', 'realtime-signal-monitor', 'daily-strategy-validation', 'weekly-strategy-discovery']:
        continue

    status = '✅' if run['status'] == 'success' else '❌'
    print(f"{status} {run['taskName']}")
    print(f"   时间: {run['triggeredAt']}")
    print(f"   状态: {run['status']}")
    print(f"   耗时: {run.get('durationMs', 0)}ms")

    # 显示部分结果
    payload = run.get('payload', {})
    if payload:
        if 'total' in payload:
            print(f"   结果: 总={payload.get('total', 0)}, 高质量={payload.get('high_quality', 0)}")
        elif 'total_strategies' in payload:
            print(f"   结果: 策略={payload.get('total_strategies', 0)}, 失败={payload.get('failed', 0)}")
    print()
EOF
