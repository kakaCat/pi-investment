#!/bin/bash
# 重启 DSH Web 的脚本

# 1. 杀掉所有 dsh web 进程
echo "正在停止 DSH Web..."
pkill -f "dsh web"
sleep 2

# 2. 确认端口 3080 已释放
if lsof -i :3080 > /dev/null 2>&1; then
    echo "端口 3080 仍被占用，强制杀掉进程..."
    lsof -ti :3080 | xargs kill -9 2>/dev/null
    sleep 1
fi

# 3. 启动 DSH Web
echo "正在启动 DSH Web..."
cd ~/.dsh/profiles/investment && nohup node_modules/.bin/dsh web > /tmp/dsh-web.log 2>&1 &
DSH_PID=$!
echo "DSH Web 已启动，PID: $DSH_PID"

# 4. 等待启动并显示访问地址
sleep 3
if grep -q "http://127.0.0.1:3080" /tmp/dsh-web.log; then
    echo "✅ DSH Web 启动成功！"
    grep "http://127.0.0.1:3080" /tmp/dsh-web.log | head -1
else
    echo "❌ DSH Web 启动可能失败，检查日志："
    tail -20 /tmp/dsh-web.log
fi
