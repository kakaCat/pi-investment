# 模拟盘自动买入阻塞修复（2026-10-29）

## 背景

`agent_brain` 长期现金接近满仓。当日核查发现总风控为 `fresh/compliant`，但今日计划的环境闸持续为 `skipped`。本窗口按用户要求只修复本实例模拟账户的信号到处置链，不开启全局信号执行，不修改其他账户授权。

## 复现与根因

- 2026-10-29 18:46 实测：市场宽度日 K 仅 35 只（8 涨 / 26 跌 / 1 平），触发 `coverage` 降级；资金氛围整维 `skipped`，计划视图显示 `数据缺失（fail-open 放行）`。
- 同一时刻多源最近交易快照可用：新浪 5576 只（781 涨 / 4727 跌 / 68 平），但原 `_get_advance_decline_ratio()` 只在盘中回源，盘后/盘前不使用该快照。
- `EnvironmentGateService` 将 `tuple("capital.sentiment_degraded")` 错写成逐字符序列。
- 入场唤醒模板只问“是否建仓”，没有要求激活计划触发后完成执行核验，容易以“继续观察”收尾。

## 修改

1. `MarketSentimentService._get_advance_decline_ratio()`：日 K 缺失或样本 `<1000` 时，盘后/盘前也回退到多源最近交易快照；实时源失败保留小样本并交由既有 coverage 守卫显式降级；盘中失败不重复拉取。
2. `EnvironmentGateService`：修正 degraded capital 的 `missing` 为单元素元组。
3. Watch V2 入场提示词：激活计划且账户自主授权时，触发进入买入执行核验；仍完整执行 R-001/R-008/R-009 和基本面排雷，全部通过才在合法时段按计划与试单额度较严值调用 `portfolio_trade`，并核对成交、止损和审计；不通过必须列具体阻塞项。
4. `MarketStateProvider`：缓存从单实例改为按指数宇宙跨请求共享 60 秒，并以锁防止并发重复回源；`force=True` 保留强制刷新。修复首次部署后 `/api/plans/today` 实测 17.58s、超过工具 15s 上限的问题。

## 验证

- 隔离 worktree 测试，强制 PYTHONPATH 指向本 worktree，避免误测主工作区源码。
- 故障注入覆盖：低覆盖回源、充足日 K 不拉快照、实时源失败保留降级、盘中失败不重复请求、degraded 字段序列化、入场执行提示词。
- `packages/qs_watch/tests/v2` + 环境闸 + 市场宽度回退 + 快照缓存 + `test_account_trading_service_v2.py`：**167 passed**。

## 边界与后续

- 本次未开启 `signal_execution_daily`，该任务服务独立量化账户，不是本实例账户的执行入口。
- 未降低任何买入标准，未绕过 regime、资金、经验检索、信号分级、交易时段或试单额度。
- 代码修复不等于实际成交。下一交易日须做一次小额模拟端到端验收；无合格触发时合法零交易，并报告具体阻塞项。
