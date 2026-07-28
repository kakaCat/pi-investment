#!/bin/bash
# 切换 LLM provider（deepseek ↔ kimi）
# 原理：改 .env 的 LLM_PROVIDER 一行。切换后需重启 agent 生效。
# （不重启的热切换 /provider 命令已合并 main，等主工作区回到 main 后可用）
set -euo pipefail

ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"

usage() {
    current=$(grep '^LLM_PROVIDER=' "$ENV_FILE" | cut -d= -f2)
    echo "当前 provider: $current"
    echo "用法: $0 [deepseek|kimi]"
    exit "${1:-0}"
}

[ $# -eq 0 ] && usage 0

target=$(echo "$1" | tr 'A-Z' 'a-z')
case "$target" in
    deepseek|kimi) ;;
    k3|kimi-k3|moonshot) target=kimi ;;
    *) echo "❌ 未知 provider: $1（可选 deepseek / kimi）"; exit 1 ;;
esac

current=$(grep '^LLM_PROVIDER=' "$ENV_FILE" | cut -d= -f2)
if [ "$current" = "$target" ]; then
    echo "ℹ️  已是 $target，无需切换"
    exit 0
fi

# 校验目标 provider 的 key 已配置
key_var="$(echo "$target" | tr 'a-z' 'A-Z')_API_KEY"
if ! grep -q "^${key_var}=sk-" "$ENV_FILE"; then
    echo "❌ $target 的 ${key_var} 未在 .env 配置"
    exit 1
fi

sed -i '' "s/^LLM_PROVIDER=.*/LLM_PROVIDER=$target/" "$ENV_FILE"
echo "✅ 已切换 $current → $target"
echo "⚠️  重启 agent 后生效（Ctrl+C 后 npm run dev）"
