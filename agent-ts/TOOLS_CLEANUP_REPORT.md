# Agent 工具清理报告

## 检查时间
2026-06-16

## 发现的问题

### 1. ❌ 重复注册的工具

#### marketStyleDetectTool - 重复 2 次
**位置**: [index.ts:278, 283](src/infrastructure/tools/index.ts#L278)

```typescript
// 第 278 行
marketStyleDetectTool,          // market_style_detect - 市场风格检测（新增）

// 第 283 行（重复！）
marketStyleDetectTool,          // market_style_detect - 市场风格检测（新增）
```

**问题**: 同一个工具在 allCustomTools 数组中注册了两次，会导致：
- 系统提示词中工具列表重复
- Agent 看到两个相同的工具，造成混淆

#### dataManagerTool - 重复 2 次
**位置**: [index.ts:205, 273](src/infrastructure/tools/index.ts#L205)

```typescript
// 第 205 行
dataManagerTool,                // data_manager - 数据管理工具（新增：从quant_cli拆分）

// 第 273 行（重复！）
dataManagerTool,                // data_manager - 数据管理工具
```

**问题**: 同样的重复问题

---

### 2. 🧪 测试/示例工具（未注册但存在文件）

#### calculate_rsi-tool.ts
**位置**: [src/infrastructure/tools/calculate_rsi-tool.ts](src/infrastructure/tools/calculate_rsi-tool.ts)

**状态**: 
- ✅ 未在 index.ts 注册
- 📁 文件仍然存在
- 🧪 有测试文件 `calculate_rsi-tool.test.ts`

**分析**:
- 这是一个完整实现的 RSI 计算工具
- 但已有更强大的 `indicatorBacktestTool` 和技术指标工具
- 看起来是早期的测试工具或被替代的工具

**建议**: 
- 如果 RSI 计算功能已被其他工具覆盖 → 删除
- 如果未来可能独立使用 → 保留但添加文档说明

#### new_tool-tool.ts
**位置**: [src/infrastructure/tools/new_tool-tool.ts](src/infrastructure/tools/new_tool-tool.ts)

**状态**:
- ✅ 未在 index.ts 注册
- 📁 文件仍然存在
- 🧪 有测试文件 `new_tool-tool.test.ts`

**分析**:
```typescript
export const new_toolTool: ToolDefinition = {
  name: "new_tool",
  label: "new_tool",
  description: "新工具",  // ← 明显是模板/占位符
  parameters: Type.Object({
    input: Type.Optional(Type.String()),
  }),
  execute: async (_toolCallId, params: any) => {
    const input = typeof params?.input === "string" ? params.input : "";
    const resultText = input ? `结果文本: ${input}` : "结果文本";
    return { ... };
  },
};
```

**问题**: 这明显是一个工具开发模板或测试占位符

**建议**: **应该删除**

#### test-utils.ts
**位置**: [src/infrastructure/tools/test-utils.ts](src/infrastructure/tools/test-utils.ts)

**状态**: 测试工具辅助文件

**建议**: 保留（测试需要）

---

### 3. ⚠️ 标记为废弃的命令

#### quant_cli 工具中的废弃命令
**位置**: [src/infrastructure/tools/core/quant-cli-tool.ts](src/infrastructure/tools/core/quant-cli-tool.ts)

**废弃命令**:
```typescript
"signal.generate" - ⚠️ DEPRECATED: signal.generate 命令已废弃
```

**注释说明**:
```typescript
// quantCliTool 本身标记为：
quantCliTool,  // quant_cli - 原统一CLI工具（向后兼容，逐步废弃）
```

**分析**:
- `quantCliTool` 是旧架构的统一入口
- 功能正在拆分为独立工具（如 dataManagerTool, marketCliTool 等）
- 保留是为了向后兼容

**建议**: 
- **不要立即删除** quantCliTool（向后兼容需要）
- 在新代码中优先使用独立工具
- 制定迁移计划，逐步替换使用场景

---

### 4. 📝 已移除但有注释的工具

#### portfolioRebalanceTool
**位置**: [index.ts:119](src/infrastructure/tools/index.ts#L119)
```typescript
// 注：portfolioRebalanceTool 已移除（2026-05-27，依赖已废弃的本地服务）
```

#### tradeManageOrdersTool
**位置**: [index.ts:122](src/infrastructure/tools/index.ts#L122)
```typescript
// 注：tradeManageOrdersTool 已移除（2026-05-27，依赖已废弃的本地服务）
```

**状态**: ✅ 已正确移除，注释记录清晰

---

## 清理建议

### 立即执行（High Priority）

#### 1. 删除重复注册 - marketStyleDetectTool
```diff
  factorModelAttributionTool,     // factor_model_attribution - 因子模型归因（新增）
  marketStyleDetectTool,          // market_style_detect - 市场风格检测（新增）
  schedulerManageTool,            // scheduler_manage - 调度器管理（新增）
  strategyComparisonTool,         // strategy_performance_comparison - 策略性能对比（新增）
  backtestStatsTool,              // backtest_stats - 回测统计（新增）
  backtestHistoryTool,            // backtest_history - 回测历史查询（新增）
- marketStyleDetectTool,          // market_style_detect - 市场风格检测（新增）  ← 删除重复
  tradeMonitorTool,               // trade_monitor - 交易监控工具
```

#### 2. 删除重复注册 - dataManagerTool
```diff
  // L1 数据管道
  dataFetchQuoteTool,             // data_fetch_quote - 获取股票实时行情
  dataFetchKlineTool,             // data_fetch_kline - 获取K线数据
  dataFetchFinancialTool,         // data_fetch_financial - 获取财务数据
  dataFetchDividendTool,          // data_fetch_dividend - 获取分红送股数据
  dataFetchMacroTool,             // data_fetch_macro - 获取宏观经济数据（新增）
  dataFetchNorthFlowTool,         // data_fetch_north_flow - 获取北向资金流向（新增）
  dataFetchMarketSentimentTool,   // data_fetch_market_sentiment - 获取市场情绪分析（新增）
  dataManagerTool,                // data_manager - 数据管理工具（新增：从quant_cli拆分）
  dataQualityReportTool,          // data_quality_report - 数据质量监控（新增）
  dataQualityManageTool,          // data_quality_manage - 数据补救管理（新增：2026-06-04）

  // ... 中间省略 ...

  // ===== 独立业务工具（从 quant_cli 拆分）=====
- dataManagerTool,                // data_manager - 数据管理工具  ← 删除重复
  riskMetricsTool,               // risk_metrics - 风险指标分析（empyrical）
```

#### 3. 删除测试工具文件
```bash
# 删除 new_tool 测试工具
rm src/infrastructure/tools/new_tool-tool.ts
rm src/infrastructure/tools/new_tool-tool.test.ts
```

### 可选执行（Medium Priority）

#### 4. 删除或归档 calculate_rsi-tool.ts
**选项 A**: 删除（如果功能已被其他工具覆盖）
```bash
rm src/infrastructure/tools/calculate_rsi-tool.ts
rm src/infrastructure/tools/calculate_rsi-tool.test.ts
```

**选项 B**: 保留但添加说明
```typescript
/**
 * Calculate RSI Tool
 * 
 * @deprecated 此工具未在生产中使用，保留用于测试目的
 * 实际使用请用 indicatorBacktestTool 或技术指标相关工具
 */
export const calculate_rsiTool: ToolDefinition = {
  // ...
};
```

### 长期规划（Low Priority）

#### 5. quantCliTool 迁移计划
- 记录所有使用 `quant_cli` 的地方
- 逐步替换为独立工具（marketCliTool, stockCliTool 等）
- 制定废弃时间表（建议 3-6 个月后完全移除）

---

## 清理脚本

创建自动清理脚本：

```bash
#!/bin/bash
# cleanup-tools.sh

echo "🧹 开始清理废弃工具..."

# 1. 删除 new_tool 测试工具
echo "删除 new_tool 测试工具..."
rm -f src/infrastructure/tools/new_tool-tool.ts
rm -f src/infrastructure/tools/new_tool-tool.test.ts

# 2. 删除 calculate_rsi 工具（可选）
read -p "是否删除 calculate_rsi 工具? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "删除 calculate_rsi 工具..."
    rm -f src/infrastructure/tools/calculate_rsi-tool.ts
    rm -f src/infrastructure/tools/calculate_rsi-tool.test.ts
fi

echo "✅ 文件清理完成"
echo ""
echo "⚠️  请手动编辑 src/infrastructure/tools/index.ts:"
echo "   1. 删除第 283 行的 marketStyleDetectTool 重复项"
echo "   2. 删除第 273 行的 dataManagerTool 重复项"
```

---

## 验证步骤

清理后执行以下验证：

### 1. TypeScript 编译检查
```bash
npm run build
```

### 2. 测试运行
```bash
npm test
```

### 3. 工具注册检查
```bash
# 检查是否还有重复工具
grep -n "marketStyleDetectTool\|dataManagerTool" src/infrastructure/tools/index.ts
```

### 4. 未使用工具检查
```bash
# 查找定义但未注册的工具
find src/infrastructure/tools -name "*-tool.ts" | while read file; do
  toolname=$(basename "$file" -tool.ts)
  if ! grep -q "$toolname" src/infrastructure/tools/index.ts; then
    echo "⚠️  未注册: $file"
  fi
done
```

---

## 统计信息

### 工具总数
- **总工具文件**: 87 个
- **注册工具**: ~85 个（去重后 ~83 个）
- **重复注册**: 2 个
- **未注册但存在**: 2-3 个

### 清理影响
- **删除文件**: 4 个（new_tool 相关）
- **修改文件**: 1 个（index.ts 去重）
- **向后兼容**: ✅ 保持（quantCliTool 保留）

---

## 总结

**必须清理**:
1. ✅ marketStyleDetectTool 重复注册
2. ✅ dataManagerTool 重复注册
3. ✅ new_tool-tool.ts 测试工具

**建议清理**:
4. ⚠️ calculate_rsi-tool.ts（需确认是否有用）

**保留不动**:
5. ✅ quantCliTool（向后兼容）
6. ✅ test-utils.ts（测试辅助）

清理后工具注册将更清晰，Agent 提示词中不会有重复工具，维护性提升。
