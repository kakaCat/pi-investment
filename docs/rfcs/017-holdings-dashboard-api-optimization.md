# RFC 017: 账户持仓看板 API 性能优化

**状态**: Draft  
**创建**: 2026-09-12  
**作者**: Claude (基于代码审查与性能分析)  
**影响范围**: `agent-dh/packages/pages/holdings`、`quantsys-v2` 相关 API 端点

---

## 1. 问题陈述

### 1.1 现状

`/dashboard/api/holdings` 接口响应时间 **4.01 秒**（实测），影响用户体验。该接口聚合 6 个上游数据源：

```typescript
// agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:38-45
const [accounts, accountStatus, trades, watchRules, schedulerTasks, agentOsTasks] = 
  await Promise.allSettled([
    this.fetchAccounts(v2BaseURL, timeout),           // 1. 账户列表
    this.fetchAccountStatus(v2BaseURL, accountName),  // 2. 持仓+汇总
    this.fetchTrades(v2BaseURL, accountName),         // 3. 交易记录
    this.fetchWatchRules(v2BaseURL, accountName),     // 4. 盯盘规则
    this.fetchSchedulerTasks(v2BaseURL),              // 5. 调度任务
    this.fetchAgentOsTasks(agentOsBaseURL),           // 6. Agent OS 任务
  ]);
```

### 1.2 根因分析

| 问题项 | 当前实现 | 瓶颈 | 影响 |
|--------|---------|------|------|
| **交易记录补名称** | 前端循环调用 `/api/stocks/search`（最多 40 次） | N+1 查询；串行请求 | 网络往返 × N |
| **调度任务全量拉取** | `GET /api/scheduler/tasks?pageSize=200` | 返回全部 200 条任务，看板只需当前账户的 5-10 条 | 数据传输 + 解析浪费 |
| **Agent OS 双请求** | 调用 `/tasks` + `/tasks/stats` 然后合并 | 两次网络往返；每次返回完整 payload（43KB） | 网络 × 2，原 `limit=50` 已改 `limit=5` |
| **盯盘规则全量** | 前端虽传 `account_name`，后端**未确认是否过滤** | 若后端未过滤，返回所有账户的规则 | 数据传输浪费 |

### 1.3 性能目标

- **P0**: `/dashboard/api/holdings` 响应时间 **< 1 秒**（从 4 秒降到 1 秒以内）
- **P1**: 减少网络往返次数（交易名称补全从 N 次降到 0 次）
- **P2**: 数据传输量减少 70%+（调度任务 200→10，Agent OS 双请求→单请求）

---

## 2. 改造方案

### 2.1 交易记录补名称（后端统一处理）

#### 现状
```typescript
// 前端代码：agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:172-207
private async enrichTradeNames(trades, v2BaseURL, timeout) {
  for (const t of trades) {
    if (!t.stock_name) {
      const resp = await fetchJson(`${v2BaseURL}/api/stocks/search?symbol=${t.symbol}`);
      t.stock_name = resp.name || t.symbol;
    }
  }
}
```

**问题**: 前端每个缺名交易发起一次 `/api/stocks/search`（最多 40 次，虽有去重但仍是网络往返）。

#### 方案 A（推荐）: 后端返回时直接带名称

**改动点**: `quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py`

```python
# 现有端点：GET /api/simulation/trades/history
@router.get('/api/simulation/trades/history')
async def get_trades(account_name: str, limit: int = 100):
    trades = repo.get_trades_by_account(account_name, limit=limit)
    # 新增：批量补全股票名称
    symbols = {t.symbol for t in trades if t.symbol}
    name_map = await _batch_get_stock_names(symbols)  # 一次 JOIN daily_klines 或查缓存
    return [{
        **t.dict(),
        'stock_name': name_map.get(t.symbol, t.symbol),  # 保证有值
    } for t in trades]

async def _batch_get_stock_names(symbols: set) -> dict:
    # 实现：JOIN daily_klines 取最新一条的 name，或用 Redis/内存缓存
    pass
```

**收益**: 前端 `enrichTradeNames` **整个方法删除**，0 次额外请求。

#### 方案 B（备选）: 新增批量查询端点

若不想改现有端点，可新增 `POST /api/stocks/names`：
```python
@router.post('/api/stocks/names')
async def batch_get_names(symbols: List[str]):
    return {sym: get_name(sym) for sym in symbols}
```
前端改为一次批量查询。收益不如方案 A（仍需 1 次额外请求）。

---

### 2.2 调度任务按需查询

#### 现状
```typescript
// agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:216
const url = `${baseURL}/api/scheduler/tasks?pageSize=200`;
```

**问题**: 无脑拉 200 条任务，看板只展示当前账户关联的 5-10 条。

#### 方案: 按账户过滤 + 限制数量

**改动点**: `quantsys-v2/adapters/inbound/fastapi_app/routes/scheduler_async.py`

```python
# 现有端点：GET /api/scheduler/tasks
@router.get('/api/scheduler/tasks')
async def list_tasks(
    account_name: Optional[str] = None,  # 新增：账户过滤
    limit: int = Query(50, le=200),      # 改：允许调用方指定 limit
):
    tasks = scheduler_repo.list_tasks()
    if account_name:
        # 过滤：只返回关联该账户的任务（根据任务命名约定或元数据）
        tasks = [t for t in tasks if _is_account_task(t, account_name)]
    return tasks[:limit]

def _is_account_task(task, account_name: str) -> bool:
    # 根据任务名称前缀或 metadata 判断
    # 例如：agent_virtual 关联 'agent-virtual-*' 或 metadata.account == 'agent_virtual'
    pass
```

**前端改动**:
```typescript
// agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:216
const url = `${baseURL}/api/scheduler/tasks?account_name=${accountName}&limit=10`;
```

**收益**: 数据量从 200 条降到 10 条（95% 减少）。

---

### 2.3 盯盘规则按账户过滤（验证后端）

#### 现状
```typescript
// agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:209
const url = `${baseURL}/api/watch-rules?account_name=${accountName}`;
```

前端**已传** `account_name`，需**验证后端是否真的在过滤**。

#### 行动项

1. **检查** `quantsys-v2/adapters/inbound/fastapi_app/routes/*.py` 中 `/api/watch-rules` 的实现
2. **若后端未过滤**: 加上 `WHERE account_name = ?`
3. **若已过滤**: 此项无需改动（标记为✅）

---

### 2.4 Agent OS 任务优化

#### 现状
```typescript
// agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:230-232
const [listR, statsR] = await Promise.allSettled([
  fetchJson(`${baseURL}/api/v1/scheduler/tasks`, t),        // 请求 1
  fetchJson(`${baseURL}/api/v1/scheduler/tasks/stats`, t),  // 请求 2
]);
// 前端合并两次结果：list 提供 owner，stats 提供运行统计
```

**问题**: 两次网络往返；每次返回完整数据（已临时改 `limit=5`，但仍是两次）。

#### 方案 A（推荐）: Agent OS 提供聚合端点

**改动点**: `agent-os` 仓库

```go
// 新增端点：GET /api/v1/scheduler/tasks/summary
// 返回：list + stats 合并后的精简数据
type TaskSummary struct {
    ID          string    `json:"id"`
    Name        string    `json:"name"`
    Owner       string    `json:"owner"`
    Enabled     bool      `json:"enabled"`
    NextRunAt   time.Time `json:"next_run_at"`
    LastRunAt   time.Time `json:"last_run_at,omitempty"`
    SuccessRate float64   `json:"success_rate,omitempty"`  // 可选
}

func GetTasksSummary(c *gin.Context) {
    owner := c.Query("owner")
    limit := c.DefaultQuery("limit", "10")
    // 一次查询，JOIN tasks + task_runs，返回合并数据
}
```

**前端改动**:
```typescript
// agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts:230
const url = `${baseURL}/api/v1/scheduler/tasks/summary?owner=investor&limit=5`;
const resp = await fetchJson(url, timeout);
return resp.tasks || [];
```

**收益**: 两次请求→一次；数据量减少（不含完整 payload）。

#### 方案 B（快速）: 前端只调 `/tasks`

若看板**不需要**运行统计（success_rate / last_run），可以：
```typescript
// 删除 statsR 请求，只保留 listR
const listR = await fetchJson(`${baseURL}/api/v1/scheduler/tasks?owner=investor&limit=5`, t);
return listR.tasks || [];
```

**收益**: 两次请求→一次（但仍返回完整 payload）。

---

## 3. 实施计划

### 3.1 阶段划分

| 阶段 | 改动项 | 预期收益 | 风险 | 工期 |
|------|--------|---------|------|------|
| **P0 快速修复** | 1. Agent OS `limit=50→5` (已完成)<br>2. 调度任务加 `limit=10`<br>3. Agent OS 删 stats 请求（方案 B） | 响应时间 4s → 2s | 低 | 1h |
| **P1 后端优化** | 4. 交易记录后端补名称<br>5. 调度任务按账户过滤 | 响应时间 2s → 1s | 中（需改 v2 端点） | 4h |
| **P2 彻底重构** | 6. Agent OS 聚合端点<br>7. 盯盘规则验证/修复 | 响应时间 1s → 0.5s | 高（需跨仓库协调） | 1d |

### 3.2 回滚策略

- **P0/P1**: 前端改动可配置开关（feature flag），出问题立即回滚
- **P2**: Agent OS 新端点不影响旧端点，可灰度切换

---

## 4. 验收标准

### 4.1 性能指标

| 指标 | 当前 | 目标 | 验证方法 |
|------|------|------|---------|
| 响应时间（P50） | 4.01s | < 1s | 压测 100 次取中位数 |
| 网络请求数 | 7+（1 主 + 6 上游） | 6（交易名称 0 次额外请求） | Chrome DevTools Network 面板 |
| 数据传输量 | ~50KB | < 15KB | 响应 Content-Length |

### 4.2 功能验证

- [ ] 交易记录的 `stock_name` 字段**不为空**（后端已补全）
- [ ] 调度任务列表**只包含当前账户**关联的任务（< 15 条）
- [ ] Agent OS 任务数据**包含运行统计**（若采用方案 A）或明确**不需要统计**（若采用方案 B）
- [ ] 盯盘规则按账户过滤生效

### 4.3 回归测试

- 账户切换功能正常（从 agent_virtual → agent_brain）
- 持仓列表、交易记录、自动化任务状态**数据正确**
- 看板刷新无白屏/报错

---

## 5. 后续优化方向

1. **缓存层**: 给 `/dashboard/api/holdings` 加 Redis 缓存（TTL 10s），减轻上游压力
2. **增量更新**: WebSocket 推送持仓变动，前端不用轮询
3. **数据预聚合**: 定时任务（每分钟）预计算 `PortfolioSummary`，存 Redis

---

## 附录 A: 相关文件清单

### 前端
- `agent-dh/packages/pages/holdings/src/services/portfolio-aggregation.ts` (核心聚合逻辑)
- `agent-dh/packages/pages/holdings/src/routes/holdings-routes.ts` (路由层)

### 后端 (quantsys-v2)
- `adapters/inbound/fastapi_app/routes/simulation_async.py` (交易记录)
- `adapters/inbound/fastapi_app/routes/scheduler_async.py` (调度任务)
- `adapters/inbound/fastapi_app/routes/*.py` (盯盘规则，待定位)

### 后端 (agent-os)
- `internal/handlers/scheduler.go` (任务端点)

---

## 附录 B: 性能基线（2026-09-12）

```bash
# 测试命令
curl -w "@curl-format.txt" "http://127.0.0.1:13080/dashboard/api/holdings?account=agent_virtual"

# 结果
time_total: 4.010s
size_download: 599 bytes
num_connects: 1
```

**上游调用耗时分布（推测）**:
- Agent OS tasks: 4s（超时等待）
- 其他 5 个: < 0.1s

---

**审批流程**: [待填写]  
**实施负责人**: [待指定]  
**预计完成时间**: P0 当天，P1 本周内，P2 下周
