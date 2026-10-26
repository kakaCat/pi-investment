# t-a5fa64 真实成交落库后发事件

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
真实成交落库后发事件

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/application/test_account_trade_fill_callback.py -q 退出码 0；断言卖出成交后监听方收到 action='sell' 且 trade_id 非空；注入抛错监听器时成交返回成功且日志含 fill_notify_error。

## 实施方案（implementation）
packages/qs_trading/qs_trading/application/services/account_trading_service.py 的 execute_trade 在成交 commit 后构建 FillEvent（trade_id/account/symbol/action/shares/price/filled_at/source='agent_trade'）并调 notify_fill，外层 try/except 只记日志；新增 tests/application/test_account_trade_fill_callback.py。

## 上游产出摘要（dependsSummary）
- 建交易包中立成交端口并保留旧路径转发

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:28:36.057Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

研发完成：真实成交在事务提交后发 FillEvent，异常不反噬成交，新增 4 例测试全绿。

### 完成项

- execute_trade 在 session.commit() 之后调用 _emit_fill_notification（源码顺序断言覆盖）
- 新增 helper：构建 FillEvent（account/symbol/action/shares/price/trade_id/filled_at/source=agent_trade）并调 notify_fill
- 回调异常只记 fill_notify_error，不回滚成交；未注册监听者为空操作
- 新增 4 例测试：事件字段、异常吞掉、未注册 no-op、commit 后发送
- 相邻回归：fill_sync_service + fill_port 共 62 例全绿

### 改动文件

- `../../packages/qs_trading/qs_trading/application/services/account_trading_service.py`
- `../../tests/application/test_account_trade_fill_callback.py`

### 下一步

联调：验证组合根注册的监听者能收到真实成交事件

---
## 汇报 2（2026-10-21T12:28:45.846Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

联调通过：真实成交事件可被组合根注册的监听者收到，字段与收敛器契约一致。

### 完成项

- 联调实测：经端口注册的监听者收到 sell/trade_id=7，链路与组合根注册同一注册位
- 组合根接线用例 test_fill_sync_factory_wiring 2 例全绿
- FillSync 收敛器与事件源字段对齐（account_name/action/shares/price/trade_id）

### 改动文件

- `../../packages/qs_trading/qs_trading/application/services/account_trading_service.py`

### 下一步

进入测试阶段：复跑验收与相邻回归

---
## 汇报 3（2026-10-21T12:28:52.920Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试通过：成交事件验收 4 例与相邻回归共 66 例全绿，无新增失败。

### 完成项

- 验收读数：test_account_trade_fill_callback → 4 passed
- 相邻回归：fill_sync_service + fill_port + 本卡用例共 66 passed
- 失败数 0

### 改动文件

- `../../tests/application/test_account_trade_fill_callback.py`

### 下一步

进入复核阶段：对照 IF-2 契约核对

---
## 汇报 4（2026-10-21T12:28:57.424Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：事件契约与失败语义无偏离；审计号缺失按契约降级处理，已登记。

### 完成项

- IF-2 核对：事件字段（账户/标的/方向/数量/价格/成交号/时间/来源）与契约一致
- 失败语义核对：回调在提交后执行、异常自吞只记日志，成交结果不可被回执改写
- 兼容核对：未注册监听者为空操作；旧调用方零改动
- 偏离登记：decision_audit_id 在 agent 成交路径暂无法取得，按契约留 None（消费侧退化为 trade 号标注降级）

### 改动文件

- `../../packages/qs_trading/qs_trading/application/services/account_trading_service.py`

### 下一步

本卡收尾后进入消息桥卡

---
