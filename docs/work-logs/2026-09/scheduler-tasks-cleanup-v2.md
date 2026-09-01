# 调度任务清理方案 V2 - 基于新架构分工

## 架构调整（2026-09-01）

**原则：**
- **V2（APScheduler）：** 业务逻辑任务（数据、因子、信号、交易）
- **Agent OS：** Agent 智能任务（分析、报告、决策）

---

## 清理策略

### 保留在 V2 的业务任务（33 个）

这些任务是核心业务逻辑，应该由 V2 的 APScheduler 执行：

#### 数据采集与处理（10 个）
| ID | 名称 | Cron | 状态 | 说明 |
|----|------|------|------|------|
| 232 | 每日数据质量检查 | 0 16 * * * | ✅ enabled | 数据质量监控 |
| 233 | 每日数据更新 | 30 7 * * 1-5 | ✅ enabled | 股票数据更新 |
| 238 | 每周财务数据更新 | 30 18 * * 6 | ✅ enabled | 财务数据 |
| 240 | 每日数据流水线 | 30 8 * * 1-5 | ✅ enabled | 数据处理流水线 |
| 241 | 每周全量重建 | 0 18 * * 6 | ✅ enabled | 全量数据重建 |
| 256 | gem-kline-update | 40 9 * * 1-5 | ✅ enabled | 创业板K线 |
| 267 | chip-distribution-update | 30 10 * * 1-5 | ✅ enabled | 筹码分布 |
| 272 | financial-statement-update | 0 12 * * 6 | ✅ enabled | 财务报表 |
| 308 | fund_flow_update | 30 15 * * 1-5 | ✅ enabled | 资金流向 |
| 250 | pre-market-scan | 25 1 * * 1-5 | ✅ enabled | 盘前扫描 |

#### 因子与信号（6 个）
| ID | 名称 | Cron | 状态 | 说明 |
|----|------|------|------|------|
| 234 | 每日因子计算 | 0 8 * * 1-5 | ✅ enabled | 因子计算 |
| 236 | 每日信号生成 | 30 8 * * 1-5 | ✅ enabled | 买入信号 |
| 242 | 每日信号执行 | 30 7 * * 1-5 | ✅ enabled | 信号执行 |
| 251 | realtime-signal-monitor | */5 1-6 * * 1-5 | ✅ enabled | 实时信号监控 |
| 261 | chan-scan-daily | 10 10 * * 1-5 | ✅ enabled | 缠论扫描 |
| 262 | chan-knowledge-distill-weekly | 0 12 * * 0 | ✅ enabled | 缠论知识蒸馏 |

#### 策略与验证（7 个）
| ID | 名称 | Cron | 状态 | 说明 |
|----|------|------|------|------|
| 249 | v13-simulation-trading | 30 6 * * 1-5 | ✅ enabled | V13模拟交易 |
| 252 | daily-strategy-validation | 0 13 * * 1-5 | ✅ enabled | 策略验证 |
| 253 | weekly-strategy-discovery | 0 2 * * 6 | ✅ enabled | 策略发现 |
| 268 | v13-risk-check | 0 8 * * 1-5 | ✅ enabled | V13风险检查 |
| 269 | v13-verification | 30 7 * * 1-5 | ✅ enabled | V13验证 |
| 270 | v14-daily-trading | 30 7 * * 1-5 | ✅ enabled | V14交易 |
| 307 | daily_trade_verify | 35 15 * * 1-5 | ✅ enabled | 交易验证 |

#### 风险与监控（5 个）
| ID | 名称 | Cron | 状态 | 说明 |
|----|------|------|------|------|
| 235 | 每周风险检查 | 0 1 * * 1 | ✅ enabled | 风险检查 |
| 258 | daily-pool-refresh | 0 18 * * 0-4 | ✅ enabled | 股票池刷新 |
| 263 | evolution-fitness-daily | 30 18 * * 1-5 | ✅ enabled | 进化适应度 |
| 264 | daily-equity-snapshot | 0 18 * * 1-5 | ✅ enabled | 权益快照 |
| 265 | decision-score-daily | 45 18 * * 1-5 | ✅ enabled | 决策评分 |

#### 报告与分析（5 个）
| ID | 名称 | Cron | 状态 | 说明 |
|----|------|------|------|------|
| 237 | 每周报告生成 | 0 10 * * 5 | ✅ enabled | 周报 |
| 266 | missed-opportunity-daily | 40 18 * * 1-5 | ✅ enabled | 错失机会分析 |
| 271 | v13-weekly-report | 0 1 * * 0 | ✅ enabled | V13周报 |
| 300 | morning_ai_analysis | 0 9 * * 1-5 | ⚠️ failed | AI早盘分析（需修复）|
| 301 | market_daily_snapshot | 0 9 * * 1-5 | ⚠️ failed | 市场快照（需修复）|

**保留总数：33 个任务**

---

### 迁移到 Agent OS 的任务（0 个新增）

Agent OS 已经接管了以下任务（cron_expression='managed_by_agent_os'），V2 不需要再执行：

- strategy_validate_daily (276)
- v13_daily_check (277)
- market_style_update (278)
- signal_generate_sell (279)
- ... 等 26 个 Agent OS 任务

**V2 策略：** 这些任务 APScheduler 会自动跳过（因为 cron='managed_by_agent_os'）

---

### 删除的重复/废弃任务（15 个）

#### 1. 重复任务（9 个）- 本地版本已被 Agent OS 替代

| ID | 名称 | 原因 |
|----|------|------|
| 243 | daily-data-quality-check | 重复 232，且已禁用 |
| 244 | daily-data-update | 重复 233，且已禁用 |
| 245 | daily-factor-compute | 重复 234，且已禁用 |
| 246 | weekly-risk-check | 重复 235，且已禁用 |
| 247 | daily-signal-generate | 重复 236，且已禁用 |
| 248 | weekly-report | 重复 237，且已禁用 |
| 254 | weekly_financial_update | 重复 238，且已禁用 |
| 257 | v13-daily-check | 重复 249，且失败 |
| 259 | daily-signal-push-fallback | 重复 242，且已禁用 |

#### 2. 临时/测试任务（4 个）

| ID | 名称 | 原因 |
|----|------|------|
| 239 | 华润三九价格监控 | 临时监控，已禁用 |
| 255 | Unnamed Task | 未命名，已禁用 |
| 260 | 恐慌抄底每日扫描 | 测试策略，已禁用 |
| 305 | market_perception_daily_snapshot | 重复，已禁用 |

#### 3. 失效命令（2 个）

| ID | 名称 | 命令 | 原因 |
|----|------|------|------|
| 300 | morning_ai_analysis | agent_turn | 持续失败，应迁移到 Agent OS |
| 301 | market_daily_snapshot | curl ... | 持续失败，应用 API 端点 |

**注意：** 300/301 如果是 Agent 任务，应该迁移到 Agent OS 而不是删除

---

## 执行方案

### 方案 1：删除重复和临时任务（13 个）

保留 300/301，因为它们可能需要迁移到 Agent OS：

```sql
BEGIN;

-- 1. 备份（可选）
CREATE TABLE quant.scheduler_tasks_backup_20260901 AS 
SELECT * FROM quant.scheduler_tasks WHERE id IN (243, 244, 245, 246, 247, 248, 254, 257, 259, 239, 255, 260, 305);

-- 2. 删除明确无用的任务
DELETE FROM quant.scheduler_tasks 
WHERE id IN (
    -- 重复任务
    243, 244, 245, 246, 247, 248, 254, 257, 259,
    -- 临时任务
    239, 255, 260, 305
);

-- 3. 验证
SELECT COUNT(*) FROM quant.scheduler_tasks;  -- 应该是 60 (73-13)

COMMIT;
```

### 方案 2：删除所有废弃任务（15 个）

包括失效的 300/301：

```sql
BEGIN;

DELETE FROM quant.scheduler_tasks 
WHERE id IN (
    243, 244, 245, 246, 247, 248, 254, 257, 259,  -- 重复
    239, 255, 260, 305,                            -- 临时
    300, 301                                       -- 失效
);

COMMIT;
```

---

## APScheduler 迁移后的任务分布

执行方案 1 后：

| 类型 | 数量 | 说明 |
|------|------|------|
| V2 业务任务（enabled） | 33 | 由 APScheduler 调度 |
| V2 失效任务（disabled） | 2 | 300/301 待修复或迁移 |
| Agent OS 任务（managed） | 26 | APScheduler 自动跳过 |
| **总计** | **61** | 从 73 减少到 61 |

执行方案 2 后：

| 类型 | 数量 | 说明 |
|------|------|------|
| V2 业务任务（enabled） | 33 | 由 APScheduler 调度 |
| Agent OS 任务（managed） | 26 | APScheduler 自动跳过 |
| **总计** | **59** | 从 73 减少到 59 |

---

## 后续建议

### 1. 修复或迁移失效任务

**300 - morning_ai_analysis:**
- 如果是 AI 分析 → 迁移到 Agent OS
- 修复 `agent_turn` 命令或替换为新的 Agent 接口

**301 - market_daily_snapshot:**
- 替换 curl 命令为 API 调用
- 或者迁移到 Agent OS 作为智能分析任务

### 2. Agent OS 任务审查

对于 276-310 这些 `managed_by_agent_os` 的任务：
- 如果 `is_enabled=false`，说明在 Agent OS 中也是禁用的
- 可以定期清理（比如每季度）超过 3 个月未启用的任务

### 3. 任务命名规范

新任务建议使用统一命名：
```
{frequency}_{business}_{action}
例如：daily_kline_update, weekly_report_generate
```

---

## 立即执行（推荐方案 1）

```bash
# 1. 连接数据库
psql quant_investment

# 2. 执行清理
BEGIN;

DELETE FROM quant.scheduler_tasks 
WHERE id IN (243, 244, 245, 246, 247, 248, 254, 257, 259, 239, 255, 260, 305);

-- 验证删除
SELECT 
    COUNT(*) FILTER (WHERE is_enabled AND cron_expression != 'managed_by_agent_os') as v2_enabled,
    COUNT(*) FILTER (WHERE cron_expression = 'managed_by_agent_os') as agent_os,
    COUNT(*) as total
FROM quant.scheduler_tasks;

-- 应该显示：v2_enabled ≈ 33, agent_os = 26, total ≈ 60

COMMIT;
```

---

**文档版本：** v2.0 - 基于新架构分工  
**创建日期：** 2026-09-01  
**执行建议：** APScheduler 迁移完成后立即执行
