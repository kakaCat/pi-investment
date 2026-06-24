#!/bin/bash
# 批量修复常见的类型错误

cd /Users/mac/Documents/ai/pi-investment/agent-ts

# 修复 calculate_rsi-tool.ts
sed -i '' 's/\.map((value) =>/\.map((value: any) =>/' src/infrastructure/tools/calculate_rsi-tool.ts

# 修复 quality-manage-tool.ts - 移除不存在的 Tool 导入
sed -i '' '/import.*Tool.*from.*@mariozechner\/pi-agent-core/d' src/infrastructure/tools/data/quality-manage-tool.ts
sed -i '' 's/async execute(_toolCallId,/async execute(_toolCallId: string,/' src/infrastructure/tools/data/quality-manage-tool.ts

echo "✅ 批量修复完成"
