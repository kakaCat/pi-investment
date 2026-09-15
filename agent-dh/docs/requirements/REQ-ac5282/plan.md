# REQ-ac5282 实施计划：修复 signal_track 两处缺陷

## 背景与根因

signal_track 工具（`packages/intelligence/src/tools/SignalTrackTool/SignalTrackTool.ts`）在 2026-09-15 会话中被两次调用失败：

1. **source 契约不一致**：`prompt.ts` 的 source enum 声明含 `manual`（5 个值），但 `validate` 的 `validSources` 只有 4 个（漏 `manual`）→ 传 `manual` 报 `source 必须是 strategy_execute/opportunity_scan/mainline_stocks/watch_rule 之一`。
2. **当日未收盘信号必被拒**：`checkPriceSanity` 用 `signal_date`（默认今天）单日查当日 kline 对账；盘前/盘中当日尚未收盘，后端 `GET /api/stock/{symbol}/klines` 单日 404 → fail-closed 拒绝写入，只有收盘后才能记录当日信号（违背"信号应在发现时记录"语义）。

## 修复方案

- **缺陷 1**：`validSources` 补 `manual`，与 `prompt.ts` enum 对齐。
- **缺陷 2**：`checkPriceSanity` 增加 `isTodayOrFuture = signal_date >= 今天` 判断；当日/未来未收盘时，单日无 K 线/404 → 回退查询最近 12 自然日区间，取最后一个已收盘交易日收盘价对账（新增 `checkAgainstLatestTradingDay`）。**过去日期无 K 线仍 fail-closed**，保留 REQ-342799 防周末假记录语义。

## 部署与验证

- build：`pnpm --filter @pi-investment/intelligence build`（tsdown，dist 包）。
- 重启：`launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`。
- noop 核验（R-017）：`signal_track record source=manual` + 今日未收盘场景 → 写入 ID 42，`price_check: verified(close=13.03, dev=0.31%)`。

## 任务表

| key | 任务 | 验收标准 |
|-----|------|----------|
| t1 | 修复 source 校验补 manual | validSources 含 manual，source=manual 不再报错 |
| t2 | 修复 checkPriceSanity 回退逻辑 | 今日未收盘单日 404 回退最近交易日对账通过；过去非交易日仍拒绝 |
| t3 | build + 校验 dist | build exit=0，dist 含 isTodayOrFuture/checkAgainstLatestTradingDay/manual |
| t4 | 重启 + noop 核验 | signal_track record(manual, 今日未收盘) 成功写入并对账 |
