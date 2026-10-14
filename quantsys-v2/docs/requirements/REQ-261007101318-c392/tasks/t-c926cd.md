# t-c926cd 补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
跑 pytest tests/services/test_watch_engine_trading_day_gate.py tests/notification -q 全 passed，且用例总数 ≥ 改动前基线 228（新增用例数 >= 3）；每条新用例失败时能指出具体行为（不得只断言 not raises）。

## 实施方案（implementation）
扩展 tests/services/test_watch_engine_trading_day_gate.py：用 now_fn 序列 + _stopped 标志驱动 run_forever 跑两轮，断言休市日不调用 tick（可用打桩计数）；新增用例断言 _log_market_closed 的按日去重（同日多次调用只留一条留痕）；扩展 tests/notification/test_notification_audit_repository.py 或新增用例，断言 notification_factory 在审计仓储装配失败时降级为 repository=None 且通知仍发出。

## 上游产出摘要（dependsSummary）
- FR-1 休市日闸门：tick() 日级收敛到 TradingDayGuard（回填）
- FR-3 外发审计 + 来源标识（回填，含建表迁移）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T05:55:17.895Z，窗口 session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544）

t5 父卡收尾：补 4 条未覆盖用例，总数 232 ≥ 228，可证伪性经变异测试证明。

### 完成项

- 子卡三段全 done：研发 t-2ae248 / 复核 t-8ccf53 / 测试 t-094f32
- 验收标准逐条命中：卡内命令 94 passed、总数 232 ≥ 基线 228、新增 4 条 ≥ 3 条
- 新用例可证伪性经变异测试验证（拆掉 run_forever 日级门即 1 failed），engine.py 已字节级还原
- 设计 §6 三项未覆盖（run_forever 整环 / 留痕去重 / 装配降级）全部补齐
- 剩余未覆盖两项（异地来源负例、sender_id host 段一致性）已在设计文档声明为能力上限/已知瑕疵，不在本卡范围

### 改动文件

- `tests/services/test_watch_engine_trading_day_gate.py`
- `tests/notification/test_notification_audit_repository.py`

### 下一步

父卡关账；t6 挂起等待 2026-10-08 复市回执（时间型，今日无法完成）

---
