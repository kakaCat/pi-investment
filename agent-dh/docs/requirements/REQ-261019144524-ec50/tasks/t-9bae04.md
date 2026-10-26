# t-9bae04 经验库噪声处置方案（unknown-symbol 记录清单与建议）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
经验库噪声处置方案（unknown-symbol 记录清单与建议）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：backend

## 得到什么结果
报告落 docs/requirements/REQ-261019144524-ec50/w4-experience-cleanup.md，包含三类处置（保留/隔离/作废）的记录数与理由；包含今后 symbol 必填纪律条款；经验库无记录被静默删除（experience_stats total 变化可解释）

## 实施方案（implementation）
①memory_search/experience_stats 按来源聚类；②抽样读记录内容判断价值；③处置方案落文档

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-19T16:39:28.565Z，窗口 session-503df447-3664-4823-ada8-9d779312d94a）

这一步做完，经验库 270 条噪声有了可裁决的处置方案：先修正口径——「155 条 unknown」是工具 200 条截断样本，库内真值 343 条中真实交易经验只有 73 条（其余是 distiller 迁移信封 64 条、伪代码 SYSTEM/000000 计 21 条、误置的工程记录 185 条，正是它们把经验_stats 胜率稀释成 1.5%）。处置建议：保留 73 / 隔离 85 / 作废 185（全部只标记不物理删除，执行待用户拍板并先备份留痕）；另给出今后 symbol 必填纪律四条。三个子卡此前速通无产出，本卡工作全部由本窗口补齐。

### 完成项

- 口径修正：需求「200 条中 155 条 unknown」是 experience_stats limit=200 截断样本；库内真值 343 条（psql 全量），真实标的经验仅 73 条（21.3%）
- 全量五分桶盘点：A 真实标的 73 / B 伪代码000000 计 8 / C 伪代码SYSTEM 计 13 / D distiller迁移JSON信封 64（全 08 月一次性）/ E 无symbol工程记录 185（09 月 175，流入已自然停止）
- 三类处置方案：保留 73 / 隔离 85（B+C+D，改 category 不删）/ 作废 185（E 桶 archived 标记不物理删除、作废前 10% 抽查蒸馏覆盖）；执行前提=用户裁决+pg_dump 备份+R-020 留痕
- symbol 必填纪律四条：真实 6 位代码必填、禁伪代码、无标的经验禁入 experience 命名空间、周报核查 unknown 占比 >5% 告警
- 验收③实测：全程只读零改动，343 条无静默删除

### 改动文件

- `docs/requirements/REQ-261019144524-ec50/w4-experience-cleanup.md`

### 下一步

按 DAG 推进 t-38602b（小仓位试单授权边界建议书）

---
