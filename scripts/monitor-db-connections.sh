#!/bin/bash
# PostgreSQL 连接数监控脚本
# 用途：监控数据库连接数，超过阈值时告警

set -e

# 配置
DB_HOST="127.0.0.1"
DB_USER="mac"
DB_NAME="quant_investment"
WARNING_THRESHOLD=80      # 警告阈值（连接数）
CRITICAL_THRESHOLD=90     # 严重阈值（连接数）
LOG_FILE="/tmp/pg-monitor-connections.log"

# 颜色输出
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查 PostgreSQL 连接
if ! pg_isready -h "$DB_HOST" > /dev/null 2>&1; then
    echo -e "${RED}CRITICAL: PostgreSQL 服务不可用${NC}"
    exit 2
fi

# 获取连接统计
STATS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c "
SELECT
    (SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME') as total,
    (SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME' AND state='idle') as idle,
    (SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME' AND state='active') as active,
    (SELECT count(*) FROM pg_stat_activity WHERE datname='$DB_NAME' AND state='idle in transaction') as idle_in_txn,
    (SELECT setting::int FROM pg_settings WHERE name='max_connections') as max_conn;
")

TOTAL=$(echo $STATS | awk '{print $1}' | tr -d ' ')
IDLE=$(echo $STATS | awk '{print $3}' | tr -d ' |')
ACTIVE=$(echo $STATS | awk '{print $5}' | tr -d ' ')
IDLE_IN_TXN=$(echo $STATS | awk '{print $7}' | tr -d ' |')
MAX_CONN=$(echo $STATS | awk '{print $9}' | tr -d ' ')

# 避免除零错误
if [ "$MAX_CONN" -eq 0 ]; then
    MAX_CONN=100
fi

USAGE_PERCENT=$((TOTAL * 100 / MAX_CONN))

# 输出统计
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PostgreSQL 连接监控 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "数据库: $DB_NAME"
echo "总连接数: $TOTAL / $MAX_CONN (${USAGE_PERCENT}%)"
echo "  - 活动连接: $ACTIVE"
echo "  - 空闲连接: $IDLE"
echo "  - 事务中空闲: $IDLE_IN_TXN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 告警判断
EXIT_CODE=0

if [ $TOTAL -ge $CRITICAL_THRESHOLD ]; then
    echo -e "${RED}CRITICAL: 连接数达到严重阈值！${NC}"
    log "CRITICAL: 连接数 $TOTAL 超过严重阈值 $CRITICAL_THRESHOLD"

    # 显示TOP 10空闲连接
    echo ""
    echo "TOP 10 最久空闲连接："
    psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "
    SELECT pid,
           usename,
           application_name,
           state,
           EXTRACT(EPOCH FROM (NOW() - state_change))/60 AS idle_minutes
    FROM pg_stat_activity
    WHERE datname='$DB_NAME' AND state='idle'
    ORDER BY state_change
    LIMIT 10;
    "

    EXIT_CODE=2

elif [ $TOTAL -ge $WARNING_THRESHOLD ]; then
    echo -e "${YELLOW}WARNING: 连接数达到警告阈值${NC}"
    log "WARNING: 连接数 $TOTAL 超过警告阈值 $WARNING_THRESHOLD"
    EXIT_CODE=1
else
    echo -e "${GREEN}OK: 连接数正常${NC}"
fi

# 检查长时间空闲的连接
LONG_IDLE=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -t -c "
SELECT count(*)
FROM pg_stat_activity
WHERE datname='$DB_NAME'
  AND state='idle'
  AND state_change < NOW() - INTERVAL '30 minutes';
")

if [ "$LONG_IDLE" -gt 10 ]; then
    echo -e "${YELLOW}WARNING: 发现 $LONG_IDLE 个超过30分钟的空闲连接${NC}"
    echo "建议运行: ./scripts/cleanup-idle-connections.sh"
    log "WARNING: $LONG_IDLE 个长时间空闲连接需要清理"
fi

exit $EXIT_CODE
