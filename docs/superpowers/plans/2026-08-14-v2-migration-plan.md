# quantsys-v2 → Agent OS 迁移执行计划

> **创建时间**: 2026-08-14  
> **目标**: 将 quantsys-v2 的功能迁移到 Agent OS + 独立服务架构  
> **原则**: OS 管通用能力，Service 管领域逻辑

---

## 📊 迁移总览

### 迁移策略

```
quantsys-v2 (All-in-One)
         ↓
    ┌────┴────┐
    ↓         ↓
Agent OS    Trading/Signal/Strategy Services
(通用)      (领域专用)
```

**目标架构**:
- **Agent OS**: Agent 运行时、调度、资源管理、记忆、决策
- **Trading Service**: 交易执行、账户管理、风控
- **Signal Service**: 信号生成、回测、优化
- **Strategy Service**: 策略引擎、因子计算
- **web-frontend**: 可视化、报表

---

## 🎯 迁移决策矩阵

| v2 模块 | 迁移目标 | 原因 | 优先级 |
|---|---|---|---|
| **Agent 运行时** | ✅ Agent OS | OS 核心职责 | P0 |
| **调度器** | ✅ Agent OS | OS 核心职责 | P0 |
| **记忆系统** | ✅ Agent OS | OS 核心职责 | P0 |
| **决策系统** | ✅ Agent OS | OS 核心职责 | P0 |
| **进化系统** | ✅ Agent OS | OS 核心职责 | P1 |
| **数据驱动** | ✅ Agent OS Driver | OS 设备层 | P1 |
| **通知系统** | ✅ Agent OS | OS 核心职责 | P0 |
| **交易执行** | ⏸️ Trading Service | 领域专用 | P2 |
| **策略引擎** | ⏸️ Strategy Service | 领域专用 | P2 |
| **信号分析** | ⏸️ Signal Service | 领域专用 | P2 |
| **缠论分析** | ⏸️ Chan Service | 领域专用 | P3 |
| **机器学习** | ⏸️ ML Service | 领域专用 | P3 |
| **Web API** | ⏸️ web-frontend | 前端 | P2 |

---

## 📋 详细迁移计划

### Phase 1: Agent OS 核心功能迁移（P0）

**目标**: 将 Agent 运行时核心功能迁移到 Agent OS

**工期**: 1-2 周

#### 模块 1.1: Memory 子系统 ⭐ 已完成

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `routes/memory_async.py` | `internal/repository/memory_repository.go` | ✅ 已完成 |
| `routes/memory_distill_async.py` | 待实现 | ⏸️ P1 |
| 数据表: `agent_memory` | 迁移到 agent_os DB | ⏸️ 待迁移 |

**迁移步骤**:
1. ✅ Go 代码已实现（internal/repository/memory_repository.go）
2. ⏸️ 数据迁移：`pg_dump agent_memory` → agent_os DB
3. ⏸️ 更新 agent-ts 连接字符串
4. ⏸️ 测试验证

---

#### 模块 1.2: Decision 子系统 ⭐ 已完成

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `routes/decisions_async.py` | `internal/repository/decision_repository.go` | ✅ 已完成 |
| `routes/decision_tracking_async.py` | `internal/service/decision_service.go` | ✅ 已完成 |
| 数据表: `agent_decisions` | 迁移到 agent_os DB | ⏸️ 待迁移 |

**迁移步骤**:
1. ✅ Go 代码已实现
2. ⏸️ 数据迁移：`pg_dump agent_decisions, decision_tracking`
3. ⏸️ 更新 agent-ts 连接
4. ⏸️ 测试验证

---

#### 模块 1.3: Scheduler 子系统 ⭐ 已完成

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `routes/scheduler_async.py` | `internal/kernel/scheduler/scheduler.go` | ✅ 已完成 |
| `scheduler_daemon.py` | Agent OS Daemon | ✅ 已完成 |
| `unified_scheduler.py` | 废弃（全新设计） | ✅ 已废弃 |

**迁移步骤**:
1. ✅ 全新 Scheduler 已实现（DAG + Executor）
2. ⏸️ 迁移 v2 任务定义到 Agent OS
3. ⏸️ 删除 v2 scheduler 代码
4. ⏸️ 测试验证

---

#### 模块 1.4: Notification 子系统 ⭐ 已完成

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `infrastructure/notification/feishu_service.py` | `drivers/feishu-driver/` | ✅ 已完成 |
| 飞书通知逻辑 | `internal/service/notification_service.go` | ✅ 已完成 |

**迁移步骤**:
1. ✅ Feishu Driver 已实现
2. ✅ Notification Manager 已实现
3. ⏸️ 更新 agent-ts 调用方式
4. ⏸️ 删除 v2 notification 代码

---

### Phase 2: Agent OS 扩展功能（P1）

**目标**: 迁移扩展功能到 Agent OS

**工期**: 1 周

#### 模块 2.1: Evolution 子系统 ⏸️ 待迁移

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `routes/evolution_async.py` | `internal/kernel/evolution/` | ⏸️ 待实现 |
| 数据表: `evolution_leaderboard` | 迁移到 agent_os DB | ⏸️ 待迁移 |
| 数据表: `evolution_suggestions` | 迁移到 agent_os DB | ⏸️ 待迁移 |

**迁移步骤**:
1. ⏸️ 实现 Evolution Manager (Go)
2. ⏸️ 迁移数据表
3. ⏸️ 实现 CLI 命令：`agent-os evolution suggest`
4. ⏸️ 更新 agent-ts 工具

**工期**: 2-3 天

---

#### 模块 2.2: Knowledge 子系统 ⏸️ 待迁移

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `routes/knowledge_async.py` | `internal/kernel/knowledge/` | ⏸️ 待实现 |
| 知识蒸馏逻辑 | `internal/service/knowledge_service.go` | ⏸️ 待实现 |

**迁移步骤**:
1. ⏸️ 实现 Knowledge Manager (Go)
2. ⏸️ 实现知识蒸馏算法
3. ⏸️ 实现 CLI 命令：`agent-os knowledge distill`
4. ⏸️ 更新 agent-ts 工具

**工期**: 2-3 天

---

#### 模块 2.3: Market Data Driver ⭐ 已完成

| v2 模块 | Agent OS 模块 | 状态 |
|---|---|---|
| `adapters/akshare_adapter.py` | `drivers/market-driver/` | ✅ 已完成 |
| `adapters/baostock_adapter.py` | 可选：添加到 market-driver | ⏸️ 可选 |
| Redis 缓存 | `drivers/market-driver/cache/` | ✅ 已完成 |

**迁移步骤**:
1. ✅ Market Driver 已实现（AKShare）
2. ⏸️ 可选：添加 Baostock 适配器
3. ⏸️ 更新 agent-ts 调用方式
4. ⏸️ 删除 v2 adapter 代码

---

### Phase 3: agent-ts 集成切换（P0）

**目标**: agent-ts 从 v2 切换到 Agent OS

**工期**: 2-3 天

#### 切换步骤

**Step 1: 更新工具定义**

| 工具 | v2 调用 | Agent OS 调用 | 状态 |
|---|---|---|---|
| `memory_write` | `POST http://v2:5001/memory/write` | `execSync('agent-os memory write ...')` | ⏸️ 待改 |
| `memory_search` | `POST http://v2:5001/memory/search` | `execSync('agent-os memory search ...')` | ⏸️ 待改 |
| `decision_record` | `POST http://v2:5001/decisions/record` | `execSync('agent-os decision record ...')` | ⏸️ 待改 |
| `recall_audit` | `POST http://v2:5001/memory/recall_audit` | `execSync('agent-os memory recall-audit ...')` | ⏸️ 待改 |
| `notification_send` | 直接调 v2 | `execSync('agent-os notify send ...')` | ⏸️ 待改 |
| `market_quote` | `POST http://v2:5001/data/quote` | `execSync('agent-os data quote ...')` | ⏸️ 待改 |

**Step 2: 任务注册迁移**

```typescript
// agent-ts/src/services/scheduler/register-to-os.ts

// Before (v2)
await axios.post('http://127.0.0.1:5001/scheduler/register', {
  name: 'daily_recall_audit',
  cron: '30 8 * * *',
  ...
});

// After (Agent OS)
await execAgentOS([
  'scheduler', 'register',
  '--name', 'daily_recall_audit',
  '--cron', '30 8 * * *',
  '--owner', 'memory-agent',
  '--agent-kind', 'memory',
  '--prompt', '执行每日召回审计',
]);
```

**Step 3: 数据库切换**

```yaml
# agent-ts/config.yaml

# Before
database:
  host: 127.0.0.1
  port: 5432
  database: quant_investment  # v2 DB

# After
database:
  host: 127.0.0.1
  port: 5432
  database: agent_os  # Agent OS DB
```

**Step 4: 删除 v2 依赖**

```bash
# agent-ts 不再依赖 v2 HTTP API
# 删除 v2 相关代码
rm -rf src/infrastructure/http/v2-client.ts
```

---

### Phase 4: Trading/Signal/Strategy Services 拆分（P2）

**目标**: 将领域专用逻辑拆分为独立服务

**工期**: 2-3 周（可延后）

#### Service 1: Trading Service ⏸️ 待拆分

**职责**: 交易执行、账户管理、风控

| v2 模块 | Trading Service 模块 | 状态 |
|---|---|---|
| `application/services/account_trading_service.py` | `trading-service/account/` | ⏸️ 待拆 |
| `live_trading/paper_trading_engine.py` | `trading-service/engine/` | ⏸️ 待拆 |
| `domain/trading/` | `trading-service/domain/` | ⏸️ 待拆 |

**技术栈**: Python（FastAPI）

**接口**: HTTP API

**数据库**: 共享 agent_os DB 的 trading 表

---

#### Service 2: Signal Service ⏸️ 待拆分

**职责**: 信号生成、回测、优化

| v2 模块 | Signal Service 模块 | 状态 |
|---|---|---|
| `application/services/signal_execution_scheduler.py` | `signal-service/execution/` | ⏸️ 待拆 |
| `adapters/outbound/repositories/simulation_repository.py` | `signal-service/simulation/` | ⏸️ 待拆 |

**技术栈**: Python（FastAPI）

**接口**: HTTP API

---

#### Service 3: Strategy Service ⏸️ 待拆分

**职责**: 策略引擎、因子计算、回测

| v2 模块 | Strategy Service 模块 | 状态 |
|---|---|---|
| `domain/strategy/` | `strategy-service/domain/` | ⏸️ 待拆 |
| `application/services/backtest_service.py` | `strategy-service/backtest/` | ⏸️ 待拆 |

**技术栈**: Python（FastAPI）

**接口**: HTTP API

---

### Phase 5: 数据迁移（关键）

**目标**: 将 v2 数据库迁移到 agent_os

**工期**: 1 天

#### 迁移步骤

**Step 1: 备份 v2 数据**

```bash
# 备份 quant_investment 数据库
pg_dump -h 127.0.0.1 -U mac -d quant_investment > v2_backup_$(date +%Y%m%d).sql

# 备份关键表
pg_dump -h 127.0.0.1 -U mac -d quant_investment \
  -t agent_memory \
  -t agent_decisions \
  -t decision_tracking \
  -t evolution_leaderboard \
  -t evolution_suggestions \
  > v2_agent_tables_$(date +%Y%m%d).sql
```

**Step 2: 迁移到 agent_os DB**

```bash
# 方案 A: 全新导入
psql -h 127.0.0.1 -U mac -d agent_os -f v2_agent_tables.sql

# 方案 B: 使用 pg_dump/restore
pg_dump -h 127.0.0.1 -U mac -d quant_investment -t agent_memory | \
  psql -h 127.0.0.1 -U mac -d agent_os
```

**Step 3: 验证数据一致性**

```sql
-- v2 DB
SELECT count(*) FROM agent_memory;
SELECT count(*) FROM agent_decisions;

-- agent_os DB
SELECT count(*) FROM agent_memory;
SELECT count(*) FROM agent_decisions;

-- 对比数量是否一致
```

**Step 4: 更新外键和索引**

```sql
-- agent_os DB
-- 确保索引存在
CREATE INDEX IF NOT EXISTS idx_agent_memory_namespace ON agent_memory(namespace_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent ON agent_decisions(agent_id);
```

---

### Phase 6: 清理 v2 代码（最后）

**目标**: 删除已迁移的 v2 代码

**工期**: 1 天

#### 清理清单

**可以删除的 v2 模块**:
- ✅ `routes/memory_async.py`
- ✅ `routes/decisions_async.py`
- ✅ `routes/decision_tracking_async.py`
- ✅ `routes/scheduler_async.py`
- ✅ `scheduler_daemon.py`
- ✅ `unified_scheduler.py`
- ✅ `infrastructure/notification/feishu_service.py`
- ⏸️ `routes/evolution_async.py`（等 Phase 2 完成）
- ⏸️ `routes/knowledge_async.py`（等 Phase 2 完成）

**保留的 v2 模块**（暂时）:
- ⏸️ Trading 相关（等 Trading Service 拆分）
- ⏸️ Signal 相关（等 Signal Service 拆分）
- ⏸️ Strategy 相关（等 Strategy Service 拆分）

---

## 📊 迁移时间线

### 总体时间线

```
Week 1-2:  Phase 1 (Agent OS 核心) - agent-ts 集成切换
Week 3:    Phase 2 (Agent OS 扩展) - Evolution + Knowledge
Week 4:    Phase 3 (数据迁移) + Phase 6 (v2 清理)
Week 5-7:  Phase 4 (Service 拆分) - 可延后
```

**关键里程碑**:
- Week 2 末: agent-ts 完全切换到 Agent OS ⭐
- Week 4 末: v2 核心代码清理完成
- Week 7 末: Service 架构完整

---

## ✅ 迁移验收标准

### Phase 1 验收

- [ ] agent-ts 能通过 Agent OS 写入/搜索记忆
- [ ] agent-ts 能通过 Agent OS 记录决策
- [ ] agent-ts 任务由 Agent OS 调度
- [ ] 飞书通知通过 Agent OS 发送
- [ ] agent-ts 不再调用 v2 HTTP API

### Phase 2 验收

- [ ] Evolution 功能正常
- [ ] Knowledge 蒸馏正常
- [ ] Market Driver 查询正常

### Phase 3 验收

- [ ] agent_memory 数据完整迁移
- [ ] agent_decisions 数据完整迁移
- [ ] 数据量一致
- [ ] 无外键错误

### Phase 4 验收

- [ ] Trading Service 独立运行
- [ ] Signal Service 独立运行
- [ ] Strategy Service 独立运行
- [ ] Agent OS 能调用这些 Service

---

## 🚀 立即可执行的任务（今天/明天）

### 任务 1: agent-ts 切换到 Agent OS ⭐ 最重要

**工期**: 1 天

**步骤**:
1. 实现 `agent-ts/src/utils/agent-os-cli.ts`
2. 改写 memory_write 工具
3. 改写 memory_search 工具
4. 改写 decision_record 工具
5. 改写 notification_send 工具
6. 测试验证

### 任务 2: 数据迁移 agent_memory

**工期**: 2 小时

**步骤**:
1. 备份 v2 数据
2. 导出 agent_memory 表
3. 导入到 agent_os DB
4. 验证数据一致性

### 任务 3: 清理 v2 scheduler 代码

**工期**: 1 小时

**步骤**:
1. 确认 agent-ts 不再使用 v2 scheduler
2. 删除 `scheduler_daemon.py`
3. 删除 `unified_scheduler.py`
4. 删除 `routes/scheduler_*.py`

---

## 💬 你的决策

**现在需要你确认**:

1. **"立即执行任务 1"** → agent-ts 切换到 Agent OS（最关键）
2. **"先做数据迁移"** → 迁移 agent_memory 到 agent_os DB
3. **"全面执行 Phase 1"** → 完整执行 Phase 1 所有任务
4. **"看看再说"** → 我继续分析或细化计划

**告诉我下一步！** 🚀
