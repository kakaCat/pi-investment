# Database Cursor Issues Report

生成时间: 2026-06-24

## 问题总结

在项目中发现了两类数据库游标使用问题：

### 1. @paginate 装饰器参数传递问题
- **已修复**: `quantsys-v2/adapters/inbound/api/routes/scheduler.py`
- 4个端点已添加 `*` 强制关键字参数

### 2. conn.cursor() 未指定 cursor_factory 问题

发现 **48个文件** 存在潜在的 `conn.cursor()` 调用问题，可能导致返回元组而不是字典。

## 已修复文件

### 高优先级（核心功能）
✅ `infrastructure/scheduler/scheduler.py` - 14处已修复
✅ `adapters/inbound/api/routes/scheduler.py` - 4个端点函数签名已修复
✅ `live_trading/simulation_repository.py` - 8处已修复

## 待修复文件

### 中优先级（实时交易和服务）

1. **live_trading/simulation_trader.py** (2处)
   - Line 190: `cursor = self.repo.conn.cursor()`
   - Line 249: `cursor = self.repo.conn.cursor()`
   - 状态: 该文件有兼容代码处理元组/字典两种情况，暂不紧急

2. **application/services/experience_accumulator.py** (2处)
   - Line 144: `cursor = conn.cursor()`
   - Line 289: `cursor = conn.cursor()`
   - 访问方式: 使用索引访问 `result[0]`, `result[1]`
   - 状态: 当前工作正常，但应统一使用字典访问

### 低优先级（脚本工具）

以下文件主要是训练脚本和批处理工具，不影响API服务：

**训练脚本 (4处)**
- `scripts/train_ml_v5_fundamental.py`
- `scripts/train_ml_v2_enhanced.py`
- `scripts/train_ml_v3_fixed.py`
- `scripts/train_ml_v4_rolling.py`

**回测脚本 (2处)**
- `scripts/backtest_ml_v6_strategy_best.py`
- `scripts/backtest_ml_v6_strategy_aggressive_v8.py`
- `scripts/backtest_ml_v6_strategy_final.py`
- `scripts/backtest_ml_v6_strategy_diversified_v14.py`

**数据导入/更新脚本 (1-2处)**
- `scripts/robust_import_klines.py`
- `scripts/backfill_stocks.py`
- `scripts/update_recent_klines_direct.py`
- `scripts/init_stocks.py`
- `scripts/import_hs300_klines.py`
- `scripts/compute_factors.py`
- `scripts/compute_factors_v2.py`
- `scripts/batch_update_klines.py`
- `scripts/batch_import_minute_klines.py`
- `scripts/import_klines_to_pg.py`
- `scripts/update_klines_multi_source.py`

**其他脚本** (共约40个文件)
- 各种迁移脚本、初始化脚本、测试脚本

## 修复建议

### 立即修复
1. ✅ 核心API路由 - 已完成
2. ✅ Scheduler服务 - 已完成
3. ✅ Simulation Repository - 已完成

### 后续修复
1. **simulation_trader.py** - 添加 RealDictCursor 使用，移除兼容代码
2. **experience_accumulator.py** - 统一使用字典访问而非索引访问

### 批量修复（可选）
对于scripts目录下的脚本，可以：
- 选项A: 保持现状（如果使用索引访问且工作正常）
- 选项B: 批量添加 cursor_factory=RealDictCursor 并改为字典访问（更好的可维护性）

## 修复模式

### 模式1: 直接指定 cursor_factory（推荐）
```python
from psycopg2.extras import RealDictCursor

cursor = conn.cursor(cursor_factory=RealDictCursor)
row = cursor.fetchone()
value = row["column_name"]  # 字典访问
```

### 模式2: 设置连接默认（已在_get_conn中设置）
```python
conn.cursor_factory = RealDictCursor
cursor = conn.cursor()  # 继承 cursor_factory
```

## 测试验证

已验证修复的功能：
- ✅ GET /api/scheduler/tasks?page=1&pageSize=12 - 正常返回
- ✅ 返回数据结构正确，包含18个任务
- ✅ 分页功能正常

## 风险评估

| 文件类型 | 风险等级 | 影响范围 | 修复状态 |
|---------|---------|---------|---------|
| API Routes | 🔴 高 | Web前端功能 | ✅ 已修复 |
| Scheduler Service | 🔴 高 | 定时任务系统 | ✅ 已修复 |
| Live Trading | 🟡 中 | 实时交易模拟 | ⚠️ 部分修复 |
| Scripts | 🟢 低 | 离线工具 | ⏸️ 待定 |

## 总结

- **已修复**: 核心API和Scheduler服务的26处问题
- **部分修复**: Live trading相关的8处问题
- **待修复**: Scripts目录约40个文件的问题（低优先级）
- **当前状态**: 主要API服务已正常运行
