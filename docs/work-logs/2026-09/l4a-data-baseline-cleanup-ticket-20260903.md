# 工单：经验/信号数据基座清理（L4-A 第一个真动作）

> 日期：2026-09-03（周四）
> 作者：investor（w-8366e526）
> 类型：L4-A 数据基座 · 盘后执行工单
> 背景：L4 元学习要可信，第一步是经验/信号两库的统计口径干净。实测现状见下，本工单为隔离动作清单。

## 1. 实测现状（2026-09-03 凌晨）

### 经验库（experience_stats，88 条）
- **结果未标注 72 条（82%）**：by_outcome profit 2 / loss 3 / neutral 11 / untagged 72
- **标的未登记 77 条（unknown）**：无法回溯行情补结果，只能归档隔离或保持现状
- 带 symbol 且无 outcome 可补标的：600519×4、600926×1、601288×1、000001×1、002241×1（多为工具验证类记录）
- 现状 win_rate 2.3% 无统计意义（16 条已标注里真交易样本极少）

### 信号库（signal_track，14 条 2026-08-04~09-03）
- **9 条 test_* 来源（64%）**：testAttribution×3 / testSuite×3 / testClient×1 / testIntegration×1 / testDuplicate×1
- 真实来源仅 5 条：manual / watch_rule / strategy_execute / opportunity_scan / mainline_stocks 各 1
- 5D/10D/20D 表现：10D/20D 全 N/A，5D 仅 3 条有值（A 级 33.3%）

## 2. 隔离动作（盘后 15:30 例程执行）

1. **今日盘后起强制 outcome 标注**（R-004 配套）：凡 experience_write / learning_track 落库必须带 outcome（profit/loss/neutral），缺省拒绝入库或标 untagged 提醒
2. **带 symbol 可补标的补标**：600519×4、600926、601288、000001、002241 共 8 条按场景补 outcome（工具验证类 → neutral），补后经验库已标注率从 18% → ~27%
3. **signal 统计隔离**：future 回填统计只计入非 test_* 来源信号

## 3. 需基建线处理的缺口（本窗口无权限/工具不可达）

| 缺口 | 说明 | 建议修法 |
|---|---|---|
| ~~signal_track report 无来源过滤~~（**已证伪，2026-09-03 代码复核**） | 无法剔除 test_* 后统计胜率 | ✅ **已具备**：SignalTrackTool report 端到端传 source（`agent-dh/packages/intelligence/src/tools/SignalTrackTool/SignalTrackTool.ts:99`），qv2 client `getSignalReport` 支持 `source` 参数（`quantsys-v2-client/src/client.ts:1561-1563`，GET /api/signals/track/report?source=）。本行此前误判为缺口，隔离动作 3 可直接执行，无需基建 |
| 经验 77 条 unknown 归档 | 无 symbol 无法补，污染统计 | 提供归档/隔离机制（如按 created_at 早于某日期隔离） |
| 信号 5D 回填仅 3/14 | 回填断档 | 盘后例程固定调 signal_track update 回填 5D/10D/20D（9/3 已有 signal-perf-verify 任务） |

## 4. 验收

- 今日盘后结束：经验 untagged 比例 < 75%（目标逐步降至 30%）
- signal_track 全部真实来源信号 5D 有值
- test_* 信号可被统计隔离（后端支持或明确记录为 gap）
