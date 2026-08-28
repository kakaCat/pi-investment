# Agent-DH 工具框架：参数校验错误包装设计

**问题：** 当前参数校验失败直接 `throw new Error`，LLM 收到的错误信息可能不够友好，缺少：
1. ❌ 明确的错误类型标识
2. ❌ 结构化的错误详情
3. ❌ 可操作的修复建议
4. ❌ 参数示例

**解决方案：** 统一的参数校验错误包装机制

---

## 🎯 核心设计

### 1. 自定义参数校验错误类

```typescript
// packages/tool-framework/src/errors.ts

/**
 * 参数校验错误（专用错误类）
 */
export class ParameterValidationError extends Error {
  readonly code = 'PARAMETER_VALIDATION_ERROR';
  readonly validationErrors: ValidationErrorDetail[];

  constructor(errors: ValidationErrorDetail[]) {
    const message = ParameterValidationError.formatMessage(errors);
    super(message);
    this.name = 'ParameterValidationError';
    this.validationErrors = errors;
  }

  /**
   * 格式化为友好的错误消息（给 LLM 看）
   */
  private static formatMessage(errors: ValidationErrorDetail[]): string {
    const lines = [
      '❌ 参数校验失败：',
      '',
    ];

    errors.forEach((err, idx) => {
      lines.push(`${idx + 1}. **${err.field}**: ${err.message}`);
      if (err.expected) {
        lines.push(`   期望值: ${err.expected}`);
      }
      if (err.received !== undefined) {
        lines.push(`   实际值: ${JSON.stringify(err.received)}`);
      }
      if (err.example) {
        lines.push(`   示例: ${err.example}`);
      }
      lines.push('');
    });

    lines.push('💡 修复建议：');
    lines.push('请检查参数格式，确保所有必填参数都已提供且格式正确。');

    return lines.join('\n');
  }

  /**
   * 转换为结构化响应（给工具框架用）
   */
  toStructuredResponse(): ToolResponse<never> {
    return {
      success: false,
      error: {
        code: this.code,
        message: this.message,
        details: {
          validationErrors: this.validationErrors,
        },
      },
      meta: {
        toolName: 'unknown',
        duration: 0,
        timestamp: new Date().toISOString(),
        executionId: '',
      },
    };
  }
}

export interface ValidationErrorDetail {
  field: string;           // 字段名
  message: string;         // 错误描述
  expected?: string;       // 期望值描述
  received?: any;          // 实际接收值
  example?: string;        // 正确示例
}

/**
 * 业务拒绝错误
 */
export class BusinessRejectionError extends Error {
  readonly code = 'BUSINESS_REJECTION';
  readonly blocked = true;

  constructor(reason: string, public readonly details?: any) {
    super(reason);
    this.name = 'BusinessRejectionError';
  }
}
```

### 2. 增强的参数校验函数

```typescript
// packages/tool-framework/src/validation.ts

import { ParameterValidationError, ValidationErrorDetail } from './errors';

export interface ValidationRule {
  field: string;
  required?: boolean;
  validator?: (value: any) => boolean;
  errorMessage?: string;
  expectedFormat?: string;    // 期望格式描述
  example?: string;           // 正确示例
}

/**
 * 统一参数校验函数（增强版）
 */
export function validateParams(args: any, rules: ValidationRule[]): void {
  const errors: ValidationErrorDetail[] = [];

  for (const rule of rules) {
    const value = args?.[rule.field];

    // 必填校验
    if (rule.required && (value === undefined || value === null || value === '')) {
      errors.push({
        field: rule.field,
        message: `${rule.field} 是必填参数`,
        expected: rule.expectedFormat || '非空值',
        received: value,
        example: rule.example,
      });
      continue;
    }

    // 跳过未提供的可选参数
    if (value === undefined || value === null) {
      continue;
    }

    // 自定义校验
    if (rule.validator && !rule.validator(value)) {
      errors.push({
        field: rule.field,
        message: rule.errorMessage || `${rule.field} 格式不正确`,
        expected: rule.expectedFormat,
        received: value,
        example: rule.example,
      });
    }
  }

  // 如果有错误，抛出专用错误类
  if (errors.length > 0) {
    throw new ParameterValidationError(errors);
  }
}

/**
 * 常用校验器（带示例）
 */
export const validators = {
  isStockCode: {
    check: (value: string) => /^\d{6}$/.test(value),
    expectedFormat: '6位数字',
    example: '600519',
  },
  
  isDate: {
    check: (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && !isNaN(Date.parse(value)),
    expectedFormat: 'YYYY-MM-DD 格式',
    example: '2024-08-27',
  },
  
  isMultipleOf: (multiple: number) => ({
    check: (value: number) => Number.isInteger(value) && value > 0 && value % multiple === 0,
    expectedFormat: `${multiple}的正整数倍`,
    example: String(multiple * 2),
  }),
  
  isOneOf: (values: any[]) => ({
    check: (value: any) => values.includes(value),
    expectedFormat: `其中之一: ${values.join(', ')}`,
    example: values[0],
  }),
  
  isPositiveNumber: {
    check: (value: number) => typeof value === 'number' && value > 0,
    expectedFormat: '正数',
    example: '100',
  },
};
```

### 3. BaseTool 中的错误处理

```typescript
// packages/tool-framework/src/BaseTool.ts

import { ParameterValidationError, BusinessRejectionError } from './errors';

export abstract class BaseTool<TParams, TResult> {
  // ... 其他代码

  /**
   * 统一调用入口（增强错误处理）
   */
  async call(args: TParams, context?: Partial<ToolContext>): Promise<ToolResponse<TResult>> {
    const executionId = uuidv4();
    const startTime = Date.now();

    const ctx: ToolContext<TParams> = {
      args,
      trace: { executionId, depth: 0 },
    };

    try {
      // 1. 参数校验（会抛出 ParameterValidationError）
      this.validateParameters(args);

      // 2. 前置条件检查
      await this.checkPreconditions(ctx);

      // 3. 执行业务逻辑
      let result = await this.execute(ctx);

      // 4. 后置处理
      result = await this.postProcess(ctx, result);

      // 5. 记录日志
      this.logToolCall(ctx, result, Date.now() - startTime).catch(console.warn);

      return {
        success: true,
        data: result,
        meta: {
          toolName: this.metadata.name,
          duration: Date.now() - startTime,
          timestamp: new Date().toISOString(),
          executionId,
        },
      };
    } catch (error: any) {
      await this.onError(ctx, error);
      this.logToolCall(ctx, null, Date.now() - startTime, error).catch(console.warn);

      // ========== 错误分类处理 ==========
      
      // 1. 参数校验错误（友好提示）
      if (error instanceof ParameterValidationError) {
        return {
          success: false,
          error: {
            code: error.code,
            message: error.message,  // 已格式化的友好消息
            details: {
              validationErrors: error.validationErrors,
            },
          },
          meta: {
            toolName: this.metadata.name,
            duration: Date.now() - startTime,
            timestamp: new Date().toISOString(),
            executionId,
          },
        };
      }

      // 2. 业务拒绝错误
      if (error instanceof BusinessRejectionError || error.blocked) {
        return {
          success: false,
          blocked: true,
          reason: error.message,
          error: {
            code: error.code || 'BUSINESS_REJECTION',
            message: error.message,
            details: error.details,
          },
          meta: {
            toolName: this.metadata.name,
            duration: Date.now() - startTime,
            timestamp: new Date().toISOString(),
            executionId,
          },
        };
      }

      // 3. 系统错误
      return {
        success: false,
        error: {
          code: error.code || 'INTERNAL_ERROR',
          message: error.message || '工具执行失败',
          details: error.details,
        },
        meta: {
          toolName: this.metadata.name,
          duration: Date.now() - startTime,
          timestamp: new Date().toISOString(),
          executionId,
        },
      };
    }
  }

  /**
   * 参数校验（使用增强版 validateParams）
   */
  private validateParameters(args: TParams): void {
    const rules = Object.entries(this.prompt.parameters).map(([field, def]) => ({
      field,
      required: def.required,
      validator: def.validator,
      errorMessage: def.errorMessage,
      expectedFormat: def.expectedFormat,
      example: def.example,
    }));

    validateParams(args, rules);  // 可能抛出 ParameterValidationError
  }

  /**
   * 业务拒绝辅助方法（使用专用错误类）
   */
  protected blocked(reason: string, details?: any): never {
    throw new BusinessRejectionError(reason, details);
  }
}
```

### 4. DSH 适配器中的错误处理

```typescript
// packages/tool-framework/src/BaseTool.ts

export abstract class BaseTool<TParams, TResult> {
  /**
   * 转换为 DSH defineTool 格式
   */
  toDSHToolDefinition() {
    return {
      name: this.metadata.name,
      description: this.prompt.description,
      parameters: this.convertParameters(this.prompt.parameters),
      output: {
        schema: this.prompt.output.schema,
        render: this.prompt.output.render,
      },
      timeoutMs: this.metadata.timeoutMs || 10000,
      
      execute: async (args: TParams) => {
        const response = await this.call(args);
        
        // ========== 错误响应处理 ==========
        
        // 1. 参数校验失败：返回结构化错误（不抛异常）
        if (!response.success && response.error?.code === 'PARAMETER_VALIDATION_ERROR') {
          return {
            success: false,
            error: {
              type: 'validation',
              message: response.error.message,  // 格式化的友好消息
              details: response.error.details,
            },
          };
        }
        
        // 2. 业务拒绝：返回特殊格式
        if (response.blocked) {
          return {
            success: false,
            blocked: true,
            reason: response.reason,
          };
        }
        
        // 3. 成功：返回数据
        if (response.success) {
          return response.data;
        }
        
        // 4. 系统错误：抛出（让 DSH 处理）
        throw new Error(response.error?.message || '工具执行失败');
      },
    };
  }
}
```

---

## 📝 完整使用示例

### 在 prompt.ts 中定义参数（带校验信息）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/prompt.ts

import { validators } from '@pi-investment/tool-framework';

export const portfolioTradePrompt = {
  // ...
  parameters: {
    action: {
      type: 'string',
      description: 'BUY：买入；SELL：卖出',
      required: true,
      enum: ['BUY', 'SELL'],
      validator: validators.isOneOf(['BUY', 'SELL']).check,
      expectedFormat: validators.isOneOf(['BUY', 'SELL']).expectedFormat,
      example: validators.isOneOf(['BUY', 'SELL']).example,
      errorMessage: 'action 必须是 BUY 或 SELL',
    },
    
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码',
      required: true,
      validator: validators.isStockCode.check,
      expectedFormat: validators.isStockCode.expectedFormat,
      example: validators.isStockCode.example,
      errorMessage: 'symbol 必须是6位数字股票代码',
    },
    
    quantity: {
      type: 'integer',
      description: '交易数量（股），买入必须是100的整数倍',
      required: true,
      validator: validators.isMultipleOf(100).check,
      expectedFormat: validators.isMultipleOf(100).expectedFormat,
      example: validators.isMultipleOf(100).example,
      errorMessage: '数量必须是100的正整数倍',
    },
    
    price: {
      type: 'number',
      description: '委托价格（元）。不传则按市价成交',
      required: false,
      validator: validators.isPositiveNumber.check,
      expectedFormat: validators.isPositiveNumber.expectedFormat,
      example: validators.isPositiveNumber.example,
      errorMessage: 'price 必须是正数',
    },
  },
  // ...
};
```

---

## 🎯 错误展示效果对比

### Before（直接抛异常）

**LLM 收到：**
```
Error: watch_manage create 缺少必填参数: name、symbol
```

❌ **问题：**
- 信息简略，不友好
- 没有格式说明
- 没有示例
- LLM 难以理解如何修复

### After（结构化包装）

**LLM 收到：**
```json
{
  "success": false,
  "error": {
    "type": "validation",
    "message": "❌ 参数校验失败：

1. **symbol**: symbol 必须是6位数字股票代码
   期望值: 6位数字
   实际值: "abc123"
   示例: 600519

2. **quantity**: 数量必须是100的正整数倍
   期望值: 100的正整数倍
   实际值: 50
   示例: 200

💡 修复建议：
请检查参数格式，确保所有必填参数都已提供且格式正确。",
    "details": {
      "validationErrors": [
        {
          "field": "symbol",
          "message": "symbol 必须是6位数字股票代码",
          "expected": "6位数字",
          "received": "abc123",
          "example": "600519"
        },
        {
          "field": "quantity",
          "message": "数量必须是100的正整数倍",
          "expected": "100的正整数倍",
          "received": 50,
          "example": "200"
        }
      ]
    }
  }
}
```

✅ **优势：**
- 结构化错误详情
- 明确的期望值和实际值
- 提供正确示例
- 友好的修复建议
- LLM 能理解并修正参数

---

## 🔄 错误处理流程图

```
工具调用
   ↓
参数校验 (validateParams)
   ↓
校验失败？
   ├─ Yes → 抛出 ParameterValidationError
   │           ↓
   │        BaseTool.call 捕获
   │           ↓
   │        包装为结构化响应
   │           ↓
   │        DSH 适配器处理
   │           ↓
   │        返回友好错误信息给 LLM
   │
   └─ No → 继续执行
           ↓
        前置条件检查
           ↓
        业务逻辑执行
           ↓
        可能抛出 BusinessRejectionError（业务拒绝）
           ↓
        BaseTool.call 捕获
           ↓
        返回 blocked: true
```

---

## ✅ 关键改进总结

### 1. 专用错误类

- ✅ `ParameterValidationError` - 参数校验专用
- ✅ `BusinessRejectionError` - 业务拒绝专用
- ✅ 结构化错误详情

### 2. 友好的错误消息

- ✅ 明确的字段名和错误描述
- ✅ 期望值 vs 实际值对比
- ✅ 正确示例
- ✅ 修复建议

### 3. 错误分类处理

- ✅ 参数校验错误 → 结构化返回
- ✅ 业务拒绝错误 → `blocked: true`
- ✅ 系统错误 → 抛出异常

### 4. LLM 友好

- ✅ Markdown 格式化
- ✅ Emoji 视觉提示
- ✅ 可操作的建议
- ✅ 完整的上下文信息

---

## 📋 实施清单

- [ ] 创建 `errors.ts`（定义专用错误类）
- [ ] 增强 `validation.ts`（支持 expectedFormat、example）
- [ ] 更新 `BaseTool.ts`（错误分类处理）
- [ ] 更新 `prompt.ts` 模板（添加 expectedFormat、example）
- [ ] 编写单元测试（覆盖各种错误场景）
- [ ] 更新文档（错误处理最佳实践）

---

**文档版本：** v4.0 (Validation Error Wrapping)  
**创建时间：** 2026-08-28T02:36:29.159Z
