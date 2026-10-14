# t-0cb72d 修正 test_false_success_guard 的打桩点

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
修正 test_false_success_guard 的打桩点

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/test_false_success_guard.py -q → 17 passed；把 runtime._send_feishu 换成记录器后跑 _run_job，记录器被调用且文本含「每日任务完成」（机制自证）；桩改回 alerting 时真实 facade 调用数 > 0（反例确认）。

## 实施方案（implementation）
把两处 monkeypatch.setattr(host_alerting, '_send_feishu', …) 改为打在 daily_jobs.runtime（文件内已导入 host_runtime）；保留 _mark_running/_mark_done 桩与全部断言；注释改成正确的打桩点规则。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-03T07:12:18.270Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

这一步做完，跑测试不再真发通知了：假任务卡片从「4 张真实投递」变成 0，测试断言一条没改。

### 完成项

- 两处 _send_feishu 桩从 alerting 模块改到 runtime 模块（_run_job 真正读取的命名空间）
- 注释改写为可复用的打桩点规则：桩打在实现所在模块，转发壳与符号来源模块都无效
- 跑 tests/test_false_success_guard.py：17 passed，真实投递 4 → 0
- 反例确认：老桩（alerting）真实 facade 调用 2 次，新桩 0 次

### 改动文件

- `tests/test_false_success_guard.py`

### 下一步

接 t2：e2e 手动触发用例同样会真跑 handler 并发 2 张卡片，按同法打桩

---
