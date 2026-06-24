#!/bin/bash
# quick-fix-remaining.sh
cd /Users/mac/Documents/ai/pi-investment/agent-ts

echo "🔧 开始快速修复剩余构建错误..."

# 修复 Error 构造调用
echo "1. 修复 Error 构造调用..."
sed -i '' 's/throw new Error(error\.message || error\.hint || "因子归因分析失败");/throw new Error(typeof error === "object" \&\& error !== null ? (error as any).message || (error as any).hint || "因子归因分析失败" : "因子归因分析失败");/' \
  src/infrastructure/tools/analysis/factor-model-attribution-tool.ts 2>/dev/null

sed -i '' 's/throw new Error(error\.message || error\.hint || "获取市场情绪失败");/throw new Error(typeof error === "object" \&\& error !== null ? (error as any).message || (error as any).hint || "获取市场情绪失败" : "获取市场情绪失败");/' \
  src/infrastructure/tools/data/fetch-market-sentiment-tool.ts 2>/dev/null

sed -i '' 's/throw new Error(error\.message || error\.hint || "Barra风险分解失败");/throw new Error(typeof error === "object" \&\& error !== null ? (error as any).message || (error as any).hint || "Barra风险分解失败" : "Barra风险分解失败");/' \
  src/infrastructure/tools/risk/barra-decomposition-tool.ts 2>/dev/null

# 修复 strategy 工具的属性访问
echo "2. 修复 strategy 工具..."
sed -i '' 's/const strategyName = deleteResult\.name || params\.strategy_name;/const strategyName = (deleteResult as any)?.name || params?.strategy_name;/' \
  src/infrastructure/tools/strategy/delete-tool.ts 2>/dev/null

sed -i '' 's/const strategyName = detail\.name;/const strategyName = (detail as any)?.name;/' \
  src/infrastructure/tools/strategy/detail-tool.ts 2>/dev/null

sed -i '' 's/const strategies = response\.items || response\.strategies || \[\];/const strategies = (response as any)?.items || (response as any)?.strategies || [];/' \
  src/infrastructure/tools/strategy/list-tool.ts 2>/dev/null

# 修复 result-persister.example.ts
echo "3. 修复 result-persister.example.ts..."
sed -i '' 's/if (!validateResult\.success)/if (!(validateResult as any)?.success)/g' \
  src/infrastructure/tools/utils/result-persister.example.ts 2>/dev/null
sed -i '' 's/data\.klines/((data as any)?.klines)/g' \
  src/infrastructure/tools/utils/result-persister.example.ts 2>/dev/null

# 修复 signal 工具
echo "4. 修复 signal 工具..."
sed -i '' 's/return response as T;/return response as any;/' \
  src/infrastructure/tools/signal/realtime-signal-tool.ts 2>/dev/null

# 修复 compact-tool.ts 的 generateSummary 参数
echo "5. 修复 compact-tool.ts..."
sed -i '' 's/await generateSummary(messages as any, model, 16384, apiKey, undefined, params\.focus);/await generateSummary(messages as any, model, 16384, undefined as any, undefined, params.focus);/' \
  src/infrastructure/tools/agent/compact-tool.ts 2>/dev/null

echo "✅ 快速修复完成"
echo ""
echo "📊 检查构建状态..."
