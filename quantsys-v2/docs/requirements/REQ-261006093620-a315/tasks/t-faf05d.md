# t-faf05d 数据契约：三值列 + CHECK + 8 行回填 + ORM·联调

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
数据契约：三值列 + CHECK + 8 行回填 + ORM·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-06T01:53:41.641Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

联调段完成：新列在仓储与调度装载链路都读得到，读到的策略分布与设计分类完全一致。

### 完成项

- 仓储读路径核实：get_task(250) 返回体含 trading_day_policy=trading-days
- 调度装载链路核实：list_tasks(enabled_only=True) 11 条全部含该字段，无缺字段
- 装载链路读到的策略分布 = always 3 / trading-days 7 / holidays 1，与设计分类（8 挂门 + 3 不挂）逐条吻合
- 两个库的列属性一致：NOT NULL、默认 always、三值 CHECK
- 本卡为纯加列与回填，无调用方改造，破坏面为零

### 改动文件

- `infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py`
- `infrastructure/persistence/orm/models/scheduler.py`

### 下一步

复核段：对照设计核对列语义与回滚路径，并做闸门边界复核（CHECK 是否真拦非法值）。

---
