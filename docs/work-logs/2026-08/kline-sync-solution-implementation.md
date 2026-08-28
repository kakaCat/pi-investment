# K线每日同步解决方案实施报告

## 问题背景

08-26/27 数据缺失的根本原因：quantsys-v2 调度器废弃后，K线每日同步任务未迁移到 Agent OS，导致新数据无人采集。

## 解决方案

**架构：Agent OS reminder → Agent-DH 工具 → quantsys-v2 HTTP API → DataBackfiller 业务逻辑**

### 实施步骤

#### 1. quantsys-v2 新增 HTTP API（✅ 完成）

**文件：`quantsys-v2/adapters/inbound/fastapi_app/routes/data_sync_async.py`**

新增端点：
- `POST /api/data/sync-daily-klines` - 同步每日K线
- `GET /api/data/sync-status` - 查询同步状态

核心逻辑：
```python
def get_active_stocks() -> set[str]:
    """获取所有活跃股票（未退市）"""
    session = get_session()
    stocks = session.query(Stock.symbol).filter(
        Stock.is_delisted == False
    ).all()
    return {s[0] for s in stocks}

@router.post("/api/data/sync-daily-klines")
async def sync_daily_klines(request: KlineSyncRequest):
    symbols = get_active_stocks()
    backfill_tasks = {
        symbol: [{'start': sync_date, 'end': sync_date, 'days': 1}]
        for symbol in symbols
    }
    result = backfiller.backfill_batch(
        backfill_tasks=backfill_tasks,
        max_workers=10,
        max_retries=3
    )
    return KlineSyncResponse(...)
```

返回字段：
- `success`: bool（成功率 ≥80%）
- `sync_date`: 同步日期
- `success_count`: 成功股票数
- `failed_count`: 失败股票数
- `total_stocks`: 总股票数
- `total_rows`: 同步数据条数
- `elapsed_time`: 耗时（秒）
- `failed_symbols`: 失败股票列表（前20）

**路由注册：`quantsys-v2/adapters/inbound/fastapi_app/main.py`**
```python
from adapters.inbound.fastapi_app.routes.data_sync_async import router as data_sync_router
app.include_router(data_sync_router)
```

#### 2. quantsys-v2-client 新增方法（✅ 完成）

**文件：`quantsys-v2-client/src/client.ts`**

```typescript
async syncDailyKlines(params?: { date?: string }): Promise<{
  success: boolean;
  sync_date: string;
  success_count: number;
  failed_count: number;
  total_stocks: number;
  total_rows: number;
  elapsed_time: number;
  message: string;
  failed_symbols?: string[];
}>

async getDataSyncStatus(): Promise<{
  status: string;
  latest_date: string | null;
  latest_count?: number;
  active_stocks_count?: number;
  coverage?: string;
  message: string;
}>
```

#### 3. agent-dh data-manager 插件新增工具（✅ 完成）

**文件：`agent-dh/packages/data-manager/src/index.ts`**

新工具：`kline_daily_sync`

```typescript
ctx.tools.register(defineTool({
  name: 'kline_daily_sync',
  description: '执行每日K线同步：调用 quantsys-v2 业务逻辑同步指定日期所有活跃股票的K线数据',
  parameters: {
    date: { 
      type: 'string', 
      description: '同步日期 YYYY-MM-DD（默认昨日）' 
    }
  },
  timeoutMs: 300000, // 5分钟
  execute: async (args) => {
    return await qv2.syncDailyKlines({ date: args.date });
  }
}));
```

#### 4. 更新 Agent OS reminder（待执行）

当前 reminder `5a0b9df8` 的 prompt 是文字描述，需要改为**直接调用工具**：

**旧 prompt（文字描述，agent 需要理解）：**
```
每日K线数据同步（临时方案）
- 同步昨日所有活跃股票的K线数据
- 检查同步结果，失败率 >20% 时告警
```

**新 prompt（直接调用工具）：**
```
执行每日K线同步任务：

1. 调用 kline_daily_sync 工具同步昨日数据
2. 检查结果：
   - success=true 且 success_count ≥ 4000：成功，记录日志
   - 否则：飞书告警，附带失败详情
3. 将结果写入 memory（namespace=operation, tags=[data-sync, kline]）
```

## 数据流

```
Agent OS Scheduler (21:00 工作日)
  ↓ 触发 reminder
Agent Session (investor)
  ↓ 收到提醒消息
调用 kline_daily_sync 工具
  ↓ HTTP POST
quantsys-v2 API (:5001/api/data/sync-daily-klines)
  ↓ 调用业务逻辑
DataBackfiller.backfill_batch()
  ↓ 批量请求
eastmoney / akshare 数据源
  ↓ 写入数据库
PostgreSQL quant.daily_klines 表
```

## 优势

1. **标准化接口**：HTTP API 解耦，可被多个客户端调用
2. **可追踪**：Agent-DH 工具有结构化返回，便于监控
3. **可测试**：可以手动调用工具验证，不依赖 reminder 触发
4. **容错**：API 失败返回明确错误，agent 可根据错误决策
5. **复用**：quantsys-v2 业务逻辑（DataBackfiller）被复用，无需重写

## 待执行任务

### 1. 重启 quantsys-v2 加载新 API（⚠️ 必须）

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
pkill -f "uvicorn.*main:app"
sleep 2
python adapters/inbound/fastapi_app/main.py
```

验证：
```bash
curl -X POST http://localhost:5001/api/data/sync-daily-klines \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-08-28"}'
```

### 2. 重启 DSH 加载新工具（⚠️ 必须）

```bash
cd ~/.dsh/profiles/investment
./stop.sh
./start.sh 13080
```

验证：访问 http://localhost:13080，工具列表中应出现 `kline_daily_sync`

### 3. 更新 reminder prompt（⚠️ 必须）

使用 `reminder_list` 查看当前 reminder，然后删除旧的，创建新的（或者通过工具更新）。

### 4. 测试完整链路（⚠️ 验收必需）

手动触发同步：
```typescript
// 在 DSH 会话中执行
kline_daily_sync({ date: '2026-08-29' })
```

预期结果：
- `success: true`
- `success_count ≥ 4000`（活跃股票约 5532 只，80% = 4426）
- `total_rows ≥ 4000`

### 5. 明天验收（2026-08-29）

**21:00 自动触发**：
- reminder 应触发 agent 调用 `kline_daily_sync`
- 检查数据库：`SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date = '2026-08-29'`
- 预期 ≥4500 条

**16:00 手动验证**：
- 查看 reminder 执行日志
- 检查是否有飞书告警

## 备用方案（Bash 脚本）

如果 HTTP API 方案有问题，已准备好 Bash 脚本兜底：

**文件：`quantsys-v2/scripts/daily_sync_klines.sh`**
- 激活 Python 环境
- 调用 `sync_daily_klines_incremental.py`
- 可直接从 cron 或 reminder 调用

## 文件清单

### 新增文件
1. `quantsys-v2/adapters/inbound/fastapi_app/routes/data_sync_async.py` - 同步 API
2. `quantsys-v2/scripts/sync_daily_klines_incremental.py` - 增量同步脚本
3. `quantsys-v2/scripts/daily_sync_klines.sh` - Bash 包装脚本（备用）

### 修改文件
1. `quantsys-v2/adapters/inbound/fastapi_app/main.py` - 注册新路由
2. `quantsys-v2-client/src/client.ts` - 新增 syncDailyKlines 方法
3. `agent-dh/packages/data-manager/src/index.ts` - 新增 kline_daily_sync 工具

## 技术亮点

1. **分层清晰**：OS调度 → Agent工具 → HTTP API → 业务逻辑，各层职责明确
2. **向下兼容**：保留 Bash 脚本，可在 API 故障时快速降级
3. **业务复用**：DataBackfiller 类不变，通过 HTTP 暴露能力
4. **可观测性**：每层都有结构化返回，便于追踪和调试

---

**创建时间**：2026-08-29 00:35  
**实施人员**：Claude (ccvibe-4-8)  
**状态**：代码已完成，待重启服务验证
