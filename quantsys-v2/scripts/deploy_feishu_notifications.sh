#!/bin/bash
#
# V13策略飞书通知系统部署脚本
#
# 功能：
# 1. 检查环境配置
# 2. 测试飞书通知功能
# 3. 安装定时任务
# 4. 启动观察期监控
#

set -e

echo "=========================================="
echo "V13策略飞书通知系统部署"
echo "=========================================="

# 项目根目录
PROJECT_ROOT="/Users/mac/Documents/ai/pi-investment/quantsys-v2"
cd "$PROJECT_ROOT"

# 1. 检查Python环境
echo ""
echo "步骤1: 检查Python环境"
echo "----------------------------------------"

if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3"
    exit 1
fi

PYTHON_PATH=$(which python3)
echo "✅ Python路径: $PYTHON_PATH"

# 检查Python版本
PYTHON_VERSION=$(python3 --version)
echo "✅ Python版本: $PYTHON_VERSION"

# 2. 检查环境变量
echo ""
echo "步骤2: 检查飞书Webhook配置"
echo "----------------------------------------"

if [ -z "$FEISHU_WEBHOOK_URL" ]; then
    echo "⚠️  未配置FEISHU_WEBHOOK_URL环境变量"
    echo ""
    echo "请先设置环境变量："
    echo "  export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx'"
    echo ""
    echo "或者在 ~/.zshrc 或 ~/.bashrc 中添加："
    echo "  export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx'"
    echo ""
    read -p "现在是否要设置环境变量？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "请输入Webhook URL: " webhook_url
        export FEISHU_WEBHOOK_URL="$webhook_url"
        echo "✅ 环境变量已设置（仅本次会话有效）"
    else
        echo "❌ 跳过部署"
        exit 1
    fi
else
    echo "✅ Webhook已配置: ${FEISHU_WEBHOOK_URL:0:50}..."
fi

# 3. 创建日志目录
echo ""
echo "步骤3: 创建日志目录"
echo "----------------------------------------"

mkdir -p live_trading/logs
echo "✅ 日志目录创建完成: $PROJECT_ROOT/live_trading/logs"

# 4. 测试飞书通知
echo ""
echo "步骤4: 测试飞书通知功能"
echo "----------------------------------------"

read -p "是否运行测试？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 scripts/test_feishu_notification.py --auto

    if [ $? -eq 0 ]; then
        echo "✅ 飞书通知测试通过"
    else
        echo "❌ 飞书通知测试失败"
        exit 1
    fi
else
    echo "⏭  跳过测试"
fi

# 5. 生成crontab配置
echo ""
echo "步骤5: 生成定时任务配置"
echo "----------------------------------------"

CRONTAB_FILE="/tmp/v13_crontab_$$.txt"

cat > "$CRONTAB_FILE" << EOF
# V13策略定时任务（由部署脚本生成）
# 生成时间: $(date)

# 环境变量
FEISHU_WEBHOOK_URL=$FEISHU_WEBHOOK_URL

# V13调仓任务（交易日 14:25）
25 14 * * 1-5 cd $PROJECT_ROOT && $PYTHON_PATH infrastructure/jobs/v13_trading_job.py >> live_trading/logs/v13_trading.log 2>&1

# 验证通知任务（交易日 15:30）
30 15 * * 1-5 cd $PROJECT_ROOT && $PYTHON_PATH infrastructure/jobs/verification_job.py >> live_trading/logs/verification.log 2>&1

# 风险检查任务（交易日 16:00）
0 16 * * 1-5 cd $PROJECT_ROOT && $PYTHON_PATH infrastructure/jobs/risk_check_job.py >> live_trading/logs/risk_check.log 2>&1

# 周报任务（每周一 09:00）
0 9 * * 1 cd $PROJECT_ROOT && $PYTHON_PATH infrastructure/jobs/weekly_report_job.py >> live_trading/logs/weekly_report.log 2>&1
EOF

echo "✅ 定时任务配置已生成: $CRONTAB_FILE"
echo ""
cat "$CRONTAB_FILE"

# 6. 安装定时任务
echo ""
echo "步骤6: 安装定时任务"
echo "----------------------------------------"

read -p "是否安装到crontab？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 备份现有crontab
    if crontab -l > /dev/null 2>&1; then
        BACKUP_FILE="/tmp/crontab_backup_$$.txt"
        crontab -l > "$BACKUP_FILE"
        echo "✅ 已备份现有crontab: $BACKUP_FILE"
    fi

    # 添加新任务
    (crontab -l 2>/dev/null || true; cat "$CRONTAB_FILE") | crontab -

    echo "✅ 定时任务安装完成"
    echo ""
    echo "已安装的定时任务："
    crontab -l | grep -A 10 "V13策略定时任务"
else
    echo "⏭  跳过安装"
    echo ""
    echo "手动安装方法："
    echo "  1. 运行: crontab -e"
    echo "  2. 将 $CRONTAB_FILE 的内容复制进去"
    echo "  3. 保存退出"
fi

# 7. 完成
echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "📊 观察期已启动，系统将自动："
echo "  • 每个交易日 14:25 检查调仓"
echo "  • 调仓后发送飞书通知"
echo "  • 5天后验证预测准确性"
echo "  • 每天 16:00 检查风险"
echo "  • 每周一 09:00 发送周报"
echo ""
echo "📝 查看日志："
echo "  tail -f $PROJECT_ROOT/live_trading/logs/v13_trading.log"
echo "  tail -f $PROJECT_ROOT/live_trading/logs/verification.log"
echo "  tail -f $PROJECT_ROOT/live_trading/logs/risk_check.log"
echo "  tail -f $PROJECT_ROOT/live_trading/logs/weekly_report.log"
echo ""
echo "🔧 管理定时任务："
echo "  查看: crontab -l"
echo "  编辑: crontab -e"
echo "  删除: crontab -r"
echo ""
