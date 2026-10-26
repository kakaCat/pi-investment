# 拆分计划（REQ-261022022657-857f · 交易闭环补口）

目标：把三处闭环断点接上——反思任务叫醒 agent、减仓部分成交收敛批次、持仓消息命中进待办并唤醒；
只接线不新建，零 schema 变更。做法：按设计 S-1~S-6 落 5 张卡，先两条独立链路（反思/批次/消息），
最后一张收口做回归与读数。

## 任务表

| 计划 key | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 | 工作量 |
|---|---|---|---|---|---|---|
| t1 | 接线反思唤醒通道（waker 注入 + 任务调用） | implement | backend | — | `pytest tests/plan/test_reflection_job.py -q` 全绿，含「注入 waker 被调用一次」「waker 失败 overdue+1」两新例；断言 review_due_at 前移 | 1 卡（约 1 小时） |
| t2 | 实现减仓批次匹配纯函数 | implement | backend | — | `pytest tests/plan/test_plan_batch_convergence.py -q` 中 match_reduce_batches 用例全绿：比例 0/0.33/0.8/1.0 四档分别返回 [..] 期望下标；越界 ValueError | 0.5 卡 |
| t3 | 扩展 on_fill 批次退役与事件留痕 | implement | backend | t2 | `pytest tests/plan/test_plan_batch_convergence.py -q` 全绿；`select detail from quant.trading_plan_events where kind='fill'` 可见 detail.batch；卖光后计划 closed；重复回执幂等 | 1 卡 |
| t4 | 接线消息→P1 待办与唤醒（含 24h 去重） | implement | backend | — | `pytest tests/plan/test_news_exit_linkage.py -q` 全绿；`select id,level,evidence->>'news_id' from quant.watch_todos where evidence->>'source'='news' limit 3` 可见行；重复扫描不建第二条 | 1 卡 |
| t5 | 扩 metrics 读数并收口回归 | test | backend | t1, t3, t4 | `pytest tests/plan -q` 全绿且 `pytest tests -k watch -q` 无新增红；`curl -s /api/watch/metrics` 返回 news_todos_today/reflection_woken_today 两字段 | 1 卡 |

## 接口清单 ↔ 接收卡 key 对照

| 接口 | 接收卡 key |
|---|---|
| IF-1 PlanReflectionJob waker 注入 | t1 |
| IF-2 match_reduce_batches 纯函数 | t2, t3 |
| IF-3 PlanService.on_fill 扩展 | t3 |
| IF-4 link_news_to_todo 消息联动 | t4 |
| IF-5 metrics 扩展字段 | t5 |
| IF-6 wake_todo_owner（复用不改） | t4 |

## 依赖理由

- t3 依赖 t2：on_fill 调用纯函数，函数签名先定后接线。
- t5 依赖 t1/t3/t4：收口卡要读三条链路的真实结果，且 metrics 扩字段需要前三条链路可用。
