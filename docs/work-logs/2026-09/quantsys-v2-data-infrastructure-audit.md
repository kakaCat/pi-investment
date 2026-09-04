# quantsys-v2 基础数据审计报告

**日期**: 2026-09-03  
**审计范围**: quantsys-v2 基础数据表、数据完整性、更新任务状态  
**数据库**: quant_investment (PostgreSQL)

---

## 执行摘要

quantsys-v2 基础数据基础设施整体**健康**，核心数据表已就位并持续更新。发现以下关键情况：

✅ **正常**:
- K线数据覆盖完整（458万+记录，5699只股票，最新至2026-09-02）
- 股票池活跃（5542只，退市324只）
- 筹码分布持续更新（57719条，最新2026-09-02）
- 资金流数据稳定（34133条，6425只股票）

⚠️ **待改进**:
- 财务报表数据过时（最新仅至2026-03-31，应有2026-06-30中报）
- 数据质量监控未持续运行（最近7天无新检查记录）
- 数据架构存在双schema隔离（public vs quant），ORM模型位置分散

---

## 一、核心数据表现状

### 1.1 数据表清单

#### quant schema（业务数据）

| 表名 | 记录数 | 独立symbol数 | 最新日期 | 存储大小 | 状态 |
|------|--------|-------------|----------|----------|------|
| **daily_klines** | 4,586,885 | 5,699 | 2026-09-02 | 1017 MB | ✅ 正常 |
| **stocks** | 5,866 | - | - | 4.7 MB | ✅ 正常 |
| **stock_fund_flow** | 34,133 | 6,425 | 2026-09-03 | 8.8 MB | ✅ 正常 |
| **chip_metrics** | 57,719 | 5,689 | 2026-09-02 | 12 MB | ✅ 正常 |
| **balance_sheets** | 1,200 | 300 | 2026-03-31 | 296 KB | ⚠️ 过时 |
| **cash_flows** | - | - | - | 272 KB | ⚠️ 待查 |

#### public schema（监控/元数据）

| 表名 | 用途 | 状态 |
|------|------|------|
| **kline_data_quality** | K线质量监控 | ⚠️ 未持续运行 |
| **data_quality_stats** | 数据质量统计 | - |
| **factor_data** | 因子数据 | - |
| **strategy_signals** | 策略信号 | - |
| **evolution_runs** | 进化实验 | - |

### 1.2 K线数据详情

```
总记录数: 4,586,885
独立股票: 5,699只
时间跨度: 1994-03-01 至 2026-09-02
2026年交易日: 197天 (2026-01-05 至 2026-09-02)
```

**最近10日数据量**:
```
2026-09-02: 5,279条 (5,279只股票)
2026-09-01: 5,278条
2026-08-31: 5,278条
2026-08-30: 10条   ⚠️ 周末数据异常
2026-08-29: 10条   ⚠️ 周末数据异常
2026-08-28: 5,315条
```

**重点股票覆盖**（抽样检查）:
- 600519（贵州茅台）: 1035条，2022-06-01至今
- 600036（招商银行）: 1035条，2022-06-01至今
- 000858（五粮液）: 1035条，2022-06-01至今
- 000001（平安银行）: 495条，2023-05-26至今

### 1.3 股票主表

```
总股票数: 5,866只
活跃股票: 5,542只
已退市: 324只
上海交易所: 2,464只 (6xxxxx)
深圳交易所: 3,079只 (0xxxxx, 3xxxxx)
```

### 1.4 财务数据

**⚠️ 关键发现: 财务报表数据过时**

```
balance_sheets:
  记录数: 1,200条
  覆盖股票: 300只
  最新报告期: 2026-03-31 (Q1季报)
  
预期: 应有2026-06-30 (Q2中报)
差距: 落后2个月+
```

**影响**:
- 基本面筛选器使用过时数据
- ROE/净利润增速等指标不准确
- 动态股票池质量受影响

### 1.5 资金流数据

```
总记录数: 34,133条
覆盖股票: 6,425只
时间跨度: 2025-12-04 至 2026-09-03
状态: ✅ 每日更新正常
```

### 1.6 筹码分布数据

```
总记录数: 57,719条
覆盖股票: 5,689只
最新更新: 2026-09-02 21:10:25
状态: ✅ 每日更新正常
```

---

## 二、数据质量监控

### 2.1 kline_data_quality 表

**表结构**: ✅ 完整（21个字段）
- 清洗统计: original_count, cleaned_count, removed_count, fixed_count
- 质量评分: completeness_score, consistency_score, accuracy_score, overall_score
- 分级: grade (A+/A/B/C/D)
- 问题追踪: errors_json, warnings_json, cleaning_operations_json

**最近记录**:
```
最后5条检查记录日期: 2026-06-24
距今: 2个月+

最近7天检查数: 0条
状态: ⚠️ 数据质量监控未持续运行
```

**历史质量分布**（2026-06-24前）:
- 所有检查记录均为 A+ 级别
- overall_score: 99.5-100
- 主要警告: 成交量异常放大（正常市场行为）

### 2.2 数据更新任务状态

**调度系统**: quant.scheduler_tasks

需要进一步检查:
- kline_update_job 最后运行时间
- financial_data_update_job 是否启用
- chip_distribution_update_job 运行频率
- fund_flow_update_job 运行状态

---

## 三、架构问题

### 3.1 双Schema隔离

**现状**:
- `quant` schema: 业务数据（klines, stocks, financial, etc.）
- `public` schema: 监控/元数据（quality, evolution, signals, etc.）

**影响**:
- SQL查询需明确schema前缀
- ORM模型需正确配置 `__table_args__`
- 跨schema JOIN复杂度增加

**建议**: 保持现状，已是合理的逻辑分层。确保Repository层正确封装schema差异。

### 3.2 ORM模型分散

**当前位置**:
```
infrastructure/persistence/orm/models/  (主ORM模型，应该在这里)
adapters/outbound/repositories/models/  (部分模型，混乱)
domain/models/                          (领域模型，正确)
```

**问题**: 
- ORM模型应统一放在 `infrastructure/persistence/orm/models/`
- `adapters/outbound/repositories/models/` 应仅包含Repository辅助类
- 当前存在 `kline_data_quality.py`、`strategy_execution.py` 等ORM模型散落

**建议**: 执行ORM模型迁移，统一到 infrastructure 层。

### 3.3 数据表缺失

未找到以下预期表的ORM模型或记录:
- ❓ `financial_statements` (可能已拆分为 balance_sheets + cash_flows + income_statements)
- ❓ `income_statements` (未确认是否存在)
- ❓ `index_constituents` (指数成分股，scheduler有seed job但未确认表)

---

## 四、数据源架构

### 4.1 多数据源抽象层

**位置**: `adapters/outbound/datasources/`

**核心组件**:
- `manager.py` - 数据源管理器
- `base.py` - 基础抽象类
- `circuit_breaker.py` - 熔断器（反IP封禁）
- `cache.py` - 缓存层
- `monitoring.py` - 监控

**Provider实现**:
```
providers/
├── kline/
│   ├── tencent.py
│   ├── baostock.py
│   └── akshare.py
├── market/
│   └── akshare.py
├── stock/
│   └── akshare.py
└── quantlib/
    ├── sina_adapter.py
    └── eastmoney_adapter.py
```

**反封禁策略**（参考记忆：kline-anti-ban-architecture）:
- baostock 网络首选源 + 限速 uniform(0.3, 0.8)s
- 降级链: database → baostock → tencent → akshare
- circuit_breaker 持久化失败记录

### 4.2 Repository层

**位置**: `adapters/outbound/repositories/`

**核心Repository**:
- `kline_repository.py` - ✅ 已完成ORM迁移（Polars兼容层）
- `stock_repository.py` - ✅ ORM迁移
- `stock_async_repository.py` - 异步版本
- `financial_repository.py` - 财务数据
- `financial_async_repository.py` - 异步版本
- `fund_flow_repository.py` - 资金流
- `stock_pool_repository.py` - 股票池

**架构特点**:
- 实现 `domain.ports.I*Repository` 接口（DDD 依赖倒置）
- 继承 `BaseORMRepository` (SQLAlchemy)
- 返回 Polars DataFrame（性能优化）
- 显式schema避免类型推断问题（参考kline_repository.py:37）

---

## 五、数据更新任务

### 5.1 调度Job文件

**位置**: `infrastructure/jobs/`

| Job文件 | 用途 | 预期频率 |
|---------|------|---------|
| `kline_update_job.py` | K线更新 | 每日 17:40 |
| `financial_data_update_job.py` | 财务报表 | 每周六 20:00 |
| `chip_distribution_update_job.py` | 筹码分布 | 每日 |
| `fund_flow_update_job.py` | 资金流 | 每日 |
| `data_quality_check_job.py` | 数据质量检查 | 需确认 |

### 5.2 调度系统状态

**需要执行**:
```sql
-- 检查调度任务注册状态
SELECT name, is_enabled, last_run_time, cron_expression
FROM quant.scheduler_tasks
WHERE name LIKE '%kline%' 
   OR name LIKE '%financial%' 
   OR name LIKE '%chip%'
   OR name LIKE '%fund_flow%'
ORDER BY name;

-- 检查最近运行记录
SELECT task_name, status, start_time, end_time, error_message
FROM quant.scheduler_runs
WHERE start_time >= CURRENT_DATE - INTERVAL '7 days'
  AND task_name LIKE '%data%'
ORDER BY start_time DESC
LIMIT 20;
```

---

## 六、问题清单与建议

### P0 - 紧急修复

1. **财务报表数据过时**
   - 现状: 最新仅至 2026-03-31
   - 影响: 基本面筛选失效
   - 行动: 
     - 检查 `financial_data_update_job.py` 是否启用
     - 手动触发回填 2026-06-30 数据
     - 确认调度任务 cron 配置正确

2. **数据质量监控停摆**
   - 现状: 最近7天无检查记录
   - 影响: K线脏数据无法及时发现
   - 行动:
     - 检查 `data_quality_check_job.py` 调度状态
     - 恢复定期检查（建议每日或每周）

### P1 - 架构优化

3. **ORM模型位置统一**
   - 现状: 模型散落在 adapters/outbound/repositories/models/
   - 行动: 迁移至 infrastructure/persistence/orm/models/

4. **缺失表确认**
   - 现状: income_statements、index_constituents 未确认
   - 行动: 检查是否存在，补充迁移文件或文档说明

### P2 - 监控增强

5. **数据完整性监控**
   - 建议: 每日检查活跃股票K线缺失情况
   - 实现: 扩展 data_quality_check_job
   - 告警: 缺失超过阈值（如5个交易日）发送通知

6. **财务数据时效性监控**
   - 建议: 每季度末+45天检查财报是否更新
   - 告警: 超期未更新发送提醒

---

## 七、后续审计建议

### 立即执行

```bash
# 1. 检查调度任务状态
psql -d quant_investment -c "
SELECT name, is_enabled, last_run_time, next_run_time, cron_expression
FROM quant.scheduler_tasks
WHERE category = 'data_update' OR name LIKE '%data%'
ORDER BY name;
"

# 2. 检查最近任务运行日志
psql -d quant_investment -c "
SELECT task_name, status, start_time, end_time, 
       EXTRACT(EPOCH FROM (end_time - start_time)) as duration_sec,
       error_message
FROM quant.scheduler_runs
WHERE start_time >= CURRENT_DATE - INTERVAL '30 days'
  AND task_name IN ('kline_update', 'financial_update', 'chip_update', 'fund_flow_update')
ORDER BY start_time DESC;
"

# 3. 检查财务报表完整情况
psql -d quant_investment -c "
SELECT report_date, COUNT(*) as company_count
FROM quant.balance_sheets
GROUP BY report_date
ORDER BY report_date DESC
LIMIT 10;
"
```

### 代码审查

1. 检查 `financial_data_update_job.py` 数据源API是否正常
2. 检查 `data_quality_check_job.py` 为何停止运行
3. 确认所有job在 `scheduler_tasks` 表中正确注册

---

## 附录：关键SQL查询

### A.1 数据完整性检查

```sql
-- 检查每日K线数据量趋势
SELECT 
  trade_date,
  COUNT(*) as record_count,
  COUNT(DISTINCT symbol) as symbol_count
FROM quant.daily_klines 
WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY trade_date 
ORDER BY trade_date DESC;

-- 检查缺失K线（活跃股票）
WITH active_stocks AS (
  SELECT symbol FROM quant.stocks 
  WHERE is_delisted = false 
  LIMIT 100
),
recent_dates AS (
  SELECT DISTINCT trade_date 
  FROM quant.daily_klines 
  WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
  ORDER BY trade_date DESC
  LIMIT 20
)
SELECT 
  s.symbol,
  COUNT(DISTINCT d.trade_date) as expected_days,
  COUNT(k.trade_date) as actual_days,
  COUNT(DISTINCT d.trade_date) - COUNT(k.trade_date) as missing_days
FROM active_stocks s
CROSS JOIN recent_dates d
LEFT JOIN quant.daily_klines k 
  ON k.symbol = s.symbol AND k.trade_date = d.trade_date
GROUP BY s.symbol
HAVING COUNT(DISTINCT d.trade_date) - COUNT(k.trade_date) > 3
ORDER BY missing_days DESC;
```

### A.2 数据质量检查

```sql
-- K线质量分级分布
SELECT 
  grade,
  COUNT(*) as check_count,
  AVG(overall_score)::numeric(5,2) as avg_score,
  MIN(created_at) as first_check,
  MAX(created_at) as last_check
FROM kline_data_quality
GROUP BY grade
ORDER BY grade;

-- 最近错误和警告
SELECT 
  symbol,
  period,
  errors_json,
  warnings_json,
  created_at
FROM kline_data_quality
WHERE (error_count > 0 OR warning_count > 0)
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 变更记录

- 2026-09-03: 初版审计报告（基于 quant_investment 数据库现状）
