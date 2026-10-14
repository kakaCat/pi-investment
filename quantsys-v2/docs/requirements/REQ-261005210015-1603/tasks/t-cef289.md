# t-cef289 新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q → 12 passed（0 failed）；其中必须存在断言 find_result_failure(契约 B 的 result) is None 与 _mark_done 以 status='success' 被调用两条；全文件运行时 notify_guard 不得出现未声明的真实外发（如出现，用例应红）。

## 实施方案（implementation）
新增 tests/test_daily_jobs_notify_truthfulness.py，按设计文档的测试用例清单写 12 条：耗时格式 2 条、摘要状态分布 1 条、⚠️ 与 ✅ 语气各 1 条、streak 短语 1 条、有产出时不出现 streak 短语 1 条、截断渲染大于等于 K 1 条、查询失败降级 1 条、find_result_failure 对契约 B 的 result 返回 None 1 条、_mark_done 收到 success 1 条、其他任务（evening_pipeline 形态、无 summary）渲染与改造前逐字一致 1 条。打桩点铁律：monkeypatch.setattr 打在 adapters.inbound.fastapi_app.daily_jobs.runtime 模块的 _send_feishu / _mark_running / _mark_done，打在 alerting 或转发壳上会静默失效；用例数据用生产真实计数形态。

## 上游产出摘要（dependsSummary）
- handler 组装：summary / no_output / 空转统计（含纯函数与查询失败降级）
- runtime 接线：耗时按量级显示 + 零产出改 ⚠️（不动 status、不碰跳过分支）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-05T13:24:27.313Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

收尾汇总：通知层回归锁建立完成

### 完成项

- 三段链全部走完：研发 t-003afe、复核 t-8bec5b、测试 t-cca3af
- 14 条用例覆盖耗时格式、摘要状态分布、⚠️/✅ 语气、空转三态、降级、失败判定不变式、其他任务逐字不变
- 桩全部打在 runtime 模块，符合打桩点铁律
- 14 passed、零真实外发，与全量回归同跑 68 passed 1 skipped

### 改动文件

- `tests/test_daily_jobs_notify_truthfulness.py`

### 下一步

t8 回归与真实观察卡（依赖本卡已解除）

---
