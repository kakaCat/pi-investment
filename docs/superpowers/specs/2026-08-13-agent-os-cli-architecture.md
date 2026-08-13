# Agent OS CLI 架构重设计

> **创建时间**: 2026-08-13  
> **核心理念**: Agent 通过 CLI 调用 OS，而非 HTTP API

---

## 1. 为什么 CLI 更适合 Agent？

### 当前设计的问题（HTTP API）

```typescript
// agent-ts 调用 OS (HTTP)
await fetch('http://localhost:8080/api/memory/write', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({content: '...', category: 'decision'})
});
```

**痛点**：
- 需要构造 HTTP 请求（headers、body、错误处理）
- 网络依赖（OS 挂了 agent 才发现）
- 序列化开销（JSON 编解码）
- agent 需要知道 OS 的地址和端口

### CLI 方式的优势

```typescript
// agent-ts 调用 OS (CLI)
const result = execSync('agent-os memory write --content "..." --category decision');
```

**优势**：
- **简单直观**：像调用 `git commit` 一样自然
- **无网络依赖**：本地二进制调用，OS 挂了立即报错
- **语义清晰**：`agent-os memory write` 比 `POST /api/memory/write` 更易读
- **调试友好**：可以在终端手动测试命令
- **LLM 友好**：Claude 本身就擅长生成 CLI 命令

---

## 2. CLI 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       agent-ts (Node.js)                         │
│                                                                   │
│  fin-agent 推理:                                                 │
│    LLM 生成工具调用 → 转换为 CLI 命令 → execSync()              │
│                                                                   │
│  示例:                                                            │
│    memory_write({content: "...", category: "decision"})          │
│      ↓ 转换                                                       │
│    agent-os memory write \                                       │
│      --content "早盘分析：市场情绪积极..." \                      │
│      --category "morning-analysis" \                             │
│      --agent-id "fin-agent"                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ execSync() / child_process.spawn()
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              agent-os CLI (Go Binary)                            │
│                 /usr/local/bin/agent-os                          │
│                                                                   │
│  命令结构:                                                        │
│    agent-os <resource> <action> [flags]                          │
│                                                                   │
│  Resources:                                                      │
│    - memory      (记忆管理)                                      │
│    - decision    (决策记录)                                      │
│    - evolution   (进化管理)                                      │
│    - scheduler   (任务调度)                                      │
│    - data        (数据查询)                                      │
│    - trading     (交易执行)                                      │
│                                                                   │
│  CLI 内部:                                                        │
│    解析命令 → 权限检查 → 调用 OS Kernel → 返回结果              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ 直接调用（同进程或 Unix Socket）
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent OS Kernel (Go)                          │
│                       daemon 模式运行                            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Core Services                                            │  │
│  │  Memory | Decision | Evolution | Scheduler | ...        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  通信方式:                                                       │
│    - Unix Domain Socket: /tmp/agent-os.sock                     │
│    - 或 直接库调用（CLI 和 Kernel 同一 Go Binary）              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ gRPC (仅 Driver 通信)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Device Drivers (Python gRPC)                        │
│                                                                   │
│  Market Driver | Feishu Driver | Trading Driver                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. CLI 命令设计

### 3.1 Memory 命令

```bash
# 写入记忆
agent-os memory write \
  --content "早盘分析：市场情绪积极，北向资金净流入 52 亿..." \
  --category "morning-analysis" \
  --agent-id "fin-agent" \
  --metadata '{"date": "2026-08-13", "symbols": ["600519.SH"]}'

# 输出 (JSON):
{
  "memory_id": 123,
  "namespace": "/memory/fin-agent/morning-analysis/2026-08-13",
  "created_at": "2026-08-13T08:30:00Z"
}

# 搜索记忆
agent-os memory search \
  --query "止盈 机械止盈" \
  --agent-id "fin-agent" \
  --top-k 10

# 输出 (JSON):
{
  "hits": [
    {
      "memory_id": 45,
      "content": "v13 复盘：机械止盈策略在崩盘日表现优异...",
      "score": 0.85,
      "category": "backtest"
    },
    ...
  ],
  "total": 10
}

# 查询记忆（按条件）
agent-os memory query \
  --category "decision" \
  --date-from "2026-08-01" \
  --date-to "2026-08-13" \
  --agent-id "fin-agent" \
  --limit 20
```

### 3.2 Decision 命令

```bash
# 记录决策
agent-os decision record \
  --action "watch" \
  --targets '["600519.SH", "000858.SZ"]' \
  --reason "早盘强势，北向资金流入" \
  --agent-id "fin-agent" \
  --metadata '{"confidence": 0.8}'

# 输出:
{
  "decision_id": 456,
  "action": "watch",
  "recorded_at": "2026-08-13T08:35:00Z"
}

# 查询决策历史
agent-os decision query \
  --action "buy" \
  --date-from "2026-08-01" \
  --agent-id "fin-agent"
```

### 3.3 Scheduler 命令

```bash
# 注册任务（agent-ts 启动时调用）
agent-os scheduler register \
  --name "morning_analysis" \
  --owner "fin-agent" \
  --cron "30 8 * * 1-5" \
  --agent-kind "fin" \
  --prompt "执行早盘分析..." \
  --timeout 1800 \
  --depends-on "market_data_sync"

# 输出:
{
  "task_id": 5,
  "name": "morning_analysis",
  "status": "registered"
}

# 查询任务列表
agent-os scheduler list --owner "fin-agent"

# 手动触发任务
agent-os scheduler trigger --task-id 5

# 查询执行历史
agent-os scheduler executions --task-id 5 --limit 10
```

### 3.4 Data 命令

```bash
# 获取实时行情（调用 Market Driver）
agent-os data quote --symbol "600519.SH"

# 输出 (JSON):
{
  "symbol": "600519.SH",
  "price": 1650.00,
  "change_pct": 2.5,
  "volume": 12500000,
  "timestamp": "2026-08-13T10:30:00Z"
}

# 获取 K 线数据
agent-os data kline \
  --symbol "600519.SH" \
  --period "1d" \
  --start "2026-08-01" \
  --end "2026-08-13"

# 获取市场情绪
agent-os data sentiment
```

### 3.5 Trading 命令

```bash
# 下单（调用 Trading Service）
agent-os trading order \
  --action "buy" \
  --symbol "600519.SH" \
  --quantity 100 \
  --price 1650.00 \
  --agent-id "fin-agent"

# 输出:
{
  "order_id": "ORD20260813001",
  "status": "pending",
  "submitted_at": "2026-08-13T10:35:00Z"
}

# 查询持仓
agent-os trading positions --agent-id "fin-agent"

# 查询订单状态
agent-os trading order-status --order-id "ORD20260813001"
```

### 3.6 Notification 命令

```bash
# 发送通知
agent-os notify send \
  --user "yunpeng" \
  --title "早盘分析完成" \
  --message "已完成早盘分析，关注 5 只强势股..." \
  --priority "normal" \
  --channels "feishu"

# 输出:
{
  "notification_id": 789,
  "channels": ["feishu"],
  "success": true
}
```

---

## 4. agent-ts 集成方式

### 4.1 工具定义（声明式）

```typescript
// agent-ts/src/infrastructure/tools/memory/memory-write-tool.ts
import { defineTool } from '../../core/tool-definition';
import { execAgentOS } from '../../utils/agent-os-cli';

export const memoryWriteTool = defineTool({
  name: 'memory_write',
  description: '写入记忆到 Agent OS',
  parameters: {
    type: 'object',
    properties: {
      content: { type: 'string', description: '记忆内容' },
      category: { type: 'string', description: '记忆分类' },
      metadata: { type: 'object', description: '元数据（可选）' }
    },
    required: ['content', 'category']
  },
  execute: async (params, context) => {
    const { content, category, metadata } = params;
    
    // 调用 CLI
    const result = await execAgentOS([
      'memory', 'write',
      '--content', content,
      '--category', category,
      '--agent-id', context.agentKind,  // 'fin' / 'memory' / 'evolution'
      '--metadata', JSON.stringify(metadata || {})
    ]);
    
    return result;  // 返回 JSON 结果给 LLM
  }
});
```

### 4.2 CLI 执行器（统一封装）

```typescript
// agent-ts/src/utils/agent-os-cli.ts
import { execSync } from 'child_process';

interface AgentOSResult {
  success: boolean;
  data?: any;
  error?: string;
}

/**
 * 执行 agent-os CLI 命令
 * @param args - 命令参数数组
 * @returns 解析后的 JSON 结果
 */
export async function execAgentOS(args: string[]): Promise<AgentOSResult> {
  try {
    // 构造完整命令
    const cmd = `agent-os ${args.map(escapeArg).join(' ')}`;
    
    // 执行（同步，因为 agent 需要等待结果）
    const stdout = execSync(cmd, {
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024,  // 10MB buffer
      timeout: 30000,                // 30s 超时
      env: {
        ...process.env,
        AGENT_OS_FORMAT: 'json',     // 强制 JSON 输出
      }
    });
    
    // 解析 JSON
    const result = JSON.parse(stdout.trim());
    
    return {
      success: true,
      data: result
    };
    
  } catch (err: any) {
    // 解析错误信息
    const stderr = err.stderr?.toString() || err.message;
    
    return {
      success: false,
      error: stderr
    };
  }
}

function escapeArg(arg: string): string {
  // Bash 转义
  if (arg.includes(' ') || arg.includes('"')) {
    return `"${arg.replace(/"/g, '\\"')}"`;
  }
  return arg;
}
```

### 4.3 错误处理

```typescript
// agent-ts/src/infrastructure/tools/memory/memory-write-tool.ts
execute: async (params, context) => {
  const result = await execAgentOS([...]);
  
  if (!result.success) {
    // CLI 执行失败
    if (result.error.includes('quota exceeded')) {
      throw new ToolExecutionError(
        'QUOTA_EXCEEDED',
        `Agent ${context.agentKind} 今日 Token 配额已用尽`,
        { recoverable: true }  // 明天可以重试
      );
    } else if (result.error.includes('permission denied')) {
      throw new ToolExecutionError(
        'PERMISSION_DENIED',
        `Agent ${context.agentKind} 无权写入记忆`,
        { recoverable: false }
      );
    } else {
      throw new ToolExecutionError(
        'CLI_ERROR',
        result.error,
        { recoverable: true }
      );
    }
  }
  
  return result.data;
}
```

---

## 5. CLI 实现（Go）

### 5.1 CLI 入口

```go
// cmd/agent-os/main.go
package main

import (
    "fmt"
    "os"
    
    "github.com/spf13/cobra"
    "agent-os/internal/cli"
)

func main() {
    rootCmd := &cobra.Command{
        Use:   "agent-os",
        Short: "Agent OS CLI - AI Agent 的操作系统",
    }
    
    // 注册子命令
    rootCmd.AddCommand(cli.MemoryCmd())
    rootCmd.AddCommand(cli.DecisionCmd())
    rootCmd.AddCommand(cli.SchedulerCmd())
    rootCmd.AddCommand(cli.DataCmd())
    rootCmd.AddCommand(cli.TradingCmd())
    rootCmd.AddCommand(cli.NotifyCmd())
    
    // 全局 flags
    rootCmd.PersistentFlags().String("socket", "/tmp/agent-os.sock", "Agent OS daemon socket")
    rootCmd.PersistentFlags().String("format", "json", "Output format: json|text")
    rootCmd.PersistentFlags().String("agent-id", "", "Agent ID (auto-detected if not provided)")
    
    if err := rootCmd.Execute(); err != nil {
        fmt.Fprintln(os.Stderr, err)
        os.Exit(1)
    }
}
```

### 5.2 Memory 命令实现

```go
// internal/cli/memory.go
package cli

import (
    "encoding/json"
    "fmt"
    
    "github.com/spf13/cobra"
    "agent-os/internal/kernel/memory"
    "agent-os/pkg/client"
)

func MemoryCmd() *cobra.Command {
    cmd := &cobra.Command{
        Use:   "memory",
        Short: "Memory management",
    }
    
    // memory write
    writeCmd := &cobra.Command{
        Use:   "write",
        Short: "Write a memory",
        RunE: func(cmd *cobra.Command, args []string) error {
            content, _ := cmd.Flags().GetString("content")
            category, _ := cmd.Flags().GetString("category")
            agentID, _ := cmd.Flags().GetString("agent-id")
            metadataJSON, _ := cmd.Flags().GetString("metadata")
            
            // 解析 metadata
            var metadata map[string]interface{}
            if metadataJSON != "" {
                json.Unmarshal([]byte(metadataJSON), &metadata)
            }
            
            // 连接 OS daemon (Unix Socket)
            client, err := client.NewClient(getSocketPath(cmd))
            if err != nil {
                return err
            }
            defer client.Close()
            
            // 调用 Kernel
            result, err := client.Memory.Write(context.Background(), &memory.WriteRequest{
                Content:  content,
                Category: category,
                AgentID:  agentID,
                Metadata: metadata,
            })
            if err != nil {
                return err
            }
            
            // 输出结果（JSON 格式）
            output, _ := json.Marshal(map[string]interface{}{
                "memory_id":  result.MemoryID,
                "namespace":  result.Namespace,
                "created_at": result.CreatedAt,
            })
            fmt.Println(string(output))
            
            return nil
        },
    }
    writeCmd.Flags().String("content", "", "Memory content (required)")
    writeCmd.Flags().String("category", "", "Memory category (required)")
    writeCmd.Flags().String("metadata", "{}", "Metadata JSON")
    writeCmd.MarkFlagRequired("content")
    writeCmd.MarkFlagRequired("category")
    
    // memory search
    searchCmd := &cobra.Command{
        Use:   "search",
        Short: "Search memories",
        RunE: func(cmd *cobra.Command, args []string) error {
            query, _ := cmd.Flags().GetString("query")
            topK, _ := cmd.Flags().GetInt("top-k")
            agentID, _ := cmd.Flags().GetString("agent-id")
            
            client, _ := client.NewClient(getSocketPath(cmd))
            defer client.Close()
            
            result, err := client.Memory.Search(context.Background(), &memory.SearchRequest{
                Query:   query,
                TopK:    topK,
                AgentID: agentID,
            })
            if err != nil {
                return err
            }
            
            output, _ := json.Marshal(result)
            fmt.Println(string(output))
            
            return nil
        },
    }
    searchCmd.Flags().String("query", "", "Search query (required)")
    searchCmd.Flags().Int("top-k", 10, "Number of results")
    searchCmd.MarkFlagRequired("query")
    
    cmd.AddCommand(writeCmd)
    cmd.AddCommand(searchCmd)
    
    return cmd
}
```

### 5.3 Unix Socket 通信

```go
// pkg/client/client.go
package client

import (
    "context"
    "net"
    "net/http"
    
    "agent-os/internal/kernel/memory"
    "agent-os/internal/kernel/decision"
)

type Client struct {
    conn    net.Conn
    Memory  *MemoryClient
    Decision *DecisionClient
    // ...
}

func NewClient(socketPath string) (*Client, error) {
    // 连接到 OS daemon 的 Unix Socket
    conn, err := net.Dial("unix", socketPath)
    if err != nil {
        return nil, err
    }
    
    client := &Client{
        conn: conn,
    }
    
    // 初始化各个子客户端
    client.Memory = &MemoryClient{conn: conn}
    client.Decision = &DecisionClient{conn: conn}
    
    return client, nil
}

type MemoryClient struct {
    conn net.Conn
}

func (c *MemoryClient) Write(ctx context.Context, req *memory.WriteRequest) (*memory.WriteResponse, error) {
    // 通过 Unix Socket 发送请求到 OS Kernel
    // 协议：简单的 JSON-RPC over Unix Socket
    
    rpcReq := map[string]interface{}{
        "method": "memory.write",
        "params": req,
    }
    
    json.NewEncoder(c.conn).Encode(rpcReq)
    
    var rpcResp struct {
        Result *memory.WriteResponse `json:"result"`
        Error  string                `json:"error"`
    }
    json.NewDecoder(c.conn).Decode(&rpcResp)
    
    if rpcResp.Error != "" {
        return nil, errors.New(rpcResp.Error)
    }
    
    return rpcResp.Result, nil
}
```

---

## 6. Driver/Service 也用 CLI？

### 6.1 Market Driver CLI

**设计思路**：Driver 提供自己的 CLI，Agent OS 调用它

```bash
# Market Driver 独立 CLI
market-driver quote --symbol "600519.SH"

# 输出 (JSON):
{
  "symbol": "600519.SH",
  "price": 1650.00,
  ...
}
```

**Agent OS 调用方式**：

```go
// internal/drivers/market/cli_driver.go
type MarketCLIDriver struct {
    cliPath string  // "/usr/local/bin/market-driver"
}

func (d *MarketCLIDriver) GetQuote(ctx context.Context, symbol string) (*Quote, error) {
    // 调用 market-driver CLI
    cmd := exec.CommandContext(ctx, d.cliPath, "quote", "--symbol", symbol)
    
    output, err := cmd.Output()
    if err != nil {
        return nil, err
    }
    
    var quote Quote
    json.Unmarshal(output, &quote)
    
    return &quote, nil
}
```

### 6.2 CLI vs gRPC Driver 对比

| 维度 | CLI Driver | gRPC Driver |
|---|---|---|
| **复杂度** | 低（直接调命令） | 中（需要 proto + gRPC server） |
| **性能** | 中（进程启动开销） | 高（长连接复用） |
| **状态管理** | 无状态（每次新进程） | 有状态（连接池、缓存） |
| **调试** | 容易（终端直接测） | 较难（需要 grpcurl） |
| **适用场景** | 低频调用、原型验证 | 高频调用、生产环境 |

### 6.3 混合方案（推荐）

**Phase 1（MVP）**：全部用 CLI
- agent-os 是 CLI
- Market Driver 也是 CLI（Python script 包装）
- 快速验证架构

**Phase 2（优化）**：高频路径改 gRPC
- agent → OS：保持 CLI（调用频率低，每轮对话几次）
- OS → Driver：改 gRPC（调用频率高，每次可能调几十次）

---

## 7. 完整调用链示例

### 案例：fin-agent 写入早盘分析记忆

```
┌─────────────────────────────────────────────────────────────┐
│ fin-agent (LLM 推理)                                         │
│                                                               │
│ LLM 决定调用工具: memory_write({content: "...", ...})        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ agent-ts (Node.js)                                           │
│                                                               │
│ execSync('agent-os memory write \                            │
│   --content "早盘分析..." \                                  │
│   --category "morning-analysis" \                            │
│   --agent-id "fin-agent"')                                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ 启动子进程
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ agent-os CLI (Go Binary)                                     │
│                                                               │
│ 1. 解析命令: memory write --content ... --agent-id fin      │
│ 2. 连接 Unix Socket: /tmp/agent-os.sock                     │
│ 3. 发送 JSON-RPC 请求                                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ Unix Socket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent OS Daemon (Go)                                         │
│                                                               │
│ 1. 接收请求: method="memory.write"                          │
│ 2. 权限检查: fin-agent 有 memory.write 能力吗？             │
│ 3. 配额检查: fin-agent 今天还有 token 吗？                  │
│ 4. 调用 Memory System                                        │
│    - 写入 PostgreSQL                                         │
│    - 生成向量 embedding                                      │
│    - 更新索引                                                │
│ 5. 返回结果                                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ 返回 JSON
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ agent-os CLI                                                 │
│                                                               │
│ 输出到 stdout (JSON):                                        │
│ {"memory_id": 123, "namespace": "/memory/fin-agent/...", ...}│
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ stdout 返回
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ agent-ts                                                     │
│                                                               │
│ const result = JSON.parse(stdout);                           │
│ return result;  // 返回给 LLM                                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ fin-agent                                                    │
│                                                               │
│ 工具返回成功，继续推理下一步...                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 与 HTTP API 的对比

| 维度 | CLI 方式 | HTTP API 方式 |
|---|---|---|
| **agent 调用** | `execSync('agent-os memory write ...')` | `fetch('http://...', {method: 'POST', ...})` |
| **网络依赖** | 无（本地二进制） | 有（需要 HTTP 服务启动） |
| **错误发现** | 立即（CLI 返回错误码） | 延迟（首次调用才发现） |
| **调试** | 终端手动运行命令 | 需要 curl/Postman |
| **LLM 友好度** | 高（LLM 擅长生成 CLI） | 中（需要构造 HTTP 请求） |
| **性能** | 中（进程启动 ~10ms） | 高（HTTP 连接复用） |
| **复杂度** | 低（execSync 一行） | 中（fetch + 错误处理） |
| **web 调用** | 不适合 | 天然适合 |

**结论**：
- **agent → OS**：用 CLI（agent 场景）
- **web → OS**：用 HTTP API（浏览器场景）
- **OS → Driver**：Phase 1 用 CLI，Phase 2 改 gRPC（性能优化）

---

## 9. 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│ 系统部署                                                     │
└─────────────────────────────────────────────────────────────┘

/usr/local/bin/
  ├── agent-os              # CLI + Daemon (同一个 Go Binary)
  ├── market-driver         # Python script (CLI 包装)
  ├── feishu-driver         # Python script (CLI 包装)
  └── ...

/tmp/
  └── agent-os.sock         # Unix Domain Socket (Daemon 监听)

启动流程:
  1. agent-os daemon start           # 启动 daemon（后台）
  2. agent-ts 启动                   # agent 启动
  3. agent-ts 调用 agent-os CLI      # CLI 通过 socket 与 daemon 通信
```

---

## 10. 实施路径

### Phase 1：CLI 架构（MVP）
- [ ] agent-os CLI 框架（Cobra）
- [ ] Unix Socket 通信（CLI ↔ Daemon）
- [ ] Memory/Decision/Scheduler 命令
- [ ] agent-ts 集成（execAgentOS 封装）
- [ ] Market Driver CLI 包装

### Phase 2：性能优化
- [ ] OS → Driver 改 gRPC（高频路径）
- [ ] CLI 输出格式优化（table/json 切换）
- [ ] 命令补全（bash/zsh completion）

### Phase 3：生产增强
- [ ] CLI 日志（`--verbose` flag）
- [ ] CLI 配置文件（`~/.agent-os/config.yaml`）
- [ ] CLI 版本管理（`agent-os version`）

---

## 11. 关键决策

### 决策 1：为什么 agent-ts 不直接调 Go 函数？

**为什么不用 FFI（Node-API）**：
- 复杂度高（需要 C++ binding）
- 调试困难（段错误难排查）
- 耦合紧（Go 升级影响 Node.js）

**CLI 的优势**：
- 解耦（agent-ts 和 OS 独立进程）
- 调试友好（终端直接测试）
- 语言无关（未来换 Python agent 也能用）

### 决策 2：为什么 web 还用 HTTP？

**web-frontend 不用 CLI**：
- 浏览器无法执行本地二进制
- HTTP 是 web 天然通信方式
- CLI 是为 agent 设计的

**结论**：双协议
- agent → OS：CLI
- web → OS：HTTP API（同一个 Go Binary，多个入口）

---

## 12. 你的决策点

1. **认可 CLI 架构吗？**
   - agent → OS 用 CLI
   - web → OS 用 HTTP
   - OS → Driver Phase 1 用 CLI，Phase 2 改 gRPC

2. **Unix Socket vs HTTP**：
   - CLI ↔ Daemon 通信用 Unix Socket？
   - 还是 CLI 直接链接 Kernel（同 binary）？

3. **Driver CLI 包装**：
   - Market Driver 提供 `market-driver` CLI？
   - 还是保持 gRPC？

4. **实施时机**：
   - MVP 全部 CLI？
   - 还是先 HTTP，Phase 2 再加 CLI？

**等你确认！**
