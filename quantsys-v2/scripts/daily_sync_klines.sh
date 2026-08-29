#!/bin/bash
# 每日K线同步脚本
# 用途：由 Agent OS reminder 调用，同步当日所有活跃股票的K线数据
# 调用方式：bash quantsys-v2/scripts/daily_sync_klines.sh [date]

set -e  # 遇错即停

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 参数：同步日期（可选，默认昨日，因为当日数据通常在收盘后才可用）
SYNC_DATE="${1:-$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d 'yesterday' +%Y-%m-%d)}"

echo "=========================================="
echo "每日K线同步"
echo "同步日期: $SYNC_DATE"
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 激活 Python 环境
if [ -f "$PROJECT_ROOT/activate-py313.sh" ]; then
    echo "激活 Python 3.13 环境..."
    source "$PROJECT_ROOT/activate-py313.sh"
else
    echo "ERROR: activate-py313.sh not found"
    exit 1
fi

# 检查数据库连接
echo "检查数据库连接..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from infrastructure.persistence.orm import get_session
try:
    session = get_session()
    session.execute('SELECT 1')
    print('✓ 数据库连接正常')
except Exception as e:
    print(f'✗ 数据库连接失败: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "ERROR: 数据库连接失败，退出"
    exit 1
fi

# 执行同步（调用 Python 脚本）
echo "----------------------------------------"
echo "开始同步 K线数据..."
python3 "$SCRIPT_DIR/sync_daily_klines_incremental.py" --date "$SYNC_DATE"

EXIT_CODE=$?

echo "----------------------------------------"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ K线同步完成"
    echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
else
    echo "❌ K线同步失败，退出码: $EXIT_CODE"
fi
echo "=========================================="

exit $EXIT_CODE
