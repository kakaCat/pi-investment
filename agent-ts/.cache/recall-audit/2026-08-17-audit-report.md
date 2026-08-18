# 每日召回审计报告 — 2026-08-17（memory 域 Agent）

> 数据范围：2026-08-16 00:00 ~ 2026-08-17 24:00
> 数据来源：JSONL 回退文件（.pi-invest/recall-audit.jsonl，27,738 行）；recall_audit API 故障不可用
> 生成时间：2026-08-17 19:05

## 一、核心统计（过去 24h，来自 JSONL）

| 指标 | 数值 |
|------|------|
| 总召回 | 5,886 |
| 注入 | 0（0%） |
| 抑制 | 5,886（100%） |
| 抑制原因 | 全部 empty-result |
| flow 分布 | wake-event 5,877（99.8%）/ scheduled-task 6 / interactive-chat 2 / skill-invocation 1 |
| 含 hits 的记录 | 0 条 |

- 全量 JSONL 27,738 行；最后一次 passed(注入) 记录为 2026-08-15 02:36（wake-event 重试，命中 memory 70/60，score 0.016-0.033）
- 真实查询（skill-invocation「华润三九 深度分析」、interactive-chat「中铝买卖点是多少」「对比」）全部召回为空

## 二、严重问题（全部延续自 8/15 报告，无一修复）

### P0-1 召回审计 API 瘫痪（第 3 天未修复）
- V2 API `/api/memory/recall-audit` GET 与 `/stats` 挂起：curl 8s 无响应（health 正常 200、db_connected=true）
- recall_audit 工具因此返回空（total=0），无法完成 list/stats/feedback
- 8/15 报告已记录：疑 FastAPI 连接池泄漏（31+ idle-in-transaction），建议重启 + 排查 with_for_update 事务路径

### P0-2 重试风暴污染召回数据（第 4 天复发）
- 过去 24h 5,877/5,886（99.8%）为 wake-event「[系统] 上轮回复为空或被截断」重试消息
- 8/14 起持续；8/14 是低分注入（score 0.016-0.033），8/16 后因检索故障转为全部 empty-result 抑制
- RecallService 未拦截系统重试消息

### P0-3（新增证据）记忆检索后端故障
- `/api/memory/search` GET 挂起（curl 8s 无响应）→ 所有召回 empty-result、0 注入
- 本地 memory_search 也返回 No relevant memories（与 API 挂起一致）
- 这是"0 注入"的直接原因：不是没有记忆，是检索链路断了

### P1-4 memory_write 静默失败（8/15 第五节发现，未修复）
- memory_write 返回 "Memory saved (local)"，但 .pi-invest/memory/daily/ 下无 8/16、8/17 文件（最新 8/15 14:45）
- 全盘 grep 无今日日报/审查标记 → 本次审计日报已改落盘 .cache/recall-audit/2026-08-17-audit-report.md 兜底

## 三、标注情况
- agent feedback 标注：0 条（无注入记录可标注；API 无法查询）
- 存量 human feedback 未触碰（human 优先）

## 四、已落盘产物
- 审查标记：P0 故障清单（memory_write 尝试写入，但疑未落盘——同 P1-4）
- 日报：memory_write 尝试写入（疑未落盘），本文件为权威版本

## 五、后续行动建议（优先级排序）
1. **P0**：重启 quantsys-v2 FastAPI 释放连接池 → 验证 recall-audit 与 memory/search 恢复
2. **P0**：排查 memory 路由挂起根因（idle-in-transaction / 连接池耗尽 / with_for_update 事务未提交）
3. **P0**：RecallService 拦截系统重试消息（queryText 含「上轮回复为空或被截断」直接跳过召回）
4. **P1**：修复 memory_write 降级链路（v2-client write 异常返回空对象导致静默失败）
5. **P1**：API 恢复后回灌 JSONL 27,738 条到 DB，重跑过去 3 天审计标注
