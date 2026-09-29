---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# 评审报告 · REQ-260928222643-4d34

> 评审人：窗口 `session-f17b3bd0`（agent-dh 投资脑工作窗口）· 时点 2026-09-28
> 对象：`packages/web/dsh-pmboard` 客户端改动（批准计划的 8 张卡 t-3e952f…t-29b629）

## 结论

改动落在**面板这一侧**，看板与后端逐字未动；五条不变量（导航唯一来源、先校验后切页、一次性、失败可见、动面板不动看板）逐条满足。**通过代码评审**；真实 :13080 的四步点击闭环属人工验收项，见 tests/test-report.md「未自动化项」。

## 逐条核对

| 不变量（design/interfaces.md I-6） | 证据 | 结论 |
|---|---|---|
| 导航唯一来源 = layout.selectPanel | src/client/conversation-progress.ts 成功分支调用 `getPageLayout()?.selectPanel(PANEL_ID)`；无 DOM/URL 路由操作 | 满足 |
| 先校验后切页 | board-entry.ts 的 activateBoardEntry 顺序 ①layout→②reqId→③isKnown→④requestFocus；失败返回 ok:false 且零副作用（TC-13 断言 0 次调用） | 满足 |
| 一次性（非粘滞） | board-focus.ts 取走即清、无 storage/URL；board-mount.ts 挂载时 take 一次；TC-8 二次挂载仍默认 | 满足 |
| 失败必须可见 | conversation-progress.ts 渲染 role="alert" 的 .dsh-pm-np-entry-err；不用 console/alert | 满足 |
| 动面板不动看板 | board-mount.ts 仅新增 takeBoardFocus 消费；其 fetchInjectionInfo 消费点（:721）保留；node-panel-process.ts 函数保留 | 满足 |

## 与设计的偏差

- **TC-7/TC-8 落点微调**：设计 test-cases.md 把这两个「看板挂载消费」用例列在 tests/board-focus.test.ts / tests/board-entry.test.ts；实现改为复用 tests/board-attach.test.ts 既有的「假容器 + fetch/EventSource 桩」挂载台（那里才真的能 drive createBoardAttachment），并在文件头补 `serves: FR-2`。语义不变、覆盖更实。
- **旧断言连带删除**：删除 tests/node-panel.test.ts 的「TC-4 执行流程三段」组之外，还删除了同属被下掉块的「TC-5 执行动作对照（规定 vs 实际）」组——其 ✅/⬜ 由 renderProcessFold 产出，属 FR-4 的下掉对象。已在 node-panel.test.ts 头注写明。

## 已知边界（不阻断本需求）

- 仓库另有 33 个用例文件失败与 3 处 tsc 报错，均来自**其它会话未提交的工作树改动**（如 REQ id 由 6 位 hex 改为 YYYYMMDDHHmm-xxxx、content-gate 文件超 400 行、application 层越界 import），与本需求无关；改动文件自身 0 type 错误、0 测试失败。
- auto-chain 执行器在本环境为 no-op（job `reqboard-1` 118ms 完成、无输出），子卡未产出 workflow run 证据 → 子卡无法由 agent 收尾；已在验收材料与窗口汇报中结构化报出（REQBOARD_SUBTASK_GATE）。
