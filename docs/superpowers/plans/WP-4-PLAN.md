# WP-4: Agent-TS Integration & Driver Architecture Plan

> **Work Package**: WP-4  
> **Title**: agent-ts 完全切换 + Driver 架构改造  
> **Duration**: 2-3 days  
> **Status**: 🚧 Planning  
> **Dependencies**: WP-1 (Scheduler), WP-2 (Resource), WP-3 (Memory), WP-7 (Decision), WP-8 (Event Bus)

---

## 📋 Overview

This work package has two main objectives:

1. **agent-ts → Agent OS 完全切换**
   - 任务调度从本地 Cron → Agent OS Scheduler
   - 工具调用从直接调用 → Agent OS CLI
   - 实现 Webhook 接口接收 OS 触发

2. **quantsys-v2 → Driver 模式改造**
   - 设计 Driver 抽象层
   - quantsys-v2 暴露 Driver CLI 接口
   - Agent OS 通过 Driver 调用 quantsys-v2
   - 保持向后兼容（agent-ts 仍可直接调用 v2 API）

---

## 🎯 Architecture Design

### Current Architecture (AS-IS)

```
┌─────────────────────────────────────────────────────┐
│                   agent-ts                          │
│                                                     │
│  ┌──────────────┐         ┌──────────────┐        │
│  │ Local Cron   │         │ Tools        │        │
│  │ (node-cron)  │         │ (60+ tools)  │        │
│  └──────┬───────┘         └──────┬───────┘        │
│         │                        │                 │
│         │ Schedule               │ Direct Call     │
│         ↓                        ↓                 │
│  ┌──────────────────────────────────────┐         │
│  │  Session Loop (AI Decision)          │         │
│  └──────────────────────────────────────┘         │
│         │                        │                 │
│         │ HTTP API               │ HTTP API        │
└─────────┼────────────────────────┼─────────────────┘
          ↓                        ↓
    ┌──────────────────────────────────────┐
    │        quantsys-v2 (Flask)           │
    │  • Pool API                          │
    │  • Signal API                        │
    │  • Trade API                         │
    │  • Data API                          │
    └──────────────────────────────────────┘
```

**Problems**:
- agent-ts 本地 Cron 无法统一管理
- 缺少任务执行监控和重试
- 无法跨 agent 协调任务
- quantsys-v2 紧耦合

---

### Target Architecture (TO-BE)

```
┌─────────────────────────────────────────────────────┐
│                   agent-ts                          │
│                                                     │
│  ┌──────────────┐         ┌──────────────┐        │
│  │ Task         │         │ Tools        │        │
│  │ Registration │         │ (OS CLI)     │        │
│  └──────┬───────┘         └──────┬───────┘        │
│         │                        │                 │
│         │ Register on            │ CLI Call        │
│         │ Startup                │                 │
└─────────┼────────────────────────┼─────────────────┘
          ↓                        ↓
    ┌─────────────────────────────────────────┐
    │           Agent OS (Go)                 │
    │                                         │
    │  ┌───────────────┐   ┌───────────────┐ │
    │  │  Scheduler    │   │  Data Command │ │
    │  │  (Cron/DAG)   │   │  (Driver CLI) │ │
    │  └───────┬───────┘   └───────┬───────┘ │
    │          │                   │         │
    │          │ Trigger           │ Call    │
    │          ↓                   ↓         │
    │  ┌──────────────┐   ┌───────────────┐ │
    │  │   Webhook    │   │ Market Driver │ │
    │  │   (HTTP)     │   │  (Python CLI) │ │
    │  └──────┬───────┘   └───────┬───────┘ │
    └─────────┼───────────────────┼─────────┘
              ↓                   ↓
       ┌──────────────┐   ┌─────────────────┐
       │  agent-ts    │   │  quantsys-v2    │
       │  Webhook     │   │  Driver CLI     │
       │  Endpoint    │   │  (Python)       │
       └──────────────┘   └─────────────────┘
```

**Benefits**:
- ✅ 统一任务调度（Agent OS Scheduler）
- ✅ 任务执行监控和重试
- ✅ Driver 抽象层（可替换数据源）
- ✅ 跨 agent 任务协调
- ✅ 事件驱动触发（Event Bus）

---

## 📊 Task Breakdown

### Part A: agent-ts Integration (1.5 days)

#### Task A1: Task Registration System (4 hours)

**Objective**: agent-ts 启动时自动注册任务到 Agent OS

**Implementation**:

1. **Create Task Registry** (`agent-ts/src/infrastructure/agent-os/task-registry.ts`)
   ```typescript
   export interface TaskDefinition {
     name: string;
     description: string;
     cron: string;
     owner: string;
     priority: number;
     tags: string[];
   }

   export class TaskRegistry {
     private tasks: TaskDefinition[] = [];

     register(task: TaskDefinition): void {
       this.tasks.push(task);
     }

     async syncToOS(): Promise<void> {
       const cli = getAgentOSCLI();
       for (const task of this.tasks) {
         await cli.scheduler.register(task);
       }
     }
   }
   ```

2. **Update Skills to Declare Tasks** (`agent-ts/src/infrastructure/skills/*.md`)
   ```yaml
   # skills/daily-pool-refresh.md
   ---
   name: daily-pool-refresh
   schedule:
     cron: "0 2 * * *"
     priority: 8
     tags: [pool, daily]
   ---
   ```

3. **Startup Hook** (`agent-ts/src/index.ts`)
   ```typescript
   async function registerTasksToOS() {
     const registry = new TaskRegistry();
     
     // Load from skills
     const skills = await loadAllSkills();
     for (const skill of skills) {
       if (skill.schedule) {
         registry.register({
           name: skill.name,
           description: skill.description,
           cron: skill.schedule.cron,
           owner: 'fin-agent',
           priority: skill.schedule.priority || 5,
           tags: skill.schedule.tags || [],
         });
       }
     }
     
     await registry.syncToOS();
     console.log('✅ Tasks registered to Agent OS');
   }
   ```

**Deliverables**:
- [ ] `task-registry.ts` implementation
- [ ] Skills YAML schema update (add `schedule` field)
- [ ] Startup hook in `index.ts`
- [ ] Unit tests for TaskRegistry

**Verification**:
```bash
# Start agent-ts
npm start

# Check tasks in Agent OS
agent-os scheduler list | grep fin-agent

# Should see:
# - daily-pool-refresh (0 2 * * *)
# - morning-signal-scan (0 9 * * *)
# - ...
```

---

#### Task A2: Webhook Endpoint (4 hours)

**Objective**: 实现 Webhook 接口，接收 Agent OS 触发

**Implementation**:

1. **Webhook Endpoint** (`agent-ts/src/api/webhook.ts`)
   ```typescript
   import express from 'express';
   import { SessionOrchestrator } from '../core/orchestrator.js';

   const router = express.Router();

   router.post('/trigger', async (req, res) => {
     const { task_id, task_name, execution_id, params } = req.body;
     
     console.log(`📥 Webhook triggered: ${task_name} (execution: ${execution_id})`);
     
     try {
       // Create session for this task
       const orchestrator = new SessionOrchestrator();
       const session = await orchestrator.createSession({
         mode: 'auto',
         initialPrompt: `/skill ${task_name}`,
         metadata: {
           task_id,
           execution_id,
           triggered_by: 'agent-os',
           params,
         },
       });
       
       // Run task
       const result = await session.run();
       
       // Report back to Agent OS
       const cli = getAgentOSCLI();
       await cli.scheduler.updateExecution({
         execution_id,
         status: 'completed',
         result: result.summary,
       });
       
       res.json({ success: true, execution_id });
     } catch (error: any) {
       console.error(`❌ Webhook execution failed:`, error);
       
       // Report failure to Agent OS
       const cli = getAgentOSCLI();
       await cli.scheduler.updateExecution({
         execution_id,
         status: 'failed',
         error: error.message,
       });
       
       res.status(500).json({ success: false, error: error.message });
     }
   });

   export default router;
   ```

2. **Register Webhook Route** (`agent-ts/src/api/index.ts`)
   ```typescript
   import webhookRouter from './webhook.js';
   
   app.use('/api/webhook', webhookRouter);
   ```

3. **Update Agent OS with Webhook URL** (`agent-ts/src/infrastructure/agent-os/task-registry.ts`)
   ```typescript
   async syncToOS(): Promise<void> {
     const cli = getAgentOSCLI();
     const webhookUrl = process.env.AGENT_WEBHOOK_URL || 'http://localhost:3000/api/webhook/trigger';
     
     for (const task of this.tasks) {
       await cli.scheduler.register({
         ...task,
         webhook_url: webhookUrl,
       });
     }
   }
   ```

**Deliverables**:
- [ ] `webhook.ts` endpoint implementation
- [ ] Session creation from webhook
- [ ] Error handling and reporting
- [ ] Integration test

**Verification**:
```bash
# Manual trigger from Agent OS
agent-os scheduler trigger --task-id <id>

# Check agent-ts logs
# Should see: 📥 Webhook triggered: daily-pool-refresh (execution: xxx)

# Check execution status
agent-os scheduler executions --task-id <id>
# Should see: completed
```

---

#### Task A3: Remove Local Cron (2 hours)

**Objective**: 删除 agent-ts 本地 Cron 代码

**Implementation**:

1. **Find and Remove**:
   ```bash
   # Search for node-cron usage
   grep -r "node-cron" agent-ts/src/
   grep -r "schedule(" agent-ts/src/
   
   # Remove:
   # - agent-ts/src/infrastructure/scheduler/*
   # - Any CronJob imports
   # - package.json dependency
   ```

2. **Update Bootstrap**:
   - Remove cron initialization
   - Keep only task registration

3. **Update Documentation**:
   - README: mention Agent OS scheduling
   - Remove cron configuration docs

**Deliverables**:
- [ ] Remove `node-cron` dependency
- [ ] Remove local scheduler code
- [ ] Update documentation

**Verification**:
```bash
# Search should return nothing
grep -r "node-cron" agent-ts/

# agent-ts should still work (triggered via webhook)
npm start
```

---

### Part B: Driver Architecture (1-1.5 days)

#### Task B1: Driver Design & Spec (2 hours)

**Objective**: 设计 Driver 抽象层规范

**Driver CLI Interface Spec**:

```bash
# Generic driver interface
<driver-name> <command> [options]

# Examples:
market-driver quote --symbol 600519.SH --format json
market-driver kline --symbol 600519.SH --period daily --limit 100
market-driver fundamentals --symbol 600519.SH --fields pe,pb,roe

# Standard output format (JSON)
{
  "success": true,
  "data": { ... },
  "metadata": {
    "source": "akshare",
    "timestamp": "2026-08-14T12:00:00Z",
    "latency_ms": 45
  },
  "error": null
}

# Standard error format
{
  "success": false,
  "data": null,
  "error": {
    "code": "DATA_UNAVAILABLE",
    "message": "Symbol not found",
    "details": { ... }
  }
}
```

**Driver Categories**:

1. **Market Driver** (`market-driver`)
   - Commands: `quote`, `kline`, `fundamentals`, `realtime`
   - Backend: quantsys-v2 (wrap existing APIs)

2. **Notification Driver** (`notification-driver`)
   - Commands: `send`, `list-channels`, `test`
   - Backend: Feishu/WeChat/Email

3. **Trade Driver** (`trade-driver`) - Future
   - Commands: `order`, `cancel`, `query`, `positions`
   - Backend: Broker API

**Deliverables**:
- [ ] Driver CLI interface spec document
- [ ] Standard output format spec
- [ ] Error handling spec

---

#### Task B2: quantsys-v2 Driver CLI (6 hours)

**Objective**: quantsys-v2 暴露 Driver CLI 接口

**Implementation**:

1. **Create Driver Entry Point** (`quantsys-v2/drivers/market_driver.py`)
   ```python
   #!/usr/bin/env python3
   """
   Market Driver CLI for Agent OS
   """
   import click
   import json
   import sys
   from datetime import datetime
   
   # Import existing v2 services
   from api.services.stock_service import StockService
   from api.services.kline_service import KlineService
   
   @click.group()
   def cli():
       """Market data driver for Agent OS"""
       pass
   
   @cli.command()
   @click.option('--symbol', required=True, help='Stock symbol (e.g., 600519.SH)')
   @click.option('--format', default='json', help='Output format')
   def quote(symbol: str, format: str):
       """Get real-time quote for a symbol"""
       start = datetime.now()
       
       try:
           service = StockService()
           data = service.get_quote(symbol)
           
           response = {
               "success": True,
               "data": data,
               "metadata": {
                   "source": "quantsys-v2",
                   "timestamp": datetime.now().isoformat(),
                   "latency_ms": int((datetime.now() - start).total_seconds() * 1000)
               },
               "error": None
           }
           
           print(json.dumps(response, ensure_ascii=False))
           sys.exit(0)
           
       except Exception as e:
           response = {
               "success": False,
               "data": None,
               "error": {
                   "code": "DRIVER_ERROR",
                   "message": str(e),
                   "details": {}
               }
           }
           
           print(json.dumps(response, ensure_ascii=False))
           sys.exit(1)
   
   @cli.command()
   @click.option('--symbol', required=True)
   @click.option('--period', default='daily', help='daily/weekly/monthly')
   @click.option('--limit', default=100, type=int)
   def kline(symbol: str, period: str, limit: int):
       """Get K-line data"""
       start = datetime.now()
       
       try:
           service = KlineService()
           data = service.get_kline(symbol, period=period, limit=limit)
           
           response = {
               "success": True,
               "data": data,
               "metadata": {
                   "source": "quantsys-v2",
                   "timestamp": datetime.now().isoformat(),
                   "latency_ms": int((datetime.now() - start).total_seconds() * 1000)
               },
               "error": None
           }
           
           print(json.dumps(response, ensure_ascii=False, default=str))
           sys.exit(0)
           
       except Exception as e:
           response = {
               "success": False,
               "data": None,
               "error": {
                   "code": "DRIVER_ERROR",
                   "message": str(e)
               }
           }
           
           print(json.dumps(response, ensure_ascii=False))
           sys.exit(1)
   
   if __name__ == '__main__':
       cli()
   ```

2. **Make Executable**:
   ```bash
   chmod +x quantsys-v2/drivers/market_driver.py
   ln -s $(pwd)/quantsys-v2/drivers/market_driver.py /usr/local/bin/market-driver
   ```

3. **Update quantsys-v2 Services** (if needed):
   - Extract reusable logic from Flask routes
   - Create service layer methods that can be called from CLI

**Deliverables**:
- [ ] `market_driver.py` CLI implementation
- [ ] Commands: `quote`, `kline`, `fundamentals`
- [ ] Standard JSON output format
- [ ] Error handling
- [ ] Installation script

**Verification**:
```bash
# Test driver CLI
market-driver quote --symbol 600519.SH
# Output: {"success": true, "data": {...}}

market-driver kline --symbol 600519.SH --period daily --limit 10
# Output: {"success": true, "data": [...]}}
```

---

#### Task B3: Agent OS Driver Integration (4 hours)

**Objective**: Agent OS Data 命令调用 Driver

**Implementation**:

1. **Driver Manager** (`agent-os/internal/drivers/manager.go`)
   ```go
   package drivers
   
   import (
       "context"
       "encoding/json"
       "fmt"
       "os/exec"
       "time"
   )
   
   type DriverResponse struct {
       Success  bool                   `json:"success"`
       Data     interface{}            `json:"data"`
       Metadata map[string]interface{} `json:"metadata"`
       Error    *DriverError           `json:"error"`
   }
   
   type DriverError struct {
       Code    string                 `json:"code"`
       Message string                 `json:"message"`
       Details map[string]interface{} `json:"details"`
   }
   
   type DriverManager struct {
       timeout time.Duration
   }
   
   func NewDriverManager() *DriverManager {
       return &DriverManager{
           timeout: 30 * time.Second,
       }
   }
   
   func (m *DriverManager) Call(ctx context.Context, driverName string, args []string) (*DriverResponse, error) {
       ctx, cancel := context.WithTimeout(ctx, m.timeout)
       defer cancel()
       
       cmd := exec.CommandContext(ctx, driverName, args...)
       output, err := cmd.CombinedOutput()
       
       if err != nil {
           return nil, fmt.Errorf("driver execution failed: %w", err)
       }
       
       var response DriverResponse
       if err := json.Unmarshal(output, &response); err != nil {
           return nil, fmt.Errorf("invalid driver response: %w", err)
       }
       
       return &response, nil
   }
   ```

2. **Update Data Command** (`agent-os/internal/cmd/data.go`)
   ```go
   var dataQuoteCmd = &cobra.Command{
       Use:   "quote",
       Short: "Get real-time quote",
       RunE: func(cmd *cobra.Command, args []string) error {
           symbol, _ := cmd.Flags().GetString("symbol")
           
           manager := drivers.NewDriverManager()
           response, err := manager.Call(
               context.Background(),
               "market-driver",
               []string{"quote", "--symbol", symbol},
           )
           
           if err != nil {
               return err
           }
           
           if !response.Success {
               return fmt.Errorf("driver error: %s", response.Error.Message)
           }
           
           // Print data
           data, _ := json.MarshalIndent(response.Data, "", "  ")
           fmt.Println(string(data))
           
           return nil
       },
   }
   ```

**Deliverables**:
- [ ] `drivers/manager.go` implementation
- [ ] Updated `cmd/data.go` to use DriverManager
- [ ] Driver registry (map driver name → binary path)
- [ ] Unit tests

**Verification**:
```bash
# Call through Agent OS
agent-os data quote --symbol 600519.SH

# Should output the same as direct driver call
market-driver quote --symbol 600519.SH
```

---

#### Task B4: Backward Compatibility (2 hours)

**Objective**: agent-ts 仍可直接调用 quantsys-v2 HTTP API

**Strategy**:
- quantsys-v2 HTTP API 保持不变
- agent-ts 工具可选择：
  - **Option 1**: 通过 Agent OS CLI 调用（推荐，统一管理）
  - **Option 2**: 直接调用 quantsys-v2 HTTP API（向后兼容）

**Implementation**:

1. **Tool Configuration** (`agent-ts/src/infrastructure/tools/config.ts`)
   ```typescript
   export const TOOL_BACKEND = {
     pool_manage: process.env.USE_AGENT_OS ? 'agent-os' : 'v2-direct',
     signal_scan: process.env.USE_AGENT_OS ? 'agent-os' : 'v2-direct',
     // ...
   };
   ```

2. **Dual-Mode Tool** (`agent-ts/src/infrastructure/tools/pool-manage.ts`)
   ```typescript
   async function poolManage(params: PoolManageParams) {
     if (TOOL_BACKEND.pool_manage === 'agent-os') {
       // Call through Agent OS
       const cli = getAgentOSCLI();
       return await cli.data.poolManage(params);
     } else {
       // Direct call to quantsys-v2
       const response = await axios.post('http://localhost:5001/api/pools/manage', params);
       return response.data;
     }
   }
   ```

**Deliverables**:
- [ ] Tool backend configuration
- [ ] Dual-mode implementation for key tools
- [ ] Environment variable `USE_AGENT_OS` (default: false for now)

---

## 🗂️ File Structure

### New Files

```
agent-ts/
├── src/
│   ├── infrastructure/
│   │   └── agent-os/
│   │       ├── task-registry.ts          # NEW
│   │       └── task-sync.ts              # NEW
│   └── api/
│       └── webhook.ts                    # NEW
│
quantsys-v2/
├── drivers/
│   ├── __init__.py                       # NEW
│   ├── market_driver.py                  # NEW
│   └── README.md                         # NEW
│
agent-os/
└── internal/
    └── drivers/
        ├── manager.go                     # NEW
        ├── manager_test.go                # NEW
        └── registry.go                    # NEW
```

---

## 🧪 Testing Strategy

### Unit Tests

```bash
# agent-ts
npm test -- task-registry.test.ts
npm test -- webhook.test.ts

# quantsys-v2
pytest drivers/test_market_driver.py

# agent-os
go test ./internal/drivers/...
```

### Integration Tests

```bash
# Test 1: Task Registration
cd agent-ts && npm start
agent-os scheduler list | grep daily-pool-refresh
# Expected: task registered

# Test 2: Webhook Trigger
agent-os scheduler trigger --task-id <id>
# Check agent-ts logs: should see webhook received

# Test 3: Driver Call
market-driver quote --symbol 600519.SH
# Expected: JSON output with quote data

# Test 4: Agent OS → Driver
agent-os data quote --symbol 600519.SH
# Expected: same output as direct driver call

# Test 5: End-to-End
# 1. Register task
# 2. OS triggers task via webhook
# 3. agent-ts executes, calls data through OS
# 4. OS calls driver
# 5. Driver returns data
# 6. agent-ts completes, reports back to OS
```

---

## 📊 Timeline

### Day 1 (8 hours)
- **Morning (4h)**: Task A1 (Task Registration)
- **Afternoon (4h)**: Task A2 (Webhook Endpoint)

### Day 2 (8 hours)
- **Morning (2h)**: Task A3 (Remove Local Cron)
- **Morning (2h)**: Task B1 (Driver Design)
- **Afternoon (4h)**: Task B2 (quantsys-v2 Driver CLI) - Part 1

### Day 3 (6 hours)
- **Morning (2h)**: Task B2 (quantsys-v2 Driver CLI) - Part 2
- **Morning (2h)**: Task B3 (Agent OS Driver Integration)
- **Afternoon (2h)**: Task B4 (Backward Compatibility) + Testing

**Total: 22 hours (~3 days)**

---

## ✅ Acceptance Criteria

### Part A: agent-ts Integration
- [ ] agent-ts 启动时自动注册任务到 Agent OS
- [ ] `agent-os scheduler list` 显示所有 agent-ts 任务
- [ ] Agent OS 可通过 Webhook 触发 agent-ts 任务
- [ ] agent-ts 任务执行完毕后报告状态到 Agent OS
- [ ] 本地 `node-cron` 代码已完全移除
- [ ] agent-ts 启动不再需要 cron 配置

### Part B: Driver Architecture
- [ ] `market-driver` CLI 可独立运行
- [ ] Driver 输出标准 JSON 格式
- [ ] Agent OS `data` 命令可调用 Driver
- [ ] Driver 调用延迟 < 500ms
- [ ] agent-ts 可选择通过 Agent OS 或直接调用 v2
- [ ] 向后兼容：不启用 Agent OS 时，agent-ts 仍可工作

### Integration
- [ ] End-to-end flow 测试通过
- [ ] 性能：Webhook 触发延迟 < 1s
- [ ] 错误处理：Driver 失败时正确报告
- [ ] 日志：完整的调用链路日志

---

## 🚨 Risk Mitigation

### Risk 1: Webhook 延迟高
**现象**: OS 触发 → agent-ts 响应时间 > 5s  
**缓解**: 
- Webhook 使用异步响应（立即返回 202，后台执行）
- Agent OS 轮询执行状态

### Risk 2: Driver CLI 性能差
**现象**: Python 启动开销 > 1s  
**缓解**:
- 考虑 Driver 常驻模式（HTTP Server）
- 或使用 Go 重写高频 Driver

### Risk 3: agent-ts 任务迁移中断服务
**现象**: 切换过程中任务停止执行  
**缓解**:
- 分阶段迁移（先迁移非关键任务）
- 保留 `USE_AGENT_OS=false` 回退选项
- 灰度发布（逐步开启）

### Risk 4: quantsys-v2 Driver 改造破坏现有 API
**现象**: Driver CLI 开发影响 HTTP API  
**缓解**:
- Driver 复用现有 Service 层，不改 API
- Driver 和 API 并行存在
- 充分的回归测试

---

## 📝 Migration Checklist

### Pre-Migration
- [ ] 备份当前 agent-ts cron 配置
- [ ] 记录所有定时任务列表
- [ ] 准备回滚方案

### Migration Steps
1. [ ] 部署 Agent OS（已完成 WP-1/2/3/7/8）
2. [ ] 实现 quantsys-v2 Driver CLI
3. [ ] 测试 Driver CLI
4. [ ] 实现 agent-ts Task Registration
5. [ ] 测试任务注册
6. [ ] 实现 agent-ts Webhook
7. [ ] 测试 Webhook 触发
8. [ ] 灰度启用：`USE_AGENT_OS=true` for 1 task
9. [ ] 验证 1 周稳定性
10. [ ] 全量启用：所有任务切换
11. [ ] 移除 node-cron 代码

### Post-Migration Validation
- [ ] 所有定时任务正常触发
- [ ] 任务执行成功率 > 99%
- [ ] 无任务丢失
- [ ] Agent OS 监控正常
- [ ] 日志完整可追溯

---

## 📚 Documentation Deliverables

1. **Driver Development Guide** (`docs/DRIVER-GUIDE.md`)
   - How to create a new driver
   - Driver CLI interface spec
   - Testing guide

2. **agent-ts Integration Guide** (`agent-ts/docs/AGENT-OS-INTEGRATION.md`)
   - Task registration
   - Webhook setup
   - Migration guide

3. **quantsys-v2 Driver README** (`quantsys-v2/drivers/README.md`)
   - Driver CLI usage
   - Installation
   - Examples

4. **Architecture Decision Record** (`docs/adr/004-driver-architecture.md`)
   - Why Driver abstraction
   - Alternatives considered
   - Trade-offs

---

## 🎯 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Task registration success rate** | 100% | `agent-os scheduler list` 显示所有任务 |
| **Webhook response time** | < 1s | 从 OS 触发到 agent-ts 收到 |
| **Task execution success rate** | > 99% | 7 天内成功率 |
| **Driver call latency** | < 500ms | `market-driver` 响应时间 |
| **Code removed** | > 200 lines | 移除的 node-cron 代码 |
| **Zero downtime** | 0 | 迁移过程服务不中断 |

---

## 🔄 Next Steps

After WP-4 completion:

1. **WP-9: Production Optimization**
   - Performance benchmarking
   - Monitoring
   - Documentation

2. **Optional: More Drivers**
   - Notification Driver (Feishu/WeChat 统一接口)
   - Trade Driver (future)
   - Data Driver 扩展（更多数据源）

3. **Optional: Driver Marketplace**
   - Community-contributed drivers
   - Driver versioning
   - Driver discovery

---

**Status**: Ready to start  
**Next Action**: Begin Task A1 (Task Registration System)  
**Estimated Completion**: 3 days from start
