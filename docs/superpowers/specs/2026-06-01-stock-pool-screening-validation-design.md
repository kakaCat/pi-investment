# 股票池筛选与策略验证设计文档

**日期**: 2026-06-01  
**状态**: 设计完成，待实施  
**方案**: 轻量扩展（方案 A）

## 概述

实现"筛选 → 股票池 → 策略验证"完整链路，补齐 quantsys-v2 中缺失的自定义股票池管理和策略对比验证能力。

### 需求摘要

| 维度 | 决策 |
|------|------|
| 筛选条件 | 综合多因子（技术面+基本面+资金面）+ 灵活可配置 |
| 池子类型 | 混合模式：静态池（手动锁定）+ 动态池（定时刷新） |
| 验证方式 | 批量对比验证：多策略 × 同一池子，横向对比排名 |
| 结果使用 | 自动推荐：系统选出最优策略 + 股票组合 |
| 筛选范围 | 固定宇宙：沪深300 + 创业板50 + 科创50（~400只） |

### 现有能力复用

- **筛选引擎**: 复用 `OpportunityScoringService.score_stocks()`，已支持技术面+基本面+资金面多因子评分
- **批量回测**: 复用 `POST /api/backtest/batch`，已支持 strategy×symbol 笛卡尔积并行回测
- **评分公式**: 复用现有综合评分 `return*0.4 + sharpe*0.2 + drawdown*0.15 + win_rate*0.15 + profit_factor*0.1`
- **股票宇宙**: 复用 `StockPoolService.get_hot_stocks()` 获取筛选范围

### 需要新建

- `stock_pools` 数据库表
- `StockPoolRepository` 数据访问层
- `StockPoolService` 扩展 CRUD + 动态刷新
- `PoolValidationService` 策略验证编排
- `pools.py` API 路由
- `pool-manage-tool.ts` + `pool-validate-tool.ts` Agent 工具
- `quant-v2-client.ts` 扩展 pool 相关方法

---

## 数据模型

### stock_pools 表

```sql
CREATE TABLE quant.stock_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,           -- 池子名称，如"低估值蓝筹池"
    pool_type VARCHAR(10) NOT NULL,       -- 'static' | 'dynamic'
    description TEXT,                     -- 描述
    symbols TEXT[] NOT NULL,              -- 当前成员 ['600519.SH', '000858.SZ', ...]
    
    -- 动态池专用：保存筛选条件，定时刷新时重新执行
    filter_template JSONB,               -- 筛选条件模板
    refresh_interval VARCHAR(20),        -- 刷新周期: 'daily' | 'weekly' | null(静态池)
    last_refreshed_at TIMESTAMP,         -- 上次刷新时间
    
    -- 验证结果快照
    last_validation JSONB,               -- 最近一次策略验证的汇总结果
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### filter_template 结构

```json
{
  "min_score": 60,
  "max_risk_level": "medium",
  "technical": ["rsi_oversold", "macd_golden_cross"],
  "fundamental": ["pe_low", "roe_high"],
  "top_n": 20
}
```

直接复用 `POST /api/signals/scan` 的请求参数格式，无需新的 DSL。

### last_validation 结构

```json
{
  "validated_at": "2026-06-01T10:00:00",
  "strategies_tested": 3,
  "best_strategy": {
    "id": 53,
    "name": "多因子波段策略v9",
    "score": 82.5,
    "avg_return": 12.3,
    "win_rate": 68.5,
    "sharpe": 1.85
  },
  "rankings": [
    { "strategy_id": 53, "name": "多因子波段策略v9", "score": 82.5, "avg_return": 12.3, "win_rate": 68.5, "sharpe": 1.85 },
    { "strategy_id": 54, "name": "RSI超买超卖策略", "score": 71.2, "avg_return": 8.1, "win_rate": 62.0, "sharpe": 1.42 },
    { "strategy_id": 55, "name": "均线突破策略", "score": 65.8, "avg_return": 6.5, "win_rate": 58.3, "sharpe": 1.15 }
  ],
  "recommended_pairs": [
    { "strategy_id": 53, "symbol": "600519.SH", "name": "贵州茅台", "expected_return": 15.2, "win_rate": 72.0 },
    { "strategy_id": 53, "symbol": "000858.SZ", "name": "五粮液", "expected_return": 13.8, "win_rate": 69.5 }
  ]
}
```

---

## 服务层

### StockPoolService 扩展

在现有 `quantsys-v2/services/stock_pool_service.py` 基础上扩展：

| 方法 | 功能 | 说明 |
|------|------|------|
| `create_pool(name, pool_type, symbols, filter_template?, refresh_interval?, description?)` | 创建池子 | static 池需提供 symbols；dynamic 池需提供 filter_template |
| `update_pool(pool_id, symbols?, name?, description?)` | 更新池子 | 支持部分更新 |
| `delete_pool(pool_id)` | 删除池子 | 同时移除定时任务（如果是动态池） |
| `get_pool(pool_id)` | 获取单个池子 | 含 symbols 和 last_validation |
| `list_pools()` | 列出所有池子 | 返回摘要信息（不含完整 symbols） |
| `refresh_pool(pool_id)` | 刷新动态池 | 用 filter_template 调用 OpportunityScoringService，更新 symbols |
| `create_from_scan(name, pool_type, scan_params, refresh_interval?)` | 筛选建池一步完成 | 执行扫描 → 取结果 symbols → 创建池子 |

**保留现有方法不变**：`get_hot_stocks()`、`get_scan_universe()` 继续正常工作。

### PoolValidationService（新建）

```
quantsys-v2/services/pool_validation_service.py
```

核心编排逻辑：

```python
class PoolValidationService:
    def validate_pool(self, pool_id: int, strategy_ids: list[int] = None,
                      start_date: str = None, end_date: str = None) -> dict:
        """
        批量对比验证流程：
        1. 读取池子 symbols
        2. 若 strategy_ids 为空，加载所有 active 策略
        3. 构建 jobs = strategy × symbol 笛卡尔积
        4. 调用 BacktestService.batch_backtest(jobs)
        5. 按策略聚合：计算每个策略在池内所有股票的平均指标
           - 平均年化收益率
           - 平均胜率
           - 平均夏普比率
           - 平均最大回撤
           - 平均盈亏比
        6. 综合评分排名
           score = return*0.4 + sharpe*0.2 + drawdown*0.15 + win_rate*0.15 + profit_factor*0.1
        7. 选出 best_strategy + recommended_pairs（每个策略×股票的最优组合 top N）
        8. 写回 pool.last_validation
        9. 返回完整排名 + 推荐结果
        """
```

**默认时间范围**：`start_date` 默认近 6 个月，`end_date` 默认当天。

**recommended_pairs 选取规则**：从最优策略的所有股票回测结果中，取综合评分 top 5 的股票组合。

---

## API 端点

### 股票池 CRUD

| 方法 | 路径 | 功能 | 请求体 |
|------|------|------|--------|
| `POST` | `/api/pools` | 创建池子 | `{ name, pool_type, symbols?, filter_template?, refresh_interval?, description? }` |
| `GET` | `/api/pools` | 列出所有池子 | — |
| `GET` | `/api/pools/:id` | 获取池子详情 | — |
| `PUT` | `/api/pools/:id` | 更新池子 | `{ name?, symbols?, description? }` |
| `DELETE` | `/api/pools/:id` | 删除池子 | — |

### 池子操作

| 方法 | 路径 | 功能 | 请求体 |
|------|------|------|--------|
| `POST` | `/api/pools/:id/refresh` | 手动刷新动态池 | — |
| `POST` | `/api/pools/:id/validate` | 执行策略验证 | `{ strategy_ids?, start_date?, end_date? }` |
| `POST` | `/api/pools/scan-and-create` | 筛选+建池一步完成 | `{ name, pool_type, filter, refresh_interval? }` |

### 响应格式

**POST /api/pools/scan-and-create 响应：**
```json
{
  "success": true,
  "pool": {
    "id": 1,
    "name": "低估值蓝筹池",
    "pool_type": "dynamic",
    "symbols": ["600519.SH", "000858.SZ", "..."],
    "count": 18,
    "refresh_interval": "weekly",
    "filter_template": { "..." }
  }
}
```

**POST /api/pools/:id/validate 响应：**
```json
{
  "success": true,
  "pool_id": 1,
  "pool_name": "低估值蓝筹池",
  "period": { "start": "2025-12-01", "end": "2026-06-01" },
  "strategies_tested": 3,
  "stocks_in_pool": 18,
  "best_strategy": {
    "id": 53,
    "name": "多因子波段策略v9",
    "score": 82.5,
    "avg_return": 12.3,
    "win_rate": 68.5,
    "sharpe": 1.85
  },
  "rankings": ["..."],
  "recommended_pairs": ["..."]
}
```

---

## Agent 工具

### pool_manage — 股票池管理

```
文件: src/infrastructure/tools/pool/pool-manage-tool.ts
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `action` | `"create" \| "list" \| "get" \| "update" \| "delete" \| "refresh" \| "scan_create"` | 操作类型 |
| `pool_id` | `number` | get/update/delete/refresh 需要 |
| `name` | `string` | create/scan_create 需要 |
| `pool_type` | `"static" \| "dynamic"` | create/scan_create 需要 |
| `symbols` | `string[]` | create(static) 手动指定成员 |
| `filter` | `object` | scan_create/create(dynamic) 筛选条件 |
| `refresh_interval` | `"daily" \| "weekly"` | 动态池刷新周期 |
| `description` | `string` | 池子描述 |

### pool_validate — 策略验证

```
文件: src/infrastructure/tools/pool/pool-validate-tool.ts
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `pool_id` | `number` | 必需，目标池子 |
| `strategy_ids` | `number[]` | 可选，为空则用所有 active 策略 |
| `start_date` | `string` | 可选，默认近6个月 |
| `end_date` | `string` | 可选，默认今天 |

### Agent 使用流程示例

用户说"帮我筛选低估值高分红的股票，然后看看哪个策略最好"：

```
Step 1: pool_manage({
  action: "scan_create",
  name: "低估值高分红池",
  pool_type: "dynamic",
  filter: { fundamental: ["pe_low", "roe_high"], min_score: 60, top_n: 20 },
  refresh_interval: "weekly"
})
→ 返回 pool_id: 1, 入池 18 只股票

Step 2: pool_validate({ pool_id: 1 })
→ 返回: 策略53(多因子波段v9)最优，评分82.5
  推荐组合: 600519+策略53(预期15.2%), 000858+策略53(预期13.8%)...

Step 3: Agent 整理为结构化表格呈现给用户
```

---

## 动态池定时刷新

### 实现方式

复用 quantsys-v2 已有的 APScheduler 基础设施：

- **注册时机**: 创建动态池时，在 APScheduler 中注册定时任务
- **执行逻辑**: 定时调用 `StockPoolService.refresh_pool(pool_id)`
- **刷新频率**:
  - `daily`: 每个交易日 09:00 执行
  - `weekly`: 每周一 09:00 执行
- **服务启动恢复**: 服务启动时查询所有 `pool_type='dynamic'` 的池子，恢复定时任务
- **删除联动**: 删除动态池时同步移除定时任务

### 刷新流程

```
定时触发 → 读取 pool.filter_template
         → 调用 OpportunityScoringService.score_stocks(hot_stocks, filters)
         → 排序取 top_n
         → 更新 pool.symbols + pool.last_refreshed_at
```

---

## 文件组织

### Python 后端（quantsys-v2）

```
quantsys-v2/
├── migrations/
│   └── add_stock_pools_table.sql          # 新建：建表 DDL
├── repositories/
│   └── stock_pool_repository.py           # 新建：CRUD 数据访问
├── services/
│   ├── stock_pool_service.py              # 扩展：增加 CRUD + refresh + create_from_scan
│   └── pool_validation_service.py         # 新建：策略验证编排
├── api/routes/
│   └── pools.py                           # 新建：API 路由
```

### TypeScript Agent

```
src/infrastructure/
├── tools/pool/
│   ├── pool-manage-tool.ts                # 新建：池子管理工具
│   └── pool-validate-tool.ts              # 新建：策略验证工具
├── quant/
│   └── quant-v2-client.ts                 # 扩展：增加 pool 相关 API 调用方法
```

---

## 约束和限制

- **筛选范围固定**: 仅从沪深300 + 创业板50 + 科创50（~400只）中筛选，不支持全市场
- **筛选条件**: 复用现有 OpportunityScoringService 支持的维度，不新增 DSL
- **回测性能**: 批量回测使用 ThreadPoolExecutor(max_workers=10)，400只×5个策略 = 2000 个 job，预计 5-10 分钟
- **数据依赖**: 筛选和回测依赖数据库中有足够的历史 K 线数据
- **服务依赖**: 需要 quantsys-v2 REST API (5001) 运行中
