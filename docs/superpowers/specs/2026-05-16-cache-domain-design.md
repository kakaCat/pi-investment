# 缓存领域设计规范

**日期**: 2026-05-16  
**状态**: 设计完成，待实现  
**目标**: 设计独立的缓存领域，统一管理项目中所有数据缓存

---

## 1. 背景与目标

### 1.1 现状问题

项目中存在三个独立的缓存实现：

1. **KlineCacheService** - SQLite 缓存 K 线数据
2. **FxRateService** - JSON 文件缓存汇率数据
3. **python-caller-resilient** - 内存 Map 缓存 + 7 天降级缓存

**问题**：
- 缓存逻辑分散，难以统一管理
- 缺乏统一的监控和管理工具
- 缓存策略不一致
- 扩展性差

### 1.2 设计目标

- ✅ 统一缓存接口，支持所有数据类型
- ✅ 混合存储策略（内存 + SQLite + JSON 文件）
- ✅ 按数据类型分类的命名空间
- ✅ 混合失效策略（TTL + 事件驱动 + 手动刷新）
- ✅ 无降级策略（缓存过期即失效）
- ✅ 全功能监控和管理工具
- ✅ 一次性替换现有缓存实现

---

## 2. 架构设计

### 2.1 目录结构

```
src/domain/cache/
├── core/
│   ├── cache-manager.ts        # 统一缓存管理器（单例）
│   ├── cache-strategy.ts       # 缓存策略接口定义
│   ├── cache-config.ts         # 配置管理（TTL、存储路径等）
│   └── types.ts                # 核心类型定义
├── storage/
│   ├── storage-interface.ts    # 存储接口
│   ├── memory-storage.ts       # 内存存储实现
│   ├── sqlite-storage.ts       # SQLite 存储实现
│   └── file-storage.ts         # JSON 文件存储实现
├── namespaces/
│   ├── base-namespace.ts       # 命名空间基类
│   ├── intraday-cache.ts       # 盘中数据（2分钟 TTL，内存）
│   ├── daily-cache.ts          # 日级数据（24小时 TTL，SQLite）
│   ├── quarterly-cache.ts      # 季度数据（7天 TTL，SQLite）
│   └── static-cache.ts         # 静态数据（30天 TTL，JSON）
├── events/
│   ├── cache-event-bus.ts      # 事件总线
│   └── event-handlers.ts       # 事件处理器（交易日切换、财报发布）
├── monitoring/
│   ├── cache-monitor.ts        # 监控统计（命中率、存储占用）
│   ├── cache-admin.ts          # 管理工具（查看、清空、导出）
│   └── cache-metrics.ts        # 性能指标收集
└── index.ts                    # 统一导出
```

### 2.2 核心类型定义

```typescript
// 缓存条目
interface CacheEntry<T> {
  key: string;
  value: T;
  namespace: CacheNamespace;
  createdAt: number;
  expiresAt: number;
  metadata?: Record<string, unknown>;
}

// 命名空间类型
type CacheNamespace = 'intraday' | 'daily' | 'quarterly' | 'static';

// 存储类型
type StorageType = 'memory' | 'sqlite' | 'file';

// 缓存配置
interface CacheConfig {
  namespace: CacheNamespace;
  ttl: number;              // 毫秒
  storageType: StorageType;
  maxSize?: number;         // 最大条目数
  autoCleanup?: boolean;    // 自动清理过期数据
}
```

### 2.3 CacheManager 核心接口

```typescript
class CacheManager {
  // 获取缓存
  async get<T>(namespace: CacheNamespace, key: string): Promise<T | null>;
  
  // 设置缓存
  async set<T>(namespace: CacheNamespace, key: string, value: T, ttl?: number): Promise<void>;
  
  // 删除缓存
  async delete(namespace: CacheNamespace, key: string): Promise<void>;
  
  // 清空命名空间
  async clear(namespace: CacheNamespace): Promise<void>;
  
  // 批量操作
  async mget<T>(namespace: CacheNamespace, keys: string[]): Promise<Map<string, T>>;
  async mset<T>(namespace: CacheNamespace, entries: Map<string, T>, ttl?: number): Promise<void>;
  
  // 事件驱动失效
  async invalidateByEvent(event: CacheEvent): Promise<void>;
  
  // 手动刷新
  async refresh(namespace: CacheNamespace, key: string, fetcher: () => Promise<unknown>): Promise<void>;
  
  // 按模式失效
  async invalidateByPattern(namespace: CacheNamespace, pattern: string): Promise<number>;
}
```

---

## 3. 存储层设计

### 3.1 存储接口

```typescript
interface IStorage {
  // 基础操作
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T, expiresAt: number): Promise<void>;
  delete(key: string): Promise<void>;
  clear(): Promise<void>;
  
  // 批量操作
  mget<T>(keys: string[]): Promise<Map<string, T>>;
  mset<T>(entries: Map<string, { value: T; expiresAt: number }>): Promise<void>;
  
  // 查询操作
  keys(pattern?: string): Promise<string[]>;
  size(): Promise<number>;
  
  // 清理操作
  cleanup(): Promise<number>; // 返回清理的条目数
}
```

### 3.2 三种存储实现

#### MemoryStorage（内存存储）
- 使用 `Map<string, CacheEntry>` 存储
- 定时器自动清理过期数据（每分钟）
- 支持 LRU 淘汰策略（当达到 maxSize）
- **适用于**: intraday 命名空间

#### SQLiteStorage（SQLite 存储）
- 表结构：`cache_entries(key TEXT PRIMARY KEY, namespace TEXT, value TEXT, expires_at INTEGER, created_at INTEGER)`
- 索引：`(namespace, expires_at)` 用于快速清理
- 事务支持批量操作
- 存储路径：`.pi-invest/cache.db`
- **适用于**: daily、quarterly 命名空间

#### FileStorage（JSON 文件存储）
- 每个命名空间一个 JSON 文件：`.pi-invest/cache/{namespace}.json`
- 读取时加载到内存，写入时原子性替换
- 适合小数据量、低频更新
- **适用于**: static 命名空间

### 3.3 存储选择策略

```typescript
class StorageFactory {
  static create(config: CacheConfig): IStorage {
    switch (config.storageType) {
      case 'memory':
        return new MemoryStorage(config.maxSize);
      case 'sqlite':
        return new SQLiteStorage('.pi-invest/cache.db', config.namespace);
      case 'file':
        return new FileStorage(`.pi-invest/cache/${config.namespace}.json`);
    }
  }
}
```

---

## 4. 命名空间设计

### 4.1 命名空间配置

```typescript
const NAMESPACE_CONFIGS: Record<CacheNamespace, CacheConfig> = {
  intraday: {
    namespace: 'intraday',
    ttl: 2 * 60 * 1000,        // 2分钟
    storageType: 'memory',
    maxSize: 500,
    autoCleanup: true
  },
  daily: {
    namespace: 'daily',
    ttl: 24 * 60 * 60 * 1000,  // 24小时
    storageType: 'sqlite',
    autoCleanup: true
  },
  quarterly: {
    namespace: 'quarterly',
    ttl: 7 * 24 * 60 * 60 * 1000,  // 7天
    storageType: 'sqlite',
    autoCleanup: true
  },
  static: {
    namespace: 'static',
    ttl: 30 * 24 * 60 * 60 * 1000,  // 30天
    storageType: 'file',
    autoCleanup: false
  }
};
```

### 4.2 数据分类映射

#### 不缓存（直接调用）
- `get_stock_realtime_price` - 实时价格
- `get_hk_stock_price` - 港股实时价格
- `get_market_overview` - 大盘实时行情

#### intraday 命名空间（2分钟 TTL，内存存储）
- `get_north_flow` - 北向资金流向
- `get_sector_fund_flow` - 板块资金流向
- `get_market_margin` - 融资融券数据
- `get_stock_news` - 股票新闻

#### daily 命名空间（24小时 TTL，SQLite 存储）
- `get_stock_history` - 历史行情（日线）
- `get_hk_stock_history` - 港股历史行情
- `calculate_technical_indicators` - 技术指标
- `get_stock_fund_flow` - 个股资金流向（历史）
- `get_lhb` - 龙虎榜
- `get_announcements` - 公司公告
- FX rates - 汇率

#### quarterly 命名空间（7天 TTL，SQLite 存储）
- `get_financial_statements` - 财务报表
- `get_financial_indicators` - 财务指标
- `get_holder_changes` - 股东变化
- `get_fund_holdings` - 基金持仓
- `get_insider_trades` - 内部交易
- `get_top_holders` - 十大股东

#### static 命名空间（30天 TTL，JSON 文件存储）
- `get_stock_info` - 公司基本信息
- `get_hk_stock_info` - 港股基本信息
- `get_sector_list` - 板块列表
- `get_concept_list` - 概念列表
- `get_concept_stocks` - 概念成分股
- `get_pe_percentile` - PE 百分位历史

### 4.3 BaseNamespace 基类

```typescript
abstract class BaseNamespace {
  protected storage: IStorage;
  protected config: CacheConfig;
  
  constructor(config: CacheConfig) {
    this.config = config;
    this.storage = StorageFactory.create(config);
  }
  
  // 生成缓存 key
  protected buildKey(identifier: string, params?: Record<string, unknown>): string {
    const paramStr = params ? `:${JSON.stringify(params)}` : '';
    return `${this.config.namespace}:${identifier}${paramStr}`;
  }
  
  // 计算过期时间
  protected getExpiresAt(customTtl?: number): number {
    const ttl = customTtl ?? this.config.ttl;
    return Date.now() + ttl;
  }
  
  // 子类可覆盖的钩子
  protected async beforeSet?(key: string, value: unknown): Promise<void>;
  protected async afterGet?(key: string, value: unknown): Promise<void>;
}
```

---

## 5. 事件驱动失效机制

### 5.1 缓存事件类型

```typescript
enum CacheEventType {
  TRADING_DAY_CHANGE = 'trading_day_change',      // 交易日切换
  FINANCIAL_REPORT = 'financial_report',          // 财报发布
  MANUAL_INVALIDATE = 'manual_invalidate',        // 手动失效
  ANNOUNCEMENT = 'announcement',                  // 公司公告
  HOLDER_CHANGE = 'holder_change'                 // 股东变化
}

interface CacheEvent {
  type: CacheEventType;
  timestamp: number;
  payload?: {
    symbol?: string;        // 相关股票代码
    namespace?: CacheNamespace;  // 影响的命名空间
    pattern?: string;       // key 匹配模式
  };
}
```

### 5.2 事件处理器

```typescript
class CacheEventBus {
  private handlers: Map<CacheEventType, Array<(event: CacheEvent) => Promise<void>>>;
  
  // 注册事件处理器
  on(eventType: CacheEventType, handler: (event: CacheEvent) => Promise<void>): void;
  
  // 触发事件
  async emit(event: CacheEvent): Promise<void>;
}

// 预定义的事件处理器
const EVENT_HANDLERS = {
  // 交易日切换 → 清空 intraday 命名空间
  [CacheEventType.TRADING_DAY_CHANGE]: async (event: CacheEvent) => {
    await cacheManager.clear('intraday');
    // 可选：预热当日常用数据
  },
  
  // 财报发布 → 失效相关股票的 quarterly 数据
  [CacheEventType.FINANCIAL_REPORT]: async (event: CacheEvent) => {
    const { symbol } = event.payload;
    await cacheManager.invalidateByPattern('quarterly', `*:${symbol}:*`);
  },
  
  // 公司公告 → 失效相关股票的 daily 公告缓存
  [CacheEventType.ANNOUNCEMENT]: async (event: CacheEvent) => {
    const { symbol } = event.payload;
    await cacheManager.delete('daily', `announcements:${symbol}`);
  }
};
```

### 5.3 手动刷新接口

```typescript
class CacheManager {
  // 手动刷新单个 key
  async refresh<T>(
    namespace: CacheNamespace, 
    key: string, 
    fetcher: () => Promise<T>
  ): Promise<T> {
    await this.delete(namespace, key);
    const value = await fetcher();
    await this.set(namespace, key, value);
    return value;
  }
  
  // 按模式失效
  async invalidateByPattern(namespace: CacheNamespace, pattern: string): Promise<number> {
    const keys = await this.namespaces[namespace].storage.keys(pattern);
    await Promise.all(keys.map(k => this.delete(namespace, k)));
    return keys.length;
  }
}
```

---

## 6. 监控和管理功能

### 6.1 监控指标

```typescript
interface CacheMetrics {
  // 命中率统计
  hits: number;
  misses: number;
  hitRate: number;  // hits / (hits + misses)
  
  // 存储统计
  totalEntries: number;
  totalSize: number;  // 字节数（估算）
  
  // 命名空间分布
  namespaceStats: Record<CacheNamespace, {
    entries: number;
    size: number;
    hitRate: number;
  }>;
  
  // 热点数据（访问次数 Top 10）
  hotKeys: Array<{
    key: string;
    namespace: CacheNamespace;
    accessCount: number;
    lastAccess: number;
  }>;
  
  // TTL 分布
  ttlDistribution: {
    expired: number;
    expiringSoon: number;  // 1小时内过期
    fresh: number;
  };
}

class CacheMonitor {
  private metrics: CacheMetrics;
  private accessLog: Map<string, { count: number; lastAccess: number }>;
  
  // 记录访问
  recordHit(namespace: CacheNamespace, key: string): void;
  recordMiss(namespace: CacheNamespace, key: string): void;
  
  // 获取指标
  getMetrics(): CacheMetrics;
  
  // 重置统计
  reset(): void;
  
  // 导出报告
  exportReport(): string;  // JSON 格式
}
```

### 6.2 管理工具

```typescript
class CacheAdmin {
  // 查看单个 key
  async inspect(namespace: CacheNamespace, key: string): Promise<{
    exists: boolean;
    value?: unknown;
    createdAt?: number;
    expiresAt?: number;
    ttl?: number;  // 剩余时间（毫秒）
  }>;
  
  // 手动设置/删除
  async set(namespace: CacheNamespace, key: string, value: unknown, ttl?: number): Promise<void>;
  async delete(namespace: CacheNamespace, key: string): Promise<void>;
  
  // 清空命名空间
  async clear(namespace: CacheNamespace): Promise<number>;  // 返回清理的条目数
  
  // 导出/导入缓存
  async export(namespace: CacheNamespace, filePath: string): Promise<void>;
  async import(namespace: CacheNamespace, filePath: string): Promise<number>;
  
  // 缓存预热
  async warmup(tasks: Array<{
    namespace: CacheNamespace;
    key: string;
    fetcher: () => Promise<unknown>;
  }>): Promise<void>;
  
  // 自动清理
  async cleanup(namespace?: CacheNamespace): Promise<{
    cleaned: number;
    remaining: number;
  }>;
}
```

### 6.3 性能分析

```typescript
class CachePerformance {
  // 操作耗时统计
  private timings: Map<string, number[]>;  // operation -> durations
  
  recordTiming(operation: string, duration: number): void;
  
  getStats(operation: string): {
    count: number;
    avg: number;
    p50: number;
    p95: number;
    p99: number;
    max: number;
  };
  
  // 慢查询日志（超过阈值的操作）
  getSlowQueries(threshold: number): Array<{
    operation: string;
    duration: number;
    timestamp: number;
    key: string;
  }>;
}
```

### 6.4 CLI 工具接口

```typescript
// 供 CLI 或管理界面调用
export const cacheCommands = {
  // 查看状态
  status: () => cacheMonitor.getMetrics(),
  
  // 查看单个 key
  get: (namespace: string, key: string) => cacheAdmin.inspect(namespace as CacheNamespace, key),
  
  // 清空缓存
  clear: (namespace?: string) => namespace 
    ? cacheAdmin.clear(namespace as CacheNamespace)
    : Promise.all(Object.keys(NAMESPACE_CONFIGS).map(ns => cacheAdmin.clear(ns as CacheNamespace))),
  
  // 预热缓存
  warmup: (config: string) => {
    const tasks = JSON.parse(config);
    return cacheAdmin.warmup(tasks);
  },
  
  // 导出报告
  report: () => cacheMonitor.exportReport()
};
```

---

## 7. 迁移策略和集成方案

### 7.1 迁移步骤

#### 阶段 1：实现新缓存系统
1. 实现 `src/domain/cache/` 所有模块
2. 编写单元测试，确保各存储层正常工作
3. 实现 CacheManager 单例和统一接口

#### 阶段 2：适配现有数据源
4. 修改 `akshare-ts/data/market.ts` - 将 KlineCacheService 替换为 CacheManager
5. 修改 `fx-rate-service.ts` - 使用 CacheManager 的 daily 命名空间
6. 修改 `python-caller-resilient.ts` - 移除内存 Map，使用 CacheManager

#### 阶段 3：数据迁移
7. 编写迁移脚本，将现有 SQLite K 线数据导入新缓存系统
8. 将 `fx-rates.json` 数据导入 daily 命名空间
9. 验证数据完整性

#### 阶段 4：清理旧代码
10. 删除 `KlineCacheService`、`StockDBService`（K 线部分）
11. 删除 `FxRateService` 的缓存逻辑
12. 删除 `python-caller-resilient.ts` 的缓存代码
13. 更新所有调用方

### 7.2 集成接口示例

#### 在 akshare-ts/data/market.ts 中使用

```typescript
import { cacheManager } from '../../../domain/cache/index.js';

export async function get_stock_history(
  symbol: string,
  period = "daily",
  start?: string,
  end?: string,
  _adjust = "qfq",
  _skip_cache = false,
): Promise<string> {
  const clean = cleanSymbolInternal(symbol);
  
  if (period === "daily" && !_skip_cache) {
    const cacheKey = `history:${clean}:${start || '2023-01-01'}:${end || today()}`;
    
    // 尝试从缓存获取
    const cached = await cacheManager.get<unknown>('daily', cacheKey);
    if (cached) {
      return JSON.stringify({ ...cached, _source: 'cache' });
    }
    
    // 缓存未命中，获取数据
    const raw = await callPythonBridge("get_stock_history", { 
      symbol: clean, 
      period, 
      start_date: start, 
      end_date: end, 
      adjust: _adjust 
    });
    
    // 写入缓存
    await cacheManager.set('daily', cacheKey, raw);
    
    return JSON.stringify(raw);
  }
  
  // 跳过缓存或非日线数据
  const raw = await callPythonBridge("get_stock_history", { 
    symbol: clean, 
    period, 
    start_date: start, 
    end_date: end, 
    adjust: _adjust 
  });
  return JSON.stringify(raw);
}
```

#### 在 fx-rate-service.ts 中使用

```typescript
import { cacheManager } from '../domain/cache/index.js';

export class FxRateService {
  async getRate(pair: "HKDCNY"): Promise<number> {
    const cacheKey = `fx:${pair}`;
    
    // 尝试从缓存获取
    const cached = await cacheManager.get<number>('daily', cacheKey);
    if (cached !== null) {
      return cached;
    }
    
    // 获取新汇率
    const rate = await this.fetchRateFromSina(pair);
    
    // 写入缓存（24小时 TTL）
    await cacheManager.set('daily', cacheKey, rate);
    
    return rate;
  }
}
```

### 7.3 向后兼容性

- 保留 `getKlineCache()` 和 `getStockDB()` 函数签名，内部委托给 CacheManager
- 迁移期间两套系统并存，逐步切换
- 提供配置开关 `USE_NEW_CACHE`，方便回滚

### 7.4 测试策略

#### 单元测试
- 每个存储层独立测试
- CacheManager 接口测试
- 事件总线测试
- TTL 过期测试

#### 集成测试
- 端到端缓存流程测试
- 多命名空间并发测试
- 数据迁移验证测试

#### 性能测试
- 内存存储性能基准
- SQLite 存储性能基准
- 并发读写压力测试

---

## 8. 设计总结

### 8.1 核心特性

✅ **清晰的领域边界** - 独立的 `src/domain/cache/` 目录  
✅ **混合存储策略** - 内存 + SQLite + JSON 文件  
✅ **四个命名空间** - intraday(2分钟) / daily(24小时) / quarterly(7天) / static(30天)  
✅ **混合失效策略** - TTL + 事件驱动 + 手动刷新  
✅ **无降级策略** - 缓存过期即失效，强制重新获取  
✅ **全功能监控** - 命中率、热点数据、性能分析、管理工具  
✅ **一次性替换** - 迁移完成后删除旧缓存代码

### 8.2 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 架构模式 | 领域驱动设计（DDD） | 清晰的领域边界，易于扩展 |
| 存储策略 | 混合存储 | 根据数据特性选择最优存储方式 |
| 命名空间 | 按数据类型分类 | 符合业务语义，TTL 管理清晰 |
| 失效策略 | TTL + 事件驱动 + 手动 | 灵活应对不同场景 |
| 降级策略 | 无降级 | 保证数据新鲜度，避免过期数据误导 |
| 迁移方式 | 一次性替换 | 避免长期维护两套系统 |

### 8.3 预期收益

- **统一管理** - 所有缓存逻辑集中在一个领域
- **性能提升** - 减少重复网络请求，提升响应速度
- **可观测性** - 完整的监控和管理工具
- **可扩展性** - 新增数据类型只需配置命名空间
- **可维护性** - 清晰的架构，易于理解和修改

---

## 9. 后续工作

1. 实现核心缓存系统
2. 编写单元测试和集成测试
3. 迁移现有缓存实现
4. 性能测试和优化
5. 文档完善和团队培训
