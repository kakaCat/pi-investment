# t-d5d9b6 FR-2 名称兜底：禁止把代码当名称（回填）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
FR-2 名称兜底：禁止把代码当名称（回填）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pytest tests/notification/test_req_c392_notification_contract.py -q 全 passed；其中 test_notifier_never_passes_symbol_as_name 必须断言：打桩 _lookup_stock_name 返回 None 时，传给 facade 的 kwargs['name'] is None（而非 '688525.SH'）；test_missing_name_degrades_explicitly_not_to_bare_symbol 断言正文含「名称缺失」。

## 实施方案（implementation）
application/services/watch_engine/notifier.py：facade 调用改为 name=payload.name or None（删除 name or symbol 的混同）；_lookup_stock_name 的取数口径并入领域端口实现 PgStockNameResolver.resolve_batch（与 SLA 巡检/回执同一份，异常/未命中返回 None）。infrastructure/notification/formatters/feishu_formatters.py：旧渲染路径名称缺失时显式输出「{代码}（名称缺失）」，不再回落成裸代码。tests/notification/test_req_c392_notification_contract.py 增补名称相关断言。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T05:44:05.185Z，窗口 session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544）

FR-2 父卡收尾：名称兜底落地并全链验证通过（10 passed，含两条点名断言）。

### 完成项

- 子卡三段全 done：研发 t-e5a244 / 复核 t-e75a19 / 测试 t-62e64a
- 验收标准逐条命中：全文件 10 passed；两条点名断言（name 传 None、正文含名称缺失）均 PASSED
- 口径单一性已核：引擎侧无第二条名称取数（PgStockNameResolver 为唯一来源）
- 用户 2026-10-07 已认可卡面（D-9），本卡为该契约的名称部分

### 改动文件

- `application/services/watch_engine/notifier.py`
- `infrastructure/notification/formatters/feishu_formatters.py`
- `tests/notification/test_req_c392_notification_contract.py`

### 下一步

父卡关账；进入 t3（FR-3 外发审计 + 来源标识）子卡链

---
