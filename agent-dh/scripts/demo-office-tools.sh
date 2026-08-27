#!/bin/bash
# RFC 010 办公室工具演示脚本

echo "🎬 RFC 010 办公室工具演示"
echo "=================================="
echo ""

# 演示前准备：注册几个测试窗口
echo "📋 准备演示环境..."
echo ""

# 清理旧的测试窗口
echo "1. 清理旧测试窗口..."
for window in "w-demo-investor" "w-demo-researcher" "w-demo-trader"; do
    curl -s -X POST http://localhost:8080/api/v1/registry/agents/unregister \
      -H "Content-Type: application/json" \
      -d "{\"agent_id\": \"$window\"}" > /dev/null 2>&1
done
echo "   ✅ 清理完成"
echo ""

# 注册演示窗口
echo "2. 注册演示窗口..."

# 窗口 1: 投资脑（空闲）
curl -s -X POST http://localhost:8080/api/v1/registry/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "w-demo-investor",
    "type": "investor",
    "name": "投资脑·演示",
    "instance": "investment",
    "session_id": "session-demo-inv",
    "status": "idle",
    "host": "127.0.0.1",
    "port": 13080,
    "pid": '$$',
    "capabilities": ["trading", "analysis"],
    "metadata": {"demo": true}
  }' > /dev/null

echo "   ✅ w-demo-investor - 投资脑·演示（空闲）"

# 窗口 2: 研究员（工作中）
curl -s -X POST http://localhost:8080/api/v1/registry/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "w-demo-researcher",
    "type": "researcher",
    "name": "研究员·演示",
    "instance": "investment",
    "session_id": "session-demo-res",
    "status": "active",
    "host": "127.0.0.1",
    "port": 13080,
    "pid": '$$',
    "capabilities": ["research", "backtesting"],
    "metadata": {"demo": true, "task": "分析白酒板块"}
  }' > /dev/null

echo "   ✅ w-demo-researcher - 研究员·演示（工作中）"

# 窗口 3: 交易员（空闲）
curl -s -X POST http://localhost:8080/api/v1/registry/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "w-demo-trader",
    "type": "trader",
    "name": "交易员·演示",
    "instance": "investment",
    "session_id": "session-demo-trader",
    "status": "idle",
    "host": "127.0.0.1",
    "port": 13080,
    "pid": '$$',
    "capabilities": ["execution"],
    "metadata": {"demo": true}
  }' > /dev/null

echo "   ✅ w-demo-trader - 交易员·演示（空闲）"
echo ""

sleep 1

echo "=================================="
echo "🎯 工具演示开始"
echo "=================================="
echo ""

# ===== 工具 1: office_roster =====
echo "📊 工具 1: office_roster - 查看办公室花名册"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💬 使用场景: 派单前先看看谁在线、谁有空"
echo ""
echo "🔧 命令: office_roster()"
echo ""
echo "📤 输出:"
echo ""

curl -s http://localhost:8080/api/v1/registry/agents/available | \
  jq -r '.[] | select(.metadata.demo == true) | 
    "### " + (if .status == "idle" then "🟢" else "🔵" end) + " " + .agent_id + " - " + .name + "\n" +
    "- **角色**: " + .agent_type + "\n" +
    "- **实例**: " + .instance + "\n" +
    "- **状态**: " + .status + 
    (if .metadata.task then "\n- **当前任务**: " + .metadata.task else "" end) + "\n"'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 工具 2: assign_task =====
echo "📮 工具 2: assign_task - 派发任务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💬 使用场景: 向空闲窗口派发新任务"
echo ""
echo "🔧 命令: assign_task("
echo "    window='w-demo-trader',"
echo "    task='执行买入订单：600519 买入 1000 股',"
echo "    note='市价单，今日完成'"
echo ")"
echo ""
echo "📤 模拟输出:"
echo ""
echo '{
  "dispatched": true,
  "window": "w-demo-trader",
  "message": "任务已派发到交易员·演示"
}'
echo ""
echo "📬 交易员收到的消息:"
echo ""
echo "【办公室派单】来自窗口 w-demo-investor（investor）："
echo ""
echo "任务：执行买入订单：600519 买入 1000 股"
echo "备注：市价单，今日完成"
echo ""
echo "完成后请 window_update 更新你的状态，并把结果写入 memory（namespace=decision）供溯源。"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 工具 3: window_update =====
echo "✏️  工具 3: window_update - 更新状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💬 使用场景: 窗口自报状态、任务、技能"
echo ""
echo "🔧 命令: window_update("
echo "    status='active',"
echo "    task='执行买入订单：600519',"
echo "    skills=['execution', 'order-management'],"
echo "    note='订单已提交，等待成交'"
echo ")"
echo ""
echo "📤 输出:"
echo ""
echo '{
  "window": "w-demo-trader",
  "updated": true,
  "queued": false
}'
echo ""
echo "💡 说明: 办公室现在知道该窗口正在工作中"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 工具 4: window_message =====
echo "💬 工具 4: window_message - 窗口通信"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💬 使用场景: 窗口间协作、询问进展"
echo ""
echo "🔧 命令: window_message("
echo "    window='w-demo-trader',"
echo "    message='订单执行完成了吗？'"
echo ")"
echo ""
echo "📤 输出:"
echo ""
echo '{
  "sent": true,
  "delivered": true,
  "to": "w-demo-trader"
}'
echo ""
echo "📬 交易员收到的消息:"
echo ""
echo "【窗口消息】来自 w-demo-investor："
echo ""
echo "订单执行完成了吗？"
echo ""
echo "回信方式：window_message(window='w-demo-investor', message='...')"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 工具 5: hire_window =====
echo "👔 工具 5: hire_window - 招募新窗口"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💬 使用场景: 需要更多人手时招募新窗口"
echo ""
echo "🔧 命令: hire_window("
echo "    task='监控白酒板块实时动态',"
echo "    skills=['market-monitoring', 'alert'],"
echo "    model='deepseek-v4-flash'"
echo ")"
echo ""
echo "📤 模拟输出:"
echo ""
echo '{
  "hired": true,
  "window": "w-abc123456",
  "session_id": "session-abc123456",
  "message": "新窗口已创建并派发任务"
}'
echo ""
echo "📬 新窗口收到的消息:"
echo ""
echo "【入职任务】你被办公室招为新窗口 w-abc123456（角色：investor）。"
echo ""
echo "任务：监控白酒板块实时动态"
echo ""
echo "要求：遵守交易宪法（提示词中的 constitution 段）；"
echo "开工前先 window_update 自报状态；"
echo "完成后把结论写入 memory（namespace=decision）并 window_update 标记 done。"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 工具 6: window_list =====
echo "📋 工具 6: window_list - 列出所有窗口"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💬 使用场景: 查看所有窗口（包括离线的）"
echo ""
echo "🔧 命令: window_list()"
echo ""
echo "📤 输出（演示窗口）:"
echo ""

curl -s http://localhost:8080/api/v1/registry/agents/available | \
  jq -r '.[] | select(.metadata.demo == true) | 
    "- " + .agent_id + " [" + .status + "] - " + .name'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 协作场景演示 =====
echo "🎭 协作场景演示"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📖 场景: 投资脑派单 → 研究员执行 → 汇报结果"
echo ""
echo "1️⃣  投资脑查看花名册"
echo "   → office_roster()"
echo "   → 发现研究员正在分析白酒板块"
echo ""
echo "2️⃣  投资脑发送消息询问"
echo "   → window_message(window='w-demo-researcher', message='白酒分析完成了吗？')"
echo ""
echo "3️⃣  研究员回复"
echo "   → window_message(window='w-demo-investor', message='已完成，建议关注贵州茅台')"
echo ""
echo "4️⃣  投资脑派单给交易员"
echo "   → assign_task(window='w-demo-trader', task='买入 600519')"
echo ""
echo "5️⃣  交易员更新状态"
echo "   → window_update(status='active', task='执行买入 600519')"
echo ""
echo "6️⃣  交易员完成后汇报"
echo "   → window_update(status='done')"
echo "   → window_message(window='w-demo-investor', message='已完成买入')"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2

# ===== 清理 =====
echo "🧹 清理演示环境..."
for window in "w-demo-investor" "w-demo-researcher" "w-demo-trader"; do
    curl -s -X POST http://localhost:8080/api/v1/registry/agents/unregister \
      -H "Content-Type: application/json" \
      -d "{\"agent_id\": \"$window\"}" > /dev/null
done
echo "   ✅ 演示窗口已注销"
echo ""

echo "=================================="
echo "✅ 演示完成"
echo "=================================="
echo ""
echo "📚 总结:"
echo ""
echo "   1. office_roster   - 查看谁在线、谁有空"
echo "   2. assign_task     - 派发任务到指定窗口"
echo "   3. window_update   - 更新自己的状态"
echo "   4. window_message  - 窗口间发消息"
echo "   5. hire_window     - 招募新窗口"
echo "   6. window_list     - 列出所有窗口"
echo ""
echo "💡 在 DSH Web UI 中，这些工具就像普通函数一样调用"
echo ""
echo "🎯 下一步: 打开 http://localhost:13080 实际体验"
echo ""
