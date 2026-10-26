# t-ebde4d 扩展 on_fill 批次退役与事件留痕·研发

> 需求：REQ-261022022657-857f 交易闭环补口：反思唤醒 + 减仓批次收敛 + 消息→离场

## 在做什么
扩展 on_fill 批次退役与事件留痕·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-21T18:35:59.045Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

批次退役研发段：on_fill 扩展 + 事件留痕 + 幂等 + 降级，PlanProgressPort 传 sold_ratio。

### 完成项

- on_fill 新增 sold_ratio，>0 时按累计比例匹配并逐批退役 reduce 规则
- 每批写 kind=fill 事件（detail 含 batch/trade_id/qty/remaining_qty/sold_ratio/rule_id/retired/degraded）
- 无匹配批次写 degraded_fill；同 trade_id 幂等（_already_logged）；remaining_qty<=0 → closing→closed

### 改动文件

- `docs/requirements/REQ-261022022657-857f/tasks/t-ebde4d.md`
- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/plan_service.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/outbound/repositories/plan_progress_port.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/plan_async.py`

---
