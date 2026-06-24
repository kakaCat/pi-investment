#!/bin/bash
# 飞书 Webhook 配置和测试自动化脚本

echo "🚀 飞书通知配置向导"
echo "===================="
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: 找不到 .env 文件"
    exit 1
fi

echo "📋 当前配置检查:"
echo ""

# 检查 Webhook URL
if grep -q "^FEISHU_WEBHOOK_URL=" .env; then
    echo "✅ FEISHU_WEBHOOK_URL 已配置"
    WEBHOOK_URL=$(grep "^FEISHU_WEBHOOK_URL=" .env | cut -d'=' -f2)
    if [ ! -z "$WEBHOOK_URL" ] && [ "$WEBHOOK_URL" != "https://open.feishu.cn/open-apis/bot/v2/hook/xxx" ]; then
        echo "   URL: ${WEBHOOK_URL:0:50}..."
        HAS_WEBHOOK=true
    else
        echo "   ⚠️ URL 为空或为示例值"
        HAS_WEBHOOK=false
    fi
else
    echo "❌ FEISHU_WEBHOOK_URL 未配置"
    HAS_WEBHOOK=false
fi

echo ""

# 检查 Chat ID
if grep -q "^FEISHU_CHAT_ID=" .env; then
    echo "✅ FEISHU_CHAT_ID 已配置"
    CHAT_ID=$(grep "^FEISHU_CHAT_ID=" .env | cut -d'=' -f2)
    if [ ! -z "$CHAT_ID" ] && [ "$CHAT_ID" != "oc_xxx" ]; then
        echo "   ID: $CHAT_ID"
        HAS_CHAT_ID=true
    else
        echo "   ⚠️ ID 为空或为示例值"
        HAS_CHAT_ID=false
    fi
else
    echo "❌ FEISHU_CHAT_ID 未配置"
    HAS_CHAT_ID=false
fi

echo ""
echo "===================="
echo ""

# 如果都没配置，显示帮助
if [ "$HAS_WEBHOOK" = false ] && [ "$HAS_CHAT_ID" = false ]; then
    echo "📝 配置说明:"
    echo ""
    echo "方式 1: Webhook URL (推荐)"
    echo "----------------------------"
    echo "1. 打开飞书群 → 设置 → 群机器人"
    echo "2. 添加自定义机器人"
    echo "3. 复制 Webhook URL"
    echo "4. 添加到 .env 文件:"
    echo ""
    echo "   FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook"
    echo ""
    echo "方式 2: Chat ID"
    echo "----------------------------"
    echo "1. 在飞书群设置中查看群 ID"
    echo "2. 添加到 .env 文件:"
    echo ""
    echo "   FEISHU_CHAT_ID=oc_你的群id"
    echo ""
    echo "详细说明请查看: docs/FEISHU_WEBHOOK_SETUP.md"
    echo ""
    exit 0
fi

# 如果已配置，询问是否测试
echo "🧪 是否执行发送测试?"
echo ""
echo "可用的测试:"
if [ "$HAS_WEBHOOK" = true ]; then
    echo "  1. Webhook 模式测试 (test-feishu-integration.ts)"
fi
if [ "$HAS_CHAT_ID" = true ]; then
    echo "  2. Chat ID 模式测试 (test-feishu-real-send.ts)"
fi
echo "  3. 服务集成测试 (不发送真实消息)"
echo "  4. 退出"
echo ""
echo -n "请选择 (1-4): "

# 在实际交互中，这里需要用户输入
# 现在先自动选择服务集成测试
echo "3"
echo ""
echo "执行服务集成测试..."
echo ""

npx tsx src/scripts/test-feishu-service-integration.ts
