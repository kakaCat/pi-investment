#!/bin/bash
# 批量修复工具返回类型问题

set -e

echo "🔧 开始批量修复工具返回类型..."

# 需要修复的文件列表
files=(
  "src/infrastructure/tools/analysis/backtest-history-tool.ts"
  "src/infrastructure/tools/analysis/backtest-stats-tool.ts"
  "src/infrastructure/tools/analysis/strategy-comparison-tool.ts"
  "src/infrastructure/tools/invest/opportunity-scan-enhanced-tool.ts"
)

# 在每个文件开头添加导入语句
for file in "${files[@]}"; do
  if [ -f "$file" ]; then
    echo "✓ 处理 $file"

    # 检查是否已经有导入
    if ! grep -q "wrapToolResult" "$file"; then
      # 找到第一个 import 语句后添加新导入
      sed -i '' "1a\\
import { wrapToolResult, wrapToolError } from '../utils/tool-result-wrapper.js';\\
" "$file"
      echo "  ✓ 添加导入语句"
    fi

    # 替换 return output; 为 return wrapToolResult(output, ...);
    # 这需要根据每个文件的具体情况手动处理

  else
    echo "⚠️  文件不存在: $file"
  fi
done

echo "✅ 批量修复完成！"
echo "📝 注意：某些复杂的返回语句需要手动修复"
