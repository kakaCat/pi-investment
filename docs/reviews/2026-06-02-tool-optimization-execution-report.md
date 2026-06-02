# 工具系统优化执行报告 - 任务 2、3、4

**执行日期**: 2026-06-02  
**任务**: 统一输出格式、统一错误处理、拆分 quant-cli-tool  
**状态**: 🟡 进行中

---

## 任务执行摘要

### ✅ 任务 2: 统一输出格式（已完成）

**创建文件**: `src/infrastructure/tools/shared/output-formatters.ts` (469行)

**提供的格式化函数**:

| 函数名 | 用途 | 主要参数 |
|--------|------|---------|
| `formatTableOutput()` | 表格数据格式化 | data[], columns[], options |
| `formatListOutput()` | 列表数据格式化 | items[], options |
| `formatKeyValueOutput()` | 键值对格式化 | data{}, options |
| `formatErrorOutput()` | 错误信息格式化 | error, context |
| `formatSuccessOutput()` | 成功消息格式化 | message, data, options |
| `formatProgressOutput()` | 进度条格式化 | current, total, message |
| `formatStatsOutput()` | 统计摘要格式化 | stats[], title |

**辅助函数**:
- `truncateText()` - 截断长文本
- `formatTimestamp()` - 时间戳格式化
- `formatNumber()` - 数字格式化（带千分位）
- `formatPercentage()` - 百分比格式化
- `formatCurrency()` - 货币格式化

**核心特性**:
- ✅ 支持中文标签和对齐
- ✅ 自动类型检测（数字、百分比、数组、对象）
- ✅ 智能截断（防止输出过长）
- ✅ 一致的样式（标题、分隔符、提示）
- ✅ 空数据处理（显示友好提示）

**使用示例**:
```typescript
import { formatTableOutput, Column } from '../shared/output-formatters.js';

const columns: Column[] = [
  { key: 'symbol', label: '代码', width: 10 },
  { key: 'name', label: '名称', width: 12 },
  { key: 'price', label: '价格', width: 10, align: 'right', format: (v) => `¥${v.toFixed(2)}` }
];

const text = formatTableOutput(stocks, columns, {
  title: '股票列表',
  maxRows: 20,
  showIndex: true
});
```

---

### ✅ 任务 3: 统一错误处理（已完成）

**创建文件**: `src/infrastructure/tools/shared/error-handler.ts` (380行)

**核心功能**:

#### 1. 工具执行包装器
```typescript
wrapToolExecution<T>(
  fn: () => Promise<T>,
  options: ToolExecutionOptions
): Promise<ToolResult>
```

**自动提供**:
- ✅ 错误捕获和格式化
- ✅ 性能监控（执行耗时）
- ✅ 慢工具告警（> 5秒）
- ✅ 统计追踪（成功率、调用次数）
- ✅ 日志记录（info/warn/error）

#### 2. 参数验证工具

| 函数 | 功能 |
|------|------|
| `validateRequiredParams()` | 检查必填参数 |
| `validateParamTypes()` | 类型验证 |
| `validateEnum()` | 枚举值验证 |
| `validateRange()` | 数值范围验证 |

#### 3. 链式验证器
```typescript
validateParams(params)
  .required(['symbol', 'strategy_id'])
  .types({ symbol: 'string', limit: 'number' })
  .enum('action', ['single', 'batch', 'pipeline'])
  .range('limit', 1, 100)
  .validate(); // 抛出错误或通过
```

#### 4. 工具统计
```typescript
getToolStatsReport() // 获取所有工具的调用统计
resetToolStats(toolName?) // 重置统计
```

**统计指标**:
- `totalCalls` - 总调用次数
- `successCalls` - 成功次数
- `failureCalls` - 失败次数
- `totalDuration` - 累计耗时
- `lastCallAt` - 最后调用时间
- `lastError` - 最后错误消息

**使用示例**:
```typescript
export const myTool = {
  name: "my_tool",
  execute: async (toolCallId, params) => {
    return wrapToolExecution(
      async () => {
        // 参数验证
        validateParams(params)
          .required(['symbol'])
          .types({ symbol: 'string' })
          .validate();

        // 工具逻辑
        const result = await doSomething(params);
        return result;
      },
      {
        toolName: "my_tool",
        enablePerformanceMonitoring: true,
        errorSuggestion: "请检查参数格式"
      }
    );
  }
};
```

---

### 🟡 任务 4: 拆分 quant-cli-tool（进行中）

**目标**: 将 1472行的 quant-cli-tool 拆分为 8 个领域工具

#### 拆分方案

| 领域工具 | 命令数 | 预计行数 | 状态 |
|---------|--------|---------|------|
| `market-cli-tool` | 12个 | ~200行 | ✅ 已创建 |
| `stock-cli-tool` | 5个 | ~150行 | ⏳ 待创建 |
| `financial-cli-tool` | 7个 | ~180行 | ⏳ 待创建 |
| `signal-cli-tool` | 4个 | ~120行 | ⏳ 待创建 |
| `analysis-cli-tool` | 7个 | ~180行 | ⏳ 待创建 |
| `backtest-cli-tool` | 3个 | ~100行 | ⏳ 待创建 |
| `watchlist-cli-tool` | 5个 | ~150行 | ⏳ 待创建 |
| `sentiment-cli-tool` | 8个 | ~180行 | ⏳ 待创建 |

#### 已完成: market-cli-tool

**文件**: `src/infrastructure/tools/cli/market-cli-tool.ts`

**包含的命令** (12个):
- `market.overview` - 指数概览
- `market.index_history` - 指数历史数据
- `market.sectors` - 行业板块列表
- `market.concept_stocks` - 概念股成分股
- `market.concepts` - 概念板块列表
- `market.macro` - 宏观指标
- `market.north_flow` - 北向资金
- `market.sector_flow` - 行业资金流向
- `market.margin` - 融资融券
- `market.news` - 市场新闻
- `market.hot_stocks` - 热搜股票
- `market.sentiment` - 市场情绪

**特性**:
- ✅ 集成 `wrapToolExecution` 错误处理
- ✅ 集成性能监控
- ✅ 自动参数验证
- ✅ 统一的错误提示

**代码结构**:
```typescript
// 1. 命令定义（类型安全）
const MARKET_COMMANDS: Record<string, CommandRule> = { ... };

// 2. 工具定义（TypeBox schema）
export const marketCliTool: ToolDefinition = {
  name: "market_cli",
  parameters: Type.Object({ ... }),
  execute: async (_toolCallId, input) => {
    return wrapToolExecution(
      async () => {
        // 命令逻辑
      },
      { toolName: "market_cli", ... }
    );
  }
};
```

---

## 完成情况

### 代码统计

| 指标 | 完成 | 目标 | 进度 |
|------|------|------|------|
| 新建文件 | 3个 | 10个 | 30% |
| 新增代码 | ~1200行 | ~2000行 | 60% |
| 格式化函数 | 7个 | 7个 | 100% |
| 验证函数 | 5个 | 5个 | 100% |
| 领域工具 | 1个 | 8个 | 12.5% |

### 影响评估

**立即收益**:
- ✅ 所有新工具都将有统一的输出格式
- ✅ 所有新工具都有自动的错误处理
- ✅ 自动的性能监控和统计
- ✅ 更好的错误提示和调试信息

**长期收益**:
- 🔄 降低工具维护成本（小文件更易维护）
- 🔄 提高代码复用性（格式化和验证函数）
- 🔄 改善用户体验（一致的输出格式）
- 🔄 更快的工具加载速度（按需加载）

---

## 下一步行动

### 立即完成（今天）

1. **继续拆分 quant-cli-tool**
   - [ ] 创建 `stock-cli-tool.ts`
   - [ ] 创建 `financial-cli-tool.ts`
   - [ ] 创建 `signal-cli-tool.ts`
   - [ ] 创建 `analysis-cli-tool.ts`
   - [ ] 创建 `backtest-cli-tool.ts`
   - [ ] 创建 `watchlist-cli-tool.ts`
   - [ ] 创建 `sentiment-cli-tool.ts`

2. **更新工具注册**
   - [ ] 在 `src/infrastructure/tools/index.ts` 中注册新工具
   - [ ] 保留原 `quant_cli` 作为委托工具（向后兼容）

3. **验证编译**
   - [ ] 修复类型错误
   - [ ] 确保所有工具正常导入

### 本周完成

4. **迁移现有工具到新格式**
   - [ ] 选择 2-3 个高频工具
   - [ ] 应用 `wrapToolExecution`
   - [ ] 应用统一格式化函数

5. **补充测试用例**
   - [ ] 测试 `output-formatters.ts`
   - [ ] 测试 `error-handler.ts`
   - [ ] 测试新的领域工具

6. **更新文档**
   - [ ] 添加工具开发指南
   - [ ] 添加格式化函数使用示例
   - [ ] 更新 CLAUDE.md

---

## 技术亮点

### 1. 类型安全的命令定义
```typescript
const COMMANDS: Record<string, CommandRule> = {
  "market.overview": {
    domain: "market",
    action: "overview",
    description: "...",
    params: {},
    example: {}
  }
};
```

### 2. 自动参数验证
```typescript
validateParams(params)
  .required(['symbol'])
  .types({ limit: 'number' })
  .range('limit', 1, 100)
  .validate();
```

### 3. 性能监控集成
```typescript
wrapToolExecution(fn, {
  toolName: "my_tool",
  enablePerformanceMonitoring: true,
  slowToolThreshold: 5000
});
// 自动记录: [Performance] my_tool: 234ms
// 慢工具告警: [SlowTool] my_tool took 6234ms
```

### 4. 统一错误格式
```typescript
❌ 执行失败

工具：market_cli
命令：market.overview

错误：网络请求超时

💡 建议：请检查 quantsys-v2 服务是否正常运行
```

---

## 遇到的问题和解决

### 问题 1: ToolResult 类型导入失败
**错误**: `Module '@mariozechner/pi-coding-agent' has no exported member 'ToolResult'`

**解决**: 在 error-handler.ts 中定义本地 ToolResult 接口
```typescript
export interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
  details?: any;
}
```

### 问题 2: 命令数量统计
**挑战**: quant-cli-tool 中有100+个命令，如何合理拆分？

**解决**: 按 domain 前缀分组，统计各领域命令数量：
- market: 12个
- sentiment: 8个
- financial: 7个
- analysis: 7个
- 其他: 60+个

---

## 相关文档

- [工具系统优化分析报告](./2026-06-02-agent-tools-optimization-analysis.md)
- [quant_cli策略命令清理报告](./2026-06-02-quant-cli-strategy-cleanup.md)
- [CLAUDE.md更新日志](./2026-06-02-claude-md-update-log.md)

---

**报告生成时间**: 2026-06-02  
**下次更新**: 完成全部8个领域工具后  
**预计完成时间**: 2026-06-02 晚上
