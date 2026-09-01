# 临时解决办法审计报告 v2（2026-09-01 复核+补充）

> 审计人：PI 投资顾问·投资脑（investor / w-8366e526）
> 触发：用户指出"有些流程不正规是临时解决办法——脚本最低要求是要包到工具里，v2 应该有对应功能，这样好管理、系统化"
> 基线：[temp-solutions-audit.md](./temp-solutions-audit.md)（w-a8a89c6a，09-01 02:26，4 类 16 处）
> 本文：①复核基线 16 处的当前状态 ②补充本日新发现 7 处（含本窗口自查 2 处）
>
> **修复进展（09-01 下午，见 §6）**：✅ E-1 假引擎拆除 / ✅ E-3 combo Mock 回收 / ✅ G-1 optimize 修复 / ✅ E-2 trade-verify 重建 / ✅ F-1 回测矩阵端点化；📋 B-1/A-1 调度拆分已定方向（[ADR-002](../adr/002-scheduler-ownership-split.md)），待 scheduler 重构会话完成后执行

---

## 0. 结论摘要

基线 16 处：**仅 1 处部分缓解（B-1），15 处仍存在**。本日复核**新发现 7 处**（E/F/G 类），合计 **23 处**。

| 类别 | 数量 | 状态 | 严重度 |
|---|---|---|---|
| A. 调度执行脱离工具层（裸脚本桥接） | 15 任务 | ❌ 仍存在 | 🔴 |
| B. 业务后端调度职责倒挂 | 25 任务 | ⚠️ 部分缓解（本地 fallback 已接入，Agent OS 仍是主调度） | 🔴 |
| C. 核心工具依赖 legacy Agent OS | 10 插件 | ❌ 仍存在 | 🟠 |
| D. 硬编码密钥 + 一次性脚本 | 3+ 处 | ❌ 仍存在 | 🟡 |
| **E. 假实现/替代实现未回收（新增）** | 3 处 | ❌ 新发现 | 🔴 |
| **F. 分析/回测逻辑散落脚本未工具化（新增）** | 3 批 | ❌ 新发现 | 🟠 |
| **G. 前端工具字段错配致绕行（新增）** | 1 处 | ❌ 新发现 | 🟠 |

---

## 1. 基线 16 处复核（对照 temp-solutions-audit.md）

| 基线条目 | 当前状态 | 证据 |
|---|---|---|
| A-1 os-remind-bridge.sh（15 任务） | ❌ 仍存在 | scheduler_manage list 实测：15 任务 command 仍指向 os-remind-bridge.sh |
| A-2 signal-perf-backfill.sh | ❌ 仍存在 | signal-perf-backfill-daily 任务 command 仍是该脚本（curl 直连后端） |
| A-3 signal-perf-verify.sh | ❌ 仍存在 | signal-perf-verify-0903 任务在册（9/3 用后即弃，到期后删） |
| B-1 调度职责倒挂（25 任务） | ⚠️ **部分缓解** | 今日重构（262e607a/8cc1d697/8a71c821）：v2 SchedulerService 已接入 FastAPI lifespan（main.py L152），**但仅作 fallback**——Agent OS 可用时仍走 Agent OS（main.py L130-138），职责倒挂本质未变 |
| C-1 10 插件依赖 agent-os-client | ❌ 仍存在 | memory/notification/scheduler 等仍走 Go legacy（未动） |
| D-1 飞书 webhook 硬编码 ×2 | ❌ 仍存在 | signal-perf-verify.sh / test-weekly-report-push.sh 未清理 |
| D-2 一次性脚本（31 个 scripts/ 下 18 个非生产） | ❌ 仍存在 | 且新增 1 个（见 F-2） |
| §5 代码内 TODO ×4 | ❌ 仍存在 | lifecycle 硬编码 capabilities/status、board isAdmin、learning 占位符 |

---

## 2. 新发现（E/F/G 类，本日复核）

### E 类：假实现/替代实现未回收 🔴

**E-1 BacktestAsyncEngine 随机数假引擎仍在服役** 🔴
- 位置：`quantsys-v2/application/services/backtest_async_engine.py` L93-120 `_simulate_trading`——`random.uniform(-0.2, 0.5)` 生成假收益、假夏普（0.5~2.5）、假回撤
- 暴露面：`ServiceFactory.get_backtest_engine()` 全站唯一 backtest_engine 提供者，任何调用方拿到的都是随机数；今日 combo 端点 500 的部分根因就是它（无同步 backtest() 方法且是假实现）
- 当前缓解：本窗口 combo 修复已绕开它（改接真实引擎 StrategyCodeService.backtest_strategy），但**本体未删**，下一个调用方仍会踩
- **正规化**：删除 `_simulate_trading` 或改为显式抛 NotImplementedError；`get_backtest_engine()` 改返回真实引擎适配器

**E-2 trade_verify 本地对账替代实现** 🟠
- 位置：`agent-dh/packages/trading/src/tools/TradeVerifyTool/TradeVerifyTool.ts` L69/79/157——自认"后端 trade-verify 路由 404 丢失后的替代实现（2026-08-23）"
- 问题：对账逻辑在前端工具里本地重算，后端权威路由缺失已 9 天未修；前后端可能对同一笔成交判定不一致
- **正规化**：修复 v2 `/api/trade-verify` 路由（找回 404 丢失的注册），工具改回调后端，本地逻辑退役

**E-3 combo 端点修复中的 Mock 残留（本窗口自查）** 🟠
- 位置：`backtest_async.py` L442-520 combo_backtest 路由内——`_MockStrategyRepo`（get_by_id 永远返回占位 `{name: 'strategy-{id}'}`）+ `_RealEngineAdapter`（类定义嵌在路由函数体内）
- 问题：为快速修复 500 用了 mock repo + 路由内嵌类——能跑但非正规：策略名校验失效（不存在的 strategy_id 也"通过"校验）、adapter 无法被其他端点复用
- **正规化**：`_RealEngineAdapter` 提升为 application 层正式服务（如 `ComboRealBacktestEngine`）；repo 接真 `get_strategy_repository()`（今日已可用）

### F 类：分析/回测逻辑散落脚本未工具化 🟠

**F-1 quantsys-v2/tools/ 33 个脚本，其中业务逻辑类未固化** 🟠
- 业务逻辑散落（应做成 API 端点或 agent 工具）：
  - `run_m32_backtest_matrix.py` / `create_m32_strategies.py`（M3-2 回测矩阵与策略创建——核心分析流程只存在于脚本）
  - `run_m64_macd_candidate.py` / `run_m64_market_filter.py` / `run_m64_trailing_stop.py`（M6-4 进化实验）
  - `backfill_daily_klines_sina.py` / `backfill_factors.py` / `backfill_factors_standalone.py`（数据回填，应归 data_manager/kline_daily_sync 工具）
  - `train_direct.py` / `train_lightgbm_simple.py` / `retrain_model_post_backfill.py`（模型训练绕行 ml/train 端点）
- 一次性迁移/检测类（可归档）：analyze_*.py ×5、detect_*.py ×6、fix_*.py ×2、migrate_*.py ×3、validate_wp15.py、gen_csi300_data.py 等
- **正规化**：业务逻辑类逐个评估固化（回测矩阵→`/api/backtest/matrix` 端点或 strategy_execute batch 模式；回填→data_manager 工具；训练→ml/train 端点参数化）；一次性类移入 `tools/_archive/` 或删除

**F-2 agent-dh/scripts/m3-2-strategy-backtest-matrix.py（新增）** 🟡
- M3-2 矩阵执行脚本放在 agent-dh/scripts（DSH 插件仓）而非 v2——业务计算落在错误的一端
- **正规化**：随 F-1 一并固化为 v2 端点，脚本删除

**F-3 本窗口 /tmp 临时脚本 15 个（自查）** 🟡
- 清单：run_v2_matrix.py / run_combo_matrix.py / run_combo2_matrix.py / run_mr648_matrix.py（回测矩阵驱动）、*_code.py + *_payload.json（策略创建载荷）、test_pool_battlefield.ts
- 说明：均为 /tmp 一次性使用、未入仓库，未违反"仓库内禁散落脚本"规则；但**分析逻辑未沉淀**——combo 矩阵/回测矩阵的驱动逻辑如果再做一次还得重写
- **正规化**：同 F-1——回测矩阵驱动固化为 v2 `/api/backtest/matrix` 端点（参数：strategies[]/symbols[]/periods[]，一次调用出分层统计），/tmp 脚本删除

### G 类：前端工具字段错配致绕行 🟠

**G-1 strategy_optimize 工具崩溃，直连绕行未修** 🟠
- 位置：`agent-dh/packages/strategy/src/tools/StrategyOptimizeTool/prompt.ts` L99：`data.best_score.toFixed(4)`
- 实测后端 `POST /api/strategies/optimize` 返回 `{success, results[], totalCombinations, successfulCombinations}`——**无 best_score 字段** → `toFixed on undefined` 必崩
- 现状：M3-2 工作中只能 curl 直连绕行；工具对用户不可用
- 根因模式：lessons 已有沉淀——"字段假设必须用真实数据验证"，此处于前端 render 层再犯
- **正规化**：render 改为从 `results[]` 取最优（`results.reduce(max by sharpeRatio)`），并对空结果兜底；补一条契约测试

---

## 3. 修复建议（按优先级）

### P0（架构风险，立即）
1. **E-1 假引擎拆除**：`BacktestAsyncEngine._simulate_trading` 删除或抛 NotImplementedError，`get_backtest_engine()` 指向真实引擎——**防止下一个调用方拿随机数当真回测**（今日 combo 已踩一次）
2. **B-1 调度收口完成**：当前 v2 SchedulerService 仅 fallback——决策：要么明确"Agent OS 主调度"为正式架构并文档化，要么切换主备（v2 主、Agent OS 退）。二选一，消除双轨
3. **A-1 os-remind-bridge 退役**：DSH scheduler 插件原生投递（cron→ctx.agents followup），15 任务迁移

### P1（消除绕行，短期）
4. **G-1 optimize 工具修复**：render 从 results[] 取最优 + 空值兜底（30 分钟工作量）
5. **E-3 combo Mock 回收**：_RealEngineAdapter 提升 application 层、接真 strategy_repo
6. **E-2 trade_verify 后端路由找回**：v2 补 /api/trade-verify，工具改回调
7. **C-1 依赖迁移**：memory/notification 插件切 v2 端点
8. **F-1/F-3 回测矩阵端点化**：`/api/backtest/matrix`（strategies×symbols×periods 批量+分层统计），tools/tmp 脚本退役

### P2（整洁性，收尾）
9. **D-1 webhook 密钥清理**（2 处改环境变量）
10. **D-2/F-2 一次性脚本归档**：scripts/ 非生产 18+1 个归档或删除；A-3 9/3 用后删
11. **§5 TODO 清理**（lifecycle 硬编码、learning 占位符）

---

## 4. 验证清单（修复后）

- [ ] `grep -rn "random.uniform" quantsys-v2/application/services/` 无命中（假引擎拆除）
- [ ] `strategy_optimize` 工具调用返回正常（不再 toFixed 崩溃）
- [ ] combo 端点不存在 _Mock/_RealEngine 路由内嵌类（application 层服务化）
- [ ] `scheduler_manage list` 无 os-remind-bridge.sh 引用
- [ ] v2 调度主备关系单一且文档化（二选一）
- [ ] `POST /api/backtest/matrix` 可用，tools/run_m32_*.py 与 /tmp/run_*_matrix.py 删除
- [ ] `grep -rn "open.feishu.cn/open-apis/bot" agent-dh/scripts/` 无命中
- [ ] trade_verify 走后端路由（工具内无"替代实现"注释）

---

## 5. 与基线报告的差异说明

- 基线（02:26）时 B-1 描述为"SchedulerService 未接入启动"——今日 11:00 前已有 3 个提交（262e607a/8cc1d697/8a71c821，另一会话）把 v2 调度接入 lifespan 作 fallback。本报告按当前事实更新为"部分缓解"
- E-3/F-3 为本窗口自查项——combo 修复的 Mock 与 /tmp 脚本是本窗口今天产生的临时办法，如实列入，不豁免

---

## 6. 修复进展（09-01 下午，w-8366e526 执行）

| 条目 | 状态 | 提交 | 验证 |
|---|---|---|---|
| E-1 假引擎拆除 | ✅ 完成 | bd0dacec | `_simulate_trading` 改抛 NotImplementedError；`get_backtest_engine()` 返回新 `RealBacktestEngineAdapter`（application 层正式服务）；故障注入验证拒服 |
| E-3 combo Mock 回收 | ✅ 完成 | bd0dacec | 路由内嵌 `_MockStrategyRepo`/`_RealEngineAdapter` 删除，接真 strategy_repository + 工厂真引擎；不存在策略正确拦截；真实策略名入 breakdown |
| G-1 optimize 字段错配 | ✅ 完成 | b7bed8c4 | execute 层字段适配（results[]→best_params/best_score/all_results）；契约测试 4 条新增；冒烟 19/19 |
| E-2 trade-verify 重建 | ✅ 完成 | 25c4a4ea | v2 新增 `/api/risk/trade-verify`（GET+POST）；字段经 ORM 实测校正（shares/shares_total）；工具本地实现删除改回调后端 |
| F-1 回测矩阵端点化 | ✅ 完成 | ca991a79 | `POST /api/backtest/matrix`：策略×股票×区间批量回测+分层统计；实测 8 回测 0 失败 |
| B-1/A-1 调度拆分 | 📋 方向已定 | ADR-002 | 用户裁决「按执行体拆分」；两阶段迁移路径；交接约束=等 scheduler 重构会话完成 |
| A-2/A-3/C-1/D-1/D-2 | ⏳ 未动 | — | A-2 依赖 ADR-002 Phase 2；C-1 大工程排期；D 类 P2 收尾 |

**事故记录**：G-1 提交（b7bed8c4）误带暂存区中 scheduler 重构会话的 14 个文件（scheduler_tasks.py 删除/task_handlers.py 半成品）。处置：评估重构自洽+main 可启动后未 revert；随后该会话继续推进并自行提交 ba12e287。教训：commit 前必须 `git status` 全量检查暂存区，不只查自己 add 的文件。
