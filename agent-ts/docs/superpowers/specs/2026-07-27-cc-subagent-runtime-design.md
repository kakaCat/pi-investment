# CC Sub-Agent Runtime 设计 — agent-ts 控制 Claude Code

> 日期: 2026-07-27 | 状态: 设计已确认（用户已批准方向） | 路线: Claude Agent SDK 嵌入

## 背景与问题

现状 `claude_code` 工具（`src/infrastructure/tools/agent/claude-code-tool.ts`）以 `claude -p --output-format json --bare` 一次性 spawn 驱动 Claude Code，存在系统性缺陷：

1. **无权限授权**：print 非交互模式下 Edit/Write/Bash 均被拒，CC 只能读不能改，"控制"名不副实
2. **结果判定不可靠**：以 exit code 0 判成功，未解析 JSON 信封的 `is_error` 字段
3. **原始 JSON 倒灌上下文**：不提取 `result` 文本、不走 `handleToolResponse` 持久化
4. **无会话连续性**：每次冷启动，不能 resume、不能中途介入
5. **cwd 锁死 agent-ts**：无法正确服务 quantsys-v2 后端开发场景
6. **零审计**：调用、产出、成本无持久化记录

## 需求（用户已确认）

| 维度 | 决策 |
|------|------|
| 主要场景 | **quantsys-v2 后端开发**（新 API、修 bug、数据管道，pytest 验证） |
| 信任级别 | **全自动 + agent 验收**：CC 可自主改代码+跑测试；agent 验收（测试+diff 审查），有否决权，失败自动回滚 |
| 交互模型 | **双向中途唤醒**：CC 中途可唤醒 agent 提问，agent 答复后 CC 继续；agent 也可随时介入运行中的 CC |
| 技术路线 | **Claude Agent SDK 嵌入**（`@anthropic-ai/claude-agent-sdk`，进程内驱动） |

## 总体架构

在 agent-ts 新增 `src/services/cc-runtime/` 模块，将 Claude Code 作为**进程内子代理**驱动：

```
agent LLM
  │ cc_delegate(任务契约)
  ▼
CCRuntime (src/services/cc-runtime/)
  ├── contract.ts        任务契约 schema + 校验
  ├── worktree.ts        git worktree 隔离工作区管理
  ├── sdk-driver.ts      query() 封装：流式事件、interrupt、resume
  ├── orchestrator-mcp.ts in-process MCP server（CC 侧唤醒/上报工具）← 双向唤醒核心
  ├── supervisor.ts      超时/心跳/预算监督 + pendingQuestions 路由
  ├── acceptance.ts      验收：diff范围检查 → 验收命令 → LLM diff 审查
  └── audit.ts           审计落盘
```

数据流：

```
cc_delegate → 契约校验 → 建 worktree → SDK 启动 CC
  → CC 干活（report_progress / ask_orchestrator 经 MCP 流入 agent）
  → CC 提交结构化完成报告
  → 验收三道闸
      通过 → diff 落回主工作区（不 commit）→ agent 可用 backend_control 重启后端生效
      失败 → resume 原 session 注入失败详情重试（≤2 次）
      仍失败 → 销毁 worktree、记 failed、审计原因、飞书通知人
```

## 任务一致性（契约 + 三道闸）

### 任务契约（cc_delegate 参数）

```ts
interface CCTaskContract {
  goal: string;                // 要做什么
  context?: string;            // 背景（为什么、相关信息）
  scope_paths: string[];       // 允许修改的目录，如 ["quantsys-v2/services", "quantsys-v2/api"]
  acceptance: {
    commands: string[];        // 验收命令，如 ["pytest tests/api -x"]
    criteria?: string;         // 自然语言验收标准（供 agent 审 diff）
  };
  timeout_minutes?: number;    // 默认 30
  max_turns?: number;          // 默认 50
  max_budget_usd?: number;     // 成本硬顶
  auto_merge?: boolean;        // 验收通过后 diff 落回主工作区（默认 true，不 commit）
}
```

### 一致性五道保障

1. **worktree 隔离** — CC 在 `.claude/worktrees/cc-tasks/<task_id>/` 工作（pi-investment monorepo 单 worktree 即覆盖 quantsys-v2）。失败 = 删 worktree，主工作区零污染。
2. **范围强制** — `canUseTool` 回调：Edit/Write 目标路径必须 ⊆ scope_paths，越界拒绝；Bash 命令黑名单（`git push`、`rm -rf`、DDL 等）。
3. **扩权申请** — CC 需改契约外文件时调 MCP `request_scope_extension(paths, reason)`，agent 批准后放行。
4. **验收三道闸**：
   - `git diff --name-only` 结果 ⊆ scope_paths
   - worktree 内跑 `acceptance.commands` 全绿（pytest 使用主工作区 venv 绝对路径，worktree 不含 `.venv-py313`）
   - agent 作为 LLM 审 diff vs goal/criteria
5. **失败回路** — 任一闸不过 → resume 原 CC session、注入失败详情（测试输出/越界清单）重试 ≤2 次；仍失败 → 销毁 worktree、记 failed、审计原因、通知人。

### 完成报告 schema

CC 终态输出必须是结构化 JSON：`{ summary, files_changed, tests_run, self_check }`。驱动层校验，缺字段视为未完成。

## 超时设计（四层）

| 层 | 机制 | 默认 |
|---|---|---|
| 心跳 | `report_progress` MCP 调用即心跳；supervisor 每 60s 检查最后事件时间 | 静默 5min → 判卡死 |
| 软超时 | 达 timeout 80% → SDK 注入消息"收尾并提交进度报告" | 24/30 min |
| 硬超时 | `interrupt()` + abort；transcript + worktree 现场保留 48h | 30 min |
| 问答超时 | `ask_orchestrator` 挂起上限；超时自动返回"按你最佳判断继续，保守优先" | 10 min |

另有 `max_turns` + `max_budget_usd` 双保险。卡死时先 interrupt 要 partial report，拿不到按失败处理但留现场。

## 相互唤醒（双向）

### CC → agent（三个 in-process MCP 工具）

- `report_progress(message, percent?)` — 单向进度。写入 agent 会话事件流 + 作为 supervisor 心跳。不强制打断 agent。
- `ask_orchestrator(question, options?)` — **中途唤醒**。handler 将问题注入 agent session（复用 WatchEngine 唤醒路径），MCP 调用挂起；agent 答复路由回来后 resolve，CC 继续。agent 忙则排队，10min 超时兜底。
- `request_scope_extension(paths, reason)` — 扩权申请，同上挂起等待批准。

### agent → CC（SDK 原生能力）

- `cc_message(task_id, text)` — 向运行中 CC session 追加指令/答复提问
- `cc_cancel(task_id)` — interrupt + abort
- 答复路由：supervisor 维护 `pendingQuestions: task_id → resolve()`，agent 回复经 WakeRouter 匹配后 resolve 对应 MCP promise

agent 侧被唤醒的落点复用现有 gateway/session 事件流，不新造 HTTP 通道。

## agent 工具面

| 工具 | 说明 |
|---|---|
| `cc_delegate` | 提交任务，**异步**立即返回 task_id；description 写明契约格式与"完成后会唤醒你" |
| `cc_status` | 状态/进度/transcript 摘要 |
| `cc_message` | 向运行中任务追加消息 |
| `cc_cancel` | 中止任务 |

- 放 admin 工具组（load_tools 动态加载，不进 Core）
- 上下文纪律：`cc_delegate` 只回 task_id；完成报告走 `handleToolResponse` 持久化，LLM 只见摘要+文件路径
- 旧 `claude_code` 工具：cc-runtime 上线后标记废弃，保留一个版本周期后删除

## 审计

每任务一目录 `.pi-invest/cc-tasks/<task_id>/`：

- `contract.json` — 任务契约
- `events.jsonl` — SDK 流事件全量
- `diff.patch` — 最终 diff
- `acceptance.json` — 三道闸各自结果
- `verdict.json` — 终判（accepted / retried / failed + 原因）

验收结论摘要写 quantsys-v2 决策审计（沿用"所有决策落库供学习"原则）。

## 衔接点

- **新依赖**：`@anthropic-ai/claude-agent-sdk`（用本机 Claude 登录或 ANTHROPIC_API_KEY；先验证与 node22/tsx 栈兼容）
- **venv**：验收命令使用主工作区 venv 绝对路径（`.venv-py313`）
- **生效**：quantsys-v2 改动落回主工作区后，agent 用现有 `backend_control` 重启后端
- **worktree 规范**：遵循仓库 worktree 隔离规则；任务 worktree 统一放 `.claude/worktrees/cc-tasks/`

## 明确不做（YAGNI）

- 多 CC 并发任务（先串行；supervisor 数据结构按可扩展设计）
- CC 反向控制 agent（CC 只能 ask/notify，不能驱动 agent 执行工具）
- 自动 git commit / push（diff 落到主工作区为止，提交由人或明确指令触发）
- web-frontend / agent-ts 自身作为首批场景（聚焦 quantsys-v2；架构不限制后续扩展）

## 测试策略

- 单元：契约校验、scope 路径检查、Bash 黑名单、完成报告 schema 校验、超时层级计算
- SDK driver：mock query 事件流，测软/硬超时、interrupt、resume 重试回路
- MCP：mock 双向唤醒（ask → 挂起 → resolve / 超时兜底）
- e2e：让 CC 在 worktree 改一个 dummy 文件 + 跑一条 trivial pytest，跑通"委托→进度→报告→验收→落盘"全链路
- 测试命令遵循仓库约定：`npm test`（--experimental-vm-modules），不用裸 npx jest
