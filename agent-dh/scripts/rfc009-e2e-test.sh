#!/bin/bash
# RFC 009 端到端验收测试
# 测试场景：A1-A5（核心流程）

set -e

API_BASE="http://localhost:8080/api/v1"
PASSED=0
FAILED=0

echo "=========================================="
echo "RFC 009 端到端验收测试"
echo "=========================================="
echo ""

# 辅助函数
pass() {
  echo "✅ $1"
  PASSED=$((PASSED + 1))
}

fail() {
  echo "❌ $1"
  FAILED=$((FAILED + 1))
}

# A1: 创建测试帖子（needs_action=false，纯记录）
echo "[A1] 创建测试帖子（done 状态）"
CREATE_RESPONSE=$(curl -s -X POST "$API_BASE/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "RFC009验收测试帖",
    "content": "这是一个测试帖子",
    "category": "knowledge",
    "tags": ["office:board", "kind:finding"]
  }')

POST_ID=$(echo "$CREATE_RESPONSE" | jq -r '.memory.id')
if [ -z "$POST_ID" ] || [ "$POST_ID" = "null" ]; then
  fail "A1: 创建帖子失败"
  echo "Response: $CREATE_RESPONSE"
  exit 1
fi
pass "A1: 创建帖子成功，ID=$POST_ID"

# 设置初始 metadata（模拟 board_post）
curl -s -X PATCH "$API_BASE/memory/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata_patch": {
      "board_status": "open",
      "kind": "finding",
      "author": "w-test",
      "revision": 1
    }
  }' > /dev/null

echo ""

# A2: 更新帖子内容（PATCH content）
echo "[A2] 更新帖子内容"
PATCH_RESPONSE=$(curl -s -X PATCH "$API_BASE/memory/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "更新后的内容",
    "expected_revision": 1
  }')

if echo "$PATCH_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
  pass "A2: 更新内容成功"
else
  fail "A2: 更新内容失败 - $PATCH_RESPONSE"
fi

echo ""

# A3: 状态迁移（open → claimed）
echo "[A3] 状态迁移测试（open → claimed）"
CLAIM_RESPONSE=$(curl -s -X PATCH "$API_BASE/memory/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata_patch": {
      "board_status": "claimed",
      "assignee": "w-test-claimer",
      "revision": 2
    },
    "expected_revision": 2
  }')

if echo "$CLAIM_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
  pass "A3: 状态迁移成功（open → claimed）"
else
  fail "A3: 状态迁移失败 - $CLAIM_RESPONSE"
fi

echo ""

# A4: 乐观锁冲突测试
echo "[A4] 乐观锁冲突测试"
CONFLICT_RESPONSE=$(curl -s -X PATCH "$API_BASE/memory/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "尝试用旧 revision 更新",
    "expected_revision": 1
  }')

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$API_BASE/memory/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "尝试用旧 revision 更新",
    "expected_revision": 1
  }')

if [ "$HTTP_CODE" = "409" ]; then
  pass "A4: 乐观锁冲突正确返回 409"
else
  fail "A4: 乐观锁冲突应返回 409，实际 $HTTP_CODE"
fi

echo ""

# A5: 软删除（DROP）
echo "[A5] 软删除测试"
DELETE_RESPONSE=$(curl -s -X DELETE "$API_BASE/memory/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "验收测试完成，删除测试帖"
  }')

if echo "$DELETE_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
  pass "A5: 软删除成功"
else
  fail "A5: 软删除失败 - $DELETE_RESPONSE"
fi

echo ""

# A6: 验证默认查询不返回已删除帖子
echo "[A6] 验证过滤逻辑（默认不返回 dropped）"
LIST_RESPONSE=$(curl -s "$API_BASE/memory?tag=office:board&limit=100")
FOUND=$(echo "$LIST_RESPONSE" | jq --arg id "$POST_ID" '.memories[] | select(.id == $id) | .id' 2>/dev/null)

if [ -z "$FOUND" ]; then
  pass "A6: 默认查询不返回 dropped 帖子"
else
  fail "A6: 默认查询返回了 dropped 帖子"
fi

echo ""

# A7: include_closed=true 可以查到已删除帖子
echo "[A7] 验证 include_closed=true 查询"
LIST_CLOSED_RESPONSE=$(curl -s "$API_BASE/memory?tag=office:board&limit=100&include_closed=true")
FOUND_CLOSED=$(echo "$LIST_CLOSED_RESPONSE" | jq --arg id "$POST_ID" '.memories[] | select(.id == $id) | .id' 2>/dev/null)

if [ -n "$FOUND_CLOSED" ]; then
  pass "A7: include_closed=true 可查到 dropped 帖子"
else
  fail "A7: include_closed=true 未查到 dropped 帖子"
fi

echo ""

# 总结
echo "=========================================="
echo "验收测试完成"
echo "=========================================="
echo "通过: $PASSED"
echo "失败: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
  echo "✅ 全部测试通过！"
  exit 0
else
  echo "❌ 有 $FAILED 个测试失败"
  exit 1
fi
