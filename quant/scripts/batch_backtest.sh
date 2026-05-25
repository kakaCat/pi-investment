#!/bin/bash
# 快速回测脚本 - 批量回测多只股票

QUANT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$QUANT_DIR"

echo "=========================================="
echo "批量策略回测"
echo "=========================================="
echo ""

# 默认参数
DAYS=60
CAPITAL=1000000

# 股票列表（从数据库自动获取）
STOCKS=(
    "000001" "000002" "000004" "000006" "000007" "000008" "000063"
    "000333" "000425" "000651" "002011" "002025" "002050" "002179"
    "002475" "002714" "300124" "300442" "301029" "600036" "600118"
    "600276" "600391" "600584" "600600" "600699" "600900" "600941"
    "601088" "601138" "601288" "601899" "603662" "603986" "603993"
    "688012" "688120" "688169" "688686" "688777" "688981"
)

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --days)
            DAYS="$2"
            shift 2
            ;;
        --capital)
            CAPITAL="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--days N] [--capital AMOUNT]"
            exit 1
            ;;
    esac
done

echo "回测参数:"
echo "  回测天数: $DAYS"
echo "  初始资金: $CAPITAL"
echo ""

# 回测每只股票
for symbol in "${STOCKS[@]}"; do
    echo "----------------------------------------"
    echo "回测股票: $symbol"
    echo "----------------------------------------"

    python scripts/weekly_backtest.py \
        --symbol "$symbol" \
        --days "$DAYS" \
        --capital "$CAPITAL"

    if [ $? -eq 0 ]; then
        echo "✓ $symbol 回测完成"
    else
        echo "✗ $symbol 回测失败"
    fi
    echo ""
done

echo "=========================================="
echo "批量回测完成"
echo "=========================================="
echo ""
echo "查看报告:"
echo "  ls -lh .pi-invest/backtest_report_*.md"
echo "  ls -lh .pi-invest/backtest_report_*.json"
