# M6-3 周报自动生成交付（2026-09-01）

> 署名：investor w-8366e526
> 状态：✅ 完成（M6 学习飞轮 4 工单全部完成，75%）

---

## 1. 现状盘点

M6-3 的"骨架"早已存在，本次补齐了**内容价值**与**验证闭环**：

| 组件 | 状态 | 说明 |
|------|------|------|
| WeeklyReportService | 已有 | generate_weekly_report / format_markdown / generate_and_push |
| 周报 API | 已有 | GET /api/reports/weekly（json/markdown）、/latest、POST /push |
| 自动调度 | 已有 | weekly-report-m6（周日 12:00，os-remind-bridge → Agent OS → 窗口会话） |
| **组合盈亏归因** | **本次新增** | 周报原只有"规则归因"（信号→规则胜率），缺"实际盈亏拆解" |

## 2. 本次改动

### 2.1 周报集成组合盈亏归因（M6-2 核心产出）

`WeeklyReportService.generate_weekly_report` 新增：
- `portfolio_attribution` 区块（调用 `AttributionService.analyze_portfolio_attribution(week_start, week_end)`）
- `summary` 新增 `realized_pnl` / `realized_trades` / `win_loss_ratio`
- `format_markdown` 新增 **💰 组合盈亏归因** 区块：本周已实现盈亏、止盈/止损贡献、决策分布、Top 5 标的、自动洞察

### 2.2 修复归因服务 2 个 bug（AttributeService.analyze_portfolio_attribution）

1. **日期过滤失效**：原 start_date/end_date 未传入 SQL，周报传周区间却返回全量（误导）→ 三张表（position_history/trades/simulation_trades）按 sell_date/trade_date 过滤
2. **连接复用崩溃**：方法 finally close 了 db 连接，第二次调用报 connection already closed → 改为只关 cursor（与 analyze_rule_performance 一致）

## 3. 验证结果

| 场景 | 结果 |
|------|------|
| 周区间 5/4-5/10 | +6986（2 笔止盈）✅ 不再是全量 52293 |
| 7 月 | +1469（1 笔）✅ |
| 8 月 | +7011（止盈 10179 / 止损 -3168）✅ |
| 全量 | +52293 / 9.07:1 ✅ 不回归 |
| 默认上周（8/24-8/30） | **-512 元（止盈2/止损3）**——自动暴露 8 月策略卖出亏损，印证归因报告 |

## 4. 周报新价值

周报现在自动回答三个问题：
1. **本周赚/亏多少钱**（realized_pnl）
2. **钱从哪来/去哪了**（止盈 vs 止损、Top 标的）
3. **有无规律性亏损**（自动洞察：集中度、最大亏损标的）

## 5. M6 学习飞轮收官

- M6-1 R-008 强制检索：✅（代码级嵌入 PortfolioTradeTool）
- M6-2 归因分析：✅（API 化 GET /api/learning/portfolio-attribution）
- M6-3 周报自动生成：✅（含组合盈亏归因）
- M6-4 evolution 常态化：✅（leaderboard + 优化验证 + regime 落地）

**M6 完成度：75%**（4/4 工单完成；剩余 25% 为 M6-3 周报首期自动触发的实战验收，待周日调度跑通后转 100%）
