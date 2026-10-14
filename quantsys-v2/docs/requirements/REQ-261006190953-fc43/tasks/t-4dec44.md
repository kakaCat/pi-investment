# t-4dec44 给净值仓储加唯一写入闸门，并让日收益基准按交易日回退·研发

> 需求：REQ-261006190953-fc43 业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点

## 在做什么
给净值仓储加唯一写入闸门，并让日收益基准按交易日回退·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T11:46:43.223Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

研发段：净值仓储成了唯一写入闸门，非交易日写不进去；读取可按交易日取数、基准回退到上一交易日

### 完成项

- upsert_equity_snapshot 加唯一写入闸门：非交易日不落库、返回 None、日志带五键注解
- 加 force 参数作显式旁路，仅限迁移/回滚/测试构造
- get_equity_snapshots 支持 trading_days_only + 注入交易日集合，limit 语义改为交易日数
- previous_valid_snapshot 支持按交易日回退基准（候选先放大到 400 再过滤）
- calculate_daily_return 签名不变，内部懒加载日历并把集合透传给基准
- 仓储模块级不引 application 层（懒加载，对齐 strategy_repository 既有做法）
- 新增 tests/test_equity_snapshot_trading_day_gate.py 共 11 例
- extend tests/test_equity_snapshot_daily_return.py 补 2 例基准接线测试

### 改动文件

- `adapters/outbound/repositories/simulation_repository.py`
- `tests/test_equity_snapshot_trading_day_gate.py`
- `tests/test_equity_snapshot_daily_return.py`

### 下一步

联调段：跑受影响的调用方（四条写入路径的测试面），确认没有把计划外的调用方改坏。

---
