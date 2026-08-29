# Agent-DH 工具清单

**最后更新**: 2026-08-28  
**总计**: 约 120 个工具  
**已重构**: 8 个 (6.7%)  
**进行中**: 0 个  
**待重构**: 约 112 个 (93.3%)

---

## 图例

- ✅ **已完成** - 已重构为 BaseTool 模式并测试通过
- 🔄 **进行中** - 正在重构
- ⏸️ **待重构** - 等待重构
- 📦 **Package** - 工具所属的 package

---

## Phase 1: Trading Package（已完成）

**Package**: `packages/trading`  
**状态**: ✅ 完成  
**完成日期**: 2026-08-28

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | account_info | ✅ | 简单 | 账户信息查询 |
| 2 | position_list | ✅ | 简单 | 持仓列表 |
| 3 | portfolio_trade | ✅ | 复杂 | 交易执行（包含 R-008/M4-1/M4-2/M2-2/M5/M3-3） |
| 4 | trade_monitor | ✅ | 简单 | 交易监控 |
| 5 | algo_execute | ✅ | 简单 | 算法执行 |
| 6 | trade_verify | ✅ | 简单 | 交易验证 |
| 7 | slippage_report | ✅ | 简单 | 滑点报告（M5） |
| 8 | m4_circuit_breaker_check | ✅ | 复杂 | 熔断检查（M4-2） |

**进度**: 8/8 (100%)

---

## Phase 2: 核心业务 Packages（优先级 P0）

### 2.1 Investment Package

**Package**: `packages/investment`  
**状态**: ⏸️ 待重构  
**优先级**: P0

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | data_fetch_quote | ⏸️ | 简单 | 获取股票行情 |
| 2 | data_fetch_kline | ⏸️ | 简单 | 获取K线数据 |
| 3 | data_fetch_financial | ⏸️ | 中等 | 获取财务数据 |
| 4 | data_fetch_macro | ⏸️ | 中等 | 获取宏观数据 |
| 5 | data_fetch_north_flow | ⏸️ | 简单 | 获取北向资金流 |
| 6 | data_fetch_market_sentiment | ⏸️ | 中等 | 获取市场情绪 |
| 7 | pool_list | ⏸️ | 简单 | 股票池列表 |
| 8 | strategy_list | ⏸️ | 简单 | 策略列表 |
| 9 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/9 (0%)

### 2.2 Strategy Package

**Package**: `packages/strategy`  
**状态**: ⏸️ 待重构  
**优先级**: P0

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | strategy_execute | ⏸️ | 复杂 | 策略执行 |
| 2 | strategy_optimize | ⏸️ | 复杂 | 策略优化 |
| 3 | opportunity_scan | ⏸️ | 中等 | 机会扫描 |
| 4 | screening | ⏸️ | 中等 | 股票筛选 |
| 5 | rotation_proposal | ⏸️ | 中等 | 轮动建议 |
| 6 | rotation_simulate | ⏸️ | 中等 | 轮动模拟 |
| 7 | rotation_execute | ⏸️ | 复杂 | 轮动执行 |
| 8 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/8 (0%)

### 2.3 Market Package

**Package**: `packages/market`  
**状态**: ⏸️ 待重构  
**优先级**: P0

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | market_style_detect | ⏸️ | 中等 | 市场风格检测 |
| 2 | sector_analysis | ⏸️ | 中等 | 板块分析 |
| 3 | chip_analysis | ⏸️ | 中等 | 筹码分析 |
| 4 | regime_daily | ⏸️ | 中等 | 每日市场状态 |
| 5 | mainline_scan | ⏸️ | 中等 | 主线扫描 |
| 6 | mainline_stocks | ⏸️ | 简单 | 主线股票 |
| 7 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/7 (0%)

### 2.4 Risk Package

**Package**: `packages/risk`  
**状态**: ⏸️ 待重构  
**优先级**: P0

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | risk_controller | ⏸️ | 复杂 | 风险控制器 |
| 2 | risk_metrics | ⏸️ | 中等 | 风险指标 |
| 3 | risk_barra_decomposition | ⏸️ | 复杂 | Barra 风险分解 |
| 4 | regime_position_limit | ⏸️ | 中等 | 市场状态仓位限制 |
| 5 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/5 (0%)

---

## Phase 3: 智能增强 Packages（优先级 P1）

### 3.1 Lifecycle Package

**Package**: `packages/lifecycle`  
**状态**: ⏸️ 待重构  
**优先级**: P1  
**工具数**: 约 16 个（最多）

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | self_restart | ⏸️ | 复杂 | 自修复重启 |
| 2 | self_finalize | ⏸️ | 复杂 | 完成自修复 |
| 3 | window_create | ⏸️ | 中等 | 创建窗口 |
| 4 | window_close | ⏸️ | 简单 | 关闭窗口 |
| 5 | window_list | ⏸️ | 简单 | 窗口列表 |
| 6 | window_switch | ⏸️ | 中等 | 切换窗口 |
| 7 | board_update | ⏸️ | 中等 | 更新看板 |
| 8 | board_read | ⏸️ | 简单 | 读取看板 |
| 9 | board_post | ⏸️ | 简单 | 发布看板消息 |
| 10-16 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/16 (0%)

### 3.2 Learning Package

**Package**: `packages/learning`  
**状态**: ⏸️ 待重构  
**优先级**: P1  
**工具数**: 约 9 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | experience_add | ⏸️ | 中等 | 添加经验 |
| 2 | experience_search | ⏸️ | 中等 | 搜索经验 |
| 3 | experience_evolve | ⏸️ | 复杂 | 进化经验 |
| 4 | lesson_learn | ⏸️ | 复杂 | 学习教训 |
| 5 | pattern_recognize | ⏸️ | 复杂 | 模式识别 |
| 6-9 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/9 (0%)

### 3.3 Intelligence Package

**Package**: `packages/intelligence`  
**状态**: ⏸️ 待重构  
**优先级**: P1  
**工具数**: 约 5 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | opponent_analysis | ⏸️ | 复杂 | 对手分析 |
| 2 | game_state_detect | ⏸️ | 复杂 | 博弈状态检测 |
| 3 | trap_detection | ⏸️ | 复杂 | 陷阱检测 |
| 4 | opportunity_exploit | ⏸️ | 复杂 | 机会利用 |
| 5 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/5 (0%)

### 3.4 Evolution Package

**Package**: `packages/evolution`  
**状态**: ⏸️ 待重构  
**优先级**: P1  
**工具数**: 约 3 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | evolution_report | ⏸️ | 中等 | 进化报告 |
| 2 | evolution_trigger | ⏸️ | 复杂 | 触发进化 |
| 3 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/3 (0%)

### 3.5 Evolver Package

**Package**: `packages/evolver`  
**状态**: ⏸️ 待重构  
**优先级**: P1  
**工具数**: 约 6 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | param_suggest | ⏸️ | 复杂 | 参数建议 |
| 2 | param_evaluate | ⏸️ | 复杂 | 参数评估 |
| 3 | param_apply | ⏸️ | 中等 | 应用参数 |
| 4-6 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/6 (0%)

### 3.6 Genome Package

**Package**: `packages/genome`  
**状态**: ⏸️ 待重构  
**优先级**: P1  
**工具数**: 约 6 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | genome_read | ⏸️ | 简单 | 读取基因 |
| 2 | genome_update | ⏸️ | 中等 | 更新基因 |
| 3 | genome_validate | ⏸️ | 中等 | 验证基因 |
| 4-6 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/6 (0%)

---

## Phase 4: 支撑系统 Packages（优先级 P2）

### 4.1 Memory Package

**Package**: `packages/memory`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | memory_search | ⏸️ | 中等 | 搜索记忆 |
| 2 | memory_write | ⏸️ | 简单 | 写入记忆 |
| 3 | memory_delete | ⏸️ | 简单 | 删除记忆 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.2 Factor Package

**Package**: `packages/factor`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 3 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | factor_compute | ⏸️ | 复杂 | 计算因子 |
| 2 | factor_backtest | ⏸️ | 复杂 | 因子回测 |
| 3 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/3 (0%)

### 4.3 Data Manager Package

**Package**: `packages/data-manager`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | data_status | ⏸️ | 简单 | 数据状态 |
| 2 | data_update | ⏸️ | 中等 | 数据更新 |
| 3 | data_clean | ⏸️ | 中等 | 数据清洗 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.4 Quantsys-V2 Manager Package

**Package**: `packages/quantsys-v2-manager`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | quantsys_v2_status | ⏸️ | 简单 | 后端状态 |
| 2 | quantsys_v2_logs | ⏸️ | 简单 | 后端日志 |
| 3 | quantsys_v2_restart | ⏸️ | 中等 | 重启后端 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.5 Agent-OS Manager Package

**Package**: `packages/agent-os-manager`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | agent_os_status | ⏸️ | 简单 | Agent OS 状态 |
| 2 | agent_os_health | ⏸️ | 简单 | 健康检查 |
| 3 | agent_os_logs | ⏸️ | 简单 | 日志查询 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.6 Window Manager Package

**Package**: `packages/window-manager`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 5 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | window_register | ⏸️ | 中等 | 注册窗口 |
| 2 | window_unregister | ⏸️ | 简单 | 注销窗口 |
| 3 | window_query | ⏸️ | 简单 | 查询窗口 |
| 4-5 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/5 (0%)

### 4.7 Model Package

**Package**: `packages/model`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | model_switch | ⏸️ | 简单 | 切换模型 |
| 2 | model_status | ⏸️ | 简单 | 模型状态 |
| 3 | model_config | ⏸️ | 简单 | 模型配置 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.8 Notification Package

**Package**: `packages/notification`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | notify_send | ⏸️ | 简单 | 发送通知 |
| 2 | notify_config | ⏸️ | 简单 | 通知配置 |
| 3 | notify_history | ⏸️ | 简单 | 通知历史 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.9 Competition Package

**Package**: `packages/competition`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 4 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | retail_sentiment | ⏸️ | 中等 | 散户情绪 |
| 2 | institution_flow | ⏸️ | 中等 | 机构资金流 |
| 3 | hot_money_trace | ⏸️ | 中等 | 游资追踪 |
| 4 | (其他工具待确认) | ⏸️ | - | - |

**进度**: 0/4 (0%)

### 4.10 Scheduler Package

**Package**: `packages/scheduler`  
**状态**: ⏸️ 待重构  
**优先级**: P2  
**工具数**: 约 2 个

| # | 工具名 | 状态 | 复杂度 | 说明 |
|---|--------|------|--------|------|
| 1 | schedule_list | ⏸️ | 简单 | 调度列表 |
| 2 | schedule_trigger | ⏸️ | 简单 | 触发调度 |

**进度**: 0/2 (0%)

---

## 统计汇总

### 按阶段统计

| 阶段 | Packages | 工具总数 | 已完成 | 进行中 | 待重构 | 完成率 |
|------|----------|----------|--------|--------|--------|--------|
| Phase 1 | 1 | 8 | 8 | 0 | 0 | 100% |
| Phase 2 | 4 | 29 | 0 | 0 | 29 | 0% |
| Phase 3 | 6 | 45 | 0 | 0 | 45 | 0% |
| Phase 4 | 10 | 38 | 0 | 0 | 38 | 0% |
| **总计** | **21** | **120** | **8** | **0** | **112** | **6.7%** |

### 按复杂度统计

| 复杂度 | 数量 | 占比 | 说明 |
|--------|------|------|------|
| 简单 | ~50 | 42% | 直接 API 调用，简单参数校验 |
| 中等 | ~45 | 37% | 需要业务逻辑处理 |
| 复杂 | ~25 | 21% | 包含多个业务规则、复杂编排 |

### 按优先级统计

| 优先级 | Packages | 工具数 | 完成数 | 完成率 |
|--------|----------|--------|--------|--------|
| P0 | 5 (含 Trading) | 37 | 8 | 21.6% |
| P1 | 6 | 45 | 0 | 0% |
| P2 | 10 | 38 | 0 | 0% |

---

## 重构进度追踪

### 本周目标（Week 1）
- [ ] Investment Package (9 工具)
- [ ] Strategy Package (8 工具)
- [ ] Market Package (7 工具)
- [ ] Risk Package (5 工具)

### 下周目标（Week 2）
- [ ] Lifecycle Package (16 工具)
- [ ] Learning Package (9 工具)
- [ ] Intelligence Package (5 工具)

### 未来计划
- Week 3: Evolution, Evolver, Genome
- Week 4: 支撑系统 Packages

---

## 更新日志

### 2026-08-28
- 创建工具清单文档
- 完成 Phase 1: Trading Package (8/8)
- index.ts 从 554 行缩减到 92 行（83% 缩减）
- 创建 REFACTOR_GUIDE.md 和 REFACTOR_PLAN.md

---

**维护说明**:
- 每完成一个工具，更新对应状态为 ✅ 并填写完成日期
- 每开始重构一个工具，更新状态为 🔄
- 定期更新统计数据

---

**参考文档**:
- [重构总计划](REFACTOR_PLAN.md)
- [Trading Package 重构指南](packages/trading/REFACTOR_GUIDE.md)
- [Trading Package 测试指南](packages/trading/TESTING_GUIDE.md)
