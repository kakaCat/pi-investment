#!/bin/bash
# 服务重启脚本

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 博弈智能系统 - 服务重启"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 停止旧服务
echo "Step 1: 停止旧服务..."
pkill -f "python.*start_all.py" 2>/dev/null && echo "  ✅ 已停止后端" || echo "  ℹ️  后端未运行"
pkill -f "vite.*dev" 2>/dev/null && echo "  ✅ 已停止前端" || echo "  ℹ️  前端未运行"
sleep 2

# 启动后端
echo ""
echo "Step 2: 启动后端服务..."
cd quantsys-v2
nohup python start_all.py > /tmp/api_server.log 2>&1 &
BACKEND_PID=$!
echo "  ✅ 后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
echo ""
echo "Step 3: 等待后端服务启动..."
sleep 5

# 验证后端
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "  ✅ 后端服务运行正常"
else
    echo "  ⚠️  后端服务可能还在启动中"
    echo "  查看日志: tail -f /tmp/api_server.log"
fi

# 前端启动说明
echo ""
echo "Step 4: 启动前端服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "前端需要在新终端运行，请执行："
echo ""
echo "  cd web-frontend"
echo "  npm run dev"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 启动后访问："
echo "  http://localhost:5173/game-intelligence/dashboard"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 后端重启完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
