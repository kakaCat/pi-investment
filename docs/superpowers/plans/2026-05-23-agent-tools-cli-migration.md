# Agent 工具切换到 CLI 命令系统 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 工具从 JSON 文件存储切换到 PostgreSQL + CLI 命令系统，通过 TypeScript 适配器层封装 CLI 调用

**Architecture:** 创建适配器层（BaseCliAdapter + 4 个领域适配器）封装 CLI 命令调用，修改工具层使用适配器替代 Service 类，删除旧 Service 代码

**Tech Stack:** TypeScript, Node.js child_process, Python CLI, PostgreSQL

---

## 文件结构

### 新增文件

**适配器层：**
- `src/infrastructure/adapters/cli/types.ts` - 类型定义和错误类
- `src/infrastructure/adapters/cli/base-cli-adapter.ts` - 基础适配器类
- `src/infrastructure/adapters/cli/position-cli-adapter.ts` - 持仓适配器
- `src/infrastructure/adapters/cli/watchlist-cli-adapter.ts` - 关注列表适配器
- `src/infrastructure/adapters/cli/trade-cli-adapter.ts` - 交易适配器
- `src/infrastructure/adapters/cli/account-cli-adapter.ts` - 账户适配器
- `src/infrastructure/adapters/cli/index.ts` - 导出文件

**测试文件：**
- `src/infrastructure/adapters/cli/__tests__/base-cli-adapter.test.ts`
- `src/infrastructure/adapters/cli/__tests__/position-cli-adapter.test.ts`
- `src/infrastructure/adapters/cli/__tests__/watchlist-cli-adapter.test.ts`
- `src/infrastructure/adapters/cli/__tests__/trade-cli-adapter.test.ts`
- `src/infrastructure/adapters/cli/__tests__/account-cli-adapter.test.ts`

### 修改文件

**工具层：**
- `src/infrastructure/tools/invest/portfolio-tools.ts` - 使用 PositionCliAdapter
- `src/infrastructure/tools/trading/watchlist-tools.ts` - 使用 WatchlistCliAdapter
- `src/infrastructure/tools/trading/trade-log-tools.ts` - 使用 TradeCliAdapter

### 删除文件

**旧 Service 层：**
- `src/services/portfolio/portfolio-service.ts`
- `src/services/portfolio/portfolio-service.test.ts`
- `src/services/portfolio/watchlist-service.ts`
- `src/services/portfolio/trade-service.ts`
- `src/services/portfolio/trade-service.test.ts`

---

## Task 1: 创建类型定义和错误类

**Files:**
- Create: `src/infrastructure/adapters/cli/types.ts`

- [ ] **Step 1: 创建适配器目录**

```bash
mkdir -p src/infrastructure/adapters/cli/__tests__
```

- [ ] **Step 2: 创建 types.ts 文件**

```typescript
/**
 * CLI Adapter Types and Error Classes
 */

// ============================================================================
// Position Types
// ============================================================================

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

// ============================================================================
// Watchlist Types
// ============================================================================

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

// ============================================================================
// Trade Types
// ============================================================================

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

// ============================================================================
// Account Types
// ============================================================================

export interface Account {
  name: string;
  current_capital: number;
  currency: string;
  notes?: string;
}

// ============================================================================
// Error Classes
// ============================================================================

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

- [ ] **Step 3: 提交类型定义**

```bash
git add src/infrastructure/adapters/cli/types.ts
git commit -m "feat(adapters): add CLI adapter types and error classes"
```

---

## Task 2: 实现 BaseCliAdapter 基础适配器类

**Files:**
- Create: `src/infrastructure/adapters/cli/base-cli-adapter.ts`
- Create: `src/infrastructure/adapters/cli/__tests__/base-cli-adapter.test.ts`

- [ ] **Step 1: 编写 BaseCliAdapter 测试（参数转换）**

```typescript
import { BaseCliAdapter } from '../base-cli-adapter.js';
import { CliExecutionError, CliParseError } from '../types.js';

// 创建测试用的具体实现类
class TestCliAdapter extends BaseCliAdapter {
  // 暴露 protected 方法用于测试
  public testBuildCommand(domain: string, action: string, params: Record<string, any>): string {
    return this.buildCommand(domain, action, params);
  }

  public testToCLIParam(key: string): string {
    return this.toCLIParam(key);
  }

  public testParseJsonOutput(stdout: string): any {
    return this.parseJsonOutput(stdout);
  }
}

describe('BaseCliAdapter', () => {
  let adapter: TestCliAdapter;

  beforeEach(() => {
    adapter = new TestCliAdapter();
  });

  describe('toCLIParam', () => {
    it('should convert camelCase to kebab-case', () => {
      expect(adapter.testToCLIParam('accountId')).toBe('account-id');
      expect(adapter.testToCLIParam('buyRangeLow')).toBe('buy-range-low');
      expect(adapter.testToCLIParam('stopLoss')).toBe('stop-loss');
    });

    it('should handle single word', () => {
      expect(adapter.testToCLIParam('symbol')).toBe('symbol');
      expect(adapter.testToCLIParam('status')).toBe('status');
    });
  });

  describe('buildCommand', () => {
    it('should build correct CLI command with parameters', () => {
      const command = adapter.testBuildCommand('position', 'list', {
        accountId: 'default',
        status: 'open'
      });
      expect(command).toBe('quant position +list --account-id default --status open --json');
    });

    it('should skip undefined and null parameters', () => {
      const command = adapter.testBuildCommand('position', 'get', {
        symbol: '600036',
        accountId: undefined,
        notes: null
      });
      expect(command).toBe('quant position +get --symbol 600036 --json');
    });

    it('should handle no parameters', () => {
      const command = adapter.testBuildCommand('position', 'summary', {});
      expect(command).toBe('quant position +summary --json');
    });
  });

  describe('parseJsonOutput', () => {
    it('should parse successful CLI output', () => {
      const output = JSON.stringify({
        data: { positions: [{ symbol: '600036' }] },
        status: 'success'
      });
      const result = adapter.testParseJsonOutput(output);
      expect(result).toEqual({ positions: [{ symbol: '600036' }] });
    });

    it('should throw error on CLI error status', () => {
      const output = JSON.stringify({
        status: 'error',
        message: 'Position not found'
      });
      expect(() => adapter.testParseJsonOutput(output)).toThrow('Position not found');
    });

    it('should throw CliParseError on invalid JSON', () => {
      expect(() => adapter.testParseJsonOutput('invalid json')).toThrow(CliParseError);
    });
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- base-cli-adapter.test.ts`
Expected: FAIL - BaseCliAdapter not found

- [ ] **Step 3: 实现 BaseCliAdapter 类**

```typescript
import { exec } from 'child_process';
import { promisify } from 'util';
import { CliExecutionError, CliParseError } from './types.js';

const execAsync = promisify(exec);

export abstract class BaseCliAdapter {
  private readonly cliPath: string;
  private readonly timeout: number;
  private readonly maxBuffer: number;

  constructor(config?: {
    cliPath?: string;
    timeout?: number;
    maxBuffer?: number;
  }) {
    this.cliPath = config?.cliPath || 'quant';
    this.timeout = config?.timeout || 30000;  // 30 seconds
    this.maxBuffer = config?.maxBuffer || 10 * 1024 * 1024;  // 10MB
  }

  /**
   * 执行 CLI 命令
   */
  protected async executeCommand(
    domain: string,
    action: string,
    params: Record<string, any>
  ): Promise<any> {
    const command = this.buildCommand(domain, action, params);

    try {
      const { stdout, stderr } = await execAsync(command, {
        timeout: this.timeout,
        maxBuffer: this.maxBuffer
      });

      if (stderr) {
        console.warn(`CLI stderr: ${stderr}`);
      }

      return this.parseJsonOutput(stdout);
    } catch (error: any) {
      throw this.handleError(error, command);
    }
  }

  /**
   * 构建 CLI 命令字符串
   */
  protected buildCommand(
    domain: string,
    action: string,
    params: Record<string, any>
  ): string {
    const args = [domain, `+${action}`, '--json'];

    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        const cliKey = this.toCLIParam(key);
        args.push(`--${cliKey}`, String(value));
      }
    }

    return `${this.cliPath} ${args.join(' ')}`;
  }

  /**
   * 将 camelCase 转换为 kebab-case
   */
  protected toCLIParam(key: string): string {
    return key.replace(/([A-Z])/g, '-$1').toLowerCase();
  }

  /**
   * 解析 CLI JSON 输出
   */
  protected parseJsonOutput(stdout: string): any {
    try {
      const parsed = JSON.parse(stdout);

      // CLI 返回格式：{ "data": {...}, "status": "success" }
      if (parsed.status === 'error') {
        throw new Error(parsed.message || 'CLI command failed');
      }

      return parsed.data;
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        throw new CliParseError('Failed to parse CLI JSON output', stdout);
      }
      throw error;
    }
  }

  /**
   * 处理错误
   */
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
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- base-cli-adapter.test.ts`
Expected: PASS - All tests pass

- [ ] **Step 5: 提交 BaseCliAdapter**

```bash
git add src/infrastructure/adapters/cli/base-cli-adapter.ts src/infrastructure/adapters/cli/__tests__/base-cli-adapter.test.ts
git commit -m "feat(adapters): implement BaseCliAdapter with CLI execution and parsing"
```

---

## Task 3: 实现 PositionCliAdapter

**Files:**
- Create: `src/infrastructure/adapters/cli/position-cli-adapter.ts`
- Create: `src/infrastructure/adapters/cli/__tests__/position-cli-adapter.test.ts`

- [ ] **Step 1: 编写 PositionCliAdapter 测试**

```typescript
import { PositionCliAdapter } from '../position-cli-adapter.js';
import { CliExecutionError } from '../types.js';
import { exec } from 'child_process';

jest.mock('child_process');

describe('PositionCliAdapter', () => {
  let adapter: PositionCliAdapter;
  let mockExec: jest.MockedFunction<typeof exec>;

  beforeEach(() => {
    adapter = new PositionCliAdapter();
    mockExec = exec as jest.MockedFunction<typeof exec>;
    jest.clearAllMocks();
  });

  describe('list', () => {
    it('should list positions with default parameters', async () => {
      const mockOutput = JSON.stringify({
        data: {
          total: 1,
          positions: [{ symbol: '600036', quantity: 100 }]
        },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      const result = await adapter.list();
      expect(result).toEqual([{ symbol: '600036', quantity: 100 }]);
    });

    it('should list positions with filters', async () => {
      const mockOutput = JSON.stringify({
        data: { total: 0, positions: [] },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        expect(cmd).toContain('--account-id test');
        expect(cmd).toContain('--status closed');
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      await adapter.list({ accountId: 'test', status: 'closed' });
    });
  });

  describe('get', () => {
    it('should get single position', async () => {
      const mockOutput = JSON.stringify({
        data: { symbol: '600036', quantity: 100 },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      const result = await adapter.get('600036');
      expect(result).toEqual({ symbol: '600036', quantity: 100 });
    });

    it('should return null when position not found', async () => {
      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(new Error('Position not found'), null);
        return {} as any;
      });

      const result = await adapter.get('NONEXISTENT');
      expect(result).toBeNull();
    });
  });

  describe('update', () => {
    it('should update position and return true on success', async () => {
      const mockOutput = JSON.stringify({
        data: { updated_rows: 1 },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      const result = await adapter.update('600036', { price: 38.5 });
      expect(result).toBe(true);
    });

    it('should return false when no rows updated', async () => {
      const mockOutput = JSON.stringify({
        data: { updated_rows: 0 },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      const result = await adapter.update('600036', { price: 38.5 });
      expect(result).toBe(false);
    });
  });

  describe('close', () => {
    it('should close position', async () => {
      const mockOutput = JSON.stringify({
        data: { closed: true },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      const result = await adapter.close('600036', '止盈');
      expect(result).toBe(true);
    });
  });

  describe('getSummary', () => {
    it('should get position summary', async () => {
      const mockOutput = JSON.stringify({
        data: {
          total_positions: 2,
          total_pnl: 1000
        },
        status: 'success'
      });

      mockExec.mockImplementation((cmd, opts, callback: any) => {
        callback(null, { stdout: mockOutput, stderr: '' });
        return {} as any;
      });

      const result = await adapter.getSummary();
      expect(result.total_positions).toBe(2);
      expect(result.total_pnl).toBe(1000);
    });
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- position-cli-adapter.test.ts`
Expected: FAIL - PositionCliAdapter not found

- [ ] **Step 3: 实现 PositionCliAdapter**

```typescript
import { BaseCliAdapter } from './base-cli-adapter.js';
import { Position, PositionSummary } from './types.js';
import { CliExecutionError } from './types.js';

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

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- position-cli-adapter.test.ts`
Expected: PASS - All tests pass

- [ ] **Step 5: 提交 PositionCliAdapter**

```bash
git add src/infrastructure/adapters/cli/position-cli-adapter.ts src/infrastructure/adapters/cli/__tests__/position-cli-adapter.test.ts
git commit -m "feat(adapters): implement PositionCliAdapter with 5 methods"
```

---

## Task 4: 实现 WatchlistCliAdapter

**Files:**
- Create: `src/infrastructure/adapters/cli/watchlist-cli-adapter.ts`

- [ ] **Step 1: 实现 WatchlistCliAdapter**

```typescript
import { BaseCliAdapter } from './base-cli-adapter.js';
import { WatchlistItem } from './types.js';
import { CliExecutionError } from './types.js';

export class WatchlistCliAdapter extends BaseCliAdapter {
  async list(params: {
    pool?: string;
    priority?: number;
    status?: string;
  } = {}): Promise<WatchlistItem[]> {
    const result = await this.executeCommand('watchlist', 'list', params);
    return result.items || [];
  }

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

  async update(symbol: string, data: Partial<WatchlistItem>): Promise<boolean> {
    const result = await this.executeCommand('watchlist', 'update', {
      symbol,
      ...data
    });
    return result.updated_rows > 0;
  }

  async remove(symbol: string): Promise<boolean> {
    const result = await this.executeCommand('watchlist', 'remove', { symbol });
    return result.removed === true;
  }
}
```

- [ ] **Step 2: 提交 WatchlistCliAdapter**

```bash
git add src/infrastructure/adapters/cli/watchlist-cli-adapter.ts
git commit -m "feat(adapters): implement WatchlistCliAdapter with 5 methods"
```

---

## Task 5: 实现 TradeCliAdapter 和 AccountCliAdapter

**Files:**
- Create: `src/infrastructure/adapters/cli/trade-cli-adapter.ts`
- Create: `src/infrastructure/adapters/cli/account-cli-adapter.ts`

- [ ] **Step 1: 实现 TradeCliAdapter**

```typescript
import { BaseCliAdapter } from './base-cli-adapter.js';
import { Trade, TradeStats } from './types.js';
import { CliExecutionError } from './types.js';

export class TradeCliAdapter extends BaseCliAdapter {
  async list(params: {
    symbol?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  } = {}): Promise<Trade[]> {
    const result = await this.executeCommand('trade', 'list', params);
    return result.trades || [];
  }

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

  async getStats(params: {
    symbol?: string;
    period?: 'all' | 'year' | 'month' | 'week';
  } = {}): Promise<TradeStats> {
    return await this.executeCommand('trade', 'stats', params);
  }
}
```

- [ ] **Step 2: 实现 AccountCliAdapter**

```typescript
import { BaseCliAdapter } from './base-cli-adapter.js';
import { Account } from './types.js';
import { CliExecutionError } from './types.js';

export class AccountCliAdapter extends BaseCliAdapter {
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

- [ ] **Step 3: 创建 index.ts 导出文件**

```typescript
export * from './types.js';
export { BaseCliAdapter } from './base-cli-adapter.js';
export { PositionCliAdapter } from './position-cli-adapter.js';
export { WatchlistCliAdapter } from './watchlist-cli-adapter.js';
export { TradeCliAdapter } from './trade-cli-adapter.js';
export { AccountCliAdapter } from './account-cli-adapter.js';
```

- [ ] **Step 4: 提交 TradeCliAdapter 和 AccountCliAdapter**

```bash
git add src/infrastructure/adapters/cli/trade-cli-adapter.ts src/infrastructure/adapters/cli/account-cli-adapter.ts src/infrastructure/adapters/cli/index.ts
git commit -m "feat(adapters): implement TradeCliAdapter and AccountCliAdapter"
```

---

## Task 6: 修改 portfolio-tools.ts 使用 PositionCliAdapter

**Files:**
- Modify: `src/infrastructure/tools/invest/portfolio-tools.ts`

- [ ] **Step 1: 备份当前文件**

```bash
cp src/infrastructure/tools/invest/portfolio-tools.ts src/infrastructure/tools/invest/portfolio-tools.ts.backup
```

- [ ] **Step 2: 修改导入语句**

将：
```typescript
import { PortfolioService } from "../../../services/portfolio/portfolio-service.js";
```

改为：
```typescript
import { PositionCliAdapter } from "../../adapters/cli/position-cli-adapter.js";
```

- [ ] **Step 3: 修改实例化代码**

将：
```typescript
const PI_DIR = join(process.cwd(), ".pi-invest");
const _portfolioSvc = new PortfolioService(PI_DIR);
```

改为：
```typescript
const _positionAdapter = new PositionCliAdapter();
```

- [ ] **Step 4: 修改 'get' action**

将：
```typescript
if (action === "get") {
  const data = _portfolioSvc.load();
  return { content: [{ type: "text" as const, text: JSON.stringify(data) }], details: undefined };
}
```

改为：
```typescript
if (action === "get") {
  const positions = await _positionAdapter.list({ status: 'open' });
  return { content: [{ type: "text" as const, text: JSON.stringify(positions) }], details: undefined };
}
```

- [ ] **Step 5: 修改 'get_with_pnl' action**

将：
```typescript
if (action === "get_with_pnl") {
  const snapshot = await _portfolioSvc.getWithPnL();
  return { content: [{ type: "text" as const, text: JSON.stringify(snapshot) }], details: undefined };
}
```

改为：
```typescript
if (action === "get_with_pnl") {
  const summary = await _positionAdapter.getSummary();
  const positions = await _positionAdapter.list({ status: 'open' });
  const snapshot = { summary, positions };
  return { content: [{ type: "text" as const, text: JSON.stringify(snapshot) }], details: undefined };
}
```

- [ ] **Step 6: 测试修改后的工具**

Run: `npm test -- portfolio-tools.test.ts`
Expected: PASS - All tests pass

- [ ] **Step 7: 提交 portfolio-tools 修改**

```bash
git add src/infrastructure/tools/invest/portfolio-tools.ts
git commit -m "refactor(tools): migrate portfolio-tools to use PositionCliAdapter"
```

---

## Task 7: 修改 watchlist-tools.ts 使用 WatchlistCliAdapter

**Files:**
- Modify: `src/infrastructure/tools/trading/watchlist-tools.ts`

- [ ] **Step 1: 修改导入和实例化**

将：
```typescript
import { WatchlistService } from "../../../services/portfolio/watchlist-service.js";
const _watchlistSvc = new WatchlistService(PI_DIR);
```

改为：
```typescript
import { WatchlistCliAdapter } from "../../adapters/cli/watchlist-cli-adapter.js";
const _watchlistAdapter = new WatchlistCliAdapter();
```

- [ ] **Step 2: 修改 'list' action**

将：
```typescript
if (action === "list") {
  const summary = _watchlistSvc.getSummary();
  // ... 格式化代码
}
```

改为：
```typescript
if (action === "list") {
  const items = await _watchlistAdapter.list({ status });
  
  // 按 pool 分组
  const grouped: Record<string, any[]> = { A: [], B: [], C: [] };
  for (const item of items) {
    if (item.pool && grouped[item.pool]) {
      grouped[item.pool].push(item);
    }
  }
  
  const summary = {
    total: items.length,
    A_pool: grouped.A,
    B_pool: grouped.B,
    C_pool: grouped.C
  };
  
  // ... 使用 summary 格式化输出
}
```

- [ ] **Step 3: 修改 'get' action**

将：
```typescript
const item = _watchlistSvc.get(symbol);
```

改为：
```typescript
const item = await _watchlistAdapter.get(symbol);
```

- [ ] **Step 4: 修改 'add' action**

将：
```typescript
const res = _watchlistSvc.add(symbol, name, market, reason, buy_range_low, ...);
```

改为：
```typescript
const id = await _watchlistAdapter.add({
  symbol,
  name,
  market,
  reason,
  buyRangeLow: buy_range_low,
  buyRangeHigh: buy_range_high,
  targetPrice: target_price,
  stopLoss: stop_loss,
  priority,
  pool,
  notes
});
const res = { success: true, id };
```

- [ ] **Step 5: 修改 'update' action**

将：
```typescript
const res = _watchlistSvc.update(symbol, updates);
```

改为：
```typescript
const success = await _watchlistAdapter.update(symbol, updates);
const res = { success };
```

- [ ] **Step 6: 修改 'remove' action**

将：
```typescript
const res = _watchlistSvc.remove(symbol);
```

改为：
```typescript
const success = await _watchlistAdapter.remove(symbol);
const res = { success };
```

- [ ] **Step 7: 提交 watchlist-tools 修改**

```bash
git add src/infrastructure/tools/trading/watchlist-tools.ts
git commit -m "refactor(tools): migrate watchlist-tools to use WatchlistCliAdapter"
```

---

## Task 8: 修改 trade-log-tools.ts 使用 TradeCliAdapter

**Files:**
- Modify: `src/infrastructure/tools/trading/trade-log-tools.ts`

- [ ] **Step 1: 修改导入和实例化**

将：
```typescript
import { TradeService } from "../../../services/portfolio/trade-service.js";
const _tradeSvc = new TradeService(PI_DIR);
```

改为：
```typescript
import { TradeCliAdapter } from "../../adapters/cli/trade-cli-adapter.js";
const _tradeAdapter = new TradeCliAdapter();
```

- [ ] **Step 2: 修改所有 TradeService 调用为 TradeCliAdapter 调用**

将：
```typescript
const trades = _tradeSvc.getAll();
```

改为：
```typescript
const trades = await _tradeAdapter.list({ limit: 100 });
```

- [ ] **Step 3: 提交 trade-log-tools 修改**

```bash
git add src/infrastructure/tools/trading/trade-log-tools.ts
git commit -m "refactor(tools): migrate trade-log-tools to use TradeCliAdapter"
```

---

## Task 9: 删除旧 Service 类

**Files:**
- Delete: `src/services/portfolio/portfolio-service.ts`
- Delete: `src/services/portfolio/portfolio-service.test.ts`
- Delete: `src/services/portfolio/watchlist-service.ts`
- Delete: `src/services/portfolio/trade-service.ts`
- Delete: `src/services/portfolio/trade-service.test.ts`

- [ ] **Step 1: 确认所有工具已迁移**

Run: `grep -r "PortfolioService\|WatchlistService\|TradeService" src/infrastructure/tools/`
Expected: 无匹配结果（所有引用已移除）

- [ ] **Step 2: 删除 Service 文件**

```bash
git rm src/services/portfolio/portfolio-service.ts
git rm src/services/portfolio/portfolio-service.test.ts
git rm src/services/portfolio/watchlist-service.ts
git rm src/services/portfolio/trade-service.ts
git rm src/services/portfolio/trade-service.test.ts
```

- [ ] **Step 3: 提交删除**

```bash
git commit -m "refactor: remove old Service classes (migrated to CLI adapters)"
```

---

## Task 10: 端到端测试和文档更新

**Files:**
- Update: `README.md` (if exists)
- Update: `docs/architecture.md` (if exists)

- [ ] **Step 1: 运行所有测试**

Run: `npm test`
Expected: PASS - All tests pass

- [ ] **Step 2: 手动测试工具功能**

测试以下工具调用：
- `manage_portfolio` with action='get'
- `manage_portfolio` with action='get_with_pnl'
- `manage_watchlist` with action='list'
- `manage_watchlist` with action='get'

Expected: 所有工具正常返回数据

- [ ] **Step 3: 更新文档（如果存在）**

在相关文档中更新架构说明：
- 移除 Service 层的描述
- 添加 Adapter 层的描述
- 更新数据流图

- [ ] **Step 4: 最终提交**

```bash
git add docs/
git commit -m "docs: update architecture documentation for CLI adapter migration"
```

- [ ] **Step 5: 推送所有更改**

```bash
git push origin main
```

---

## 完成

所有任务已完成！Agent 工具已成功从 JSON 文件存储切换到 PostgreSQL + CLI 命令系统。

**验收标准：**
- ✅ 5 个适配器类已实现并测试
- ✅ 3 个工具文件已迁移
- ✅ 旧 Service 类已删除
- ✅ 所有测试通过
- ✅ 工具功能正常

