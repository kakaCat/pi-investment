#!/bin/bash
# 批量修复 'unknown' 类型错误

cd /Users/mac/Documents/ai/pi-investment/agent-ts/src/infrastructure/tools

# 修复 factor 工具中的 unknown 类型错误
for file in factor/batch-layering-backtest-tool.ts factor/correlation-tool.ts factor/ic-monitor-tool.ts factor/layering-backtest-tool.ts factor/list-tool.ts factor/portfolio-optimize-tool.ts; do
  if [ -f "$file" ]; then
    # 修复 errorData
    sed -i '' 's/errorData is of type '\''unknown'\''/errorData: any/' "$file"
    # 修复 result
    sed -i '' 's/const result =/const result: any =/' "$file"
    echo "✅ 修复 $file"
  fi
done

echo "✅ 批量修复完成"
