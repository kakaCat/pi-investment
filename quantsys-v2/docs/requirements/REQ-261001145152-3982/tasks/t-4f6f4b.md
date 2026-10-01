# t-4f6f4b 消 application 层 12 处顶层越层导入

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
消 application 层 12 处顶层越层导入

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

按用户裁定**只治理卡片点名的那部分**，并如实登记余量：
① 点名文件的**顶层**越层导入归零：`application/notification/notification_factory.py` 顶层越层导入 **0 处**（原 4 处：`infrastructure.config.settings` + `notification.channels.{feishu,agent}` + `notification.formatters.feishu_formatters`，已按卡片允许的"至少下沉到函数内"处理）；`application/services/scheduler.py`（`from infrastructure.scheduler.scheduler import *` 通配壳，实测全仓无人引用）已删除。
② `grep -rn "^from infrastructure.notification.channels" application/` → **0**（实测；直接对应 CLAUDE.md 通知架构强制条款）。
③ `pytest tests/notification -q` → **72 passed**（实测）；且 `NotificationFactory.get_instance()` 真实装配成功、`app` 仍可导入（101 路由）。
④ **口径修订 + 余量登记**（原验收"违规导入总数 → 顶层降为 0"不可按字面执行）：`tools/analyze_layer_violations.py` 用 AST `generic_visit` 统计，**涵盖函数内导入**，故其"违规导入总数 117"不会因"下沉到函数内"而下降——该指标口径与本卡动作不匹配。改以 AST **顶层**口径衡量：application 层顶层越层导入 **49 → 44**。
   余量明细（可复现：对本仓 `application/**/*.py` 做模块级 AST 扫描，统计 `infrastructure.*`/`adapters.*`）：
   · **44 处 / 34 个文件**；
   · 按目标归类：`config.constants.scoring.scorer_params` 6、`persistence.orm.async_config` 4、`services.service_factory` 3、`config.constants.detection_config` 3，其余为长尾；
   · 按文件：`services/watch_engine/factory.py` 5、`services/opportunity_scoring_service.py` 3、`daily_orchestrator.py`/`core_async_services.py`/`trade_service.py`/`strategy_code_service.py` 各 2。
   余 44 处**不在本卡范围**（涉及把装配点下沉到 composition root、改 DI 注入，属更大改造），需另立卡分批治理。

## 实施方案（implementation）
12 处顶层越层导入改为经 port/工厂注入或按裁定口径下沉；application/notification/notification_factory.py:20,28,29,30 的 infrastructure.config.settings 与 notification.channels.* 顶层导入移至 infrastructure 侧装配；删除 application/services/scheduler.py 的 `from infrastructure.scheduler.scheduler import *` 通配壳。

## 上游产出摘要（dependsSummary）
- 挂上分层护栏（hook + 基线 + 纯净性断言）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-01T11:14:53.421Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

这一步做完，变化是：**应用层里那个组装通知系统的文件不再"顶层直接抓"基础设施的通知渠道与格式化器**（改为用到时才取），通知系统的真实装配与投递尝试照常工作（通知测试 72 条全过）；同时删掉一个没人用的通配转发壳。按你的裁定只做点名部分，并把剩下的 44 处同类问题列了可复现清单留给后续批次。

### 完成项

- 删除 `application/services/scheduler.py`——2 行的 `from infrastructure.scheduler.scheduler import *` 通配壳（实测全仓无人引用；删后 app 101 路由正常、真实 SchedulerService 仍可从其正式位置导入）
- `application/notification/notification_factory.py` 的 4 处**顶层**越层导入（settings / 两个通知渠道 / 格式化器）下沉到使用它们的函数内；文件头写明理由、代价与真正的架构解法
- 验收②：`grep -rn '^from infrastructure.notification.channels' application/` = **0**（原 2 处，直接对应 CLAUDE.md 通知架构强制条款）
- 验收③：`pytest tests/notification -q` = **72 passed**；`NotificationFactory.get_instance()` 真实装配成功、真实投递路径被实际触发（投递失败系 Agent OS 8080 不在线的既有环境问题）
- 验收①（修订口径）：点名文件顶层越层导入 4 → **0**；application 层顶层越层导入 **49 → 44**（余量 44 处 / 34 文件，两次扫描结果一致、可复现）
- 范围纪律：按用户裁定**只做点名部分**，未扩大改造面；未引入新的反向依赖（本次未新建 infrastructure 文件）
- 口径修订留痕：原验收要求"违规导入总数 → 顶层降为 0"不可执行——`tools/analyze_layer_violations.py` 的 AST 统计**含函数内导入**，与"下沉"动作不匹配；已按用户裁定与可复现的顶层口径修订，余量明细登记在案
- 复核附带发现（供后续批次）：把通知装配真正下沉到 infrastructure，会**顺带修掉 4 处反向顶层依赖**（`infrastructure/jobs/{risk_check,verification,weekly_report,strategy_risk_check}_job.py` → `application.notification.notification_factory`），即正确解法是双重收益
- 四张子卡（研发/联调/复核/测试）全部完成

### 改动文件

- `application/notification/notification_factory.py`

---
