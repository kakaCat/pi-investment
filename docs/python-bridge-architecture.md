# Python Bridge 调用机制详解

> 生成时间: 2026-05-22
> 
> 本文档详细说明 TypeScript 与 Python 后端的通信架构

## 目录

1. [架构概览](#架构概览)
2. [调用层次](#调用层次)
3. [Python Daemon 机制](#python-daemon-机制)
4. [弹性调用层](#弹性调用层)
5. [Bridge-to-CLI 路由](#bridge-to-cli-路由)
6. [缓存系统](#缓存系统)
7. [超时与重试策略](#超时与重试策略)
8. [非交易时段处理](#非交易时段处理)

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    TypeScript 工具层                          │
│  (invest-tools.ts, risk-tools.ts, analysis-tools.ts...)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Python Caller (统一入口)                         │
│           src/infrastructure/tools/shared/                   │
│                  python-caller.ts                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            弹性调用层 (Resilient Adapter)                     │
│     python-caller-resilient-adapter.ts                       │
│  • 缓存管理 (intraday/daily/quarterly/static)                │
│  • 超时控制 (15s/35s/55s/120s)                               │
│  • 重试机制 (1-2次)                                           │
│  • 非交易时段快速失败                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          Bridge-to-CLI 路由适配器                             │
│        bridge-to-cli-adapter.ts                              │
│  • 高频函数 (11个) → QuantSys CLI                             │
│  • ML/可视化函数 (7个) → Python Bridge Daemon                 │
│  • 未知/失败函数 → Python Bridge Daemon (fallback)            │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│   QuantSys CLI 适配器     │  │   Python Bridge Daemon       │
│  • market-query-cli       │  │   python-bridge.ts           │
│  • stock-query-cli        │  │  • JSON-RPC 2.0 协议          │
│  • financial-query-cli    │  │  • 持久化进程                 │
│  • analysis-query-cli     │  │  • stdin/stdout 通信          │
│  • sentiment-query-cli    │  │  • 自动重启                   │
│  • risk-query-cli         │  │                              │
└──────────────┬───────────┘  └──────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│  QuantSys CLI (Python)   │  │  AkShare Bridge (Python)     │
│  quant/quantsys/cli/     │  │  quant/quantsys/bridge/      │
│  • risk_query.py         │  │  akshare_bridge.py           │
│  • market_query.py       │  │  • AkShare API 调用           │
│  • financial_query.py    │  │  • 数据清洗与转换             │
│  • analysis_query.py     │  │  • ML 模型推理                │
│  • ...                   │  │                              │
└──────────────────────────┘  └──────────────────────────────┘
```

---

## 调用层次

### 1. 工具层 (Tool Layer)

**文件**: `src/infrastructure/tools/invest/*.ts`

```typescript
// 示例：获取股票价格
export const getStockPriceTool: ToolDefinition = {
  name: "get_stock_price",
  execute: async (_toolCallId, params: any) => {
    const result = await callPython("get_stock_realtime_price", { symbol: params.symbol });
    return { content: [{ type: "text", text: result }], details: undefined };
  },
};
```

### 2. Python Caller (统一入口)

**文件**: `src/infrastructure/tools/shared/python-caller.ts`

```typescript
export async function callPython(func: string, args: Record<string, unknown> = {}): Promise<string> {
  return callPythonResilient(func, args);
}
```

### 3. 弹性调用层 (Resilient Layer)

**文件**: `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`

职责:
- 缓存管理
- 超时控制
- 重试机制
- 非交易时段处理
- 降级策略

### 4. Bridge-to-CLI 路由

**文件**: `src/infrastructure/quant/bridge-to-cli-adapter.ts`

职责:
- 路由高频函数到 QuantSys CLI
- 路由 ML/可视化函数到 Python Bridge Daemon
- 提供 fallback 机制

---

## Python Daemon 机制

### 架构特点

**文件**: `src/infrastructure/tools/core/python-bridge.ts`

1. **持久化进程**: 启动一个长期运行的 Python 进程，避免每次调用都启动新进程
2. **JSON-RPC 2.0 协议**: 使用标准 JSON-RPC 协议进行通信
3. **stdin/stdout 通信**: 通过标准输入输出流传递数据
4. **自动重启**: 进程崩溃时自动重启（延迟 1 秒）
5. **优雅关闭**: 支持 SIGTERM/SIGINT 信号的优雅关闭

### 通信协议

#### 请求格式 (JSON-RPC Request)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "get_stock_realtime_price",
  "params": {
    "symbol": "600519"
  }
}
```

#### 响应格式 (JSON-RPC Response)

成功响应:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "{\"symbol\":\"600519\",\"price\":1850.00,\"change_pct\":2.5}"
}
```

错误响应:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Stock not found",
    "data": {"symbol": "600519"}
  }
}
```

### 生命周期管理

```typescript
class PythonDaemon {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pendingRequests = new Map<number, PendingRequest>();
  
  // 启动 Python 进程
  private start(): void {
    this.process = spawn("python3", [PYTHON_SCRIPT, "--daemon"], {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, TQDM_DISABLE: "1", PYTHONUNBUFFERED: "1" },
    });
    
    // 监听 stdout (JSON-RPC 响应)
    this.rl = readline.createInterface({ input: this.process.stdout! });
    this.rl.on("line", (line) => this.handleResponse(line));
    
    // 监听进程退出，自动重启
    this.process.on("exit", (code, signal) => {
      this.cleanup();
      if (!this.isShuttingDown) {
        setTimeout(() => this.start(), RESTART_DELAY_MS);
      }
    });
  }
  
  // 发送请求
  async call(method: string, params: Record<string, unknown>): Promise<string> {
    const id = ++this.requestId;
    const request: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };
    
    return new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timeout after ${REQUEST_TIMEOUT_MS}ms`));
      }, REQUEST_TIMEOUT_MS);
      
      this.pendingRequests.set(id, { resolve, reject, timer });
      this.process!.stdin!.write(JSON.stringify(request) + "\n");
    });
  }
}
```

### Python 端实现

**文件**: `quant/quantsys/bridge/akshare_bridge.py`

```python
#!/usr/bin/env python3
import sys
import json
import akshare as ak

def handle_request(request):
    """处理 JSON-RPC 请求"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    try:
        # 调用对应的 AkShare 函数
        if method == "get_stock_realtime_price":
            result = ak.stock_zh_a_spot_em()
            # 数据清洗与转换
            result = result[result['代码'] == params['symbol']]
            # ...
            
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": json.dumps(result)
        }
    except Exception as e:
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": str(e)
            }
        }
    
    return response

def main():
    """Daemon 模式：持续监听 stdin"""
    for line in sys.stdin:
        request = json.loads(line)
        response = handle_request(request)
        print(json.dumps(response), flush=True)

if __name__ == "__main__":
    main()
```

---

## 弹性调用层

### 核心特性

**文件**: `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`

1. **缓存管理**: 4 级缓存命名空间
2. **超时控制**: 分级超时策略
3. **重试机制**: 智能重试
4. **非交易时段处理**: 快速失败
5. **降级策略**: 备选方案提示

### 缓存命名空间

```typescript
const NAMESPACE_MAP: Record<string, CacheNamespace> = {
  // intraday (5-10分钟) - 实时数据
  'get_stock_realtime_price': 'intraday',
  'get_market_overview': 'intraday',
  'get_north_flow': 'intraday',
  
  // daily (24小时) - 日级数据
  'get_stock_info': 'daily',
  'get_financial_indicators': 'daily',
  'get_financial_statements': 'daily',
  
  // quarterly (90天) - 季度数据
  // (暂未使用)
  
  // static (永久) - 静态数据
  // (暂未使用)
};
```

### 超时配置

```typescript
const TIMEOUT_FAST = 15000;      // 15秒 - 快速接口
const TIMEOUT_MEDIUM = 35000;    // 35秒 - 中速接口
const TIMEOUT_SLOW = 55000;      // 55秒 - 慢速接口
const TIMEOUT_VERY_SLOW = 120000; // 120秒 - 超慢接口（腾讯API）

const TIMEOUT_CONFIG: Record<string, number> = {
  'get_stock_realtime_price': TIMEOUT_FAST,
  'get_north_flow': TIMEOUT_MEDIUM,
  'get_sector_fund_flow': TIMEOUT_VERY_SLOW,
  'get_financial_statements': TIMEOUT_SLOW,
  // ...
};
```

### 重试策略

```typescript
const RETRY_CONFIG: Record<string, number> = {
  // 慢接口只重试 1 次
  'get_macro_data': 1,
  'get_financial_statements': 1,
  'get_sector_fund_flow': 1,
  
  // 其他接口重试 2 次
  // (DEFAULT_MAX_RETRIES = 2)
};

// 可重试的错误类型
function isRetriableError(error: unknown): boolean {
  const retriablePatterns = [
    'timeout', 'econnrefused', 'econnreset', 'etimedout',
    'enetunreach', 'socket hang up', 'network', 'temporary',
  ];
  return retriablePatterns.some(pattern => message.includes(pattern));
}
```

### 调用流程

```typescript
export async function callPythonResilient(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  const namespace = NAMESPACE_MAP[func] || 'intraday';
  const cacheKey = `python:${func}:${JSON.stringify(args, Object.keys(args).sort())}`;
  
  // 1. 检查缓存
  const cached = await cacheManager.get<string>(namespace, cacheKey);
  if (cached) return cached;
  
  // 2. 非交易时段快速失败（仅限实时类工具）
  if (!OFFLINE_CAPABLE_TOOLS.has(func)) {
    if (!isTradingHours()) {
      return getNonTradingMessage(func);
    }
  }
  
  // 3. 调用 bridge-to-cli-adapter（带重试）
  const timeout = TIMEOUT_CONFIG[func] ?? DEFAULT_TIMEOUT;
  try {
    const result = await callPythonWithRetry(func, args, timeout);
    
    // 4. 缓存成功结果
    if (!isErrorResult(result)) {
      await cacheManager.set(namespace, cacheKey, result);
    }
    
    return result;
  } catch (error) {
    // 5. 返回错误（包含备选方案）
    return JSON.stringify({
      error: `数据获取失败: ${error.message}`,
      _alternatives: getAlternatives(func)
    });
  }
}
```

---

## Bridge-to-CLI 路由

### 路由策略

**文件**: `src/infrastructure/quant/bridge-to-cli-adapter.ts`

```typescript
// 高频函数 (11个) → QuantSys CLI
const CLI_FUNCTION_MAP: Record<string, CliAdapter> = {
  // 市场数据 (3)
  'get_sector_list': async () => getSectorListViaQuantCli(),
  'get_north_flow': async () => getNorthFlowViaQuantCli(),
  'get_sector_fund_flow': async () => getSectorFundFlowViaQuantCli(),
  
  // 个股数据 (2)
  'get_stock_realtime_price': async (args) => getStockPriceViaQuantCli(args.symbol),
  'get_stock_history': async (args) => getStockHistoryViaQuantCli(args),
  
  // 财务数据 (3)
  'get_financial_indicators': async (args) => getFinancialIndicatorsViaQuantCli(args.symbol),
  'get_income_statement': async (args) => getFinancialStatementsViaQuantCli({...}),
  'get_cash_flow': async (args) => getFinancialStatementsViaQuantCli({...}),
  
  // 估值分析 (2)
  'get_stock_valuation': async (args) => getValuationViaQuantCli(args.symbol),
  'get_pe_percentile': async (args) => getPePercentileViaQuantCli(args.symbol, args.years),
  
  // 资金流向 (1)
  'get_stock_fund_flow': async (args) => getStockFundFlowViaQuantCli(args),
};

// ML/可视化函数 (7个) → Python Bridge Daemon
const BRIDGE_ONLY_FUNCTIONS = new Set([
  'run_confidence_calibration',
  'predict_signal_confidence',
  'combine_strategy_signals',
  'plot_model_accuracy_trend',
  'plot_equity_curve',
  'plot_strategy_comparison',
  'plot_feature_importance',
]);
```

### 路由逻辑

```typescript
export async function callBridgeOrCli(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  // 1. ML/可视化函数 → 强制使用 Bridge
  if (BRIDGE_ONLY_FUNCTIONS.has(func)) {
    return callPythonDaemon(func, args);
  }
  
  // 2. 高频函数 → 优先使用 CLI
  const cliAdapter = CLI_FUNCTION_MAP[func];
  if (cliAdapter) {
    try {
      return await cliAdapter(args);
    } catch (error) {
      console.warn(`[bridge-to-cli] CLI failed for ${func}, fallback to bridge:`, error);
      return callPythonDaemon(func, args);
    }
  }
  
  // 3. 未知函数 → 使用 Bridge (fallback)
  return callPythonDaemon(func, args);
}
```

---

## 缓存系统

### 缓存管理器

**文件**: `src/domain/cache/core/cache-manager.ts`

```typescript
export class CacheManager {
  private static instance: CacheManager;
  
  async get<T>(namespace: CacheNamespace, key: string): Promise<T | null> {
    const entry = await this.storage.get(namespace, key);
    if (!entry) return null;
    
    // 检查 TTL
    if (Date.now() > entry.expiresAt) {
      await this.storage.delete(namespace, key);
      return null;
    }
    
    return entry.value as T;
  }
  
  async set<T>(namespace: CacheNamespace, key: string, value: T): Promise<void> {
    const ttl = this.getTTL(namespace);
    const entry: CacheEntry<T> = {
      value,
      createdAt: Date.now(),
      expiresAt: Date.now() + ttl,
    };
    await this.storage.set(namespace, key, entry);
  }
  
  private getTTL(namespace: CacheNamespace): number {
    const TTL_MAP = {
      'intraday': 5 * 60 * 1000,      // 5分钟
      'daily': 24 * 60 * 60 * 1000,   // 24小时
      'quarterly': 90 * 24 * 60 * 60 * 1000, // 90天
      'static': Infinity,              // 永久
    };
    return TTL_MAP[namespace];
  }
}
```

### 缓存键生成

```typescript
// 确保参数顺序一致，避免缓存未命中
const cacheKey = `python:${func}:${JSON.stringify(args, Object.keys(args).sort())}`;

// 示例
// func = "get_stock_price", args = { symbol: "600519" }
// cacheKey = "python:get_stock_price:{"symbol":"600519"}"
```

---

## 超时与重试策略

### 超时控制

```typescript
async function callPythonWithTimeout(
  func: string,
  args: Record<string, unknown>,
  timeoutMs: number
): Promise<string> {
  return Promise.race([
    callBridgeOrCli(func, args),
    new Promise<string>((_, reject) =>
      setTimeout(() => reject(new Error(`Timeout after ${timeoutMs}ms`)), timeoutMs)
    )
  ]);
}
```

### 重试机制

```typescript
async function callPythonWithRetry(
  func: string,
  args: Record<string, unknown>,
  timeoutMs: number
): Promise<string> {
  const maxRetries = RETRY_CONFIG[func] ?? DEFAULT_MAX_RETRIES;
  let lastError: unknown;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        // 指数退避：1s, 2s, 4s (最大 5s)
        const delayMs = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
      
      return await callPythonWithTimeout(func, args, timeoutMs);
    } catch (error) {
      lastError = error;
      
      // 非可重试错误，直接抛出
      if (!isRetriableError(error)) {
        throw error;
      }
      
      // 达到最大重试次数
      if (attempt === maxRetries) {
        throw new Error(`${error.message} (failed after ${maxRetries + 1} attempts)`);
      }
    }
  }
  
  throw lastError;
}
```

---

## 非交易时段处理

### 交易时段判断

```typescript
// 非交易时段可继续的工具（不依赖实时行情数据）
const OFFLINE_CAPABLE_TOOLS = new Set([
  'get_stock_info',           // 基础信息
  'get_financial_indicators', // 财务数据
  'get_financial_statements', // 财务报表
  'get_stock_history',        // 历史行情
  'get_macro_data',           // 宏观数据
  'get_stock_news',           // 新闻公告
  // ...
]);

function isTradingHours(): boolean {
  const now = new Date();
  const chinaTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
  const dayOfWeek = chinaTime.getDay();
  const hours = chinaTime.getHours();
  const minutes = chinaTime.getMinutes();
  const currentMinutes = hours * 60 + minutes;
  
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
  const morningStart = 9 * 60 + 30;   // 9:30
  const morningEnd = 11 * 60 + 30;    // 11:30
  const afternoonStart = 13 * 60;     // 13:00
  const afternoonEnd = 15 * 60;       // 15:00
  
  return !isWeekend && (
    (currentMinutes >= morningStart && currentMinutes <= morningEnd) ||
    (currentMinutes >= afternoonStart && currentMinutes <= afternoonEnd)
  );
}
```

### 快速失败响应

```typescript
function getNonTradingMessage(func: string): string {
  const chinaTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
  
  return JSON.stringify({
    error: '非交易时段（9:30-11:30 / 13:00-15:00），数据源不可用',
    _non_trading_hours: true,
    _current_time: chinaTime.toLocaleString('zh-CN'),
    _suggestion: '请在北京时间 9:30-15:00（交易日）使用，或使用不依赖实时行情的工具',
  });
}
```

---

## 备选方案提示

当 Python 调用失败时，系统会返回备选方案提示：

```typescript
const ALTERNATIVES: Record<string, string[]> = {
  'get_stock_realtime_price': [
    "使用 get_stock_info 获取基本信息（不含实时价格）",
    "使用 get_stock_history 获取最近的历史数据",
    "如果是港股，尝试 get_hk_stock_price"
  ],
  'get_north_flow': [
    "使用 get_market_margin 查看融资融券数据作为资金流向参考",
    "使用 get_sector_fund_flow 查看板块资金流向",
    "等待数据源恢复后重试"
  ],
  // ...
};

// 错误响应示例
{
  "error": "数据获取失败: Timeout after 35000ms",
  "_no_operation_performed": true,
  "_suggestion": "数据源可能暂时不可用，请稍后重试",
  "_alternatives": [
    "使用 get_market_margin 查看融资融券数据作为资金流向参考",
    "使用 get_sector_fund_flow 查看板块资金流向",
    "等待数据源恢复后重试"
  ]
}
```

---

## 性能优化

### 1. 持久化进程

- **问题**: 每次调用启动新 Python 进程耗时 ~500ms
- **方案**: Python Daemon 持久化进程，启动一次，复用多次
- **效果**: 调用延迟降低至 ~50ms

### 2. 分级缓存

- **问题**: 实时数据频繁请求，网络开销大
- **方案**: 4 级缓存命名空间（intraday/daily/quarterly/static）
- **效果**: 缓存命中率 ~70%，响应时间降低 90%

### 3. 分级超时

- **问题**: 统一超时导致快速接口等待慢速接口
- **方案**: 根据接口特性设置不同超时（15s/35s/55s/120s）
- **效果**: 快速接口响应时间降低 60%

### 4. 智能重试

- **问题**: 所有错误都重试，浪费时间
- **方案**: 只重试网络错误，慢接口只重试 1 次
- **效果**: 失败响应时间降低 50%

### 5. 非交易时段快速失败

- **问题**: 非交易时段请求实时数据，等待超时
- **方案**: 检测交易时段，非交易时段直接返回错误
- **效果**: 非交易时段响应时间从 35s 降低至 <1ms

---

## 监控与调试

### 日志输出

```typescript
// Python Daemon 启动
[python-daemon] Started (PID=12345)

// 请求超时
[python-resilient] get_north_flow attempt 1 failed: Timeout after 35000ms
[python-resilient] get_north_flow retry 1/2 after 1000ms

// CLI 失败，fallback 到 Bridge
[bridge-to-cli] CLI failed for get_stock_price, fallback to bridge: Error: ...

// 非交易时段快速失败
[python-resilient] get_stock_realtime_price 非交易时段快速失败，跳过 Python 请求

// Python 进程退出
[python-daemon] Process exited (code=1, signal=null)
[python-daemon] Restarting in 1000ms...
```

### 缓存统计

```typescript
export async function getCacheStats() {
  const cacheManager = CacheManager.getInstance();
  return {
    cache_size: 0,
    by_namespace: {
      intraday: 0,
      daily: 0,
      quarterly: 0,
      static: 0,
    },
  };
}
```

---

**文档生成时间**: 2026-05-22  
**项目**: pi-investment  
**相关文档**: [agent-tools-mapping.md](./agent-tools-mapping.md)
