# src/infrastructure/tools 优化建议

**日期**: 2026-06-03  
**当前状态**: ✅ 编译成功，但有优化空间

---

## 📊 现状分析

### 代码规模
- **文件总数**: 91 个 TypeScript 文件
- **测试文件**: 22 个测试文件（测试覆盖率 24%）
- **目录大小**: 800KB
- **工具总数**: 68 个 Agent 工具

### 测试状态
- ❌ 多个测试套件失败（skill-guard, strategy-optimize, backup-service 等）
- ⚠️ 测试覆盖率偏低（仅 24% 的文件有测试）

### 代码质量
- ✅ 无 TODO/FIXME 标记（代码维护较好）
- ⚠️ 最大文件 995 行（quant-cli-tool.ts）
- ⚠️ 多个文件超过 300 行

---

## 🎯 优化建议

### 1. **修复失败的测试** ⭐⭐⭐ (高优先级)

**问题**:
- `skill-guard.test.ts` - 技能授权验证失败
- `strategy/optimize-tool.test.ts` - API 调用参数不匹配
- `intelligence/comparator.test.ts` - 大盘比较逻辑错误
- `operations/backup-service.test.ts` - 备份服务断言失败

**行动**:
```bash
# 逐个修复测试
npm test -- skill-guard.test.ts
npm test -- strategy/optimize-tool.test.ts
```

**影响**: 提高代码可靠性，防止回归

---

### 2. **拆分大文件** ⭐⭐⭐ (高优先级)

**问题文件**:
- `core/quant-cli-tool.ts` (995 行) - 包含 46 个命令
- `agent/backend-control-tool.ts` (820 行) - 服务管理逻辑复杂
- `shared/error-handler.ts` (459 行)
- `shared/output-formatters.ts` (449 行)

**建议拆分**:

#### quant-cli-tool.ts (995行 → 300行以内)
```typescript
// 当前结构
quant-cli-tool.ts (995行)
  - 46个命令定义
  - 参数验证
  - API调用

// 优化后结构
core/
  quant-cli-tool.ts (200行)  // 主入口
  commands/
    indicators.ts             // 8个指标命令
    portfolio.ts              // 2个组合命令
    risk.ts                   // 4个风控命令
    performance.ts            // 3个绩效命令
    data.ts                   // 3个数据命令
    report.ts                 // 2个报告命令
```

**收益**:
- 每个文件职责单一，易维护
- 减少 merge 冲突
- 提高代码可读性

---

### 3. **增加测试覆盖率** ⭐⭐ (中优先级)

**当前覆盖情况**:
```
测试文件: 22/91 (24%)
未测试的关键工具:
  - data/fetch-*.ts (4个数据工具)
  - factor/*.ts (2个因子工具)
  - pool/*.ts (2个股票池工具)
  - strategy/*.ts (8个策略工具中仅1个有测试)
  - indicator/*.ts (6个指标工具全部无测试)
```

**建议目标**: 50% 覆盖率

**优先测试**:
1. 数据层工具（data/）- 最底层，影响最广
2. 因子工具（factor/）- 量化核心
3. 策略工具（strategy/）- 业务关键

**示例测试框架**:
```typescript
// src/infrastructure/tools/data/fetch-stock-tool.test.ts
import { dataFetchQuoteTool } from './fetch-stock-tool';

describe('data_fetch_stock tool', () => {
  it('should fetch A-share stock price', async () => {
    const result = await dataFetchQuoteTool.execute('test', { symbol: '600519' });
    expect(result.content[0].text).toContain('price');
  });

  it('should reject invalid symbols', async () => {
    const result = await dataFetchQuoteTool.execute('test', { symbol: 'INVALID' });
    expect(result.content[0].text).toContain('不支持的股票代码');
  });
});
```

---

### 4. **统一错误处理模式** ⭐⭐ (中优先级)

**问题**:
- 部分工具使用 `wrapToolExecution`（CLI 工具）
- 部分工具手动构造 ToolResult（data 工具）
- 错误消息格式不一致

**建议**:
```typescript
// shared/tool-wrapper.ts
export function createTool<T>(config: {
  name: string;
  description: string;
  parameters: any;
  execute: (params: T) => Promise<any>;
  errorHint?: string;
}): ToolDefinition {
  return {
    name: config.name,
    description: config.description,
    parameters: config.parameters,
    execute: async (_toolCallId: string, params: any, _signal?: AbortSignal) => {
      return wrapToolExecution(
        () => config.execute(params),
        { 
          toolName: config.name,
          errorSuggestion: config.errorHint 
        }
      );
    }
  };
}

// 使用示例
export const dataFetchQuoteTool = createTool({
  name: "data_fetch_stock",
  description: "获取股票实时行情",
  parameters: stockParamsSchema,
  execute: async (params) => {
    // 业务逻辑
  },
  errorHint: "请检查股票代码格式"
});
```

**收益**:
- 统一的性能监控
- 统一的错误格式
- 减少样板代码

---

### 5. **优化工具注册顺序** ⭐ (低优先级)

**当前问题**:
```typescript
// index.ts 中的注册顺序
export const allCustomTools = [
  planTool,           // 高频
  clarifyTool,        // 高频
  taskCreateTool,     // 高频
  // ... 68 个工具混在一起
  compactTool,        // 低频
  browserTool         // 低频
];
```

**建议**:
- 按使用频率排序（已经部分实现）
- 添加清晰的分组注释
- 考虑 lazy loading（延迟加载低频工具）

```typescript
// 优化后
export const allCustomTools = [
  // === 核心工作流（使用频率 > 50%） ===
  planTool,
  clarifyTool,
  taskCreateTool,
  
  // === 数据查询（使用频率 30-50%） ===
  dataFetchQuoteTool,
  dataFetchKlineTool,
  
  // === 分析工具（使用频率 10-30%） ===
  factorCalculateTool,
  opportunityScanTool,
  
  // === 运维工具（使用频率 < 5%） ===
  compactTool,
  browserTool,
];
```

---

### 6. **添加工具性能监控** ⭐ (低优先级)

**当前状态**:
- `wrapToolExecution` 已记录耗时
- `tool-stats-manager` 已持久化统计
- ⚠️ 缺少可视化和告警

**建议**:
```typescript
// shared/performance-monitor.ts
export class ToolPerformanceMonitor {
  // 慢工具告警（超过阈值）
  async checkSlowTools(): Promise<string[]> {
    const stats = getStatsManager().getStats();
    return stats
      .filter(s => s.avgDuration > 5000)
      .map(s => `${s.toolName}: ${s.avgDuration}ms`);
  }

  // 失败率告警（超过20%）
  async checkHighFailureRate(): Promise<string[]> {
    const stats = getStatsManager().getStats();
    return stats
      .filter(s => s.successRate < 0.8)
      .map(s => `${s.toolName}: ${s.successRate * 100}% 成功率`);
  }

  // 生成周报
  async generateWeeklyReport(): Promise<string> {
    // Markdown 格式的性能报告
  }
}
```

**使用场景**:
- Agent 启动时检查慢工具
- 每周自动生成性能报告
- 失败率过高时主动告警

---

### 7. **清理已废弃服务** ⭐ (低优先级)

**当前状态**:
- `src/services/quant/` 目录仍保留
- 已从编译中排除，但占用代码库空间
- 可能误导新开发者

**建议时机**:
- 确认所有测试已迁移到 quantsys-v2
- 确认无任何代码依赖这些文件
- 建议 1 个月后（2026-07-03）执行清理

**清理计划**:
```bash
# 1. 归档到单独分支
git checkout -b archive/old-quant-services
git add src/services/quant/
git commit -m "archive: 保留旧 quant 服务作为历史参考"
git push origin archive/old-quant-services

# 2. 从主分支删除
git checkout main
git rm -r src/services/quant/backtest-engine.ts
git rm -r src/services/quant/signal-generator.ts
git rm -r src/services/quant/signal-arbiter-example.ts
git commit -m "refactor: 移除已迁移到 quantsys-v2 的旧服务"
```

---

### 8. **改进类型安全** ⭐ (低优先级)

**问题**:
- 部分工具参数使用 `any` 类型
- `wrapToolExecution` 返回类型不够精确

**建议**:
```typescript
// Before
execute: async (_toolCallId: string, input: any, _signal?: AbortSignal) => {
  const { command, params = {} } = input as { command: string; params?: Record<string, any> };
}

// After
interface CliToolInput {
  command: string;
  params?: Record<string, unknown>;
}

execute: async (_toolCallId: string, input: unknown, _signal?: AbortSignal) => {
  const validated = input as CliToolInput;
  const { command, params = {} } = validated;
}
```

---

## 📅 实施路线图

### Phase 1: 稳定性修复（1周内）
- [x] 修复编译错误（已完成）
- [ ] 修复所有失败的测试
- [ ] 验证核心工具功能正常

### Phase 2: 代码质量提升（2周内）
- [ ] 拆分 quant-cli-tool.ts
- [ ] 拆分 backend-control-tool.ts
- [ ] 统一错误处理模式
- [ ] 添加核心工具测试（data/, factor/）

### Phase 3: 长期维护（1月内）
- [ ] 提升测试覆盖率到 50%
- [ ] 添加性能监控和告警
- [ ] 清理已废弃服务
- [ ] 改进类型安全

---

## 💰 预估收益

| 优化项 | 工作量 | 收益 | ROI |
|--------|--------|------|-----|
| 修复测试 | 2天 | 高（稳定性） | ⭐⭐⭐ |
| 拆分大文件 | 3天 | 中（可维护性） | ⭐⭐ |
| 增加测试 | 5天 | 高（可靠性） | ⭐⭐⭐ |
| 统一错误处理 | 2天 | 中（一致性） | ⭐⭐ |
| 性能监控 | 1天 | 低（可观测性） | ⭐ |
| 清理废弃代码 | 0.5天 | 低（清洁度） | ⭐ |

**总工作量**: 约 13.5 天  
**推荐优先级**: 修复测试 > 增加测试 > 拆分大文件

---

## 🔗 相关资源

- [工具开发指南](docs/tools/tool-development-guide.md)
- [测试最佳实践](https://jestjs.io/docs/getting-started)
- [TypeScript 严格模式](https://www.typescriptlang.org/tsconfig#strict)
