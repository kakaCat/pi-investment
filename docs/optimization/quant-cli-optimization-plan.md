# quant_cli 优化实施方案

**日期**: 2026-06-03  
**当前状态**: 1040 行，42 个命令，已分类

---

## 🎯 优化目标

1. **保持功能完整** - 所有 42 个命令都保留
2. **提升可维护性** - 降低代码复杂度
3. **改善性能** - 优化高频命令
4. **增强文档** - 更好的使用指南

---

## 📋 推荐的优化方案（按优先级）

### Phase 1: 文档优化（1天，高ROI）⭐⭐⭐⭐⭐

**当前问题**:
- description 字符串过长（552行有一个超长字符串）
- 缺少命令使用示例
- 没有高频命令快速参考

**优化方案**:

#### 1.1 添加 README.md（2小时）
```markdown
# quant_cli 使用指南

## 快速开始

### 高频命令（每天使用）
- `data.update` - 更新数据
- `data.status` - 检查数据状态
- `risk.trade_check` - 交易前风控
- `performance.by_strategy` - 查看策略表现

### 常用命令（每周使用）
- `portfolio.optimize` - 组合优化
- `screening.sector` - 行业筛选
- `factor.list` - 查看可用因子

### 专业命令（按需使用）
- `factor.fama_french_5` - FF五因子模型
- `timeseries.arima` - ARIMA预测
- `calibrate.run` - 置信度校准

## 命令分类

### 数据管理（高频）
- data.status - 数据库状态
- data.update - 统一更新入口
- data.update_klines - 批量更新K线
- data.full_status - 完整性检查

### 风险控制（高频）
- risk.check - 综合风控
- risk.trade_check - 交易前检查
- risk.position_size - Kelly仓位
- risk.stop_loss - 止损计算

[... 其他分类]

## 使用示例

### 场景1: 每日数据更新
```bash
# 更新所有数据
quant_cli({ command: "data.update", params: { source: "all" } })

# 检查数据状态
quant_cli({ command: "data.status" })
```

### 场景2: 交易前风控检查
```bash
# 检查单笔交易
quant_cli({ 
  command: "risk.trade_check", 
  params: { 
    symbol: "600519", 
    action: "buy", 
    price: 1800, 
    shares: 100 
  } 
})
```

### 场景3: 组合优化
```bash
# 优化组合权重
quant_cli({ 
  command: "portfolio.optimize", 
  params: { 
    symbols: ["600000", "000001", "600519"],
    method: "max_sharpe",
    risk_free_rate: 0.03
  } 
})
```
```

**收益**: 
- 用户学习成本 ⬇️ 50%
- 使用错误率 ⬇️ 30%
- 文档查询时间 ⬇️ 60%

---

### Phase 2: 代码结构优化（3天，中ROI）⭐⭐⭐⭐

**当前问题**:
- COMMANDS 对象包含 42 个命令定义（~600 行）
- 参数验证逻辑混在主文件中
- 难以快速找到特定命令

**优化方案**:

#### 2.1 按功能拆分命令定义（2天）

```typescript
// 文件结构
src/infrastructure/tools/core/
  quant-cli-tool.ts          // 主入口（200行）
  commands/
    data-commands.ts          // 数据管理命令（4个）
    risk-commands.ts          // 风险控制命令（4个）
    portfolio-commands.ts     // 组合优化命令（2个）
    performance-commands.ts   // 性能分析命令（3个）
    factor-commands.ts        // 因子计算命令（5个）
    timeseries-commands.ts    // 时间序列命令（4个）
    trading-commands.ts       // 订单交易命令（4个）
    screening-commands.ts     // 筛选工具命令（2个）
    monitoring-commands.ts    // 监控预警命令（7个）
    tools-commands.ts         // 工具命令（2个）

// quant-cli-tool.ts 主文件
import { DATA_COMMANDS } from './commands/data-commands.js';
import { RISK_COMMANDS } from './commands/risk-commands.js';
// ... 其他导入

const COMMANDS: Record<string, CommandRule> = {
  ...DATA_COMMANDS,
  ...RISK_COMMANDS,
  ...PORTFOLIO_COMMANDS,
  // ... 其他命令
};

// commands/data-commands.ts 示例
export const DATA_COMMANDS: Record<string, CommandRule> = {
  "data.status": {
    domain: "data",
    action: "status",
    description: "查看本地量化数据库状态。",
    params: { db_path: { type: "string" } },
    example: {},
  },
  // ... 其他 data 命令
};
```

**收益**:
- 主文件: 1040行 → ~200行 (-80%)
- 每个命令文件: 50-100行
- 易于维护和测试

**风险**: 中（需要重构导入）

---

#### 2.2 提取参数验证逻辑（1天）

```typescript
// commands/validators.ts
export const validateDataUpdateParams = (params: any) => {
  if (!params.source) {
    throw new Error("source 参数必填");
  }
  if (!["portfolio", "watchlist", "hs300", "all"].includes(params.source)) {
    throw new Error("source 必须是: portfolio, watchlist, hs300, all");
  }
};

export const validateRiskParams = (params: any) => {
  if (params.price <= 0) {
    throw new Error("price 必须大于0");
  }
  // ...
};

// 在命令中使用
"data.update": {
  // ...
  validate: validateDataUpdateParams,
}
```

**收益**: 
- 验证逻辑可重用
- 更容易测试
- 代码更清晰

---

### Phase 3: 性能优化（2天，中ROI）⭐⭐⭐

**当前问题**:
- 所有命令都通过同一个 execute 函数
- 没有命令级别的缓存
- 高频命令没有优化

**优化方案**:

#### 3.1 添加命令级缓存（1天）

```typescript
// shared/command-cache.ts
import LRU from 'lru-cache';

const commandCache = new LRU({
  max: 100,
  ttl: 1000 * 60 * 5, // 5分钟
});

export const getCachedResult = (command: string, params: any) => {
  const key = `${command}:${JSON.stringify(params)}`;
  return commandCache.get(key);
};

export const setCachedResult = (command: string, params: any, result: any) => {
  const key = `${command}:${JSON.stringify(params)}`;
  commandCache.set(key, result);
};

// 在 quant-cli-tool.ts 中使用
execute: async (_toolCallId, rawParams: any) => {
  const { command, params } = rawParams;
  
  // 检查缓存（仅对读命令）
  if (isReadOnlyCommand(command)) {
    const cached = getCachedResult(command, params);
    if (cached) return cached;
  }
  
  // 执行命令
  const result = await runQuantV2(command, params);
  
  // 缓存结果
  if (isReadOnlyCommand(command)) {
    setCachedResult(command, params, result);
  }
  
  return result;
}

// 只缓存这些读命令
const READ_ONLY_COMMANDS = [
  'data.status',
  'data.full_status',
  'factor.list',
  'performance.by_strategy',
  'orders.list',
  'trades.list',
];
```

**收益**:
- 高频命令响应速度 ⬆️ 80%
- 减少 quantsys-v2 负载

---

#### 3.2 添加命令执行统计（1天）

```typescript
// shared/command-stats.ts
export class CommandStats {
  private stats = new Map<string, {
    count: number;
    totalTime: number;
    errors: number;
  }>();

  record(command: string, duration: number, error?: boolean) {
    const stat = this.stats.get(command) || { count: 0, totalTime: 0, errors: 0 };
    stat.count++;
    stat.totalTime += duration;
    if (error) stat.errors++;
    this.stats.set(command, stat);
  }

  getTopCommands(n: number = 10) {
    return Array.from(this.stats.entries())
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, n);
  }

  getSlowestCommands(n: number = 10) {
    return Array.from(this.stats.entries())
      .map(([cmd, stat]) => ({
        command: cmd,
        avgTime: stat.totalTime / stat.count
      }))
      .sort((a, b) => b.avgTime - a.avgTime)
      .slice(0, n);
  }
}

// 在 execute 中使用
const stats = new CommandStats();

execute: async (_toolCallId, rawParams: any) => {
  const startTime = Date.now();
  let error = false;
  
  try {
    const result = await runQuantV2(command, params);
    return result;
  } catch (e) {
    error = true;
    throw e;
  } finally {
    const duration = Date.now() - startTime;
    stats.record(command, duration, error);
  }
}
```

**收益**:
- 识别性能瓶颈
- 优化高频命令
- 发现问题命令

---

### Phase 4: 错误处理优化（1天，高ROI）⭐⭐⭐⭐

**当前问题**:
- 错误消息不够友好
- 缺少常见错误的解决建议
- 没有错误分类

**优化方案**:

#### 4.1 友好的错误消息（0.5天）

```typescript
// shared/error-messages.ts
export const ERROR_MESSAGES = {
  INVALID_SYMBOL: (symbol: string) => ({
    error: `不支持的股票代码 "${symbol}"`,
    suggestion: "本系统仅支持A股（6位数字，如 600519）",
    examples: ["600000", "000001", "600519"]
  }),
  
  DATA_NOT_READY: (symbol: string) => ({
    error: `股票 ${symbol} 的数据尚未准备好`,
    suggestion: "请先运行数据更新命令",
    command: `quant_cli({ command: "data.update", params: { source: "all" } })`
  }),
  
  INVALID_PARAMS: (param: string, expected: string) => ({
    error: `参数 ${param} 无效`,
    suggestion: `期望值: ${expected}`,
    docs: "运行 tools.describe 查看完整参数说明"
  }),
};

// 使用
if (!isValidSymbol(symbol)) {
  return formatError(ERROR_MESSAGES.INVALID_SYMBOL(symbol));
}
```

**收益**:
- 用户自助解决问题 ⬆️ 60%
- 支持工作量 ⬇️ 40%

---

#### 4.2 错误分类和重试逻辑（0.5天）

```typescript
// shared/error-handler.ts
export enum ErrorType {
  VALIDATION_ERROR,    // 参数验证错误 - 不重试
  DATA_NOT_FOUND,      // 数据未找到 - 不重试
  NETWORK_ERROR,       // 网络错误 - 重试3次
  TIMEOUT_ERROR,       // 超时 - 重试2次
  SERVER_ERROR,        // 服务器错误 - 重试1次
}

export const shouldRetry = (errorType: ErrorType) => {
  return [
    ErrorType.NETWORK_ERROR,
    ErrorType.TIMEOUT_ERROR,
    ErrorType.SERVER_ERROR,
  ].includes(errorType);
};

// 在 execute 中使用
let retries = 0;
const maxRetries = 3;

while (retries <= maxRetries) {
  try {
    return await runQuantV2(command, params);
  } catch (error) {
    const errorType = classifyError(error);
    
    if (!shouldRetry(errorType) || retries >= maxRetries) {
      throw error;
    }
    
    retries++;
    await sleep(1000 * retries); // 指数退避
  }
}
```

**收益**:
- 网络波动容错 ⬆️ 80%
- 用户体验改善

---

### Phase 5: 测试覆盖（3天，长期ROI）⭐⭐⭐

**当前问题**:
- quant-cli-tool.test.ts 只有基础测试
- 没有针对每个命令的单元测试
- 没有集成测试

**优化方案**:

#### 5.1 添加命令级单元测试（2天）

```typescript
// commands/data-commands.test.ts
describe('data commands', () => {
  describe('data.status', () => {
    it('should return database status', async () => {
      const result = await executeCommand('data.status', {});
      expect(result).toHaveProperty('total_stocks');
      expect(result).toHaveProperty('last_update');
    });
  });

  describe('data.update', () => {
    it('should validate source parameter', async () => {
      await expect(
        executeCommand('data.update', { source: 'invalid' })
      ).rejects.toThrow('source 必须是');
    });

    it('should update portfolio data', async () => {
      const result = await executeCommand('data.update', { 
        source: 'portfolio' 
      });
      expect(result.success).toBe(true);
    });
  });
});
```

**目标**: 覆盖率 70%+

---

#### 5.2 添加集成测试（1天）

```typescript
// quant-cli-tool.integration.test.ts
describe('quant_cli integration', () => {
  it('should complete typical workflow', async () => {
    // 1. 检查数据状态
    const status = await executeCommand('data.status');
    
    // 2. 如果数据过期，更新数据
    if (isDataStale(status)) {
      await executeCommand('data.update', { source: 'portfolio' });
    }
    
    // 3. 筛选股票
    const stocks = await executeCommand('screening.sector', {
      sector: '白酒',
      max_pe: 30
    });
    
    // 4. 风控检查
    for (const stock of stocks) {
      const riskCheck = await executeCommand('risk.trade_check', {
        symbol: stock.symbol,
        action: 'buy',
        price: stock.price,
        shares: 100
      });
      expect(riskCheck).toHaveProperty('passed');
    }
  });
});
```

**收益**: 防止回归错误

---

## 📊 优化方案对比

| Phase | 工作量 | ROI | 优先级 | 收益 |
|-------|--------|-----|--------|------|
| 1. 文档优化 | 1天 | ⭐⭐⭐⭐⭐ | 最高 | 用户体验⬆️ 60% |
| 2. 代码结构 | 3天 | ⭐⭐⭐⭐ | 高 | 可维护性⬆️ 80% |
| 3. 性能优化 | 2天 | ⭐⭐⭐ | 中 | 响应速度⬆️ 80% |
| 4. 错误处理 | 1天 | ⭐⭐⭐⭐ | 高 | 用户自助⬆️ 60% |
| 5. 测试覆盖 | 3天 | ⭐⭐⭐ | 中 | 代码质量⬆️ |

---

## 🎯 推荐实施顺序

### 立即开始（本周）
1. **Phase 1: 文档优化**（1天）
   - 创建 README.md
   - 添加使用示例
   - 建立命令快速参考

### 短期（2周内）
2. **Phase 4: 错误处理优化**（1天）
   - 友好的错误消息
   - 错误分类和重试

3. **Phase 2: 代码结构优化**（3天）
   - 拆分命令定义
   - 提取验证逻辑

### 中期（1月内）
4. **Phase 3: 性能优化**（2天）
   - 添加命令缓存
   - 命令执行统计

5. **Phase 5: 测试覆盖**（3天）
   - 命令级单元测试
   - 集成测试

---

## 💰 预期收益

### 短期（2周后）
- ✅ 用户学习成本 ⬇️ 50%
- ✅ 使用错误率 ⬇️ 30%
- ✅ 用户自助解决问题 ⬆️ 60%
- ✅ 支持工作量 ⬇️ 40%

### 中期（1月后）
- ✅ 代码可维护性 ⬆️ 80%
- ✅ 命令响应速度 ⬆️ 80%
- ✅ 测试覆盖率 70%+
- ✅ 代码行数 ⬇️ 50%（主文件）

---

## 📋 实施检查清单

### Phase 1: 文档优化
- [ ] 创建 `docs/tools/quant-cli-guide.md`
- [ ] 添加高频命令列表
- [ ] 添加使用场景示例
- [ ] 更新 CLAUDE.md

### Phase 2: 代码结构
- [ ] 创建 `commands/` 目录
- [ ] 拆分命令定义（10个文件）
- [ ] 提取参数验证逻辑
- [ ] 更新导入和测试

### Phase 3: 性能优化
- [ ] 添加 LRU 缓存
- [ ] 实现命令统计
- [ ] 添加性能监控

### Phase 4: 错误处理
- [ ] 创建友好错误消息
- [ ] 实现错误分类
- [ ] 添加重试逻辑

### Phase 5: 测试覆盖
- [ ] 为每个命令组编写测试
- [ ] 添加集成测试
- [ ] 达到 70% 覆盖率

---

**完成时间**: 2026-06-03  
**推荐**: 从 Phase 1 开始（文档优化），ROI 最高
