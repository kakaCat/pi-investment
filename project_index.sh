#!/bin/bash
# Flask → FastAPI 迁移项目 - 文件索引和导航工具

echo "=========================================="
echo "Flask → FastAPI 迁移项目文件索引"
echo "=========================================="
echo ""

# 统计函数
count_files() {
    find $1 -name "$2" 2>/dev/null | wc -l | xargs
}

echo "📁 项目文件统计"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 核心代码文件
echo "1. 核心代码文件:"
echo "   FastAPI 主应用:"
[ -f "adapters/inbound/fastapi_app/main.py" ] && echo "     ✅ main.py"
[ -f "adapters/inbound/fastapi_app/websocket_server.py" ] && echo "     ✅ websocket_server.py"

async_routes=$(count_files "adapters/inbound/fastapi_app/routes" "*_async.py")
echo "   异步路由: $async_routes 个"

echo ""

# 文档文件
echo "2. 项目文档 (10份):"
docs=(
    "ACCEPTANCE.md:验收确认书"
    "PROJECT_SUMMARY.md:项目总结"
    "README_MIGRATION.md:快速导航"
    "QUICKSTART_FASTAPI.md:快速启动"
    "MIGRATION_COMPLETE.md:完成报告"
    "DEPLOYMENT_GUIDE.md:部署指南"
    "VERIFICATION_CHECKLIST.md:验证清单"
    "MIGRATION_PLAN.md:迁移方案"
    "TEST_REPORT.md:测试报告"
    "WORK_SUMMARY.md:工作总结"
)

for doc in "${docs[@]}"; do
    IFS=: read -r file desc <<< "$doc"
    if [ -f "$file" ]; then
        echo "   ✅ $file - $desc"
    else
        echo "   ❌ $file - $desc"
    fi
done

echo ""

# 工具脚本
echo "3. 自动化工具 (7个):"
tools=(
    "check_migration.py:迁移检查"
    "auto_migrate.py:自动生成"
    "cleanup_flask.sh:Flask清理"
    "test_fastapi.sh:FastAPI测试"
    "test_agent_integration.sh:集成测试"
    "quick_benchmark.sh:性能测试"
    "check_project_status.sh:状态检查"
)

for tool in "${tools[@]}"; do
    IFS=: read -r file desc <<< "$tool"
    if [ -f "$file" ]; then
        echo "   ✅ $file - $desc"
    else
        echo "   ❌ $file - $desc"
    fi
done

echo ""

# 其他文件
echo "4. 其他文件:"
[ -f "EXECUTIVE_SUMMARY.txt" ] && echo "   ✅ EXECUTIVE_SUMMARY.txt - 执行摘要"
[ -f "DELIVERY.md" ] && echo "   ✅ DELIVERY.md - 交付简报"
[ -f "SUMMARY.md" ] && echo "   ✅ SUMMARY.md - 简要总结"
[ -f "FINAL_REPORT.md" ] && echo "   ✅ FINAL_REPORT.md - 最终报告"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 快速导航"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔴 新手必读 (按顺序):"
echo "   1. cat EXECUTIVE_SUMMARY.txt     # 5分钟了解全貌"
echo "   2. cat README_MIGRATION.md       # 10分钟上手"
echo "   3. cat ACCEPTANCE.md             # 查看验收结果"
echo ""
echo "🟡 深入了解:"
echo "   4. cat PROJECT_SUMMARY.md        # 完整项目总结"
echo "   5. cat QUICKSTART_FASTAPI.md     # 快速启动指南"
echo ""
echo "🟢 进阶参考:"
echo "   6. cat DEPLOYMENT_GUIDE.md       # 生产部署"
echo "   7. cat VERIFICATION_CHECKLIST.md # 验证清单"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛠️ 常用命令"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "查看服务:"
echo "  curl http://127.0.0.1:5001/health"
echo "  open http://127.0.0.1:5001/docs"
echo ""
echo "运行测试:"
echo "  python check_migration.py          # 检查迁移进度"
echo "  bash check_project_status.sh       # 检查项目状态"
echo "  bash quick_benchmark.sh            # 性能测试"
echo ""
echo "查看日志:"
echo "  tail -f /tmp/quantsys_fastapi.log"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "提示: 运行 'cat EXECUTIVE_SUMMARY.txt' 查看项目摘要"
echo ""
