#!/bin/bash
# 激活 Python 3.13 虚拟环境

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 激活虚拟环境
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    echo "✅ 已激活 Python 3.13 虚拟环境: $(python --version)"
else
    echo "❌ 虚拟环境不存在，请先运行："
    echo "   /opt/homebrew/bin/python3.13 -m venv venv"
    exit 1
fi
