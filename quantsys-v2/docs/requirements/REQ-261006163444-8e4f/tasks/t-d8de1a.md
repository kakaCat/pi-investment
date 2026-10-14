# t-d8de1a 仓储加分域只读方法并把评级计数改为 distinct·联调

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
仓储加分域只读方法并把评级计数改为 distinct·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-06T08:49:25.032Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

联调段完成：两个只读方法已被分域模块真实调用，真库结果与 SQL 复算逐项一致。

### 完成项

- 真库联调：build_domain_snapshot(KlineORMRepository()) 接出 5280 / 3 / 403，与 SQL 独立复算一致
- 掉出名单接出 ['002813','603183']，与 SQL 口径一致
- count_by_grade_on('D') = 404，与 count(distinct symbol) 相等

### 改动文件

- `adapters/outbound/repositories/kline_repository.py`

---
