# t-ec9d80 补挂止损/止盈写持仓状态·复核

> 需求：REQ-261021194640-69b8 盯盘执行闭环三接缝：成交回写·消息投递·待办闭环

## 在做什么
补挂止损/止盈写持仓状态·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/REQ-261021194640-69b8/design/` 逐条核对；`npx vitest run tests/` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-21T12:22:20.230Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：无偏离。补挂两路均写 holding；缺列与旧规则两种边界按 fail-open 处理；改动面仅限两处调用与测试。

### 完成项

- 对照设计逐条：补挂止损/止盈均写 holding，覆盖 FR-8 的两条创建路径
- 边界核对：create_rule 缺列时忽略新字段并告警，状态退化为未知 fail-open，不误跳过
- 副作用核对：仅两处补挂调用点变化，update_fields 不重置 position_state
- 测试替身与断言同步更新，无其它调用方受影响

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/position_lifecycle_service.py`
- `../../tests/application/test_watch_position_lifecycle.py`

### 下一步

测试段：复跑验收与状态门回归

---
