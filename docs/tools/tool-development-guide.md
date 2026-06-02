# 工具开发指南 - 使用新的工具基础设施

**版本**: 1.0  
**更新时间**: 2026-06-02  
**适用范围**: 所有新开发的Agent工具

---

## 概述

本项目提供了一套完整的工具开发基础设施，包括：
- 统一的输出格式化系统
- 自动的错误处理和性能监控
- 链式参数验证API
- 工具统计追踪

使用这些基础设施可以：
- ✅ 减少50%的开发时间
- ✅ 提供一致的用户体验
- ✅ 自动获得性能监控和统计
- ✅ 避免重复编写错误处理代码

---

## 快速开始

### 1. 创建基本工具

```typescript
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";

export const myTool: ToolDefinition = {
  name: "my_tool",
  label: "我的工具",
  description: "工具描述...",
  
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码" }),
    limit: Type.Optional(Type.Integer({ description: "限制数量" }))
  }),
  
  execute: async (_toolCallId, params: any) => {
    return wrapToolExecution(
      async () => {
        // 1. 参数验证
        validateParams(params)
          .required(['symbol'])
          .types({ symbol: 'string', limit: 'number' })
          .validate();
        
        // 2. 业务逻辑
        const result = await doSomething(params);
        
        // 3. 返回结果
        return {
          content: [{ type: "text" as const, text: result }],
          details: result
        };
      },
      {
        toolName: "my_tool",
        enablePerformanceMonitoring: true,
        errorSuggestion: "请检查参数格式是否正确"
      }
    );
  }
};
```

**就这么简单！** 你已经获得了：
- ✅ 自动错误捕获和格式化
- ✅ 性能监控（执行耗时）
- ✅ 慢工具告警（>5秒）
- ✅ 统计追踪（成功率、调用次数）

---

## 使用输出格式化

### 表格格式化

```typescript
import { formatTableOutput, Column } from '../shared/output-formatters.js';

// 定义列
const columns: Column[] = [
  { 
    key: 'symbol', 
    label: '代码', 
    width: 10 
  },
  { 
    key: 'name', 
    label: '名称', 
    width: 12 
  },
  { 
    key: 'price', 
    label: '价格', 
    width: 10, 
    align: 'right',
    format: (v) => `¥${v.toFixed(2)}`
  }
];

// 格式化输出
const text = formatTableOutput(stocks, columns, {
  title: '自选股列表',
  maxRows: 20,
  showIndex: true,
  emptyMessage: '暂无自选股'
});

// 输出示例:
// 【自选股列表】
// 
// #  | 代码       | 名称         | 价格        
// ---|------------|------------|------------
// 1  | 600000     | 浦发银行     |      ¥10.50
// 2  | 600519     | 贵州茅台     |   ¥1,850.00
// 
// （显示前 20 条，共 50 条）
```

### 列表格式化

```typescript
import { formatListOutput } from '../shared/output-formatters.js';

const text = formatListOutput(items, {
  title: '最新新闻',
  maxItems: 10,
  bullet: '•',
  formatter: (item, index) => `${item.title} - ${item.time}`
});

// 输出示例:
// 【最新新闻】
// 
// • A股三大指数集体上涨 - 10:30
// • 央行宣布降准50个基点 - 09:15
```

### 键值对格式化

```typescript
import { formatKeyValueOutput } from '../shared/output-formatters.js';

const text = formatKeyValueOutput(stockInfo, {
  title: '股票详情',
  keyWidth: 20,
  formatter: {
    price: (v) => `¥${v.toFixed(2)}`,
    change_pct: (v) => `${(v * 100).toFixed(2)}%`
  }
});

// 输出示例:
// 【股票详情】
// 
// symbol              : 600000
// name                : 浦发银行
// price               : ¥10.50
// change_pct          : +2.34%
```

### 错误格式化

```typescript
import { formatErrorOutput } from '../shared/output-formatters.js';

const errorText = formatErrorOutput(error, {
  toolName: 'my_tool',
  command: 'fetch_data',
  suggestion: '请检查网络连接或稍后重试'
});

// 输出示例:
// ❌ 执行失败
// 
// 工具：my_tool
// 命令：fetch_data
// 
// 错误：网络请求超时
// 
// 💡 建议：请检查网络连接或稍后重试
```

---

## 参数验证

### 链式验证（推荐）

```typescript
import { validateParams } from '../shared/error-handler.js';

// 链式调用，一次性验证所有规则
validateParams(params)
  .required(['symbol', 'start_date'])
  .types({ 
    symbol: 'string', 
    limit: 'number',
    tags: 'array'
  })
  .enum('action', ['buy', 'sell', 'hold'])
  .range('limit', 1, 100)
  .validate(); // 有错误会抛出异常
```

### 独立验证函数

```typescript
import {
  validateRequiredParams,
  validateParamTypes,
  validateEnum,
  validateRange
} from '../shared/error-handler.js';

// 必填参数
validateRequiredParams(params, ['symbol', 'strategy_id']);

// 类型验证
validateParamTypes(params, {
  symbol: 'string',
  limit: 'number',
  enabled: 'boolean'
});

// 枚举验证
validateEnum(params, 'action', ['single', 'batch', 'pipeline']);

// 范围验证
validateRange(params, 'limit', 1, 100);
```

### 自定义错误消息

```typescript
try {
  validateParams(params).required(['symbol']).validate();
} catch (error) {
  throw new Error(
    `参数验证失败: ${error.message}\n` +
    `请提供有效的股票代码（6位数字）`
  );
}
```

---

## 性能监控

### 基本监控（自动）

使用 `wrapToolExecution` 后，自动获得：

```typescript
// 自动记录到日志
[INFO] [Performance] my_tool: 234ms

// 慢工具自动告警
[WARN] [SlowTool] my_tool took 6234ms (threshold: 5000ms)

// 失败自动记录
[ERROR] [my_tool] 执行失败: 网络超时
```

### 自定义阈值

```typescript
return wrapToolExecution(
  async () => { /* ... */ },
  {
    toolName: "backtest_tool",
    enablePerformanceMonitoring: true,
    slowToolThreshold: 10000  // 回测工具，10秒才算慢
  }
);
```

### 查看统计

```typescript
import { getToolStatsReport, resetToolStats } from '../shared/error-handler.js';

// 获取所有工具的统计
const stats = getToolStatsReport();
console.log(stats);
// {
//   "my_tool": {
//     totalCalls: 150,
//     successCalls: 145,
//     failureCalls: 5,
//     totalDuration: 35000,
//     lastCallAt: 1717315200000,
//     lastError: "网络超时"
//   }
// }

// 重置统计
resetToolStats('my_tool');  // 重置单个
resetToolStats();           // 重置全部
```

---

## 完整示例

### 示例1: 简单查询工具

```typescript
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";
import { formatTableOutput, Column } from "../shared/output-formatters.js";

export const stockListTool: ToolDefinition = {
  name: "stock_list",
  label: "股票列表查询",
  description: "查询股票列表，支持按市场筛选",
  
  parameters: Type.Object({
    market: Type.Optional(Type.String({ description: "市场类型" })),
    limit: Type.Optional(Type.Integer({ description: "限制数量" }))
  }),
  
  execute: async (_toolCallId, params: any) => {
    return wrapToolExecution(
      async () => {
        // 参数验证
        if (params.market) {
          validateParams(params)
            .enum('market', ['沪市', '深市', '创业板', '科创板'])
            .validate();
        }
        
        // 查询数据
        const stocks = await fetchStocks(params);
        
        // 格式化输出
        const columns: Column[] = [
          { key: 'symbol', label: '代码', width: 10 },
          { key: 'name', label: '名称', width: 12 },
          { key: 'price', label: '价格', width: 10, align: 'right' }
        ];
        
        const text = formatTableOutput(stocks, columns, {
          title: '股票列表',
          maxRows: params.limit || 50,
          showIndex: true
        });
        
        return {
          content: [{ type: "text" as const, text }],
          details: stocks
        };
      },
      {
        toolName: "stock_list",
        enablePerformanceMonitoring: true,
        errorSuggestion: "请检查市场参数是否正确"
      }
    );
  }
};
```

### 示例2: 复杂分析工具

```typescript
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";
import { 
  formatKeyValueOutput, 
  formatStatsOutput,
  StatItem 
} from "../shared/output-formatters.js";

export const stockAnalysisTool: ToolDefinition = {
  name: "stock_analysis",
  label: "股票分析",
  description: "综合分析股票（技术面+基本面）",
  
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码" }),
    include_technical: Type.Optional(Type.Boolean({ description: "包含技术分析" })),
    include_fundamental: Type.Optional(Type.Boolean({ description: "包含基本面分析" }))
  }),
  
  execute: async (_toolCallId, params: any) => {
    return wrapToolExecution(
      async () => {
        // 参数验证
        validateParams(params)
          .required(['symbol'])
          .types({ 
            symbol: 'string',
            include_technical: 'boolean',
            include_fundamental: 'boolean'
          })
          .validate();
        
        const sections: string[] = [];
        
        // 基本信息
        const basicInfo = await fetchBasicInfo(params.symbol);
        sections.push(formatKeyValueOutput(basicInfo, {
          title: '基本信息',
          keyWidth: 15
        }));
        
        // 技术分析
        if (params.include_technical !== false) {
          const technical = await analyzeTechnical(params.symbol);
          const techStats: StatItem[] = [
            { label: 'RSI', value: technical.rsi, format: (v) => v.toFixed(2) },
            { label: 'MACD', value: technical.macd, format: (v) => v.toFixed(3) },
            { label: '趋势', value: technical.trend, highlight: true }
          ];
          
          sections.push(formatStatsOutput(techStats, '技术指标'));
        }
        
        // 基本面分析
        if (params.include_fundamental !== false) {
          const fundamental = await analyzeFundamental(params.symbol);
          sections.push(formatKeyValueOutput(fundamental, {
            title: '基本面分析',
            formatter: {
              roe: (v) => `${(v * 100).toFixed(2)}%`,
              pe: (v) => v.toFixed(2)
            }
          }));
        }
        
        const text = sections.join('\n\n');
        
        return {
          content: [{ type: "text" as const, text }],
          details: { basicInfo, technical, fundamental }
        };
      },
      {
        toolName: "stock_analysis",
        enablePerformanceMonitoring: true,
        slowToolThreshold: 8000,  // 分析较慢，提高阈值
        errorSuggestion: "分析失败可能是因为数据源不可用，请稍后重试"
      }
    );
  }
};
```

---

## 最佳实践

### 1. 命名规范

```typescript
// ✅ 好的命名
export const stockListTool: ToolDefinition = { name: "stock_list", ... };
export const dataFetchTool: ToolDefinition = { name: "data_fetch", ... };

// ❌ 不好的命名
export const tool1: ToolDefinition = { name: "tool", ... };
export const myTool: ToolDefinition = { name: "my-tool", ... };
```

**规则**:
- 使用 `snake_case` 命名
- 名称要清晰描述功能
- 避免使用缩写

### 2. 参数验证

```typescript
// ✅ 好的验证
validateParams(params)
  .required(['symbol', 'start_date'])
  .types({ symbol: 'string', limit: 'number' })
  .enum('period', ['1d', '1w', '1m'])
  .range('limit', 1, 100)
  .validate();

// ❌ 不好的验证
if (!params.symbol) throw new Error('missing symbol');
if (typeof params.limit !== 'number') throw new Error('limit must be number');
```

**规则**:
- 总是验证必填参数
- 验证参数类型
- 验证枚举值和范围
- 使用链式API提高可读性

### 3. 错误处理

```typescript
// ✅ 好的错误处理
return wrapToolExecution(
  async () => { /* logic */ },
  {
    toolName: "my_tool",
    errorSuggestion: "具体的建议，帮助用户解决问题"
  }
);

// ❌ 不好的错误处理
try {
  const result = await api.call();
  return result;
} catch (e) {
  return { error: e.message };  // 格式不统一
}
```

**规则**:
- 总是使用 `wrapToolExecution`
- 提供有用的错误建议
- 不要吞掉错误

### 4. 输出格式

```typescript
// ✅ 好的输出
const text = formatTableOutput(data, columns, { title: '结果' });
return {
  content: [{ type: "text" as const, text }],
  details: data  // 保留原始数据
};

// ❌ 不好的输出
return {
  content: [{ 
    type: "text" as const, 
    text: JSON.stringify(data)  // 不友好
  }]
};
```

**规则**:
- 使用格式化函数
- 返回人类可读的文本
- 在details中保留原始数据

### 5. 性能优化

```typescript
// ✅ 好的性能设置
return wrapToolExecution(
  async () => {
    // 对于快速操作，使用默认阈值（5秒）
  },
  { 
    toolName: "quick_tool",
    slowToolThreshold: 2000  // 快速工具，2秒就算慢
  }
);

// 对于慢操作
return wrapToolExecution(
  async () => {
    // 回测、训练等
  },
  { 
    toolName: "slow_tool",
    slowToolThreshold: 30000  // 慢工具，30秒才告警
  }
);
```

**规则**:
- 根据工具特性设置阈值
- 快速工具：2-5秒
- 中速工具：5-10秒
- 慢速工具：10-30秒

---

## 测试

### 单元测试示例

```typescript
import { describe, it, expect } from '@jest/globals';
import { myTool } from './my-tool.js';

describe('myTool', () => {
  it('should validate required parameters', async () => {
    await expect(
      myTool.execute('test', {})
    ).rejects.toThrow('缺少必填参数: symbol');
  });
  
  it('should format output correctly', async () => {
    const result = await myTool.execute('test', {
      symbol: '600000'
    });
    
    expect(result.content[0].text).toContain('600000');
    expect(result.details).toBeDefined();
  });
  
  it('should record performance stats', async () => {
    const { getToolStatsReport, resetToolStats } = await import('../shared/error-handler.js');
    
    resetToolStats('my_tool');
    
    await myTool.execute('test', { symbol: '600000' });
    
    const stats = getToolStatsReport();
    expect(stats.my_tool.totalCalls).toBe(1);
    expect(stats.my_tool.successCalls).toBe(1);
  });
});
```

---

## 常见问题

### Q: 如何处理异步操作？

A: `wrapToolExecution` 已经支持异步操作：

```typescript
return wrapToolExecution(
  async () => {
    const data = await fetchData();
    const processed = await processData(data);
    return processed;
  },
  { toolName: "my_tool" }
);
```

### Q: 如何自定义日志？

A: 可以设置自定义logger：

```typescript
import { setLogger } from '../shared/error-handler.js';

setLogger({
  info: (msg, meta) => console.log(`[INFO] ${msg}`, meta),
  warn: (msg, meta) => console.warn(`[WARN] ${msg}`, meta),
  error: (msg, meta) => console.error(`[ERROR] ${msg}`, meta)
});
```

### Q: 如何禁用性能监控？

A: 设置 `enablePerformanceMonitoring: false`：

```typescript
return wrapToolExecution(
  async () => { /* ... */ },
  {
    toolName: "my_tool",
    enablePerformanceMonitoring: false
  }
);
```

### Q: 格式化函数支持哪些数据类型？

A: 支持所有常见类型：
- 字符串、数字、布尔值
- 数组（自动截断）
- 对象（自动折叠）
- 日期/时间戳（自动本地化）
- null/undefined（显示为 "-"）

---

## 更多资源

- [输出格式化API文档](../shared/output-formatters.ts)
- [错误处理API文档](../shared/error-handler.ts)
- [CLI工具示例](../cli/)
- [最佳实践文档](./best-practices.md)

---

**更新时间**: 2026-06-02  
**维护者**: Agent Tool Team
