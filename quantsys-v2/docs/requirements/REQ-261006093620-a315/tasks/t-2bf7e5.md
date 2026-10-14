# t-2bf7e5 人工触发改投一次性 manual=True job·研发

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
人工触发改投一次性 manual=True job·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T02:01:09.444Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

研发段完成：人工触发改投一次性 manual=True job，既保住人工口子又不扰动 cron 排期；13 条全过。

### 完成项

- trigger_task_now 改为投递一次性 DateTrigger job，kwargs 显式带 manual=True
- 不再 modify_job：cron 的 next_run_time 不被扰动（旧实现会提前排期、可能吞掉当天正常排班）
- 保留 job 不存在时抛 ValueError 的既有语义（路由层靠它降级到 legacy 路径）
- 一次性 job 的 id 为 manual_{task_id}_{epoch}，执行后由 APScheduler 自动摘除
- misfire_grace_time=None：人工触发不该因宽限被丢
- 同步重写 test_trigger_task_now 四条断言（排期不变、manual job 唯一、参数为 True、未知 task 抛 ValueError）
- 该文件 13 条全过

### 改动文件

- `infrastructure/scheduler/apscheduler_service.py`
- `tests/infrastructure/test_apscheduler_service.py`

### 下一步

联调段：核实路由层 trigger 路径与 legacy 降级路径行为不变。

---
