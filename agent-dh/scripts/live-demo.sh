#!/bin/bash
# RFC 010 真实工具演示脚本（实际调用 DSH 工具）

echo "🎬 RFC 010 办公室工具真实演示"
echo "=================================="
echo ""
echo "⚠️  这个演示需要在 DSH Web UI (http://localhost:13080) 中执行"
echo "    因为工具必须在 agent 会话上下文中调用"
echo ""
echo "📋 当前 Agent OS 注册表状态："
echo ""

# 查询当前注册的窗口
RESPONSE=$(curl -s http://localhost:8080/api/v1/registry/agents/available)

if [ $? -eq 0 ]; then
    echo "$RESPONSE" | jq -r '.[] | 
        if .status == "timeout" then empty else
            "### " + (if .status == "idle" then "🟢" else "🔵" end) + " " + .agent_id + 
            "\n- 名称: " + (.name // "N/A") + 
            "\n- 角色: " + .agent_type + 
            "\n- 状态: " + .status + 
            "\n- 注册: " + .registered_at +
            "\n- 心跳: " + .last_heartbeat_at + "\n"
        end'
    
    ACTIVE_COUNT=$(echo "$RESPONSE" | jq '[.[] | select(.status != "timeout")] | length')
    TIMEOUT_COUNT=$(echo "$RESPONSE" | jq '[.[] | select(.status == "timeout")] | length')
    
    echo ""
    echo "📊 统计: 在线 $ACTIVE_COUNT 个，超时 $TIMEOUT_COUNT 个"
else
    echo "❌ 无法连接 Agent OS (http://localhost:8080)"
    exit 1
fi

echo ""
echo "=================================="
echo "🎯 如何验收工具"
echo "=================================="
echo ""
echo "请在 http://localhost:13080 的对话框中输入以下命令："
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "工具 1: office_roster - 查看花名册"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "调用 office_roster 工具"
echo ""
echo "预期输出："
echo "- 看到当前注册的所有窗口"
echo "- 包含名称、角色、状态、技能等信息"
echo "- Markdown 格式，易读"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "工具 2: window_update - 更新自己的状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "调用 window_update 工具，参数："
echo "  status: 'active'"
echo "  task: '测试 RFC 010 工具'"
echo "  skills: ['testing', 'validation']"
echo "  note: '验收办公室工具'"
echo ""
echo "预期输出："
echo "- 返回 {updated: true, queued: false}"
echo "- 再次调用 office_roster 应该看到状态已更新"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "工具 3: window_list - 列出所有窗口"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "调用 window_list 工具"
echo ""
echo "预期输出："
echo "- 返回所有窗口的简要信息"
echo "- 包括离线窗口（超时的）"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "工具 4-6: 需要多窗口场景"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "以下工具需要多个窗口才能演示："
echo ""
echo "4. assign_task(window='w-xxx', task='...')"
echo "   → 需要另一个窗口接收任务"
echo ""
echo "5. window_message(window='w-xxx', message='...')"
echo "   → 需要另一个窗口接收消息"
echo ""
echo "6. hire_window(task='...', skills=[...])"
echo "   → 会创建新窗口（需要 DSH 支持）"
echo ""
echo "💡 建议："
echo "   打开另一个浏览器标签页 → http://localhost:13080"
echo "   这会创建第二个 agent 会话窗口"
echo "   然后在第一个窗口中 assign_task 或 window_message 给第二个"
echo ""
echo "=================================="
echo "✅ 验收检查清单"
echo "=================================="
echo ""
echo "[ ] 1. office_roster 能看到当前窗口"
echo "[ ] 2. window_update 能更新自己的状态"
echo "[ ] 3. office_roster 再次查询能看到更新"
echo "[ ] 4. window_list 返回所有窗口（包括超时的）"
echo "[ ] 5. 创建第二个窗口后能互相通信"
echo ""
echo "=================================="
echo "🔍 验证后端数据"
echo "=================================="
echo ""
echo "执行以下命令验证数据库："
echo ""
echo "psql -d quant_investment -c \"SELECT agent_id, name, agent_type, status, registered_at FROM agents WHERE status != 'timeout' ORDER BY registered_at DESC LIMIT 5;\""
echo ""
