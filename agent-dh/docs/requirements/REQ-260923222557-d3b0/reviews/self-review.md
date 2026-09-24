# REQ-260923222557-d3b0 交付自评（implementing → accepting）

> 评审人：投资脑窗口 w-959cebfe（session-959cebfe-094f-4f09-894d-20a5c35d4d62）
> 评审时点：2026-09-24 00:0x（数据时点同此，线上为 :13080 实例）
> 范围：本需求 7 张任务卡（t-787137 / t-b2e945 / t-06d59d / t-485233 / t-595192 / t-b9ff3f / t-4e8339）

## 1. 交付是否回答了需求（FR-1..FR-10 逐条）

| 条款 | 交付物 | 自评 |
|---|---|---|
| FR-1 implementing 注入 worktree 规范 | `src/domain/prompt/fragments/implementing/light.md` + `generated/fragments.ts` | 通过（fragments 基线快照 + 用例锁定） |
| FR-2 子任务完成在 worktree 中 commit | `src/domain/prompt/worktree-events.ts`（task_done 事件）+ CaptureHook 投递接线 | 通过（注入成功/失败两条路径都有用例） |
| FR-3 归档节点合并并删除 worktree | worktree-events 的 archived 事件 + 接线 | 通过 |
| FR-4 走既有节点路由提示词机制 | 复用 resolveStagePrompt / onStagePrompt 通道，未新造机制 | 通过 |
| FR-5 reqboard_ask_confirm 超时 1 小时 | `limits.ts` timeoutInteractiveMs=3_600_000，AskConfirm/Capture/TaskExecute/Advance 引用 | 机制级通过；**运行期端到端未闭环**（见 §3） |
| FR-6 ask_user_question 在 reqboard 上下文同超时 | 所有"需人弹框"工具统一取 LIMITS.timeoutInteractiveMs（含 AcceptSheet 走 timeoutSheetMs） | 机制级通过 |
| FR-7 超时可配置不硬编码 | 单一常量文件 domain/limits.ts，5 个消费方零字面量 | 通过 |
| FR-8 设计节点头部胶囊对齐新管线 | stage-panel.ts design 分支改按设计文档交付/确认取词 | 通过（线上 30 需求回归，旧管线 9 个文案不变） |
| FR-9 文档行可点 + 待交占位统一 | node-panel.ts renderDesignInfo 已交改 docItem、renderDecomposingInfo 补占位 | 通过（线上两种状态都实测到） |
| FR-10 未到达节点不说过时式 | node-panel.ts renderHead（state=pending → 「未开始」） | 通过（线上预览实测） |

## 2. 交付质量自评（证据强度）

- **证据取自线上真实数据**：30 个需求的 design 节点载荷由 :13080 的 reqboard API 实时返回，再过**源码渲染器**（tsx 直跑，非 mock）得到文案/HTML，避免"单测绿但线上不对"。
- **回归面覆盖全部存量需求**：不只挑样例——全量 30 个需求跑取词口径，旧管线 9 / 新管线 19 / 不一致 0。
- **构建产物可复核且确定**：连跑两次 `pnpm build:client` 的 `lib/client.js` md5 相同，且与重启前那份一致 → 排除"浏览器拿到旧包"。
- **零副作用**：本轮全部抽样均为只读；对账前后 `trade_monitor` queued 恒为 2、filled=0（无任何委托产生）。

## 3. 未闭环与风险（响亮报出，不静默）

1. **FR-5 的"跨过旧 600 秒仍有效"没有运行期实证**：只能证明到"声明值=3_600_000 + 框架按声明武装 deadline（无 600s 截断）+ 新值已随 2026-09-23T23:59:23 重启加载"。本会话是 PTC(run_code) 模式，run_code 自身预算 default 120000ms / cap 600000ms 覆盖嵌套工具等待，10 分钟恰好等于要跨过的旧值，故无法在一次调用内完成实测。
2. **由此暴露的更大问题**：PTC 模式窗口调用 `reqboard_ask_confirm` 时，实际等待上限仍被压到 ≤10 分钟——也就是说本需求"给用户 1 小时"的意图，对 PTC 窗口**不生效**，只在原生工具调用窗口生效。若要覆盖 PTC 窗口，需调整框架级 PTC 预算，会波及**所有**嵌套工具等待，超出本需求「不影响其他非 reqboard 弹框的超时」的边界 → 建议人工裁定或另立需求，不在本需求内擅自扩范围。
3. **worktree 落地依赖 agent 自觉**：FR-1..FR-3 只注入规范文本，不强制 git 命令（需求"不做什么"第 1、2 条明确如此）。规范是否被遵守，需在后续需求的实际开发中观察，本轮无法证伪。

## 4. 结论

需求边界内 10 条功能点中 9 条已闭环且有线上证据，FR-5 达"机制级通过、运行期待人工确认"。**建议**：按 §3.1 由人工在原生工具调用会话确认，或接受常量级证据并在 §3.2 另立需求。是否通过由人工裁决。
