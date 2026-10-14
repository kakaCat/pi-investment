# t-a7e4bb 数据契约：三值列 + CHECK + 8 行回填 + ORM·研发

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
数据契约：三值列 + CHECK + 8 行回填 + ORM·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T01:53:28.099Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

研发段完成：迁移与 ORM 同批落地，两个库都已 apply，8 行策略精确回填，漂移门 6 条全过。

### 完成项

- 新建迁移脚本：加列 + CHECK 约束 + 按 id 精确回填 8 行 + COMMENT
- ORM 模型加同名列（String(16) nullable=False server_default=always）
- dry-run 退出码 0，只打印 4 条 DDL 与 8 行回填计划，零写入
- 测试库 apply 通过：空表路径正常，无 row[0] TypeError（N7 负向已验）
- 生产库 apply 通过：8 行精确回填，其余行保持缺省 always
- 数据断言：挂门 trading-days 7 行、holidays 1 行（232）、其余启用行非 always 0 行、启用总数 11
- 库列属性核对：NOT NULL + 默认 always + CHECK 三值约束均在位
- ORM 漂移门 6 条全过
- 迁移加 SET LOCAL lock_timeout=30s，避免测试库 DDL 无限等锁

### 改动文件

- `infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py`
- `infrastructure/persistence/orm/models/scheduler.py`

### 下一步

联调段：核实新列经 ORM 读得到、APScheduler 装载链路能读到该字段。

---
