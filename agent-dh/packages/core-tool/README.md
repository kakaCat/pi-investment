# @pi-investment/core-tool-tool

Agent-DH 工具框架核心规范包。

## 定位

**本包只提供规范定义，不包含具体实现。**

- ✅ 类型定义（TypeScript interfaces/types）
- ✅ 三段式接口规范
- ✅ 工具执行流程框架
- ❌ 具体的 validators（应在各工具自己的目录）
- ❌ 具体的 routing rules（应在各工具自己的目录）
- ❌ 具体的 schema templates（应在各工具自己的目录）

## 三段式接口规范

根据设计文档，工具执行分为三个独立阶段：

### Phase 1: 入参校验（Input Validation）

```typescript
import { validateInputPhase, InputSchema } from '@pi-investment/core-tool';

const inputSchema: InputSchema = {
  symbol: {
    required: true,
    validator: (v) => /^\d{6}$/.test(v),
    expectedFormat: '6位数字',
    example: '600519',
    description: 'A股股票代码',
    purpose: '唯一标识一只股票',
    impact: '执行交易',
    commonMistakes: ['不要包含交易所前缀（如 SH600519）'],
  },
};

const result = validateInputPhase(args, inputSchema);
if (!result.success) {
  console.error(result.error);
}
```

### Phase 2: 任务执行（Task Execution）

```typescript
import { executeTaskPhase, BusinessValidator } from '@pi-investment/core-tool';

const myBusinessValidator: BusinessValidator = (args, context) => {
  // 业务规则校验（如交易时段检查）
  if (!isTradingHours()) {
    return {
      success: false,
      errorType: 'BUSINESS_REJECTION',
      rule: '交易时段限制',
      issue: '当前非交易时段',
    };
  }
  return { success: true };
};

const result = await executeTaskPhase(
  args,
  context,
  myBusinessValidator,
  async (args) => {
    // 实际业务逻辑
    return qv2.executeTrade(args);
  }
);
```

### Phase 3: 出参包装（Output Wrapping）

```typescript
import { wrapOutputPhase, OutputSchema } from '@pi-investment/core-tool';

const outputSchema: OutputSchema = {
  order_id: {
    required: true,
    description: '订单ID',
    impact: '无法追踪订单',
  },
  price: {
    required: true,
    description: '成交价格',
    impact: '无法计算成本',
  },
};

const result = wrapOutputPhase(rawResult, outputSchema, context, myRoutingRules);
```

### 完整流程（自动串联）

```typescript
import { enhancedToolExecute } from '@pi-investment/core-tool';

const result = await enhancedToolExecute(
  'portfolio_trade',
  args,
  { input: inputSchema, output: outputSchema },
  async (args) => qv2.executeTrade(args),
  {
    businessValidator: myBusinessValidator,
    customRoutingRules: myRoutingRules,
  }
);

if (!result.success) {
  console.error(result.error);
  if (result.routing?.shouldRoute) {
    console.log(`推荐使用: ${result.routing.recommendedTool}`);
  }
}
```

## 核心类型

### ErrorType

```typescript
enum ErrorType {
  INPUT_ERROR = 'INPUT_ERROR',           // 入参格式错误
  INPUT_EMPTY = 'INPUT_EMPTY',           // 必填参数缺失
  OUTPUT_ERROR = 'OUTPUT_ERROR',         // 数据结构异常
  OUTPUT_EMPTY = 'OUTPUT_EMPTY',         // 查询无结果
  BUSINESS_REJECTION = 'BUSINESS_REJECTION', // 违反业务规则
  TOOL_NOT_APPLICABLE = 'TOOL_NOT_APPLICABLE', // 场景不匹配
  EXECUTION_ERROR = 'EXECUTION_ERROR',   // 执行异常
  TIMEOUT = 'TIMEOUT',                   // 超时
}
```

### ValidationResult

```typescript
interface ValidationResult {
  success: boolean;
  errorType?: ErrorType;
  field?: string;
  issue?: string;
  received?: any;
  expected?: any;
  example?: any;
  guide?: string;
  commonMistakes?: string[];
  possibleReasons?: string[];
  alternatives?: AlternativeAction[];
  solutions?: BusinessSolution[];
  data?: any; // 成功时的数据
}
```

### BusinessValidator

```typescript
type BusinessValidator = (
  args: any,
  context: BusinessContext
) => ValidationResult | Promise<ValidationResult>;
```

### ToolRoutingRule

```typescript
interface ToolRoutingRule {
  from: string;                                    // 来源工具
  condition: (error: ValidationResult) => boolean; // 触发条件
  to: string;                                      // 目标工具
  reason: string;                                  // 推荐理由
  example: string;                                 // 使用示例
}
```

## 工具实现示例

具体工具应该在自己的目录下实现 schema、validators、routing rules：

```
packages/trading/src/tools/PortfolioTradeTool/
├── schema.ts           ← 定义 input/output schema
├── validators.ts       ← 定义业务校验器
├── routing-rules.ts    ← 定义路由规则
└── tool.ts             ← 使用 core 框架实现工具
```

## 设计原则

**"不只告诉 Agent 错了，而是告诉它为什么错、怎么改、或者试试别的工具"**

1. **入参错误** → 明确指出问题 + 提供示例 + 引导修正
2. **出参错误** → 说明数据异常 + 给出可能原因 + 推荐替代方案
3. **业务错误** → 解释业务约束 + 提供解决路径 + 推荐其他工具
4. **工具路由** → A 工具不行时，自动推荐 B 工具

## 错误处理与工具路由最佳实践

> 以下为工具实现时的实战规范，配合上文的三段式框架与核心类型使用。当前实现以 `BaseTool` 抽象类为准：子类重写 `validate()` / `execute()` / `wrap()` 三段方法（真实示例见 `packages/investment/src/tools/` 下的各工具目录）。

### 错误分类矩阵

| 错误类型 | 触发时机 | 返回内容 | Agent 行动 |
|---------|---------|---------|-----------|
| 入参错误 (INPUT_ERROR) | 参数格式/类型不对 | 期望格式 + 示例 + 修正建议 | 修正参数重试 |
| 入参为空 (INPUT_EMPTY) | 必填参数缺失 | 参数说明 + 示例 + 用途说明 | 补充参数重试 |
| 出参错误 (OUTPUT_ERROR) | 后端数据结构异常 | 期望结构 + 实际数据 + 可能原因 | 报告问题或换工具 |
| 出参无数据 (OUTPUT_EMPTY) | 查询无结果 | 无数据原因 + 检查建议 + 替代方案 | 调整条件或换工具 |
| 业务拒绝 (BUSINESS_REJECTION) | 违反业务规则 | 规则说明 + 当前状态 + 解决路径 | 调整策略或换工具 |
| 工具不适用 (TOOL_NOT_APPLICABLE) | 场景不匹配 | 不适用原因 + 推荐工具 | 切换到推荐工具 |
| 执行异常 (EXECUTION_ERROR) / 超时 (TIMEOUT) | 后端/网络故障 | 错误原因 + 重试建议 | 重试或上报 |

### 工具路由规则表（示例）

| 当前工具 | 失败原因 | 推荐工具 | 推荐理由 | 示例 |
|---------|---------|---------|---------|------|
| portfolio_trade | 非交易时段 | watch_manage | 可设置价格提醒 | `watch_manage({ action: 'create', ... })` |
| portfolio_trade | 资金不足 | position_list | 先查持仓释放资金 | `position_list()` |
| data_fetch_quote | 股票不存在 | screening | 搜索正确代码 | `screening({ filters: { name: '茅台' } })` |
| model_predict | 模型异常 | strategy_execute | 改用策略信号 | `strategy_execute({ strategy_id: 1 })` |
| strategy_execute | 无信号 | opportunity_scan | 扩大选股范围 | `opportunity_scan({ limit: 10 })` |

**路由决策流程**：工具执行失败 → 识别失败类型 →（入参错误→修正参数重试 / 出参异常→匹配路由规则推荐替代工具 / 业务拒绝→提供解决方案或换工具）。

### 编写规范

**错误提示（DO / DON'T）**
- ✅ `issue: "symbol 必须是6位数字股票代码"`，附 `received` / `expected` / `example` / `commonMistakes: ["不要包含交易所前缀"]`
- ❌ `{ error: "参数错误" }` —— 太模糊，Agent 无法理解

**业务约束说明（DO / DON'T）**
- ✅ 给出 `rule` + `issue` + `currentTime` / `nextTradingTime` + `solutions[]`（含 `approach` 与 `tool`）
- ❌ `{ error: "不能交易" }` —— 没说原因也没给方案

**工具路由推荐（DO / DON'T）**
- ✅ `routing: { shouldRoute: true, recommendedTool: "watch_manage", reason: "...", example: "...", confidence: "high" }`
- ❌ `{ suggestion: "试试其他工具" }` —— 没说具体工具与用法

## 相关文档

工具框架设计已完整记录于本文件（三段式接口规范 + 核心类型 + 上述最佳实践）。历史设计迭代文档已移除，避免与当前 `BaseTool` 实现脱节。
