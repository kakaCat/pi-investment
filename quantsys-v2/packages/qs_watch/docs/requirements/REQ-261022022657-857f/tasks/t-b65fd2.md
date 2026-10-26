# t-b65fd2 扩 metrics 读数并收口回归

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
扩 metrics 读数并收口回归

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
pytest tests/plan -q 全绿；pytest tests -k watch -q 无新增红（仅允许两例预存红）；curl -s http://127.0.0.1:5001/api/watch/metrics 含 news_todos_today 与 reflection_woken_today（缺数 null）；给出三条读数样例。

## 实施方案（implementation）
改 adapters/inbound/fastapi_app/routes/watch_async.py：/api/watch/metrics 增 news_todos_today（watch_todos evidence.source=news 当日计数）与 reflection_woken_today（当日唤醒计数），异常返回 null；补 tests/plan/test_metrics_ext.py；跑两套件回归并在 test-evidence 记读数。

## 上游产出摘要（dependsSummary）
- 接线反思唤醒通道（waker 注入 + 任务调用）
- 扩展 on_fill 批次退役与事件留痕
- 接线消息→P1 待办与唤醒（含 24h 去重）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T18:39:02.223Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

收口卡完成：metrics 两读数上线，plan 139 例绿，watch 无新增红。

### 完成项

- metrics 扩展两字段（news_todos_today / reflection_woken_today），失败降级 null
- tests/plan/test_metrics_ext.py 3 例全绿
- 收口回归：pytest tests/plan -q 139 passed；pytest tests -k watch -q 791 passed / 2 预存红（同基线，无新增）

### 改动文件

- `docs/requirements/REQ-261022022657-857f/tasks/t-b65fd2.md`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/watch_metrics_async.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_metrics_ext.py`

---
