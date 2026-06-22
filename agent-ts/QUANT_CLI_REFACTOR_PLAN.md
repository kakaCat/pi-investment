# quantCliTool 拆解方案

## 现状分析

### quantCliTool 基本信息
- **文件**: [src/infrastructure/tools/core/quant-cli-tool.ts](src/infrastructure/tools/core/quant-cli-tool.ts)
- **代码行数**: 716 行
- **命令数量**: 15 个
- **状态**: 标记为"向后兼容，逐步废弃"

### 命令清单

| 命令 | 功能 | 状态 | 建议 |
|------|------|------|------|
| `tools.list` | 列出所有命令 | ⚠️ 元命令 | 保留或废弃 |
| `tools.describe` | 查看命令参数定义 | ⚠️ 元命令 | 保留或废弃 |
| `screening.sector` | 按行业筛选股票 | ❌ 未拆分 | **需要拆分** |
| `screening.quality` | 质量评分筛选 | ❌ 未拆分 | **需要拆分** |
| `jobs.list` | 查询异步任务 | ❌ 未拆分 | **需要拆分** |
| `scheduler.tasks` | 查询定时任务 | ✅ 已有 schedulerManageTool | 可删除 |
| `sector.aggregate` | 行业聚合分析 | ❌ 未拆分 | **需要拆分** |
| `benchmark.compare` | 基准比较 | ❌ 未拆分 | **需要拆分** |
| `watch.price_alert` | 价格预警 | ❌ 未拆分 | **需要拆分** |
| `watchlist.check` | 检查自选股 | ✅ 已有 watchlistCliTool | 可删除 |
| `stress.test` | 交易验证 | ❌ 未拆分 | **需要拆分** |
| `report.daily` | 生成日报 | ❌ 未拆分 | **需要拆分** |
| `report.read_daily` | 读取日报 | ❌ 未拆分 | **需要拆分** |
| `calibrate.run` | 置信度校准 | ❌ 未拆分 | **需要拆分** |
| `training.reports` | 训练报告列表 | ❌ 未拆分 | **需要拆分** |

---

## 拆解策略

### 阶段 1: 创建新的独立工具（优先级 High）

#### 1. screening-tool.ts - 股票筛选工具
**命令**: `screening.sector`, `screening.quality`

```typescript
// src/infrastructure/tools/screening/screening-tool.ts
export const screeningTool: ToolDefinition = {
  name: "screening",
  label: "股票筛选",
  description: "按行业、质量评分筛选股票",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("sector"),
      Type.Literal("quality")
    ]),
    sector: Type.String({ description: "行业板块名称" }),
    min_roe: Type.Optional(Type.Number()),
    max_pe: Type.Optional(Type.Number()),
    min_score: Type.Optional(Type.Integer()),
    limit: Type.Optional(Type.Integer({ default: 20 }))
  }),
  execute: async (_toolCallId, params) => {
    // 调用 runQuantV2
  }
};
```

#### 2. sector-analysis-tool.ts - 行业分析工具
**命令**: `sector.aggregate`

```typescript
// src/infrastructure/tools/analysis/sector-analysis-tool.ts
export const sectorAnalysisTool: ToolDefinition = {
  name: "sector_analysis",
  label: "行业分析",
  description: "按行业或板块聚合估值、质量、负债率和信号数量",
  parameters: Type.Object({
    sector_field: Type.Optional(Type.Union([
      Type.Literal("sector"),
      Type.Literal("industry")
    ])),
    limit: Type.Optional(Type.Integer({ default: 20 }))
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("sector", "aggregate", params);
  }
};
```

#### 3. benchmark-compare-tool.ts - 基准比较工具
**命令**: `benchmark.compare`

```typescript
// src/infrastructure/tools/analysis/benchmark-compare-tool.ts
export const benchmarkCompareTool: ToolDefinition = {
  name: "benchmark_compare",
  label: "基准比较",
  description: "比较策略收益与基准收益，计算 alpha 和相对表现",
  parameters: Type.Object({
    strategy_return: Type.Number(),
    benchmark_return: Type.Number(),
    strategy_name: Type.Optional(Type.String()),
    benchmark_name: Type.Optional(Type.String()),
    equity: Type.Optional(Type.String()),
    benchmark: Type.Optional(Type.String())
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("benchmark", "compare", params);
  }
};
```

#### 4. watch-alert-tool.ts - 价格监控预警
**命令**: `watch.price_alert`

```typescript
// src/infrastructure/tools/monitor/watch-alert-tool.ts
export const watchAlertTool: ToolDefinition = {
  name: "watch_price_alert",
  label: "价格预警",
  description: "校验股票价格是否触发上破、下破或涨跌幅预警",
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码" }),
    price: Type.Number({ description: "当前价格" }),
    above: Type.Optional(Type.Number()),
    below: Type.Optional(Type.Number()),
    change_pct: Type.Optional(Type.Number()),
    last_price: Type.Optional(Type.Number())
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("watch", "price-alert", params);
  }
};
```

#### 5. trade-verify-tool.ts - 交易验证工具
**命令**: `stress.test`

```typescript
// src/infrastructure/tools/trade/trade-verify-tool.ts
export const tradeVerifyTool: ToolDefinition = {
  name: "trade_verify",
  label: "交易验证",
  description: "对比实盘交易记录和回测交易记录，识别差异",
  parameters: Type.Object({
    trades_json: Type.String({ description: "实盘交易记录 JSON" }),
    backtest_json: Type.String({ description: "回测交易记录 JSON" })
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("trade", "verify", params);
  }
};
```

#### 6. daily-report-tool.ts - 日报管理工具
**命令**: `report.daily`, `report.read_daily`

```typescript
// src/infrastructure/tools/report/daily-report-tool.ts
export const dailyReportTool: ToolDefinition = {
  name: "daily_report",
  label: "日报管理",
  description: "生成或读取日度量化报告",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("generate"),
      Type.Literal("read")
    ]),
    date: Type.Optional(Type.String()),
    output_dir: Type.Optional(Type.String())
  }),
  execute: async (_toolCallId, params) => {
    if (params.action === "generate") {
      return await runQuantV2("report", "daily", params);
    } else {
      return await runQuantV2("report", "read-daily", params);
    }
  }
};
```

#### 7. async-jobs-tool.ts - 异步任务管理
**命令**: `jobs.list`

```typescript
// src/infrastructure/tools/core/async-jobs-tool.ts
export const asyncJobsTool: ToolDefinition = {
  name: "async_jobs",
  label: "异步任务管理",
  description: "查询异步任务列表和状态",
  parameters: Type.Object({
    action: Type.Optional(Type.Literal("list"))
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("jobs", "list", params);
  }
};
```

#### 8. calibrate-tool.ts - 置信度校准工具
**命令**: `calibrate.run`

```typescript
// src/infrastructure/tools/model/calibrate-tool.ts
export const calibrateTool: ToolDefinition = {
  name: "calibrate_confidence",
  label: "置信度校准",
  description: "运行置信度校准，计算各技术指标的 IC 和最优阈值",
  parameters: Type.Object({
    forward_days: Type.Optional(Type.Integer({ default: 5 })),
    return_threshold: Type.Optional(Type.Number({ default: 0.02 })),
    lookback_days: Type.Optional(Type.Integer({ default: 180 })),
    max_symbols: Type.Optional(Type.Integer({ default: 100 }))
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("calibrate", "run", params);
  }
};
```

#### 9. training-reports-tool.ts - 训练报告工具
**命令**: `training.reports`

```typescript
// src/infrastructure/tools/model/training-reports-tool.ts
export const trainingReportsTool: ToolDefinition = {
  name: "training_reports",
  label: "训练报告",
  description: "查询模型训练报告列表",
  parameters: Type.Object({
    action: Type.Optional(Type.Literal("list"))
  }),
  execute: async (_toolCallId, params) => {
    return await runQuantV2("training", "reports", params);
  }
};
```

---

### 阶段 2: 处理元命令（优先级 Low）

#### 选项 A: 完全删除
`tools.list` 和 `tools.describe` 是元命令，用于查询 quantCliTool 自身支持的命令。

**理由**:
- Agent 已经通过系统提示词知道所有可用工具
- 不需要运行时查询工具列表
- 删除后简化系统

**建议**: ✅ **删除**

#### 选项 B: 保留但重命名
如果需要保留查询后端 API 能力的功能，可以重命名为：
- `backend_commands_list` - 列出后端支持的所有命令
- `backend_command_info` - 查看后端命令的参数定义

---

### 阶段 3: 删除 quantCliTool（优先级 Medium）

完成所有命令拆分后：

1. **从 index.ts 删除注册**
```diff
- import { quantCliTool } from "./core/quant-cli-tool.js";
  
  export const allCustomTools = [
    // ...
-   quantCliTool,  // quant_cli - 原统一CLI工具（向后兼容，逐步废弃）
    // ...
  ];
```

2. **删除文件**
```bash
rm src/infrastructure/tools/core/quant-cli-tool.ts
```

3. **更新注释**
```diff
- // L3.5 策略（从 quant_cli 提取为独立工具）
+ // L3.5 策略工具
```

---

## 实施计划

### Week 1: 核心工具拆分
- [ ] 创建 `screening-tool.ts`
- [ ] 创建 `sector-analysis-tool.ts`
- [ ] 创建 `benchmark-compare-tool.ts`
- [ ] 创建 `watch-alert-tool.ts`
- [ ] 测试以上 4 个工具

### Week 2: 其他工具拆分
- [ ] 创建 `trade-verify-tool.ts`
- [ ] 创建 `daily-report-tool.ts`
- [ ] 创建 `async-jobs-tool.ts`
- [ ] 创建 `calibrate-tool.ts`
- [ ] 创建 `training-reports-tool.ts`
- [ ] 测试以上 5 个工具

### Week 3: 清理与验证
- [ ] 所有新工具注册到 `index.ts`
- [ ] 删除 `quantCliTool` 注册
- [ ] 删除 `quant-cli-tool.ts` 文件
- [ ] 全量测试
- [ ] 更新文档

---

## 文件结构

```
src/infrastructure/tools/
├── screening/
│   └── screening-tool.ts          # 新增
├── analysis/
│   ├── sector-analysis-tool.ts    # 新增
│   └── benchmark-compare-tool.ts  # 新增
├── monitor/
│   └── watch-alert-tool.ts        # 新增
├── trade/
│   └── trade-verify-tool.ts       # 新增
├── report/
│   └── daily-report-tool.ts       # 新增
├── core/
│   ├── async-jobs-tool.ts         # 新增
│   └── quant-cli-tool.ts          # 待删除
└── model/
    ├── calibrate-tool.ts          # 新增
    └── training-reports-tool.ts   # 新增
```

---

## 工具注册顺序

在 `index.ts` 的 `allCustomTools` 数组中，按以下顺序注册新工具：

```typescript
export const allCustomTools = [
  // ===== 高频 — 工作流核心 =====
  planTool,
  // ...

  // ===== 六层量化投资架构工具 =====
  // ...

  // ===== 筛选与分析工具 =====
  screeningTool,              // screening - 股票筛选（sector/quality）
  sectorAnalysisTool,         // sector_analysis - 行业聚合分析
  benchmarkCompareTool,       // benchmark_compare - 基准比较

  // ===== 监控与预警工具 =====
  watchAlertTool,             // watch_price_alert - 价格预警

  // ===== 交易验证工具 =====
  tradeVerifyTool,            // trade_verify - 交易记录验证

  // ===== 报告工具 =====
  dailyReportTool,            // daily_report - 日报生成/读取

  // ===== 模型工具 =====
  calibrateTool,              // calibrate_confidence - 置信度校准
  trainingReportsTool,        // training_reports - 训练报告查询

  // ===== 系统工具 =====
  asyncJobsTool,              // async_jobs - 异步任务管理

  // ...
];
```

---

## 代码复用

所有新工具都复用 `runQuantV2` 函数：

```typescript
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { formatMaybeLargeToolOutput } from "../shared/large-tool-output.js";

// 在 execute 中
const result = await runQuantV2(domain, action, params);
return formatMaybeLargeToolOutput(result);
```

---

## 测试策略

### 单元测试
每个新工具创建对应的测试文件：
```
screening-tool.test.ts
sector-analysis-tool.test.ts
benchmark-compare-tool.test.ts
...
```

### 集成测试
创建 `quant-cli-migration.test.ts`：
```typescript
describe('quantCliTool Migration', () => {
  it('screening.sector → screeningTool', async () => {
    // 对比新旧工具输出
  });

  it('sector.aggregate → sectorAnalysisTool', async () => {
    // 对比新旧工具输出
  });

  // ... 其他命令
});
```

---

## 迁移检查清单

- [ ] 所有 15 个命令已拆分为独立工具
- [ ] 新工具已注册到 `index.ts`
- [ ] 新工具有单元测试
- [ ] 集成测试通过
- [ ] 文档已更新
- [ ] `quantCliTool` 已从 `index.ts` 删除
- [ ] `quant-cli-tool.ts` 文件已删除
- [ ] 所有引用 `quant_cli` 的注释已更新
- [ ] 编译通过 `npm run build`
- [ ] 测试通过 `npm test`

---

## 风险评估

### 低风险
- ✅ 所有命令都是简单的参数验证 + `runQuantV2` 调用
- ✅ 逻辑清晰，易于拆分
- ✅ 无复杂的状态管理

### 中等风险
- ⚠️ 参数验证逻辑需要迁移到新工具
- ⚠️ 错误提示可能需要调整

### 缓解措施
1. 创建共享的参数验证工具
2. 逐个工具拆分并测试
3. 保留 `quantCliTool` 直到所有新工具验证完成

---

## 预期收益

### 代码质量
- **减少代码行数**: 716 行 → 每个工具约 50-80 行
- **提高可维护性**: 每个工具职责单一
- **更好的类型安全**: 每个工具有独立的参数类型定义

### 用户体验
- **更清晰的工具名称**: `screening` vs `quant_cli command="screening.sector"`
- **更好的提示词**: 每个工具有明确的 description
- **更快的响应**: Agent 不需要解析 command 字符串

### 系统维护
- **降低耦合**: 删除 716 行的巨型工具
- **易于扩展**: 新增功能只需添加新工具
- **便于测试**: 每个工具独立测试

---

## 总结

**总工作量**: 约 15-20 小时
- 工具创建: 9 个工具 × 1 小时 = 9 小时
- 测试编写: 9 个测试 × 0.5 小时 = 4.5 小时
- 集成测试: 2 小时
- 文档更新: 1 小时
- 清理验证: 2 小时
- 缓冲时间: 2.5 小时

**推荐度**: ⭐⭐⭐⭐⭐ (5/5)

拆解 quantCliTool 将显著提升代码质量和可维护性，值得投入！
