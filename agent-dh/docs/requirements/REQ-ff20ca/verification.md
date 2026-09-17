# REQ-ff20ca 验收材料

> 状态：待人工审核 · 类型：feature · 绑定窗口：w-24ded829
> 上游：[requirement.md](./requirement.md)（1–5 节定稿）· [plan.md](./plan.md)（8 任务）

## 1. 交付结论

两批交付全部完成：

**① 确认门工具化（最高优先，修 REQ-31e11f 的实现缺陷）**
- 补上 brainstorming 阶段产物登记入口（原缺失 → 看板确认按钮 400 死锁）
- 人工确认门支持**双通道落章**：看板点击（`via=board`）/ 会话经 `ask_user_question`（`via=session` + `evidence` 审计）
- 门禁判定从"谁调用"改为"产物是否已确认"；agent 侧补上产物闸门（原可绕过）

**② 文档打开迁移官方 sidebarRight（人机回路载体）**
- 会话框 + 看板两处文档点击 → 官方右侧栏 `documentpreview` 渲染
- 自研弹窗**整套删除**（文件/函数/CSS），零降级残留
- 阶段纪律工具化：五段 prompt 均要求用 `ask_user_question` 发起回路

## 2. 证据清单

| # | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 1 | 未确认时门禁拒绝 | `reqboard_move(decomposing→implementing)` 返回：需要人确认产物（kind=decomposition）+ 两条确认通道 | ✅ |
| 2 | 会话确认落章 | `reqboard_confirm_artifact` 返回 success；台账 `confirmedVia=session`、`confirmedEvidence="确认，放行进入实施 (Recommended)"`、`confirmedBy={kind:human,sessionId:...}` | ✅ |
| 3 | 门开启后放行 | 确认后同转移返回 `success: true, from: decomposing, to: implementing` | ✅ |
| 4 | 会话框文档 → 右栏 | 用户实测：右栏打开且 markdown 正常 | ✅ |
| 5 | 看板文档 → 右栏 | 用户实测：右栏打开且正常（不再出现 `md·19:15` 弹窗） | ✅ |
| 6 | 弹窗整套清除 | `doc-modal.ts` 已删除；`grep -rn openDocModal src/ lib/client.js` 无结果；弹窗 CSS 计数 0；`.dsh-pm-md` 保留 21 处 | ✅ |
| 7 | 登记工具（t1） | `tests/requirement-submit.test.ts` 4 用例：首次登记/幂等/文件缺失拒绝且不写台账/非 brainstorming 拒绝 | ✅ |
| 8 | 阶段纪律工具化 | `tests/stage-prompts.test.ts` 追加 5 条断言（各段含 `ask_user_question`、brainstorming 含 submit+confirm 指引、planning 含 target=plan 等） | ✅ |
| 9 | 全量回归 | `npx vitest run` → **Test Files 24 passed / Tests 402 passed** | ✅ |
| 10 | 构建门禁 | `pnpm build:client` → `[verify-client] OK bundle=244329 bytes, 关键符号齐全, styles.ts 括号配对` | ✅ |

## 3. 交付物

**代码**
- `packages/pages/dsh-pmboard/src/host/agent-tools.ts` — 新增 2 工具 + move 门禁改造 + agent 侧产物闸门
- `packages/pages/dsh-pmboard/src/host/routes.ts` — 看板确认写 `via=board`
- `packages/pages/dsh-pmboard/src/shared/protocol.ts` — `confirmedVia/evidence`、`approvedVia/evidence`
- `packages/pages/dsh-pmboard/src/index.ts` — 工具注册
- `packages/pages/dsh-pmboard/src/client/file-address.ts`（新）— 地址 grammar（对齐官方）
- `packages/pages/dsh-pmboard/src/client/open-doc.ts`（新）— 统一打开入口
- `packages/pages/dsh-pmboard/src/client/conversation-progress.ts` / `board-mount.ts` — 接线
- `packages/pages/dsh-pmboard/src/client/styles.ts` — 弹窗 CSS 删除（保留 `.dsh-pm-md`）
- `packages/pages/dsh-pmboard/src/client/doc-modal.ts` — **删除**
- `packages/pages/dsh-pmboard/src/host/stage-prompts.ts` — 五段工具化条款

**测试**
- `tests/requirement-submit.test.ts`（新，4 用例）
- `tests/stage-prompts.test.ts`（+5 断言）
- `tests/apply-wiring.test.ts`（工具名单更新）

**文档**
- `docs/architecture/page-plugin-contract.md` — 新增「打开文档：走官方右侧栏」一节（inject 必需性/地址 grammar/sessionId 来源/为何不造弹窗）
- `docs/rfcs/014-requirement-board.md` — 新增 §10a「人工确认门：双通道落章」

## 4. 已知限制与遗留

1. **t7（阶段提示词）需重启生效**：`stage-prompts.ts` 是 host 侧常量，单测已锁内容，线上生效需重启进程。
2. **t1 的首次登记**未在真实 brainstorming 需求上演示（本需求已完成该阶段），由工具层单测覆盖；下一个新建需求会自然走通。
3. **`marked` 依赖已无引用**（`view.ts` 用自研零依赖渲染）→ bundle 244KB→197KB；声明保留未动（避免 `pnpm install` 链接漂移），可在下次依赖整理时移除。
4. **`view.ts` 的 `renderMarkdown` 是自研轻量渲染**（非官方）：本次未纳入改造（需求卡描述属行内预览，非文档预览），可另立优化项。
5. **测试遗留**：包目录 `packages/pages/dsh-pmboard/docs/` 是既有工具测试的产物（untracked），非本次新增。
