---
id: std-account-and-trading
title: 账户与交易纪律（边界 / 下单前检查 / reason）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, trading, accounts]
---

# 账户与交易纪律

**这页回答**：动钱之前必须满足什么；账户名从哪来。

## 结论先行

1. **账户的唯一事实源是 `profileDir/agents.json` 的 `instance.account`**（agent 条目可用 `account` 覆盖）。
   **账户名不得写死在任务/提示词/代码里**——换账户只改一处。本实例自有账户为 `agent_brain`；
   `agent_virtual` 属 agent-ts（**只读不写**）；`v13/v14/v15/chip_simulation` 属定时策略线。
2. **买入前四件套（R-001）**：`data_fetch_quote` 确认价格 → `account_info` 确认可用资金 →
   `regime_position_limit` 确认额度与余量（verdict 须 compliant）→ `risk_controller position_size` 算仓位。
3. **卖出前两件套（R-002）**：`position_list` 确认 `shares_available`（T+1）→ `risk_controller stop_loss` 算止损价。
4. **`reason` 必填（R-005）**：引用规则 ID + 一句话理由（含决策前检索结论，R-008）。
   没有依据的单子不打。
5. **硬约束（宪法层，不可越）**：交易时段 9:30-11:30 / 13:00-15:00；T+1；买入 100 股整数倍；
   单股 ≤20%、单行业 ≤40%、现金 ≥10%；止损档位（蓝筹 -8% / 成长 -10% / 小盘题材 -12%）；
   regime 仓位上限与三重钳制取**最严值**（R-006）。

## 关键机制

- 撮合与风控在后端：`portfolio_trade` 走 trade_guard（总仓硬顶 80%）；盘前挂单
  `execute_at: 'market_open'` 在 9:31 起撮合；重复挂单需 `allow_duplicate`（先 `trade_monitor` 核对）。
- 撤单也要留 `reason` 与 `decision_audit`；成交后 `trade_verify` 对账。
- 大额订单（>该股日均成交额 1%）用 `algo_execute` 拆单——⚠️ 该工具当前**只生成切片计划不真下单**，
  需真实成交请分批 `portfolio_trade`。

## 依据

- R-019 事故：工具层曾把 `agent_virtual` 硬编码为默认账户 → agent-dh 的例行任务在**别人的账**上下单 23 笔；
- 数据冻结期的假熔断（见数据规范）；
- 宪法与 R-001/R-002/R-005/R-006/R-009 原文（系统提示词基因组段）。

## 自检清单

- [ ] 账户名是从身份段/工具默认值来的，还是我写死的？
- [ ] 买入前四件套 / 卖出前两件套都跑了吗？额度 verdict 是 compliant 吗？
- [ ] `reason` 里有规则 ID 与检索结论吗？
- [ ] 现在是不是合法交易时段？T+1 可卖数量够吗？

## 相关页面

- [数据与降级规范](data-and-degradation.md)
- [工具开发规范](tool-development.md)
- [下单 API 指南](../guides/order-api-guide.md)
- [交易执行协议](../protocols/trade-execution-protocol.md)
