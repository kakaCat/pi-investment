# 需求文档修订记账（2026-10-06 · design 阶段）

## 事件

`requirement.md` 在 brainstorming 阶段经人确认落章、并推进到 design 之后，**又被修改过一次**，
但这次修改**无法经 `reqboard_submit(kind=requirement, change_note=…)` 留痕**——工具按状态拒绝：

```
Error: reqboard_requirement_submit 未执行：需求当前处于 design，
       需求文档只能在 brainstorming 阶段提交（回到需求分析重新提交会作废既有确认）
       （REQBOARD_BAD_STATUS）
```

**处置**：不绕过闸门（不回退状态、不假装走过 change_note 通道），改为在本文件如实记账。
产物按**路径**登记，故评审人打开 `requirement.md` 看到的就是修订后的版本。

## 改了什么（仅「判定标准（可跑）」一节，正文与 D-x 未改）

| # | 原文 | 改为 | 为什么 |
|---|---|---|---|
| 1 | `pytest tests/test_risk_metrics_service.py -k nav_returns -v` | `pytest tests/test_nav_series.py tests/test_equity_snapshot_daily_return.py -q` | **原命令指向的文件不存在**（实测：`nav_returns_from_snapshots` 的既有测试在 `tests/test_equity_snapshot_daily_return.py`）。判定标准挂不可执行的命令＝验收无法复核，属实质缺陷 |
| 2 | `pytest tests/ -k "snapshot and trading_day" -v` | `pytest tests/test_equity_snapshot_trading_day_gate.py -q` | `-k` 模糊过滤会随测试文件增删漂移；改为指向本需求新建的具名文件 |
| 3 | 休市日样例 `2026-10-02 / 2026-10-07` | `2026-09-05`（周六）/ `2026-10-02`（国庆） | `10-07` 是**未来日**（`TradingDayGuard` 判 `source='future'`），当下跑不到；换成已取证的两个日期，判据当天即可执行 |
| 4 | 判据 5 的 SQL 无注解 | 补注「判据用 `is not true`（更严）；删除只用 `is_trading_day = false`（防日历缺行误删）」 | 两处 SQL 谓词**故意不同**，不注解会被读成口径矛盾（设计见 `design/data-model.md` §3） |

## 未改的部分

需求边界、FR-1~FR-8、D-1~D-5、取证 E1~E7 与反向证据 R1~R3 全部保持确认时原样；
本次修订不改变任何条款语义，只让判定标准**可执行**。

## 残留风险

本次修订的**内容**未经人重新确认（工具不允许在该阶段重提）。若评审认为"判定标准变更也算实质变更"，
请在 design 确认门里提出——届时可退回 brainstorming 重走需求确认（会作废既有确认，需重新批准）。
