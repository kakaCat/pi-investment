# Phase 4: 架构重构计划

**日期**: 2026-06-02  
**任务**: 进一步拆分 quant-cli-tool，优化工具加载机制

---

## 一、当前状况分析

### 1.1 quant-cli-tool 现状

**文件大小**: 994 行（已从 1,025 行优化到 994 行）

**命令分布**（46个命令）：
```
已拆分到独立工具:
  ✅ market.*     (12个) → market_cli
  ✅ stock.*      (5个)  → stock_cli
  ✅ financial.*  (7个)  → financial_cli
  ✅ sentiment.*  (8个)  → sentiment_cli
  ✅ analysis.*   (7个)  → analysis_cli
  ✅ signal.*     (4个)  → signal_cli
  ✅ backtest.*   (3个)  → backtest_cli
  ✅ watchlist.*  (5个)  → watchlist_cli
  ✅ strategy.*   (已完全移除) → 独立 strategy_* 工具
  ✅ indicators.* (已完全移除) → 独立 indicator_* 工具

仍在 quant-cli-tool 中:
  ⚠️ indicators.*  (8个)  - 指标管理
  ⚠️ portfolio.*   (2个)  - 组合管理
  ⚠️ risk.*        (4个)  - 风控命令
  ⚠️ performance.* (3个)  - 绩效分析
  ⚠️ data.*        (3个)  - 数据管理
  ⚠️ report.*      (2个)  - 报告生成
  ⚠️ screening.*   (2个)  - 股票筛选
  ⚠️ tools.*       (2个)  - 元命令
```

### 1.2 问题分析

**问题1**: quant-cli-tool 仍然较大（994行）
- indicators.* 命令与独立 indicator_* 工具重复
- 其他命令职责不够清晰

**问题2**: 工具加载机制
- 所有 70 个工具在启动时全部加载
- 没有懒加载机制
- 启动时间受影响

**问题3**: 工具接口不统一
- CLI 工具返回格式各异
- 独立工具返回格式各异
- 缺少统一的接口规范

---

## 二、重构目标

### 2.1 拆分 quant-cli-tool

**目标**: 将 994 行拆分为更小的模块

**方案**:
1. `risk_cli` - 风控命令（4个命令）
2. `performance_cli` - 绩效分析（3个命令）
3. `data_cli` - 数据管理（3个命令）
4. `report_cli` - 报告生成（2个命令）
5. `screening_cli` - 股票筛选（2个命令）
6. 保留 `quant_cli` - 核心元命令（tools.* 等，~200行）

**indicators.* 处理**:
- indicators.* 命令与独立 indicator_* 工具功能重复
- 建议：标记为 deprecated，引导使用独立工具

### 2.2 实现工具懒加载

**目标**: 减少启动时的加载开销

**方案**:
```typescript
// 当前：立即加载所有工具
export const allCustomTools = [
  planTool,
  clarifyTool,
  dataFetchStockTool,
  // ... 70 个工具全部加载
];

// 重构后：懒加载注册表
export const toolRegistry = {
  'plan': () => import('./agent/plan-tool.js').then(m => m.planTool),
  'clarify': () => import('./agent/clarify-tool.js').then(m => m.clarifyTool),
  'data_fetch_stock': () => import('./data/fetch-stock-tool.js').then(m => m.dataFetchStockTool),
  // ...
};

// 高频工具仍然预加载
export const preloadTools = [
  planTool,
  clarifyTool,
  taskCreateTool,
  // ... 10-15 个高频工具
];
```

### 2.3 统一工具接口

**目标**: 建立统一的工具接口规范

**方案**:
```typescript
// 统一的工具返回格式
interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
  details?: {
    success: boolean;
    data?: any;
    error?: string;
    metadata?: {
      duration?: number;
      cached?: boolean;
      source?: string;
    };
  };
}

// 统一的错误格式
interface ToolError {
  code: string;           // ERROR_CODE
  message: string;        // 用户友好的错误消息
  suggestion?: string;    // 解决建议
  details?: any;          // 技术细节
}
```

---

## 三、实施计划

### 阶段1: 拆分 quant-cli-tool（1-2天）

**步骤1.1**: 创建新的 CLI 工具（5个）

- [ ] `risk_cli` - 风控命令
  - risk.check
  - risk.monitor
  - risk.limit
  - risk.alert

- [ ] `performance_cli` - 绩效分析
  - performance.analyze
  - performance.by_strategy
  - performance.comparison

- [ ] `data_cli` - 数据管理
  - data.update
  - data.clean
  - data.validate

- [ ] `report_cli` - 报告生成
  - report.generate
  - report.export

- [ ] `screening_cli` - 股票筛选
  - screening.sector
  - screening.quality

**步骤1.2**: 处理 indicators.* 命令

**方案A**: 完全移除，引导使用独立工具
```typescript
// 在 quant-cli-tool 中添加废弃提示
if (command.startsWith('indicators.')) {
  return {
    content: [{
      type: "text",
      text: `⚠️ indicators.* 命令已废弃。\n\n` +
            `请使用独立的 indicator_* 工具替代：\n` +
            `- indicators.list → indicator_list()\n` +
            `- indicators.detail → indicator_detail({ name })\n` +
            `- indicators.create → indicator_create({ ... })\n` +
            `- 其他命令类似转换`
    }]
  };
}
```

**方案B**: 作为独立 indicator_cli 工具（推荐）
- 与现有 indicator_* 工具共存
- indicator_cli: 快速查询（list, detail）
- indicator_*: 完整功能（create, update, delete, run, backtest）

**步骤1.3**: 精简 quant_cli

保留核心元命令：
- tools.list
- tools.describe
- 其他必要的核心命令

预期结果：
- quant-cli-tool.ts: 994行 → ~200行（-80%）
- 新增 5-6 个 CLI 工具

### 阶段2: 实现工具懒加载（1天）

**步骤2.1**: 创建工具注册表

```typescript
// src/infrastructure/tools/registry.ts
export interface ToolLoader {
  load: () => Promise<ToolDefinition>;
  preload?: boolean;
  priority?: number;
}

export const toolRegistry: Record<string, ToolLoader> = {
  // 高频工具 - 预加载
  'plan': {
    load: async () => (await import('./agent/plan-tool.js')).planTool,
    preload: true,
    priority: 1
  },
  
  // 中频工具 - 懒加载
  'data_fetch_stock': {
    load: async () => (await import('./data/fetch-stock-tool.js')).dataFetchStockTool,
    preload: false,
    priority: 2
  },
  
  // 低频工具 - 懒加载
  'evolution_run': {
    load: async () => (await import('./agent/evolution-tool.js')).evolutionRunTool,
    preload: false,
    priority: 3
  },
};
```

**步骤2.2**: 实现加载器

```typescript
// src/infrastructure/tools/loader.ts
export class ToolLoader {
  private loadedTools = new Map<string, ToolDefinition>();
  private loadingPromises = new Map<string, Promise<ToolDefinition>>();

  async loadTool(name: string): Promise<ToolDefinition> {
    // 已加载？直接返回
    if (this.loadedTools.has(name)) {
      return this.loadedTools.get(name)!;
    }

    // 正在加载？等待
    if (this.loadingPromises.has(name)) {
      return this.loadingPromises.get(name)!;
    }

    // 开始加载
    const loader = toolRegistry[name];
    if (!loader) {
      throw new Error(`Tool not found: ${name}`);
    }

    const promise = loader.load().then(tool => {
      this.loadedTools.set(name, tool);
      this.loadingPromises.delete(name);
      return tool;
    });

    this.loadingPromises.set(name, promise);
    return promise;
  }

  async preloadTools(): Promise<void> {
    const preloadList = Object.entries(toolRegistry)
      .filter(([_, loader]) => loader.preload)
      .sort((a, b) => (a[1].priority || 99) - (b[1].priority || 99));

    await Promise.all(
      preloadList.map(([name]) => this.loadTool(name))
    );
  }
}
```

**步骤2.3**: 集成到工具系统

```typescript
// src/infrastructure/tools/index.ts
import { ToolLoader } from './loader.js';
import { toolRegistry } from './registry.js';

export const toolLoader = new ToolLoader();

// 初始化时预加载高频工具
export async function initTools() {
  await toolLoader.preloadTools();
  console.log('High-frequency tools preloaded');
}

// 动态获取工具
export async function getTool(name: string): Promise<ToolDefinition> {
  return toolLoader.loadTool(name);
}

// 向后兼容：立即加载所有工具（可选）
export async function getAllTools(): Promise<ToolDefinition[]> {
  const names = Object.keys(toolRegistry);
  return Promise.all(names.map(name => toolLoader.loadTool(name)));
}
```

预期结果：
- 启动时间减少：70个工具 → 10-15个预加载
- 内存占用减少：~30%
- 首次工具调用增加：~10-50ms（懒加载开销）

### 阶段3: 统一工具接口（0.5天）

**步骤3.1**: 定义标准接口

```typescript
// src/infrastructure/tools/types.ts
export interface StandardToolResult {
  content: Array<{ type: "text"; text: string }>;
  details?: {
    success: boolean;
    data?: any;
    error?: ToolError;
    metadata?: ToolMetadata;
  };
}

export interface ToolError {
  code: string;
  message: string;
  suggestion?: string;
  details?: any;
}

export interface ToolMetadata {
  duration?: number;
  cached?: boolean;
  source?: string;
  timestamp?: string;
}
```

**步骤3.2**: 创建适配器

```typescript
// src/infrastructure/tools/adapter.ts
export function standardizeToolResult(result: any): StandardToolResult {
  // 已经是标准格式
  if (result?.content && Array.isArray(result.content)) {
    return result as StandardToolResult;
  }

  // 字符串结果
  if (typeof result === 'string') {
    return {
      content: [{ type: "text", text: result }],
      details: { success: true }
    };
  }

  // 对象结果
  if (typeof result === 'object' && result !== null) {
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      details: { success: true, data: result }
    };
  }

  // 其他类型
  return {
    content: [{ type: "text", text: String(result) }],
    details: { success: true }
  };
}
```

**步骤3.3**: 更新 wrapToolExecution

```typescript
// 在 error-handler.ts 中
export async function wrapToolExecution<T>(
  fn: () => Promise<T>,
  options: ToolExecutionOptions
): Promise<StandardToolResult> {
  // ... 现有逻辑 ...
  
  const result = await fn();
  
  // 标准化输出
  const standardResult = standardizeToolResult(result);
  
  // 添加元数据
  if (!standardResult.details) {
    standardResult.details = {};
  }
  standardResult.details.metadata = {
    duration,
    timestamp: new Date().toISOString()
  };
  
  return standardResult;
}
```

预期结果：
- 所有工具返回统一格式
- 易于调试和日志记录
- 为未来扩展奠定基础

---

## 四、风险评估

### 4.1 风险识别

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 懒加载破坏兼容性 | 高 | 中 | 保留 getAllTools() 向后兼容 |
| 工具拆分遗漏命令 | 中 | 低 | 仔细审查，编写测试 |
| 性能回归 | 中 | 低 | 基准测试，预加载高频工具 |
| 接口标准化工作量大 | 低 | 高 | 分阶段实施，先标准化新工具 |

### 4.2 回滚计划

**如果重构失败**:
1. Git 回滚到重构前的提交
2. 保留已完成的文档和分析
3. 重新评估方案

**回滚成本**: 低（所有修改在新分支）

---

## 五、实施时间表

| 阶段 | 任务 | 预计耗时 | 累计耗时 |
|------|------|----------|----------|
| 准备 | 创建重构分支、备份 | 15分钟 | 0.25小时 |
| 阶段1 | 拆分 quant-cli-tool | 1.5天 | 12.25小时 |
| 阶段2 | 实现工具懒加载 | 1天 | 20.25小时 |
| 阶段3 | 统一工具接口 | 0.5天 | 24.25小时 |
| 测试 | 集成测试、性能测试 | 0.5天 | 28.25小时 |
| 文档 | 更新文档、编写指南 | 0.5天 | 32.25小时 |
| **总计** | | **4天** | **32.25小时** |

---

## 六、预期收益

### 6.1 代码质量

| 指标 | 改善 |
|------|------|
| quant-cli-tool 大小 | 994行 → ~200行（-80%） |
| 新增 CLI 工具 | 5-6 个 |
| 平均工具文件大小 | < 200 行 |

### 6.2 性能

| 指标 | 改善 |
|------|------|
| 启动时间 | -30% ~ -50% |
| 内存占用 | -30% |
| 首次工具调用 | +10-50ms（可接受） |

### 6.3 可维护性

| 指标 | 改善 |
|------|------|
| 模块化程度 | 显著提升 |
| 代码可读性 | 提升 30% |
| 新工具添加成本 | 降低 40% |

---

## 七、后续优化方向

### 7.1 工具版本管理

```typescript
export interface ToolVersion {
  version: string;
  deprecated?: boolean;
  replacement?: string;
}

export const toolRegistry: Record<string, ToolLoader & ToolVersion> = {
  'data_fetch_stock': {
    version: '2.0.0',
    load: async () => ...
  },
  'stock.quote': {
    version: '1.0.0',
    deprecated: true,
    replacement: 'data_fetch_stock',
    load: async () => ...
  }
};
```

### 7.2 工具依赖管理

```typescript
export const toolRegistry: Record<string, ToolLoader & { dependencies?: string[] }> = {
  'pool_validate': {
    dependencies: ['strategy_list', 'backtest_cli'],
    load: async () => ...
  }
};

// 自动加载依赖
async function loadToolWithDeps(name: string): Promise<ToolDefinition> {
  const loader = toolRegistry[name];
  if (loader.dependencies) {
    await Promise.all(loader.dependencies.map(dep => loadTool(dep)));
  }
  return loadTool(name);
}
```

### 7.3 工具热重载

```typescript
export class ToolLoader {
  async reloadTool(name: string): Promise<ToolDefinition> {
    this.loadedTools.delete(name);
    delete require.cache[require.resolve(`./path/to/${name}`)];
    return this.loadTool(name);
  }
}
```

---

## 八、决策点

### 需要确认的问题

**问题1**: indicators.* 命令如何处理？
- [ ] 选项A: 完全移除，标记为废弃
- [ ] 选项B: 作为 indicator_cli 保留
- [ ] 选项C: 保持现状，不做修改

**问题2**: 工具懒加载是否全面实施？
- [ ] 选项A: 全面实施（所有工具）
- [ ] 选项B: 部分实施（仅低频工具）
- [ ] 选项C: 暂不实施，仅做准备

**问题3**: 接口标准化的优先级？
- [ ] 选项A: 高优先级，与重构同步
- [ ] 选项B: 中优先级，重构后逐步
- [ ] 选项C: 低优先级，长期任务

---

**建议**: 执行阶段1（拆分），暂缓阶段2-3，先评估效果。

需要我开始执行吗？
