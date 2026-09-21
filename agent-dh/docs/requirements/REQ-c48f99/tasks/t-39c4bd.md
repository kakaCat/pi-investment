# t-39c4bd 端到端实测验收（E1-E4）+ 留证

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端实测验收（E1-E4）+ 留证

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：review
- 端侧：fullstack

## 得到什么结果
E1 三连不同 to 的 task_move 折叠行两两不同含中文动作；E2 reqboard_status 展开首行中文；E3 bash/read/edit 零回归；E4 畸形 block 显示兜底行不白屏——四项逐条记录进验收材料

## 实施方案（implementation）
restart-with-build.sh 重启后新窗口会话实操；对照审计报告改前状态描述

## 上游产出摘要（dependsSummary）
- 其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage）
- renderSmart 人话首行：13 个 pmboard 工具逐配 summarize
- 迁移与兼容验证：renderJson 保留 + 旧会话重渲染 + 未注册工具零回归

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T03:42:39.423Z，窗口 session-85447f15-ee57-44ef-8fd0-d8526111c0b3）

E1-E4 端到端实测汇总：E1 用户目检确认 task_move 折叠行中文动作且两两不同（对照改前 76 行全同）；E2 reqboard_status 展开首行=中文摘要（会话事件实证 + 用户确认）；E3 用户确认 bash/read/edit 零回归；E4 畸形 block 兜底=vitest 9 例断言（畸形→null→fallbackRow），GUI 层真实畸形 block 未遇到，降级标注待实战复核

### 完成项

- E1 ✅ 用户确认：本会话 task_move 折叠行=「任务推进 t-xxx → 中文动作」，两两不同
- E2 ✅ 会话事件实证：reqboard_status 渲染首行=「📊 看板：1 个进行中需求（REQ-c48f99 implementing）」+ 用户目检确认
- E3 ✅ 用户确认：bash/read/edit 终端卡/读取卡/diff 卡与改前一致
- E4 ⚠️ 逻辑层：vitest 34 例含 9 例畸形输入→null→fallbackRow 断言；GUI 层未遇到真实畸形 block，诚实降级标注

### 下一步

提交需求验收材料（reqboard_submit kind=verification）

---
