#!/bin/bash
# 激活 Python 3.13 虚拟环境

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 激活虚拟环境
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    echo "✅ 已激活 Python 3.13 虚拟环境: $(python --version)"

    # 限制 polars 线程数，避免与 NumPy 内存分配器冲突导致崩溃
    # 参考：psycopg2-binary double-openssl crash 同类问题（2026-08-11）
    export POLARS_MAX_THREADS=4
    echo "🔧 POLARS_MAX_THREADS=4 (避免多线程内存竞争)"

    # 项目根目录加入 PYTHONPATH：脚本/工具无需再 sys.path.insert
    # （Phase 3 任务 6：统一路径入口，替代各文件散落的 200+ 处 sys.path.insert）
    export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH}"
    echo "🔧 PYTHONPATH=$SCRIPT_DIR"
else
    echo "❌ 虚拟环境不存在，请先运行："
    echo "   /opt/homebrew/bin/python3.13 -m venv venv"
    exit 1
fi
