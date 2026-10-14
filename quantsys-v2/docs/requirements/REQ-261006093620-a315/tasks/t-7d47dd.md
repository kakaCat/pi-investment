# t-7d47dd 巡检口径同步：should_have_run 与 watchdog·联调

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
巡检口径同步：should_have_run 与 watchdog·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-06T02:04:16.950Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

联调段完成：只读检查器在生产库实跑，读数与预期一致；并如实登记迁移 updated_at 带来的护栏豁免副作用。

### 完成项

- 只读检查器在生产库实跑：11 启用 / 1 漏跑 / 10 改动豁免，退出码 2（真漏跑那条是 daily-strategy-validation，属不挂门的三条之一）
- 读数里能直接看到本次要修的那条假成功：pre-market-scan 上次 2026-10-06 09:25(success)
- 下一个休市日槽位是 2026-10-07 09:25——门接上后它会产出 skipped，而本模块现在会把该槽位认作已处理（R3 的假警由此消除）
- tests/test_should_have_run.py + tests/test_health_probe.py 共 36 passed
- 如实登记一处迁移副作用：回填时写了 updated_at=now()，使 10 条任务的配置改动护栏暂时豁免（约一个排班周期后自然失效）
- 未运行 health_probe 本体（它会真外发通知），只跑共用同一实现的只读检查器

### 下一步

复核段：核对 watchdog 的两处判据哪一处属本次范围。

---
