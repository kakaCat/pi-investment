#!/bin/bash
# 交互式重构向导 - 引导用户完成重构步骤

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                   交互式重构向导                                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# 函数：询问用户
ask_user() {
    local question="$1"
    local default="${2:-n}"
    
    if [[ "$default" == "y" ]]; then
        echo -e "${BLUE}$question [Y/n]:${NC} "
    else
        echo -e "${BLUE}$question [y/N]:${NC} "
    fi
    
    read -r response
    response=${response:-$default}
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# 函数：显示进度
show_progress() {
    local step=$1
    local total=$2
    local desc="$3"
    
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}步骤 $step/$total: $desc${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 开始向导
echo "这个向导将引导你完成重构的各个步骤。"
echo "你可以选择跳过某些步骤，稍后手动执行。"
echo ""

if ! ask_user "开始重构向导？" "y"; then
    echo "已取消"
    exit 0
fi

# 步骤 1: 验证当前状态
show_progress 1 7 "验证当前状态"

echo "首先，让我们看看当前的问题状态..."
python scripts/refactor/verify_fixes.py

echo ""
if ! ask_user "继续下一步？" "y"; then
    echo "退出向导"
    exit 0
fi

# 步骤 2: 安装项目包
show_progress 2 7 "安装项目包"

if ask_user "是否安装项目为 Python 包 (pip install -e .)？" "y"; then
    make install
    echo -e "${GREEN}✅ 项目包安装完成${NC}"
else
    echo -e "${YELLOW}⏭️  跳过安装${NC}"
fi

# 步骤 3: 移除 sys.path.insert
show_progress 3 7 "移除 sys.path.insert"

echo "当前有 212 处 sys.path.insert 需要清理"
echo ""

if ask_user "是否预览将要清理的内容？" "y"; then
    python scripts/refactor/remove_sys_path_hacks.py | head -50
fi

echo ""
if ask_user "是否执行清理 (移除所有 sys.path.insert)？" "n"; then
    make fix-syspath
    echo -e "${GREEN}✅ sys.path.insert 清理完成${NC}"
else
    echo -e "${YELLOW}⏭️  跳过清理${NC}"
fi

# 步骤 4: 扫描违规导入
show_progress 4 7 "扫描数据源直接导入"

if ask_user "是否扫描违规的数据源导入？" "y"; then
    make scan-imports | head -80
    echo ""
    echo -e "${YELLOW}💡 提示: 完整报告可运行: make scan-imports > report.md${NC}"
else
    echo -e "${YELLOW}⏭️  跳过扫描${NC}"
fi

# 步骤 5: 代码格式化
show_progress 5 7 "代码格式化"

if ask_user "是否运行代码格式化 (black + ruff)？" "y"; then
    if command -v black &> /dev/null && command -v ruff &> /dev/null; then
        make format
        echo -e "${GREEN}✅ 代码格式化完成${NC}"
    else
        echo -e "${RED}❌ black 或 ruff 未安装${NC}"
        echo "安装: pip install black ruff"
    fi
else
    echo -e "${YELLOW}⏭️  跳过格式化${NC}"
fi

# 步骤 6: 运行测试
show_progress 6 7 "运行测试"

if ask_user "是否运行测试验证修改？" "y"; then
    echo "运行快速测试..."
    make test-quick || {
        echo -e "${RED}❌ 测试失败${NC}"
        if ask_user "查看测试失败详情？" "y"; then
            make test
        fi
    }
    echo -e "${GREEN}✅ 测试通过${NC}"
else
    echo -e "${YELLOW}⏭️  跳过测试${NC}"
fi

# 步骤 7: 保存进度
show_progress 7 7 "保存进度"

if ask_user "是否保存进度快照？" "y"; then
    make progress
    echo -e "${GREEN}✅ 进度已保存${NC}"
else
    echo -e "${YELLOW}⏭️  跳过保存${NC}"
fi

# 完成
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                   🎉 向导完成！                                           ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 接下来的步骤:"
echo "  1. 检查修改: git diff"
echo "  2. 阅读文档: cat docs/refactor/QUICKSTART.md"
echo "  3. 继续执行 Week 2-4 的任务"
echo ""
echo "💡 有用的命令:"
echo "  make verify     - 验证状态"
echo "  make history    - 查看进度历史"
echo "  make report     - 生成状态报告"
echo ""
