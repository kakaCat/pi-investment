#!/bin/bash
# REQ-327bdf 快速验证脚本

echo "=== REQ-327bdf 验收验证 ==="
echo ""

fail_count=0

# 1. 核心功能
echo "1. 核心功能验证..."
ls -la packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts > /dev/null 2>&1 && echo "  ✅ reqboard_task_execute" || { echo "  ❌ reqboard_task_execute"; ((fail_count++)); }
ls -la packages/pages/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts > /dev/null 2>&1 && echo "  ✅ reqboard_task_status" || { echo "  ❌ reqboard_task_status"; ((fail_count++)); }
ls -la packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/generate-stages.ts > /dev/null 2>&1 && echo "  ✅ generateStages" || { echo "  ❌ generateStages"; ((fail_count++)); }
ls -la packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/update-task-card.ts > /dev/null 2>&1 && echo "  ✅ updateTaskCard" || { echo "  ❌ updateTaskCard"; ((fail_count++)); }
grep -q "todo_write" packages/pages/dsh-pmboard/src/application/use-cases/Decompose.ts && echo "  ✅ todo_write 集成" || { echo "  ❌ todo_write 集成"; ((fail_count++)); }

echo ""

# 2. 文档
echo "2. 文档验证..."
ls -la docs/guides/workflow-tools-guide.md > /dev/null 2>&1 && echo "  ✅ 工具使用指南" || { echo "  ❌ 工具使用指南"; ((fail_count++)); }
ls -la docs/guides/task-execution-migration.md > /dev/null 2>&1 && echo "  ✅ 迁移指南" || { echo "  ❌ 迁移指南"; ((fail_count++)); }
ls -la docs/requirements/REQ-327bdf/e2e-test-report.md > /dev/null 2>&1 && echo "  ✅ E2E 报告" || { echo "  ❌ E2E 报告"; ((fail_count++)); }

echo ""

# 3. 测试
echo "3. 测试验证..."
ls -la tests/task-retry.test.ts > /dev/null 2>&1 && echo "  ✅ 失败重试测试文件" || { echo "  ❌ 失败重试测试文件"; ((fail_count++)); }

echo ""

# 4. 构建
echo "4. 构建验证..."
ls -la packages/pages/dsh-pmboard/lib/client.js > /dev/null 2>&1 && echo "  ✅ 客户端构建" || { echo "  ❌ 客户端构建"; ((fail_count++)); }

echo ""
echo "==================================="
if [ $fail_count -eq 0 ]; then
  echo "✅ 全部验证通过！"
  exit 0
else
  echo "❌ 有 $fail_count 项验证失败"
  exit 1
fi
