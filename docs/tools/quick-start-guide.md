# 工具系统使用快速指南

**更新时间**: 2026-06-02  
**适用范围**: 所有开发者和用户

---

## 🚀 快速开始

### 使用CLI工具

#### 1. 市场数据查询
```typescript
// 查询市场概览
market_cli({ command: "market.overview" })

// 查询指数历史
market_cli({ 
  command: "market.index_history",
  params: { 
    index_code: "000001", 
    start_date: "2026-01-01" 
  }
})
```

#### 2. 个股数据查询
```typescript
// 股票评分
stock_cli({ 
  command: "stock.score", 
  params: { symbol: "600000" } 
})

// 批量报价
stock_cli({ 
  command: "stock.batch_quotes",
  params: { symbols: ["600000", "000001", "600519"] }
})
```

#### 3. 财务数据查询
```typescript
// 财务指标
financial_cli({ 
  command: "financial.indicators",
  params: { symbol: "600000", years: 5 }
})

// PE分位数
financial_cli({ 
  command: "financial.pe_percentile",
  params: { symbol: "600000" }
})
```

#### 4. 市场情绪分析
```typescript
// 龙虎榜
sentiment_cli({ 
  command: "sentiment.lhb",
  params: { date: "20260601" }
})

// 资金流向
sentiment_cli({ 
  command: "sentiment.stock_fund_flow",
  params: { symbol: "600000", days: 5 }
})
```

#### 5. 股票分析
```typescript
// 技术分析
analysis_cli({ 
  command: "analysis.technical",
  params: { symbol: "600000", period: 60 }
})

// 买入区间
analysis_cli({ 
  command: "analysis.buy_range",
  params: { symbol: "600000" }
})
```

#### 6. 信号管理
```typescript
// 查询信号列表
signal_cli({ 
  command: "signal.list",
  params: { date: "2026-06-01", limit: 20 }
})

// 信号统计
signal_cli({ 
  command: "signal.statistics",
  params: { strategy_id: "53" }
})
```

#### 7. 指标回测
```typescript
// 指标回测（专用工具）
indicator_backtest({ 
  indicator_id: 1,
  symbol: "600000",
  start_date: "2025-01-01",
  end_date: "2025-12-31",
  initial_cash: 1000000
})

// 查询结果
// 回测结果会直接返回在 indicator_backtest 的响应中
```

#### 8. 自选股管理
```typescript
// 列出自选股
watchlist_cli({ command: "watchlist.list" })

// 添加股票
watchlist_cli({ 
  command: "watchlist.add",
  params: { 
    symbol: "600000", 
    note: "关注银行股" 
  }
})

// 更新备注
watchlist_cli({ 
  command: "watchlist.update",
  params: { 
    symbol: "600000", 
    note: "等待回调",
    tags: ["银行", "低估值"]
  }
})
```

---

## 🛠️ 开发新工具

### 基本模板

```typescript
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";
import { formatTableOutput } from "../shared/output-formatters.js";

export const myTool: ToolDefinition = {
  name: "my_tool",
  label: "我的工具",
  description: "工具描述",
  
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码" })
  }),
  
  execute: async (_toolCallId, params: any) => {
    return wrapToolExecution(
      async () => {
        // 1. 验证参数
        validateParams(params).required(['symbol']).validate();
        
        // 2. 执行业务逻辑
        const result = await doSomething(params);
        
        // 3. 格式化输出
        const text = formatTableOutput(result, columns, { title: '结果' });
        
        // 4. 返回结果
        return {
          content: [{ type: "text" as const, text }],
          details: result
        };
      },
      {
        toolName: "my_tool",
        enablePerformanceMonitoring: true
      }
    );
  }
};
```

---

## 📊 工具特性

### 自动功能

所有新CLI工具自动享有：

✅ **错误处理**
- 自动捕获异常
- 友好的错误提示
- 自定义建议消息

✅ **性能监控**
- 自动记录执行耗时
- 慢工具告警（>5秒）
- 性能统计追踪

✅ **参数验证**
- 必填参数检查
- 类型验证
- 枚举和范围验证

✅ **统计追踪**
- 调用次数统计
- 成功率追踪
- 平均耗时计算

### 查看工具统计

```typescript
import { getToolStatsReport } from './shared/error-handler.js';

const stats = getToolStatsReport();
console.log(stats);

// 输出示例:
// {
//   "market_cli": {
//     totalCalls: 150,
//     successCalls: 145,
//     failureCalls: 5,
//     totalDuration: 35000,
//     lastCallAt: 1717315200000
//   }
// }
```

---

## 🎓 最佳实践

### 1. 命令命名
- 使用清晰的动词：list, get, create, update, delete
- 保持一致性：所有工具使用相同的命名模式

### 2. 参数设计
- 必填参数放前面
- 使用有意义的参数名
- 提供清晰的描述

### 3. 错误提示
- 说明问题是什么
- 提供解决建议
- 包含示例用法

### 4. 输出格式
- 使用统一的格式化函数
- 保持输出简洁清晰
- 提供足够的信息

---

## 📚 更多资源

- [工具开发指南](./tools/tool-development-guide.md)
- [输出格式化API](../src/infrastructure/tools/shared/output-formatters.ts)
- [错误处理API](../src/infrastructure/tools/shared/error-handler.ts)
- [CLI工具示例](../src/infrastructure/tools/examples/example-cli-tool.ts)

---

## 🆘 常见问题

### Q: 如何选择使用哪个工具？

A: 根据数据类型选择：
- 市场整体数据 → `market_cli`
- 个股数据 → `stock_cli`  
- 财务数据 → `financial_cli`
- 情绪数据 → `sentiment_cli`
- 分析功能 → `analysis_cli`
- 信号管理 → `signal_cli`
- 指标回测 → `indicator_backtest`
- 自选股 → `watchlist_cli`

### Q: 工具执行失败怎么办？

A: 检查以下几点：
1. 参数是否正确
2. quantsys-v2服务是否运行
3. 查看错误提示中的建议
4. 检查日志文件

### Q: 如何提升工具性能？

A: 几个建议：
1. 减少不必要的数据查询
2. 使用批量操作
3. 合理设置慢工具阈值
4. 查看统计报告识别瓶颈

---

**最后更新**: 2026-06-02  
**维护者**: Agent Tool Team
