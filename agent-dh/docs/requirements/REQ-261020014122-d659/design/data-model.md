# 数据模型（REQ-261020014122-d659）

> 本需求**无 DB 表/schema 变更**；以下为内存/JSON 契约层面的字段新增与口径声明。

## 字段变更清单 `serves: FR-2`

### `metrics` dict（run_backtest_from_signals 返回值，JSON 透传） `serves: FR-2`

| 字段 | 类型 | 必填 | 默认值 | 版本兼容 |
|---|---|---|---|---|
| `open_position_at_end` | bool | 恒存在 | `false` | 纯新增键；旧消费方忽略未知键即可 |
| `forced_closes` | int | 恒存在 | `0`（取值 0 或 1；int 预留多次扩展） | 纯新增键 |

### `trades[]` / `trade_records[]` 元素 `serves: FR-1, FR-2`

| 字段 | 类型 | 必填 | 说明 | 版本兼容 |
|---|---|---|---|---|
| `forced_close` | bool | 仅强制平仓条目出现，值恒 `true` | 标记该笔为窗口末计账平仓 | 普通条目不出现此键，旧报告字段形状不变 |

## 口径变更声明 `serves: FR-1, FR-2`

- **`total_trades` 新口径** =「发生过的往返交易数（含窗口末强制平仓）」；旧口径 =「恰好平仓的交易数」。变更方向只增不减。
- **生效时点**：本需求验收上线日。上线前历史报告与新口径**不可直接比较**；消费方只有 evolution MIN_TRADES 判据（:198/:223，语义不变、输入从此正确）与报表展示层，无下游持久化聚合需要回填。
- **告知落点**：本文件 + quantsys-v2 changelog 各记一笔即完成告知义务。
- **pnl 口径**：强制平仓条目不计卖出费用，与权益曲线（持仓按末日市值计入、未扣卖出费）对齐，保证 `sum(trades.pnl)` 与权益变动可对账。

## 迁移与回滚 `serves: FR-1, FR-2, FR-3`

- **数据回填**：无（无持久化变更）。
- **开关/灰度**：不需要——两个修复均为「错误→正确」的缺陷修复，无行为分叉需求。
- **回滚路径**：两侧均为纯代码变更，`git revert` 即可。agent-dh 侧 evolution 包为 **dist 加载**（package.json `main=./dist/index.mjs`），上线与回滚都必须走 `agent-dh/scripts/restart-with-build.sh`（构建 → 校验 dist 产物含新符号 → 重启）；quantsys-v2 侧重启服务进程生效。
