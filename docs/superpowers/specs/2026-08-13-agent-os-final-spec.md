# Agent OS 最终规格说明书

> **创建时间**: 2026-08-13  
> **基于**: 现有系统全景审计（agent-ts + quantsys-v2 + web-frontend）  
> **状态**: Final Spec - 待批准后开工

---

## 0. 执行摘要

**Agent OS 定位**：AI Agent 的操作系统底座，提供**资源管理、任务调度、持久化存储、服务发现、权限管控、进程间通信**六大核心能力。

**核心使命**：解决当前系统的六大痛点（调度分裂、资源无管控、状态分散、耦合严重、权限缺失、职责不清）。

**不做什么**：不管 Agent 内部逻辑（Prompt、LLM 调用）、不管业务策略（选股、交易决策）、不管前端展示。

---

## 1. 核心能力清单

### 能力 1：统一调度器（Unified Scheduler）

**解决的问题**：
- 当前 agent-ts 有 3 个任务，v2 有 40+ 任务，互不可见
- 无法表达依赖关系（morning_analysis 必须在 market_data_sync 之后）
- 无并发控制（多个 agent 任务同时跑，抢占 token）
- 无执行历史（上次跑成功了吗？耗时多久？）

**Agent OS 提供**：

#### 1.1 任务注册表
```
所有任务统一注册到 OS：
- Agent 任务（agent-ts 的 3 个）
- v2 后端任务（40+ 个）
- 未来新增任务

数据表：scheduler_tasks
字段：id, name, owner, cron, depends_on, timeout, max_retries, ...
```

#### 1.2 DAG 依赖解析
```
任务依赖声明：
  morning_analysis:
    depends_on: [market_data_sync, pool_scan]
    
调度器保证：
  - 上游失败 → 下游自动取消
  - 循环依赖检测（启动时）
  - 拓扑排序（执行顺序）
```

#### 1.3 并发控制
```
全局限制：最多 5 个任务同时执行
任务级限制：daily_recall_audit 最多 1 个实例（避免重复）
Agent 级限制：memory-agent 的任务最多 2 个并发
```

#### 1.4 执行历史
```
数据表：scheduler_executions
记录：started_at, ended_at, status, duration, token_consumed, error_message

供分析：
  - 哪个任务最容易失败？
  - 哪个任务最耗 token？
  - 历史趋势图（前端展示）
```

#### 1.5 重试策略
```
任务失败 → 自动重试（可配置）
  max_retries: 3
  retry_backoff: 60s（指数退避）
  
超时控制：
  timeout: 1800s（30 分钟）
  超时自动 kill
```

#### 1.6 手动触发
```
CLI 工具：agent-os-ctl task trigger daily_recall_audit
前端按钮：web-frontend 任务管理页的"立即执行"
API：POST /syscall/scheduler/tasks/{id}/trigger
```

---

### 能力 2：资源管理器（Resource Manager）

**解决的问题**：
- Token 消耗无配额（agent 可以无限跑，成本失控）
- 无优先级（交易时段 fin-agent 应该优先，但现在是先到先得）
- 无 Memory 空间配额（agent 可以无限写记忆）

**Agent OS 提供**：

#### 2.1 Token 配额管理
```yaml
# configs/agents.yaml
agents:
  fin-agent:
    token_per_day: 100000    # 每天 10 万 token
  memory-agent:
    token_per_day: 20000     # 每天 2 万 token
  evolution-agent:
    token_per_day: 50000     # 每天 5 万 token
```

**调度器集成**：
```
触发任务前检查：
  if agent.token_used_today >= agent.token_quota:
    return ErrQuotaExceeded  # 任务排队等待明天
    
任务完成后记录：
  agent.token_used_today += execution.token_consumed
```

**配额重置**：
```
每天凌晨 0 点自动重置
  quota_reset_hour: 0  # 可配置
```

#### 2.2 Memory 空间配额
```yaml
agents:
  fin-agent:
    memory_size_mb: 500      # 500 MB 记忆空间
  memory-agent:
    memory_size_mb: 100      # 100 MB
```

**写入时检查**：
```
memory.write() 时检查：
  if agent.memory_used >= agent.memory_quota:
    触发 GC（垃圾回收低价值记忆）
    if still exceeded:
      return ErrQuotaExceeded
```

#### 2.3 优先级调度
```yaml
agents:
  fin-agent:
    priority: 10              # 最高优先级（交易时段）
    priority_schedule:
      "09:00-15:00": 10       # 交易时段
      "15:00-09:00": 5        # 非交易时段
  memory-agent:
    priority: 5
  evolution-agent:
    priority: 7
```

**调度器应用**：
```
任务队列排序：
  按 priority 排序（高优先级先执行）
  
并发限制冲突时：
  低优先级任务排队，等高优先级完成
```

---

### 能力 3：持久化抽象层（Persistence Abstraction）

**解决的问题**：
- 当前 agent-ts 直接调用 v2 的 `/api/memory/search`
- 紧耦合：v2 API 改动 → agent-ts 也要改
- 难以测试：测试时需要启动 v2
- 难以替换：想换向量数据库 → 牵一发动全身

**Agent OS 提供**：

#### 3.1 Memory 子系统
```
Syscall 接口（对 agent 暴露）：
  POST /syscall/memory.write
  POST /syscall/memory.search
  GET  /syscall/memory.query
  POST /syscall/memory.gc

内部实现（对 agent 透明）：
  - PostgreSQL (结构化存储)
  - pgvector (向量检索)
  - BM25 (全文检索)
  - RRF (混合排序)
  
命名空间隔离：
  /memory/fin-agent/decisions/...
  /memory/memory-agent/audit/...
  
配额检查：
  写入时检查 agent 的 memory_quota
```

#### 3.2 Decision 子系统
```
Syscall 接口：
  POST /syscall/decision.record
  GET  /syscall/decision.query
  GET  /syscall/decision.track

内部实现：
  - agent_decisions 表
  - decision_tracking 表
  
权限控制：
  fin-agent: 读写自己的决策
  memory-agent: 只读所有决策（复盘需要）
```

#### 3.3 Evolution 子系统
```
Syscall 接口：
  POST /syscall/evolution.suggest
  GET  /syscall/evolution.leaderboard
  POST /syscall/evolution.execute

内部实现：
  - evolution_suggestions 表
  - evolution_leaderboard 表
```

#### 3.4 Knowledge 子系统
```
Syscall 接口：
  GET  /syscall/knowledge.query
  POST /syscall/knowledge.distill

内部实现：
  - agent_knowledge 表（缠论知识等）
  - 检索引擎
```

**设计原则**：
```
agent 只知道 syscall 接口，不知道底层：
  - 数据库表结构
  - 索引算法
  - 存储引擎
  
好处：
  - 可测试（Mock syscall 接口）
  - 可替换（换 Vector DB 不影响 agent）
  - 可升级（OS 内部优化透明）
```

---

### 能力 4：服务注册表（Service Registry）

**解决的问题**：
- agent-ts 硬编码 `http://127.0.0.1:5001`
- v2 挂了 agent 首次调用才发现（不是启动时）
- web-frontend 也硬编码 5001

**Agent OS 提供**：

#### 4.1 服务注册
```
OS 启动时自检：
  - Memory 子系统: OK
  - Decision 子系统: OK
  - Evolution 子系统: OK
  - Market Driver (gRPC): OK
  - Trading Service (HTTP): UNAVAILABLE  # 报警

暴露注册表 API：
  GET /api/registry/capabilities
  Response:
  {
    "services": {
      "memory": {"status": "healthy", "version": "1.0.0"},
      "decision": {"status": "healthy"},
      "market_driver": {"status": "healthy"},
      "trading": {"status": "unavailable"}
    }
  }
```

#### 4.2 健康检查
```
周期性检查（每 30s）：
  - 调用 Market Driver gRPC: Ping()
  - 查询 PG: SELECT 1
  - 查询 Redis: PING
  
状态更新到注册表
```

#### 4.3 Agent 启动时查询
```typescript
// agent-ts/src/services/startup.ts
async function initializeAgent() {
  const registry = await fetch('http://agent-os:8080/api/registry/capabilities');
  const caps = await registry.json();
  
  if (!caps.services.memory || caps.services.memory.status !== 'healthy') {
    throw new Error('Memory service unavailable, cannot start agent');
  }
  
  // 初始化成功
}
```

#### 4.4 配置文件管理
```yaml
# agent-ts/configs/services.yaml
services:
  agent_os:
    url: "http://localhost:8080"
    timeout: 30000
  
  # 不再硬编码 v2 地址
```

---

### 能力 5：权限管控（Access Control）

**解决的问题**：
- memory-agent 可以调用交易工具（虽然不会用，但有安全风险）
- 无法限制 evolution-agent 修改交易配置
- agent 之间无隔离（可以互相干扰）

**Agent OS 提供**：

#### 5.1 能力授权（Capability-based）
```yaml
# configs/agents.yaml
agents:
  fin-agent:
    capabilities:
      - memory.read
      - memory.write
      - decision.record
      - trading.execute        # 只有 fin 能交易
      - data.market.read
  
  memory-agent:
    capabilities:
      - memory.read
      - memory.write
      - memory.audit
      - decision.read          # 只读（复盘需要）
      # 没有 trading.execute  # 不能交易
  
  evolution-agent:
    capabilities:
      - memory.read
      - evolution.suggest
      - evolution.execute
```

#### 5.2 Syscall 权限检查
```go
// internal/api/middleware/auth.go
func CheckCapability(c *gin.Context) {
    agentID := c.GetHeader("X-Agent-ID")  // 从 header 获取身份
    resource := c.Param("resource")       // memory / decision / trading
    operation := c.Param("operation")     // read / write / execute
    
    capability := fmt.Sprintf("%s.%s", resource, operation)
    
    if !authManager.HasCapability(agentID, capability) {
        c.JSON(403, gin.H{"error": "permission denied", "capability": capability})
        c.Abort()
        return
    }
    
    c.Next()
}
```

#### 5.3 命名空间隔离
```
Memory 命名空间：
  fin-agent 写入：/memory/fin-agent/decisions/2026-08-13/trade-001
  memory-agent 写入：/memory/memory-agent/audit/2026-08-13/recall-audit
  
读取权限：
  fin-agent 可以读自己的 + memory-agent 的（复盘需要）
  memory-agent 只能读自己的
  evolution-agent 可以读所有（分析需要）
```

#### 5.4 审计日志
```
所有 syscall 调用记录审计日志：
  2026-08-13 19:00:00 [INFO] memory-agent called memory.write (success)
  2026-08-13 19:05:00 [WARN] memory-agent called trading.execute (denied)
  
供分析：
  - 哪个 agent 试图越权？
  - 哪些权限配置不合理？
```

---

### 能力 6：Agent 间通信（Inter-Agent Communication）

**解决的问题**：
- 当前 agent 之间无法协作
- 想实现：memory-agent 写入新记忆 → evolution-agent 收到通知，评估是否需要进化
- 当前只能通过轮询（低效）

**Agent OS 提供**：

#### 6.1 Event Bus（事件总线）
```
技术选型：
  - Phase 1: PostgreSQL LISTEN/NOTIFY（零依赖）
  - Phase 2: Redis Pub/Sub（更高性能）

Channel 设计：
  memory.created          # memory-agent 发布
  memory.deleted
  decision.recorded       # fin-agent 发布
  evolution.suggested     # evolution-agent 发布
  trading.executed        # fin-agent 发布
```

#### 6.2 发布（Publish）
```
Syscall 接口：
  POST /syscall/event.publish
  Body: {
    "channel": "memory.created",
    "payload": {
      "memory_id": 123,
      "agent_id": "memory-agent",
      "category": "recall-audit"
    }
  }

内部实现（PG NOTIFY）：
  conn.Exec("NOTIFY memory_created, '...'")
```

#### 6.3 订阅（Subscribe）
```
Syscall 接口：
  WebSocket: ws://agent-os:8080/syscall/event.subscribe?channels=memory.*,trading.*

agent-ts 使用：
  const ws = new WebSocket('ws://agent-os:8080/syscall/event.subscribe?channels=memory.*');
  ws.onmessage = (event) => {
    const {channel, payload} = JSON.parse(event.data);
    if (channel === 'memory.created') {
      // evolution-agent 收到通知，评估是否需要进化
      handleNewMemory(payload);
    }
  };
```

#### 6.4 使用场景
```
场景 1：进化建议触发
  1. memory-agent 写入新记忆 → 发布 memory.created
  2. evolution-agent 订阅 memory.created
  3. 收到通知后评估：该记忆是否暴露新问题？
  4. 如果是 → 生成进化建议
  
场景 2：交易完成后复盘
  1. fin-agent 完成交易 → 发布 trading.executed
  2. memory-agent 订阅 trading.executed
  3. 收到通知后自动写复盘记忆
  
场景 3：实时协作
  1. 人类通过 web-frontend 手动触发任务
  2. web-frontend 发布 task.manual_trigger
  3. agent-ts 收到通知，创建会话执行
```

---

### 能力 7：设备驱动层（Device Drivers）

**解决的问题**：
- 金融数据源（AKShare、Tushare）只有 Python SDK
- 如果全部用 Go 重写适配器 → 工作量大、容易出 bug
- 需要保留 Python 生态，但又不能让 OS 内核依赖 Python

**Agent OS 提供**：

#### 7.1 驱动架构
```
┌─────────────────────────────────────┐
│       Agent OS Kernel (Go)          │
│  ┌──────────────────────────────┐   │
│  │  Syscall: data.market.quote  │   │
│  └──────────┬───────────────────┘   │
│             │ gRPC Call              │
└─────────────┼──────────────────────┘
              │
┌─────────────▼──────────────────────┐
│  Market Driver (Python Process)    │
│  ┌──────────────────────────────┐  │
│  │  gRPC Server                 │  │
│  │  ├─ GetQuote()               │  │
│  │  ├─ GetKline()               │  │
│  │  └─ GetFinancials()          │  │
│  └──────────┬───────────────────┘  │
│             │                       │
│  ┌──────────▼───────────────────┐  │
│  │ AKShare / Tushare Adapters   │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

#### 7.2 驱动列表
```
Market Driver:
  - 实时行情（GetQuote）
  - K 线数据（GetKline）
  - 财报数据（GetFinancials）
  - 分红数据（GetDividends）
  - 市场情绪（GetSentiment）
  
Signal Driver（可选，Phase 2）:
  - 实时信号监控
  - 信号流式推送
  
Trading Driver（可选，Phase 2）:
  - 虚拟盘下单（Mock Broker）
  - 实盘接口（富途 API）
```

#### 7.3 驱动管理
```
OS 启动时自动启动驱动：
  python3 drivers/market_driver/main.py &
  
驱动崩溃自动重启：
  监控进程退出 → 等待 5s → 重启
  
健康检查：
  每 30s 调用 gRPC Ping()
  连续 3 次失败 → 标记 UNAVAILABLE → 报警
```

#### 7.4 Agent 使用（透明）
```
agent 只需调用 syscall：
  POST /syscall/data.market.quote
  Body: {"symbol": "600519.SH"}

OS 内核处理：
  1. 权限检查（agent 有 data.market.read 能力吗？）
  2. 调用 Market Driver gRPC
  3. 重试（如果失败）
  4. 返回结果给 agent
  
agent 不知道：
  - 驱动是 Python 还是 Go
  - gRPC 还是 HTTP
  - 数据源是 AKShare 还是 Tushare
```

---

## 2. 能力优先级矩阵

| 能力 | 优先级 | 理由 | MVP 包含 |
|---|---|---|---|
| **统一调度器** | P0 | 最痛点，无法统一管理任务 | ✅ Yes |
| **资源管理器** | P0 | 成本失控、无法公平调度 | ✅ Yes |
| **持久化抽象** | P0 | 解耦、可测试、可替换 | ✅ Yes（Memory + Decision） |
| **服务注册表** | P1 | 提升可靠性，启动时 Fail Fast | ✅ Yes |
| **权限管控** | P1 | 安全风险，但暂时可控 | ⏸️ Phase 2 |
| **Agent 间通信** | P2 | 有价值，但非紧急 | ⏸️ Phase 2 |
| **设备驱动层** | P0 | 金融数据必须有 | ✅ Yes（Market Driver） |

---

## 3. 技术栈最终确认

### 3.1 OS 内核层
```
语言：Go 1.21+
框架：Gin (HTTP) / gRPC (驱动通信)
数据库：PostgreSQL 15+ / Redis 7+
日志：Zap (结构化日志)
监控：Prometheus + Grafana
配置：Viper (YAML 配置)
测试：go test + testify
```

### 3.2 设备驱动层
```
语言：Python 3.11+
框架：gRPC (通信) / FastAPI (可选，未来 HTTP 驱动)
数据源：AKShare / Tushare / yfinance
部署：独立进程（由 OS 管理生命周期）
```

### 3.3 CLI 工具
```
语言：Go
框架：Cobra (命令行)
发布：单一二进制（agent-os-ctl）
```

---

## 4. 系统架构图（最终版）

```
┌────────────────────────────────────────────────────────────────┐
│                       Application Layer                         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  fin-agent   │  │memory-agent  │  │evolution-agt │         │
│  │  (agent-ts)  │  │  (agent-ts)  │  │  (agent-ts)  │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                      │
│                   Syscall API (HTTP)                            │
└───────────────────────────┼──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                       Agent OS (Go Kernel)                        │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Core Runtime Services                     │  │
│  │                                                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │  Scheduler  │  │  Resource   │  │  Service    │       │  │
│  │  │  (DAG、优先级│  │  Manager    │  │  Registry   │       │  │
│  │  │   并发控制)  │  │  (配额管理) │  │  (健康检查) │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  │                                                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │  Memory     │  │  Decision   │  │  Evolution  │       │  │
│  │  │  System     │  │  System     │  │  System     │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  │                                                             │  │
│  │  ┌─────────────┐  ┌─────────────┐                         │  │
│  │  │  Knowledge  │  │  Event Bus  │  (Phase 2)             │  │
│  │  │  System     │  │  (IPC)      │                         │  │
│  │  └─────────────┘  └─────────────┘                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               Device Drivers (Python gRPC)                 │  │
│  │                                                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│  │  │Market Driver │  │Signal Driver │  │Trading Driver│   │  │
│  │  │(AKShare/     │  │(Realtime     │  │(Mock/        │   │  │
│  │  │ Tushare)     │  │ Signals)     │  │ Futu API)    │   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Storage & Infrastructure                  │  │
│  │  PostgreSQL │ Redis │ Vector Index │ ...                 │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                    ▼
┌──────────────┐  ┌──────────────┐    ┌──────────────┐
│Trading       │  │Strategy      │    │web-frontend  │
│Service       │  │Service       │    │(Vue3)        │
│(quantsys-v2) │  │(quantsys-v2) │    │              │
│独立或保留    │  │独立或保留    │    │              │
└──────────────┘  └──────────────┘    └──────────────┘
```

---

## 5. MVP 范围定义

### MVP 目标
证明 Agent OS 的核心价值：**统一调度 + 资源管控 + 持久化抽象**

### MVP 包含（3-4 周）

#### Week 1: 脚手架 + 调度器
- [x] Go 项目脚手架（Clean Architecture）
- [x] PostgreSQL Schema（scheduler_tasks, scheduler_executions）
- [x] Scheduler 核心（注册、触发、DAG 依赖）
- [x] 执行引擎（超时、重试、并发控制）
- [x] 单元测试

#### Week 2: 资源管理 + 持久化
- [x] Resource Manager（Token 配额、Memory 配额、优先级）
- [x] Memory System（write、search、namespace）
- [x] Decision System（record、query）
- [x] 数据库表迁移（从 v2 迁移 agent_memory、agent_decisions）
- [x] 集成测试

#### Week 3: API + 驱动
- [x] Syscall API（Gin 路由 + Handlers）
- [x] Service Registry（capabilities、health）
- [x] Market Driver（Python gRPC server + AKShare 适配）
- [x] gRPC 通信测试

#### Week 4: CLI + 端到端
- [x] agent-os-ctl CLI 工具（task、quota 命令）
- [x] agent-ts 切换到 Agent OS（启动时注册任务）
- [x] 端到端测试（agent 触发任务 → OS 调度 → 执行 → 记录历史）
- [x] 部署脚本（launchd / systemd）

### MVP 不包含（Phase 2）
- ⏸️ 权限管控（Access Control）
- ⏸️ Event Bus（Agent 间通信）
- ⏸️ Evolution/Knowledge System（先迁移 Memory/Decision）
- ⏸️ Trading Driver（先用 Market Driver 验证架构）
- ⏸️ web-frontend 任务管理页（先用 CLI）

---

## 6. 验收标准

### 功能验收
- [ ] `agent-os-ctl task list` 能看到 agent 任务 + v2 任务（40+ 个）
- [ ] 手动触发 `daily_recall_audit` → 执行成功 → 历史记录可查
- [ ] Token 配额生效：memory-agent 超配额 → 任务排队
- [ ] DAG 依赖生效：morning_analysis 在 market_data_sync 之后执行
- [ ] agent-ts 调用 `memory.write` → 写入 Agent OS DB
- [ ] agent-ts 调用 `data.market.quote` → Market Driver 返回行情

### 性能验收
- [ ] 任务触发延迟 < 100ms（从 API 调用到调度器响应）
- [ ] Memory 写入延迟 < 200ms（包含索引更新）
- [ ] Market Driver 行情查询 < 500ms（含 gRPC 往返）

### 可靠性验收
- [ ] Market Driver 崩溃 → 5s 后自动重启
- [ ] PostgreSQL 连接失败 → 重试 3 次 → 报错
- [ ] 任务超时 → 自动 kill → 记录 timeout 状态

---

## 7. 迁移计划

### Phase 0: Agent OS MVP（Week 1-4，上述）

### Phase 1: agent-ts 全量切换（Week 5-6）
- [ ] agent-ts 的 3 个任务注册到 Agent OS
- [ ] agent-ts 的 Memory 调用切换到 OS syscall
- [ ] agent-ts 的 Decision 调用切换到 OS syscall
- [ ] 删除 agent-ts 本地 Cron（改用 OS 调度）
- [ ] 验收：agent-ts 完全依赖 Agent OS

### Phase 2: v2 后端任务迁移（Week 7-8）
- [ ] v2 的 40+ 任务定义迁移到 Agent OS
- [ ] v2 的 scheduler_tasks.py 改为调用 OS API
- [ ] 验收：所有任务在 OS 统一管理

### Phase 3: 权限 + Event Bus（Week 9-10）
- [ ] 权限管控实现
- [ ] Event Bus（PG NOTIFY）
- [ ] agent 间通信示例

### Phase 4: 生产优化（Week 11-12）
- [ ] 性能测试 + 调优
- [ ] 监控告警完善
- [ ] 文档完善

---

## 8. 风险与缓解

### 风险 1：Go 技能曲线
- **风险**：团队对 Go 不熟悉，开发慢
- **缓解**：MVP 代码量小（<5000 行），边学边做；有 AI 辅助

### 风险 2：数据迁移出错
- **风险**：从 v2 迁移表时数据丢失
- **缓解**：双写期（OS 和 v2 同时写）；充分测试；可回滚

### 风险 3：gRPC 通信不稳定
- **风险**：Python Driver 崩溃影响 OS
- **缓解**：自动重启；健康检查；降级方案（直接调 v2 API）

### 风险 4：性能不达预期
- **风险**：Go 调度器没有比 Python 快
- **缓解**：性能测试先行；Rust 重写热点作为备选方案

---

## 9. 你的决策点

**现在需要你确认**：

1. **这个能力清单满意吗？** 有缺失或冗余的能力吗？
   
2. **MVP 范围合理吗？** 3-4 周能完成吗？还是太激进？

3. **技术栈确认**：Go + Python 驱动 + PostgreSQL/Redis，OK 吗？

4. **迁移策略**：Phase 0-4 的节奏，认可吗？

5. **什么时候开工**：
   - 选项 A：现在立即开工（我建 Go 脚手架）
   - 选项 B：等明晚 `daily_recall_audit` 首次触发观察完
   - 选项 C：还有其他考虑

**等你拍板！**
