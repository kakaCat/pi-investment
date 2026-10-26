# 策略库治理清单盘点（analyze 阶段产出）

> **正本已迁移**：本文件是 t-ab4c82 analyze 子卡的工作底稿；验收正本（含全部清单、evolution_run 降级实测结论与验收锚点）已落
> [docs/requirements/REQ-261019144524-ec50/w4-strategy-cleanup.md](../../requirements/REQ-261019144524-ec50/w4-strategy-cleanup.md)（2026-10-19 w-503df447 归并）。
> 以下内容为 analyze 阶段原始产出，保留作证据底稿；如两处不一致，以 w4 正本为准。

- **时点**：2026-10-19 22:30 CST（盘后，非交易时段，全程只读）
- **窗口**：investor / 4c658b7a-0a1f-4dc4-b7c6-6c61143c358a（实施子代理）
- **数据来源**：quant_investment DB 直查（psql）、v2 git log、`strategy_list`/`strategy_execute`/`evolution_run` 工具实调、记忆库（memories 表）

---

## 一、策略库现状（2026-10-19 实测）

`quant.strategy_configs` 仅 **5 条**（与 `/api/strategies` total=5 一致，分页拉取无隐藏页）：

| id | 名称 | status | structure | performance | 备注 |
|---|---|---|---|---|---|
| 163 | range-breakout-v1 | stopped | unknown | unmeasured | is_active=t |
| 178 | value-macd-cross-v1 | stopped | unknown | unmeasured | is_active=t |
| 179 | 多因子波段策略v9 日线版 | stopped | unknown | unmeasured | is_active=t |
| 193 | VBottom-v2 | stopped | unknown | unmeasured | is_active=t（R-011 实证过其 error+invalid 下批量异常输出） |
| 202 | v13 趋势突破 | error | invalid | unmeasured | v13 策略线账户的策略，按 R-019 不代为处置 |

另：`quant.strategy_metadata` 19 条 = 内置策略**类**注册表（ma_cross/turtle 等），不是用户策略实例，不属于治理对象。

### 数量变迁时间线（治理断链证据）

| 时点 | strategy_configs 条数 | 依据 |
|---|---|---|
| 2026-09-13 清理前 | 89（另有 245 条 TEST 垃圾已先清，commit d9f8724bb） | commit 0f79691da 台账 `config/strategy_archive/DELETED_20260913.md` |
| 2026-09-13 清理后 | 14（API 可见 13） | 同台账 |
| 2026-10-11 | **101**（unmeasured 1 / NULL 100） | 记忆《周度策略进化·诊断台账 2026-10-11》w-f0101ceb |
| 2026-10-19（今天） | **5** | 本卡 psql/API 双重实测 |

⇒ 14→101（回灌/再入库）与 101→5（大规模删除）**两次变动均无 git 台账、无 archive 备份、无 events 表记录**。`config/strategy_archive/` 只有 09-13 一份归档。且台账自洽性有问题：09-13 被删清单含 178/179/193，"保留 14 条"名单含 162/164/245/266/267/268/269/365/416/418/429/637——**现状恰好反过来**（178/179/193 在、保留名单里 10 条全不在），疑似发生过"从 09-13 备份恢复 + 另行删除保留项"的操作，无任何留痕（updated_at 仍是 09-13 时间戳，支持"从备份 JSON 整行插回"的推测）。

## 二、TEST 残留盘点（逐处定级）

| 位置 | 规模 | 定级 | 处置建议 |
|---|---|---|---|
| `quant.strategy_configs` TEST 命名 | **0 条** | ✅ 已清干净（09-13 两批共 320 条） | 无 |
| `quant.backtest_results` | 540 行，属 12 个**已不存在**的策略名（macd-golden-cross-v1 等 v1/v2 试验名），最新 2026-08-31 | ⚠️ 孤儿数据 | 可归档导出后清表；先登记 data_contracts（R-020） |
| `public.evolution_runs` | 32 行中 **19 行**指向已删策略（203/266/268/488/635~639） | ⚠️ 悬空引用 | 台账留作历史证据即可；若要清，先确认前端无引用 |
| `quant.evolution_strategy_runs` | 91 行中 **87 行**属已删策略 635（09-05 前）；4 行属 202 且全 degraded | ⚠️ 悬空引用 | 同上 |
| `quant.stock_strategy_map` | 560 行，按**策略名**（B_H/RSI_ATR/MA_ADAPTIVE 三档）引用而非 id | ℹ️ 非悬空但已陈旧 | 属"股票→最优策略类型"映射，无 configs 外键，删除策略不影响它；新鲜度待确认 |
| `quant.signal_test_log` | 51 行，最新 2026-05-26 | ℹ️ **活功能旧数据**（路由 signal_test_async 仍在） | 不是残留，不删 |
| `quant_test` 数据库 | 15 表全 0 行 | ✅ **不是残留**——pytest 专用库（`.env.test`、tests/ 引用），2026-10-19 刚做过孤儿数据清理（commit 00c7229f5） | 保留 |
| `public.strategy_signals / strategy_execution_log / strategy_backtest / strategy_performance` | 全 0 行 | ✅ 无残留 | — |
| `config/strategy_registry.json` | 2 条：zz-loop-e2e（720，已删，探针性质）、core-overlay-v1（active） | ✅ 正常 | — |

**结论：TEST 残留在策略主表已清零；真正的残留是派生表的孤儿/悬空数据（backtest_results 540 + evolution 两表 106 行），且无一条有 data_contracts 登记（R-020 盲区）。**

## 三、unmeasured 补测可行性抽查

1. **回测通道可用**：`strategy_execute(179, backtest, 600519, 2025-10~2026-03)` 返回 94 点 equityCurve，但 **0 交易**（要么该窗口无信号、要么踩中"开仓未平仓不计 trades"判据缺陷）。
2. **evolution_run 不可用（第 4 周复现）**：`evolution_run(202, 002007, propose)` 再报 schema 硬错误（best_params/best_metrics/fitness 必填 vs 降级返回）。**且服务端日志实证判据缺陷**：同一轮基线回测实际总收益 **−23.18%**、夏普 −1.16（有交易发生），却被判"total_trades=0、窗口无信号"拒绝进化——"只在 SELL 分支记 trades、窗口末不强制平仓"的计数缺陷再次坐实。`evolution_leaderboard` 能正常读出 degraded_reason，缺陷在 schema 边界。
3. **补测拦路虎**：①4 条非 202 策略无绑定默认标的（strategyProfile 空），补测需先定池；②回测 trades 计数缺陷不修，补测结论会被"零交易"误读污染；③202 归 v13 策略线（R-019），投资脑不代为补测。
4. **建议的补测序**：先修 trades 计数缺陷（或补测结论一律标注口径）→ 修 evolution_run 降级 schema → 对 163/178/179/193 各选 3~5 只默认池标的跑 1 年 OOS → 回填 performance_status/evidence。

## 四、置信度与适用边界

- **高置信**：现状条数、TEST 残留分布、evolution_run 缺陷复现（本卡实调 + 服务端日志双证据）。
- **中置信**：14→101→5 的变动路径（"备份恢复"为推测，无直接证据；只确证两端点数与无台账事实）。
- **边界**：①本清单只管 quantsys-v2 侧，不含 agent-dh 提示词中的策略引用；②处置建议不自动执行（删数据需用户裁决 + R-020 登记先行）；③补测可行性结论基于抽查的 2 条策略，未穷尽 5 条。

## 五、被证伪的假设

1. ~~策略库有约 101 条待治理、含大量 TEST 残留~~ → 实际 5 条、TEST 命名 0 条；101 是 10-11 的过期快照。
2. ~~TEST 残留主要在策略主表~~ → 主表已清；残留在派生表（backtest_results/evolution 两表）。
3. ~~quant_test 库是 TEST 残留~~ → 它是 pytest 测试基础设施，不是垃圾。
4. ~~signal_test_log 是废弃残留~~ → 是活功能（路由仍在）的旧数据。
5. ~~09-13 清理后保留的 14 条至今在位~~ → 保留名单 10 条已消失、被删名单 3 条反而复活，变动无台账。
6. ~~evolution_run propose 模式可用~~ → 连续第 4 周 schema 硬错误；"零交易"判据缺陷同日再次实证（实际 −23.18% 被判无信号）。
