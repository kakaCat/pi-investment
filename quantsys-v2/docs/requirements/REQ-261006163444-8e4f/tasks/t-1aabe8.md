# t-1aabe8 仓储加分域只读方法并把评级计数改为 distinct·复核

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
仓储加分域只读方法并把评级计数改为 distinct·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T08:49:31.640Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

复核段完成：仓储改动与设计契约一致；一处必要修正（交易日取够 5 个）已如实登记并补回归锁。

### 完成项

- 对照 design/interfaces §2 逐条核对：SQL 形态、无时间过滤、失败先 _safe_rollback 再抛，全部一致
- count_by_grade_on 的当日口径（func.date(created_at)）与 symbols 空集返回 0 均与契约一致
- 如实登记一处有意偏离：build_domain_snapshot 取 5 个交易日而非 2 个（否则 gap 2-4 被静默当存量），已在 kline_domain 与 design 中留痕
- 结论：除该必要修正外无偏离

### 改动文件

- `adapters/outbound/repositories/kline_quality_repository.py`
- `adapters/outbound/repositories/kline_repository.py`
- `application/services/kline_domain.py`

---
