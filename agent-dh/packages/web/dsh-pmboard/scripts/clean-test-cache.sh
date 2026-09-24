#!/bin/bash
set -e

echo "🧹 清理 Vitest 缓存..."

# 1. 删除 Vite 缓存
rm -rf node_modules/.vite
rm -rf node_modules/.vitest

# 2. 删除可能的临时目录
rm -rf .vitest
rm -rf dist

echo "✅ 缓存清理完成"
echo ""
echo "下一步："
echo "  npx vitest run tests/template-address.test.ts --no-cache"
