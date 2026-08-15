# 每日召回审计报告 2026-08-14（审计范围 08-13 ~ 08-14）

## 统计（recall_audit stats，date_from=2026-08-13, date_to=2026-08-15，date_to 排他）
- 总数 4280，注入 4211（98.4%），抑制 69（1.6%，全部 empty-result，无分数阈值抑制）
- by_flow: wake-event 4240（注入4177/抑制63）、scheduled-task 23（18/5）、interactive-chat 17（16/1）
- score_histogram 异常：0.0-0.1 有80条、0.9-1.0 有8376条（>范围总数，疑似全库口径），中间区间全空

## 标注（agent feedback，仅标无既有 feedback 的记录）
- 成功 4 条 irrelevant：audit 4246 memory 60/18、audit 201 memory 60/18（wake 重试消息噪声注入）
- 未写入 3 条 relevant（后端连接池故障）：audit 2806/24 → memory 64（盘中快检持仓经验）、audit 23 → memory 63（早盘分析经验）
- 跳过未标：interactive-chat 低分注入记录（audit 2740/2508/2713/18，分数0.016无法判断相关性）；audit 2824/17 内容不确定

## 关键发现
1. 【严重】wake 重试风暴：08-14 09:37-19:01 数百次"[系统]上轮回复为空或被截断"重试占 wake-event 绝大部分，每次注入相同 memory 60/18（bm25 高分 14.26/11.89 但语义无关，语义搜索无匹配内容）。98% 注入率系重试噪声虚高。
2. 低分注入持续：真实查询"今天股市大跌看看有什么机会吗"命中分数 0.016 仍注入（08-13 日报已记录 scheduled-task 0.016-0.031 问题，未解决）。
3. 【严重】写路径事务泄漏：feedback/memory_write 请求后连接停留 idle in transaction 不释放，SQLAlchemy 池（pool_size=10, max_overflow=20，无 pool_recycle）被占满，写操作全部超时。已 pg_terminate_backend 清理 31 个连接（DB 侧恢复），但 SQLAlchemy 池内连接对象计数未释放（无 pool_pre_ping），写路径仍间歇失败。root cause：repository 查询/session 生命周期未及时 commit/rollback/close。
4. stats 时间过滤 date_to 排他：date_from=08-13&date_to=08-14 返回 0，需 date_to=08-15 才覆盖 08-14。
5. 并发调用 feedback 会加速打爆连接池（7 并发 → 立即 QueuePool overflow），应串行。

## 人工审查清单（3 项，memory_write category=recall-audit-review）
1. wake 重试风暴（已写入 #70）：重试循环无上限 + 系统消息应跳过召回 + memory 60/18 词面高分原因
2. 个股查询召回缺口（未写入）："中国铝业发生什么了"召回 51/54/27 但库中无该股记忆
3. 低分注入未解决（未写入）：bm25 应加绝对低分阈值

## 建议
- 修复 wake 重试循环根因（agent 回复为空→无限重试），系统内部消息跳过记忆召回/注入
- bm25 命中加绝对分数下限（如 <1.0 不注入），或归一化 <0.3 丢弃
- 修复 session 事务生命周期（请求结束 commit/close，加 pool_pre_ping/pool_recycle）
- 为重要个股建事件记忆索引（"中国铝业"查询无命中）
- 修复 stats 时间口径（date_to 排他 vs 直觉含当日）与 score_histogram 范围口径

## 已试方案
1. 串行重试 feedback/memory_write → 间歇成功，连接池反复被打满
2. 等待 60-120s → 不恢复（连接泄漏非临时占用）
3. pg_terminate_backend 清理 idle in transaction → DB 侧恢复，SQLAlchemy 池计数未释放，写路径仍不稳
4. 确认后端进程健康（health ok, db_connected true），问题在应用层连接池
