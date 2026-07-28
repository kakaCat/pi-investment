# PI Investment Agent — 系统自评报告

> 评估日期：2026-07-25 | 评估者：Agent 自我审计

---

## 1. 执行摘要

### 系统成熟度评分：58/100

| 维度 | 得分 | 评级 |
|------|:----:|------|
| 数据管道（L1） | 65 | ⚠️ 仅A股，港股/US/期货缺失 |
| 因子工厂（L2） | 78 | ✅ 163因子 + IC分析 + 分层回测 |
| 策略系统（L3） | 72 | ⚠️ 工具完备但MECE有重叠 |
| 组合/风控（L4-L5） | 60 | ⚠️ 风控偏弱，缺压力测试 |
| 执行/监控（L6-L7） | 55 | ⚠️ 虚拟仓，无真实执行链路 |
| 博弈智能 | 65 | ✅ 三个博弈工具，但数据源依赖单一 |
| 自我进化 | 45 | ⚠️ 有evolution框架但TODO未填实 |
| 前端监控 | 50 | ⚠️ 多页面但大量TODO路由 |

### 🔴 三大最紧迫问题

1. **港股/多市场盲区** — 12+ 工具硬编码"仅支持A股"，港股、美股、期货、ETF、可转债完全空白，损失大量交易机会
2. **执行链路缺失** — 从策略信号 → 风控 → 下单 只有虚拟仓，没有真实券商API对接，无法闭环收益
3. **LLM 上下文瓶颈** — DeepSeek-chat 仅 64K 窗口/8K 输出，60+ 工具定义占大量token，留给推理的空间严重不足

---

## 2. 架构逐层审计

### L1 数据管道层

| 工具 | 覆盖 | 问题 |
|------|------|------|
| `data_fetch_quote` | A股实时行情 | ⚠️ 仅A股，5数据源但 fallback 策略不透明 |
| `data_fetch_kline` | A股日/周/月线 | ⚠️ 仅A股，无分钟线（indicator_backtest支持但data_fetch_kline不支持） |
| `data_fetch_financial` | A股财务报表 | ⚠️ 仅A股，PE分位依赖数据库有足够历史 |
| `data_fetch_dividend` | A股分红数据 | ✅ 三种模式完备 |
| `data_fetch_macro` | 宏观经济 | ⚠️ 依赖akshare单数据源，无failover |
| `data_fetch_north_flow` | 北向资金 | ⚠️ 仅存量资金，无实时板块资金流 |
| `data_fetch_market_sentiment` | 市场情绪 | ⚠️ 输出为定性描述，无定量恐慌/贪婪指数 |
| `data_manager` | 数据管理 | ⚠️ 后台任务，前端不可见 |
| `data_quality_report/manage` | 数据质量 | ✅ 检测+回填成熟 |

**L1 评分：65/100**

**核心缺陷**：
- 全市场 A 股垄断，无跨市场数据
- 没有 ETF/LOF/可转债 数据（A股重要的交易品种）
- 没有 Level 2 行情（逐笔成交、十档盘口）
- 宏观数据仅 akshare 单源

---

### L2 因子工厂层

| 工具 | 功能 | 状态 |
|------|------|:--:|
| `factor_calculate` | 163因子批量计算 | ✅ |
| `factor_analyze` | alphalens专业IC分析 | ✅ |
| `factor_layering_backtest` | 分层回测 | ✅ |
| `batch_factor_layering_backtest` | 批量分层 | ✅ |
| `factor_list` | 因子清单 | ✅ |
| `factor_correlation` | 相关性矩阵 | ✅ |
| `factor_portfolio_optimize` | 因子组合优化 | ✅ |
| `factor_ic_monitor` | IC衰减监控 | ✅ |

**L2 评分：78/100**（系统最强层）

**优势**：
- 163因子覆盖全面（含TA-Lib C实现，性能优秀）
- alphalens-reloaded专业分析
- 从因子计算→分析→分层→组合优化→监控 形成完整闭环

**缺陷**：
- 因子全部为技术面，缺基本面因子（如 Piotroski F-Score、Beneish M-Score、Altman Z-Score）
- 无另类数据因子（新闻情绪NLP、供应链关系图、卫星图像）
- `factor_analyze` 生成 HTML 报告但 agent 看不到图表（只能读文字）

---

### L2.5-L2.8 机会雷达 & 股票池

| 工具 | 功能 | 问题 |
|------|------|------|
| `opportunity_scan` | 三维评分（技术+基本面+资金） | ✅ 三种权重模式 |
| `analysis_swing_points` | ZigZag波段 | ✅ |
| `realtime_signal_scan` | 实时信号 | ⚠️ 依赖策略预先注册 |
| `pool_manage` | 股票池CRUD | ✅ 静态+动态+scan_signals |
| `pool_validate` | 多策略批量验证 | ⚠️ 大数据量时慢 |

**缺口**：
- `opportunity_scan` 与 `screening` 功能重叠（都有行业/质量过滤）
- 股票池没有"自动止损触发→移出池"的联动

---

### L3 策略&模型层

| 子层 | 工具数 | 覆盖 |
|------|:--:|------|
| 策略管理 | 9 (list/detail/write/execute/status/optimize/batch_validate/delete/discovery) | ✅ 完备 |
| 指标管理 | 6 (list/detail/create/update/delete/backtest) | ✅ 完备 |
| ML模型 | 7 (train/predict/evaluate/monitor/list/calibrate/reports) | ✅ 完备但使用率存疑 |

**L3 评分：72/100**

**关键问题**：

1. **策略/指标双轨制混淆** — `strategy_*` 和 `indicator_*` 两套工具在底层操作同一张 `indicators` 表。agent 容易产生困惑："我的RSI策略该用 strategy_write 还是 indicator_update?"
2. **ML 模型使用率低** — 7个ML工具存在但 `model_predict` 文档注明"⚠️ 低置信度"。如果模型不可靠，7个工具就是死代码
3. **`strategy_write` 代码安全性** — 允许任意 Python 代码执行，无沙箱隔离。恶意或错误的策略代码可导致后端崩溃
4. **`strategy_discovery` 参数空间爆炸** — "每个原型30个参数组合 × N个原型 × M只股票" 容易超时

---

### L4-L5 组合&执行层

| 工具 | 功能 | 成熟度 |
|------|------|:--:|
| `portfolio_optimizer` | 权重优化（5种方法） | ⚠️ 缺真实约束（最小交易单位、停牌处理） |
| `portfolio_trade` | 虚拟仓交易 | ⚠️ 无真实券商对接 |
| `portfolio_status/analyze/account` | 虚拟仓管理 | ✅ 功能完备 |
| `trade_algo_execute` | TWAP/VWAP | ⚠️ 仅算法建议，无执行 |
| `trade_monitor/verify` | 交易监控 | ⚠️ 仅虚拟仓数据 |
| `signal_execution` | 信号执行 | ⚠️ 触发→执行链路不完整 |

**L4-L5 评分：60/100**

**核心缺陷**：
- **虚拟仓闭环但无真金白银** — 最完整的 `portfolio_*` 体系都在虚拟账户，没有华泰/XTP/QMT 等券商API对接
- **无 OMS（订单管理系统）** — 订单状态机、撤单、改单、滑点管理全部缺失
- **无真实持仓同步** — 不能用真实持仓校准虚拟仓

---

### L6 监控&风控层

| 工具 | 功能 | 问题 |
|------|------|------|
| `monitor_alert` | 告警通知 | ⚠️ feishu channel 未完整实现 |
| `watch_manage` | 实时盯盘规则 | ✅ 价格/涨跌幅/盈亏/量能 |
| `watch_price_alert` | 价格预警 | ✅ |
| `risk_controller` | 风控检查/仓位/止损 | ✅ |
| `risk_metrics` | empyrical 8指标 | ✅ |
| `risk_barra_decomposition` | Barra风险分解 | ✅ |
| `schedule_next_check` | 盯盘间隔 | ⚠️ max 60分钟 |

**L6 评分：55/100**

**关键缺口**：
- **缺压力测试** — 没有 "如果大盘跌10%会怎样" 的情景分析
- **缺实时风控阻断** — watch_manage 只能"通知"，不能"阻止交易"
- **监控告警不可靠** — feishu 通知有大量 TODO 未实现
- **schedule_next_check 上限60分钟** — 午休11:30-13:00 需要手动设置

---

### 博弈智能层

| 工具 | 功能 | 状态 |
|------|------|:--:|
| `opponent_behavior` | 对手行为分析 | ✅ |
| `pool_battlefield` | 池子战场评估 | ✅ |
| `manipulation_detect` | 操纵检测 | ✅ |
| `market_style_detect` | 市场风格检测 | ✅ |

**博弈层评分：65/100**

**优势**：这是系统的差异化能力——大多数量化系统不做博弈分析

**缺陷**：
- 所有博弈数据依赖 quantsys-v2 后端单一数据源
- 缺乏 "对手仓位估算"（需要从龙虎榜/融资融券/大宗交易推算）
- `manipulation_detect` 依赖的模式库有限（拉高出货一种模式）
- 博弈分析结果未反馈回策略权重调整

---

### 自我进化 & 元学习

| 工具 | 状态 |
|------|:--:|
| `evolution_run` | ⚠️ 框架存在但 `evolution-service.ts` 含多个 TODO |
| `experience_write` / `query_experience` | ✅ 功能可用但经验库规模未知 |
| `calibrate_confidence` | ⚠️ 仅对技术指标做IC分析 |
| `decision_record` / `decision_history` | ✅ 审计轨迹完备 |

**元学习评分：45/100**

**核心问题**：
- `evolution_run` 调用后实际改了什么？无验证机制
- 经验的 `recommendation` 从 aggressive→avoid 四个等级，但 agent 真正采纳经验建议的机制不明确
- 缺少 A/B 测试框架：无法验证"新参数是否比旧参数更好"

---

## 3. 全系统约束清单

### 硬编码限制（影响决策质量）

| 约束 | 影响范围 | 严重度 |
|------|---------|:--:|
| ❌ 港股数据不可用 | fetch_quote, fetch_kline, fetch_financial, factor_calculate, model_predict, indicator_backtest 等 12+ 工具 | 🔴 |
| ❌ 美股/期货/期权/ETF/可转债 完全缺失 | 所有工具 | 🔴 |
| ❌ DeepSeek-chat 64K 上下文窗口 | 60+工具定义 + system prompt 占 30K+，留给分析仅 30K | 🟡 |
| ❌ DeepSeek-chat 8K max_tokens 输出 | 深度分析报告可能被截断 | 🟡 |
| ❌ 仅处理单一工具调用（tool_choice="auto"） | 无法并行调用工具，每次只能一个 | 🟡 |
| ⚠️ factor_calculate 仅A股校验 | 港股因子无法计算 | 🟡 |
| ⚠️ indicator_backtest 仅A股验证（但参数描述说支持港股） | 矛盾——参数说支持但运行时拒绝 | 🟡 |
| ⚠️ schedule_next_check 最大60分钟 | 午休超长时间需手动分段 | 🟢 |

### 工具冗余/重叠

| 重叠组 | 工具 | 建议 |
|--------|------|------|
| 策略 vs 指标 | `strategy_write` / `indicator_create` | 合并为单一入口 |
| 机会扫描 vs 筛选 | `opportunity_scan` / `screening` | screening 合并到 opportunity_scan |
| 风险分析 | `risk_metrics` / `risk_controller` / `risk_barra_decomposition` | 工具职责清晰但 agent 容易选错 |
| 因子分析 | `factor_analyze` / `factor_layering_backtest` / `factor_academic` | 三个工具都在分析因子，入口分散 |
| 回测 | `indicator_backtest` / `strategy_execute` / `pool_validate` / `strategy_combo_backtest` | 4个回测入口，agent 选哪个？ |

---

## 4. 管道集成分析

### 完整交易链路测试

```
screening → opportunity_scan → strategy_execute → risk_controller 
  → portfolio_trade → trade_monitor → performance_analyzer → experience_write
```

| 步骤 | 状态 | 断点 |
|------|:--:|------|
| 筛选→机会扫描 | ✅ | screening 和 opportunity_scan 可串联 |
| 机会→策略执行 | ✅ | strategy_execute(single) 接受 symbol |
| 策略→风控 | ⚠️ | strategy_execute(pipeline) 有时间风控，但 risk_controller(trade_check) 需要手动调用 |
| 风控→下单 | ❌ | risk_controller 只返回建议，不自动调用 portfolio_trade |
| 下单→监控 | ⚠️ | trade_monitor 可查虚拟仓，但无实时推送 |
| 监控→绩效 | ✅ | performance_analyzer 可按策略查询 |
| 绩效→经验 | ⚠️ | 需手动调用 experience_write |

### 断链分析

**最大断点：风控→执行**。风控工具返回 "建议仓位 X%"，但 agent 需要解读这个建议然后手动调用 `portfolio_trade`。没有自动化的 "signal → check → execute" 原子操作。

**第二大断点：真实执行**。整个 `portfolio_trade` 链路都在虚拟仓，无法产生真实收益。这使系统停留在 "paper trading" 阶段。

---

## 5. 前端监控状态

| 页面 | 状态 | 问题 |
|------|:--:|------|
| Dashboard | ⚠️ | 数据来源不明确 |
| StockList/StockDetail | ⚠️ | 依赖 v2 API |
| PoolList/PoolDetail | ✅ | 较完整 |
| StrategyCenter/StrategyConfig | ⚠️ | 策略配置界面未完成 |
| IndicatorIDE | ✅ | 代码编辑器可用 |
| SimulationTrading | ⚠️ | 仅虚拟仓 |
| FactorAnalysis | ⚠️ | 因子分析可视化不足 |
| RiskCheck | ❓ | 未知完成度 |
| GameIntelligence | ❓ | 未知完成度 |
| Scheduler | ✅ | 任务管理可用 |
| 大量路由 | ❌ | TODO占位（training/portfolio/backtest/performance/pipeline/jobs/platform/features/charts/strategies/signals/stocks 全部未实现） |

**前端评分：50/100** — 页面框架存在，但大量后端路由是占位符，数据流不通。

---

## 6. 测试覆盖评估

| 指标 | 数值 | 评级 |
|------|:--:|:--:|
| TypeScript 测试文件 | 96 | ✅ |
| 核心业务逻辑测试 | ~30个 | ⚠️ |
| 工具集成测试 | ~20个 | ⚠️ |
| Python 后端测试 | ~40个 | ✅ |
| E2E 测试 | 0 | ❌ |
| 回测准确性验证 | 0 | ❌ |

**测试评分：55/100**

**最大风险**：
- **无 E2E 测试** — 无法验证完整投资链路
- **回测结果未交叉验证** — 没人确认过回测的收益率是否正确
- **大部分工具测试仅测格式不测逻辑** — `tool-response-format.test.ts` 这类测试不验证业务正确性

---

## 7. 综合诊断

### 系统强项

1. **因子体系完整** — 163因子 + alphalens + IC监控 + 分层回测，业界水准
2. **博弈智能差异化** — opponent_behavior/manipulation_detect 是真正差异化的能力
3. **策略开发工具体系化** — write→backtest→optimize→discovery 形成迭代闭环
4. **股票池管理体系** — 静态/动态/筛选建池 + validate + scan_signals，功能完整
5. **审计轨迹** — decision_record/decision_history 保证可追溯性

### 系统弱项

1. **仅A股，无跨市场** — 最严重的功能盲区
2. **无真实交易闭环** — 停留在 paper trading
3. **LLM 上下文瓶颈** — 64K窗口 vs 60+工具定义 = 推理空间不足
4. **大量 TODO/占位符** — web路由、feishu通知、evolution服务均未完成
5. **无E2E测试** — 无法信任回测结果准确性
6. **策略/指标双轨制** — agent 产生工具选择困惑

---

## 8. 优先级推荐路线图

### 🔴 短期（0-30天）— 修断链

| 优先级 | 任务 | 预期效果 |
|:--:|------|------|
| P0 | **合并 strategy_write/indicator_create** — 单一入口，底层自动判断 | 消除 agent 工具选择困惑 |
| P0 | **实现 strategy_execute(pipeline) → risk_controller → portfolio_trade 自动串联** | 补上最大断链 |
| P0 | **工具定义精简** — 对 agent 只暴露 30 个核心工具（用 skill 路由复杂工具） | LLM 推理空间释放 40% |
| P1 | **indicator_backtest 参数一致性修复** — 港股参数要么支持要么诚实报错 | 消除矛盾提示 |
| P1 | **evolution 核心逻辑补全** — 至少实现 "策略权重自动调整" 一个闭环 | self-improvement MVP |

### 🟡 中期（30-90天）— 拓市场

| 优先级 | 任务 | 预期效果 |
|:--:|------|------|
| P0 | **港股数据全链路打通** — quote/kline/financial/factor/backtest | 交易机会翻倍 |
| P1 | **ETF/可转债支持** — 先做 A 股 ETF（量最大、需求最刚） | 扩展交易品种 |
| P1 | **券商 API 对接（华泰XTP）** — 真实下单链路 | 从 paper trading 到 live trading |
| P2 | **压力测试框架** — "大盘跌10%"、"个股跌停" 情景模拟 | 补风控盲区 |
| P2 | **Level 2 行情** — 逐笔成交、十档盘口 | 增强博弈分析 |

### 🟢 长期（90天+）— 强智能

| 优先级 | 任务 | 预期效果 |
|:--:|------|------|
| P2 | **美股数据接入** — 打通美股 quote/financial/factor | 全球化 |
| P2 | **A/B 测试框架** — 自动验证新策略 vs 旧策略 | 量化自我进化 |
| P3 | **多模型 LLM 支持** — 切换大窗口模型做深度分析 | 解除上下文瓶颈 |
| P3 | **前端路由补全** — 实现占位路由，dashboard 可展示 | 可视化监控 |
| P3 | **E2E 测试框架** — 回测准确性自动化验证 | 信任基础 |

---

## 9. 对 deep-analysis 技能的影响

当前 deep-analysis 技能引用了已废弃的 `financial_cli` 和 `analysis_cli`（虽然有 fallback 标注），但实际执行中：

- **P2 估值** 完全依赖 `data_fetch_financial(pe_percentile)` — 如果数据库 PE 历史不足，整个 P2 报废
- **P3 技术分析** 依赖 `factor_calculate` — 如果当天 K 线数据未更新，RSI/MACD 都不可用
- **P4 ML预测** 文档标注 "⚠️ 低置信度" — 实际决策价值存疑
- **P6 风控** 没有工具级支持 — 止损/止盈价格全靠 agent 手动推算

**建议**：在 deep-analysis 技能中：
1. 删除所有 `financial_cli`/`analysis_cli` 引用（已有多处但不够彻底）
2. P6 增加对 `risk_controller(stop_loss)` 的调用
3. P4 增加对 `model_predict` 置信度的阈值判断（<0.6 则不采用 ML 信号）

---

## 附录A：工具统计

| 层级 | 工具数 | 核心 | 重复 | 实验性 |
|------|:--:|:--:|:--:|:--:|
| L1 数据 | 10 | 7 | 1 | 2 |
| L2 因子 | 10 | 8 | 1 | 1 |
| L2.5-L2.8 机会/池 | 6 | 5 | 1 | 0 |
| L3 策略/指标/ML | 22 | 18 | 3 | 1 |
| L4-L5 组合/执行 | 9 | 5 | 1 | 3 |
| L6 监控/风控 | 10 | 7 | 2 | 1 |
| 博弈智能 | 4 | 4 | 0 | 0 |
| 元工具/进化 | 12 | 8 | 1 | 3 |
| 分析/决策 | 8 | 6 | 1 | 1 |
| **总计** | **~91** | **68** | **11** | **12** |

> 注：91 个工具中包含 SDK 内置工具（read, plan, task, compact, browser, reflect 等），纯投资业务工具约 75 个。11 个存在功能重叠，12 个为实验性或未完成。

---

## 附录B：工具名称映射速查

本报告基于 `src/infrastructure/tools/index.ts` 中的工具注册顺序和描述分析，每个主张均有工具描述原文支持。
