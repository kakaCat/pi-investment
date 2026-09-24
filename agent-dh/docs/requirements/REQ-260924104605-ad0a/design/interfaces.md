---
requirement_refs: [FR-2, FR-3, FR-4, FR-8, FR-13, FR-14]
---

# 接口设计：盯盘通知改版（REQ-260924104605-ad0a）

## NotificationFacade.send_watch_triggered（签名不变）（serves: FR-2）

参数/返回（ChannelResult）零变更；内部行为变更：notify_mode='direct' 分支改走
send_with_fallback('agent','feishu')。错误语义不变：Agent OS 不可达 → 降级飞书，
metadata 含 wake_status/fallback 标注；双路失败 → success=False。

## ReceiptService（应用层契约）（serves: FR-3, FR-8, FR-14）

- result(todo, terminal) 接线后由 TodoService.close 调用；返回
  {issued, duplicate, sent, kind, todo_id, channel, delivery_status, digest, message}（既有形状）。
- 聚合投递新契约：ReceiptService 暴露 collect/drain 语义——escalate/timeout 调用
  先入组（本轮缓冲），flush_grouped() 由 WatchSlaJob.run_once 末尾调用，按 kind 分组
  各发一张聚合卡并回写各行 delivery_status/message_id；sender 抛错 → 整组记 failed
  （不吞错）。空组 flush 为 no-op。
- render_receipt(todo, kind, period, *, name=None, close_reason=None, next_condition=None,
  action_kind=None)：result 分支渲染三要素；timeout/escalate 渲染为一行清单项
  （供聚合卡逐行拼接）。

## watch_channels.send_watch_receipt（payload 扩展）（serves: FR-3）

payload 新增 os_channel 字段（逻辑频道码）；经 facade 发送时写入
Notification.variables['os_channel']。超时/P0 → 'risk_stop'，其余 → 'watch_symbol'。

## StockNameResolver（新端口）（serves: FR-13）

resolve_batch(symbols: list[str]) -> dict[str, str|None]；实现联查 quant.stocks。
错误语义：查询异常 → 返回全 None（名称缺失降级），绝不抛进巡检主循环。

## POST /api/watch/todos/{id}/close（响应填充）（serves: FR-14）

响应 data.receipt 由 None 改为真实回执结果 dict（未发出时为
{issued:false, reason:'duplicate'}）。请求体契约不变（terminal/close_reason/
next_condition/action_kind）。

## 模板渲染入口（纯函数，签名稳定）（serves: FR-4）

render_watch_message(level, items) / resolve_level_template(level) 签名不变；
WatchCardItem 仅新增可选字段。未知级别 → P2 兜底 + 显式标注（既有语义）。
