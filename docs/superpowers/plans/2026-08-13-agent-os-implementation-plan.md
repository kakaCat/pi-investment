# Agent OS 实施计划总表

> **创建时间**: 2026-08-13  
> **目标**: 分 6 个批次完成 Agent OS，每批次 1-2 周，可独立验收  
> **原则**: 增量交付、最小可用、风险可控

---

## 0. 批次总览

| 批次 | 名称 | 核心目标 | 工期 | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| **Batch 0** | 项目脚手架 | Go 项目结构 + CLI 框架 | 2-3 天 | 无 | CLI 能响应 `agent-os version` |
| **Batch 1** | 调度器 MVP | 统一任务调度 + 执行历史 | 1 周 | Batch 0 | agent 任务和 v2 任务统一管理 |
| **Batch 2** | 资源管理 + Memory | 配额管理 + Memory 子系统 | 1 周 | Batch 1 | Token 配额生效，Memory 读写 |
| **Batch 3** | CLI 集成 + agent 切换 | agent-ts 切换到 OS | 3-5 天 | Batch 2 | agent-ts 完全依赖 OS |
| **Batch 4** | Driver 层 + 数据服务 | Market Driver + 通知系统 | 1 周 | Batch 3 | 行情查询、飞书通知 |
| **Batch 5** | 权限 + Event Bus | 权限管控 + Agent 间通信 | 1 周 | Batch 4 | memory-agent 不能调交易 |
| **Batch 6** | 生产优化 | 性能测试 + 监控 + 文档 | 3-5 天 | Batch 5 | 生产环境稳定运行 |

**总工期**：5-6 周（35-42 天）

---

## Batch 0: 项目脚手架（2-3 天）

### 目标
建立 Go 项目基础结构，CLI 能运行基本命令

### 任务清单

#### Day 1: 项目初始化
- [ ] 创建项目目录：`agent-os/`
- [ ] 初始化 Go Module：`go mod init github.com/pi-investment/agent-os`
- [ ] 安装核心依赖：
  ```
  github.com/spf13/cobra      # CLI 框架
  github.com/spf13/viper      # 配置管理
  github.com/gin-gonic/gin    # HTTP 服务器
  go.uber.org/zap             # 日志
  github.com/jackc/pgx/v5     # PostgreSQL
  ```
- [ ] 设置项目结构（Clean Architecture）：
  ```
  agent-os/
  ├── cmd/
  │   └── agent-os/
  │       └── main.go          # 入口
  ├── internal/
  │   ├── cli/                 # CLI 命令
  │   ├── kernel/              # 内核服务
  │   ├── api/                 # HTTP API
  │   └── storage/             # 存储层
  ├── pkg/
  │   ├── types/               # 公共类型
  │   └── client/              # Go Client SDK
  ├── configs/
  │   └── agent-os.yaml        # 配置文件
  ├── scripts/
  │   ├── build.sh
  │   └── deploy.sh
  ├── go.mod
  ├── go.sum
  └── README.md
  ```

#### Day 2: CLI 框架搭建
- [ ] 实现 CLI 入口（`cmd/agent-os/main.go`）
- [ ] 实现基础命令：
  ```
  agent-os version             # 显示版本
  agent-os help                # 帮助信息
  agent-os daemon start        # 启动 daemon（空实现）
  agent-os daemon stop         # 停止 daemon（空实现）
  ```
- [ ] 配置文件加载（Viper）
- [ ] 日志系统（Zap）

#### Day 3: 数据库 Schema + 测试
- [ ] PostgreSQL Schema 设计：
  ```sql
  -- scheduler_tasks 表
  -- scheduler_executions 表
  -- quota_usage 表
  ```
- [ ] 数据库连接测试
- [ ] 单元测试框架搭建（testify）
- [ ] 编写 `scripts/build.sh` 构建脚本

### 验收标准
- [ ] `go build` 编译成功，生成 `agent-os` 二进制
- [ ] `agent-os version` 输出版本信息
- [ ] `agent-os help` 显示命令列表
- [ ] 配置文件能正确加载
- [ ] 数据库连接测试通过

### 产出物
- `agent-os` 二进制（v0.1.0）
- 项目脚手架代码
- 数据库 Schema SQL 文件

---

## Batch 1: 调度器 MVP（1 周，5-7 天）

### 目标
实现统一调度器，agent 任务和 v2 任务能统一管理

### 任务清单

#### Day 1-2: 核心数据结构 + Repository
- [ ] 定义核心类型（`pkg/types/task.go`）：
  ```go
  type TaskDefinition struct {...}
  type TaskExecution struct {...}
  ```
- [ ] 实现 TaskRepository（CRUD）
- [ ] 实现 ExecutionRepository
- [ ] 单元测试

#### Day 3-4: Scheduler 核心逻辑
- [ ] 实现 Scheduler 核心：
  ```go
  func (s *Scheduler) RegisterTask(task *TaskDefinition) error
  func (s *Scheduler) TriggerTask(taskID uint64) error
  func (s *Scheduler) Start() error  // Cron 启动
  ```
- [ ] Cron 触发器集成（robfig/cron）
- [ ] 执行引擎（Executor）：
  - 超时控制
  - 重试逻辑
  - 并发控制
- [ ] 单元测试 + 集成测试

#### Day 5: DAG 依赖解析
- [ ] 实现 DAG 结构（`internal/kernel/scheduler/dag.go`）
- [ ] 循环依赖检测
- [ ] 拓扑排序
- [ ] 依赖检查逻辑
- [ ] 单元测试

#### Day 6: CLI 命令实现
- [ ] 实现 Scheduler CLI：
  ```bash
  agent-os scheduler register --name ... --cron ...
  agent-os scheduler list
  agent-os scheduler trigger --task-id 5
  agent-os scheduler executions --task-id 5
  ```
- [ ] Unix Socket 通信（CLI ↔ Daemon）
- [ ] JSON 输出格式

#### Day 7: HTTP API + 端到端测试
- [ ] 实现 HTTP API（Gin 路由）：
  ```
  POST /api/scheduler/tasks
  GET  /api/scheduler/tasks
  POST /api/scheduler/tasks/:id/trigger
  GET  /api/scheduler/executions
  ```
- [ ] 端到端测试：
  - 注册任务 → Cron 触发 → 记录历史
  - 手动触发 → 执行成功
  - 依赖检查生效

### 验收标准
- [ ] 通过 CLI 注册 3 个 agent 任务（daily_recall_audit, morning_analysis, weekly_evolution）
- [ ] 通过 CLI 查看任务列表，能看到所有任务
- [ ] 手动触发任务，执行成功，历史记录可查
- [ ] DAG 依赖生效：上游失败 → 下游自动取消
- [ ] 并发控制生效：最多 5 个任务同时执行
- [ ] HTTP API 正常工作（web 能调用）

### 产出物
- Scheduler 模块代码（`internal/kernel/scheduler/`）
- CLI 命令（`scheduler` 子命令）
- HTTP API（`/api/scheduler/*`）
- 单元测试 + 集成测试
- 数据表数据（注册的任务）

---

## Batch 2: 资源管理 + Memory 子系统（1 周，5-7 天）

### 目标
实现 Token 配额管理和 Memory 子系统

### 任务清单

#### Day 1-2: Resource Manager
- [ ] 实现配额管理（`internal/kernel/resource/quota.go`）：
  ```go
  func (m *Manager) CheckQuota(agentID string) bool
  func (m *Manager) ConsumeToken(agentID string, tokens int)
  ```
- [ ] 配额配置加载（`configs/agents.yaml`）
- [ ] 命名空间隔离（`namespace.go`）
- [ ] CLI 命令：
  ```bash
  agent-os resource quota --agent fin-agent
  ```
- [ ] 单元测试

#### Day 3-4: Memory System
- [ ] 数据库表迁移：
  ```sql
  -- 从 quantsys-v2 迁移 agent_memory 表
  -- pg_dump + 改连接字符串
  ```
- [ ] 实现 Memory Store（`internal/kernel/memory/store.go`）：
  ```go
  func (s *Store) Write(content, category, agentID string) (memoryID uint64, error)
  func (s *Store) Search(query string, topK int) ([]*Memory, error)
  ```
- [ ] BM25 全文检索（使用 PG tsvector）
- [ ] 向量检索（pgvector 扩展）
- [ ] CLI 命令：
  ```bash
  agent-os memory write --content "..." --category decision
  agent-os memory search --query "止盈"
  ```
- [ ] 单元测试

#### Day 5: Decision 子系统
- [ ] 数据表迁移（agent_decisions, decision_tracking）
- [ ] 实现 Decision System（`internal/kernel/decision/`）
- [ ] CLI 命令：
  ```bash
  agent-os decision record --action buy --targets '["600519.SH"]'
  agent-os decision query --action buy
  ```
- [ ] 单元测试

#### Day 6: Scheduler 集成配额检查
- [ ] 在 Scheduler 触发任务前检查配额：
  ```go
  if !resourceMgr.CheckQuota(task.Owner) {
    return ErrQuotaExceeded
  }
  ```
- [ ] 任务完成后消费配额：
  ```go
  resourceMgr.ConsumeToken(task.Owner, exec.TokenConsumed)
  ```
- [ ] 集成测试

#### Day 7: HTTP API + 验收
- [ ] Memory HTTP API：
  ```
  POST /api/memory/write
  POST /api/memory/search
  ```
- [ ] Decision HTTP API
- [ ] 端到端测试

### 验收标准
- [ ] 配额生效：fin-agent 配额用完后任务排队
- [ ] Memory 写入成功，能通过 CLI 搜索到
- [ ] Decision 记录成功，能查询历史
- [ ] Scheduler 触发任务时会检查配额
- [ ] HTTP API 正常（web 能调用）

### 产出物
- Resource Manager 代码
- Memory System 代码
- Decision System 代码
- 数据表迁移脚本
- CLI 命令（`memory`, `decision`, `resource`）

---

## Batch 3: CLI 集成 + agent-ts 切换（3-5 天）

### 目标
agent-ts 完全切换到 Agent OS

### 任务清单

#### Day 1: agent-ts CLI 执行器
- [ ] 实现 `agent-ts/src/utils/agent-os-cli.ts`：
  ```typescript
  export async function execAgentOS(args: string[]): Promise<AgentOSResult>
  ```
- [ ] 错误处理封装
- [ ] 单元测试（Mock execSync）

#### Day 2: 工具迁移（Memory + Decision）
- [ ] 改写 `memory_write` 工具：
  ```typescript
  execute: async (params) => {
    return await execAgentOS(['memory', 'write', ...]);
  }
  ```
- [ ] 改写 `memory_search` 工具
- [ ] 改写 `decision_record` 工具
- [ ] 改写 `recall_audit` 工具
- [ ] 单元测试

#### Day 3: 任务注册迁移
- [ ] agent-ts 启动时注册任务到 OS：
  ```typescript
  // src/services/scheduler/register-to-os.ts
  await execAgentOS(['scheduler', 'register', '--name', 'daily_recall_audit', ...]);
  ```
- [ ] 删除 agent-ts 本地 Cron 代码
- [ ] OS 触发任务时调用 agent-ts Webhook：
  ```
  POST http://localhost:3000/api/agent/trigger
  Body: {execution_id, agent_kind, prompt}
  ```
- [ ] agent-ts 实现 Webhook 接口

#### Day 4-5: 端到端测试 + 修 bug
- [ ] 测试完整流程：
  1. agent-ts 启动 → 注册任务到 OS
  2. OS Cron 8:30 触发 morning_analysis
  3. OS 调用 agent-ts Webhook
  4. fin-agent 推理 → 调用工具 → execAgentOS
  5. 完成后回调 OS
  6. OS 更新配额
- [ ] 修复发现的 bug
- [ ] 性能测试（CLI 调用延迟 < 100ms）

### 验收标准
- [ ] agent-ts 启动后能在 OS 看到 3 个任务
- [ ] `agent-os scheduler list` 显示 agent 任务 + v2 任务（40+ 个）
- [ ] OS 触发任务 → agent-ts 执行成功
- [ ] agent 调用工具 → OS 处理 → 返回结果
- [ ] agent-ts 不再有本地 Cron 代码
- [ ] agent-ts 不再硬编码 `http://127.0.0.1:5001`

### 产出物
- agent-ts CLI 集成代码
- 迁移后的工具定义
- Webhook 接口
- 端到端测试用例

---

## Batch 4: Driver 层 + 数据服务（1 周，5-7 天）

### 目标
实现 Market Driver 和通知系统

### 任务清单

#### Day 1-2: Market Driver (Python CLI)
- [ ] 创建 `drivers/market_driver/` 目录
- [ ] 实现 Market Driver CLI：
  ```bash
  market-driver quote --symbol 600519.SH
  market-driver kline --symbol 600519.SH --period 1d
  ```
- [ ] AKShare 适配器
- [ ] Redis 缓存层
- [ ] 单元测试（Python pytest）

#### Day 3: OS 调用 Market Driver
- [ ] OS 实现 Data CLI 命令（代理到 Driver）：
  ```bash
  agent-os data quote --symbol 600519.SH
  # 内部调用 market-driver CLI
  ```
- [ ] 实现 MarketCLIDriver（Go）：
  ```go
  func (d *MarketCLIDriver) GetQuote(symbol string) (*Quote, error) {
    cmd := exec.Command("market-driver", "quote", "--symbol", symbol)
    output, _ := cmd.Output()
    return parseJSON(output)
  }
  ```
- [ ] 失败重试逻辑
- [ ] 集成测试

#### Day 4-5: 通知系统
- [ ] 实现 Notification Manager（`internal/kernel/notification/`）
- [ ] 实现 Feishu Driver（Python CLI）：
  ```bash
  feishu-driver send --title "任务完成" --message "..." --priority normal
  ```
- [ ] OS Notify 命令：
  ```bash
  agent-os notify send --user yunpeng --title "..." --message "..."
  ```
- [ ] 在 Scheduler 中集成通知：
  ```go
  // 任务完成后发送通知
  notificationMgr.Notify(userID, "task.completed", payload, PriorityNormal)
  ```
- [ ] 测试飞书通知

#### Day 6-7: HTTP API + 验收
- [ ] Data HTTP API：
  ```
  GET /api/data/quote?symbol=600519.SH
  GET /api/data/kline?symbol=...
  ```
- [ ] Notification HTTP API：
  ```
  POST /api/notification/send
  ```
- [ ] agent-ts 迁移数据工具（如果有）
- [ ] 端到端测试

### 验收标准
- [ ] `agent-os data quote --symbol 600519.SH` 返回实时行情
- [ ] agent 调用数据工具成功
- [ ] 任务完成后飞书收到通知
- [ ] 通知消息卡片格式正确
- [ ] HTTP API 正常（web 能调用）

### 产出物
- Market Driver 代码（Python）
- Feishu Driver 代码（Python）
- OS Data 命令代码
- OS Notification Manager 代码

---

## Batch 5: 权限管控 + Event Bus（1 周，5-7 天）

### 目标
实现权限系统和 Agent 间通信

### 任务清单

#### Day 1-2: 权限系统
- [ ] 定义权限配置（`configs/agents.yaml`）：
  ```yaml
  agents:
    fin-agent:
      capabilities: [memory.read, memory.write, trading.execute]
    memory-agent:
      capabilities: [memory.read, memory.write, memory.audit]
  ```
- [ ] 实现权限检查（`internal/kernel/security/`）：
  ```go
  func (m *AuthManager) CheckCapability(agentID, capability string) bool
  ```
- [ ] 在 CLI/API 入口处检查权限
- [ ] 单元测试

#### Day 3-4: Event Bus
- [ ] 实现 Event Bus（PostgreSQL NOTIFY）：
  ```go
  func (e *EventBus) Publish(channel string, payload interface{}) error
  func (e *EventBus) Subscribe(channel string) (<-chan Event, error)
  ```
- [ ] WebSocket 订阅接口（HTTP）：
  ```
  ws://localhost:8080/api/events/subscribe?channels=task.*
  ```
- [ ] 在 Scheduler 中发布事件：
  ```go
  eventBus.Publish("task.completed", map[string]interface{}{
    "task_id": taskID,
    "status": "success",
  })
  ```
- [ ] agent-ts 订阅事件示例（可选）

#### Day 5: Evolution 子系统
- [ ] 数据表迁移（evolution_leaderboard, evolution_suggestions）
- [ ] 实现 Evolution System
- [ ] CLI 命令：
  ```bash
  agent-os evolution suggest --type tool_add --details '...'
  agent-os evolution leaderboard
  ```

#### Day 6-7: 集成测试 + 验收
- [ ] 测试权限：memory-agent 调用 trading 命令 → 403 拒绝
- [ ] 测试 Event Bus：任务完成 → web 收到 WebSocket 通知
- [ ] 测试 Evolution 功能
- [ ] 全链路测试

### 验收标准
- [ ] memory-agent 无法调用 trading 命令（权限拒绝）
- [ ] fin-agent 可以调用所有命令
- [ ] 任务完成时 web 收到实时通知
- [ ] Evolution 建议能记录和查询
- [ ] 所有核心功能正常

### 产出物
- 权限系统代码
- Event Bus 代码
- Evolution System 代码
- WebSocket 订阅接口

---

## Batch 6: 生产优化（3-5 天）

### 目标
性能优化、监控、文档，达到生产级标准

### 任务清单

#### Day 1: 性能测试 + 优化
- [ ] 性能基准测试：
  - CLI 调用延迟（目标 < 100ms）
  - Memory 写入延迟（目标 < 200ms）
  - Scheduler 触发延迟（目标 < 100ms）
- [ ] 性能优化（如果不达标）：
  - 数据库索引优化
  - 连接池配置
  - 缓存策略
- [ ] 压力测试（1000 次并发调用）

#### Day 2: 监控 + 日志
- [ ] Prometheus 指标暴露：
  ```
  GET /metrics
  ```
- [ ] 关键指标：
  - 任务执行耗时
  - Token 消耗统计
  - API 响应时间
  - 错误率
- [ ] 结构化日志完善
- [ ] 日志轮转配置

#### Day 3: 部署脚本 + 文档
- [ ] 部署脚本：
  ```bash
  scripts/deploy.sh           # 部署到生产
  scripts/start-daemon.sh     # 启动 daemon
  scripts/stop-daemon.sh      # 停止 daemon
  ```
- [ ] systemd/launchd 配置文件
- [ ] 健康检查脚本
- [ ] 文档：
  - README.md（快速开始）
  - ARCHITECTURE.md（架构文档）
  - API.md（API 文档）
  - CLI.md（CLI 使用手册）

#### Day 4-5: 全面测试 + 修 bug
- [ ] 回归测试（所有功能）
- [ ] 边界条件测试
- [ ] 错误处理测试
- [ ] 修复所有已知 bug
- [ ] 生产环境试运行 1 天

### 验收标准
- [ ] 性能达标（所有延迟 < 目标值）
- [ ] Prometheus 监控正常
- [ ] 日志清晰完整
- [ ] 部署脚本正常工作
- [ ] 文档完善
- [ ] 生产环境稳定运行 24 小时无故障

### 产出物
- 性能测试报告
- Prometheus 监控配置
- 部署脚本
- 完整文档
- v1.0.0 发布版本

---

## 风险与缓解

### 风险 1：Go 技能不足导致开发慢
**缓解**：
- Batch 0-1 边学边做，AI 辅助
- 参考成熟项目（K8s、etcd）
- 代码审查（我可以帮你审查）

### 风险 2：数据迁移出错
**缓解**：
- Batch 2 充分测试
- 双写期（OS 和 v2 同时写）
- 备份数据库

### 风险 3：agent-ts 切换失败
**缓解**：
- Batch 3 小步迁移（先一个工具，再全部）
- 保留 v2 作为 fallback
- 灰度切换

### 风险 4：性能不达标
**缓解**：
- Batch 6 性能测试在前
- Rust 重写热点作为 Plan B
- 降级策略（CLI → HTTP）

---

## 并行工作建议

### 可并行的批次
- Batch 1（调度器）和 Batch 2（资源管理）**部分可并行**（前 3 天独立）
- Batch 4（Driver）和 Batch 5（权限）**完全可并行**（不同模块）

### 不可并行的批次
- Batch 3 必须等 Batch 1+2 完成（agent 切换需要 OS 核心功能）
- Batch 6 必须等所有功能完成（生产优化是最后一步）

---

## 时间线（理想 vs 保守）

### 理想情况（5 周）
```
Week 1: Batch 0 (3天) + Batch 1 开始 (4天)
Week 2: Batch 1 完成 + Batch 2 (7天)
Week 3: Batch 3 (5天) + Batch 4 开始 (2天)
Week 4: Batch 4 完成 + Batch 5 (7天)
Week 5: Batch 6 (5天)
```

### 保守情况（7 周）
```
Week 1: Batch 0 (5天)
Week 2: Batch 1 (7天)
Week 3: Batch 2 (7天)
Week 4: Batch 3 (7天)
Week 5: Batch 4 (7天)
Week 6: Batch 5 (7天)
Week 7: Batch 6 (7天)
```

**建议**：按保守估算，留 buffer

---

## 下一步

1. **你确认计划吗？** 有需要调整的批次或时间吗？

2. **什么时候开始？**
   - 选项 A：现在立即开工 Batch 0
   - 选项 B：等明晚 `daily_recall_audit` 首次触发观察完
   - 选项 C：等周末（有更多时间）

3. **谁来做？**
   - 你自己写代码？
   - 我帮你生成代码？
   - 还是结对编程（你定方向，我写代码）？

**准备好就告诉我！**
