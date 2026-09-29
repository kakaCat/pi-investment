---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
sides: [frontend]
---

# 架构设计（REQ-260928222643-4d34）

> 读者：继续改 dsh-pmboard 的开发者（人读，业务后果在前、技术细节在后）。
> 本需求是**客户端（浏览器侧）单侧改动**：节点面板加「项目看板 ↗」入口 → 一次性交接给看板
> 并定位到该需求详情；同时下掉面板里的「🔄 执行流程」折叠块与它的两次无用拉取。
> 不改台账、不改后端路由、不改看板既有行为（见 requirement.md「不做什么」）。

## 目标与总体方案 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

**问题**：从「看完某个节点」到「看这条需求的全景」要三步（关面板 → 侧栏点项目看板 → 找需求）；
且面板末尾挂着一个没人消费的「🔄 执行流程」块，为它每次展开都多打两次接口。

**当前状况（读码证据，时点 2026-09-28）**：

| 事实 | 证据位置 |
|---|---|
| 面板状态行由 `renderHead` 渲染（状态胶囊 + 一句话 + 相对时间） | `src/client/node-panel.ts:292-305` |
| 分类跳过（`enabled=false`）走**early return**，只渲染 `renderHead` + 空态 | `src/client/node-panel.ts:324-329` |
| 面板末尾固定追加 `renderProcessFold` | `src/client/node-panel.ts:344` |
| 展开面板时拉注入/隔离留痕，只为喂该折叠块 | `src/client/conversation-progress.ts:182-198` |
| 看板视图状态机 `mode` 是**挂载闭包内**的 `let` | `src/client/board-mount.ts:180`、`:231-269` |
| 宿主 keyed 插槽「切走即卸载、切回即挂载」 | `src/client/page/host.ts:54-58` |
| 页面导航唯一来源 `ctx.layout.selectPanel(id\|null)` | `src/client/page/page-runtime.ts:15-18` |
| 模块级持有器已有先例（`layout` 交 `page-runtime`） | `src/client/page/page-runtime.ts:20-42` |

**设计方案（三段）**：

1. **入口**（FR-1）：在 `renderHead` 内、相对时间之后追加一个 `<button data-action="np-board-entry">`。
   因为 `renderHead` 被**跳过分支与正常分支共用**，7 个节点（含「本分类跳过该节点」）自动全覆盖——
   不需要在 7 处分别接线。
2. **交接**（FR-2）：新增模块级**一次性持有器** `src/client/board-focus.ts`。点入口时先校验可达性，
   通过后 `requestBoardFocus(reqId)` → 关闭面板 → `layout.selectPanel(PANEL_ID)`；看板宿主挂载时
   `takeBoardFocus()` **取走即清**，据此把 `mode` 初始化为 `{kind:'req', reqId}`。
3. **下掉**（FR-4/FR-5）：`node-panel.ts` 删掉 `renderProcessFold` 调用与 `injection`/`isolation`
   两个入参；`conversation-progress.ts` 删掉状态、拉取 effect 与两个 props。`node-panel-process.ts`
   **保留**（requirement 明示「函数可留」），只断调用。

**不这么做的后果**：

- 入口不在 `renderHead` 内 → 跳过态漏入口（FR-1 的判定就是拿跳过态验的）；
- 交接用 URL hash → 客户端全 `src/client` 无 hash/query 解析，且导航的唯一来源是 `selectPanel`，
  等于新开第二条导航真相（requirement「界面与契约」明确禁止）；
- 交接状态留在看板 `state` 里 → 粘滞，刷新或再次进入看板仍停在旧定位，违反「一次性」数据契约。

## 模块改动地图 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

**图示**：

```
[conversation-progress.tsx]  会话头槽位（面板宿主 + 点击委派）
   │ 点「项目看板 ↗」
   ├─(1) 取 layout = getPageLayout()            ← page-runtime.ts（既有）
   ├─(2) await api.fetchState() 核对该 REQ 在册  ← api.ts（既有，读同一台账）
   ├─(3) requestBoardFocus(reqId)                ← board-focus.ts（新增·一次性持有器）
   ├─(4) 关面板（setDetailOpen(false) / setSelectedStage(null)）
   └─(5) layout.selectPanel(PANEL_ID)            ← 导航唯一来源
                                   │
                                   ▼
[page/host.ts]  keyed 插槽切到 PANEL_ID → 挂载 BoardPanelHost → attachBoard(container)
                                   │
                                   ▼
[board-mount.ts] takeBoardFocus() → mode = {kind:'req', reqId}   （取走即清）
                 fetchAll() → render() → buildReqDetail(...)      （既有渲染路径）
                 若该 req 不在 → 既有回退：mode = {kind:'board'}
```

**改动清单**：

| 文件 | 类型 | 改动内容 | 服务条款 | 影响范围 |
|---|---|---|---|---|
| `src/client/board-focus.ts` | 新增 | 模块级一次性持有器（零 import，同 `page-runtime` 纪律） | FR-2 | 仅本包客户端 |
| `src/client/board-entry.ts` | 新增 | 纯函数：可达性判定 + 失败原因→人话提示映射（依赖注入，可单测） | FR-3 | 仅本包客户端 |
| `src/client/node-panel.ts` | 改 | `renderHead` 加入口按钮；删 `renderProcessFold` 调用、`ProcessFoldContext`、`injection`/`isolation` 入参；删头注里的执行流程描述 | FR-1, FR-4, FR-5 | 面板 DOM 结构 |
| `src/client/conversation-progress.ts` | 改 | 加 `np-board-entry` 点击委派 + 面板内失败提示；删两条留痕的 state/effect/props；`closePanel` 上移到 early return 之前 | FR-1, FR-2, FR-3, FR-5 | 会话头组件 |
| `src/client/styles/node-panel.ts` | 改 | 新增 `.dsh-pm-np-board-entry`（不被裁切、可点）与 `.dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err` 两条作用域内规则 | FR-1, FR-3 | 仅本面板 |
| `src/client/board-mount.ts` | 改 | 挂载时 `takeBoardFocus()` 决定初始 `mode`（一行式改动，其余分支不动） | FR-2 | 看板初始视图 |
| `src/client/node-panel-process.ts` | 不动 | 保留（函数可留）；调用方删除后本模块不再被 client 引用 | FR-4 | 无运行时影响 |
| `src/client/api.ts` | 不动 | `fetchInjectionInfo` / `fetchIsolationLog` 保留（看板与其它消费方仍用） | FR-5 | 无 |

## 为什么用模块级一次性持有器（关键决策） `serves: FR-2`

看板的 `mode` 是**挂载闭包内**的局部变量（`board-mount.ts:180`），宿主又是 keyed 插槽
（`page/host.ts`：切走即卸载）。因此「谁在什么时候把 REQ id 交给看板」只有两个窗口：
**面板点击时**（看板还没挂载）与**看板挂载时**（此刻只能从模块级读）。三个候选：

| 候选 | 为什么不用 |
|---|---|
| URL hash / query | 客户端全 `src/client` 无 `location.hash`/`URLSearchParams` 解析；且导航唯一来源是 `layout.selectPanel`——引入第二条导航真相 |
| 自定义事件（`window.dispatchEvent`） | 事件发出时看板**尚未挂载**（`selectPanel` 之后宿主才 mount），必然丢事件 |
| 模块级持有器（选中） | 与既有 `page-runtime.ts` 同款（`layout` 就是靠模块级交给 `session-jump` 的）；不新增全局量（不挂 `window`）；天然支持「挂载时读一次」 |

**一次性语义**：`takeBoardFocus()` 读后立即清空，不落 storage、不落台账。故刷新页面或再次进入看板
必然回到默认视图——这正是 requirement 数据契约要求的「不得形成粘滞状态」。

## 错误处理与响亮失败 `serves: FR-3`

导航前**先校验、后切页**：两道前置检查任一不过就**不切页**，并把原因就地显示在面板里（不用 console）。

| 错误码 | 触发条件 | 人看到的文案 | 页面对不对 |
|---|---|---|---|
| `nav-unavailable` | `getPageLayout()` 返回 `undefined`（layout 服务未注入） | 「页面导航服务不可用（layout 未注入），请刷新页面后重试」 | 不切页 |
| `req-missing` | 入口未带 REQ id，或该 id 不在台账 `requirements` 里 | 「需求 {id} 不在台账（可能已归档或被删除），未跳转」 | 不切页 |
| `ledger-unreachable` | `fetchState()` 抛错/超时（8s，走 `api.ts` 既有超时） | 「无法确认需求是否可达（台账接口失败：{原因}），未跳转」 | 不切页 |

失败提示载体 = **面板内一行 `role="alert"` 文本**（`.dsh-pm-np-entry-err`），复用既有
「会话跳转结果要能说清为什么没跳」的约定（`board-mount.ts:jumpResultMessage` 的 client 侧同款），
但本需求要求**可见**，所以不走 console。

## 兼容与回滚 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

- **数据迁移：无**。不新增/变更台账字段，不动 `REQBOARD_SCHEMA_VERSION`（与 requirement「数据契约」一致）。
- **旧行为兼容**：定位通路不可用时 FR-3 生效（留在原页 + 提示），不产生悬挂状态；面板其余块
  （REQ 行 / 基础信息 / DAG·泳道）与看板全部既有行为逐字不变。
- **上线下线**：本包是页面插件，产物需重建并重启才生效——
  `cd packages/web/dsh-pmboard && pnpm build:client`，随后按 `agent-dh/scripts/restart-with-build.sh` 发版。
  （纪律：`dsh-pmboard` 从 `dist` 加载，只改源码不 build 等于没改。）
- **回滚路径**：`git revert` 对应提交 → 重跑 `build:client`（过 WRAP_SENTINEL 哨兵）→ 重启。
  台账与后端零残留，无需回填。

## 验收口径 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

在 `packages/web/dsh-pmboard` 下执行：

```bash
# FR-4①：渲染器不再调用执行流程块（函数可留，调用必须断）——期望 exit 1（无匹配）
grep -n "renderProcessFold" src/client/node-panel.ts
# FR-4②：渲染输出不含该标题行 —— 期望全部通过
npx vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts
# FR-5：面板侧不再拉两条留痕 —— 期望 exit 1（无匹配）
grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts
# FR-5 反面：看板的既有消费方逐字未动 —— 期望恰好 1 处
grep -c "fetchInjectionInfo" src/client/board-mount.ts
# FR-2/FR-3：一次性持有器 + 失败提示映射 —— 期望全绿
npx vitest run tests/board-focus.test.ts tests/board-entry.test.ts
# 构建门（页面插件产物必须重建且过哨兵）
pnpm build:client
```

**对 requirement.md 原始验收命令的一处修正（须在确认门说明）**：原文写的是
`grep -rn "fetchInjectionInfo\|fetchIsolationLog" packages/web/dsh-pmboard/src/client`（整目录、期望非 0）。
该命令**必然仍匹配** `src/client/board-mount.ts:721`（看板自己的「本次注入了什么」块）与
`src/client/api.ts:53,68`（API 层定义本身），而 requirement「不做什么 1/2」明确禁止动看板与后端。
故本设计把可证伪的不变量收紧为「**面板侧三文件内零引用**」，并追加一条**反面断言**（board-mount 恰好 1 处）
防止顺手误删看板消费方。这不是降低标准，而是把标准钉在「面板这一侧」这个真实边界上。

**端到端（人工，:13080）**：① 点开任一流程节点（含分类跳过节点）→ 状态行出现「项目看板 ↗」，
且面板里**没有**「🔄 执行流程」那一行；② 点入口 → 切到项目看板并显示**这条需求的详情**，节点面板关闭、
会话没被切走；③ 刷新页面 → 看板回到默认视图（非粘滞）；④ 用不存在的 REQ 触发 → 仍停在会话页并有失败提示。

## 遗留问题 `serves: FR-1`

| 问题 | 影响 | 计划 |
|---|---|---|
| `requirement.md` 无 front-matter（缺 `sides` / `requirement_refs`） | 本需求是前端改动，但 G2 不会要求 `frontend.md`/`backend.md`；端侧声明与设计文档集脱钩 | 本设计**照前端改动全交** `frontend.md` + 原型（不靠门禁兜底）；是否补 front-matter 由人裁定 |
| `node-panel-process.ts` 成死代码（无调用方） | 体积与认知负担；`tests/node-panel-process-map.test.ts` 仍在守护一个无人调用的模块 | 本轮按 requirement「函数可留」保留，另立清理项 |
| RTM 解析器 `parseRequirementFRs` 不接受行首列表符，与提示词示范口径冲突 | 追溯视图 `total_frs` 恒为 0 | 已单独记录（本设计的 serves 标注不受影响），另立 bug 需求 |
