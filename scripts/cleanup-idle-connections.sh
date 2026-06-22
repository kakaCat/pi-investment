#!/bin/bash
# 清理 PostgreSQL 空闲连接脚本
# 用途：定期清理超过指定时间的空闲连接，防止连接泄漏

set -e

# 配置
DB_HOST="127.0.0.1"
DB_USER="mac"
DB_NAME="quant_investment"
IDLE_TIMEOUT_MINUTES=30  # 空闲超过30分钟的连接将被终止
LOG_FILE="/tmp/pg-cleanup-idle-connections.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

# 检查 PostgreSQL 连接
if ! pg_isready -h "$DB_HOST" > /dev/null 2>&1; then
    log_error "PostgreSQL 服务不可用"
    exit 1
fi

log "开始清理空闲连接..."

# 1. 统计当前连接数
TOTAL_CONNECTIONS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c \
    "SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME';")
IDLE_CONNECTIONS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c \
    "SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME' AND state='idle';")

log "当前连接数: $TOTAL_CONNECTIONS (其中空闲: $IDLE_CONNECTIONS)"

# 2. 查找超时的空闲连接
TIMEOUT_QUERY="
SELECT pid,
       state,
       EXTRACT(EPOCH FROM (NOW() - state_change))/60 AS idle_minutes,
       usename,
       application_name
FROM pg_stat_activity
WHERE datname = '$DB_NAME'
  AND state = 'idle'
  AND state_change < NOW() - INTERVAL '$IDLE_TIMEOUT_MINUTES minutes'
  AND pid <> pg_backend_pid()
ORDER BY state_change;
"

TIMEOUT_CONNECTIONS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c \
    "SELECT count(*) FROM pg_stat_activity
     WHERE datname='$DB_NAME'
       AND state='idle'
       AND state_change < NOW() - INTERVAL '$IDLE_TIMEOUT_MINUTES minutes'
       AND pid <> pg_backend_pid();")

if [ "$TIMEOUT_CONNECTIONS" -eq 0 ]; then
    log_success "没有超时的空闲连接需要清理"
    exit 0
fi

log_warning "发现 $TIMEOUT_CONNECTIONS 个超时空闲连接（超过 $IDLE_TIMEOUT_MINUTES 分钟）"

# 3. 显示即将终止的连接详情
echo "即将终止的连接详情："
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "$TIMEOUT_QUERY"

# 4. 终止超时连接
TERMINATE_QUERY="
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_NAME'
  AND state = 'idle'
  AND state_change < NOW() - INTERVAL '$IDLE_TIMEOUT_MINUTES minutes'
  AND pid <> pg_backend_pid();
"

TERMINATED_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c "$TERMINATE_QUERY" | grep -c "t" || echo "0")

log_success "成功终止 $TERMINATED_COUNT 个超时空闲连接"

# 5. 统计清理后的连接数
FINAL_CONNECTIONS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c \
    "SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME';")
FINAL_IDLE=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c \
    "SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME' AND state='idle';")

log_success "清理完成！当前连接数: $FINAL_CONNECTIONS (其中空闲: $FINAL_IDLE)"

# 6. 检查连接使用率
MAX_CONNECTIONS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c "SHOW max_connections;")
USAGE_PERCENT=$((FINAL_CONNECTIONS * 100 / MAX_CONNECTIONS))

if [ $USAGE_PERCENT -gt 80 ]; then
    log_warning "警告：连接使用率 $USAGE_PERCENT% (${FINAL_CONNECTIONS}/${MAX_CONNECTIONS})，建议检查连接泄漏问题"
else
    log "连接使用率: $USAGE_PERCENT% (${FINAL_CONNECTIONS}/${MAX_CONNECTIONS})"
fi

exit 0
