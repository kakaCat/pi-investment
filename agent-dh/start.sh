#!/bin/bash
# Agent-DH 启动脚本
# 使用 tsx 加载器支持 TypeScript 源码直接运行

export NODE_OPTIONS="--import tsx/esm"

# 清理可能占用的端口
lsof -ti:3080 | xargs kill -9 2>/dev/null || true

# 启动 DSH
exec ~/.dsh/profiles/investment/node_modules/.bin/dsh --profile investment "$@"
