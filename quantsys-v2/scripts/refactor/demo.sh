#!/bin/bash
# 中等问题重构 - 一键演示脚本
# 
# 此脚本演示重构工具链的完整工作流程

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     QuantSys V2 中等问题重构 - 工具演示                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

cd "$PROJECT_ROOT"

# 1. 验证当前状态
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 步骤 1/4: 验证当前修复状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python scripts/refactor/verify_fixes.py
echo ""

# 2. 扫描数据源违规导入
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 步骤 2/4: 扫描数据源直接导入"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python scripts/refactor/find_direct_imports.py 2>&1 | head -40
echo ""
echo "ℹ️  完整报告: python scripts/refactor/find_direct_imports.py > report.md"
echo ""

# 3. TODO 分类统计
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 步骤 3/4: TODO/FIXME 分类统计"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python scripts/refactor/classify_todos.py 2>&1 | head -50
echo ""
echo "ℹ️  完整报告: python scripts/refactor/classify_todos.py > todos.md"
echo ""

# 4. sys.path.insert 预览
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 步骤 4/4: sys.path.insert 清理预览 (预览模式)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python scripts/refactor/remove_sys_path_hacks.py 2>&1 | head -50
echo ""
echo "ℹ️  实际修改: python scripts/refactor/remove_sys_path_hacks.py --fix"
echo ""

# 总结
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║ ✅ 演示完成！                                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📚 下一步:"
echo "  1. 阅读文档: docs/refactor/README.md"
echo "  2. 快速开始: docs/refactor/QUICKSTART.md"
echo "  3. 执行重构: 按 Week 1-4 计划逐步进行"
echo ""
echo "🔗 相关文档:"
echo "  - 执行摘要: docs/refactor/EXECUTIVE-SUMMARY.md"
echo "  - 技术方案: docs/refactor/medium-issues-solution.md"
echo "  - 快速指南: docs/refactor/QUICKSTART.md"
echo ""
