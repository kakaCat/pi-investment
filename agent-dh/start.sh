#!/bin/bash
# Agent-DH 启动脚本
# 使用 tsx 加载器支持 TypeScript 源码直接运行

# 堆上限设置（2026-09-11 紧急修复）
# 问题：多窗口共享单进程，内存持续增长，默认 4GB 限制导致 OOM 循环重启
# 解决：提升到 16GB（机器有 64GB RAM，余量充足）
DSH_MAX_OLD_SPACE="${DSH_MAX_OLD_SPACE:-16384}"
export NODE_OPTIONS="--max-old-space-size=${DSH_MAX_OLD_SPACE} --import tsx/esm"

echo "========================================"
echo "  Agent-DH 启动"
echo "========================================"
echo "Node: $(node --version)"
echo "Heap limit: ${DSH_MAX_OLD_SPACE}MB"
echo "Port: 3080"
echo ""

# 清理可能占用的端口
lsof -ti:3080 | xargs kill -9 2>/dev/null || true

# 启动 DSH
exec ~/.dsh/profiles/investment/node_modules/.bin/dsh --profile investment "$@"
