# REQ-2e9473 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t01 | t-e87559 | decompose 幂等守卫（W3） | implement | backend | - | 重复 decompose 被拒并返回已有任务清单；vitest 用例通过（故障注入：任务数不变） |
| t02 | t-23ca69 | rollup 阻塞 blockers 字段（W3） | implement | backend | - | 有未完成任务的 verify_submit/task_move 返回含 blockers 任务清单；单测覆盖 |
| t03 | t-51b936 | PlanTask.implementation 字段 + plan_submit 校验（W5，含事故 G DAG 校验） | implement | backend | - | 缺 implementation 或 acceptance 空话的计划提交被拒；任务表 DAG 提交时校验（前向引用/不存在依赖打回）；单测覆盖 |
| t05 | t-a43393 | capture-hook 工具痕迹跟踪（W2 前置） | implement | backend | - | tool/call 事件按窗口计数并可按任务开工时间分段查询；单测覆盖 |
| t07 | t-d48823 | reqboard_ask_confirm 原子工具（W1 核心） | implement | backend | - | 弹框确认→落章→推进一次完成；选"需修改"不推进；subagent 调用降级提示看板通道 |
| t10 | t-56b863 | 文字确认核验（W1 三通道③） | implement | backend | - | confirm_artifact evidence 伪造/找不到原文被拒；真实用户消息原文通过；弹框答复免引证 |
| t11 | t-ccf7db | REQ 目录产物自动发现（W4） | implement | fullstack | - | 新文件落 docs/requirements/<REQ>/ 后详情页文档记录区自动出现（带自动发现徽标）；重复扫描幂等 |
| t04 | t-32fd09 | decompose 薄卡拒落 + 开工任务卡送达（W5） | implement | backend | t-51b936 | 薄卡落库被拒；task_move→in_progress 返回含 acceptance/implementation/context 全文 |
| t08 | t-2c945b | 闸门问题卡 + 提交类工具 note 改指向（W1） | implement | backend | t-d48823 | move 被拒返回 gate_question 可被 ask_confirm 直接消费；三处 submit note 含"下一步调 reqboard_ask_confirm" |
| t09 | t-c1a5e8 | 里程碑超时未确认主动提醒（W1） | implement | backend | t-d48823 | 产物登记 >30min 未确认时绑定窗口收到注入提醒（注入留痕可查）；单测模拟覆盖 |
| t12 | t-e0110f | 任务文件上浮 + evidence 存在性 + 归档漏登警告（W4） | implement | backend | t-ccf7db | files_changed 进需求级产物清单；伪造 evidence 路径被拒；archive 漏登返回警告清单 |
| t06 | t-18d27a | done 凭证门三件套（W2） | implement | backend | t-32fd09, t-a43393 | 无 report/无工具痕迹/60s 内连续 done 均被拒；pages 任务 lib/client.js 陈旧被拒；故障注入 25ms 速通被拒 |
| t13 | t-70911c | 验收单数据模型 + verify_submit 生成逐项验收单（W6） | implement | backend | t-32fd09 | 验收单含每任务验收标准+需求级标准逐项（含 evidence）；版本化存储；挂起/续验状态持久化（pending/passed/failed 逐项） |
| t17 | t-ff597e | W7 阶段产物边界：plan_submit 任务表改可选 + decompose 承担任务卡创作 | implement | backend | t-51b936, t-32fd09 | 不含任务表的计划可提交（技术设计一套文档）；decompose 接受创作型 tasks 并经拆分确认门确认；故障注入：planning 阶段尝试落库任务被拒 |
| t19 | t-923e93 | W8 文档演进留痕与变更传播 | implement | backend | t-ccf7db | 文档 changelog 段强制（重登记必填变更原因）；上游变更→下游标"待同步"并在推进/验收时警告；同步后销标；影响清单进时间线 |
| t14 | t-6f3a71 | 验收单逐项确认 + 断点续验 + 返工回路（W6） | implement | frontend | t-70911c | ask_user_question 逐项弹框验收；发现问题可挂起（小修当场改留痕/大修打回生成返工任务）；修复后从断点继续且已过项不重弹；看板勾选并行通道 |
| t18 | t-78e660 | W7 阶段职责规范落地：STAGE_PROMPTS 七阶段重写 + workflow-stages.md 固化 | implement | backend | t-ff597e | STAGE_PROMPTS 与 requirement.md W7 逐字对齐；brainstorming 含九步检查表；workflow-stages.md 新增各阶段六要素规范 |
| t15 | t-8425bc | 故障注入与回归测试 | test | fullstack | t-e87559, t-23ca69, t-18d27a, t-2c945b, t-c1a5e8, t-56b863, t-e0110f, t-6f3a71, t-78e660, t-923e93 | A/B/C/E/F/G 六类事故复现用例全绿；vitest 全套通过；build:client + verify-client-build OK |
| t16 | t-bfc351 | 文档同步（workflow-stages/RFC 014/工具描述） | doc | doc | t-8425bc | 相关文档更新至新行为；阶段纪律文本与实现一致 |
