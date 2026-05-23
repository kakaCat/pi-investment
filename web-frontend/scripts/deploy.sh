#!/bin/bash

###############################################################################
# PI Investment Web Frontend - Deploy Script
# 用途: 部署前端应用到生产服务器
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

# 默认配置
ENVIRONMENT="${1:-production}"
DEPLOY_METHOD="${2:-ssh}"

# 配置文件
CONFIG_FILE="$PROJECT_DIR/.deploy.config"

###############################################################################
# 加载配置
###############################################################################

load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
        log_success "已加载配置文件: $CONFIG_FILE"
    else
        log_warning "配置文件不存在，使用环境变量"
    fi

    # 必需的环境变量
    DEPLOY_HOST="${DEPLOY_HOST:-}"
    DEPLOY_USER="${DEPLOY_USER:-}"
    DEPLOY_PATH="${DEPLOY_PATH:-/var/www/pi-investment-web}"
    DEPLOY_PORT="${DEPLOY_PORT:-22}"
}

###############################################################################
# 验证配置
###############################################################################

validate_config() {
    log_info "验证部署配置..."

    if [ "$DEPLOY_METHOD" = "ssh" ]; then
        if [ -z "$DEPLOY_HOST" ] || [ -z "$DEPLOY_USER" ]; then
            log_error "SSH部署需要设置 DEPLOY_HOST 和 DEPLOY_USER"
            echo "请设置环境变量或创建 .deploy.config 文件"
            exit 1
        fi
    fi

    log_success "配置验证通过"
}

###############################################################################
# 构建应用
###############################################################################

build_app() {
    log_info "构建应用..."

    cd "$PROJECT_DIR"

    if [ -f "scripts/build.sh" ]; then
        bash scripts/build.sh
    else
        npm run build
    fi

    log_success "应用构建完成"
}

###############################################################################
# SSH部署
###############################################################################

deploy_via_ssh() {
    log_info "通过SSH部署到 $DEPLOY_HOST..."

    local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local BACKUP_DIR="$DEPLOY_PATH.backup.$TIMESTAMP"
    local TEMP_DIR="/tmp/pi-investment-web-$TIMESTAMP"

    # 1. 上传构建产物
    log_info "上传构建产物..."
    ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$DEPLOY_HOST" "mkdir -p $TEMP_DIR"
    scp -P "$DEPLOY_PORT" -r "$PROJECT_DIR/dist/"* "$DEPLOY_USER@$DEPLOY_HOST:$TEMP_DIR/"

    # 2. 备份当前版本
    log_info "备份当前版本..."
    ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$DEPLOY_HOST" << EOF
        if [ -d "$DEPLOY_PATH" ]; then
            sudo mv "$DEPLOY_PATH" "$BACKUP_DIR"
            echo "已备份到: $BACKUP_DIR"
        fi
EOF

    # 3. 部署新版本
    log_info "部署新版本..."
    ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$DEPLOY_HOST" << EOF
        sudo mv "$TEMP_DIR" "$DEPLOY_PATH"
        sudo chown -R www-data:www-data "$DEPLOY_PATH"
        sudo chmod -R 755 "$DEPLOY_PATH"
        echo "新版本已部署到: $DEPLOY_PATH"
EOF

    # 4. 重载Nginx
    log_info "重载Nginx..."
    ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$DEPLOY_HOST" << EOF
        sudo nginx -t && sudo systemctl reload nginx
        echo "Nginx已重载"
EOF

    # 5. 清理旧备份（保留最近3个）
    log_info "清理旧备份..."
    ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$DEPLOY_HOST" << EOF
        cd $(dirname "$DEPLOY_PATH")
        ls -t pi-investment-web.backup.* 2>/dev/null | tail -n +4 | xargs -r sudo rm -rf
        echo "已清理旧备份"
EOF

    log_success "SSH部署完成"
}

###############################################################################
# Docker部署
###############################################################################

deploy_via_docker() {
    log_info "通过Docker部署..."

    cd "$PROJECT_DIR"

    # 1. 构建Docker镜像
    log_info "构建Docker镜像..."
    docker build -t pi-investment-web:latest .

    # 2. 停止旧容器
    log_info "停止旧容器..."
    docker-compose down || true

    # 3. 启动新容器
    log_info "启动新容器..."
    docker-compose up -d

    # 4. 查看容器状态
    log_info "容器状态:"
    docker-compose ps

    log_success "Docker部署完成"
}

###############################################################################
# 健康检查
###############################################################################

health_check() {
    log_info "执行健康检查..."

    local HEALTH_URL="${DEPLOY_URL:-http://$DEPLOY_HOST}"
    local MAX_RETRIES=5
    local RETRY_DELAY=3

    for i in $(seq 1 $MAX_RETRIES); do
        log_info "尝试 $i/$MAX_RETRIES..."

        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")

        if [ "$HTTP_CODE" = "200" ]; then
            log_success "健康检查通过！站点正常响应 (HTTP $HTTP_CODE)"
            return 0
        else
            log_warning "站点响应异常 (HTTP $HTTP_CODE)，等待 ${RETRY_DELAY}s 后重试..."
            sleep $RETRY_DELAY
        fi
    done

    log_error "健康检查失败！站点无法正常访问"
    return 1
}

###############################################################################
# 回滚
###############################################################################

rollback() {
    log_warning "开始回滚..."

    if [ "$DEPLOY_METHOD" = "ssh" ]; then
        ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$DEPLOY_HOST" << EOF
            LATEST_BACKUP=\$(ls -t $(dirname "$DEPLOY_PATH")/pi-investment-web.backup.* 2>/dev/null | head -n 1)
            if [ -n "\$LATEST_BACKUP" ]; then
                sudo rm -rf "$DEPLOY_PATH"
                sudo mv "\$LATEST_BACKUP" "$DEPLOY_PATH"
                sudo systemctl reload nginx
                echo "已回滚到: \$LATEST_BACKUP"
            else
                echo "未找到备份，无法回滚"
                exit 1
            fi
EOF
        log_success "回滚完成"
    else
        log_error "Docker部署暂不支持自动回滚"
    fi
}

###############################################################################
# 主函数
###############################################################################

main() {
    log_info "开始部署 PI Investment Web Frontend..."
    echo "=================================================="
    echo "环境: $ENVIRONMENT"
    echo "方法: $DEPLOY_METHOD"
    echo "=================================================="

    # 加载配置
    load_config

    # 验证配置
    validate_config

    # 构建应用
    build_app

    # 执行部署
    if [ "$DEPLOY_METHOD" = "ssh" ]; then
        deploy_via_ssh
    elif [ "$DEPLOY_METHOD" = "docker" ]; then
        deploy_via_docker
    else
        log_error "不支持的部署方法: $DEPLOY_METHOD"
        exit 1
    fi

    # 健康检查
    if health_check; then
        log_success "部署成功！"
    else
        log_error "部署后健康检查失败"
        read -p "是否回滚？(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback
        fi
        exit 1
    fi

    echo "=================================================="
    log_success "部署流程完成！"
}

###############################################################################
# 执行主函数
###############################################################################

main "$@"
