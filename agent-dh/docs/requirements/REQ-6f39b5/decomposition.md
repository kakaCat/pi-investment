# REQ-6f39b5 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t-001 | t-b8104c | 创建 workflow-constants.ts | implement | frontend | - | 文件存在，导出 WORKFLOW_STAGES / PROGRESS_DOT_STAGES / LANE_STAGES，包含注释引用唯一事实源 |
| t-002 | t-75b97e | 实现 buildProgressDots() | implement | frontend | t-b8104c | 函数存在，返回 HTML 包含 8 个进度点，当前态高亮正确 |
| t-003 | t-a1ddf2 | 实现 buildTabs() | implement | frontend | - | 函数存在，返回 4 个 Tab 按钮 HTML，概览默认 active |
| t-004 | t-7cd8f2 | 实现 buildTabContents() | implement | frontend | t-a1ddf2 | 函数存在，返回 4 个 Tab 内容区 HTML，内容完整无遗漏 |
| t-005 | t-a12946 | 重写 buildReqDetail() | implement | frontend | t-75b97e, t-a1ddf2, t-7cd8f2 | 删除了 8 个节点导航按钮和 11 个折叠区，集成了新组件，签名保持不变 |
| t-006 | t-5e83d0 | 实现 Tab 切换交互 | implement | frontend | t-a12946 | 点击 Tab 正确切换内容区，无闪烁，active 状态正确 |
| t-007 | t-b570fd | 添加样式（进度点 + Tab） | implement | frontend | t-5e83d0 | 样式文件更新，进度点和 Tab 视觉效果与原型一致 |
| t-008 | t-be0387 | 适配泳道图与列表视图 | implement | frontend | t-b8104c | 泳道图和列表视图流程节点名称正确显示（立项、需求分析、技术设计...） |
| t-009 | t-7aa2ec | 功能测试 | test | fullstack | t-be0387 | 测试清单全部通过，无回归问题 |
| t-010 | t-174c57 | 文档更新 | doc | doc | t-7aa2ec | README 包含 Tab 使用说明，代码注释完整 |
