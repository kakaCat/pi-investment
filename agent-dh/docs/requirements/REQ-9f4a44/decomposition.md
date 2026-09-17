# REQ-9f4a44 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-939208 | 状态机改造：新增 accepting→archived、移除 done 相关转移与门 | implement | backend | - | protocol.ts 中 REQ_TRANSITIONS 含 accepting→archived 且无 done 相关转移；HUMAN_ONLY 移除 done>archived；ARTIFACT_CONFIRM_GATES 改为 accepting>archived:verification；ALL_REQ_STATUSES 保留 done 作 legacy；单测断言上述表内容与 assertReqTransition 行为 |
| t2 | t-0a1ad4 | 验收通过落点改 archived + archive_submit 放宽为 archived 可用 | implement | backend | t-939208 | handleVerifyDecision(pass=true) 写 status=archived（pass=false 仍回 implementing）；reqboard_archive_submit 在 archived 态可调且仍按 ARCHIVE_DOC_RULES 校验；单测覆盖两项 |
| t3 | t-23ebb9 | 移除流程图与分类档案中的 done 节点 | implement | frontend | t-939208 | conversation-progress.ts 的 FLOW 不含 done（流程止于归档）；CATEGORY_FLOW_PROFILES 各分类 stages/confirmGates 不含 done；单测遍历分类断言 |
| t4 | t-456236 | 验收通过后注入"请准备归档材料"提示 | implement | backend | t-0a1ad4 | 验收通过后绑定会话可收到"请准备归档材料"提示（复用既有注入点）；单测断言提示文本与触发条件 |
| t5 | t-431822 | 看板：archived 且无 archive 产物显示"归档材料待补" | ui | frontend | t-0a1ad4 | 看板对 archived 且缺 archive 产物的需求显示"归档材料待补"标记；build:client 通过 |
| t6 | t-cf5bec | 单测与 13080 实测（含历史 done 兼容） | test | fullstack | t-939208, t-0a1ad4, t-23ebb9, t-456236, t-431822 | vitest 全绿（含新转移/兼容/流程图断言）；13080 实测：造一个 accepting 需求 → 会话确认验收 → 状态直接 archived、无人工归档动作、流程图无 done、会话收到备料提示；含 done 的历史台账载入不报错 |
