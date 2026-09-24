# REQ-260924104605-ad0a 拆分计划：盯盘通知改版

> 目标：盯盘通知全部进专用群 + 意图驱动骨架 + 回执聚合 + 处置结论回执（闭环）。
> 做法：契约卡先行（字段/端口/签名定死）→ 模板/路由/聚合/闭环四张实现卡并行 →
> 迁移兼容卡 + 集成验收卡收尾。全部改动在 quantsys-v2（backend）；FR-1 配置已落地，
> 本计划只含其回归与回滚演练。

## 1. 改动盘点（对照 design/）

### 修改
| 文件 | 改动 | 承接卡 |
|---|---|---|
| infrastructure/notification/formatters/watch_level_templates.py | WatchCardItem 扩展可选字段；display 名称优先；render_p0/p1/p2 骨架重写；P1 判重；意图 emoji | t1/t2 |
| application/notification/notification_facade.py | direct 分支改 send_with_fallback('agent','feishu')；variables 补 rule_id | t3 |
| application/services/watch_engine/watch_channels.py | send_watch_receipt/send_watch_alert 携带 os_channel（risk_stop/watch_symbol） | t3 |
| application/services/watch_engine/receipt_service.py | render_receipt 签名扩展（name/close_reason/next_condition/action_kind）；result 三要素文案；时间格式与双竖线修复；collect/flush_grouped 聚合投递 | t4/t5 |
| adapters/inbound/fastapi_app/watch_sla_job.py | run_once 收集本轮回执组、末尾 flush；名称批量解析注入渲染 | t4 |
| application/services/watch_engine/todo_service.py | 可选 receipt_service 依赖；close 成功后触发 ReceiptService.result | t5 |
| adapters/inbound/fastapi_app/routes/watch_todo_async.py | 响应 data.receipt 由 None 填充为真实回执结果 | t5 |
| domain/watch/ports.py | 新增 StockNameResolver 端口（resolve_batch） | t1 |
| tests/notification/test_watch_templates.py、tests/watch/* | 模板/路由/聚合/闭环用例扩展 | t2~t5 |

### 新增
| 文件 | 说明 | 承接卡 |
|---|---|---|
| adapters/outbound/repositories/stock_name_resolver.py | quant.stocks 批量联查实现（只读，异常→全 None 降级） | t1 |

### 删除
无。无 DDL、无数据回填；notification_channels 的 UPDATE 已执行（FR-1）。

## 2. 任务表

| key | title | phase | side | depends_on | FR 覆盖 |
|---|---|---|---|---|---|
| t1 | 定契约：WatchCardItem 扩展 + StockNameResolver 端口 + render_receipt 签名 | implement | backend | - | FR-4, FR-13 |
| t2 | 重写四级模板为意图驱动骨架（判重/多账户/名称优先/卫生） | implement | backend | t1 | FR-4~7, FR-9, FR-10, FR-12, FR-13 |
| t3 | 接线 direct 渠道路由与回执 os_channel、补 rule_id 传递 | implement | backend | t1 | FR-2, FR-3, FR-10 |
| t4 | 回执聚合投递 + 名称批量解析 + 时间格式修复 | implement | backend | t1 | FR-8, FR-11, FR-13 |
| t5 | 处置结论回执：close 触发 result + 三要素文案 + 响应填充 | implement | backend | t1 | FR-14 |
| t6 | 迁移与兼容：FR-1 回归、回滚演练、旧渲染兼容、运维指引 | test | backend | t2, t3, t4, t5 | FR-1 |
| t7 | 集成验收：触发落群/网关降级/close 收卡/聚合一卡/pytest 全绿 | test | backend | t2, t3, t4, t5 | FR-2, FR-8, FR-14 |

## 3. 验收口径

每卡 acceptance 均可跑（pytest 用例名或可执行步骤），见落库任务卡；
t7 的 5 步集成验证对应需求文档 §1.2 的可证伪判定标准。
