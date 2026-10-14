# t-0da0b9 补分域纯函数用例（含 gap 边界与不变量）·测试

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
补分域纯函数用例（含 gap 边界与不变量）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T08:52:27.274Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

测试段完成：14 条用例全绿。

### 完成项

- pytest tests/test_kline_domain.py -q → 14 passed（首轮 1 条断言写法报 TypeError，改 r.getMessage() 后全绿，被测代码无缺陷）
- notify-guard intercepted=0 egress=0
- 如实声明：子卡模板给的是 pnpm test（本仓 Python），实际用 pytest 自证

### 改动文件

- `tests/test_kline_domain.py`

---
