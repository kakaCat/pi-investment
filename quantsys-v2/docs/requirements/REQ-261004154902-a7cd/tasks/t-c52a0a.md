# t-c52a0a 新增结果契约与失败可见性出口

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增结果契约与失败可见性出口

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
venv/bin/python -m pytest tests/test_run_outcome.py tests/test_failure_sink.py -q 全过；用例含：①error 非空时 ok=False 无论 executed；②not_trading_day/not_due 映射 skipped、rebalance_failed/model_not_loaded 映射 failed；③report_failure 在 NotificationFacade 抛错时不向外抛且日志含 source/reason。

## 实施方案（implementation）
新增 application/observability/run_outcome.py（RunOutcome 值对象：executed/action/reason/error/detail，ok 只由 executed and error is None 派生，reason 受控枚举，to_dict 为既有字段超集）与 application/observability/failure_sink.py（report_failure(source, reason, error, severity, context)：先结构化日志再经 NotificationFacade 外发，自身绝不抛异常）；新增 tests/test_run_outcome.py、tests/test_failure_sink.py。不改动任何既有算法。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-04T08:05:21.503Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

这一步做完，任何自动链路的运行结果第一次有了统一说法与统一出口：结果对象自己就能回答「这次算不算真的干成了」，失败会同时落结构化日志并主动外发，不再只躺在日志里等人翻。具体是新增一个只读的值对象（RunOutcome）与一个失败出口（FailureSink），不含任何算法改动，后续 t2/t4/t6/t11 都接它。

### 完成项

- 新增 application/observability 包：run_outcome.py 定义结果契约，failure_sink.py 定义失败出口
- ok 与 status 的判定收成唯一实现：跳过类不算干成，出错一定不算干成，空转（executed 为真但未到周期）也不再算 success
- reason 做成受控枚举，写错值当场抛错，杜绝悄悄多出第四种状态
- 执行 run_daily_check 返回体仍兼容：executed / reason / action 三个键名不变，detail 平铺到顶层且不得覆盖保留键
- 失败出口先落日志再走既有通知门面（agent 优先、飞书降级），通道抛错也不向外抛，并把「外发未送达」也记成 error
- 通道可注入，测试与离线环境不会触碰真实外发
- 新增 tests/test_run_outcome.py（16 条）与 tests/test_failure_sink.py（6 条），共 22 条全部通过
- pytest 会话末 notify-guard 报告 intercepted=0 egress=0，零外发

### 改动文件

- `application/observability/__init__.py`
- `application/observability/run_outcome.py`
- `application/observability/failure_sink.py`
- `tests/test_run_outcome.py`
- `tests/test_failure_sink.py`

### 下一步

t2 与 t4、t6、t11 现在可以开工：日检按该契约如实上报、撮合批量不中断、调度失败接飞书兜底、账本超卖拦截都会复用这两个模块。

---
