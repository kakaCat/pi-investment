# REQ-a33899 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-87dc49 | 立 Token 契约与纯函数 | implement | fullstack | - | tests/token-usage.test.ts：四桶加减正确、负分量截断、totalTokens=四桶之和、估算单调非负、fmtTokens/fmtCny 边界（<1000/k/M/undefined→—）；pnpm test 与 typecheck 全绿。 |
| t2 | t-dea770 | 会话 Token 读取端口与降级 | implement | backend | t-87dc49 | 单测：假 projections→source=projection 四桶一致；服务 undefined→source=unavailable、全 0、不抛。 |
| t3 | t-4fe9dc | 台账 v6 + 写路径快照与迁移 | implement | backend | t-87dc49, t-dea770 | 单测：跨 2 节点后 StatusEvent 含 tokenSnapshot；任务写 start/end/delta；v5 样例可 load 不改版本；迁移后 schemaVersion=6 且 migrations 有 {from:5,to:6}；pnpm test 全绿。 |
| t4 | t-506414 | 读路径装配与 HTTP（需求/节点/任务） | implement | backend | t-4fe9dc | 端到端 curl token 接口返回 byStage+executions；不存在 404；有 unavailable 快照时 degraded=true 且无编造数字；progress/state 扩展字段可见。 |
| t5 | t-77067a | 提示词成本读路径（固定系统提示词 + 注入提示词） | implement | backend | t-506414 | 单测：systemPrompt 可用→sections 逐段 chars 等于文本长度且每段 text 随响应返回、perTurn=sections+contexts+tools；不可用→source=unavailable 不猜；injections 聚合 chars 等于留痕 charCount 之和、按阶段分组正确、明细可用。 |
| t6 | t-baeed5 | 详情页「🪙 Token」tab（汇总卡 + 四个折叠块） | ui | frontend | t-506414, t-77067a | pnpm build:client 通过且 verify-client-build 无报错；grep -c 'data-tab="token"' lib/client.js >= 1；一级折叠四块齐全；固定系统提示词每段可展开看到具体提示词内容（pre-wrap，超长内滚动）；无快照显示「无快照」、服务不可用显示「不可用」，均不显示 0。 |
| t7 | t-dbdeec | 会话顶部每节点 Token（同行）+ 看板卡面 | ui | frontend | t-506414 | build 后 client 产物含 .dsh-pm-flow-meta/.dsh-pm-flow-token 且既有 .dsh-pm-flow-node/.dsh-pm-flow-dot/.dsh-pm-flow-label 样式未被改写（grep 对照）；卡面含徽章；无 tokenTotals 不渲染徽章。 |
| t8 | t-1616b2 | 端到端自证与文档更新 | test | doc | t-4fe9dc, t-506414, t-77067a, t-baeed5, t-dbdeec | verification.md 含 curl 输出摘要 + tokenUsage.totals 核对 + 系统提示词段字符对照 + 三条命令通过输出；文档含 token 契约与口径说明。 |
