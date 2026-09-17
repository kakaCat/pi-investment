# REQ-ff20ca 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-bbea78 | 新增 reqboard_requirement_submit 登记需求文档产物 | implement | backend | - | 调用后台账 artifacts 出现 {kind:requirement,stage:brainstorming,path}；文件不存在则报错且不写台账；同 path 幂等；单测通过。 |
| t2 | t-9fc198 | 新增 reqboard_confirm_artifact 并扩展确认模型（via/evidence） | implement | backend | - | 会话确认落库 confirmedBy.via=session 且 evidence/sessionId 与传入一致；看板确认写 via=board；老记录读取不报错；单测覆盖三类来源。 |
| t3 | t-447c4a | 改造 reqboard_move 门禁：产物已确认即放行 | implement | backend | t-9fc198 | 未确认时 move 被拒且提示含 ask_user_question；已确认（board 或 session 来源）时放行；推进留痕 by=agent + 依据说明；单测覆盖两态。 |
| t4 | t-90ec62 | 确认门全链路单测与 13080 实测 | test | fullstack | t-bbea78, t-9fc198, t-447c4a | 13080 上全链路走通（提交→确认→推进）；看板「确认产物」按钮返回 200 并写入 confirmedAt；vitest 全绿。 |
| t5 | t-de13e3 | sidebarRight 最小验证（会话框单入口） | implement | frontend | - | 13080 上会话框点文档在官方右侧栏打开且 Markdown 正确（列表续行非 pre）；console 记录 sidebarRight 探测与地址；file-address 单测通过。 |
| t6 | t-802055 | 全量接线（看板）+ 弹窗整套删除 | implement | frontend | t-de13e3 | 看板点文档同样打开右栏；doc-modal.ts 不存在；全仓 grep 无 openDocModal；无降级分支；view.ts 需求卡 markdown 仍正常。 |
| t7 | t-4c05e9 | 阶段纪律工具化（stage-prompts 要求 ask_user_question） | implement | backend | - | 各阶段 prompt 含"必须用 ask_user_question"条款；单测锁定措辞防回退；既有注入机制与单测不受影响。 |
| t8 | t-d40689 | 文档更新与需求归档材料 | doc | doc | t-90ec62, t-802055, t-4c05e9 | 架构文档记录 sidebarRight 优先链路与确认门双通道；需求目录含可复核的验收材料。 |
