# t-e95a2a 关闭待办接规则变更联动

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
关闭待办接规则变更联动

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/application/test_rule_change_linkage.py tests/application/test_watch_todo_close_rule_change.py -q 退出码 0；断言 ignored+rule_change 后规则字段变化、watch_rule_changes 新增 1 行且 trigger_id 非空；重复 close 返回 409。

## 实施方案（implementation）
adapters/inbound/fastapi_app/routes/watch_todo_async.py 透传 additive rule_change；packages/qs_watch/.../todo_service.py 在 close 成功后调 RuleChangeLinkage.apply（trigger_id 必填、事务、失败回滚）；新增 tests/application/test_watch_todo_close_rule_change.py。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:26:17.167Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

「不执行 → 改规则」联动交付完成：契约、错误码、顺序取舍与回归全部自证。

### 完成项

- 四段子卡完成：研发 / 联调 / 复核 / 测试
- close 接规则变更联动：先落规则与审计、后收敛待办
- 验收 64 例与合同/仓储回归 40 例全绿

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/todo_service.py`
- `../../packages/qs_watch/qs_watch/domain/watch/ports.py`
- `../../adapters/inbound/fastapi_app/routes/watch_todo_async.py`
- `../../tests/application/test_watch_todo_close_rule_change.py`
- `../../tests/application/test_todo_service.py`

### 下一步

进入 sla-deadline：执行期限巡检与时区归一

---
