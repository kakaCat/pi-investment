# quant_cli 工具错误提示增强：自动附加策略列表

**日期：** 2026-05-29  
**状态：** 设计完成，待实现

## 背景

当前 `quant_cli` 工具在缺少 `strategy_id` 必填参数时，仅返回通用错误提示：

```
缺少必填参数: strategy_id。原因：该参数是命令执行的必要条件，不能为空。
```

这导致 LLM 需要额外调用 `strategy.list` 命令才能获取可用策略列表，增加了交互轮次和响应延迟。

## 目标

在 `strategy_id` 参数缺失时，错误消息中自动附加可用策略列表，使 LLM 能够立即选择正确的策略 ID，减少工具调用次数。

## 适用范围

所有需要 `strategy_id` 必填参数的命令：

- `performance.by_strategy` — 查询单个策略性能
- `strategy.get` — 查询策略详情
- `strategy.optimize` — 策略参数优化
- `strategy.run` — 实时运行策略
- `backtest.strategy` — 运行策略回测
- `signal.generate` — 生成交易信号

## 设计方案

### 方案选择

采用 **方案 A：参数验证时动态查询**

**理由：**
- 实现简单，改动最小
- 信息始终最新
- 性能开销可接受（50-200ms，仅在异常路径触发）
- 容错性好（查询失败时降级为通用提示）

### 核心改动

#### 1. 修改 `validateParams()` 函数

**位置：** `src/infrastructure/tools/core/quant-cli-tool.ts:1444`

**当前逻辑：**
```typescript
if (paramRule.required && isEmpty(value)) {
  return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。`;
}
```

**改进后：**
```typescript
if (paramRule.required && isEmpty(value)) {
  // 特殊处理：strategy_id 参数缺失时附加策略列表
  if (key === 'strategy_id') {
    const strategyListHint = await fetchStrategyListHint();
    return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。\n\n${strategyListHint}`;
  }
  return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。`;
}
```

**注意：** `validateParams()` 需要改为 `async` 函数。

#### 2. 新增 `fetchStrategyListHint()` 辅助函数

**位置：** `src/infrastructure/tools/core/quant-cli-tool.ts`（在 `validateParams()` 之前定义）

**功能：**
- 调用 `runQuantV2("strategy.list", {})` 获取策略列表
- 格式化为友好的错误提示文本
- 容错处理：查询失败时返回降级提示

**实现：**
```typescript
/**
 * 获取策略列表提示文本（用于 strategy_id 参数缺失时的错误消息）
 * @returns 格式化的策略列表提示，或降级提示（查询失败时）
 */
async function fetchStrategyListHint(): Promise<string> {
  try {
    const response = await runQuantV2("strategy.list", {});
    const strategies = (response as any)?.strategies || [];
    
    if (strategies.length === 0) {
      return "提示：当前系统中没有可用策略。请先使用 strategy.create 创建策略。";
    }
    
    // 格式化策略列表（最多显示前 10 个）
    const displayStrategies = strategies.slice(0, 10);
    const strategyLines = displayStrategies.map((s: any) => 
      `  - ID: ${s.id}, 名称: ${s.name}`
    ).join('\n');
    
    const moreHint = strategies.length > 10 
      ? `\n\n（共 ${strategies.length} 个策略，仅显示前 10 个）` 
      : '';
    
    return `可用策略列表：\n${strategyLines}${moreHint}\n\n提示：使用 strategy.list 命令可查看完整策略详情。`;
    
  } catch (error) {
    // 降级：查询失败时返回通用提示
    return "提示：使用 strategy.list 命令查看可用策略列表。";
  }
}
```

#### 3. 调整调用链

由于 `validateParams()` 改为 `async`，需要在调用处添加 `await`：

**位置：** `src/infrastructure/tools/core/quant-cli-tool.ts:1334`

**当前：**
```typescript
const validation = validateParams(command, rule, params);
if (validation) {
  return validationError(validation, formatCommandHelp(command, rule));
}
```

**改进后：**
```typescript
const validation = await validateParams(command, rule, params);
if (validation) {
  return validationError(validation, formatCommandHelp(command, rule));
}
```

## 错误消息示例

### 成功查询策略列表

```
缺少必填参数: strategy_id。原因：该参数是命令执行的必要条件，不能为空。

可用策略列表：
  - ID: 53, 名称: 多因子波段策略v9
  - ID: 54, 名称: RSI超买超卖策略
  - ID: 55, 名称: MACD金叉死叉策略
  - ID: 56, 名称: 均线交叉策略

提示：使用 strategy.list 命令可查看完整策略详情。

命令说明: performance.by_strategy - 查询单个策略的性能详情：收益、回撤、夏普比率。v2 端点。
必填参数: strategy_id
支持参数: strategy_id
示例 params: {"strategy_id":"rsi-strategy"}
```

### 策略列表为空

```
缺少必填参数: strategy_id。原因：该参数是命令执行的必要条件，不能为空。

提示：当前系统中没有可用策略。请先使用 strategy.create 创建策略。

命令说明: performance.by_strategy - 查询单个策略的性能详情：收益、回撤、夏普比率。v2 端点。
必填参数: strategy_id
支持参数: strategy_id
示例 params: {"strategy_id":"rsi-strategy"}
```

### 查询失败（降级）

```
缺少必填参数: strategy_id。原因：该参数是命令执行的必要条件，不能为空。

提示：使用 strategy.list 命令查看可用策略列表。

命令说明: performance.by_strategy - 查询单个策略的性能详情：收益、回撤、夏普比率。v2 端点。
必填参数: strategy_id
支持参数: strategy_id
示例 params: {"strategy_id":"rsi-strategy"}
```

## 性能影响

- **正常路径**：无影响（参数验证通过时不触发查询）
- **异常路径**：增加 50-200ms（一次 HTTP 调用）
- **频率**：仅在参数错误时触发，属于低频场景

## 容错处理

1. **quantsys-v2 服务不可用**：降级为通用提示，不阻塞错误返回
2. **策略列表为空**：显示友好提示，引导用户创建策略
3. **策略数量过多**：仅显示前 10 个，避免消息过长

## 测试场景

1. **正常场景**：缺少 `strategy_id` 参数，成功显示策略列表
2. **空列表**：系统中无策略，显示创建提示
3. **大量策略**：超过 10 个策略，仅显示前 10 个并提示总数
4. **服务不可用**：quantsys-v2 未启动，降级为通用提示
5. **其他必填参数**：非 `strategy_id` 参数缺失，保持原有错误提示

## 实现文件

- `src/infrastructure/tools/core/quant-cli-tool.ts`
  - 新增 `fetchStrategyListHint()` 函数
  - 修改 `validateParams()` 为 `async` 函数
  - 调整调用处添加 `await`

## 后续优化（可选）

1. **缓存策略列表**：如果性能成为瓶颈，可考虑短期缓存（如 1 分钟）
2. **扩展到其他参数**：如 `indicator_id` 缺失时附加指标列表
3. **智能推荐**：基于命令上下文推荐最相关的策略

## 风险评估

- **低风险**：改动集中在错误处理路径，不影响正常功能
- **向后兼容**：错误消息格式变化，但不影响工具调用逻辑
- **依赖性**：依赖 quantsys-v2 服务，但有降级处理

## 验收标准

- [ ] 缺少 `strategy_id` 时，错误消息包含策略列表
- [ ] 策略列表格式清晰，包含 ID 和名称
- [ ] 超过 10 个策略时，仅显示前 10 个并提示总数
- [ ] quantsys-v2 不可用时，降级为通用提示
- [ ] 其他必填参数缺失时，保持原有错误提示
- [ ] 所有受影响命令（6 个）均正常工作
