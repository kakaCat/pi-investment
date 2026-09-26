#!/bin/bash

echo "🎮 启动坦克大作战游戏..."
echo ""

# 检查端口 8000 是否被占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口 8000 已被占用，尝试使用端口 8001..."
    PORT=8001
else
    PORT=8000
fi

# 启动 HTTP 服务器
if command -v python3 &> /dev/null; then
    echo "✅ 使用 Python 3 启动服务器..."
    echo "🌐 游戏地址: http://localhost:$PORT"
    echo "⏹️  按 Ctrl+C 停止服务器"
    echo ""
    python3 -m http.server $PORT
elif command -v python &> /dev/null; then
    echo "✅ 使用 Python 2 启动服务器..."
    echo "🌐 游戏地址: http://localhost:$PORT"
    echo "⏹️  按 Ctrl+C 停止服务器"
    echo ""
    python -m SimpleHTTPServer $PORT
else
    echo "❌ 未找到 Python，请安装 Python 或手动打开 index.html"
    echo ""
    echo "🔧 安装方法："
    echo "   macOS: brew install python3"
    echo "   Ubuntu: sudo apt install python3"
    echo "   Windows: 从 python.org 下载安装"
    echo ""
    echo "📂 或者直接双击 index.html 文件在浏览器中打开"
    exit 1
fi
