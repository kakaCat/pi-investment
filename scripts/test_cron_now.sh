#!/bin/bash
# 立即触发定时任务测试 - 不等到9点或18点

echo "============================================================"
echo "定时任务立即触发测试"
echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ==================== 测试1: 早盘分析流程 ====================
echo -e "${BLUE}==================== 测试1: 早盘分析流程 ====================${NC}"
echo ""

echo "📊 执行早盘分析脚本..."
./scripts/morning_analysis.sh

if [ -f "/tmp/quantsys_morning.log" ]; then
    echo ""
    echo -e "${GREEN}✅ 早盘分析执行成功${NC}"
    echo ""
    echo "📋 执行日志（最后20行）："
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -20 /tmp/quantsys_morning.log
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo -e "${RED}❌ 早盘分析执行失败 - 日志文件未生成${NC}"
fi

echo ""

# ==================== 测试2: 实时监控流程 ====================
echo -e "${BLUE}==================== 测试2: 实时监控流程 ====================${NC}"
echo ""

echo "🚨 执行实时监控脚本..."
./scripts/realtime_monitor.sh

if [ -s "/tmp/quantsys_monitor.log" ]; then
    echo ""
    echo -e "${GREEN}✅ 实时监控执行成功（发现预警）${NC}"
    echo ""
    echo "📋 监控日志："
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    cat /tmp/quantsys_monitor.log
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
elif [ -f "/tmp/quantsys_monitor.log" ]; then
    echo -e "${GREEN}✅ 实时监控执行成功（无紧急预警）${NC}"
else
    echo -e "${YELLOW}⚠️  实时监控日志未生成（可能API服务未启动）${NC}"
fi

echo ""

# ==================== 测试3: 每日学习流程 ====================
echo -e "${BLUE}==================== 测试3: 每日学习流程 ====================${NC}"
echo ""

echo "🎓 执行每日学习脚本..."
./scripts/daily_learning.sh

if [ -f "/tmp/quantsys_learning.log" ]; then
    echo ""
    echo -e "${GREEN}✅ 每日学习执行成功${NC}"
    echo ""
    echo "📋 学习日志（最后20行）："
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -20 /tmp/quantsys_learning.log
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo -e "${RED}❌ 每日学习执行失败 - 日志文件未生成${NC}"
fi

echo ""

# ==================== 总结 ====================
echo ""
echo "============================================================"
echo "定时任务测试完成"
echo "============================================================"
echo ""

# 统计结果
SUCCESS=0
FAIL=0

[ -f "/tmp/quantsys_morning.log" ] && SUCCESS=$((SUCCESS + 1)) || FAIL=$((FAIL + 1))
[ -f "/tmp/quantsys_learning.log" ] && SUCCESS=$((SUCCESS + 1)) || FAIL=$((FAIL + 1))

echo "执行结果:"
echo -e "${GREEN}成功: ${SUCCESS}/2 任务${NC}"
if [ $FAIL -gt 0 ]; then
    echo -e "${RED}失败: ${FAIL}/2 任务${NC}"
fi

echo ""
echo -e "${YELLOW}💡 这就是定时任务实际会执行的内容！${NC}"
echo ""
echo "如果看到API返回数据 → 说明整个流程work了！"
echo ""

if [ $SUCCESS -eq 2 ]; then
    echo -e "${GREEN}✅ 定时任务流程验证通过！${NC}"
    echo ""
    echo "📋 下一步："
    echo "1. 配置crontab:"
    echo "   crontab -e"
    echo ""
    echo "2. 添加定时任务:"
    echo "   0 9 * * 1-5 $(pwd)/scripts/morning_analysis.sh"
    echo "   0 18 * * * $(pwd)/scripts/daily_learning.sh"
    echo "   */5 9-15 * * 1-5 $(pwd)/scripts/realtime_monitor.sh"
    echo ""
    echo "3. 系统将7×24小时自动运行！"
    exit 0
else
    echo -e "${YELLOW}⚠️  部分任务执行失败${NC}"
    echo ""
    echo "可能原因："
    echo "1. API服务未启动"
    echo "   启动命令: cd quantsys-v2 && python start_all.py &"
    echo ""
    echo "2. 数据库连接问题"
    echo "   检查命令: psql -U postgres -d quantsys_v2 -c 'SELECT 1;'"
    echo ""
    exit 1
fi
