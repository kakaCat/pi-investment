---
requirement_refs: [FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-14]
---

# 测试设计：盯盘通知改版（REQ-260924104605-ad0a）

## 模板单测（tests/notification/test_watch_templates.py 扩展）（serves: FR-4, FR-5, FR-6, FR-7, FR-9, FR-10, FR-12, FR-13）

- 骨架顺序：意图→触发→现价→目的→预案→风控→下一步（AC-4.1）
- P0：@所有人/止损止盈/处置入口/不聚合（AC-5.1/5.2）
- P1 N=1：action 文本出现次数=1（AC-6.1/9.1）；N=3：1 完整+2 摘要含待办#与归属（AC-6.2）
- 多账户：同标的双账户 → 两行各带归属、不合并；无账户 → 「通用观察」（AC-4.3/4.4）
- 规则号：有规则显示真实号；无规则显示「手工」；不出现「规则#-」（AC-10.1）
- 名称：display=「名称（代码）」；name=None → 纯代码+「名称缺失」（AC-13.2/13.3）
- 卫生：全部渲染结果不含「频道：」（AC-12.1）
- P2 行首意图 emoji；P3 standalone_push=False 回归（AC-7.1/7.2）

## 回执与聚合单测（tests/watch/ 扩展）（serves: FR-8, FR-11, FR-13, FR-14）

- 同周期 3 条超时 → flush 后 sender 仅 1 次调用、卡片 3 行、每行带归属（AC-8.1）
- 重跑同周期 → 全 duplicate、sender 0 调用（AC-8.2）；空组 flush no-op（AC-8.3）
- 文案无微秒、无「| 周期 |」、due 只出现一次（AC-11.1）
- result 回执三要素（结论/原因/next_condition）；ignored 必含 NEXT 原文（AC-14.1/14.2）
- 名称批量解析：一次 resolve_batch、未命中降级（AC-13.1/13.3）

## 路由单测（tests/notification/ 扩展）（serves: FR-2, FR-3）

- direct 分支走 agent 优先；os_channel 直透到 AgentChannel（AC-2.1 的单测半）
- Agent OS 不可达 → 降级飞书 + metadata 标注（AC-2.2）
- 回执 payload 带 os_channel=risk_stop/watch_symbol（AC-3.1 的单测半）
- sender 抛错 → 整组 failed、不打断巡检（AC-3.2/8.2 纪律）

## 集成验证（人工跑，验收单操作步骤）（serves: FR-1, FR-2, FR-14）

1. 造 L1 规则触发 → 盯盘群收卡、alerts 群无（AC-1.2/2.1）
2. 停 :8080 再触发 → 降级直飞书送达、metadata 有标注（AC-2.2）
3. close 一条真实待办 → 盯盘群收处置后回执三要素卡（AC-14.1）
4. 回滚演练：10 行 webhook 改回 …172829 → 消息回原群（AC-1.3）
5. pytest quantsys-v2/tests/notification/ 与 tests/watch/ 全绿（回归）
