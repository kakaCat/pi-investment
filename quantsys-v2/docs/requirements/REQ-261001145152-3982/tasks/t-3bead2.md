# t-3bead2 调度去重：4 套 → 1 套（分步灰度）·联调

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
调度去重：4 套 → 1 套（分步灰度）·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-02T02:30:20.828Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：**去重后的调度确实能跑**（接口看到 16 条、cron 不撞点，手动触发一条任务全链路走通并落留痕，今天也有任务正常跑完）——但同时**抓出一个真问题**：16 条启用任务里有 **5 条的命令在代码里根本没有对应实现**，属于"一触发必失败"，其中那条每 5 分钟跑一次的今天已经失败了 16 次。

### 完成项

- **联调①（② 调度端到端可用）**：`GET /api/scheduler/tasks?pageSize=100` 返回 **32 条（16 启用 / 16 停用）**，启用集合的 **cron 零撞点** ✅——去重结果在运行中的服务里成立
- **联调②（真的能跑任务）**：`POST /api/scheduler/tasks/232/trigger` → `{"success":true,"message":"Task 232 dispatched asynchronously"}`，并在 `quant.scheduler_runs` 生成新记录 **3360**（running）——证明 API → APSchedulerService → 执行器 → 写留痕整条链路通
- **联调③（既有成功案例）**：今日已有启用任务正常跑完并记 success——`chan-scan-daily`(10:10)、`daily-signal-push-fallback`(09:40) ✅
- **🔴 联调④（新发现的真问题，直接关系本卡）**：系统性核对 16 条启用任务的 command 是否有 handler——**11 条有效、5 条全仓零 handler（每次触发必然失败）**：`risk_check`(235 每周风险检查) · `data_pipeline_daily`(240 每日数据流水线) · `data_pipeline_weekly`(241 每周全量重建) · `signal_monitor_realtime`(251 realtime-signal-monitor) · `daily_equity_snapshot`(264 全账户净值快照)
- **联调⑤（失败噪音已量化）**：其中 251 `realtime-signal-monitor`（每 5 分钟）**今日已失败 16 次**，错误为 `Unknown scheduler command: 'signal_monitor_realtime'. Not in JobRegistry and not in legacy handlers`；历史累计失败 47 次。它创建于 2026-06-26（从 agent-ts 迁移），命令对应的 handler 已不在代码里
- **联调⑥（顺带发现）**：`weekly-risk-check`(246，停用) 与 `每周风险检查`(235，启用) 是**同一命令的中英同体对**，与我在库表去重时清掉的那批同型
- **待查**：我触发的那条 `data_quality_check`（全库质量扫描）已运行 135 秒仍未结束——需观察是"本身慢"还是"会卡住"（会卡住则说明 ② 缺少单任务超时，属另一个问题）
- **未完成即未完成**：本子卡（联调）在"5 条坏任务如何处置"有结论前不算完成——因为这直接改变启用集合，而卡片的验收正是围绕启用集合的正确性

---
## 汇报 2（2026-10-02T02:58:07.236Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：**把"打开调度"之后的真实健康面查了一遍**——链路是通的（接口看到 11 条、手动触发能真跑完并留痕、今天也有任务成功），但**启用集合里有 5 条任务的命令在代码里根本没有实现**（一触发就失败，其中每 5 分钟那条今天已失败 21 次）。经你逐条确认后把这 5 条停用（它们本来就不工作，停用只停噪音），并发现"停用 DB 还不够、得重载调度器"才彻底生效——现在调度器与实际启用集合一致，噪音归零；这 5 项能力缺位已如实记档。

### 完成项

- **联调①（② 链路端到端可用）**：`GET /api/scheduler/tasks` → 32 条（分页），启用集合 **cron 零撞点**；`POST /api/scheduler/tasks/232/trigger` → `dispatched`，并落执行留痕 3360（最终 **success**，耗时 1,052,851 ms ≈ **17.5 分钟**——不是卡死而是很慢，已记录）
- **联调②（既有成功案例）**：今日 `chan-scan-daily`、`daily-signal-push-fallback`、`pre-market-scan`、`每日数据质量检查` 各有 1 次 success ✓
- **🔴 联调③（本轮抓出并修掉的真问题）**：系统性核对"启用任务的命令是否都有实现" → **16 条里 5 条的命令全仓零 handler（每次触发必失败）**：`risk_check`(235) · `data_pipeline_daily`(240) · `data_pipeline_weekly`(241) · `signal_monitor_realtime`(251) · `daily_equity_snapshot`(264)。其中 251 每 5 分钟失败一次、今日累计 21 次、近一小时 12 次
- **联调④（处置，经用户逐条确认）**：5 条**全部停用**（它们本就每次失败，停用不改变任何实际行为、只停噪音）→ 启用集合 **16 → 11**，且**11 条的命令现在全部有 handler（无效 0）**
- **联调⑤（发现停用不够、还需重载）**：停用 DB 行后 251 **仍在触发**（10:50 又失败一次）——因为任务已注册进 APScheduler 的 jobstore；调 `POST /api/scheduler/reload` 后 jobstore **11 条、task_251 已移除**，再观察 75 秒**运行记录数不再增长**（1951 → 1951）✅ 噪音彻底停止
- **联调⑥（口径纠正，我先错后改）**：我最初建议把 240/241 "接线"到 `DataPipelineService.run_daily_update/run_full_rebuild`（依据是方法名精确对应）——**复查发现该服务生产从未接线（零生产调用方，只有测试用）**，接线等于**新做一项生产能力**（需要先定标的域/日期口径）。已向用户纠正并改为"全停 + 记能力缺口"
- **联调最终态**：jobstore **11** = 库表启用 **11**（已同步）；验收① cron 撞点 **0**；验收③ `adapters/` 里 `unified_scheduler` **0**；服务 `/docs=200`、探针 exit=0；近 5 分钟调度 **0 成功 0 失败**（无噪音）
- **能力缺口（已记录，待后续定夺）**：① 数据管道（`DataPipelineService` 存在但从未接线）；② 盘中实时信号扫描（`signal_monitor_realtime` 无实现；日频 `signal_generate` 已有）；③ 周度风险/组合分析（无实现；`risk_check_job` 是 V13 专用、`intraday_risk_check` 是盘中止损）；④ 账户净值快照（能力已在 ③ 编排器线程里跑，属重复故停用）

---
