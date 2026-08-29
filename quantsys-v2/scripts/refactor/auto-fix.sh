#!/bin/bash
# 自动修复脚本 - 一键运行所有自动化修复工具
#
# Usage:
#   bash scripts/refactor/auto-fix.sh [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
fi

cd "$PROJECT_ROOT"

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║           QuantSys V2 自动修复脚本                                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

if $DRY_RUN; then
    echo "🔍 预览模式 (不会修改文件)"
else
    echo "⚠️  修改模式 (将实际修改文件)"
    echo ""
    read -p "确认继续? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

echo ""

# 步骤 1: 移除 sys.path.insert
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 步骤 1/3: 移除 sys.path.insert"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if $DRY_RUN; then
    python scripts/refactor/remove_sys_path_hacks.py
else
    python scripts/refactor/remove_sys_path_hacks.py --fix
fi

echo ""

# 步骤 2: 代码格式化
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 步骤 2/3: 代码格式化 (Black + Ruff)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v black &> /dev/null; then
    if $DRY_RUN; then
        echo "预览 Black 格式化..."
        black --check --diff . 2>&1 | head -20
    else
        echo "运行 Black 格式化..."
        black .
    fi
else
    echo "⚠️  Black 未安装，跳过格式化"
fi

echo ""

if command -v ruff &> /dev/null; then
    if $DRY_RUN; then
        echo "预览 Ruff 检查..."
        ruff check . 2>&1 | head -20
    else
        echo "运行 Ruff 修复..."
        ruff check --fix .
    fi
else
    echo "⚠️  Ruff 未安装，跳过检查"
fi

echo ""

# 步骤 3: 验证
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 步骤 3/3: 验证修复结果"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python scripts/refactor/verify_fixes.py

echo ""

# 总结
if $DRY_RUN; then
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║ 预览完成！要实际修改文件，运行:                                          ║"
    echo "║   bash scripts/refactor/auto-fix.sh                                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
else
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║ ✅ 自动修复完成！                                                         ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📝 下一步:"
    echo "  1. 检查修改: git diff"
    echo "  2. 运行测试: pytest"
    echo "  3. 提交更改: git add . && git commit -m 'refactor: auto-fix code quality issues'"
fi

echo ""
