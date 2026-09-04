# @pi-investment/dashboard-bulletin（公告板页面，RFC 013）

DSH GUI 页面域第三个看板插件，镜像 dashboard-holdings / dashboard-execution 双半插件模式。

- 数据源：Agent OS memory（tag office:board），与 board_post/board_read/board_update 工具同源（RFC 009）
- 实施节奏（用户指定）：phase1 = 先在 pages 创建包 + 侧栏顶部菜单按钮，验证 OK 后再做看板正文（phase2）
- 入口位置：侧栏顶部 logoRow 之下、新会话/会话列表上方（与「智能执行」「账户持仓」同锚点并列，纯 DOM 行）
- phase1 状态：宿主 apply 仅占位；client 只挂「公告板」顶部按钮（点击为占位反馈，看板正文 phase2 接入）

## phase2 预留契约（勿提前实现）

- 宿主路径：/dashboard/api/bulletin/posts（唯一所有者；与 execution /dashboard/api/board、holdings /dashboard/api/holdings 互斥）
- 客户端命名空间 dsh-bbd-*；视图根 data-dsh-bbd-view；html[data-dsh-bbd-active] 显隐；ACTIVATE_EVENT 互斥
- 详情见 docs/rfcs/013-bulletin-board-page.md
