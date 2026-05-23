# Agent 工具切换到 CLI 命令系统 - 设计文档

**日期：** 2026-05-23  
**状态：** 设计阶段  
**作者：** Claude (Kiro)

## 1. 概览

### 1.1 目标

将 Agent 工具从 JSON 文件存储（Service 层）切换到 PostgreSQL + CLI 命令系统（DAO 层），通过 TypeScript 适配器层封装 CLI 调用。

### 1.2 背景

**当前状态：**
- Agent 工具使用 JSON 文件存储数据（`.pi-invest/portfolio.json`, `.pi-invest/watchlist.json`, `.pi-invest/trades.json`）
- 通过 Service 类（`PortfolioService`, `WatchlistService`, `TradeService`）访问数据
- 数据已迁移到 PostgreSQL
- 已实现完整的 DAO 层和 CLI 命令（20 个命令）

**问题：**
- 数据存储方式不统一（JSON vs PostgreSQL）
- Service 类与 DAO 层功能重复
- 维护两套数据访问代码

**解决方案：**
- 创建 TypeScript 适配器层封装 CLI 调用
- 修改工具使用适配器替代 Service
- 删除旧 Service 类，统一使用 PostgreSQL

### 1.3 核心原则

1. **保持工具接口不变** - Agent 无需重新学习
2. **最小改动** - 降低风险，易于回滚
3. **类型安全** - 完整的 TypeScript 类型定义
4. **错误处理** - 统一的错误处理策略
5. **可测试** - 完整的单元测试和集成测试

### 1.4 范围

**包含：**
- 创建适配器层（5 个适配器类）
- 修改 3 个工具文件
- 删除 3 个 Service 类
- 编写测试
- 更新文档

**不包含：**
- 数据迁移（已完成）
- DAO 层实现（已完成）
- CLI 命令实现（已完成）
- 工具接口重设计

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent (DeepSeek)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tool Layer (TypeScript)                   │
│  - portfolio-tools.ts                                        │
│  - watchlist-tools.ts                                        │
│  - trade-log-tools.ts                                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Adapter Layer (TypeScript) ← NEW             │
│  - BaseCliAdapter                                            │
│  - PositionCliAdapter                                        │
│  - WatchlistCliAdapter                                       │
│  - TradeCliAdapter                                           │
│  - AccountCliAdapter                                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ (child_process.exec)
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer (Python)                        │
│  quant position +list --json                                 │
│  quant watchlist +add --symbol 600519 --json                 │
│  quant trade +stats --json                                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      DAO Layer (Python)                      │
│  - BaseDAO                                                   │
│  - PositionDAO                                               │
│  - WatchlistDAO                                              │
│  - TradeDAO                                                  │
│  - AccountDAO                                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                        │
│  Schema: quant_agent                                         │
│  Tables: positions, watchlist, position_history, accounts    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 文件结构

```
src/infrastructure/
├── adapters/cli/                    # 新增：适配器层
│   ├── base-cli-adapter.ts          # 基础适配器类
│   ├── position-cli-adapter.ts      # 持仓适配器
│   ├── watchlist-cli-adapter.ts     # 关注列表适配器
│   ├── trade-cli-adapter.ts         # 交易适配器
│   ├── account-cli-adapter.ts       # 账户适配器
│   ├── types.ts                     # 类型定义
│   └── __tests__/                   # 测试文件
│       ├── base-cli-adapter.test.ts
│       ├── position-cli-adapter.test.ts
│       ├── watchlist-cli-adapter.test.ts
│       ├── trade-cli-adapter.test.ts
│       └── account-cli-adapter.test.ts
│
├── tools/
│   ├── invest/
│   │   └── portfolio-tools.ts       # 修改：使用 PositionCliAdapter
│   └── trading/
│       ├── watchlist-tools.ts       # 修改：使用 WatchlistCliAdapter
│       └── trade-log-tools.ts       # 修改：使用 TradeCliAdapter
│
└── services/portfolio/              # 删除整个目录
    ├── portfolio-service.ts         # 删除
    ├── portfolio-service.test.ts    # 删除
    ├── watchlist-service.ts         # 删除
    ├── trade-service.ts             # 删除
    └── trade-service.test.ts        # 删除
```

### 2.3 数据流

**旧流程（JSON 文件）：**
```
Agent → Tool → Service → JSON File
```

**新流程（PostgreSQL）：**
```
Agent → Tool → Adapter → CLI → DAO → PostgreSQL
```

**关键变化：**
- 移除 Service 层
- 新增 Adapter 层封装 CLI 调用
- 数据存储从文件系统迁移到数据库

---

## 3. 适配器层设计

### 3.1 BaseCliAdapter（基础适配器类）

**职责：**
- 执行 CLI 命令（通过 `child_process.exec`）
- 构建命令参数
- 解析 JSON 输出
- 统一错误处理
- 超时控制

**核心方法：**

```typescript
abstract class BaseCliAdapter {
  /**
   * 执行 CLI 命令
   * @param domain - 命令域（position/watchlist/trade/account）
   * @param action - 操作（list/get/add/update/remove）
   * @param params - 参数对象
   * @returns 解析后的数据
   */
  protected async executeCommand(
    domain: string,
    action: string,
    params: Record<string, any>
  ): Promise<any>;

  /**
   * 构建 CLI 命令字符串
   * @param domain - 命令域
   * @param action - 操作
   * @param params - 参数对象
   * @returns 完整命令字符串
   */
  protected buildCommand(
    domain: string,
    action: string,
    params: Record<string, any>
  ): string;

  /**
   * 将参数对象转换为 CLI 参数数组
   * @param params - 参数对象
   * @returns CLI 参数数组
   */
  protected buildCliArgs(params: Record<string, any>): string[];

  /**
   * 将 camelCase 转换为 kebab-case
   * @param key - camelCase 键名
   * @returns kebab-case 键名
   */
  protected toCLIParam(key: string): string;

  /**
   * 解析 CLI JSON 输出
   * @param stdout - CLI 标准输出
   * @returns 解析后的数据
   */
  protected parseJsonOutput(stdout: string): any;

  /**
   * 处理错误
   * @param error - 原始错误
   * @param command - 执行的命令
   * @throws CliExecutionError 或 CliParseError
   */
  protected handleError(error: any, command: string): never;
}
```

**实现细节：**

```typescript
// 命令构建示例
// Input: domain='position', action='list', params={accountId: 'default', status: 'open'}
// Output: 'quant position +list --account-id default --status open --json'

protected buildCommand(domain: string, action: string, params: Record<string, any>): string {
  const args = [`${domain}`, `+${action}`, '--json'];
  
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      const cliKey = this.toCLIParam(key);  // accountId -> account-id
      args.push(`--${cliKey}`, String(value));
    }
  }
  
  return `quant ${args.join(' ')}`;
}

// 参数名转换
protected toCLIParam(key: string): string {
  return key.replace(/([A-Z])/g, '-$1').toLowerCase();
}
```

**错误处理：**

```typescript
protected async executeCommand(domain: string, action: string, params: any): Promise<any> {
  const command = this.buildCommand(domain, action, params);
  
  try {
    const { stdout, stderr } = await execAsync(command, {
      timeout: 30000,           // 30 秒超时
      maxBuffer: 10 * 1024 * 1024  // 10MB 缓冲区
    });
    
    if (stderr) {
      console.warn(`CLI stderr: ${stderr}`);
    }
    
    return this.parseJsonOutput(stdout);
  } catch (error) {
    throw this.handleError(error, command);
  }
}

protected parseJsonOutput(stdout: string): any {
  try {
    const parsed = JSON.parse(stdout);
    
    // CLI 返回格式：{ "data": {...}, "status": "success" }
    if (parsed.status === 'error') {
      throw new Error(parsed.message || 'CLI command failed');
    }
    
    return parsed.data;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new CliParseError('Failed to parse CLI JSON output', stdout);
    }
    throw error;
  }
}

protected handleError(error: any, command: string): never {
  if (error.killed || error.signal === 'SIGTERM') {
    throw new CliExecutionError('Command timeout', command, -1);
  }
  
  if (error.code) {
    throw new CliExecutionError(
      error.message || 'Command execution failed',
      command,
      error.code
    );
  }
  
  throw error;
}
```

### 3.2 领域适配器类

#### 3.2.1 PositionCliAdapter

```typescript
export class PositionCliAdapter extends BaseCliAdapter {
  /**
   * 列出持仓
   */
  async list(params: {
    accountId?: string;
    status?: string;
  } = {}): Promise<Position[]> {
    const result = await this.executeCommand('position', 'list', params);
    return result.positions || [];
  }

  /**
   * 获取单个持仓
   */
  async get(symbol: string, accountId: string = 'default'): Promise<Position | null> {
    try {
      return await this.executeCommand('position', 'get', { symbol, accountId });
    } catch (error) {
      if (error instanceof CliExecutionError && error.message.includes('not found')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * 更新持仓
   */
  async update(
    symbol: string,
    data: {
      quantity?: number;
      price?: number;
      stopLoss?: number;
      takeProfit?: number;
      notes?: string;
    },
    accountId: string = 'default'
  ): Promise<boolean> {
    const result = await this.executeCommand('position', 'update', {
      symbol,
      accountId,
      ...data
    });
    return result.updated_rows > 0;
  }

  /**
   * 关闭持仓
   */
  async close(
    symbol: string,
    reason?: string,
    accountId: string = 'default'
  ): Promise<boolean> {
    const result = await this.executeCommand('position', 'close', {
      symbol,
      accountId,
      reason
    });
    return result.closed === true;
  }

  /**
   * 获取持仓汇总
   */
  async getSummary(accountId: string = 'default'): Promise<PositionSummary> {
    return await this.executeCommand('position', 'summary', { accountId });
  }
}
```

#### 3.2.2 WatchlistCliAdapter

```typescript
export class WatchlistCliAdapter extends BaseCliAdapter {
  /**
   * 列出关注列表
   */
  async list(params: {
    pool?: string;
    priority?: number;
    status?: string;
  } = {}): Promise<WatchlistItem[]> {
    const result = await this.executeCommand('watchlist', 'list', params);
    return result.items || [];
  }

  /**
   * 获取单个关注项
   */
  async get(symbol: string): Promise<WatchlistItem | null> {
    try {
      return await this.executeCommand('watchlist', 'get', { symbol });
    } catch (error) {
      if (error instanceof CliExecutionError && error.message.includes('not found')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * 添加到关注列表
   */
  async add(data: {
    symbol: string;
    name: string;
    market: 'A' | 'HK';
    reason: string;
    buyRangeLow: number;
    buyRangeHigh?: number;
    targetPrice?: number;
    stopLoss?: number;
    priority?: number;
    pool?: 'A' | 'B' | 'C';
    notes?: string;
  }): Promise<string> {
    const result = await this.executeCommand('watchlist', 'add', data);
    return result.id;
  }

  /**
   * 更新关注项
   */
  async update(symbol: string, data: Partial<WatchlistItem>): Promise<boolean> {
    const result = await this.executeCommand('watchlist', 'update', {
      symbol,
      ...data
    });
    return result.updated_rows > 0;
  }

  /**
   * 移除关注项
   */
  async remove(symbol: string): Promise<boolean> {
    const result = await this.executeCommand('watchlist', 'remove', { symbol });
    return result.removed === true;
  }
}
```

#### 3.2.3 TradeCliAdapter

```typescript
export class TradeCliAdapter extends BaseCliAdapter {
  /**
   * 列出交易历史
   */
  async list(params: {
    symbol?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  } = {}): Promise<Trade[]> {
    const result = await this.executeCommand('trade', 'list', params);
    return result.trades || [];
  }

  /**
   * 获取单笔交易
   */
  async get(tradeId: string): Promise<Trade | null> {
    try {
      return await this.executeCommand('trade', 'get', { tradeId });
    } catch (error) {
      if (error instanceof CliExecutionError && error.message.includes('not found')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * 获取交易统计
   */
  async getStats(params: {
    symbol?: string;
    period?: 'all' | 'year' | 'month' | 'week';
  } = {}): Promise<TradeStats> {
    return await this.executeCommand('trade', 'stats', params);
  }
}
```

#### 3.2.4 AccountCliAdapter

```typescript
export class AccountCliAdapter extends BaseCliAdapter {
  /**
   * 获取账户信息
   */
  async get(name: string = 'Default Account'): Promise<Account | null> {
    try {
      return await this.executeCommand('account', 'get', { name });
    } catch (error) {
      if (error instanceof CliExecutionError && error.message.includes('not found')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * 更新账户信息
   */
  async update(
    name: string,
    data: {
      capital?: number;
      currency?: string;
      notes?: string;
    }
  ): Promise<boolean> {
    const result = await this.executeCommand('account', 'update', {
      name,
      ...data
    });
    return result.updated_rows > 0;
  }
}
```

---

## 4. 类型定义

### 4.1 types.ts

```typescript
// Position 相关
export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  cost_basis: number;
  current_price?: number;
  entry_date: string;
  stop_loss?: number;
  take_profit?: number;
  status: 'open' | 'closed';
  account_id: string;
  notes?: string;
}

export interface PositionSummary {
  total_positions: number;
  total_quantity: number;
  total_cost: number;
  total_market_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

// Watchlist 相关
export interface WatchlistItem {
  symbol: string;
  name: string;
  market: 'A' | 'HK';
  priority: number;
  pool: 'A' | 'B' | 'C';
  status: 'watching' | 'ready' | 'bought' | 'discarded';
  buy_range_low?: number;
  buy_range_high?: number;
  target_price?: number;
  stop_loss?: number;
  reason?: string;
  notes?: string;
}

// Trade 相关
export interface Trade {
  id: string;
  symbol: string;
  name: string;
  action: 'buy' | 'sell';
  quantity: number;
  price: number;
  timestamp: string;
  realized_pnl?: number;
  notes?: string;
}

export interface TradeStats {
  total_trades: number;
  buy_count: number;
  sell_count: number;
  total_pnl: number;
  avg_pnl: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
}

// Account 相关
export interface Account {
  name: string;
  current_capital: number;
  currency: string;
  notes?: string;
}

// 错误类型
export class CliExecutionError extends Error {
  constructor(
    message: string,
    public readonly command: string,
    public readonly exitCode: number
  ) {
    super(message);
    this.name = 'CliExecutionError';
  }
}

export class CliParseError extends Error {
  constructor(
    message: string,
    public readonly output: string
  ) {
    super(message);
    this.name = 'CliParseError';
  }
}
```

---

## 5. 工具层修改

### 5.1 修改策略

**原则：**
- 保持工具接口不变（参数、返回格式）
- 只修改内部实现（Service → Adapter）
- 同步方法改为异步方法
- 移除 `PI_DIR` 依赖

### 5.2 portfolio-tools.ts 修改

**修改前：**
```typescript
import { PortfolioService } from "../../../services/portfolio/portfolio-service.js";

const PI_DIR = join(process.cwd(), ".pi-invest");
const _portfolioSvc = new PortfolioService(PI_DIR);

// 在 execute 中
if (action === "get") {
  const data = _portfolioSvc.load();
  return { content: [{ type: "text", text: JSON.stringify(data) }], details: undefined };
}
```

**修改后：**
```typescript
import { PositionCliAdapter } from "../../adapters/cli/position-cli-adapter.js";

const _positionAdapter = new PositionCliAdapter();

// 在 execute 中
if (action === "get") {
  const positions = await _positionAdapter.list({ status: 'open' });
  return { content: [{ type: "text", text: JSON.stringify(positions) }], details: undefined };
}
```

**关键变化：**
1. 导入路径：`services/portfolio/portfolio-service` → `adapters/cli/position-cli-adapter`
2. 实例化：移除 `PI_DIR` 参数
3. 方法调用：`_portfolioSvc.load()` → `await _positionAdapter.list()`
4. 异步处理：添加 `await` 关键字

### 5.3 watchlist-tools.ts 修改

**修改前：**
```typescript
import { WatchlistService } from "../../../services/portfolio/watchlist-service.js";

const _watchlistSvc = new WatchlistService(PI_DIR);

// 在 execute 中
if (action === "list") {
  const summary = _watchlistSvc.getSummary();
  // ... 格式化输出
}
```

**修改后：**
```typescript
import { WatchlistCliAdapter } from "../../adapters/cli/watchlist-cli-adapter.js";

const _watchlistAdapter = new WatchlistCliAdapter();

// 在 execute 中
if (action === "list") {
  const items = await _watchlistAdapter.list({ status });
  // 按 pool 分组（适配器返回扁平列表，工具层负责分组展示）
  const grouped = this.groupByPool(items);
  // ... 格式化输出
}
```

**注意事项：**
- 旧 Service 的 `getSummary()` 返回按 pool 分组的数据
- 新 Adapter 的 `list()` 返回扁平列表
- 需要在工具层添加分组逻辑

### 5.4 trade-log-tools.ts 修改

**修改前：**
```typescript
import { TradeService } from "../../../services/portfolio/trade-service.js";

const _tradeSvc = new TradeService(PI_DIR);

// 在 execute 中
const trades = _tradeSvc.getAll();
```

**修改后：**
```typescript
import { TradeCliAdapter } from "../../adapters/cli/trade-cli-adapter.js";

const _tradeAdapter = new TradeCliAdapter();

// 在 execute 中
const trades = await _tradeAdapter.list({ limit: 100 });
```

### 5.5 特殊处理

#### 5.5.1 港股汇率转换

**问题：** 旧代码在 Service 层处理港股汇率转换，新 CLI 是否支持？

**解决方案：**
- 检查 CLI 命令是否已处理汇率转换
- 如果没有，在适配器层添加汇率转换逻辑
- 或者在工具层保留汇率转换代码

#### 5.5.2 P&L 计算

**问题：** 旧代码的 `getWithPnL()` 方法获取实时价格并计算盈亏

**解决方案：**
- 检查 `position.summary` CLI 命令是否返回 P&L 数据
- 如果返回，直接使用
- 如果不返回，需要在适配器层或工具层实现：
  1. 调用 `position.list` 获取持仓
  2. 调用行情 API 获取实时价格
  3. 计算 P&L

#### 5.5.3 数据格式兼容

**问题：** 确保新旧数据格式一致

**解决方案：**
- 在适配器层进行字段映射
- 例如：CLI 返回 `cost_basis`，工具期望 `avg_cost`
- 添加转换逻辑：`{ ...position, avg_cost: position.cost_basis }`

---

## 6. 错误处理

### 6.1 错误类型

**CliExecutionError：**
- 场景：CLI 命令执行失败（Python 环境问题、数据库连接失败、命令不存在）
- 包含信息：错误消息、执行的命令、退出码
- 处理：工具层捕获后返回友好的错误消息给 Agent

**CliParseError：**
- 场景：CLI 输出无法解析为 JSON
- 包含信息：错误消息、原始输出
- 处理：记录日志，返回解析错误消息

**业务错误：**
- 场景：数据不存在（position not found、watchlist item not found）
- 处理：返回 `null` 或空数组，不抛出异常
- 工具层检查并返回 "未找到" 消息

**超时错误：**
- 场景：CLI 命令执行超过 30 秒
- 处理：终止进程，抛出 `CliExecutionError`
- 工具层返回超时错误消息

### 6.2 错误处理流程

```
CLI 执行失败
    ↓
BaseCliAdapter.handleError()
    ↓
抛出 CliExecutionError 或 CliParseError
    ↓
工具层 try-catch 捕获
    ↓
返回友好的错误消息给 Agent
```

### 6.3 工具层错误处理示例

```typescript
try {
  const position = await _positionAdapter.get(symbol);
  if (!position) {
    return {
      content: [{
        type: "text",
        text: `未找到持仓: ${symbol}`
      }],
      details: undefined
    };
  }
  // ... 正常处理
} catch (error) {
  if (error instanceof CliExecutionError) {
    return {
      content: [{
        type: "text",
        text: `❌ 操作失败: ${error.message}\n命令: ${error.command}`
      }],
      details: undefined
    };
  }
  throw error;  // 未知错误继续抛出
}
```

---

## 7. 测试策略

### 7.1 适配器层测试

#### 单元测试

**测试内容：**
- 命令构建逻辑（参数转换、命令格式）
- JSON 解析（正常输出、错误输出、格式错误）
- 错误处理（超时、执行失败、数据不存在）
- 参数名转换（camelCase → kebab-case）

**Mock 策略：**
- Mock `child_process.exec` 避免实际执行 CLI
- 提供预定义的 stdout/stderr 输出
- 模拟各种错误场景

**示例：**
```typescript
describe('BaseCliAdapter', () => {
  it('should build correct CLI command', () => {
    const adapter = new TestAdapter();
    const command = adapter.buildCommand('position', 'list', {
      accountId: 'default',
      status: 'open'
    });
    expect(command).toBe('quant position +list --account-id default --status open --json');
  });

  it('should parse JSON output correctly', () => {
    const adapter = new TestAdapter();
    const output = '{"data": {"positions": []}, "status": "success"}';
    const result = adapter.parseJsonOutput(output);
    expect(result).toEqual({ positions: [] });
  });

  it('should throw CliParseError on invalid JSON', () => {
    const adapter = new TestAdapter();
    expect(() => adapter.parseJsonOutput('invalid json')).toThrow(CliParseError);
  });
});
```

#### 集成测试

**测试内容：**
- 实际执行 CLI 命令
- 验证数据正确性
- 测试完整的数据流

**环境要求：**
- 测试数据库（独立于生产数据库）
- Python 环境和 quant CLI 可用
- 测试数据预填充

**示例：**
```typescript
describe('PositionCliAdapter Integration', () => {
  let adapter: PositionCliAdapter;

  beforeAll(async () => {
    // 设置测试数据库
    await setupTestDatabase();
    adapter = new PositionCliAdapter();
  });

  it('should list positions', async () => {
    const positions = await adapter.list({ status: 'open' });
    expect(Array.isArray(positions)).toBe(true);
  });

  it('should return null for non-existent position', async () => {
    const position = await adapter.get('NONEXISTENT');
    expect(position).toBeNull();
  });
});
```

### 7.2 工具层测试

**策略：**
- Mock 适配器返回值
- 验证工具返回格式正确
- 验证错误处理逻辑

**示例：**
```typescript
describe('manage_portfolio tool', () => {
  let mockAdapter: jest.Mocked<PositionCliAdapter>;

  beforeEach(() => {
    mockAdapter = {
      list: jest.fn(),
      get: jest.fn(),
      // ... 其他方法
    } as any;
  });

  it('should return positions on get action', async () => {
    mockAdapter.list.mockResolvedValue([
      { symbol: '600036', quantity: 100, /* ... */ }
    ]);

    const result = await managePortfolioTool.execute('test', { action: 'get' });
    expect(result.content[0].text).toContain('600036');
  });
});
```

---

## 8. 实施计划

### 8.1 实施阶段

#### Phase 1: 基础设施（1-2 天）

**任务：**
1. 创建 `src/infrastructure/adapters/cli/` 目录
2. 实现 `types.ts` - 类型定义
3. 实现 `base-cli-adapter.ts` - 基础适配器类
4. 编写基础适配器单元测试

**验收标准：**
- 所有类型定义完整
- BaseCliAdapter 可以执行 CLI 命令并解析输出
- 单元测试覆盖率 > 80%

#### Phase 2: 领域适配器（2-3 天）

**任务：**
1. 实现 `position-cli-adapter.ts`
2. 实现 `watchlist-cli-adapter.ts`
3. 实现 `trade-cli-adapter.ts`
4. 实现 `account-cli-adapter.ts`
5. 编写各适配器的单元测试
6. 编写集成测试

**验收标准：**
- 所有适配器方法实现完整
- 单元测试覆盖率 > 80%
- 集成测试通过

#### Phase 3: 工具层迁移（2-3 天）

**任务：**
1. 修改 `portfolio-tools.ts` 使用 `PositionCliAdapter`
2. 修改 `watchlist-tools.ts` 使用 `WatchlistCliAdapter`
3. 修改 `trade-log-tools.ts` 使用 `TradeCliAdapter`
4. 更新工具层测试
5. 手动测试所有工具功能

**验收标准：**
- 所有工具功能正常
- 工具返回格式与旧版本一致
- 测试通过

#### Phase 4: 清理和文档（1 天）

**任务：**
1. 删除 `src/services/portfolio/portfolio-service.ts`
2. 删除 `src/services/portfolio/watchlist-service.ts`
3. 删除 `src/services/portfolio/trade-service.ts`
4. 删除相关测试文件
5. 更新 README 和相关文档
6. 端到端测试

**验收标准：**
- 旧 Service 类完全删除
- 文档更新完整
- 端到端测试通过

**总计：6-9 天**

### 8.2 风险控制

#### 回滚计划

**Phase 1-2：**
- 直接删除适配器代码
- 无影响，因为工具层尚未使用

**Phase 3：**
- 恢复工具文件的 git 版本
- 回滚到使用 Service 的状态

**Phase 4：**
- 从 git 恢复 Service 类
- 恢复工具文件

#### 渐进式迁移

**策略：**
- 可以先迁移一个工具（如 watchlist）验证
- 验证通过后再迁移其他工具
- 降低风险，便于问题定位

#### 监控和验证

**迁移后验证：**
- 手动测试所有工具功能
- 检查 Agent 使用工具是否正常
- 监控错误日志
- 性能对比（CLI 调用 vs 直接文件读取）

---

## 9. 配置和环境

### 9.1 环境要求

**必需：**
- Node.js 环境可以执行 `quant` CLI 命令
- PostgreSQL 数据库已配置并运行
- Python 环境变量 `QUANT_DB_PROVIDER=postgres` 已设置
- `quant` 命令在 PATH 中可用

**可选：**
- 配置 `quant` CLI 的完整路径（如果不在 PATH 中）

### 9.2 配置选项

```typescript
// src/infrastructure/adapters/cli/config.ts
export interface CliAdapterConfig {
  cliPath?: string;           // CLI 命令路径，默认 'quant'
  timeout?: number;           // 超时时间（毫秒），默认 30000
  maxBuffer?: number;         // 输出缓冲区大小，默认 10MB
  retryAttempts?: number;     // 重试次数，默认 0（不重试）
  retryDelay?: number;        // 重试延迟（毫秒），默认 1000
}

// 使用示例
const adapter = new PositionCliAdapter({
  cliPath: '/usr/local/bin/quant',
  timeout: 60000,  // 60 秒
  retryAttempts: 3
});
```

### 9.3 环境变量

```bash
# PostgreSQL 配置
export QUANT_DB_PROVIDER=postgres
export QUANT_DATABASE_URL=postgresql://user:pass@localhost:5432/quant_investment
export QUANT_PG_SCHEMA=quant_agent

# CLI 路径（可选）
export QUANT_CLI_PATH=/usr/local/bin/quant
```

---

## 10. 附录

### 10.1 CLI 命令参考

**Position 命令：**
```bash
quant position +list --account-id default --status open --json
quant position +get --symbol 600036 --json
quant position +update --symbol 600036 --price 38.5 --json
quant position +close --symbol 600036 --reason "止盈" --json
quant position +summary --json
```

**Watchlist 命令：**
```bash
quant watchlist +list --pool A --priority 1 --json
quant watchlist +get --symbol 600519 --json
quant watchlist +add --symbol 600519 --name "贵州茅台" --market A --json
quant watchlist +remove --symbol 600519 --json
quant watchlist +update --symbol 600519 --priority 2 --json
```

**Trade 命令：**
```bash
quant trade +list --limit 10 --json
quant trade +get --trade-id "1600000001001" --json
quant trade +stats --period month --json
```

**Account 命令：**
```bash
quant account +get --json
quant account +update --capital 250000 --json
```

### 10.2 数据格式示例

**Position 列表响应：**
```json
{
  "data": {
    "total": 2,
    "positions": [
      {
        "symbol": "600036",
        "name": "招商银行",
        "quantity": 100,
        "cost_basis": 38.50,
        "current_price": 40.20,
        "entry_date": "2026-05-01",
        "status": "open",
        "account_id": "default"
      }
    ]
  },
  "status": "success"
}
```

**错误响应：**
```json
{
  "status": "error",
  "message": "Position not found: NONEXISTENT"
}
```

---

## 11. 总结

### 11.1 关键决策

1. ✅ **切换范围**：所有相关工具（Watchlist + Portfolio + Trade）
2. ✅ **实现方式**：TypeScript 适配器层封装 CLI 调用
3. ✅ **架构模式**：基础适配器 + 领域适配器继承结构
4. ✅ **修改策略**：最小改动，保持工具接口不变
5. ✅ **数据迁移**：已完成

### 11.2 预期收益

**统一性：**
- 所有数据访问统一使用 PostgreSQL
- 消除 JSON 文件和数据库的数据不一致问题

**可维护性：**
- 删除重复的 Service 代码
- 统一的错误处理和类型定义
- 更清晰的架构分层

**可扩展性：**
- 适配器层易于扩展新功能
- CLI 命令可以被其他系统复用

**性能：**
- PostgreSQL 查询性能优于文件读取（大数据量时）
- 支持复杂查询和聚合

### 11.3 风险和缓解

**风险：**
- CLI 调用开销（进程启动、JSON 解析）
- 工具层改动可能引入 bug
- Agent 适应新的错误消息

**缓解：**
- 完整的测试覆盖
- 渐进式迁移，逐个工具切换
- 保持工具接口不变
- 清晰的回滚计划

### 11.4 下一步

1. 用户审阅本设计文档
2. 创建实施计划（writing-plans skill）
3. 开始 Phase 1 实施

