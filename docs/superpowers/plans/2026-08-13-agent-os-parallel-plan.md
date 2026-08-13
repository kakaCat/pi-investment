# Agent OS 并行执行计划

> **创建时间**: 2026-08-13  
> **执行模式**: 多 Agent 并行 + 人类审核  
> **目标**: 最大化并行度，最短时间完成 Agent OS

---

## 1. 并行执行策略

### 核心理念
- **多个 Agent 同时工作**：不同模块独立开发，互不阻塞
- **人类做审核员**：你审核代码、测试、拍板决策
- **增量交付**：每个模块完成立即提交，不等全部完成

### 你的角色（审核员）
1. **审核代码**：Agent 完成后，你 Review 代码质量
2. **运行测试**：执行 `go test`、`go build`、手动测试
3. **决策拍板**：技术选型、架构调整、优先级变更
4. **集成验证**：多个模块完成后，验证集成效果

### Agent 的角色（执行者）
1. **写代码**：按照规格文档实现功能
2. **写测试**：单元测试、集成测试
3. **写文档**：代码注释、README
4. **提交代码**：完成后提交到 worktree

---

## 2. 可并行的工作包（Work Package）

### 依赖关系图

```
                    ┌─────────────┐
                    │  Batch 0    │
                    │ 项目脚手架   │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐     ┌──────────┐    ┌──────────┐
    │  WP-1    │     │  WP-2    │    │  WP-3    │
    │ Scheduler│     │ Resource │    │  Memory  │
    │  Core    │     │ Manager  │    │  System  │
    └────┬─────┘     └────┬─────┘    └────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                          ▼
                    ┌──────────┐
                    │  WP-4    │
                    │CLI 集成  │
                    │agent切换 │
                    └────┬─────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐  ┌──────────┐
    │  WP-5    │   │  WP-6    │  │  WP-7    │
    │ Market   │   │  Feishu  │  │ Decision │
    │ Driver   │   │  Driver  │  │ System   │
    └────┬─────┘   └────┬─────┘  └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
                        ▼
                  ┌──────────┐
                  │  WP-8    │
                  │  权限 +  │
                  │Event Bus │
                  └────┬─────┘
                       │
                       ▼
                  ┌──────────┐
                  │  WP-9    │
                  │生产优化  │
                  └──────────┘
```

### 并行执行矩阵

| 阶段 | 可并行工作包 | 预计时间 | 依赖 |
|---|---|---|---|
| **Stage 0** | WP-0: 项目脚手架 | 1 天 | 无 |
| **Stage 1** | WP-1: Scheduler Core<br>WP-2: Resource Manager<br>WP-3: Memory System | 2-3 天<br>(并行) | Batch 0 |
| **Stage 2** | WP-4: CLI 集成 + agent 切换 | 2 天 | Stage 1 全部完成 |
| **Stage 3** | WP-5: Market Driver<br>WP-6: Feishu Driver<br>WP-7: Decision System | 2 天<br>(并行) | WP-4 完成 |
| **Stage 4** | WP-8: 权限 + Event Bus | 2 天 | Stage 3 全部完成 |
| **Stage 5** | WP-9: 生产优化 | 1 天 | Stage 4 完成 |

**理论最短工期**：1 + 3 + 2 + 2 + 2 + 1 = **11 天**

---

## 3. 详细工作包定义

### WP-0: 项目脚手架（1 天）

**目标**：建立 Go 项目基础，能编译运行

**任务**：
- [ ] 创建目录结构（Clean Architecture）
- [ ] 初始化 go.mod，安装依赖
- [ ] 实现 CLI 框架（Cobra）
- [ ] 实现配置加载（Viper）
- [ ] 实现日志系统（Zap）
- [ ] 数据库 Schema SQL 文件
- [ ] 编写 `scripts/build.sh`

**产出物**：
- `agent-os` 可编译的二进制
- `agent-os version` 命令能运行
- 项目结构完整

**验收标准**：
```bash
go build -o agent-os ./cmd/agent-os
./agent-os version  # 输出版本信息
./agent-os help     # 显示命令列表
```

**Agent 分配**：1 个 Agent，专注写基础框架

---

### WP-1: Scheduler Core（2-3 天，可与 WP-2/WP-3 并行）

**目标**：实现调度器核心逻辑

**任务**：
- [ ] 定义核心类型（TaskDefinition, TaskExecution）
- [ ] 实现 TaskRepository（CRUD）
- [ ] 实现 ExecutionRepository
- [ ] 实现 Scheduler 核心逻辑：
  - RegisterTask
  - TriggerTask
  - Cron 触发器集成
- [ ] 实现 Executor（超时、重试、并发控制）
- [ ] 实现 DAG 依赖解析
- [ ] CLI 命令：`scheduler register/list/trigger/executions`
- [ ] HTTP API：`/api/scheduler/*`
- [ ] 单元测试 + 集成测试

**产出物**：
- `internal/kernel/scheduler/` 完整代码
- `internal/cli/scheduler.go` CLI 命令
- `internal/api/scheduler_handler.go` HTTP API
- 测试覆盖率 > 80%

**验收标准**：
```bash
# 注册任务
agent-os scheduler register \
  --name test_task \
  --cron "*/5 * * * *" \
  --owner fin-agent

# 查看任务
agent-os scheduler list

# 手动触发
agent-os scheduler trigger --task-id 1

# 查看执行历史
agent-os scheduler executions --task-id 1
```

**Agent 分配**：1 个 Agent，专注调度器

---

### WP-2: Resource Manager（2-3 天，可与 WP-1/WP-3 并行）

**目标**：实现资源管理器（配额、优先级、命名空间）

**任务**：
- [ ] 实现 Quota Manager：
  - CheckQuota
  - ConsumeToken
  - 配额重置逻辑
- [ ] 实现 Namespace Manager：
  - 命名空间隔离
  - 路径解析
  - 权限检查（简化版）
- [ ] 配置文件加载（`configs/agents.yaml`）
- [ ] CLI 命令：`resource quota`
- [ ] HTTP API：`/api/resource/*`
- [ ] 单元测试

**产出物**：
- `internal/kernel/resource/` 完整代码
- `configs/agents.yaml` 配置文件
- `internal/cli/resource.go` CLI 命令
- 测试覆盖率 > 80%

**验收标准**：
```bash
# 查询配额
agent-os resource quota --agent fin-agent

# 输出:
# {
#   "agent_id": "fin-agent",
#   "token_quota": 100000,
#   "token_used": 0,
#   "memory_quota_mb": 500,
#   "memory_used_mb": 0
# }
```

**Agent 分配**：1 个 Agent，专注资源管理

---

### WP-3: Memory System（2-3 天，可与 WP-1/WP-2 并行）

**目标**：实现 Memory 子系统（写入、检索、命名空间）

**任务**：
- [ ] 数据表迁移脚本（从 v2 迁移 agent_memory）
- [ ] 实现 Memory Store：
  - Write（写入记忆 + 向量化）
  - Search（BM25 + 向量混合检索）
  - Query（按条件查询）
- [ ] 命名空间隔离集成
- [ ] CLI 命令：`memory write/search/query`
- [ ] HTTP API：`/api/memory/*`
- [ ] 单元测试

**产出物**：
- `internal/kernel/memory/` 完整代码
- `scripts/migrate-memory.sql` 迁移脚本
- `internal/cli/memory.go` CLI 命令
- 测试覆盖率 > 70%（向量化部分难测试）

**验收标准**：
```bash
# 写入记忆
agent-os memory write \
  --content "测试记忆内容" \
  --category "test" \
  --agent-id "fin-agent"

# 搜索记忆
agent-os memory search \
  --query "测试" \
  --agent-id "fin-agent" \
  --top-k 10
```

**Agent 分配**：1 个 Agent，专注 Memory

---

### WP-4: CLI 集成 + agent-ts 切换（2 天，依赖 WP-1/2/3）

**目标**：agent-ts 完全切换到 Agent OS

**任务**：
- [ ] 实现 agent-ts CLI 执行器（`agent-os-cli.ts`）
- [ ] 改写工具定义（memory_write, memory_search, decision_record）
- [ ] 实现任务注册逻辑（启动时注册到 OS）
- [ ] 实现 Webhook 接口（OS 触发 agent）
- [ ] 删除 agent-ts 本地 Cron 代码
- [ ] 端到端测试

**产出物**：
- `agent-ts/src/utils/agent-os-cli.ts`
- 迁移后的工具定义
- `agent-ts/src/api/agent-trigger.ts` Webhook
- 端到端测试用例

**验收标准**：
```bash
# agent-ts 启动后，OS 能看到任务
agent-os scheduler list | grep daily_recall_audit

# OS 触发任务，agent 执行成功
agent-os scheduler trigger --task-id <id>

# agent 调用工具，OS 处理
# (在 agent 推理过程中观察)
```

**Agent 分配**：1 个 Agent，专注 agent-ts 集成

---

### WP-5: Market Driver（2 天，可与 WP-6/WP-7 并行）

**目标**：实现市场数据驱动（Python CLI）

**任务**：
- [ ] 创建 `drivers/market_driver/` 目录
- [ ] 实现 Market Driver CLI（Python）：
  - `market-driver quote --symbol ...`
  - `market-driver kline --symbol ...`
- [ ] AKShare 适配器
- [ ] Redis 缓存层（可选）
- [ ] OS 实现 Data 命令（调用 Driver）
- [ ] Python 单元测试

**产出物**：
- `drivers/market_driver/main.py`
- `drivers/market_driver/akshare_adapter.py`
- `internal/cli/data.go` CLI 命令
- `internal/drivers/market/cli_driver.go` OS 调用 Driver

**验收标准**：
```bash
# 直接调用 Driver
market-driver quote --symbol 600519.SH

# 通过 OS 调用
agent-os data quote --symbol 600519.SH
```

**Agent 分配**：1 个 Agent，专注 Market Driver

---

### WP-6: Feishu Driver（2 天，可与 WP-5/WP-7 并行）

**目标**：实现飞书通知驱动

**任务**：
- [ ] 创建 `drivers/feishu_driver/` 目录
- [ ] 实现 Feishu Driver CLI（Python）：
  - `feishu-driver send --title ... --message ...`
- [ ] 飞书 Webhook API 集成
- [ ] 消息卡片构造
- [ ] OS 实现 Notification Manager
- [ ] OS Notify 命令
- [ ] 在 Scheduler 中集成通知
- [ ] Python 单元测试

**产出物**：
- `drivers/feishu_driver/main.py`
- `internal/kernel/notification/manager.go`
- `internal/cli/notify.go` CLI 命令

**验收标准**：
```bash
# 直接调用 Driver
feishu-driver send \
  --title "测试通知" \
  --message "这是测试消息"

# 通过 OS 发送通知
agent-os notify send \
  --user yunpeng \
  --title "测试" \
  --message "测试消息"

# 飞书收到消息卡片
```

**Agent 分配**：1 个 Agent，专注 Feishu Driver

---

### WP-7: Decision System（2 天，可与 WP-5/WP-6 并行）

**目标**：实现 Decision 子系统

**任务**：
- [ ] 数据表迁移（agent_decisions, decision_tracking）
- [ ] 实现 Decision Store：
  - Record（记录决策）
  - Query（查询决策）
  - Track（追踪决策结果）
- [ ] CLI 命令：`decision record/query/track`
- [ ] HTTP API：`/api/decision/*`
- [ ] 单元测试

**产出物**：
- `internal/kernel/decision/` 完整代码
- `scripts/migrate-decision.sql` 迁移脚本
- `internal/cli/decision.go` CLI 命令

**验收标准**：
```bash
# 记录决策
agent-os decision record \
  --action "watch" \
  --targets '["600519.SH"]' \
  --reason "早盘强势" \
  --agent-id "fin-agent"

# 查询决策
agent-os decision query \
  --action "watch" \
  --agent-id "fin-agent"
```

**Agent 分配**：1 个 Agent，专注 Decision

---

### WP-8: 权限 + Event Bus（2 天，依赖 Stage 3）

**目标**：实现权限系统和事件总线

**任务**：
- [ ] 实现权限检查（AuthManager）
- [ ] 在 CLI/API 入口处集成权限检查
- [ ] 实现 Event Bus（PostgreSQL NOTIFY）
- [ ] WebSocket 订阅接口
- [ ] 在 Scheduler 中发布事件
- [ ] 单元测试

**产出物**：
- `internal/kernel/security/auth.go`
- `internal/kernel/ipc/eventbus.go`
- `internal/api/events_handler.go` WebSocket

**验收标准**：
```bash
# memory-agent 调用 trading 命令 → 403
AGENT_ID=memory-agent agent-os trading order ... 
# Error: permission denied

# 任务完成后，web 收到 WebSocket 通知
# (在浏览器 console 观察)
```

**Agent 分配**：1 个 Agent

---

### WP-9: 生产优化（1 天，依赖 Stage 4）

**目标**：性能测试、监控、文档

**任务**：
- [ ] 性能基准测试
- [ ] Prometheus 指标暴露
- [ ] 部署脚本（systemd/launchd）
- [ ] 文档完善（README, ARCHITECTURE, API, CLI）
- [ ] 回归测试
- [ ] 生产试运行

**产出物**：
- 性能测试报告
- `scripts/deploy.sh`
- 完整文档

**验收标准**：
- [ ] CLI 调用 < 100ms
- [ ] Memory 写入 < 200ms
- [ ] 生产环境稳定运行 24 小时

**Agent 分配**：1 个 Agent

---

## 4. 执行时间线（并行版）

### Stage 0: 项目脚手架（Day 1）
```
Day 1: WP-0 (1 Agent)
  ├─ 上午: 项目结构 + Go Module
  ├─ 下午: CLI 框架 + 配置系统
  └─ 晚上: 数据库 Schema + 构建脚本
  
你的工作: 审核项目结构、运行 go build 测试
```

### Stage 1: 核心模块（Day 2-4，3 天）
```
Day 2-4: WP-1 + WP-2 + WP-3 (3 Agents 并行)
  
  Agent A: Scheduler Core
    ├─ Day 2: 数据结构 + Repository
    ├─ Day 3: Scheduler 核心 + Executor
    └─ Day 4: DAG + CLI + 测试
  
  Agent B: Resource Manager
    ├─ Day 2: Quota Manager
    ├─ Day 3: Namespace Manager
    └─ Day 4: CLI + 测试
  
  Agent C: Memory System
    ├─ Day 2: 数据迁移 + Store
    ├─ Day 3: 检索引擎（BM25 + Vector）
    └─ Day 4: CLI + 测试

你的工作:
  - Day 2 晚: 审核数据结构定义
  - Day 3 晚: 审核核心逻辑
  - Day 4 晚: 运行所有测试，集成验证
```

### Stage 2: CLI 集成（Day 5-6，2 天）
```
Day 5-6: WP-4 (1 Agent)
  ├─ Day 5: agent-ts CLI 执行器 + 工具改写
  └─ Day 6: Webhook + 端到端测试

你的工作:
  - Day 5 晚: 审核 agent-ts 集成代码
  - Day 6 晚: 手动测试完整流程
```

### Stage 3: Driver + Decision（Day 7-8，2 天）
```
Day 7-8: WP-5 + WP-6 + WP-7 (3 Agents 并行)
  
  Agent A: Market Driver
    ├─ Day 7: Python CLI + AKShare
    └─ Day 8: OS 集成 + 测试
  
  Agent B: Feishu Driver
    ├─ Day 7: Python CLI + 飞书 API
    └─ Day 8: Notification Manager + 测试
  
  Agent C: Decision System
    ├─ Day 7: 数据迁移 + Store
    └─ Day 8: CLI + 测试

你的工作:
  - Day 7 晚: 审核 Driver 代码
  - Day 8 晚: 测试飞书通知、行情查询
```

### Stage 4: 权限 + Event Bus（Day 9-10，2 天）
```
Day 9-10: WP-8 (1 Agent)
  ├─ Day 9: 权限系统 + Event Bus
  └─ Day 10: WebSocket + 测试

你的工作:
  - Day 9 晚: 审核权限逻辑
  - Day 10 晚: 测试权限拒绝、WebSocket 推送
```

### Stage 5: 生产优化（Day 11，1 天）
```
Day 11: WP-9 (1 Agent)
  ├─ 上午: 性能测试 + Prometheus
  ├─ 下午: 部署脚本 + 文档
  └─ 晚上: 回归测试

你的工作:
  - 全天: 审核所有文档
  - 晚上: 生产环境部署试运行
```

**总工期: 11 天**

---

## 5. 审核 Checklist

### 每个 WP 完成后，你需要审核：

#### 代码质量
- [ ] 代码结构清晰（Clean Architecture）
- [ ] 命名规范（Go 风格）
- [ ] 错误处理完善
- [ ] 日志记录合理

#### 功能完整性
- [ ] 所有任务清单完成
- [ ] CLI 命令能运行
- [ ] HTTP API 能调用（如果有）
- [ ] 单元测试通过

#### 集成验证
- [ ] 与其他模块集成无冲突
- [ ] 数据库操作正常
- [ ] 配置文件加载正常

#### 文档完整性
- [ ] 代码注释清晰
- [ ] README 更新
- [ ] API 文档完整（如果有）

### 你的审核方式

#### 快速审核（每天晚上）
```bash
# 1. 拉取代码
git fetch
git checkout <worktree-branch>

# 2. 编译测试
go build -o agent-os ./cmd/agent-os
go test ./...

# 3. 手动测试关键命令
./agent-os scheduler list
./agent-os memory write --content "test" --category test

# 4. 审核代码（重点看核心逻辑）
# 看 internal/kernel/ 下的核心代码
```

#### 深度审核（Stage 结束时）
```bash
# 1. 回归测试
./scripts/run-all-tests.sh

# 2. 集成测试
./scripts/integration-test.sh

# 3. 性能测试（Stage 1 后）
./scripts/benchmark.sh

# 4. 端到端测试（Stage 2 后）
# 启动 agent-ts，观察完整流程
```

---

## 6. 协作流程

### Agent 提交代码
1. Agent 在 worktree 中完成代码
2. Agent 运行测试，确保通过
3. Agent 提交代码 + 写完成报告
4. Agent 通知你审核

### 你审核代码
1. 收到通知，拉取代码
2. 运行 `go build` + `go test`
3. 手动测试关键功能
4. 审核核心代码逻辑
5. 反馈：
   - ✅ **通过**：合并到 main，进入下一个 WP
   - 🔄 **修改**：指出问题，Agent 修复后重新提交
   - ❌ **重做**：架构问题，Agent 重新设计

### 每日站会（可选）
- 时间：每晚 10 点（你审核完成后）
- 内容：
  - 今天完成了什么
  - 遇到了什么问题
  - 明天计划做什么
  - 需要调整优先级吗

---

## 7. 风险应对

### 风险 1: Agent 并行冲突
**现象**: WP-1/2/3 修改了同一个文件  
**应对**: 
- 代码结构严格分层，避免交叉
- 冲突时人类合并（你来决定保留哪个）

### 风险 2: 集成测试失败
**现象**: Stage 1 结束后，3 个模块集成不工作  
**应对**:
- Stage 1 最后 1 天留 buffer，专门做集成测试
- 失败时你指定 1 个 Agent 专门修集成问题

### 风险 3: 性能不达标
**现象**: CLI 调用 > 100ms  
**应对**:
- Stage 5 专门留 1 天优化
- 如果还不行，启动 Rust 重写计划（Plan B）

---

## 8. 下一步行动

### 立即行动（现在）
1. **你确认计划**：这个并行方案可行吗？
2. **我启动 Agent**：创建 3 个 Agent（WP-0, WP-1, WP-2）
3. **开工 WP-0**：1 个 Agent 先做脚手架（1 天）

### 明天行动
1. **你审核 WP-0**：晚上审核脚手架代码
2. **启动 Stage 1**：3 个 Agent 并行开工（WP-1/2/3）

### 后续行动
按照 Stage 1 → 5 推进，每个 Stage 结束你深度审核

---

## 9. 你的决策

**现在需要你确认**：

1. **并行方案认可吗？**
   - 11 天工期可行吗？
   - 3 Agent 并行你能审核过来吗？

2. **什么时候开工？**
   - 现在立即启动 WP-0？
   - 还是明天？

3. **审核节奏？**
   - 每天晚上审核？
   - 还是每 Stage 结束审核？

4. **我的角色？**
   - 我扮演 3 个 Agent（轮流写代码）？
   - 还是你希望我只做 1 个 Agent（串行）？

**告诉我，我们立即开工！** 🚀
