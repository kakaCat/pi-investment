#!/bin/bash

###############################################################################
# PI Investment Web Frontend - Build Script
# 用途: 构建生产环境的前端应用
###############################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 配置
BUILD_DIR="$PROJECT_DIR/dist"
NODE_VERSION="20"

###############################################################################
# 主函数
###############################################################################

main() {
    log_info "开始构建 PI Investment Web Frontend..."
    echo "=================================================="

    # 检查Node.js版本
    check_node_version

    # 清理旧的构建产物
    clean_build

    # 安装依赖
    install_dependencies

    # 类型检查
    type_check

    # 构建应用
    build_app

    # 构建报告
    build_report

    log_success "构建完成！"
    echo "=================================================="
}

###############################################################################
# 检查Node.js版本
###############################################################################

check_node_version() {
    log_info "检查Node.js版本..."

    if ! command -v node &> /dev/null; then
        log_error "未找到Node.js，请先安装Node.js $NODE_VERSION+"
        exit 1
    fi

    CURRENT_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)

    if [ "$CURRENT_VERSION" -lt "$NODE_VERSION" ]; then
        log_error "Node.js版本过低，当前: v$CURRENT_VERSION，需要: v$NODE_VERSION+"
        exit 1
    fi

    log_success "Node.js版本检查通过: $(node -v)"
}

###############################################################################
# 清理构建目录
###############################################################################

clean_build() {
    log_info "清理旧的构建产物..."

    cd "$PROJECT_DIR"

    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        log_success "已清理 dist 目录"
    fi

    # 清理缓存
    if [ -d "node_modules/.vite" ]; then
        rm -rf "node_modules/.vite"
        log_success "已清理 Vite 缓存"
    fi
}

###############################################################################
# 安装依赖
###############################################################################

install_dependencies() {
    log_info "安装依赖..."

    cd "$PROJECT_DIR"

    if [ ! -d "node_modules" ]; then
        npm ci
        log_success "依赖安装完成"
    else
        log_info "node_modules 已存在，跳过安装"
    fi
}

###############################################################################
# 类型检查
###############################################################################

type_check() {
    log_info "执行TypeScript类型检查..."

    cd "$PROJECT_DIR"

    if npx vue-tsc --noEmit; then
        log_success "类型检查通过"
    else
        log_error "类型检查失败"
        exit 1
    fi
}

###############################################################################
# 构建应用
###############################################################################

build_app() {
    log_info "构建生产版本..."

    cd "$PROJECT_DIR"

    # 设置环境变量
    export NODE_ENV=production

    # 执行构建
    if npm run build; then
        log_success "应用构建成功"
    else
        log_error "应用构建失败"
        exit 1
    fi
}

###############################################################################
# 构建报告
###############################################################################

build_report() {
    log_info "生成构建报告..."

    cd "$PROJECT_DIR"

    if [ -d "$BUILD_DIR" ]; then
        # 统计文件大小
        TOTAL_SIZE=$(du -sh "$BUILD_DIR" | cut -f1)
        FILE_COUNT=$(find "$BUILD_DIR" -type f | wc -l)

        echo ""
        echo "=================================================="
        log_success "构建统计信息:"
        echo "  - 构建目录: $BUILD_DIR"
        echo "  - 总大小: $TOTAL_SIZE"
        echo "  - 文件数量: $FILE_COUNT"
        echo ""

        # 列出主要文件
        log_info "主要文件:"
        find "$BUILD_DIR" -type f -name "*.js" -o -name "*.css" | while read file; do
            size=$(du -h "$file" | cut -f1)
            name=$(basename "$file")
            echo "  - $name: $size"
        done

        echo "=================================================="
    else
        log_error "构建目录不存在"
        exit 1
    fi
}

###############################################################################
# 执行主函数
###############################################################################

main "$@"
