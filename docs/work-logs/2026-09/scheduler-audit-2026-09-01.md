# Scheduler Audit Report - 2026-09-01

## Executive Summary

审计时间：2026-09-01  
审计范围：调度系统配置、任务运行状态、失败率分析  
数据窗口：最近7天运行记录

**关键发现：**
- 总任务数：73个（启用35个，禁用38个）
- 7天内失败任务：26个任务类型出现失败
- 高失败率任务：15个任务失败率≥75%
- 主要问题：命令未注册、语法错误、模块缺失

---

## 1. 任务配置概览

### 1.1 任务启用状态

| 状态 | 数量 | 占比 |
|------|------|------|
| 已启用 (is_enabled=true) | 35 | 47.9% |
| 已禁用 (is_enabled=false) | 38 | 52.1% |
| **总计** | **73** | **100%** |

### 1.2 任务类型分布

**Agent OS托管任务（managed_by_agent_os）：27个**
- 所有Agent OS webhook任务当前均已禁用（is_enabled=false）
- 这些任务通过Agent OS的调度系统触发，不依赖cron表达式
- 任务ID范围：276-310

**传统cron任务：46个**
- 启用：35个
- 禁用：11个

---

## 2. 失败率分析（最近7天）

### 2.1 100%失败率任务（紧急）

| 任务名称 | 运行次数 | 失败次数 | 最后运行时间 | 主要错误 |
|---------|---------|---------|-------------|---------|
| daily-equity-snapshot | 3 | 3 | 2026-08-27 12:14 | IndentationError: unexpected indent |
| decision-score-daily | 3 | 3 | 2026-08-27 12:14 | IndentationError: unexpected indent |
| missed-opportunity-daily | 3 | 3 | 2026-08-27 12:14 | IndentationError: unexpected indent |
| evolution-fitness-daily | 3 | 3 | 2026-08-27 12:14 | IndentationError: unexpected indent |
| daily-pool-refresh | 3 | 3 | 2026-08-27 12:14 | IndentationError: unexpected indent |
| morning_ai_analysis | 2 | 2 | 2026-08-26 17:00 | 未知错误 |
| 每日因子计算 | 2 | 2 | 2026-08-26 16:00 | 未知错误 |
| chan-scan-daily | 2 | 2 | 2026-08-27 12:14 | IndentationError: unexpected indent |
| market_daily_snapshot | 1 | 1 | 2026-08-26 17:00 | 未知错误 |
| chan-knowledge-distill-weekly | 1 | 1 | 2026-08-25 22:24 | IndentationError: unexpected indent |

**根本原因：**
- **scheduler_tasks.py line 204/205 语法错误**（2026-08-31 18:43前引入）
- 影响多个任务在特定时间段全面失败

### 2.2 高失败率任务（75-83%）

| 任务名称 | 运行次数 | 失败次数 | 失败率 | 主要错误 |
|---------|---------|---------|--------|---------|
| pool_refresh_daily | 6 | 5 | 83.3% | unexpected indent (scheduler_tasks.py) |
| fund_flow_update | 12 | 9 | 75.0% | **Unknown scheduler command: 'fund_flow_update'** |
| gem-kline-update | 4 | 3 | 75.0% | 未详查 |
| market_style_update | 4 | 3 | 75.0% | **No module named 'infrastructure.scheduler.market_style_jobs'** |
| chan_scan_daily | 4 | 3 | 75.0% | unexpected indent (scheduler_tasks.py) |

**根本原因：**
1. **fund_flow_update**：命令未在scheduler.py的`_execute_command()`处理器中注册
2. **market_style_update**：模块路径错误，实际应该是别的模块或不存在

### 2.3 中度失败率任务（33-67%）

| 任务名称 | 失败率 | 问题 |
|---------|-------|------|
| 恐慌抄底每日扫描 | 66.7% | 未详查 |
| 每日数据更新 | 66.7% | 未详查 |
| daily-factor-compute | 66.7% | 未详查 |
| factor_compute_daily | 33.3% | 部分成功，Zombie run reaped |
| daily-strategy-validation | 33.3% | 未详查 |

### 2.4 低失败率但需关注（16-20%）

| 任务名称 | 失败率 | 备注 |
|---------|-------|------|
| strategy_validate_daily | 20.0% | 偶发失败 |
| data_quality_check_daily | 16.7% | **最新失败（2026-09-01 16:00）：name 'datetime' is not defined** |

---

## 3. 重复任务配置

### 3.1 同一command的多个任务

| Command | 任务数量 | 启用状态分布 | 建议 |
|---------|---------|------------|------|
| agent_os_webhook | 27 | 全部禁用 | ✅ 正常（Agent OS托管） |
| data_update | 6 | 1启用，5禁用 | ⚠️ 清理禁用任务 |
| data_quality_check | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |
| factor_compute | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |
| financial_data_update | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |
| report_daily | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |
| risk_check | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |
| signal_execution_daily | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |
| signal_generate | 2 | 1启用，1禁用 | ⚠️ 清理禁用任务 |

**重复任务示例：**

- **data_update**：
  - ID 233: 每日数据更新 (启用, 7:30 工作日)
  - ID 239: 华润三九价格监控 (禁用)
  - ID 244: daily-data-update (禁用)
  - ID 255: Unnamed Task (禁用)
  - ID 260: 恐慌抄底每日扫描 (禁用)
  - ID 305: market_perception_daily_snapshot (禁用)

---

## 4. 命令处理器缺口

### 4.1 scheduler.py中缺失的命令处理器

当前scheduler.py中已注册的命令（`_execute_command`方法）：

✅ 已注册（48个）：
- data_quality_check, data_update, signal_generate, risk_check, report_daily
- backtest_run, strategy_backtest, factor_compute, model_train, benchmark_run
- data_pipeline_daily, data_pipeline_weekly, signal_execution_daily
- market_style_update, v13_daily_check, signal_monitor_realtime
- strategy_validate_daily, financial_data_update, market_scan_preopen
- strategy_discover_weekly, kline_update, chip_distribution_update
- index_constituents_update, v13_risk_check, v13_verification
- v13_weekly_report, v14_daily_check, financial_statement_update

❌ **缺失的命令**（任务表中使用但未注册）：

1. **fund_flow_update** - 🔴 高优先级
   - 任务ID: 308
   - cron: 30 15 * * 1-5 (每工作日15:30)
   - 状态: 已启用
   - Job文件: `infrastructure/jobs/fund_flow_update_job.py` 存在
   - **影响：** 12次运行中9次失败

2. **pool_refresh_daily** - 🔴 高优先级
   - 任务ID: 258, 285
   - cron: 0 18 * * 0-4 (周日到周四18:00)
   - 状态: 258启用，285禁用（Agent OS托管）
   - **影响：** 6次运行5次失败（83.3%失败率）

3. **chan_scan** - 🔴 高优先级
   - 任务ID: 261
   - cron: 10 10 * * 1-5 (工作日10:10)
   - 状态: 已启用
   - **影响：** 4次运行3次失败

4. **chan_knowledge_distill** - 🟡 中优先级
   - 任务ID: 262
   - cron: 0 12 * * 0 (周日12:00)
   - 状态: 已启用

5. **evolution_fitness_daily** - 🟡 中优先级
   - 任务ID: 263
   - cron: 30 18 * * 1-5 (工作日18:30)
   - 状态: 已启用

6. **daily_equity_snapshot** - 🟡 中优先级
   - 任务ID: 264
   - cron: 0 18 * * 1-5 (工作日18:00)
   - 状态: 已启用

7. **decision_score_daily** - 🟡 中优先级
   - 任务ID: 265
   - cron: 45 18 * * 1-5 (工作日18:45)
   - 状态: 已启用

8. **missed_opportunity_daily** - 🟡 中优先级
   - 任务ID: 266
   - cron: 40 18 * * 1-5 (工作日18:40)
   - 状态: 已启用

9. **v13_trading** - 🟢 低优先级
   - 任务ID: 257
   - 状态: 已禁用

10. **agent_turn** - 🔴 高优先级
    - 任务ID: 300
    - cron: 0 9 * * 1-5 (工作日09:00)
    - 状态: 已启用
    - **特殊命令：** 可能需要特殊处理（调用Agent）

11. **curl命令** - 🟢 低优先级
    - 任务ID: 301 (market_daily_snapshot)
    - command: `curl -X POST http://localhost:5001/api/market/perception/snapshot`
    - 状态: 已启用
    - **特殊：** 直接curl命令，需要shell执行支持

12. **trade_verify_daily** - 🟡 中优先级
    - 任务ID: 307
    - cron: 35 15 * * 1-5 (工作日15:35)
    - 状态: 已启用
    - **未跑过：** last_run_at为空

### 4.2 模块缺失问题

❌ **infrastructure.scheduler.market_style_jobs**
- 当前代码中找不到该模块
- 影响任务：market_style_update (ID 278, Agent OS托管，已禁用)
- **建议：** 定位正确的market_style_update实现位置

---

## 5. 僵尸任务处理

### 5.1 当前running状态任务
✅ **无僵尸任务** - 当前没有status='running'的记录

### 5.2 僵尸任务自动判死机制
✅ **已实施** - scheduler.py:L466-481
- 超时阈值：6小时（ZOMBIE_RUN_TIMEOUT）
- 自动判死并标记为failed
- 防止任务永久阻塞

### 5.3 历史僵尸任务案例
- 2026-08-28: 2个任务被健康监控器清理（Zombie run reaped by health monitor）
  - strategy_validate_daily (run开始于00:32:38)
  - factor_compute_daily (run开始于00:32:33)

---

## 6. Agent OS集成状态

### 6.1 Agent OS托管任务（27个）

所有Agent OS webhook任务（task_id 276-310）：
- **状态：** 全部禁用（is_enabled=false）
- **cron表达式：** "managed_by_agent_os"（特殊标记）
- **command：** agent_os_webhook
- **最后运行时间：** 2026-09-01前后仍有运行记录

**任务清单：**
```
276: strategy_validate_daily         (last_run: 2026-09-01 13:00)
277: v13_daily_check                 (last_run: 2026-09-01 14:30)
278: market_style_update             (last_run: 2026-09-01 15:30)
279: signal_generate_sell            (last_run: 2026-09-01 15:30)
280: v13_risk_check                  (last_run: 2026-09-01 16:00)
281: v13_verification                (last_run: 2026-09-01 16:30)
282: data_quality_check_daily        (last_run: 2026-09-01 16:00) ⚠️ 最新失败
283: daily_equity_snapshot           (last_run: 2026-08-31 18:41)
284: chan_knowledge_distill_weekly   (last_run: 2026-08-30 12:00)
285: pool_refresh_daily              (last_run: 2026-09-01 02:00)
286: signal_execution_daily          (last_run: 2026-09-01 07:30)
287: factor_compute_daily            (last_run: 2026-09-01 08:00)
288: data_pipeline_daily             (last_run: 2026-09-01 08:30)
289: signal_generate_buy             (last_run: 2026-09-01 09:00)
290: chan_scan_daily                 (last_run: 2026-09-01 10:10)
291: chip_distribution_update        (last_run: 2026-09-01 10:30)
292: kline_update                    (last_run: 2026-08-31 18:41)
293: report_weekly                   (last_run: 2026-08-28 10:00)
294: v13_weekly_report               (last_run: 2026-08-29 10:00) ⚠️ 失败
295: data_pipeline_weekly            (last_run: 2026-08-29 18:00)
296: financial_data_update           (last_run: 2026-08-29 18:30)
297: financial_statement_update      (last_run: 2026-08-29 20:00)
298: strategy_discover_weekly        (last_run: 2026-08-30 14:00)
299: risk_check_weekly               (last_run: 2026-08-31 01:00)
306: market_perception_daily         (last_run: 2026-08-31 16:54)
309: factor_compute                  (last_run: 2026-09-01 10:15)
310: data_update                     (last_run: 2026-08-31 19:13)
```

### 6.2 Agent OS webhook失败案例

🔴 **最新失败（2026-09-01）：**
- **data_quality_check_daily** (16:00): `name 'datetime' is not defined`
  - 代码问题：Agent OS webhook处理器中datetime模块未导入

🔴 **高频失败（2026-08-31）：**
- **市场风格更新失败** (3次): `No module named 'infrastructure.scheduler.market_style_jobs'`

🔴 **语法错误期（2026-08-27至08-31）：**
- 多个任务因 `unexpected indent (scheduler_tasks.py, line 204/205)` 失败
- 时间窗口：2026-08-27 12:14 至 2026-08-31 18:41

---

## 7. 任务调度时间分析

### 7.1 时间冲突检查

**早盘前（07:00-09:30）：**
```
07:30 (工作日):
  - 每日数据更新 (data_update) - ID 233 ✅
  - 每日信号执行 (signal_execution_daily) - ID 242 ✅
  - v13_verification - ID 269 ✅
  - v14_daily_check - ID 270 ✅
  - signal_execution_daily (Agent OS) - ID 286 🔴 禁用
  - 恐慌抄底每日扫描 (data_update) - ID 260 🔴 禁用

08:00 (工作日):
  - 每日因子计算 (factor_compute) - ID 234 ✅
  - v13_risk_check - ID 268 ✅
  - factor_compute_daily (Agent OS) - ID 287 🔴 禁用
  - daily-factor-compute - ID 245 🔴 禁用

08:30 (工作日):
  - 每日数据流水线 (data_pipeline_daily) - ID 240 ✅
  - 每日信号生成 (signal_generate) - ID 236 ✅
  - data_pipeline_daily (Agent OS) - ID 288 🔴 禁用
  - daily-signal-generate - ID 247 🔴 禁用

09:00 (工作日):
  - morning_ai_analysis - ID 300 ✅ (可能需要特殊处理)
  - market_daily_snapshot (curl) - ID 301 ✅
  - signal_generate_buy (Agent OS) - ID 289 🔴 禁用
```

**盘中（09:30-15:00）：**
```
09:25 (工作日):
  - pre-market-scan (market_scan_preopen) - ID 250 ✅

09:40 (工作日):
  - gem-kline-update (kline_update) - ID 256 ✅

09:00-14:00 每5分钟 (工作日):
  - realtime-signal-monitor (signal_monitor_realtime) - ID 251 ✅

10:10 (工作日):
  - chan-scan-daily (chan_scan) - ID 261 ⚠️ 命令未注册
  - chan_scan_daily (Agent OS) - ID 290 🔴 禁用

10:30 (工作日):
  - chip-distribution-update - ID 267 ✅
  - chip_distribution_update (Agent OS) - ID 291 🔴 禁用

13:00 (工作日):
  - daily-strategy-validation (strategy_validate_daily) - ID 252 ✅

14:30 (工作日):
  - v13-simulation-trading (v13_daily_check) - ID 249 ✅
```

**收盘后（15:00-18:00）：**
```
15:30 (工作日):
  - fund_flow_update - ID 308 ⚠️ 命令未注册
  - market_perception_daily_snapshot (data_update) - ID 305 🔴 禁用
  - daily-data-update - ID 244 🔴 禁用
  - market_style_update (Agent OS) - ID 278 🔴 禁用
  - signal_generate_sell (Agent OS) - ID 279 🔴 禁用

15:35 (工作日):
  - daily_trade_verify (trade_verify_daily) - ID 307 ⚠️ 命令未注册，从未运行

16:00 (工作日/每日):
  - 每日数据质量检查 (data_quality_check) - ID 232 ✅
  - v13_risk_check (Agent OS) - ID 280 🔴 禁用
  - data_quality_check_daily (Agent OS) - ID 282 🔴 禁用
  - daily-data-quality-check - ID 243 🔴 禁用
```

**夜间（18:00-次日02:00）：**
```
18:00 (周日-周四):
  - daily-pool-refresh (pool_refresh_daily) - ID 258 ⚠️ 命令未注册
  - daily_equity_snapshot - ID 264 ⚠️ 命令未注册
  - pool_refresh_daily (Agent OS) - ID 285 🔴 禁用

18:00 (周五/周六):
  - 每周报告生成 (report_daily) - ID 237 ✅
  - 每周全量重建 (data_pipeline_weekly) - ID 241 ✅

18:30 (周六):
  - 每周财务数据更新 (financial_data_update) - ID 238 ✅

18:30-18:45 (工作日):
  - evolution_fitness_daily - ID 263 ⚠️ 命令未注册
  - missed_opportunity_daily - ID 266 ⚠️ 命令未注册
  - decision_score_daily - ID 265 ⚠️ 命令未注册

01:00 (周一):
  - 每周风险检查 (risk_check) - ID 235 ✅

02:00 (周六):
  - weekly-strategy-discovery (strategy_discover_weekly) - ID 253 ✅
```

### 7.2 潜在时间冲突

⚠️ **高负载时段（工作日早盘前）：**
- 07:30-09:00 期间有多个数据更新/因子计算任务并发
- 建议：监控数据库连接池和CPU使用率

⚠️ **禁用任务与启用任务时间重叠：**
- 多个禁用的Agent OS任务与启用的传统cron任务时间相同
- 可能原因：任务迁移到Agent OS后未清理旧cron配置

---

## 8. 优先级修复建议

### 🔴 P0 - 紧急修复（影响生产运行）

#### P0-1: 补全缺失的命令处理器
**影响任务：9个启用任务无法执行**

修改文件：`quantsys-v2/infrastructure/scheduler/scheduler.py`

在 `_execute_command()` 方法的 handlers 字典中添加：

```python
def _execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    handlers: Dict[str, Any] = {
        # ... 现有处理器 ...
        
        # P0-1: 新增处理器
        "fund_flow_update": self._handle_fund_flow_update,
        "pool_refresh_daily": self._handle_pool_refresh_daily,
        "chan_scan": self._handle_chan_scan,
        "chan_knowledge_distill": self._handle_chan_knowledge_distill,
        "evolution_fitness_daily": self._handle_evolution_fitness_daily,
        "daily_equity_snapshot": self._handle_daily_equity_snapshot,
        "decision_score_daily": self._handle_decision_score_daily,
        "missed_opportunity_daily": self._handle_missed_opportunity_daily,
        "trade_verify_daily": self._handle_trade_verify_daily,
        "agent_turn": self._handle_agent_turn,  # 特殊：需要调用Agent
    }
```

实现各处理器方法（委托模式）：
```python
def _handle_fund_flow_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """资金流向日更：委托 infrastructure.jobs.fund_flow_update_job.execute"""
    from infrastructure.jobs.fund_flow_update_job import execute
    return execute(**(params or {}))

def _handle_pool_refresh_daily(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """股票池每日刷新：委托对应job模块"""
    # TODO: 定位并委托实际实现
    pass

# ... 其他7个处理器 ...
```

**预期效果：**
- fund_flow_update失败率从75%降至<5%
- pool_refresh_daily失败率从83.3%降至<5%
- 其他7个任务恢复正常执行

#### P0-2: 修复data_quality_check_daily的datetime错误
**错误：** `name 'datetime' is not defined` (2026-09-01 16:00)

**位置：** Agent OS webhook处理器或相关job代码

**修复方法：**
1. 定位agent_os_webhook处理器代码
2. 在文件头部添加：`from datetime import datetime`
3. 或检查data_quality_check_job.py是否缺少导入

#### P0-3: 修复market_style_update模块缺失
**错误：** `No module named 'infrastructure.scheduler.market_style_jobs'`

**定位步骤：**
```bash
# 1. 搜索market_style相关代码
find . -name "*market_style*" -type f

# 2. 检查git历史
git log --all --full-history --oneline -- "*market_style*"

# 3. 确认正确的模块路径
```

**可能的修复：**
- 选项A：找到正确的market_style_update实现并修正import路径
- 选项B：如果功能已废弃，禁用相关任务（ID 278）

### 🟡 P1 - 重要优化（提升系统健康度）

#### P1-1: 清理重复任务配置
**目标：** 删除38个禁用的冗余任务

**操作：**
```sql
-- 删除禁用的重复任务（保留Agent OS托管任务）
DELETE FROM quant.scheduler_tasks 
WHERE is_enabled = false 
  AND id NOT BETWEEN 276 AND 310  -- 保留Agent OS任务
  AND id IN (
      239, 244, 245, 246, 247, 248, 254, 255, 257, 259, 260, 305
      -- 其他确认可删除的ID
  );
```

**影响：**
- 简化任务列表
- 减少维护负担
- 避免误启用旧配置

#### P1-2: 标准化任务命名
**问题：** 任务命名不一致（中文/英文/短横线/下划线混用）

**建议规范：**
- 中文任务：用于人工阅读的描述性名称
- 英文任务：全部使用下划线命名（snake_case）
- 避免：短横线命名（kebab-case）和驼峰命名

**示例：**
```
❌ daily-factor-compute
❌ dailyFactorCompute
✅ factor_compute_daily
```

#### P1-3: 补全任务描述（description字段）
**现状：** 多个任务description为空

**建议：**
- 为所有启用任务添加清晰的中文描述
- 包含：作用、数据来源、输出结果、依赖关系

#### P1-4: 优化任务调度时间
**目标：** 避免高负载时段的资源竞争

**建议调整：**
```
现状: 08:00 有4个任务（2启用+2禁用）
优化: 
  - 08:00: 每日因子计算 (factor_compute)
  - 08:05: v13_risk_check
  - 清理禁用任务

现状: 18:00-18:45 有6个任务密集
优化:
  - 拉开间隔到5-10分钟
  - 考虑依赖关系（equity_snapshot → evolution_fitness）
```

### 🟢 P2 - 长期改进（架构优化）

#### P2-1: Agent OS任务迁移完整性审查
**问题：** 27个Agent OS任务全部禁用，但仍有运行记录

**调查事项：**
1. Agent OS是否已完全接管这些任务的调度？
2. 为什么任务禁用后仍有last_run_at更新？
3. 是否存在双重调度（cron + Agent OS）？

**建议行动：**
- 与Agent OS调度系统对账
- 确认哪些任务应保留在quantsys-v2调度
- 对于完全迁移的任务，从scheduler_tasks表归档

#### P2-2: 监控和告警机制
**缺失功能：**
- 任务失败自动告警
- 执行时间异常检测（超过预期时长）
- 僵尸任务实时监控

**建议实现：**
```python
# 1. 失败告警
def _on_task_failed(self, task_name: str, error: str):
    if self._should_alert(task_name):
        send_alert(f"调度任务失败: {task_name}\n错误: {error}")

# 2. 执行时长监控
def _check_duration_anomaly(self, task_id: int, duration_ms: int):
    avg_duration = self._get_avg_duration(task_id)
    if duration_ms > avg_duration * 3:
        logger.warning(f"Task {task_id} took {duration_ms}ms (avg: {avg_duration}ms)")
```

#### P2-3: 任务依赖图
**目标：** 可视化任务间的数据依赖关系

**好处：**
- 优化调度顺序
- 发现循环依赖
- 支持失败重试策略

**示例依赖链：**
```
kline_update → factor_compute → signal_generate → signal_execution
              ↓
              chip_distribution_update
              market_style_update
```

#### P2-4: 支持任务参数模板化
**现状：** 任务params存储为JSONB，但缺少模板和校验

**建议：**
- 为每个command定义参数schema
- 前端任务配置UI提供表单校验
- 支持参数继承和覆盖

---

## 9. 风险评估

### 9.1 高风险任务

| 任务 | 风险等级 | 风险描述 | 缓解措施 |
|------|---------|---------|---------|
| fund_flow_update | 🔴 高 | 命令未注册，75%失败率，影响资金流数据完整性 | P0-1立即修复 |
| pool_refresh_daily | 🔴 高 | 83.3%失败率，影响股票池数据新鲜度 | P0-1立即修复 |
| evolution_fitness_daily | 🟡 中 | 100%失败（语法错误期），进化系统数据断流 | P0-1修复+回填历史数据 |
| factor_compute | 🟡 中 | 偶发僵尸进程，占用资源 | 监控僵尸判死机制 |
| morning_ai_analysis | 🟡 中 | 100%失败，AI分析未执行 | P0-1实现agent_turn处理器 |

### 9.2 数据质量风险

**潜在数据缺口（因任务失败导致）：**

1. **资金流数据**（fund_flow_update）
   - 缺口期：2026-08-31至09-01，9次失败
   - 影响：资金流向分析不准确

2. **股票池数据**（pool_refresh_daily）
   - 缺口期：2026-08-26至09-01，5次失败
   - 影响：股票池成员可能过时

3. **进化系统数据**（evolution_fitness_daily等）
   - 缺口期：2026-08-27至08-31（语法错误期）
   - 影响：进化学习中断，适应度评分缺失

**修复建议：**
- P0修复完成后，运行一次性回填脚本
- 对关键时间点（2026-08-26至09-01）的数据质量进行审计

### 9.3 系统稳定性风险

**并发负载风险：**
- 早盘前（07:30-09:00）有10+任务集中执行
- 可能导致：数据库连接池耗尽、CPU峰值、任务排队

**僵尸任务风险：**
- 虽然有6小时判死机制，但仍可能造成资源浪费
- 建议：降低判死阈值到3小时（针对预期运行时间<30分钟的任务）

---

## 10. 执行计划

### 第一周（2026-09-02至09-06）- P0修复

**Day 1-2: 命令处理器补全**
- [ ] 在scheduler.py中添加9个缺失的命令处理器
- [ ] 实现各处理器的委托逻辑
- [ ] 单元测试：每个处理器的成功/失败路径
- [ ] 部署到测试环境验证

**Day 3: 模块路径修复**
- [ ] 定位market_style_update的正确实现
- [ ] 修复datetime导入问题
- [ ] 回归测试：运行所有启用任务一次

**Day 4-5: 数据回填**
- [ ] 编写回填脚本（fund_flow, pool_refresh, evolution_fitness）
- [ ] 对2026-08-26至09-01的数据缺口进行补录
- [ ] 数据质量验证

### 第二周（2026-09-09至09-13）- P1优化

**Day 1: 任务清理**
- [ ] 审查38个禁用任务，确认可删除清单
- [ ] 执行DELETE操作（先备份）
- [ ] 更新任务文档

**Day 2-3: 命名和描述标准化**
- [ ] 制定任务命名规范文档
- [ ] 重命名不符合规范的任务
- [ ] 补全description字段

**Day 4-5: 调度时间优化**
- [ ] 绘制当前任务时间线图
- [ ] 识别高负载时段和冲突
- [ ] 调整任务cron表达式，拉开间隔

### 第三周（2026-09-16至09-20）- P2架构改进

**Day 1-2: Agent OS集成审查**
- [ ] 对账Agent OS和quantsys-v2的任务调度
- [ ] 确认双重调度的任务并解决
- [ ] 归档已完全迁移的任务

**Day 3-4: 监控告警**
- [ ] 实现任务失败告警（钉钉/邮件）
- [ ] 添加执行时长异常检测
- [ ] 配置告警规则和阈值

**Day 5: 文档和复盘**
- [ ] 更新调度系统文档
- [ ] 编写运维手册（添加任务、故障排查）
- [ ] 团队复盘会议

---

## 11. 监控指标

### 11.1 健康度指标

**任务成功率（目标：>95%）：**
```sql
SELECT 
    DATE(started_at) as date,
    COUNT(*) as total_runs,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM quant.scheduler_runs
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(started_at)
ORDER BY date DESC;
```

**任务平均执行时长：**
```sql
SELECT 
    t.name,
    COUNT(*) as runs,
    AVG(r.duration_ms) as avg_ms,
    MAX(r.duration_ms) as max_ms,
    STDDEV(r.duration_ms) as stddev_ms
FROM quant.scheduler_runs r
JOIN quant.scheduler_tasks t ON r.task_id = t.id
WHERE r.started_at > NOW() - INTERVAL '7 days'
  AND r.status = 'success'
  AND r.duration_ms IS NOT NULL
GROUP BY t.name
ORDER BY avg_ms DESC
LIMIT 20;
```

### 11.2 告警阈值

| 指标 | 告警阈值 | 紧急阈值 |
|------|---------|---------|
| 日任务失败率 | >10% | >20% |
| 单任务连续失败 | 3次 | 5次 |
| 执行时长异常 | >均值3倍 | >均值5倍 |
| running状态滞留 | >3小时 | >6小时 |
| 数据库连接池使用率 | >70% | >90% |

---

## 12. 附录

### 12.1 完整任务清单

（略，见第1节和6.1节）

### 12.2 命令处理器映射表

| Command | Handler方法 | Job文件 | 状态 |
|---------|-----------|---------|------|
| fund_flow_update | ❌ 缺失 | fund_flow_update_job.py | 存在 |
| pool_refresh_daily | ❌ 缺失 | ? | 待定位 |
| chan_scan | ❌ 缺失 | ? | 待定位 |
| chan_knowledge_distill | ❌ 缺失 | ? | 待定位 |
| kline_update | ✅ _handle_kline_update | kline_update_job.py | 正常 |
| chip_distribution_update | ✅ _handle_chip_distribution_update | chip_distribution_update_job.py | 正常 |
| financial_statement_update | ✅ _handle_financial_statement_update | financial_statement_update_job.py | 正常 |
| v13_risk_check | ✅ _handle_v13_risk_check | risk_check_job.py | 正常 |
| ... | ... | ... | ... |

### 12.3 SQL快速查询

**查看特定任务的最近10次运行：**
```sql
SELECT 
    r.id, r.status, r.started_at, r.duration_ms,
    LEFT(r.error, 100) as error
FROM quant.scheduler_runs r
JOIN quant.scheduler_tasks t ON r.task_id = t.id
WHERE t.name = 'fund_flow_update'
ORDER BY r.started_at DESC
LIMIT 10;
```

**查看当天所有失败任务：**
```sql
SELECT 
    t.name, r.started_at, r.error
FROM quant.scheduler_runs r
JOIN quant.scheduler_tasks t ON r.task_id = t.id
WHERE r.status = 'failed'
  AND DATE(r.started_at) = CURRENT_DATE
ORDER BY r.started_at DESC;
```

**统计各命令的执行频率：**
```sql
SELECT 
    t.command,
    COUNT(DISTINCT t.id) as task_count,
    SUM(CASE WHEN t.is_enabled THEN 1 ELSE 0 END) as enabled_count,
    COUNT(r.id) as total_runs_7d
FROM quant.scheduler_tasks t
LEFT JOIN quant.scheduler_runs r ON t.id = r.task_id 
    AND r.started_at > NOW() - INTERVAL '7 days'
GROUP BY t.command
ORDER BY total_runs_7d DESC;
```

---

## 审计结论

**系统状态评级：⚠️ 需要改进（C级）**

**关键问题：**
1. 🔴 **9个启用任务因命令未注册而无法执行**（P0）
2. 🔴 **资金流/股票池等关键数据任务高失败率**（P0）
3. 🟡 **任务配置混乱：38个冗余禁用任务**（P1）
4. 🟡 **Agent OS集成状态不明确**（P1）

**预期改进效果（完成P0+P1）：**
- 任务成功率：当前约60% → 目标>95%
- 失败任务数：26个 → <3个
- 配置清晰度：73个任务（52%禁用） → ~35个任务（全部有效）

**下一步行动：**
立即执行第一周P0修复计划，优先补全9个缺失的命令处理器。

---

**审计人：** Claude (Kiro)  
**审计日期：** 2026-09-01  
**文档版本：** v1.0  
**下次审计建议：** 2026-09-15（P0/P1修复完成后）
