# 复核报告 · REQ-261006190953-fc43（业绩归因/风险指标窗口按交易日取数）

**复核者**：本窗口（**提交者自查**——不是独立复核窗口；独立复核请走看板勾选通道，见文末）
**复核时间**：2026-10-06 20:1x–20:5x CST
**工作区**：`/Users/mac/Documents/ai/pi-investment/quantsys-v2`（monorepo 根 `/Users/mac/Documents/ai/pi-investment`；卡 E 改的是兄弟仓 `agent-dh`）
**方法**：所有判定来自**我自己重跑命令 / 读代码 / 做变异验证**，不复用子代理的自述；本文档与 `tests/` 是本次需求目录内唯一新增的评审类文件。

---

## 0. 一句话结论

**代码侧可交付**：四层口径（写入闸门 / 读取过滤 / 缺口判断 / 存量清理）都已落地并有可跑判据，
v2 侧 117 passed（新增与改动文件）+ 391 passed（邻域），agent-dh 侧 15 passed。
**两项不能算「端到端成立」**（都需人放行，详见 §4）：生产数据清理未执行、v2 API 未重启。

---

## 1. 这一轮真正抓到的问题（4 个真问题，都不是"看着像"）

| # | 问题 | 怎么抓到的 | 处置 |
|---|---|---|---|
| 1 | **设计前提错**：`design/data-model.md` §3 的删除谓词 `is_trading_day is false` 在生产日历上匹配 **0 行**（日历 23373 行全是 true，是白名单：缺行即非交易日）→ 迁移按字面执行**清不掉任何脏数据** | 卡 F 子代理实施后跑生产 dry-run 报"待删 0 行 ≠ 预期 35"，**拒绝自行改口径**并如实上报 | 上报人裁定 → **D-6**：改白名单语义 + 覆盖范围防误删；迁移、巡检、设计文档、需求台账四处同步 |
| 2 | **既有测试隐含假设"今天一定是交易日"**：`tests/test_multi_account_domain.py::test_equity_snapshot_upsert` 不传 `snapshot_date`（取今天），今天是休市 → 闸门一上线它当场变红，而且**每个节假日都会红** | 卡 B 改动后我自己跑四条写路径的调用方面，1 failed | 扩该文件**既有的** autouse 夹具（它本就声明"交易判定不是本文件测试目标"）注入常真门；未改用例语义、未动生产代码 |
| 3 | **新增代码引入 500**：`/api/risk/metrics` 在**显式 returns 口径**下 `window`/`nav_coverage` 未初始化 → `UnboundLocalError` | 卡 D 子代理被既有 parity 回归抓住 | 修 + 补 `test_explicit_returns_path_unchanged` 锁死该分支 |
| 4 | **一条把"未实现的缓解"写成既成事实的注释**：`trading_day_guard.py` 声称 08-08 那批脏行「已标记某合成标记列并从统计口径排除」——**该列不存在、全仓零引用** | 我核对 35 行脏数据时顺手 grep，发现该标记名只出现在这一行注释里 | 订正注释（并因此发现卡 G 的 `grep == 0` 判据会绊倒我的订正文字 → **改文字不放松判据**） |

## 2. 变异验证（证明用例是"活的"，不是摆设）

| 卡 | 变异手法 | 结果 | 来源 |
|---|---|---|---|
| B | 把 `written += 1` 退回无条件（回填计数） | 5 条红 | 卡 C 子代理 |
| C | 两段跳过文案混成一段 | 4 条红 | 卡 C 子代理 |
| C | 引擎 `None` 分支退回 `snap.daily_return` | 2 条红（AttributeError） | 卡 C 子代理 |
| D | 两条路由 `trading_days_only=True` 改回 False | 风险端 6 条、绩效端 2 条红 | 卡 D 子代理 |
| E | `missing_count`/`missing_trading_days` 临时改成恒 0 | ④ 的两条红 | 卡 E 子代理 |
| G | 巡检器造脏行 | 退出码 2（不造则 0） | 我自己 |

**我自己复核的**：G 的三态（0/2/3）在测试库与生产库各跑一次，实际输出见 `tests/test-evidence.md`。

## 3. 逐 FR 核对（代码侧）

| FR | 落点 | 判据 | 状态 |
|---|---|---|---|
| FR-1 写入唯一闸门 | `SimulationORMRepository.upsert_equity_snapshot` | 休市日返回 None 且零行；降级照写；force 旁路 | ✅ |
| FR-2 门在被调函数层 | 同上（四条路径共用） | 打桩断言"两条服务路径都调了同一判据" | ✅ |
| FR-3 缺口改交易日口径 | v2 算 `nav_coverage`；agent-dh 消费 | 国庆整段缺口 0；缺 09-25 报 1；缺字段如实声明 | ✅（①端到端待重启） |
| FR-4 读取按交易日 | `nav_series` + `get_equity_snapshots(trading_days_only)` + 两路由 | navPoints == 交易日数；`filtered_non_trading` 有计数 | ✅ |
| FR-5 基准=上一交易日 | `previous_valid_snapshot` / `calculate_daily_return` | before=10-08 返回 09-30 而非 10-02 | ✅ |
| FR-6 存量清理 + 重算 | 迁移三态 | dry-run 零副作用；apply 后判据 0；rollback 可恢复 | ✅（生产未 apply） |
| FR-7 可证伪 + 常驻判据 | 巡检器 + 一致性校验器 | 生产 35 行红 → apply 后应绿；校验器 diff 判据 | ✅ |
| FR-8 口径可见化 | 接口 `window`/`nav_coverage`；agent-dh 文案 | 五字段齐、basis 与来源透出、未校验显式声明 | ✅ |

## 4. ⚠️ 两项待人工放行（**不满足则不能说"端到端成立"**）

1. **生产数据清理未执行**：迁移只跑了 dry-run（待删 35 / 重算 65 / 零改动）。
   执行命令见 `tests/test-evidence.md`。执行后巡检器应从退出码 2 转 0、一致性校验器从 119 处差异转 diff=0。
2. **v2 API 未重启**：现场核对 `GET /api/simulation/performance` 仍只有 5 个旧键
   （`equity_curve/initial_capital/current_value/cumulative_return/max_drawdown`），
   没有 `window`/`nav_coverage`。**故卡 E 的"透出"分支当前只能算桩测**。
   ⚠️ 重启会把**其他需求在飞的未提交改动**一并投上生产（工作区里 `should_have_run.py`、
   `trading_day_resolver.py` 等都有未提交改动），属跨需求部署决定 —— 本窗口不擅自执行。

## 5. 残余风险（完整清单见 `notes/implementation-deviations.md` 的 R-1~R-7）

- **R-4 分层棘轮红**：`tests/test_layer_purity.py` 实测 320 > 基线 318。逐文件归因：本需求 **+1**（仓储调闸门，
  结构性代价：替代方案"组合根注入回调"会重新打开"漏加门"的洞，已明确否决），他人在飞 **+1**。
  **未调基线**（规则禁止为新债调基线）。移交：`should_have_run.py` / `trading_day_resolver.py` 的 +5
  属 `REQ-261006093620-a315` 范围。
- **R-1** 未来日期（`source='future'`）会被闸门拒写：当前四个写入方都写"今天"，无触发路径。
- **R-2** `tools/snapshot_daily.py` 仍自带"当日有无 K 线"的第二套代理判据（与门同向、不构成故障）。
- **R-3** `take_daily_snapshot` 新增了 `skipped` 返回形状：Python 侧唯一消费方（orchestrator）只透传，**agent 侧容错未确认**。
- **R-5/R-6/R-7** 见 §4 与 agent-dh 预存失败说明。

## 6. 关于"独立复核"

本文件是**提交者自查**，按本仓规则不能替代独立复核。独立通道：**看板验收单逐项勾选**
（人逐项 通过 / 不通过 + 意见）。若需要独立窗口复核，请另开窗口对
`requirement.md` / `design/*` / `decomposition.md` / `notes/implementation-deviations.md` 与本节 §1 的 4 个问题做交叉复核。
