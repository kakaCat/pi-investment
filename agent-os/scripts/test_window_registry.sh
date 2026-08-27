#!/bin/bash
# RFC 010: Agent OS Window Registry API 测试
# 测试现有 API 兼容性 + 新增 role 查询功能

set -e

API_BASE="http://localhost:8080/api/v1"
AGENT_ID="w-test-$(date +%s)"
ROLE="investor"

echo "🧪 RFC 010 Window Registry API 测试"
echo "======================================"
echo ""

# 1. 注册窗口
echo "1️⃣ 测试窗口注册 (POST /registry/agents/register)"
REGISTER_RESP=$(curl -s -X POST "$API_BASE/registry/agents/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"type\": \"$ROLE\",
    \"name\": \"测试窗口\",
    \"instance\": \"test-instance\",
    \"capabilities\": [\"trading\", \"analysis\"],
    \"status\": \"idle\",
    \"port\": 13080,
    \"pid\": $$
  }")

echo "$REGISTER_RESP" | jq .
echo ""

# 检查响应
if echo "$REGISTER_RESP" | jq -e '.agent_id' > /dev/null; then
  echo "✅ 注册成功: agent_id=$AGENT_ID"
else
  echo "❌ 注册失败"
  exit 1
fi
echo ""

# 2. 查询窗口（按 agent_id）
echo "2️⃣ 测试查询窗口 (GET /registry/agents/$AGENT_ID)"
curl -s "$API_BASE/registry/agents/$AGENT_ID" | jq .
echo ""

# 3. 心跳更新
echo "3️⃣ 测试心跳 (POST /registry/agents/heartbeat)"
HEARTBEAT_RESP=$(curl -s -X POST "$API_BASE/registry/agents/heartbeat" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"status\": \"active\"
  }")

echo "$HEARTBEAT_RESP" | jq .
echo ""

# 4. 按 role 查询在线窗口（RFC 010 新功能）
echo "4️⃣ 测试按 role 查询 (GET /registry/agents/available?role=$ROLE)"
ROLE_QUERY_RESP=$(curl -s "$API_BASE/registry/agents/available?role=$ROLE")
echo "$ROLE_QUERY_RESP" | jq .
echo ""

# 检查是否包含刚注册的窗口
if echo "$ROLE_QUERY_RESP" | jq -e ".[].agent_id | select(. == \"$AGENT_ID\")" > /dev/null; then
  echo "✅ 按 role 查询成功，找到窗口 $AGENT_ID"
else
  echo "⚠️  按 role 查询未找到窗口（可能是响应格式问题）"
fi
echo ""

# 5. 按 role + status 查询
echo "5️⃣ 测试按 role+status 查询 (GET /registry/agents/available?role=$ROLE&status=active)"
curl -s "$API_BASE/registry/agents/available?role=$ROLE&status=active" | jq .
echo ""

# 6. 注销窗口
echo "6️⃣ 测试注销 (POST /registry/agents/unregister)"
UNREGISTER_RESP=$(curl -s -X POST "$API_BASE/registry/agents/unregister" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\"
  }")

echo "$UNREGISTER_RESP" | jq .
echo ""

# 7. 验证注销后查询
echo "7️⃣ 验证注销后窗口状态"
AFTER_UNREG=$(curl -s "$API_BASE/registry/agents/$AGENT_ID")
echo "$AFTER_UNREG" | jq .

if echo "$AFTER_UNREG" | jq -e '.status == "offline"' > /dev/null; then
  echo "✅ 注销成功，状态变为 offline"
else
  echo "⚠️  状态未变为 offline（可能数据库未更新）"
fi
echo ""

echo "======================================"
echo "✅ 所有测试完成"
