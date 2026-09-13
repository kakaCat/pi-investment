---
id: guide-trading-constraints
title: 交易约束速查
type: guide
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [guide, trading, constraints]
---

# 交易约束速查

**这页回答**：下单前要过的硬约束，一张表查完（完整纪律见 [账户与交易纪律](../standards/account-and-trading.md)）。

## 硬约束（宪法层，不可越）

| 约束 | 阈值 | 说明 |
|---|---|---|
| 交易时段 | 9:30-11:30 / 13:00-15:00（A股交易日） | 其余时间只能分析与复盘，禁下单 |
| T+1 | 当日买入次日才可卖 | 卖出前看 `position_list.shares_available` |
| 最小单位 | 买入 100 股整数倍 | — |
| 单股上限 | ≤ 总资产 20% | — |
| 单行业上限 | ≤ 总资产 40% | — |
| 现金下限 | ≥ 总资产 10% | 隐含权益恒 ≤90% |
| 止损铁律 | 蓝筹 -8% / 成长 -10% / 小盘题材 -12% | 触及必须卖，不补仓不摊平 |
| 服务端总仓硬顶 | 80%（trade_guard） | 与上面三者冲突时**取最严值** |

## regime → 权益仓位上限（R-006）

| regime | 上限 | | regime | 上限 |
|---|---|---|---|---|
| 恐慌 panic | ≤100% | | 偏空 risk_off | ≤40% |
| 偏多 risk_on | ≤80% | | 狂热 euphoria | ≤30% |
| 震荡 sideways | ≤60% | | 数据降级/矛盾 | 按震荡档（60%）保守执行 |

实际可用额度以 `regime_position_limit` 返回为准（含 `verdict` 与 `headroom_pct`），**不凭感觉**。

## 下单前后动作

| 时点 | 动作 |
|---|---|
| 买入前 | `data_fetch_quote`（实时价）→ `account_info`（可用资金）→ `regime_position_limit`（额度，verdict 须 compliant）→ `risk_controller position_size` |
| 卖出前 | `position_list`（shares_available）→ `risk_controller stop_loss`（止损价） |
| 下单 | `portfolio_trade`（**必填 reason**：规则 ID + 理由 + 检索结论）；大额（>日均成交额 1%）拆单 |
| 下单后 | `trade_monitor`（成交/挂单）→ 盘后 `trade_verify` 对账；异常挂单 `cancel_pending_order`（也要 reason） |
| 开仓后 | 挂止损盯盘规则（`watch_manage`，带 account） |

## 依据

宪法（交易宪法段）与 R-001 / R-002 / R-003 / R-006 / R-007（回撤熔断 -8%）。

## 相关页面

- [账户与交易纪律](../standards/account-and-trading.md) · [账户模型与边界](../architecture/accounts-and-boundaries.md)
- [交易执行协议](../protocols/trade-execution-protocol.md)
