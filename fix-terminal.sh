#!/bin/bash
# 修复终端乱码问题
# 使用方法：source fix-terminal.sh 或 . fix-terminal.sh

echo "🔧 修复终端编码和显示..."

# 1. 重置终端状态
reset -Q 2>/dev/null || reset

# 2. 恢复正常终端模式
stty sane 2>/dev/null

# 3. 启用 UTF-8 输入
stty iutf8 2>/dev/null

# 4. 设置编码环境变量
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8

# 5. 清屏
clear

echo "✅ 终端已修复"
echo ""
echo "编码设置："
echo "  LANG=$LANG"
echo "  LC_ALL=$LC_ALL"
echo ""
echo "如果问题仍然存在，请："
echo "  1. 完全关闭当前终端窗口"
echo "  2. 打开新的终端窗口"
echo "  3. 重新启动 agent"
