# Agent Session Web 可视化设计

- **日期**: 2026-07-25
- **状态**: 已批准（用户逐节确认）
- **前置**: `feature/agent-gateway` 分支（PR #2）的 `/api/sessions` API 与 session 事件流
- **范围**: web-frontend 会话列表 + 详情钻取（回放/诊断）+ v2 AI 诊断端点
- **不在本次范围**: 跨会话趋势面板、实时 WebSocket 推送、自动 AI 复盘（会话结束自动触发）

## 1. 背景与需求

gateway 项目（spec: `2026-07-22-agent-gateway-session-design.md`）已让 agent 的每次工作产生结构化 session 事件流并同步到 v2。本设计解决"看见"的问题：**事后诊断复盘**——用户在 web 上查看 agent 做了什么、做得好不好。

用户确认的决策：

| 决策点 | 选择 | 备选 |
|---|---|---|
| 核心价值 | 事后诊断复盘 | 实时监控、两者兼顾 |
| 页面组织 | 列表 + 详情钻取 | 单页三栏、三个独立菜单页 |
| 智能表现 | 先做单会话诊断 | 加跨会话趋势面板 |
| 实现方案 | A：纯前端只读 + 前端加工 | B：v2 回放专用端点；C：旧裸 axios 模式 |
| 诊断深度 | 规则指标 + AI 诊断按钮 | 只做规则指标；自动 AI 复盘 |

## 2. 页面结构与路由

仿 GameIntelligence 分组路由（`MainLayout` children 内）：

```
/agent-session            → redirect /agent-session/list
/agent-session/list       → views/AgentSession/SessionList.vue
/agent-session/:key       → views/AgentSession/SessionDetail.vue
```

- `session_key` 含 `:`，前端 `encodeURIComponent` 传递；v2 已用 `<path:session_key>` 兼容
- 菜单：MainLayout 侧边栏"博弈智能"组下新增 `Agent 会话`（icon: ChatDotRound）
- 刷新策略：列表 `usePolling(30s)`；详情页手动刷新按钮，不自动轮询

## 3. API 层

`src/services/api/agentSession.ts`（遵循 `services/api/agent.ts` 的 apiClient 模式，禁止裸 axios）：

```typescript
export const agentSessionApi = {
  list(params?: { channel?: string; limit?: number }),
  get(key: string),
  getEvents(key: string, params?: { event_type?: string; limit?: number; offset?: number }),
  getDiagnosis(key: string),
  aiDiagnosis(key: string, refresh?: boolean),   // POST /api/sessions/{key}/ai-diagnosis
}
```

类型加入 `src/types/models.ts`：`AgentSession`、`SessionEvent`、`SessionDiagnosis`、`AiDiagnosis`。barrel（`services/api/index.ts`、`types/index.ts`）各加导出。

## 4. 页面组件

### 4.1 SessionList.vue

- `el-table` 列：session_key（缩写+tooltip）、channel（el-tag：wake 蓝/feishu 绿/cli 灰）、message_count、tool_call_count、error_count（>0 红）、last_active_at（相对时间）
- 通道筛选 `el-select`（全部/wake/feishu）；点击行 `router.push` 钻取
- 空态 `el-empty`；API 错误走 apiClient 统一 ElMessage

### 4.2 SessionDetail.vue · Tab 会话回放

- 核心纯函数 `groupEventsToTurns(events)`（`src/services/agentSession/replay.ts`）：按 `user_message` 切分回合，回合内挂 tool_call/error，`assistant_reply` 收尾；独立单测
- `el-timeline`：用户/Agent 大节点，工具调用小节点（成功绿/失败红+耗时）；长文本折叠 3 行可展开
- 顶部按 event_type 过滤（全部/仅对话/仅工具/仅错误）

### 4.3 SessionDetail.vue · Tab 智能诊断

- 4 个指标卡：工具成功率、工具调用数、平均耗时、错误数
- insight `el-alert`（v2 规则化解读）
- 慢工具 TOP5 横向条形图（`useChart`，从 events 的 tool_call 按 toolName 聚合 max durationMs）
- 错误聚类 el-table、关联决策 el-table（evaluation_status el-tag）
- **AI 诊断按钮**：loading（约 30s）→ 渲染三段分析（做得好/问题与根因/改进建议）+ 生成时间 + "重新生成"链接

## 5. v2 AI 诊断端点

`POST /api/sessions/{key}/ai-diagnosis`（挂在现有 `agent_sessions_bp`）：

1. 取会话事件流压缩成摘要（用户消息截断 200 字、tool_call 按工具聚合、error 全文、关联决策），prompt ≤ 4K token
2. 新增 `application/services/llm_service.py` 薄封装：requests 直连 DeepSeek（`https://api.deepseek.com/v1/chat/completions`，`DEEPSEEK_API_KEY` env，60s 超时）
3. 固定输出三段：做得好的地方 / 问题与根因 / 下次改进建议
4. 缓存：`quant.agent_sessions` 加两列 `ai_diagnosis JSONB`、`ai_diagnosis_at TIMESTAMPTZ`（小迁移）；缓存命中直接返回，`?refresh=true` 强制重新生成
- 未配置 key → 503 + 明确文案；超时 → 明确失败提示；AI 诊断按需触发，不影响规则指标

## 6. 错误处理

| 场景 | 处理 |
|---|---|
| v2 未启动/500 | apiClient 统一 ElMessage；列表页 el-empty"无法连接后端" |
| session_key 404 | 详情页 el-result 404 + 返回列表按钮 |
| 事件流为空 | 回放 tab el-empty |
| AI 诊断超时/失败 | el-alert 错误 + 可重试，不影响规则指标区 |
| DeepSeek key 未配置 | v2 503 + 明确文案 |

## 7. 测试策略

**web-frontend（vitest + happy-dom）**：
- `replay.test.ts` — groupEventsToTurns：回合切分/工具挂载/空流/乱序 seq
- `agentSession.test.ts` — API 层 mock
- `SessionList.test.ts`、`SessionDetail.test.ts` — mount + globalStubs，mock API 模块
- router 正则断言一条（仿 tests/unit/router.test.ts）

**v2（pytest）**：
- ai-diagnosis：mock LLM 调用成功/超时/未配置 key 三路径 + 缓存命中不重复调用

## 8. 改动清单

**web-frontend 新建**：`views/AgentSession/SessionList.vue`、`SessionDetail.vue`、`services/api/agentSession.ts`、`services/agentSession/replay.ts`、4-5 个测试文件
**web-frontend 修改**：`router/index.ts`、`components/layout/MainLayout.vue`、`services/api/index.ts`、`types/models.ts`、`types/index.ts`
**v2 新建**：`application/services/llm_service.py`、`migrations/add_session_ai_diagnosis.sql`、测试
**v2 修改**：`routes/agent_sessions.py`（ai-diagnosis 端点）、`session_service.py`（缓存读写）

**分支策略**：`feature/agent-session-web` 从 `feature/agent-gateway` 切出（依赖其 v2 API），gateway PR 合并后 rebase 或直接合 main。
