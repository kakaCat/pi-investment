# t-3b5da9 服务层返回 per_symbol 全量事实并修 original_count 取键·联调

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
服务层返回 per_symbol 全量事实并修 original_count 取键·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-06T08:51:30.857Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

联调段完成：per_symbol 已被作业层真实消费，且未泄漏进 run 结果。

### 完成项

- 联调：作业层经 quality_result['per_symbol'] 真实消费该键（回填目标与域内统计都读它）
- 契约核对：per_symbol 未写入 run 结果（负向契约实测 False）；既有键一个未改
- 小样本真库跑通：2 只标的 per_symbol 形状与审计行逐项一致

### 改动文件

- `application/services/data_quality_service.py`
- `infrastructure/jobs/data_quality_check_job.py`

---
