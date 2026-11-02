# t-cd55bf 把 V2 服务救活并留下运行证据·测试

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
把 V2 服务救活并留下运行证据·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
目标命令输出全绿（贴命令与结果摘要）

---
## 汇报 1（2026-10-01T07:15:47.993Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

测试段：开关的开关语义与预期一致（只认 true），验收命令全绿；唯一局限是它不认 1，这与本仓其它开关口径相同、已在汇报中如实标注。

### 完成项

- 正负例：DISABLE_APSCHEDULER=""→False、"true"→True、"TRUE"→True、"false"→False、"1"→False（与仓内既有开关同口径：只认 true，不认 1）
- py_compile adapters/inbound/fastapi_app/main.py → OK
- 验收命令复跑：GET /docs = 200；select max(started_at) from quant.scheduler_runs 仍为 2026-09-13（调度未开火）
- 局限（如实记录）：开关只接受 true/TRUE/True，传 1 不生效——与本仓其它开关（DISABLE_DAILY_JOBS 等）口径一致，非本次引入的偏差

---
