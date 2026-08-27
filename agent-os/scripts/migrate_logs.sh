#!/bin/bash
# 日志迁移脚本：将标准库 log 转换为结构化日志
# 用法：./migrate_logs.sh <file_path>

set -e

if [ $# -ne 1 ]; then
    echo "用法: $0 <file_path>"
    echo "示例: $0 internal/service/notification_service.go"
    exit 1
fi

FILE="$1"

if [ ! -f "$FILE" ]; then
    echo "❌ 文件不存在: $FILE"
    exit 1
fi

echo "📝 迁移文件: $FILE"

# 1. 替换 import
if grep -q '"log"' "$FILE"; then
    echo "  → 替换 import"
    sed -i '' 's|"log"|"github.com/pi-investment/agent-os/internal/logger"|g' "$FILE"
fi

# 2. 备份原文件
cp "$FILE" "$FILE.bak"

# 3. 简单的 log.Println 替换
echo "  → 替换简单日志"
sed -i '' 's/log\.Println(\([^)]*\))/logger.L().Info(\1)/g' "$FILE"

# 4. log.Printf 需要手动处理（提示）
if grep -q "log\.Printf" "$FILE"; then
    echo "⚠️  文件中仍有 log.Printf，需要手动转换为结构化日志："
    echo ""
    grep -n "log\.Printf" "$FILE" | head -5
    echo ""
    echo "转换示例："
    echo "  log.Printf(\"User %s logged in\", userID)"
    echo "  → logger.L().Info(\"User logged in\", logger.String(\"user_id\", userID))"
    echo ""
fi

# 5. 检查是否有 log.Fatal/Panic
if grep -qE "log\.(Fatal|Panic)" "$FILE"; then
    echo "⚠️  文件中有 log.Fatal/Panic，需要手动决定处理方式"
    grep -nE "log\.(Fatal|Panic)" "$FILE"
fi

echo "✅ 迁移完成（备份: $FILE.bak）"
echo ""
echo "📋 下一步："
echo "  1. 检查文件差异: diff $FILE.bak $FILE"
echo "  2. 手动转换 log.Printf 为结构化日志"
echo "  3. 编译测试: go build ./..."
echo "  4. 确认无误后删除备份: rm $FILE.bak"
