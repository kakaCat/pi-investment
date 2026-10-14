# t-acb9b3 服务层返回 per_symbol 全量事实并修 original_count 取键·复核

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
服务层返回 per_symbol 全量事实并修 original_count 取键·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T08:51:37.282Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

复核段完成：per_symbol 与 grade 单点计算逐条对照设计，无偏离。

### 完成项

- 对照 design/data-model §6：per_symbol 恰含 8 键、键名与类型一致、只增不改
- grade 单点：_persist_quality_audit 未传值时兼容就计算，传入时不再重算（两条路径实测同值）
- original_count 取 total_trading_days，与 data_gap_detector 的真实返回键一致
- 结论：无偏离；既有 summary 键一个未改（回归 17 条全过）

### 改动文件

- `application/services/data_quality_service.py`

---
