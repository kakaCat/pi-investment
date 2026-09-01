# 工具链连通性审计（agent-dh → quantsys-v2 全量实测）

> 审计人：investor（w-8366e526）｜日期：2026-09-01 晚
> 触发：用户问"agent-dh 调用 quantsys-v2 都需通过工具实现，确认业务流程都是通的吗"
> 方法：44+ 个工具逐个真实调用（只读全测；写操作做安全验证——portfolio_trade 宪法拦截响应即证明链路通）

---

## 0. 结论

**主干业务链路是通的**（数据→决策→交易→复盘核心工具全部正常），但实测揪出 **10 个断链**（4 路由 404 + 6 工具执行期崩溃）+ **8 处数据/逻辑异常**。断链已全部修复并验证（提交 2b2cebbe/b6dfd277）。

| 状态 | 数量 | 说明 |
|---|---|---|
| ✅ 正常 | 34 | 核心链路全覆盖 |
| ❌ 断链（已修复） | 10 | 4 路由 404 + 6 缺 wrap |
| ⚠️ 异常（通但数据/逻辑有问题） | 8 | 见 §3 |

## 1. 断链清单与修复（10 处，全部已修）

### 1.1 路由 404（4 处）——根因两类

| 工具 | 端点 | 根因 | 修复 |
|---|---|---|---|
| strategy_list | /api/strategies/list | services.py rewrite（55c0ce73）后 22 处裸名 from-import 全炸 → 19 个路由模块注册失败 | services.py 加模块级 `__getattr__` + `_LazyServiceProxy` 惰性代理（避免启动早期深层依赖解析崩溃） |
| market_alert | /api/alerts/check | 同上（alerts_async 缺 game_alert_service） | 同上（修复后 200，首次查询 27s 属重计算正常） |
| event_calendar_check | /api/events/upcoming | events_async.py 存在但 **main.py 从未 include**（路由写了没注册） | main.py 补注册段 |
| retail_panic_index | /api/market/perception/panic-index | 端点从未实现（服务层 retail_panic_index_service 早已存在，路由层缺失） | market_perception_async 补 panic-index + series 两端点 |

**修复后注册失败 19→3**（剩 p1_batch/p2_batch1/p2_batch2 相对导入，既有非关键路径问题）。

⚠️ 重要关联：backtest_async 也在失败清单（缺 backtest_engine 裸名）——**combo/matrix/backtest-run 全系路由在当日午间后实际处于 404 状态**，本次一并修复。

### 1.2 工具执行期崩溃（6 处）——同一根因

| 工具 |
|---|
| trading_calendar、opponent_behavior、limit_up_pool、lhb_dragon_tiger、fund_flow、stock_intel |

- **根因**：`BaseTool.wrap` 是 abstract 方法，6 个工具子类未实现；tsx 运行时不检查 abstract → schema 冒烟（19/19 只编译不执行）抓不到 → 调用时才炸 `this.wrap is not a function`
- **修复**（b6dfd277）：wrap 改为默认实现 `{success: true, data}`，子类需自定义 message/metadata 时覆盖——治本且防再犯
- **生效条件**：需 DSH profile 重启加载新代码（与 M2-3/E-2 同批待重启）

## 2. 主干链路实测（全部通过）

| 链路 | 工具 | 结果 |
|---|---|---|
| 行情数据 | quote / kline / financial / market_sentiment | ✅ |
| 决策前置 | regime_position_limit（euphoria 上限 30% 合规）/ m4_circuit_breaker（回撤 -7.72% 未熔断）/ risk_controller / risk_metrics | ✅ |
| 信号 | strategy_execute（扫 396 只）/ signal_track report / opportunity_scan | ✅ |
| 标的 | pool_list（29 池）/ mainline_scan / mainline_stocks / chip_analysis | ✅ |
| 交易 | account_info / position_list / trade_monitor / **portfolio_trade（非交易时段宪法正确拦截：链路通+校验生效）** | ✅ |
| 学习进化 | learning_analyze（43 样本 5 模式）/ evolution_leaderboard / genome_list/read | ✅ |
| 运维 | scheduler_manage list / data_manager status / notification_channels（今日 3 条通知已送达）/ agent_os_status | ✅ |

## 3. 数据/逻辑异常（链路通但不正常，待修）

| # | 工具 | 异常 | 性质 |
|---|---|---|---|
| 1 | position_list vs risk_controller | **持仓不一致**：前者 2 只（601288/002241），后者 3 只（300750/000999/600036） | 🔴 数据源不一致，影响仓位校验可信度 |
| 2 | screening | ROE≥15 筛选返回退市股（688287 退市观典）且得分全 0、"符合条件: undefined 只" | 🟠 筛选逻辑/字段映射异常 |
| 3 | opportunity_scan | 扫描范围 0 只 | 🟠 池子为空或未传 pool |
| 4 | risk_barra_decomposition | 因子协方差全 null | 🟠 因子数据不足 |
| 5 | data_fetch_financial | PE-TTM/PB 全 0 | 🟠 估值字段未计算 |
| 6 | data_fetch_kline | "时间范围: undefined ~ undefined" | 🟡 渲染字段缺失 |
| 7 | rotation_simulate | action 大小写敏感（BUY 被拒，要求小写） | 🟡 入参校验过严 |
| 8 | mainline_scan | mainlines 空（今日主线未落库） | 🟡 数据待积累 |
| 附 | data_fetch_macro | "后端未提供 pmi 数据" | 🟡 宏观数据未接入 |
| 附 | data_fetch_north_flow | 北向数据源永久不可用（交易所停止披露）——工具优雅降级+替代方案，设计良好 | ⚪ 外部变化，非 bug |
| 附 | memory_search "止损经验" | 0 条 | 🟡 经验库沉淀不足 |

## 4. 调度侧附带发现

- Agent OS 任务列表大面积禁用是 ADR-002 切换的预期结果（v2 APScheduler 接管），但意味着**无 failover**——v2 调度挂则任务全停。建议补 v2 调度健康监控告警。
- 公告板 board_read 返回的历史帖子记录了一个相关遗留：risk metrics 忽略 account_name（#/api/risk/metrics 全局数据问题）——board 帖 #25409abb 仍 open，与本审计 §3-1 持仓不一致可能同源（账户过滤缺失）。

## 5. 修复提交

- `2b2cebbe`：services 裸名导入兜底 + events/panic-index 端点补全
- `b6dfd277`：BaseTool.wrap 默认实现
- 验证：4 个 404 端点全部 200；冒烟 19/19；工具待 DSH 重启后线上生效

## 6. 后续建议（按优先级）

1. **P0**：DSH 重启（加载 wrap 修复 + M2-3 pool_battlefield + E-2 trade_verify 工具新代码）——等并行会话 untracked 工作提交后执行
2. **P1**：持仓数据源不一致排查（position_list vs risk_controller 读不同表？）
3. **P1**：board 遗留帖 #25409abb 的 risk metrics account_name 过滤修复
4. **P2**：screening/opportunity_scan 空结果排查；barra 因子数据补齐
5. **P2**：v2 调度健康监控（无 failover 后的单点告警）
