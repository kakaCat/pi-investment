---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 用例（REQ-260927144541-0481）

## UC-1 起链后一眼看清父子结构 <!-- serves: FR-3, FR-4 -->

1. 窗口绑定需求，调 `reqboard_task_run(task_id=父卡)` → 拿到 `job_id/run_id`；
2. 调 `reqboard_task_tree(parent_id=父卡)` → 看到 4 张子卡（研发/联调/复核/测试）各自 status 与是否跑过；
3. 对正在跑的子卡调 `reqboard_task_status(task_id=子卡)` → 读到真实 run 结果；
异常流：未绑定需求 → `REQBOARD_NO_BOUND_REQ`；父卡尚未开工 → `subtasks=[]` + note。

## UC-2 用错边推进被解释，而不是只被拒 <!-- serves: FR-5 -->

1. 手工窗口用 legacy 边推一张父卡（`in_progress→in_review`）；
2. 工具拒绝并说明：这张是**父卡**，合法边是 `todo→in_progress→done`，联调/测试由子卡承载；
3. 调用方改调 `task_tree` 看子卡，再按合法边重试或起链；
异常流：`acceptance` 传入空话 → `REQBOARD_INVALID_INPUT`（沿用计划期门槛）。

## UC-3 验收标准不可执行时当场能改 <!-- serves: FR-5 -->

1. 读到某子卡 acceptance 是模板空话（验收会被 `ACCEPTANCE_NOT_EXECUTABLE` 拦）；
2. 调 `reqboard_task_move(task_id, acceptance="命令：… → 看到 …")`（不传 `to`）；
3. 台账 `task.acceptance` 更新、卡文档「得到什么结果」同步；随后重提验收通过。

## UC-4 维护者新增工具时被门禁兜底 <!-- serves: FR-2, FR-7 -->

1. 新增工具或改返回体，忘声明返回键；
2. `output-contract` 静态扫描红（点名缺失键）；`tools-schema` 构造全工具，参数 DSL 写错即抛；
3. 修完再提交——不再靠人记得。

## 范围外（另行立项） <!-- serves: FR-1 -->

需求级工具（`clear_pause` 旧式参数、其它需求级契约）不在本需求：`clear_pause` 的参数修复走单独 chore；
`decompose`/`submit`/`ask_confirm` 等行为不动。
