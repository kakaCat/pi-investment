#!/bin/bash

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 PI Investment 功能实现状态检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. 后端Service
echo "1️⃣ 后端Service层"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
services=(
  "opponent_behavior_service"
  "battlefield_assessor"
  "manipulation_detector"
  "decision_service"
  "knowledge_service"
  "decision_evaluator"
  "learning_engine"
  "game_alert_service"
  "risk_assessor"
  "health_tracker"
  "attribution_analyzer"
)

for svc in "${services[@]}"; do
  if [ -f "quantsys-v2/application/services/${svc}.py" ]; then
    echo "  ✅ $svc.py"
  else
    echo "  ❌ $svc.py - 未找到"
  fi
done
echo ""

# 2. API端点
echo "2️⃣ API端点"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
api_files=(
  "game_intelligence.py"
  "decision_tracking.py"
  "knowledge_management.py"
  "learning_system.py"
  "game_alert.py"
  "config.py"
)

for api in "${api_files[@]}"; do
  if [ -f "quantsys-v2/adapters/inbound/api/routes/${api}" ]; then
    count=$(grep -c "@.*route" "quantsys-v2/adapters/inbound/api/routes/${api}")
    echo "  ✅ $api - $count 个端点"
  else
    echo "  ❌ $api - 未找到"
  fi
done
echo ""

# 3. Agent工具
echo "3️⃣ Agent工具"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "agent-ts/src/infrastructure/tools/agent" ]; then
  tools=$(ls agent-ts/src/infrastructure/tools/agent/*.ts 2>/dev/null | grep -E "opponent|battlefield|manipulation|decision|knowledge|learning|alert|risk" | wc -l)
  echo "  ✅ 找到 $tools 个博弈智能工具"
  ls agent-ts/src/infrastructure/tools/agent/*.ts 2>/dev/null | grep -E "opponent|battlefield|manipulation|decision|knowledge|learning|alert|risk" | sed 's/.*\//  • /'
else
  echo "  ❌ Agent工具目录不存在"
fi
echo ""

# 4. 前端页面
echo "4️⃣ 前端页面"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "web-frontend/src/views/GameIntelligence" ]; then
  pages=$(ls web-frontend/src/views/GameIntelligence/*.vue 2>/dev/null | wc -l)
  echo "  ✅ 找到 $pages 个前端页面"
  ls web-frontend/src/views/GameIntelligence/*.vue 2>/dev/null | sed 's/.*\//  • /'
else
  echo "  ❌ 前端页面目录不存在"
fi
echo ""

# 5. 定时任务
echo "5️⃣ 定时任务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
scripts=(
  "morning_analysis.sh"
  "realtime_monitor.sh"
  "daily_learning.sh"
)

for script in "${scripts[@]}"; do
  if [ -f "scripts/${script}" ]; then
    echo "  ✅ scripts/$script"
  else
    echo "  ❌ scripts/$script - 未找到"
  fi
done

echo ""
echo "  Crontab配置:"
cron_count=$(crontab -l 2>/dev/null | grep -v "^#" | grep -c quantsys)
if [ $cron_count -gt 0 ]; then
  echo "  ✅ 已配置 $cron_count 个定时任务"
  crontab -l 2>/dev/null | grep quantsys | sed 's/^/  • /'
else
  echo "  ❌ 未配置crontab"
fi
echo ""

# 6. 进程守护
echo "6️⃣ 进程守护"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v pm2 &> /dev/null; then
  echo "  ✅ pm2 已安装"
  pm2_agent=$(pm2 list 2>/dev/null | grep -c agent)
  if [ $pm2_agent -gt 0 ]; then
    echo "  ✅ agent 进程由pm2管理"
  else
    echo "  ⚠️  agent 未由pm2管理"
  fi
else
  echo "  ❌ pm2 未安装"
fi
echo ""

# 7. 通知服务
echo "7️⃣ 通知服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
notif_files=$(find agent-ts/src -name "*notif*" -o -name "*feishu*" 2>/dev/null | grep -v node_modules | wc -l)
if [ $notif_files -gt 0 ]; then
  echo "  ✅ 找到 $notif_files 个通知相关文件"
else
  echo "  ❌ 未找到通知服务实现"
fi
echo ""

# 8. 工作流
echo "8️⃣ 工作流编排"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
workflow_files=$(find agent-ts/src -name "*workflow*" 2>/dev/null | grep -v node_modules | wc -l)
if [ $workflow_files -gt 0 ]; then
  echo "  ✅ 找到 $workflow_files 个工作流文件"
else
  echo "  ❌ 未找到工作流实现"
fi
echo ""

# 9. 配置文件
echo "9️⃣ 配置管理"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "quantsys-v2/config/automation.json" ]; then
  echo "  ✅ automation.json 存在"
else
  echo "  ⚠️  automation.json 不存在（配置保存功能可能未使用）"
fi
echo ""

# 总结
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 总结"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ 已实现："
echo "  • 博弈智能模块（Service + API + 工具 + 页面）"
echo "  • 定时任务脚本"
echo "  • 配置管理API"
echo ""
echo "❌ 未实现："
echo "  • 定时任务调度（crontab未配置）"
echo "  • 进程守护（pm2未配置）"
echo "  • 通知服务（未实现）"
echo "  • 工作流编排（未实现）"
echo ""
echo "🎯 下一步："
echo "  1. 配置crontab"
echo "  2. 实现通知服务"
echo "  3. 编写工作流"
echo "  4. 配置pm2"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
