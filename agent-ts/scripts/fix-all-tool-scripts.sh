#!/bin/bash
# 一键修复所有工具任务脚本的代理问题

cd /Users/mac/Documents/ai/pi-investment/agent-ts

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 修复工具任务脚本 - 解决HTTP代理502问题"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 备份所有相关脚本
echo "📦 备份现有脚本..."
BACKUP_DIR="scripts/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

for script in execute-tool-tasks{,-fixed,-final}.py run-morning-analysis.py final-tool-task.py demo-tool-workflow.py; do
    if [ -f "scripts/$script" ]; then
        cp "scripts/$script" "$BACKUP_DIR/$script"
        echo "  ✅ 已备份: $script"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 应用修复..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 替换所有脚本为修复版本
SCRIPTS_TO_FIX=(
    "execute-tool-tasks.py"
    "execute-tool-tasks-fixed.py"
    "execute-tool-tasks-final.py"
)

for script in "${SCRIPTS_TO_FIX[@]}"; do
    if [ -f "scripts/$script" ]; then
        cp "scripts/run-tool-tasks-now.py" "scripts/$script"
        echo "  ✅ 已修复: $script"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 修复完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 修复内容:"
echo "  • 清除HTTP代理环境变量"
echo "  • 使用requests.Session并禁用trust_env"
echo "  • 直接访问本地API (127.0.0.1:5001)"
echo ""
echo "💾 备份位置: $BACKUP_DIR"
echo ""
echo "🧪 测试修复结果:"
python3 scripts/run-tool-tasks-now.py
echo ""
echo "💡 下次飞书通知应该显示所有任务 ✅ 而不是 ❌"
