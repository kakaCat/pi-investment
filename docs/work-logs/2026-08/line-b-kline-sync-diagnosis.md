# 线B地基修复：K线同步管线诊断报告

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-28 01:35 |
| 诊断方 | agent-dh k3（审计+文档） |
| 问题级别 | 🔴 P0（阻塞 M1/M3/M7/M8 所有数据依赖模块） |

---

## 问题现象

### 数据断崖

| 日期 | K线记录数 | 覆盖率 | 状态 |
|---|---|---|---|
| 活跃股票总数 | — | — | 5532 只 |
| 2026-08-24 | 4961 | 90% | ✅ 正常 |
| 2026-08-25 | 5274 | 95% | ✅ 正常 |
| **2026-08-26** | **1062** | **19%** | ❌ 断崖 |
| **2026-08-27** | **384** | **7%** | ❌ 崩溃 |

### 影响范围

1. **M1 市场感知**：
   - sentiment_daily coverage=6（08-27 快照），情绪分/regime 失真
   - 15:30 snapshot 读到的是残缺数据 → 输出垃圾结论

2. **M3 信号择时**：
   - 策略回测依赖 daily_klines → 08-26/27 数据缺失导致回测失败或信号错误

3. **M7 对手行为**：
   - opponent_behavior 依赖完整市场宽度 → 08-26/27 无法判断散户/机构情绪

4. **M8 预测引擎**：
   - model_predict 输入缺失 → 预测失效

---

## 根因诊断

### 1. K线同步任务完全缺失

**检查结果**：
- ✅ Agent OS reminder 列表（6个任务）：**无 K线同步任务**
- ✅ 运行中进程：**无数据同步进程**
- ✅ quantsys-v2/scripts：有 `w1_backfill_klines.py`（回填脚本），**无 daily_sync**

**结论**：08-24/25 的数据是历史一次性导入，08-26/27 因无自动同步任务而断崖。

### 2. quantsys-v2 废弃后的迁移缺口

quantsys-v2 曾经的数据同步服务（如有）未迁移到新架构（Agent OS + DSH）：
- 旧架构可能有 cron/systemd 定时任务或 Flask 内置 scheduler
- 废弃时未建立替代方案
- daily_klines 表成为"只读历史数据"，无增量更新

### 3. 数据采集能力本身存在

- `w1_backfill_klines.py` 证明 quantsys-v2 有 K线采集能力（通过 DataBackfiller）
- quant.stocks 表有 5532 只活跃股票
- 08-24/25 数据质量正常 → 数据源和采集逻辑可用

**缺的是自动化调度**，不是采集能力。

---

## 修复方案

### 短期（P0，今明两天）：手动回填 + 临时调度

#### Step 1：手动回填 08-26/27

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh  # 或对应的 venv

# 回填 08-26
python scripts/w1_backfill_klines.py --start-date 2026-08-26 --end-date 2026-08-26

# 回填 08-27
python scripts/w1_backfill_klines.py --start-date 2026-08-27 --end-date 2026-08-27

# 验证
psql quant_investment -c "SELECT trade_date, COUNT(*) FROM quant.daily_klines WHERE trade_date >= '2026-08-26' GROUP BY trade_date ORDER BY trade_date;"
```

#### Step 2：挂载临时每日同步任务

通过 Agent OS reminder 每晚 21:00 触发回填脚本（给数据源同步留 6 小时缓冲）：

```javascript
// 在 DSH Web UI (localhost:13080) 执行
reminder_create({
  name: "daily-kline-sync",
  cron: "0 0 21 * * 1-5",  // 工作日 21:00
  prompt: "执行 K线每日同步：cd /Users/yunpeng/pi-investment/quantsys-v2 && source activate-py313.sh && python scripts/w1_backfill_klines.py --start-date $(date +%Y-%m-%d) --end-date $(date +%Y-%m-%d)。完成后汇报同步股票数和任何异常。",
  window: "w-6807aa37"
})
```

**注意**：这是临时方案，因为 reminder prompt 调用 bash 脚本可能失败（DSH agent 执行环境限制）。

### 中期（P1，本周内）：实现专用数据同步插件

创建 `@pi-investment/data-sync` 插件，提供工具：

#### 工具设计

```typescript
// 1. 手动触发同步
sync_daily_klines({
  date: "2026-08-28",  // 可选，默认今天
  symbols: ["600519", ...],  // 可选，默认全市场
})

// 2. 查看同步状态
sync_status({
  recent_days: 7
})
// 返回：每日同步股票数、缺失日期、上次同步时间
```

#### 实现要点

- 调用 quantsys-v2 的 DataBackfiller（虽然 quantsys-v2 废弃，但数据采集逻辑复用）
- 或直接调用数据源 API（akshare/tushare/eastmoney）
- 失败降级：akshare 限流时切换数据源
- 增量同步：只拉取缺失日期，避免重复

#### 挂载调度

```javascript
reminder_create({
  name: "daily-kline-sync-tool",
  cron: "0 0 21 * * 1-5",
  prompt: "调用 sync_daily_klines() 同步今日 K线，完成后调用 sync_status({recent_days:3}) 确认覆盖率",
  window: "w-6807aa37"
})
```

### 长期（P2，后续优化）：数据湖架构

将 daily_klines 从 PostgreSQL 迁移到专门的时序数据库（如 TimescaleDB/InfluxDB），或对象存储（Parquet 文件）：
- 提升查询性能（当前单表 >100万行）
- 降低 PG 存储压力
- 支持更长历史回测（当前只保留近期）

---

## 验收标准（短期方案）

1. **回填验证**：
   ```sql
   SELECT trade_date, COUNT(*) 
   FROM quant.daily_klines 
   WHERE trade_date >= '2026-08-26' 
   GROUP BY trade_date 
   ORDER BY trade_date;
   ```
   预期：08-26/27 各有 ≥4500 条记录

2. **调度验证**（挂载后次日 21:00）：
   - 检查 reminder 最近触发时间
   - 验证当日 K线自动写入

3. **下游修复确认**：
   - M1 sentiment_daily coverage 恢复到 >4000
   - M3 策略回测不再因数据缺失报错

---

## 当前状态

| 项 | 状态 |
|---|---|
| 根因诊断 | ✅ 完成（同步任务缺失） |
| 短期方案 Step 1（手动回填） | 🟡 **等执行**（需 quantsys-v2 Python 环境） |
| 短期方案 Step 2（挂临时 reminder） | 🟡 **等 Step 1 验证后挂载** |
| 中期方案（data-sync 插件） | 📋 设计完成，等实施 |

---

## 下一步

**立即（我）**：
1. 执行 Step 1 手动回填（如果 quantsys-v2 Python 环境可用）
2. 验证回填结果
3. 挂载 Step 2 临时 reminder

**本周（实施窗口）**：
4. 实现 `@pi-investment/data-sync` 插件
5. 替换临时 reminder 为正式工具调度

**验收（我）**：
6. 连续 3 个交易日自动同步验证（覆盖率 ≥90%）
