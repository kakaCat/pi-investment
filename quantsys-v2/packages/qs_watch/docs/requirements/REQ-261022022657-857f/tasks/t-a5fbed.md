# t-a5fbed 接线消息→P1 待办与唤醒（含 24h 去重）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接线消息→P1 待办与唤醒（含 24h 去重）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/plan/test_news_exit_linkage.py -q 全绿：critical+持仓 → TodoService.create（P1/rule_change/evidence.source=news）且 wake 一次；同 news_id+symbol 24h 内不建第二条；无持仓不建待办仅通知。psql 查 watch_todos evidence->>'source'='news' 可见行。

## 实施方案（implementation）
新增 packages/qs_watch/qs_watch/application/services/watch_engine/news_exit_linkage.py：link_news_to_todo(...)——critical 且标的在持仓或计划 targets → TodoService.create(P1, action_kind=rule_change, evidence={source:news,news_id,title,hits,symbol,plan_id}) → wake_todo_owner；24h 去重查 evidence->>'news_id'+symbol 未闭合；out_of_scope 跳过留痕。news_watch_service 扫描尾部调用；开关 NEWS_TODO_ENABLED；新增 tests/plan/test_news_exit_linkage.py 三例。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T18:37:38.997Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

消息→离场链核实与回归：既有 69b8 实现已覆盖 FR-3，本轮补 5 例回归，无重复实现。

### 完成项

- 核对：FR-3 已由 REQ-261021194640-69b8 实现（news_todo_bridge + 工厂装配 + TodoService.assigner 唤醒）
- 本轮新增 tests/plan/test_news_exit_linkage.py 5 例回归（建单/派工/去重/soft/缺标的/扫描接线）
- 诚实登记：本卡未新增实现代码，不重复造桥

### 改动文件

- `docs/requirements/REQ-261022022657-857f/tasks/t-a5fbed.md`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_news_exit_linkage.py`

---
