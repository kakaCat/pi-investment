# t-88d4da 新闻与政策扫描接入消息桥

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新闻与政策扫描接入消息桥

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/application/test_news_watch_service.py tests/application/test_policy_watch_service.py -q 退出码 0；critical 命中建 1 条待办、soft 建 0 条；bridge 未注入时行为与现状一致。

## 实施方案（implementation）
packages/qs_watch/.../news_watch_service.py 与 policy_watch_service.py 增加可空 bridge 注入；critical 命中持仓标的/持仓板块时调 dispatch，未注入保持只发卡；账户与板块映射在服务内解析；补 tests/application/test_news_watch_service.py、test_policy_watch_service.py 断言。

## 上游产出摘要（dependsSummary）
- 消息→P1 待办桥（critical 建单 + 唤醒）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:38:18.170Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试通过：两条扫描路径接入消息桥，48 例全绿，未注入桥时保持旧行为。

### 完成项

- 新闻扫描：critical 命中持仓 → 交给消息桥（带 symbol/account/titles/words），soft 不调用
- 政策扫描：critical 命中持仓 → 交给消息桥（带 symbol/sector），soft 不调用
- 未注入桥时行为与现状一致；桥抛错不影响发卡与扫描
- 验收：news + policy + hooks 三套共 48 例全绿

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/news_watch_service.py`
- `../../packages/qs_watch/qs_watch/application/services/watch_engine/policy_watch_service.py`
- `../../tests/application/test_news_hooks.py`

### 下一步

复核：核对两条扫描路径与改造口径

---
## 汇报 2（2026-10-21T12:38:22.410Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：两条接入与设计一致，兼容与错误隔离已核对。

### 完成项

- 口径核对：个股按持仓标的命中、政策按持仓板块映射后的标的命中，均只对 critical 建单
- 兼容核对：bridge 参数可空；不传时两条扫描路径与改造前逐字一致
- 副作用核对：桥调用包在 try/except，发卡与扫描结果不受影响
- 偏离登记：政策侧账户未解析（按无归属建单，由待办路由兜底），与设计「无账户照常建单」一致

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/news_watch_service.py`
- `../../packages/qs_watch/qs_watch/application/services/watch_engine/policy_watch_service.py`

### 下一步

本卡关闭，进入盘后窗口卡

---
