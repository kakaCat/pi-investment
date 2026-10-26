# W4 策略库治理清单（TEST 残留盘点 + unmeasured 补测可行性）

> **处置状态：✅ 部分已执行（2026-10-20，w-503df447）**——backtest_results 540 行孤儿（实测 100% 属已删策略）已导出 CSV 后 DELETE，表现存 0 行；备份 backups/2026-10-20-input-governance/backtest_results_orphans_20261020.csv，契约登记 governance=orphan_rows_cleanup_20261020。evolution_runs / evolution_strategy_runs 悬空行按 §2 建议**保留作历史证据**未动。策略主表 5 条未动。

- **需求**：REQ-261019144524-ec50 进化闭环有效性改造（SP-4 / 工作包 W4）
- **任务**：t-ab4c82（collect 子卡 t-ee21d9 · analyze 子卡 t-542f40 · review 子卡 t-5c0823）
- **落盘**：2026-10-19 · w-503df447（investor）；全程只读盘点，**未执行任何删除/归档动作**（处置待用户裁决）
- **数据来源**：quant_investment DB 直查（psql，子代理实调）、v2 git log、strategy_list / strategy_execute / evolution_run / evolution_leaderboard 工具实调、记忆库；子代理详细工作底稿见 [strategy-library-governance-inventory.md](../../work-logs/2026-10/strategy-library-governance-inventory.md)

## 0. 关键事实修正（对父卡预期的证伪）

父卡预期「125 条策略中含 TEST 残留待盘点归档」**已被证伪**：当前策略主表 `quant.strategy_configs` 仅 **5 条**（TEST 命名 **0 条**），101 条是 2026-10-11 的过期快照。真正的治理对象已迁移为：**派生表的孤儿/悬空数据 + 无台账的两次库表变动（14→101→5）**。

## 1. 策略主表现状（2026-10-19 strategy_list 实调复核）

| id | 名称 | 创建时间 | status | structure | performance | 处置建议 |
|---|---|---|---|---|---|---|
| 163 | range-breakout-v1 | 2026-05-30 | stopped | unknown | unmeasured | 保留，纳入补测候选（先定默认池） |
| 178 | value-macd-cross-v1 | 2026-05-31 | stopped | unknown | unmeasured | 保留，纳入补测候选 |
| 179 | 多因子波段策略v9 日线版 | 2026-05-31 | stopped | unknown | unmeasured | 保留，纳入补测候选 |
| 193 | VBottom-v2 | 2026-06-01 | stopped | unknown | unmeasured | 保留但标记 R-011 风险（曾在 error+invalid 下产出全 SELL 异常批量）；补测通过前禁止作信号源 |
| 202 | v13 趋势突破 | 2026-06-01 | error | invalid | unmeasured | **不处置**——v13 策略线账户资产（R-019），归策略线自行治理 |

**TEST 残留条款的落实**：验收要求"每条 TEST 策略的 id/名称/创建时间与处置建议"——实测 TEST 命名策略在主表为 **0 条**（2026-09-13 两批共清 320 条，commit 0f79691da / d9f8724bb 台账），无条目可列；上表为现存全部 5 条的完整清单。TEST 残留的真正所在是派生表（§2）。

## 2. TEST 残留真正所在：派生表孤儿/悬空数据（均无 data_contracts 登记 = R-020 盲区）

| 位置 | 规模 | 定级 | 处置建议（待用户裁决） |
|---|---|---|---|
| `quant.backtest_results` | 540 行，属 12 个**已删**策略名（macd-golden-cross-v1 等），最新 2026-08-31 | ⚠️ 孤儿数据 | 归档导出后清表；先登记 data_contracts |
| `public.evolution_runs` | 32 行中 **19 行**指向已删策略（203/266/268/488/635~639） | ⚠️ 悬空引用 | 留作历史证据；若清，先确认前端无引用 |
| `quant.evolution_strategy_runs` | 91 行中 **87 行**属已删策略 635；4 行属 202 且全 degraded | ⚠️ 悬空引用 | 同上 |
| `quant.stock_strategy_map` | 560 行按策略名引用（无 configs 外键） | ℹ️ 非悬空但陈旧 | 新鲜度待确认，暂不动 |
| `quant.signal_test_log` | 51 行，最新 2026-05-26 | ℹ️ 活功能旧数据（路由 signal_test_async 仍在） | 不删 |
| `quant_test` 数据库 | 15 表全 0 行 | ✅ pytest 基础设施，非残留 | 保留 |
| `config/strategy_registry.json` | 2 条（zz-loop-e2e 已删探针、core-overlay-v1 active） | ✅ 正常 | — |

## 3. 治理断链证据（14→101→5 两次变动无台账）

| 时点 | strategy_configs 条数 | 依据 |
|---|---|---|
| 2026-09-13 清理前 | 89（另 245 条 TEST 垃圾先清） | commit 0f79691da 台账 |
| 2026-09-13 清理后 | 14 | 同台账 |
| 2026-10-11 | **101** | 记忆《周度策略进化·诊断台账 2026-10-11》w-f0101ceb |
| 2026-10-19 | **5** | 本卡 psql/API 双重实测 |

⇒ 两次变动（14→101 回灌、101→5 删除）**均无 git 台账、无 archive 备份、无 events 记录**；且 09-13「保留 14 条」名单中 10 条已消失、被删名单的 178/179/193 反而在位（updated_at 停在 09-13，疑似从备份 JSON 整行恢复）。→ 支撑需求根因假设 4（失败/变动无告警闭环），建议纳入后续"策略库变动强制台账"纪律（另立卡，不在本卡边界）。

## 4. unmeasured 补测可行性（含 evolution_run 降级原因实测结论）

1. **回测通道可用**：直接 POST /api/backtest/strategy（策略 202/002007 一年窗）equity 100000→82664、184 天有持仓；策略 179/600519 回测返回 94 点权益曲线但 0 交易（真实无信号或踩判据缺陷）。
2. **evolution_run 不可用（第 4 周复现）**：`evolution_run(202, 002007, propose)` 报 schema 硬错误（best_params/best_metrics/fitness 必填 vs 诚实降级返回）；同一事实经 `evolution_leaderboard` 能正常读出 degraded_reason——**缺陷在工具输出 schema 边界，不在后端**（与 lessons「降级路径输出形状必须与成功形状分离」一致）。
3. **"零交易"判据缺陷当日再次实证**：服务端日志显示该轮基线回测实际总收益 **−23.18%**、夏普 −1.16（有交易发生），却被判"total_trades=0、窗口无信号"拒绝进化——trades 只在 SELL 分支 append、窗口末不强制平仓的计数缺陷坐实。**补测判据禁用 totalTrades，应以权益曲线变动/持仓天数为准。**
4. **补测拦路虎**：①163/178/179/193 无绑定默认标的（strategyProfile 空），需先定池；②trades 计数缺陷不修，补测结论会被"零交易"误读污染；③202 归 v13 策略线不代为补测。
5. **建议补测序**：修 trades 计数缺陷（或结论标注口径）→ 修 evolution_run 降级 schema → 对 163/178/179/193 各选 3~5 只默认池标的跑 1 年 OOS → 回填 performance_status/evidence。

## 5. 验收锚点（本卡三项）

- [x] **清单落盘**：本文件（w4-strategy-cleanup.md）——含现存全部策略的 id/名称/创建时间/处置建议（§1；TEST 命名 0 条的事实修正见 §0），派生表残留清单与处置建议（§2）。
- [x] **evolution_run 降级原因实测结论**：§4.2/§4.3——schema 边界硬错误 + "零交易"判据缺陷（实际 −23.18% 被判无信号），第 4 周复现，双证据（工具实调 + 服务端日志）。
- [x] **strategy_list 复核无策略被硬删**：本卡全程只读、未执行任何删除；2026-10-19 strategy_list 实调复核现存 5 条（163/178/179/193/202）与盘点一致，无一条因本卡动作被硬删。

## 6. 置信度与边界

- **高置信**：现状条数、TEST 残留分布、evolution_run 缺陷复现（实调 + 服务端日志双证据）。
- **中置信**：14→101→5 变动路径（"备份恢复"为推测；只确证两端点数与无台账事实）。
- **边界**：①只管 quantsys-v2 侧，不含 agent-dh 提示词中的策略引用；②§2 处置建议均需用户裁决后执行，删除前先 R-020 登记 + decision_audit + memory 留痕；③补测结论基于 2 条策略抽查，未穷尽 5 条。
