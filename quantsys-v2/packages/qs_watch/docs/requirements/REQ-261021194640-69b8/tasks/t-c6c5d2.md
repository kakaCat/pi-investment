# t-c6c5d2 建交易包中立成交端口并保留旧路径转发

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
建交易包中立成交端口并保留旧路径转发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
venv/bin/python -m pytest tests/application/test_fill_port.py -q 退出码 0；断言注册/注销生效、旧 import 等价、无监听者时 notify_fill 返回 False 且不抛错。

## 实施方案（implementation）
新建 packages/qs_trading/qs_trading/application/ports/fill_listener.py：FillEvent 数据类、IFillListener 协议、register/get/unregister、notify_fill（自吞异常、未注册返回 False）。改 application/trading/paper_trading_engine.py 保留同名导出并转发，_notify_fill 改调 notify_fill。验证 import 与行为等价。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:14:31.107Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

成交回调端口迁到交易包中立侧 qs_trading.application.ports.fill_listener，旧路径 paper_trading_engine 保留同名符号转发；notify_fill 为唯一分发出口，未注册返回 False、监听者异常自吞只记日志。

### 完成项

- 新建中立端口模块：FillEvent 数据类、IFillListener 协议、register/get/unregister、notify_fill
- paper_trading_engine 改为同名转发，_notify_fill 调 notify_fill（实例监听器优先、回落模块级）
- 新增 24 个端口契约用例，覆盖注册注销、旧 import 等价、未注册返回 False、异常自吞
- 验收命令 pytest tests/application/test_fill_port.py -q 通过（24 passed）
- 相邻回归 pytest tests/application/test_fill_sync_service.py tests/application/test_fill_sync_factory_wiring.py tests/test_paper_trading_engine_risk.py -q 通过（45 passed）

### 改动文件

- `packages/qs_trading/qs_trading/application/ports/fill_listener.py`
- `packages/qs_trading/qs_trading/application/ports/__init__.py`
- `application/trading/paper_trading_engine.py`
- `tests/application/test_fill_port.py`

### 下一步

进入 fill-emit 卡：execute_trade 成交落库后构建 FillEvent 并调用 notify_fill

---
## 汇报 2（2026-10-21T12:16:24.393Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

父卡凭证补齐：改动文件按工作区根登记，四段子卡均已完成并留有测试读数。

### 完成项

- 按工作区根修正父卡改动文件路径（源码在上级仓目录）
- 本卡四段子卡全部完成：研发 / 联调 / 复核 / 测试
- 验收读数：端口 24 例全绿；相邻成交与回执回归 45 例全绿

### 改动文件

- `../../packages/qs_trading/qs_trading/application/ports/fill_listener.py`
- `../../packages/qs_trading/qs_trading/application/ports/__init__.py`
- `../../application/trading/paper_trading_engine.py`
- `../../tests/application/test_fill_port.py`

### 下一步

进入 fill-emit 卡：execute_trade 成交落库后发事件

---
