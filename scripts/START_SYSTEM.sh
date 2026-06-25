#!/bin/bash
# 博弈智能系统启动脚本

echo "🚀 启动博弈智能系统"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 启动后端
echo "📡 启动后端API服务..."
cd quantsys-v2
pkill -f "python.*start_all.py" 2>/dev/null
nohup python start_all.py > /tmp/api_server.log 2>&1 &
API_PID=$!
echo "   后端服务PID: $API_PID"

# 等待服务启动
sleep 5

# 验证后端
echo "🔍 验证后端服务..."
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "   ✅ 后端服务运行正常"
else
    echo "   ❌ 后端服务启动失败"
    echo "   查看日志: tail -f /tmp/api_server.log"
    exit 1
fi

# 2. 启动前端
echo ""
echo "🎨 启动前端开发服务器..."
cd ../web-frontend

if [ ! -d "node_modules" ]; then
    echo "   📦 安装依赖..."
    npm install
fi

echo "   🚀 启动Vue开发服务器..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 后端: http://localhost:5001"
echo "✅ 前端: 将在下方显示（通常是 http://localhost:5173）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 访问以下页面："
echo "   - 总览仪表板: /game-intelligence/dashboard"
echo "   - 对手行为: /game-intelligence/opponent-behavior"
echo "   - 预警中心: /game-intelligence/alerts"
echo "   - 学习闭环: /game-intelligence/learning-loop"
echo "   - 任务监控: /game-intelligence/automation-monitor"
echo "   - 自动化配置: /game-intelligence/automation-config"
echo ""
echo "按 Ctrl+C 停止前端服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

npm run dev
