#!/bin/bash
# 模型版本切换工具
# 用于在V13、V14原版、V14 P0之间快速切换

MODELS_DIR="live_trading/models"

show_current() {
    if [ -f "$MODELS_DIR/CURRENT_VERSION.txt" ]; then
        cat "$MODELS_DIR/CURRENT_VERSION.txt"
    else
        echo "未找到版本信息文件"
    fi
}

switch_to_v13() {
    echo "切换到V13模型..."
    if [ -f "$MODELS_DIR/v13_backup.json" ]; then
        cp "$MODELS_DIR/v13_backup.json" "$MODELS_DIR/v13_model.json"
        cp "$MODELS_DIR/v13_factors.json" "$MODELS_DIR/valid_factors.json" 2>/dev/null
        echo "v13" > "$MODELS_DIR/CURRENT_VERSION.txt"
        echo "✓ 已切换到V13模型"
    else
        echo "✗ V13备份文件不存在"
    fi
}

switch_to_v14_original() {
    echo "切换到V14原版模型..."
    if [ -f "$MODELS_DIR/v14_original_backup.json" ]; then
        cp "$MODELS_DIR/v14_original_backup.json" "$MODELS_DIR/v13_model.json"
        cp "$MODELS_DIR/v14_original_factors.json" "$MODELS_DIR/valid_factors.json"
        echo "v14_original" > "$MODELS_DIR/CURRENT_VERSION.txt"
        echo "✓ 已切换到V14原版模型"
        echo "⚠️  注意: V14原版样本量仅160条，不推荐实盘使用"
    else
        echo "✗ V14原版备份文件不存在"
    fi
}

switch_to_v14_p0() {
    echo "切换到V14 P0优化版..."
    if [ -f "$MODELS_DIR/v14_p0_model.json" ]; then
        cp "$MODELS_DIR/v14_p0_model.json" "$MODELS_DIR/v13_model.json"
        cp "$MODELS_DIR/v14_p0_valid_factors.json" "$MODELS_DIR/valid_factors.json"
        cat > "$MODELS_DIR/CURRENT_VERSION.txt" <<EOF
当前模型版本: V14 P0 优化版
切换时间: $(date '+%Y-%m-%d %H:%M:%S')
训练样本: 233,456条
有效因子: 75个
预期年化: 41.2% (回测)
预期IC/IR: 0.065 / 2.5
EOF
        echo "✓ 已切换到V14 P0优化版"
    else
        echo "✗ V14 P0模型文件不存在"
    fi
}

list_models() {
    echo ""
    echo "可用模型列表:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [ -f "$MODELS_DIR/v13_backup.json" ]; then
        echo "✓ V13 (原始)"
        echo "  年化: 15.0%, IC: 0.025, IR: 0.48"
    fi

    if [ -f "$MODELS_DIR/v14_original_backup.json" ]; then
        echo "✓ V14原版"
        echo "  年化: 21.3%, IC: 0.040, IR: 1.37"
        echo "  ⚠️  样本量仅160条，不推荐实盘"
    fi

    if [ -f "$MODELS_DIR/v14_p0_model.json" ]; then
        echo "✓ V14 P0优化版 (推荐)"
        echo "  年化: 41.2%, IC: 0.065, IR: 2.5"
        echo "  样本量: 233,456条"
    fi

    echo ""
}

# 主菜单
case "$1" in
    current)
        show_current
        ;;
    v13)
        switch_to_v13
        ;;
    v14)
        switch_to_v14_original
        ;;
    p0|v14_p0)
        switch_to_v14_p0
        ;;
    list)
        list_models
        ;;
    *)
        echo "模型版本切换工具"
        echo ""
        echo "用法: $0 {current|v13|v14|p0|list}"
        echo ""
        echo "命令:"
        echo "  current  - 显示当前使用的模型版本"
        echo "  v13      - 切换到V13模型"
        echo "  v14      - 切换到V14原版模型"
        echo "  p0       - 切换到V14 P0优化版 (推荐)"
        echo "  list     - 列出所有可用模型"
        echo ""
        echo "示例:"
        echo "  $0 p0       # 切换到V14 P0优化版"
        echo "  $0 current  # 查看当前版本"
        exit 1
        ;;
esac
