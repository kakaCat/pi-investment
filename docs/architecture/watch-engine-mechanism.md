# 盯盘引擎触发机制详解

## 1. 系统概述

盯盘引擎（WatchEngine）是 PI Investment 系统的实时监控核心，负责在交易时段内持续监控股票价格，当满足预设条件时自动唤醒 Agent 进行智能决策。

### 关键特性

- **实时监控**：交易时段（9:30-11:30 / 13:00-15:00）持续运行
- **自适应频率**：基础 60s 轮询，接近阈值时加速至 10s
- **智能去重**：条件冷却期（默认 5 分钟）防止重复触发
- **At-Least-Once**：通知失败时落库待补发，保证不漏单
- **优雅降级**：取价失败不阻塞其他规则判定

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI 5001 进程                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  lifespan 启动 (watch_bootstrap.py)                      │   │
│  │    └─> start_watch_engine_in_thread()                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                      │
│                            ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          WatchEngine 后台线程 (常驻)                      │   │
│  │                                                            │   │
│  │  run_forever() {                                          │   │
│  │    while not stopped:                                     │   │
│  │      if 交易时段:                                          │   │
│  │        tick()  # 一次完整判定                             │   │
│  │        sleep(fast_mode ? 10s : 60s)                       │   │
│  │      else:                                                 │   │
│  │        sleep(60s)  # 非交易时段心跳                       │   │
│  │  }                                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心流程：tick() 单次判定

```
┌─ tick() 开始 ────────────────────────────────────────────────┐
│                                                                │
│  1️⃣ 初始化                                                     │
│     ├─ 跨天检测 → 重置状态（均量缓存 / 历史价格 / 触发记录）  │
│     └─ 加载所有启用规则 (rule_repo.list_enabled())           │
│                                                                │
│  2️⃣ 遍历每条规则                                              │
│     ├─ 检查活动窗口 (active_window)                           │
│     │   └─ 非活动窗口 → 跳过                                  │
│     │                                                           │
│     ├─ 获取实时行情 (quote_service.get_realtime_quote())      │
│     │   └─ 取价失败 → 记 warning，跳过（不阻塞其他规则）      │
│     │                                                           │
│     ├─ 更新价格历史 (_push_history, 保留 30 分钟)             │
│     │                                                           │
│     ├─ 构建评估上下文 (EvalContext)                           │
│     │   ├─ cost_price: 成本价（用于盈亏计算）                 │
│     │   ├─ price_history: 最近 30 分钟价格序列                │
│     │   ├─ avg_volume_20d: 20 日均量（用于放量判定）          │
│     │   └─ elapsed_fraction: 当日交易时间进度（用于成交量折算）│
│     │                                                           │
│     └─ 3️⃣ 遍历该规则的所有条件                                │
│         ├─ evaluate(condition, quote, ctx)                     │
│         │   ├─ price_break: 突破价格阈值                       │
│         │   ├─ pct_change: 涨跌幅阈值                          │
│         │   ├─ pnl_pct: 盈亏比例阈值                           │
│         │   ├─ velocity: 窗口内波动速度                        │
│         │   └─ volume_surge: 成交量放大倍数                    │
│         │                                                       │
│         ├─ 🚀 自适应加速逻辑                                   │
│         │   └─ distance_ratio ≤ 0.2 → 进入 fast_mode (10s)    │
│         │                                                       │
│         ├─ 冷却期检查 (_in_cooldown)                           │
│         │   └─ 距上次触发 < cooldown_sec → 跳过（防止重复）    │
│         │                                                       │
│         └─ ✅ 触发确认 → 执行通知                              │
│             ├─ notifier.notify()                               │
│             ├─ 记录触发时间 (_last_triggered)                 │
│             └─ 返回事件详情                                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. 条件评估详解

### 4.1 支持的条件类型

| 条件类型 | 参数 | 触发逻辑 | 应用场景 |
|---------|------|----------|----------|
| **price_break** | `price`, `direction` | 价格突破阈值（above/below） | 关键价位突破 |
| **pct_change** | `pct`, `direction` | 涨跌幅超过阈值 | 异动监控 |
| **pnl_pct** | `pct`, `direction` | 盈亏比例达到止盈/止损线 | 持仓风控 |
| **velocity** | `pct`, `window_min` | 窗口内波动速度 | 短期剧烈波动 |
| **volume_surge** | `multiple` | 成交量倍数放大 | 放量突破/异常交易 |

### 4.2 距离比计算（distance_ratio）

用于自适应频率调整，表示"距触发还有多远"：

```python
# 以 price_break 为例
if direction == 'above':
    distance_ratio = (threshold - current_price) / threshold
else:  # below
    distance_ratio = (current_price - threshold) / threshold

# distance_ratio ≤ 0.2 → 进入快速模式（10s 轮询）
# distance_ratio = 0    → 已触发
```

**示例**：
- 阈值 100 元，当前 95 元 → distance = 5%（正常 60s）
- 阈值 100 元，当前 98 元 → distance = 2%（加速 10s）
- 阈值 100 元，当前 100.5 元 → distance = 0（已触发）

---

## 5. 通知机制：三路并发

```
┌─ notifier.notify() ──────────────────────────────────────────┐
│                                                                │
│  1️⃣ 唤醒 Agent (_notify_agent_with_retry)                     │
│     ├─ POST http://127.0.0.1:3002/wake                        │
│     ├─ Payload: {event: 'watch_triggered', data: {...}}      │
│     ├─ 超时策略：30s（LLM 决策耗时长，超时视为已送达）        │
│     ├─ 重试策略：最多 3 次，间隔 1s                            │
│     └─ 返回值：                                                │
│         ├─ 'ok'      → 成功确认                               │
│         ├─ 'timeout' → 超时（事件已送达，不重试）             │
│         └─ 'error'   → 连接失败（可重试）                     │
│                                                                │
│  2️⃣ WebSocket 广播 (_broadcast_ws)                            │
│     ├─ POST http://127.0.0.1:5003/broadcast/market_data       │
│     ├─ 用途：实时推送到 web-frontend 前端                     │
│     └─ 失败策略：记 debug log，忽略（不阻塞主流程）           │
│                                                                │
│  3️⃣ 审计落库 (_record)                                        │
│     ├─ 写入 watch_triggers 表                                 │
│     ├─ 字段：rule_id, symbol, condition, trigger_price, ...   │
│     ├─ notified 字段标记 Agent 是否成功唤醒                    │
│     └─ 用途：失败补发 + 历史审计                              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 5.1 At-Least-Once 保证

```
触发成功 → notified=True  → 正常流程
触发失败 → notified=False → 落库待补发（未来 Agent 可主动拉取）
```

---

## 6. Agent 唤醒流程

```
┌─ Agent 端 (agent-ts) ────────────────────────────────────────┐
│                                                                │
│  POST /wake {event: 'watch_triggered', data: {...}}          │
│     ↓                                                          │
│  WakeAdapter 解析事件                                          │
│     ↓                                                          │
│  构造 Agent 提示词：                                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 【盯盘触发】                                            │  │
│  │ 股票：600519 贵州茅台                                   │  │
│  │ 现价：1650.00 元（+2.5%）                              │  │
│  │ 触发条件：price_break above 1600                       │  │
│  │ 持仓盈亏：+8.3%（成本价 1523.00）                      │  │
│  │                                                         │  │
│  │ 请分析当前形势并决定：                                  │  │
│  │ 1. 是否需要调整仓位？                                   │  │
│  │ 2. 是否需要发送通知给用户？                             │  │
│  │ 3. 其他需要采取的行动？                                 │  │
│  └────────────────────────────────────────────────────────┘  │
│     ↓                                                          │
│  LLM 决策（调用 DeepSeek）                                     │
│     ├─ 分析市场形势                                            │
│     ├─ 查询相关工具（如查看持仓、技术指标等）                  │
│     └─ 执行动作（如发送飞书通知、调整仓位等）                  │
│     ↓                                                          │
│  返回 {success: true} 给 WatchNotifier                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. 自适应频率机制

### 7.1 三档速度

```
非交易时段：60s 心跳（仅保活，不判定）
正常模式：  60s 轮询（大部分时间）
快速模式：  10s 轮询（接近触发阈值时）
```

### 7.2 升档逻辑

每个 tick 检查所有条件的 `distance_ratio`：

```python
fast = False
for rule in rules:
    for condition in rule.conditions:
        result = evaluate(condition, quote, ctx)
        if result.distance_ratio is not None and result.distance_ratio <= 0.2:
            fast = True
self.fast_mode = fast
```

**示例**：
- 监控 10 只股票，其中 1 只接近止损线（distance = 0.15）
- 整个引擎进入 fast_mode，所有股票都按 10s 轮询
- 该股票跌破止损线后，若其他股票都远离阈值，恢复 60s

---

## 8. 冷却期防重复

```python
_last_triggered = {
    (rule_id, condition_index): last_trigger_time
}

def _in_cooldown(rule_id, cond_idx, cond, now):
    last = _last_triggered.get((rule_id, cond_idx))
    if last is None:
        return False
    cooldown = cond.get('cooldown_sec', 300)  # 默认 5 分钟
    return (now - last).total_seconds() < cooldown
```

**设计目的**：
- 防止价格在阈值附近震荡时重复触发
- 每个条件独立计时（规则 A 条件 1 触发不影响条件 2）
- 用户可自定义冷却时间（如重要阈值设置 60s 短冷却）

---

## 9. 数据库表结构

### 9.1 watch_rules（监控规则）

```sql
CREATE TABLE watch_rules (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,       -- 账户归属
    symbol VARCHAR(16) NOT NULL,           -- 股票代码
    conditions JSONB NOT NULL,             -- 条件数组
    enabled BOOLEAN DEFAULT TRUE,          -- 启用状态
    cost_price NUMERIC(10, 2),             -- 成本价（用于盈亏计算）
    active_window TEXT[],                  -- 活动时间窗口（如 ['09:30-10:00']）
    context TEXT,                          -- 额外上下文（如 "v13 持仓"）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 示例数据
{
    "id": 1,
    "symbol": "600519",
    "conditions": [
        {
            "type": "pnl_pct",
            "params": {"pct": -5, "direction": "below"},
            "cooldown_sec": 300,
            "desc": "止损线"
        },
        {
            "type": "velocity",
            "params": {"pct": 3, "window_min": 10},
            "cooldown_sec": 600,
            "desc": "10分钟内波动超3%"
        }
    ],
    "cost_price": 1523.00,
    "active_window": ["09:30-11:30", "13:00-15:00"]
}
```

### 9.2 watch_triggers（触发历史）

```sql
CREATE TABLE watch_triggers (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES watch_rules(id),
    symbol VARCHAR(16) NOT NULL,
    condition JSONB NOT NULL,              -- 触发的具体条件
    trigger_price NUMERIC(10, 2),          -- 触发时价格
    detail JSONB,                          -- 评估详情（value, message）
    notified BOOLEAN DEFAULT FALSE,        -- 是否成功唤醒 Agent
    triggered_at TIMESTAMP DEFAULT NOW()
);
```

---

## 10. 部署架构

### 10.1 宿主进程变更历史

| 时间 | 宿主进程 | 状态 |
|------|---------|------|
| 2026-07-22 之前 | scheduler_daemon.py | ✅ 正常运行 |
| 2026-08-02 | FastAPI 5001 切换 | ❌ daemon 未重启，盯盘静默失败 |
| 2026-08-12 | watch_bootstrap.py 装配 | ✅ 恢复正常，唯一宿主确立 |

### 10.2 当前部署（2026-08-12 后）

```bash
# 唯一宿主：FastAPI 5001 进程
# 启动方式：launchd 自动拉起
~/Library/LaunchAgents/com.pi-investment.v2-api.plist

# 查看日志
tail -f ~/v2-api.log | grep -i watch

# 重启服务（同时重启盯盘引擎）
launchctl kickstart -k gui/501/com.pi-investment.v2-api

# 或手动启动（测试用）
cd quantsys-v2
python start_all.py  # 内部调用 FastAPI lifespan
```

### 10.3 启动流程

```python
# quantsys-v2/adapters/inbound/fastapi_app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    watch_handle = start_watch_engine(skip=False)
    yield
    # 关闭时
    if watch_handle:
        engine, thread = watch_handle
        engine.stop()
        thread.join(timeout=5)
```

---

## 11. 监控与排查

### 11.1 健康检查

```bash
# 1. 检查进程是否运行
ps aux | grep "uvicorn.*fastapi_app.main:app"

# 2. 检查日志是否有 tick 记录
tail -f ~/v2-api.log | grep "WatchEngine"

# 预期输出：
# WatchEngine 启动 base_interval=60 fast_interval=10
# （每 60s 或 10s 一次心跳日志）

# 3. 检查数据库触发记录
psql -d quant_investment -c "
    SELECT symbol, condition->>'type', trigger_price, notified, triggered_at
    FROM watch_triggers
    ORDER BY triggered_at DESC
    LIMIT 10;
"
```

### 11.2 常见故障

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| 规则创建成功但不触发 | FastAPI 未启动 / daemon 运行但 5001 未启动 | 确认 5001 进程存在 |
| 触发但 Agent 未响应 | Agent 3002 端口未监听 | 启动 agent-ts |
| 频繁触发相同条件 | 冷却期设置过短 | 增大 cooldown_sec |
| 取价失败导致漏监控 | quote_service 数据源故障 | 检查行情服务健康度 |
| watch_triggers 一直是 notified=False | Agent 连接失败 | 检查 AGENT_API_URL 配置 |

### 11.3 调试模式

```python
# 临时降低轮询间隔（测试用）
# quantsys-v2/application/services/watch_engine/factory.py
def start_watch_engine_in_thread():
    engine = WatchEngine(
        ...,
        base_interval=5,   # 改为 5s（默认 60s）
        fast_interval=1,   # 改为 1s（默认 10s）
    )
```

---

## 12. 未来优化方向

### 12.1 性能优化

- [ ] 批量取价（减少行情接口调用）
- [ ] 规则分片（按 symbol 分散到多线程）
- [ ] Redis 缓存（均量、历史价格）

### 12.2 功能增强

- [ ] 更多条件类型（如 MACD 金叉、布林带突破）
- [ ] 动态冷却期（根据波动率自适应）
- [ ] 失败补发机制（Agent 主动拉取 notified=False 的触发）
- [ ] 规则优先级（重要股票优先判定）

### 12.3 可靠性

- [ ] 健康度上报（Prometheus metrics）
- [ ] 异常自愈（取价失败自动切换数据源）
- [ ] 分布式部署（多实例选主）

---

## 13. 参考资料

- 核心代码：[quantsys-v2/application/services/watch_engine/](../../quantsys-v2/application/services/watch_engine/)
- 条件评估器：[engine.py](../../quantsys-v2/application/services/watch_engine/engine.py)
- 通知器实现：[notifier.py](../../quantsys-v2/application/services/watch_engine/notifier.py)
- 启动装配：[watch_bootstrap.py](../../quantsys-v2/adapters/inbound/fastapi_app/watch_bootstrap.py)
- Agent 接入：[wake-adapter.ts](../../agent-ts/src/api/adapters/wake-adapter.ts)
- 单元测试：[tests/services/test_watch_engine.py](../../quantsys-v2/tests/services/test_watch_engine.py)

---

**文档版本**：v1.0  
**最后更新**：2026-08-24  
**维护者**：kakaCat
