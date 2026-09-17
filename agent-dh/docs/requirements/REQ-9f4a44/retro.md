# REQ-9f4a44 复盘

## 做对了什么

1. **三个关键决策全部先确认后动手**：归档材料谁准备（Q1）→ 状态形状（Q2）→ 流程形状（两问），
   每步都用 `ask_user_question` 走回路，没有抢跑。REQ-ff20ca 交付的确认门工具化在本需求全程可用。
2. **新门禁链路被真实使用且验证**：brainstorming→planning（requirement_submit + confirm + move）、
   decomposing→implementing（confirm decomposition）两条人工门都由会话确认走通。
3. **历史数据兼容优先**：`MAIN_REQ_STATUSES` 去 done 但 `ALL_REQ_STATUSES` 保留——重启后 18 条 legacy done 需求零丢失。
4. **发现并清理死接口**：`POST /req/archive` 在归档自动化后必然失效（done 已是 legacy 终态），
   实施中一并移除而非留死代码。

## 做得不好的

1. **实施顺序跳步**：开工任务时忘了先 `decomposing→implementing` 推进，导致任务 done 了需求还在 decomposing，
   事后补走该门。→ 教训：**状态推进与任务执行是两条线，decompose 落库后应先推进再开工**。
2. **计划漏排文档任务**：6 个任务里没有"更新设计文档"，归档时才补 work-log/retro。→ 教训：
   refactor 类需求应在计划里显式排"文档合并"任务（否则归档校验会卡）。
3. **测试适配耗时**：done 移除波及 8 个测试文件、24 个断言，逐条语义修改占用大量轮次。→ 教训：
   改状态机前先 grep 断言基数的波及面，把"测试适配"作为独立任务排进计划（估算工作量）。

## 数据

- 单测：24 文件 / 395 用例（改前 402，删 done 相关用例后净减 7）
- 改动：源码 7 文件 + 测试 8 文件
- 历史兼容：31 条需求（18 done legacy）零丢失
