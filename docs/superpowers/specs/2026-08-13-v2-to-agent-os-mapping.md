# quantsys-v2 → Agent OS 功能迁移映射表

> **创建时间**: 2026-08-13  
> **目标**: 精确定义 v2 的每个模块在 Agent OS 中的归宿  
> **原则**: OS 核心 vs 领域服务 vs 废弃

---

## 迁移决策矩阵

| 分类 | 迁移到 Agent OS | 保留在独立服务 | 废弃/重构 |
|---|---|---|---|
| **Agent 运行时** | ✅ 核心职责 | ❌ | ❌ |
| **数据驱动** | ✅ 设备驱动层 | ❌ | ❌ |
| **交易执行** | ❌ | ✅ Trading Service | ❌ |
| **策略引擎** | ❌ | ✅ Strategy Service | ❌ |
| **信号分析** | ❌ | ✅ Signal Service | ❌ |
| **机器学习** | ❌ | ✅ ML Service | ❌ |
| **监控工具** | 部分 | 部分 | 部分 |
| **报表可视化** | ❌ | ✅ web-frontend | ❌ |

---

## 1. Agent OS Core Runtime（核心运行时）

**原则**: 任何 AI Agent 都需要的**通用能力**

### ✅ 迁移到 Agent OS (Go 内核层)

| v2 模块 | Agent OS 模块 | 迁移方式 | 优先级 |
|---|---|---|---|
| `memory_async.py` | `internal/kernel/memory/` | 重写为 Go | P0 |
| `memory_distill_async.py` | `internal/kernel/memory/distill.go` | 重写为 Go | P1 |
| `decisions_async.py` | `internal/kernel/decision/` | 重写为 Go | P0 |
| `decision_tracking_async.py` | `internal/kernel/decision/tracking.go` | 重写为 Go | P1 |
| `agent_decision_async.py` | `internal/kernel/decision/agent.go` | 重写为 Go | P1 |
| `evolution_async.py` | `internal/kernel/evolution/` | 重写为 Go | P1 |
| `knowledge_async.py` | `internal/kernel/knowledge/` | 重写为 Go | P1 |
| `scheduler_async.py` | `internal/kernel/scheduler/` | 重写为 Go（全新设计） | P0 |
| `agent_sessions_async.py` | `internal/kernel/session/` | 重写为 Go | P2 |

**实施细节**：

#### Memory 子系统
```
quantsys-v2/adapters/inbound/fastapi_app/routes/memory_async.py
  ↓ 重写为
agent-os/internal/kernel/memory/
  ├── store.go          # 写入/查询
  ├── index.go          # BM25 + Vector 索引
  ├── namespace.go      # 命名空间隔离
  └── gc.go             # 垃圾回收

数据表迁移：
  agent_memory (v2) → agent_memory (agent-os DB)
  保持表结构，只改连接字符串
```

#### Scheduler 子系统（全新设计）
```
quantsys-v2/adapters/inbound/fastapi_app/routes/scheduler_async.py
  ↓ 废弃，全新设计
agent-os/internal/kernel/scheduler/
  ├── scheduler.go      # 调度器核心
  ├── dag.go            # DAG 依赖解析
  ├── executor.go       # 执行引擎
  └── queue.go          # 任务队列

数据表新建：
  scheduler_tasks (agent-os 新建)
  scheduler_executions (agent-os 新建)
```

#### Decision 子系统
```
quantsys-v2/adapters/inbound/fastapi_app/routes/decisions_async.py
  ↓ 重写为
agent-os/internal/kernel/decision/
  ├── record.go         # 决策记录
  ├── tracking.go       # 决策追踪
  └── query.go          # 决策查询

数据表迁移：
  agent_decisions (v2) → agent_decisions (agent-os DB)
  decision_tracking (v2) → decision_tracking (agent-os DB)
```

#### Evolution 子系统
```
quantsys-v2/adapters/inbound/fastapi_app/routes/evolution_async.py
  ↓ 重写为
agent-os/internal/kernel/evolution/
  ├── suggestion.go     # 进化建议
  ├── leaderboard.go    # 排行榜
  └── executor.go       # 执行器

数据表迁移：
  evolution_leaderboard (v2) → evolution_leaderboard (agent-os DB)
  evolution_suggestions (v2) → evolution_suggestions (agent-os DB)
```

---

## 2. Agent OS Device Drivers（设备驱动层）

**原则**: 外部数据源适配器，Python 实现通过 gRPC 暴露

### ✅ 迁移到 Agent OS (Python 驱动进程)

| v2 模块 | Agent OS 驱动 | 迁移方式 | 优先级 |
|---|---|---|---|
| `market_async.py` | `drivers/market_driver/market.py` | 代码迁移 + gRPC 封装 | P0 |
| `market_data_async.py` | `drivers/market_driver/data.py` | 代码迁移 + gRPC 封装 | P0 |
| `quote_market_async.py` | `drivers/market_driver/quote.py` | 代码迁移 + gRPC 封装 | P0 |
| `dividends_async.py` | `drivers/market_driver/dividend.py` | 代码迁移 + gRPC 封装 | P1 |
| `financials_async.py` | `drivers/market_driver/financial.py` | 代码迁移 + gRPC 封装 | P1 |
| `sentiment_async.py` | `drivers/market_driver/sentiment.py` | 代码迁移 + gRPC 封装 | P1 |
| `stock_async.py` | `drivers/market_driver/stock.py` | 代码迁移 + gRPC 封装 | P1 |
| `timeseries_async.py` | `drivers/market_driver/timeseries.py` | 代码迁移 + gRPC 封装 | P1 |
| `data_quality_async.py` | `drivers/market_driver/quality.py` | 代码迁移 + gRPC 封装 | P2 |

**实施细节**：

```
quantsys-v2/adapters/inbound/fastapi_app/routes/market_async.py
quantsys-v2/adapters/outbound/datasources/akshare/
  ↓ 迁移为
agent-os/drivers/market_driver/
  ├── main.py                    # gRPC server 入口
  ├── proto/
  │   └── market.proto           # gRPC 接口定义
  ├── adapters/
  │   ├── akshare_adapter.py     # v2 代码原样迁移
  │   ├── tushare_adapter.py
  │   └── yahoo_adapter.py
  ├── cache.py                   # Redis 缓存层
  └── requirements.txt

Go 侧调用：
agent-os/internal/drivers/market/
  ├── client.go                  # gRPC client
  └── types.go                   # Go 类型定义
```

**gRPC 接口示例**：
```protobuf
service MarketDataService {
  rpc GetQuote(QuoteRequest) returns (QuoteResponse);
  rpc GetKline(KlineRequest) returns (KlineResponse);
  rpc GetFinancials(FinancialsRequest) returns (FinancialsResponse);
  rpc GetDividends(DividendsRequest) returns (DividendsResponse);
  rpc GetSentiment(SentimentRequest) returns (SentimentResponse);
}
```

---

## 3. Trading & Portfolio Services（交易执行层）

**原则**: 金融领域特有，但不是 OS 核心职责

### ❌ 不迁移到 Agent OS，独立为 Trading Service

| v2 模块 | 新架构位置 | 说明 |
|---|---|---|
| `orders_async.py` | `trading-service/orders/` | 独立微服务（Go/Python 待定） |
| `executions_async.py` | `trading-service/executions/` | 同上 |
| `pools_async.py` | `trading-service/pools/` | 同上 |
| `portfolio_opt_async.py` | `trading-service/portfolio/` | 同上 |
| `risk_async.py` | `trading-service/risk/` | 同上 |
| `strategy_trading_async.py` | `trading-service/strategy/` | 同上 |
| `v14_trading.py` | `trading-service/v14/` | 同上 |

**理由**：
- Trading 是**领域业务逻辑**，不是 OS 基础设施
- fin-agent 通过 Agent OS 的 syscall 调用 Trading Service
- 架构：`fin-agent → Agent OS (权限检查) → Trading Service`

**实施路径**：
1. **Phase 1**：Trading Service 保持在 quantsys-v2（暂不迁移）
2. **Phase 2**：Agent OS 提供统一的 `/syscall/trading/*` 代理接口
3. **Phase 3**：Trading Service 独立部署（可选，单机够用可以不拆）

---

## 4. Strategy & Backtest Services（策略引擎层）

**原则**: 策略研究工具，不是 OS 核心

### ❌ 不迁移到 Agent OS，独立为 Strategy Service

| v2 模块 | 新架构位置 | 说明 |
|---|---|---|
| `strategies_async.py` | `strategy-service/strategies/` | 策略管理 |
| `strategy_async.py` | `strategy-service/execution/` | 策略执行 |
| `strategy_execution_async.py` | `strategy-service/execution/` | 同上 |
| `backtest_async.py` | `strategy-service/backtest/` | 回测引擎 |
| `backtest_history_async.py` | `strategy-service/backtest/` | 回测历史 |
| `simulation_async.py` | `strategy-service/simulation/` | 模拟 |
| `pipeline_async.py` | `strategy-service/pipeline/` | 策略流水线 |

**理由**：
- 策略引擎是**量化研究工具**，agent 不一定需要
- 回测、模拟等是离线分析，不是实时运行时需求

**实施路径**：
1. 保持在 quantsys-v2（改名为 `quant-research` 或 `strategy-lab`）
2. 作为独立工具箱使用，不走 Agent OS

---

## 5. Signal & Analysis Services（信号分析层）

**原则**: 金融分析工具，部分迁移

### 🔀 混合处理

| v2 模块 | 处理方式 | 说明 |
|---|---|---|
| `signals_async.py` | ✅ 迁移到 Agent OS Driver | 实时信号是数据源 |
| `realtime_signals_async.py` | ✅ 迁移到 Agent OS Driver | 同上 |
| `signal_test_async.py` | ❌ 保留在 Strategy Service | 信号测试是研究工具 |
| `pool_scan_async.py` | ❌ 保留在 Strategy Service | 池扫描是研究工具 |
| `chan_async.py` | ❌ 保留在 Strategy Service | 缠论分析是研究工具 |
| `analysis_async.py` | ❌ 保留在 Strategy Service | 分析服务是研究工具 |
| `indicators_async.py` | ✅ 迁移到 Agent OS Driver | 技术指标是数据计算 |
| `factor_models_async.py` | ❌ 保留在 Strategy Service | 因子模型是研究工具 |

**实施细节**：

#### 实时信号 → Agent OS Driver
```
quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py
quantsys-v2/adapters/inbound/fastapi_app/routes/realtime_signals_async.py
  ↓ 迁移为
agent-os/drivers/signal_driver/
  ├── main.py                    # gRPC server
  ├── proto/signal.proto
  ├── realtime.py                # 实时信号监控
  └── stream.py                  # 流式推送
```

#### 信号测试/分析 → Strategy Service
保持在 quantsys-v2 或独立为 `signal-research` 工具

---

## 6. ML & Training Services（机器学习层）

**原则**: 研究工具，不迁移

### ❌ 不迁移到 Agent OS

| v2 模块 | 新架构位置 | 说明 |
|---|---|---|
| `ml_async.py` | `ml-service/` 或保留在 v2 | 模型推理可能需要 |
| `training_async.py` | 保留在 v2 作为研究工具 | 模型训练是离线任务 |

**理由**：
- 模型训练是离线研究工作
- 模型推理如果 agent 需要，可以作为独立 ML Service

---

## 7. Monitoring & Tools（监控工具层）

**原则**: OS 内置 vs 外部工具

### 🔀 混合处理

| v2 模块 | 处理方式 | 说明 |
|---|---|---|
| `health_async.py` | ✅ 迁移到 Agent OS | OS 健康检查 |
| `alerts_async.py` | ❌ 独立 Alert Service | 告警是外部系统 |
| `watchlist_async.py` | ❌ web-frontend | 前端功能 |
| `watch_async.py` | ❌ web-frontend | 前端功能 |
| `diagnosis_async.py` | ✅ 迁移到 Agent OS | OS 诊断工具 |
| `tools_async.py` | ❌ 保留在 v2 | 研究工具 |
| `jobs_async.py` | ✅ 整合到 Scheduler | 任务管理归调度器 |
| `config_async.py` | ✅ 迁移到 Agent OS | OS 配置管理 |

---

## 8. Reporting & Visualization（报表可视化层）

**原则**: 前端职责，不迁移

### ❌ 不迁移到 Agent OS

| v2 模块 | 新架构位置 | 说明 |
|---|---|---|
| `report_async.py` | `web-frontend/` | 报表生成由前端调用 |
| `charts_async.py` | `web-frontend/` | 图表数据由前端调用 |
| `market_style_async.py` | `web-frontend/` | 市场风格分析由前端调用 |

**理由**：
- 报表、图表是可视化需求，不是 OS 核心
- web-frontend 直接调用数据源（Market Driver）生成报表

---

## 9. Auth & Discovery（辅助服务层）

### 🔀 混合处理

| v2 模块 | 处理方式 | 说明 |
|---|---|---|
| `auth_async.py` | ❌ 不需要（Agent OS 用简化认证） | Agent 身份通过 X-Agent-ID header |
| `discovery_async.py` | ✅ 迁移到 Agent OS | Service Registry 职责 |

---

## 10. 数据表迁移策略

### ✅ 迁移到 Agent OS Database

| v2 表 | Agent OS 表 | 迁移方式 |
|---|---|---|
| `agent_memory` | `agent_memory` | pg_dump + 改连接 |
| `agent_knowledge` | `agent_knowledge` | 同上 |
| `memory_recall_audit` | `memory_recall_audit` | 同上 |
| `agent_decisions` | `agent_decisions` | 同上 |
| `decision_tracking` | `decision_tracking` | 同上 |
| `evolution_leaderboard` | `evolution_leaderboard` | 同上 |
| `evolution_suggestions` | `evolution_suggestions` | 同上 |
| `scheduler_tasks` | 新建（全新设计） | - |
| `scheduler_executions` | 新建（全新设计） | - |

### ❌ 保留在 quantsys-v2 Database

| v2 表 | 说明 |
|---|---|
| `positions` | 交易持仓（Trading Service） |
| `orders` | 订单记录（Trading Service） |
| `pool_*` | 股票池（Trading Service） |
| `backtest_*` | 回测结果（Strategy Service） |
| `strategies` | 策略定义（Strategy Service） |
| `realtime_signals` | 实时信号（Signal Driver 读写） |
| `signal_test_results` | 信号测试（Strategy Service） |

---

## 11. 最终架构图

```
┌────────────────────────────────────────────────────────────────┐
│                         User Space                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Fin Agent   │  │ Memory Agent │  │Evolution Agt │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         └─────────────────┴─────────────────┘                  │
└─────────────────────────┬──────────────────────────────────────┘
                          │ Syscall API (HTTP/gRPC)
┌─────────────────────────▼──────────────────────────────────────┐
│                     Agent OS (Go Kernel)                        │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Core Runtime Services                                      ││
│  │  Memory | Decision | Evolution | Knowledge | Scheduler    ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Device Drivers (Python gRPC Servers)                       ││
│  │  Market Driver | Signal Driver | Indicator Driver         ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Storage                                                     ││
│  │  PostgreSQL (agent_memory/decisions/evolution/...)         ││
│  │  Redis (Event Bus, Cache)                                  ││
│  └────────────────────────────────────────────────────────────┘│
└────────────────────┬───────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Trading       │ │Strategy      │ │web-frontend  │
│Service       │ │Service       │ │(Vue)         │
│(quantsys-v2) │ │(quantsys-v2) │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## 12. 迁移优先级与时间线

### Phase 0：Agent OS 框架搭建（Week 1-3）
- [x] Go 项目脚手架
- [x] Scheduler 核心（全新设计）
- [x] Resource Manager
- [x] Syscall API 框架
- [x] CLI 工具

### Phase 1：Core Runtime 迁移（Week 4-6）
- [ ] Memory 子系统（P0）
- [ ] Decision 子系统（P0）
- [ ] 数据库表迁移
- [ ] agent-ts 切换到 Agent OS

### Phase 2：Device Drivers 迁移（Week 7-9）
- [ ] Market Driver（P0）
- [ ] Signal Driver（P1）
- [ ] Indicator Driver（P1）
- [ ] gRPC 接口实现

### Phase 3：其他子系统（Week 10-12）
- [ ] Evolution 子系统（P1）
- [ ] Knowledge 子系统（P1）
- [ ] Event Bus（P1）

### Phase 4：Trading/Strategy Services（Week 13+）
- [ ] 评估是否独立部署
- [ ] 如果是，设计 Trading Service
- [ ] 如果否，保持在 quantsys-v2 作为研究工具

---

## 13. 关键决策记录

### 决策 1：为什么 Trading 不放在 Agent OS？

**理由**：
- Trading 是**领域业务逻辑**（买什么、卖什么、仓位多少）
- Agent OS 是**基础设施**（调度、记忆、通信）
- 类比：Linux 不管你的应用是做电商还是社交，只管进程调度和文件系统

**影响**：
- fin-agent 通过 Agent OS syscall 调用 Trading Service
- Agent OS 只负责权限检查（fin-agent 能调用，memory-agent 不能）

### 决策 2：为什么 Strategy/Backtest 不放在 Agent OS？

**理由**：
- 策略回测是**离线研究工具**，不是实时运行时需求
- agent 做决策时不需要回测（回测是策略开发阶段的事）
- 类比：TensorFlow 训练模型 vs TensorFlow Serving 推理模型

**影响**：
- quantsys-v2 保留策略研究能力，改名为 `quant-research` 或 `strategy-lab`
- Agent OS 专注运行时，不管策略怎么来的

### 决策 3：为什么 Scheduler 全新设计，不迁移 v2 的？

**理由**：
- v2 的 scheduler 只管 v2 后端任务，agent 任务不在其中（双调度器问题）
- 新 Scheduler 需要 DAG 依赖、Token 配额、并发控制（v2 没有）
- 迁移改造成本 > 全新设计

**影响**：
- v2 的 `scheduler_async.py` 废弃
- Agent OS 的 Scheduler 是从零设计的

### 决策 4：为什么用 Go 而不是继续 Python？

**理由**：
- Go 的并发模型（goroutine）天然适合调度器
- Go 的 GC 延迟低，适合实时系统
- Python GIL 限制并发，不适合做 OS 内核

**影响**：
- Core Runtime 全部用 Go 重写
- 数据驱动层保留 Python（金融库生态丰富）

---

## 14. 你的下一步决策

1. **这个迁移映射满意吗？** 哪些模块的归宿需要调整？

2. **Trading/Strategy Services 的未来**：
   - 选项 A：短期保持在 quantsys-v2，长期独立部署
   - 选项 B：永久保持在 quantsys-v2 作为研究工具
   - 选项 C：迁移到 Agent OS（我不推荐）

3. **数据库迁移策略**：
   - 选项 A：Agent OS 新建数据库 `agent_os`，从 v2 迁移表
   - 选项 B：Agent OS 复用 v2 数据库 `quant_investment`（改名）
   
4. **启动时机确认**：现在立即开工建 Go 脚手架？

告诉我你的决定！
