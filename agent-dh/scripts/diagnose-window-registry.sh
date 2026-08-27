#!/bin/bash
# RFC 010 诊断脚本 - 检查窗口注册系统状态

echo "=== RFC 010 Window Registry 诊断 ==="
echo ""
echo "时间: $(date)"
echo ""

echo "1. 检查 Agent OS 状态..."
if lsof -i :8080 | grep -q LISTEN; then
    echo "✅ Agent OS 运行中 (port 8080)"
    AGENT_OS_PID=$(lsof -ti :8080)
    echo "   PID: $AGENT_OS_PID"
else
    echo "❌ Agent OS 未运行"
    exit 1
fi
echo ""

echo "2. 检查 DSH 状态..."
if lsof -i :13080 | grep -q LISTEN; then
    echo "✅ DSH 运行中 (port 13080)"
    DSH_PID=$(lsof -ti :13080)
    echo "   PID: $DSH_PID"
else
    echo "❌ DSH 未运行"
    exit 1
fi
echo ""

echo "3. 测试 Agent OS Registry API..."
RESPONSE=$(curl -s -w "%{http_code}" http://localhost:8080/api/v1/registry/agents/available -o /tmp/registry_test.json)
if [ "$RESPONSE" = "200" ]; then
    echo "✅ API 响应正常"
    TOTAL=$(jq 'length' /tmp/registry_test.json)
    ACTIVE=$(jq '[.[] | select(.status == "active" or .status == "idle")] | length' /tmp/registry_test.json)
    echo "   总窗口数: $TOTAL"
    echo "   活跃窗口: $ACTIVE"
else
    echo "❌ API 响应失败 (HTTP $RESPONSE)"
fi
echo ""

echo "4. 查看最近注册的窗口..."
echo "   (过去1小时内注册的窗口)"
CUTOFF=$(date -u -v-1H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "2026-08-27T17:00:00Z")
jq --arg cutoff "$CUTOFF" '.[] | select(.registered_at > $cutoff) | {agent_id, name, status, registered_at}' /tmp/registry_test.json || echo "   无最近注册的窗口"
echo ""

echo "5. 查看 DSH 相关的窗口..."
jq '.[] | select(.agent_id | startswith("w-") or contains("dsh")) | {agent_id, name, status, registered_at, last_heartbeat_at}' /tmp/registry_test.json || echo "   无 DSH 窗口"
echo ""

echo "6. 检查心跳活跃度..."
echo "   (最近5分钟内有心跳的窗口)"
HEARTBEAT_CUTOFF=$(date -u -v-5M +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d '5 minutes ago' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "2026-08-27T17:50:00Z")
jq --arg cutoff "$HEARTBEAT_CUTOFF" '[.[] | select(.last_heartbeat_at > $cutoff)] | length' /tmp/registry_test.json
echo ""

echo "=== 诊断完成 ==="
echo ""
echo "💡 提示："
echo "   - 如果没有 DSH 窗口注册，可能是 lifecycle 插件未触发"
echo "   - 尝试通过 Web UI 发送一条消息，触发 agent 创建"
echo "   - 或者在 DSH 控制台中手动调用 window_update 工具"
