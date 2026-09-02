# Autonomy 线定时任务"真实现"核查（2026-09-03）

> 署名：investor w-8366e526
> 主题：验证 docs/architecture/autonomy-profit-engine-unified.md §5 声称的 Autonomy 线定时任务（distill/variant/gate/meta/weekly-report）是否"注册→投递→业务真实执行"全链路成立
> 方法：M1 空壳判定标准（不看注册与 cron 触发痕迹，直接查业务工具代码 + 业务产出落库证据）
> 结论：**注册+调度配置真实，但迁移后至今无一次完整业务闭环；weekly-report-m6 曾引用不存在的 agent 工具（M1 式空壳）——2026-09-03 已补工具并实测闭合；distill 本体实测非空壳；剩余为时间驱动的首窗验证（9/3 16:00 / 9/5-9/6）**

---

## 1. 判定总表

| 任务 | cron | 注册 | 投递痕迹 | 业务工具代码 | 真实执行证据(9/1后) |
|---|---|---|---|---|---|
| evolution-distill-daily | 工作日16:00 | ✅ | ⚠️ 9/1 入信箱无 delivered；9/2 未投出 | ✅ daily_distill 编排真实(evolver) | ✗ 最近真实报告 8/26；9/1-9/2 零产出 |
| evolution-weekly-variant | 周六10:00 | ✅ | ✗ 从未触发（task_runs 0 条） | ✅ prompt_evolver 真实 | ✗ 从未到达执行窗口 |
| evolution-gate-adjudicate | 周日11:00 | ✅ | ✗ 从未触发（task_runs 0 条） | ✅ validation_gate 真实 | ✗ 从未到达执行窗口 |
| meta-learning-weekly | 周日11:30 | ✅ | 仅 9/1 02:11 manual 创建测试 | 通用工具组合，prompt 引导 | ✗ 从未到达执行窗口 |
| weekly-report-m6 | 周日12:00 | ✅ | 8/30 旧链路入信箱 success | ✅ ~~不存在~~ → 2026-09-03 已补（WeeklyReportTool） | ✗ 无法执行（工具缺失）→ 已修复，待 9/6 首窗 |

## 2. 关键证据

### 2.1 注册真实（tasks 表 5 行全配置正确）
cron/启用/中文 prompt 均在，executor=dsh-native、agent_line=autonomy、executor_type=agent（9/2 回填）。创建时间：weekly-report-m6 8/27、distill/variant/gate 8/31 22:20、meta 9/1 02:10。

### 2.2 投递层：9/2 白天证明新链路真实，但 Autonomy 线恰逢断档
- **新链路真实**：NativeReminderScheduler 代码完整（30s tick、cron 匹配、三态 deliver、compensate），9/2 09:25/09:35/13:00 三个 profit_engine 任务有 office:delivered 真实投递（investor-session-* direct 模式）。
- **9/2 15:30-16:45 全批断档**：post-market(15:30)/distill(16:00)/data-quality(16:05)/m4(16:30)/event(16:45) 在 native-scheduler.json 的 lastFired 全部是 `2026-09-02T11:11:00.000Z`（北京 19:11）同一分钟 → 这是 19:11 某 dsh 实例启动时 compensate() 对"无 lastFired"任务写的 baseline（设计为不投递），**不是真实投递时间**。同期 task_runs 全失败（stale agent-os 仍 exec 已删的 os-remind-bridge.sh）。→ 蒸馏 9/2 16:00 从未被投出。
- **9/1 16:00 distill**：task_runs success 仅是旧链路入信箱（tags=office:reminder 无 delivered），非投递到 agent 窗口。

### 2.3 业务工具层：3 个真实，1 个不存在（2026-09-03 已补）
- daily_distill / prompt_evolver / validation_gate 在 agent-dh/packages/evolver 为真实编排（learning_analyze→genome_update(candidate)→validation_gate→promote/rollback），非 execute 空壳。
- **weekly_report（weekly-report-m6 的 prompt 要求"调用 weekly_report"）：agent-dh 全仓 grep 零命中，我的工具清单无此工具 → agent 收到该提醒无工具可调，业务必然落空。**
  - 注意：后端 quantsys-v2 确有 WeeklyReportService + `GET /api/reports/weekly/latest`（实测 200 返回 8/24-8/30 数据），v2 scheduler 也注册了 v13_weekly_report job——但这是后端/旧策略账户周报，**未封装为 agent 可调工具**，prompt 与工具契约断裂。
  - **修复（见 §6.2）：2026-09-03 已在 evolver 包新增 WeeklyReportTool 并注册，重启后实测调用返回完整周报 → 契约断裂已闭合。**

### 2.4 真实执行证据：迁移后零闭环
- genome_history：9/1 13:31Z 一次 update（g18 lessons v7，作者 agent=8处链路修复手动沉淀）；8/25 最后一次 promote；**9/1-9/3 无 candidate 创建/promote/rollback** → 蒸馏→变异→裁决闭环从未自动跑出基因组变更。
- daily_distill 最近一次真实"每日蒸馏报告"memory 是 8/26（早于任务创建，测试期）。
- 9/1 22:16 memory 明载"因调度断链今日未自动执行，手动补跑"——盘后例程当日未自动执行的自证。
- 周度任务 variant/gate（8/31 创建）与 meta（9/1 创建）：**首个自然触发窗口为 9/5(周六)/9/6(周日)，尚未到达**，且 gate/variant 的 task_runs 至今 0 条。

## 3. 空壳判定清单（对照 M1 教训）

1. ❌ **weekly-report-m6 = 典型注册空壳**：任务/提醒在，但被引用的业务工具（weekly_report）在 agent 侧不存在——连"看似在跑"都谈不上，投递即空转。
2. ❌ **distill 迁移后从未真实执行**：9/1 仅入信箱、9/2 投递断档；最近真实业务产出停在 8/26。
3. ❌ **自进化闭环无产出**：9/1 后 genome 零 candidate/promote，§5 声称"L3 已迁 DSH NativeReminderScheduler ✅"只证明调度代码迁了，没证明业务闭环跑通。

## 4. 活验证窗口（下一步证明点）

- **9/3(四) 16:00 evolution-distill-daily**：若 16:00 distill 出现 office:delivered 且次日有蒸馏报告/决策提案落库，则链路打通；否则确认持续空转。
- 9/5(六) 10:00 variant / 9/6(日) 11:00 gate / 11:30 meta / 12:00 weekly-report：周度任务首次自然窗口，逐一验证。

## 5. 附：相关文件与数据源

- 声称文档：docs/architecture/autonomy-profit-engine-unified.md §5
- M1 空壳先例：docs/work-logs/2026-09/scheduler-v2-task-duplication-audit-20260902.md
- 迁移记录：docs/work-logs/2026-09/scheduler-line-tagging-20260902.md（5 autonomy + 8 profit_engine 清单）
- 数据源：quant_investment.public.tasks / public.task_runs / genome_history / memories(tags 判别 delivered vs 入信箱) / native-scheduler.json(lastFired)

## 6. 修复与实测记录（2026-09-03，investor w-8366e526）

### 6.1 daily_distill 业务本体实测：非空壳 ✅

手动调用 daily_distill(days=7) 实测（预览路径，不改基因组）：22 样本分析、5 模式真实产出（portfolio_trade 成功率 33.3% 平均奖励 -0.17、rotation_execute 成功率 0% 平均奖励 -0.3、opportunity_scan 80% 等），生成 3 条进化提案 → learning_analyze → prompt_evolver 编排真实可跑。
- 结论：distill 工具链**非 execute 空壳**；问题不在工具本体，而在 ①9/2 投递断档从未触发 ②auto_apply 默认关（预览），提案从未落地为 genome candidate。

### 6.2 weekly_report 工具缺口：已修复 ✅（M1 空壳闭环）

原判定：weekly-report-m6 的 prompt 要求"调用 weekly_report"，但 agent 侧全仓 grep 零命中 → 投递即空转。
修复（evolver 包新增 WeeklyReportTool，封装后端 `GET /api/reports/weekly`）：

| 文件 | 内容 |
|---|---|
| `agent-dh/packages/evolver/src/tools/WeeklyReportTool/prompt.ts`（新增） | 参数/结果类型 + ToolPrompt（week_start/week_end/format json\|markdown） |
| `agent-dh/packages/evolver/src/tools/WeeklyReportTool/WeeklyReportTool.ts`（新增） | BaseTool 实现：校验日期格式 → fetch 后端 json+markdown 双取 → 归一化返回 |
| `agent-dh/packages/evolver/src/tools/WeeklyReportTool/index.ts`（新增） | createWeeklyReportTool(baseURL) 工厂 |
| `agent-dh/packages/evolver/src/tools/index.ts` | 导出 WeeklyReportTool |
| `agent-dh/packages/evolver/src/index.ts` | import + registerTools 注册第 4 工具 + 构造器存 qv2BaseURL |

验证：
- 冒烟测试 `npx vitest run tests/plugin-schema.smoke.test.ts`：19/19 通过（覆盖 evolver 构造即编译全部工具 schema）
- 类型检查：WeeklyReportTool 相关文件零错误
- **重启后实测调用 weekly_report：返回完整第 35 周（2026-08-24~30）markdown 周报**——信号分级分布（A3/B4/C3）、规则归因（R-001）、亮点与改进建议齐全 → 工具注册 + 后端连通 + 业务产出三重验证通过。

### 6.3 守护链确认（防 9/2 式断档重演）

- dsh launchd plist `KeepAlive=true` + `RunAtLoad=true` + ThrottleInterval 10s → 实例崩溃/被杀自动拉起。
- scheduler-watchdog（com.pi-investment.scheduler-watchdog）每 900s 巡检。
- 9/2 15:30-16:45 断档根因是**无 dsh 实例运行 native-scheduler 的时间窗口**（lastFired 全部落在 19:11 同一分钟=启动 baseline 非投递），非守护缺失。9/3 起 dsh 持续在线至各验证窗口。

### 6.4 变更集状态

- 改动文件：上述 evolver 5 文件（均属本任务自有改动）
- 检查点：agent-self/20260903-002555（self_restart 自动创建）；验证通过后 self_finalize(merge) 合回 main

### 6.5 遗留验证点（时间驱动，非代码问题）

| 窗口 | 验证内容 | 判定标准 |
|---|---|---|
| 9/3(四) 16:00 | distill 首窗投递 | office:delivered + 次日蒸馏报告/提案落库 |
| 9/5(六) 10:00 | variant 首窗 | 同上（evolution-weekly-variant） |
| 9/6(日) 11:00/11:30/12:00 | gate/meta/weekly-report 首窗 | gate→candidate 裁决痕迹；weekly-report 任务 agent 能调通 weekly_report 工具出报告 |


