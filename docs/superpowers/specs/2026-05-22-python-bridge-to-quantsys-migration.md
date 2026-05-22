# Python Bridge Daemon 迁移到 QuantSys 设计规范

> 状态: 待实施
> 日期: 2026-05-22
> 类型: 一次性重构
> 关联: [quant-system-design](2026-05-17-quant-system-design.md), [risk-bridge-migration](2026-05-21-risk-bridge-migration.md)

## 1. 动机

### 1.1 当前问题

当前项目维护两套 Python 后端调用机制：

1. **QuantSys CLI** (`python -m quantsys.cli`) - 每次调用启动新进程
2. **Python Bridge Daemon** (`quant/quantsys/bridge/akshare_bridge.py`) - 持久化 JSON-RPC 进程

两套系统的共存导致：

- **架构不一致**：bridge-to-cli-adapter.ts 需要复杂的路由逻辑（CLI 适配器 vs bridge fallback）
- **代码重复**：11 个 CLI 适配器文件，每个都是薄封装层
- **维护负担**：两套系统的生命周期管理、错误处理、日志格式各不相同
- **功能分裂**：ML/可视化函数只能在 bridge 中运行，其他函数优先走 CLI

### 1.2 目标

将所有 Python 后端调用统一到 QuantSys CLI 的 daemon 模式，通过 JSON-RPC 2.0 协议通信，优先级：

1. **架构统一** - 单一调用路径，TypeScript 层一个连接点
2. **性能保持** - 保留 daemon 模式的进程复用机制
3. **功能完整** - 所有函数（包括 ML/可视化）均可通过 daemon 调用
4. **风险可控** - 接口不变，缓存层保留，可快速回滚

## 2. 架构设计

### 2.1 目标架构

```
TypeScript 工具层
  ↓
python-caller.ts (统一入口，接口不变)
  ↓
python-caller-resilient-adapter.ts (缓存、超时、重试)
  ↓
quantsys-daemon-adapter.ts (新增：QuantSys Daemon 适配器)
  ↓
JSON-RPC 2.0 over stdin/stdout
  ↓
python -m quantsys.cli --daemon
  ↓
QuantSys 模块 (market, financial, risk, ml, analysis...)
```

### 2.2 调用流程变化

**当前（复杂）：**
```
callPython() → resilient-adapter → bridge-to-cli-adapter (路由判断)
  → CLI 适配器 (11个函数) → spawn CLI 进程
  → Python Bridge  (7个函数) → JSON-RPC daemon
  → fallback         (未知) → JSON-RPC daemon
```

**迁移后（简化）：**
```
callPython() → resilient-adapter → quantsys-daemon-adapter → JSON-RPC daemon (所有函数)
```

## 3. Python 端实现

### 3.1 Daemon 服务端

**新增文件：`quant/quantsys/cli/daemon.py`**

```python
"""
JSON-RPC 2.0 Daemon Server for QuantSys CLI.

通过 stdin/stdout 接收 JSON-RPC 请求，路由到对应的 CLI 命令处理函数。
"""

import json
import sys
import traceback
from typing import Any, Dict, Optional


class JsonRpcRequest:
    jsonrpc: str = "2.0"
    id: int
    method: str
    params: Dict[str, Any]


class QuantSysDaemon:
    """QuantSys CLI Daemon 服务端"""

    def __init__(self):
        self._load_registry()

    def _load_registry(self):
        """加载 CLI 命令注册表，建立 method → handler 映射"""
        from .registry import CommandRegistry
        self.registry = CommandRegistry()

    def _parse_method(self, method: str) -> tuple:
        """
        解析 JSON-RPC method 到 (domain, action)
        
        映射规则：
        - method 名称与现有 CLI 命令名称一致
        - 例如: "get_stock_price" → domain="stock", action="price"
        - 例如: "check_trade_risk" → domain="risk", action="trade-check"
        """
        return self.registry.resolve_method(method)

    def handle_request(self, request: dict) -> dict:
        """处理单个 JSON-RPC 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            domain, action = self._parse_method(method)
            handler = self.registry.get_handler(domain, action)

            if handler is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            result = handler(params)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": json.dumps(result, default=str, ensure_ascii=False)
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(e),
                    "data": {"traceback": traceback.format_exc()}
                }
            }

    def run(self):
        """主循环：读取 stdin，逐行处理 JSON-RPC 请求"""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response, ensure_ascii=False), flush=True)
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {e}"
                    }
                }
                print(json.dumps(error_response, ensure_ascii=False), flush=True)


def main():
    daemon = QuantSysDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
```

### 3.2 ML 函数 CLI 模块

**新增文件：`quant/quantsys/cli/ml_query.py`**

```python
"""
ML 查询 CLI 模块。

迁移自 akshare_bridge.py 中的 ML/可视化函数。
"""


def run_confidence_calibration(params):
    """模型置信度校准"""
    from quantsys.ml.calibration import ConfidenceCalibrator
    calibrator = ConfidenceCalibrator()
    return calibrator.run(**params)


def predict_signal_confidence(params):
    """信号置信度预测"""
    from quantsys.ml.predictor import SignalPredictor
    predictor = SignalPredictor()
    return predictor.predict(**params)


def combine_strategy_signals(params):
    """策略信号组合"""
    from quantsys.ml.combiner import StrategyCombiner
    combiner = StrategyCombiner()
    return combiner.combine(**params)


def plot_model_accuracy_trend(params):
    """模型准确率趋势图"""
    from quantsys.ml.viz import plot_accuracy_trend
    return plot_accuracy_trend(**params)


def plot_equity_curve(params):
    """权益曲线图"""
    from quantsys.ml.viz import plot_equity_curve
    return plot_equity_curve(**params)


def plot_strategy_comparison(params):
    """策略对比图"""
    from quantsys.ml.viz import plot_strategy_comparison
    return plot_strategy_comparison(**params)


def plot_feature_importance(params):
    """特征重要性图"""
    from quantsys.ml.viz import plot_feature_importance
    return plot_feature_importance(**params)
```

### 3.3 CLI 入口修改

**修改文件：`quant/quantsys/cli/main.py`**

在 `main()` 函数开头添加 daemon 模式处理：

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true',
                       help='Run in daemon mode (JSON-RPC over stdin/stdout)')
    # ... 其他参数

    args, unknown = parser.parse_known_args()

    if args.daemon:
        from .daemon import main as daemon_main
        daemon_main()
        return 0

    # 原有的 CLI 逻辑保持不变
    # ...
```

## 4. TypeScript 端实现

### 4.1 QuantSys Daemon 适配器

**新增文件：`src/infrastructure/quant/quantsys-daemon-adapter.ts`**

```typescript
/**
 * QuantSys Daemon Adapter - 与 QuantSys CLI Daemon 通信的客户端
 *
 * 重构自 python-bridge.ts，主要改动：
 * - 启动命令从 akshare_bridge.py 改为 python -m quantsys.cli --daemon
 * - 工作目录设置为 quant/ 根目录
 * - 其他生命周期管理逻辑保持不变
 */

import { spawn, ChildProcess } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import * as readline from "readline";

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUANT_ROOT = join(__dirname, "..", "..", "..", "quant");
const RESTART_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 150000;

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

interface PendingRequest {
  resolve: (value: string) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

class QuantSysDaemon {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pendingRequests = new Map<number, PendingRequest>();
  private isShuttingDown = false;
  private restartTimer: NodeJS.Timeout | null = null;
  private rl: readline.Interface | null = null;

  constructor() {
    this.start();
    process.on("exit", () => this.shutdown());
    process.on("SIGINT", () => this.shutdown());
    process.on("SIGTERM", () => this.shutdown());
  }

  private start(): void {
    if (this.isShuttingDown) return;

    try {
      this.process = spawn("python3", ["-m", "quantsys.cli", "--daemon"], {
        cwd: QUANT_ROOT,
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, PYTHONUNBUFFERED: "1" },
      });

      this.rl = readline.createInterface({
        input: this.process.stdout!,
        crlfDelay: Infinity,
      });

      this.rl.on("line", (line) => {
        this.handleResponse(line);
      });

      this.process.stderr?.on("data", (data) => {
        const msg = data.toString().trim();
        if (msg) {
          console.error(`[quantsys-daemon stderr] ${msg}`);
        }
      });

      this.process.on("exit", (code, signal) => {
        console.warn(`[quantsys-daemon] Process exited (code=${code}, signal=${signal})`);
        this.cleanup();

        const entries = Array.from(this.pendingRequests.entries());
        for (const [id, pending] of entries) {
          clearTimeout(pending.timer);
          pending.reject(new Error("QuantSys daemon process exited unexpectedly"));
          this.pendingRequests.delete(id);
        }

        if (!this.isShuttingDown) {
          console.log(`[quantsys-daemon] Restarting in ${RESTART_DELAY_MS}ms...`);
          this.restartTimer = setTimeout(() => this.start(), RESTART_DELAY_MS);
        }
      });

      this.process.on("error", (err) => {
        console.error(`[quantsys-daemon] Process error:`, err);
      });

      console.log(`[quantsys-daemon] Started (PID=${this.process.pid})`);
    } catch (error) {
      console.error(`[quantsys-daemon] Failed to start:`, error);
      if (!this.isShuttingDown) {
        this.restartTimer = setTimeout(() => this.start(), RESTART_DELAY_MS);
      }
    }
  }

  private cleanup(): void {
    if (this.rl) {
      this.rl.close();
      this.rl.removeAllListeners();
      this.rl = null;
    }
    if (this.process) {
      this.process.stdin?.removeAllListeners();
      this.process.stdout?.removeAllListeners();
      this.process.stderr?.removeAllListeners();
      this.process.removeAllListeners();
    }
    this.process = null;
  }

  private handleResponse(line: string): void {
    if (!line.trim()) return;

    try {
      const response: JsonRpcResponse = JSON.parse(line);

      if (response.jsonrpc !== "2.0" || typeof response.id !== "number") {
        console.warn(`[quantsys-daemon] Invalid JSON-RPC response:`, line);
        return;
      }

      const pending = this.pendingRequests.get(response.id);
      if (!pending) {
        console.warn(`[quantsys-daemon] Received response for unknown request ID ${response.id}`);
        return;
      }

      clearTimeout(pending.timer);
      this.pendingRequests.delete(response.id);

      if (response.error) {
        pending.reject(new Error(response.error.message));
      } else {
        const resultStr = typeof response.result === "string"
          ? response.result
          : JSON.stringify(response.result);
        pending.resolve(resultStr);
      }
    } catch (error) {
      console.error(`[quantsys-daemon] Failed to parse response:`, line, error);
    }
  }

  async call(method: string, params: Record<string, unknown> = {}): Promise<string> {
    if (!this.process || this.process.exitCode !== null) {
      throw new Error("QuantSys daemon is not running");
    }

    const id = ++this.requestId;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timeout after ${REQUEST_TIMEOUT_MS}ms`));
      }, REQUEST_TIMEOUT_MS);

      this.pendingRequests.set(id, { resolve, reject, timer });

      try {
        const requestLine = JSON.stringify(request) + "\n";
        this.process!.stdin!.write(requestLine, "utf8", (err) => {
          if (err) {
            clearTimeout(timer);
            this.pendingRequests.delete(id);
            reject(new Error(`Failed to write to QuantSys daemon: ${err.message}`));
          }
        });
      } catch (error) {
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }

  shutdown(): void {
    if (this.isShuttingDown) return;
    this.isShuttingDown = true;

    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }

    const entries = Array.from(this.pendingRequests.entries());
    for (const [id, pending] of entries) {
      clearTimeout(pending.timer);
      pending.reject(new Error("QuantSys daemon is shutting down"));
      this.pendingRequests.delete(id);
    }

    if (this.process) {
      try {
        this.process.stdin?.end();
        this.process.kill("SIGTERM");
        setTimeout(() => {
          if (this.process && this.process.exitCode === null) {
            this.process.kill("SIGKILL");
          }
        }, 2000);
      } catch (error) {
        console.error(`[quantsys-daemon] Error during shutdown:`, error);
      }
    }

    this.cleanup();
  }
}

let daemon: QuantSysDaemon | null = null;

export async function callQuantSysDaemon(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  if (!daemon) {
    daemon = new QuantSysDaemon();
  }
  return daemon.call(func, args);
}

export function shutdownQuantSysDaemon(): void {
  if (daemon) {
    daemon.shutdown();
    daemon = null;
  }
}
```

### 4.2 修改弹性调用层

**修改文件：`src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`**

改动 1 - import 变更：
```typescript
// 旧代码
import { callBridgeOrCli } from "../../quant/bridge-to-cli-adapter.js";

// 新代码
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";
```

改动 2 - 调用点变更（在 `callPythonWithTimeout` 函数中）：
```typescript
// 旧代码
return Promise.race([
  callBridgeOrCli(func, args),
  new Promise<string>((_, reject) =>
    setTimeout(() => reject(new Error(`Timeout after ${timeoutMs}ms`)), timeoutMs)
  )
]);

// 新代码
return Promise.race([
  callQuantSysDaemon(func, args),
  new Promise<string>((_, reject) =>
    setTimeout(() => reject(new Error(`Timeout after ${timeoutMs}ms`)), timeoutMs)
  )
]);
```

### 4.3 修改 Agent 重启工具

**修改文件：`src/infrastructure/tools/agent/restart-agent-tool.ts`**

```typescript
// 旧代码 - 查找 akshare_bridge.py 进程
const result = execSync("pgrep -f 'akshare_bridge.py' 2>/dev/null || true", { ... });

// 新代码 - 查找 quantsys daemon 进程
const result = execSync("pgrep -f 'quantsys.cli.*--daemon' 2>/dev/null || true", { ... });
```

## 5. 文件变更清单

### 5.1 新增文件

| 文件 | 职责 |
|------|------|
| `quant/quantsys/cli/daemon.py` | JSON-RPC 2.0 daemon 服务端 |
| `quant/quantsys/cli/ml_query.py` | ML 函数 CLI 模块 |
| `src/infrastructure/quant/quantsys-daemon-adapter.ts` | TypeScript daemon 客户端 |

### 5.2 修改文件

| 文件 | 改动 |
|------|------|
| `quant/quantsys/cli/main.py` | 添加 `--daemon` 参数 |
| `quant/quantsys/cli/registry.py` | 注册 ml_query 命令 |
| `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts` | 替换 import 和调用点 |
| `src/infrastructure/tools/agent/restart-agent-tool.ts` | 更新进程查找关键字 |
| `src/infrastructure/tools/index.ts` | 移除旧 export |

### 5.3 删除文件

| 文件 | 原因 |
|------|------|
| `src/infrastructure/tools/core/python-bridge.ts` | 被 quantsys-daemon-adapter 替代 |
| `src/infrastructure/quant/bridge-to-cli-adapter.ts` | 无需路由，统一走 daemon |
| `src/infrastructure/quant/market-query-cli-adapter.ts` | 无需独立 CLI 进程 |
| `src/infrastructure/quant/stock-query-cli-adapter.ts` | 同上 |
| `src/infrastructure/quant/financial-query-cli-adapter.ts` | 同上 |
| `src/infrastructure/quant/analysis-query-cli-adapter.ts` | 同上 |
| `src/infrastructure/quant/sentiment-query-cli-adapter.ts` | 同上 |
| `src/infrastructure/quant/risk-query-cli-adapter.ts` | 同上 |
| `quant/quantsys/bridge/` (整个目录) | 被 daemon.py 替代 |

### 5.4 不变文件（风险隔离）

| 文件 | 说明 |
|------|------|
| `src/infrastructure/tools/invest/*.ts` | 投资工具定义不变 |
| `src/infrastructure/tools/analysis/*.ts` | 分析工具不变 |
| `src/infrastructure/tools/trading/*.ts` | 交易工具不变 |
| `src/core/agent/agent-loop.ts` | Agent 循环接口不变 |
| `quant/quantsys/cli/risk_query.py` | 风控 CLI 模块不变 |
| `quant/quantsys/cli/market_query.py` | 市场 CLI 模块不变 |
| `quant/quantsys/risk/bridge.py` | 风控桥接层不变 |

## 6. 错误处理

### 6.1 Python Daemon 崩溃

- QuantSysDaemon 监听进程退出事件
- 自动重启（延迟 1 秒）
- 拒绝所有待处理的请求，返回错误
- TypeScript 层的重试机制会重新发起请求

### 6.2 请求超时

- 每个请求设置超时定时器（150 秒）
- 超时后拒绝 Promise，由弹性调用层处理
- 弹性调用层根据 RETRY_CONFIG 决定是否重试
- 最终失败返回错误 + 备选方案提示

### 6.3 Python 函数执行错误

- Python 端捕获异常，返回 JSON-RPC error 响应
- TypeScript 端解析 error 字段，抛出异常
- 弹性调用层包装为友好的错误消息（含备选方案）

### 6.4 非交易时段

- 弹性调用层在发送请求前检查
- 对于实时数据工具，直接返回错误（不调用 daemon）
- 对于离线可用工具（OFFLINE_CAPABLE_TOOLS），正常调用

## 7. 测试策略

### 7.1 单元测试

- Python daemon: 测试 JSON-RPC 请求/响应格式
- ML 函数: 验证 7 个函数的输入输出
- TypeScript 适配器: 模拟 Python 进程测试通信

### 7.2 集成测试

- 启动 daemon → 调用函数 → 验证结果
- 模拟 daemon 崩溃 → 验证自动重启
- 模拟超时 → 验证重试和降级
- 非交易时段 → 验证快速失败

### 7.3 回归测试

- `npm test` 现有测试套件
- 手动验证关键路径：get_stock_price、get_financial_statements、check_trade_risk、predict_signal_confidence

## 8. 回滚策略

1. `git checkout` 恢复旧文件
2. 修改 `resilient-adapter` 的 import 路径
3. 无需数据库迁移或数据回滚（纯代码层变更）

## 9. 性能基准

| 指标 | 迁移前 | 迁移后 | 变化 |
|------|--------|--------|------|
| 调用延迟（缓存命中） | <1ms | <1ms | 不变 |
| 调用延迟（缓存未命中） | ~50ms (daemon) / ~300ms (CLI) | ~50ms | 统一 |
| 内存占用 | 2 进程 (cli + daemon) | 1 进程 | 减少 |
| 启动时间 | daemon 启动 ~500ms，CLI 每次 ~300ms | daemon 启动 ~500ms | 持平 |
| 缓存命中率 | ~70% | ~70% | 不变 |

## 10. 实施步骤

**预计时间：1-2 天**

1. **Python 端** (半天)
   - 创建 `daemon.py`
   - 创建 `ml_query.py`
   - 修改 `main.py` 添加 `--daemon`
   - 修改 `registry.py` 注册 ml 命令

2. **TypeScript 端** (半天)
   - 创建 `quantsys-daemon-adapter.ts`
   - 修改 `python-caller-resilient-adapter.ts`
   - 删除旧文件
   - 更新 `index.ts` 和 `restart-agent-tool.ts`

3. **测试和清理** (半天)
   - 运行 `npm test`
   - 启动应用手动验证
   - 删除 `quant/quantsys/bridge/` 目录
   - 更新文档

---

**关联文档**:
- [agent-tools-mapping](../agent-tools-mapping.md)
- [python-bridge-architecture](../python-bridge-architecture.md)
