# t-cb5d73 策略日检如实上报并修回通知方法·研发

> 需求：REQ-261004154902-a7cd V13 策略实现缺陷排查（因子/模型/调仓/止损全链路取证）

## 在做什么
策略日检如实上报并修回通知方法·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-04T08:11:53.406Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

研发子卡：日检第一次做到「干了就说干了、没干就说没干、失败就说失败并通知人」。顺带修掉那个让每次调仓都崩在最后一步的通知方法缩进错位。

### 完成项

- 修掉一个真 bug：调仓通知方法此前被缩进在 if __name__ 块里（不是类方法），每次调仓走到第 10 步必抛 AttributeError，而那时钱已下单、错被吞、通知从未发出
- 日检不再丢弃调仓结果：失败如实变成 ok=False、status=failed、error 非空，并主动外发
- 保留具体失败原因：因子为空就是 factor_empty，不再被笼统的 rebalance_failed 盖掉
- 模型未加载从「合理跳过」升格为「失败」——环境坏不是跳过
- 止损执行抛错也会如实上报（此前只有一行日志）
- 通知只当副作用：发送失败只留痕（notify_error），不把一次成功的调仓判成失败
- 上层三态映射：daily_check 如实回 success / skipped / failed；手动调仓不再无条件报成功
- 补上通知结果字段：调仓返回值与日检 detail 都带 notify_ok 与 notify_error

### 改动文件

- `live_trading/simulation_trader.py`
- `application/services/strategy_service.py`

---
