#!/bin/bash
# RFC 010 快速启动指南

set -e

echo "🚀 RFC 010 Phase 1 - 快速启动指南"
echo "=================================="
echo ""

# 检查目录
AGENT_OS_DIR="/Users/yunpeng/pi-investment/agent-os"
# 2026-09-13：旧布局 ~/.dsh/profiles/investment 已随遗留清理删除；现役为项目内托管布局，
# 从脚本自身位置反推，不再硬编码 home（同 scripts/restart-with-build.sh 的做法）。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DSH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/.dsh-home/profiles/investment"

if [ ! -d "$AGENT_OS_DIR" ]; then
    echo "❌ Agent OS 目录不存在: $AGENT_OS_DIR"
    exit 1
fi

if [ ! -d "$DSH_DIR" ]; then
    echo "❌ DSH 目录不存在: $DSH_DIR"
    exit 1
fi

echo "✅ 目录检查通过"
echo ""

# 1. 启动 Agent OS
echo "1️⃣  启动 Agent OS..."
cd "$AGENT_OS_DIR"
if ./agent-os.sh status | grep -q "运行中"; then
    echo "   ℹ️  Agent OS 已在运行"
else
    ./agent-os.sh start
    if [ $? -ne 0 ]; then
        echo "   ❌ Agent OS 启动失败"
        exit 1
    fi
fi
echo ""

# 2. 检查 DSH
echo "2️⃣  检查 DSH..."
if lsof -i :13080 | grep -q LISTEN; then
    DSH_PID=$(lsof -ti :13080)
    echo "   ✅ DSH 已在运行 (PID: $DSH_PID)"
else
    echo "   ⚠️  DSH 未运行，请手动启动:"
    echo "      $SCRIPT_DIR/start.sh 13080   # 托管布局：profile 目录内没有 start.sh，入口在仓库 scripts/"
fi
echo ""

# 3. 系统诊断
echo "3️⃣  系统诊断..."
DIAG_SCRIPT="/Users/yunpeng/pi-investment/agent-dh/scripts/diagnose-window-registry.sh"
if [ -f "$DIAG_SCRIPT" ]; then
    $DIAG_SCRIPT | grep -E "✅|❌|活跃窗口"
else
    echo "   ⚠️  诊断脚本不存在"
fi
echo ""

# 4. 快速测试
echo "4️⃣  API 快速测试..."
RESPONSE=$(curl -s http://localhost:8080/health)
if echo "$RESPONSE" | grep -q "ok"; then
    echo "   ✅ Agent OS API 正常"
else
    echo "   ❌ Agent OS API 异常"
fi
echo ""

# 5. 使用提示
echo "=================================="
echo "✅ 系统启动完成！"
echo ""
echo "📖 快速使用:"
echo ""
echo "   1. 打开 Web UI: http://localhost:13080"
echo ""
echo "   2. 使用办公室工具:"
echo "      office_roster()                    # 查看花名册"
echo "      assign_task(...)                   # 派发任务"
echo "      hire_window(...)                   # 招募新窗口"
echo ""
echo "   3. 管理 Agent OS:"
echo "      cd $AGENT_OS_DIR"
echo "      ./agent-os.sh status              # 查看状态"
echo "      ./agent-os.sh logs                # 查看日志"
echo "      ./agent-os.sh restart             # 重启"
echo ""
echo "   4. 启动守护进程（可选）:"
echo "      cd $AGENT_OS_DIR"
echo "      nohup ./agent-os-daemon.sh > daemon.log 2>&1 &"
echo ""
echo "📚 完整文档:"
echo "   /Users/yunpeng/pi-investment/agent-dh/docs/work-logs/2026-08/"
echo "   - rfc-010-phase1-final-delivery.md"
echo ""
echo "🎉 享受多窗口协同工作！"
