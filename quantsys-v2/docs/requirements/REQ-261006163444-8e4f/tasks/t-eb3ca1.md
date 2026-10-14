# t-eb3ca1 补分域纯函数用例（含 gap 边界与不变量）·研发

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
补分域纯函数用例（含 gap 边界与不变量）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T08:52:26.742Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

研发段完成：分域纯函数用例交付，含一条集成回归锁。

### 完成项

- 新增 tests/test_kline_domain.py：14 条用例覆盖设计 T1-T7 与契约用例
- 覆盖三分法、gap 4/5 边界、gap==1 的掉出定义、单交易日不可判、空输入退化、脏日期哨兵、三集合不变量、重复标的取最新、frozen、鸭子类型入参、失败退化
- 另加集成回归锁：build_domain_snapshot 必须取够 5 个交易日（否则 gap 2-4 被静默当存量）
- 实测 ./venv/bin/python -m pytest tests/test_kline_domain.py -q → 14 passed

### 改动文件

- `tests/test_kline_domain.py`

---
