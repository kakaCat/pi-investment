# 每日召回审计报告 — 2026-08-15（memory 域 Agent）

> 数据范围：2026-08-14 00:00 ~ 2026-08-15 24:00（DB 直连读取，recall_audit API 故障不可用）
> 生成时间：2026-08-15 19:10

## 一、核心统计（DB: quant_investment.quant.memory_recall_audit）

| 指标 | 8/14-8/15 | 8/15 当天 |
|------|-----------|-----------|
| 总召回 | 8,281 | 2,533 |
| 注入 | 8,005（97%） | 2,380（94%） |
| 抑制 | 276（3%） | 153（6%） |
| 抑制原因 | 全部 empty-result | 全部 empty-result |

- 总表存量：8,299 条（id 1~8299），首次记录 2026-08-13 20:22，最新 2026-08-15 19:02
- flow 分布（8/14）：wake-event 8,246 / interactive-chat 13 / scheduled-task 22
- 评分直方图（8/14）：0.0-0.1: 7,320；0.9-1.0: 8,713；中间 0.1-0.9 全部为 0（双峰异常）

## 二、严重问题（P0-P2）

### P0-1 召回审计 API 瘫痪（审计链路本身故障）
- quantsys-v2 FastAPI(5001) `/api/memory/recall-audit` GET/POST 间歇性超时挂起
  - health 正常（200），recall-audit GET 10s 超时，POST 3s abort（HTTP 000）
- pg_stat_activity 显示大量 idle-in-transaction 连接（31+ 条，连接池≈40 接近耗尽）
- 后果：
  - agent-ts 写入全部降级 JSONL（.pi-invest/recall-audit.jsonl 21,857 行 vs DB 8,299 行）
  - recall_audit 工具 list/stats/feedback 全部返回空，无法完成审计标注
- 证据：早盘 06:45 已有一条 fact 记忆记录同一问题（FastAPI 连接池泄漏），本次审计独立复现确认
- 修复：重启 FastAPI 释放连接；排查 update_feedback 的 with_for_update 事务提交/回滚路径

### P0-2 重试风暴污染召回数据（8/14 已记录，复发）
- 8/14 以来 8,239/8,281 条（99.5%）由 wake-event「[系统] 上轮回复为空或被截断」重试消息触发
- 每次重复召回并注入相同 memory_id=70/60（分数仅 0.016-0.033）
- 8/14 的同类问题已记入 memory 60/70（「wake重试风暴」审查标记），未落地修复即复发
- 修复：RecallService 对系统重试类消息（queryText 含「上轮回复为空或被截断」）直接跳过召回

### P1-3 低分命中注入无门槛 + hybrid 评分双峰异常
- 8/14 以来 7,320 个命中 score<0.6 仍注入（大量 0.0-0.1 分）
- 门禁只抑制 empty-result，未对低分命中设阈值
- 评分分布 0.0-0.1 与 0.9-1.0 双峰、中间全零 → 疑似 bm25/vector 分数未归一化或取 max 而非融合
- 修复：quality-gate 增加 score 下限（如 <0.35 抑制）；核查 hybrid 评分融合逻辑

### P2-4 scheduled-task 语义召回价值低
- 8/15 scheduled-task 11 条全部被抑制（长工作流文本无真实查询意图）
- 修复：scheduled-task 默认跳过语义召回或仅用 bm25

## 三、标注情况
- 本次新增 agent feedback：0 条（recall_audit API 故障无法提交；存量 49 条 feedback 未触碰，human 优先）
- 通过 DB 直连完成等效的统计与清单分析

## 四、已落盘产物
- 审查清单 3 条（memory_write category=recall-audit-review，⚠️ 疑未真正落盘，见下）
- 日报 1 条（memory_write category=daily-recall-audit，⚠️ 疑未真正落盘，见下）

## 五、⚠️ 衍生发现：memory_write 疑似静默失败
- memory_write 工具返回 "Memory saved (local)"，但：
  - .pi-invest/memory/daily/2026-08-15.jsonl 最后修改 14:45（早于本次 19:09 写入），内容无日报/审查清单
  - 全盘 grep 无「每日召回审计日报 2026-08-15」记录
- 可能原因：v2 memory API 超时 → 降级 file-fallback，但 file-fallback 返回 path 非空应显示 "memory/daily"；显示 "local" 说明 provider 返回空对象（疑 v2-client write 异常路径返回 {} 且降级未生效/未落盘）
- 影响：审计成果未持久化，需以本文件为准
- 修复：核查 MemoryProvider 降级链路（provider-manager + v2-client write 异常返回）

## 六、后续行动建议
1. P0：重启 quantsys-v2 FastAPI（释放连接池）→ 恢复 recall-audit API 与 memory_write
2. P0：RecallService 拦截系统重试消息（止损数据污染）
3. P1：quality-gate 增加分数下限；核查 hybrid 评分归一化
4. P1：修复 memory_write 静默失败（降级链路）
5. P2：scheduled-task 跳过语义召回
