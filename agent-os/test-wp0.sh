#!/bin/bash
# WP-0 验收测试脚本

set -e

echo "======================================"
echo "WP-0 项目脚手架 - 验收测试"
echo "======================================"
echo ""

cd "$(dirname "$0")"

# 1. 编译检查
echo "✓ 测试 1: 编译检查"
go build -o agent-os ./cmd/agent-os
echo "  ✅ 编译成功"
echo ""

# 2. version 命令
echo "✓ 测试 2: version 命令"
VERSION_OUTPUT=$(./agent-os version)
if [[ "$VERSION_OUTPUT" == *"v0.1.0"* ]]; then
    echo "  ✅ version 命令正常: $VERSION_OUTPUT"
else
    echo "  ❌ version 命令失败: $VERSION_OUTPUT"
    exit 1
fi
echo ""

# 3. help 命令
echo "✓ 测试 3: help 命令"
HELP_OUTPUT=$(./agent-os help)
if [[ "$HELP_OUTPUT" == *"Available Commands"* ]]; then
    echo "  ✅ help 命令正常"
else
    echo "  ❌ help 命令失败"
    exit 1
fi
echo ""

# 4. 数据库连接
echo "✓ 测试 4: 数据库检查"
NAMESPACE_COUNT=$(psql -d agent_os -tAc "SELECT COUNT(*) FROM namespaces;")
if [[ "$NAMESPACE_COUNT" == "4" ]]; then
    echo "  ✅ Namespaces: $NAMESPACE_COUNT 个"
else
    echo "  ❌ Namespaces 数量错误: 期望 4, 实际 $NAMESPACE_COUNT"
    exit 1
fi

PERMISSION_COUNT=$(psql -d agent_os -tAc "SELECT COUNT(*) FROM permissions;")
if [[ "$PERMISSION_COUNT" == "18" ]]; then
    echo "  ✅ Permissions: $PERMISSION_COUNT 个"
else
    echo "  ❌ Permissions 数量错误: 期望 18, 实际 $PERMISSION_COUNT"
    exit 1
fi

QUOTA_COUNT=$(psql -d agent_os -tAc "SELECT COUNT(*) FROM resource_quotas;")
if [[ "$QUOTA_COUNT" == "9" ]]; then
    echo "  ✅ Resource Quotas: $QUOTA_COUNT 个"
else
    echo "  ❌ Resource Quotas 数量错误: 期望 9, 实际 $QUOTA_COUNT"
    exit 1
fi
echo ""

# 5. 视图检查
echo "✓ 测试 5: 视图检查"
psql -d agent_os -c "SELECT * FROM active_tasks LIMIT 1;" > /dev/null 2>&1
echo "  ✅ active_tasks 视图正常"

psql -d agent_os -c "SELECT * FROM quota_usage LIMIT 1;" > /dev/null 2>&1
echo "  ✅ quota_usage 视图正常"
echo ""

# 总结
echo "======================================"
echo "✅ 所有测试通过！"
echo "======================================"
echo ""
echo "验收标准达成："
echo "  ✅ agent-os version 能运行"
echo "  ✅ agent-os help 能运行"
echo "  ✅ 数据库 schema 正常"
echo "  ✅ 默认数据已插入"
echo ""
echo "WP-0 完成，可以进入 Batch 1！"
