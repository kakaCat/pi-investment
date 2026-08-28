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

## 相关文档

- [TOOL-ERROR-HANDLING-AND-ROUTING.md](../../docs/TOOL-ERROR-HANDLING-AND-ROUTING.md)
- [TOOL-FRAMEWORK-VALIDATION-ERROR-ENHANCED.md](../../docs/TOOL-FRAMEWORK-VALIDATION-ERROR-ENHANCED.md)
- [TOOL-FRAMEWORK-DSH-COMPATIBLE.md](../../docs/TOOL-FRAMEWORK-DSH-COMPATIBLE.md)
