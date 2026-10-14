# t-cda13d 通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

跑 ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q -k elapsed → 2 passed。再跑 ./venv/bin/python -c 断言五组：_format_elapsed(1.21) 得 1.2 秒、_format_elapsed(59.96) 得 60.0 秒、_format_elapsed(60.0) 得 1.0 分钟、_format_elapsed(125.0) 得 2.1 分钟、_format_elapsed(-1) 得 0.0 秒。旧行为不得变：以 evening_pipeline 形态（无 summary）跑 _summarize_result → 输出逐字为 kline_sync[updated=3, status=success]（用例 test_other_job_summary_unchanged 锁死）。可查字段：quant.inprocess_job_runs.result 的 summary。

## 实施方案（implementation）
adapters/inbound/fastapi_app/daily_jobs/alerting.py：新增 _format_elapsed(seconds) -> str —— 秒数小于 60 用 f-string 渲染为 X.X 秒，否则渲染为 X.X 分钟（均 1 位小数），负数按 0 处理；改造 _summarize_result —— 当 result.get('summary') 是非空字符串时，以其为 parts 首段且不再输出子字典段，否则逐字保持现有行为（其他任务零变化）；白名单键补 computed_ok / insufficient_sample / no_trades / data_gap / no_output（兜底可见）。不改 _send_feishu。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-05T13:11:20.274Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

通知层加了耗时格式化器，并让摘要优先采用 handler 自述的人话文本

### 完成项

- 新增 _format_elapsed：60 秒以内显示秒、否则分钟、负数按 0
- 实测 1.21→1.2 秒、59.96→60.0 秒、60.0→1.0 分钟、125.0→2.1 分钟、-1→0.0 秒
- _summarize_result 在有非空 summary 时以其为首段，且不再 dump 子字典段
- 无 summary 的任务输出逐字不变，用 evening_pipeline 形态对照验证通过
- 白名单补 computed_ok / insufficient_sample / no_trades / data_gap 与「无有效产出=True」兜底

### 改动文件

- `adapters/inbound/fastapi_app/daily_jobs/alerting.py`

### 下一步

t4 负责写入 summary 与 no_output；t6 用 12 条用例把本卡行为固化为回归锁

---
## 汇报 2（2026-10-05T13:16:09.837Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

收尾汇总：通知层契约落地完成，四段证据齐备

### 完成项

- 四段链全部走完：研发 t-39a1a8、联调 t-bf7712、复核 t-bf4521、测试 t-b8daeb
- 研发：新增 _format_elapsed 与 summary 优先，白名单补四个状态键与「无有效产出=True」
- 联调：runtime 与 alerting 读的是同一函数对象，真实 result 渲染出目标文案
- 复核：契约逐条对照通过，并修正了陷阱 1 表述强度（四组实测对照）
- 测试：40 passed、1 skipped，notify-guard intercepted=0 egress=0

### 下一步

t4 handler 组装可开工（依赖已解除）；t5 亦可用本卡的格式化器

---
