# 迁移设计与行为等价验证 «serves: FR-3, FR-4, FR-5»

> REQ-260928185112-e20d（refactor）· 设计文档 2/2
> 文档级 serves: FR-3, FR-4, FR-5
> 事实基线：2026-09-28 对本仓 `packages/web/` 的实测（口径见各节）。

## 迁移单位：一个页面 = 一个文件夹 «serves: FR-5»

每个页面一处改动、一处回滚，页与页之间**没有共享改动点**（`dsh-pmboard` 不依赖 `page-kit`，helper 落在它自己包内）。
页面文件夹 = `packages/web/<包>/src/client/page/`，新增 `register.ts`（注册两端）与 `host.ts`（薄宿主）。
以此为单位可并行、可独立验证：改完一页 → `pnpm --filter <包> build:client` + 单测 → 再下一程。

## 面板清单（实测） «serves: FR-5»

需求文档列的 8 个名字里**实测只有 5 个存在**；`atb` / `taskboard` / `ssh` 三个在本仓无对应包、
无 git 历史（`git log --all -S"dashboard-atb"` 空），只残留在各面板 `OTHER_ACTIVE_ATTRS` 字符串数组里。
故迁移清单 = 下表的 4 个页面（看板本体由 FR-2/FR-3/FR-4 覆盖，不重复列）。

| 页面 | 现有入口 | 依赖属性 | 关联 CSS | 改造工作量 | 风险 |
|---|---|---|---|---|---|
| 项目看板 `dsh-pmboard` | `slots.inject('sidebar.footer.action')` | `data-dsh-pm-active`（+ 6 个兄弟属性互斥表） | 5 条：`styles/base.ts` 4 + `styles/panel.ts` 1 | 大：新增 page/、删 board-shell、改 session-jump（client/ 24 个 ts、约 4900 行） | 中：监听器/定时器多，dispose 漏一处即"看似关掉仍在跑" |
| 双线执行 `execution` | `slots.inject('sidebar.footer.action')` | `data-dsh-exec-active` | 4 条：`styles.ts` | 小：client/ 9 个 ts、约 2000 行，已有 controller/onMount 契约 | 低-中：入口从侧栏底部迁到面板列表，位置变化需确认 |
| 账户持仓 `holdings` | `mountSidebarEntry`（DOM 注入 logo 行下方） | `data-dsh-hld-active` | 4 条：`styles.ts` | 小-中：client/ 9 个 ts、约 1530 行 | 中：`onMount` 里启动即取数有测试锁定，迁移要保住"未在看=不取数" |
| 基因进化 `genome` | `mountSidebarEntry` | `data-dsh-gen-active` | 9 条：`styles.ts`（属性锚最多） | 小：client/ 7 个 ts、约 1071 行 | 低：`inject: []`，无 sessions 依赖 |
| 公告板 `bulletin` | `mountSidebarEntry`（自有 `sidebar-entry.ts`） | `data-dsh-bbd-active` | 5 条：`styles.ts` | 小：client/ 7 个 ts、约 911 行 | 低-中：入口同时注入 toast 样式，迁后需保留 |

口径：关联 CSS 条数 = `grep -c "data-dsh-<前缀>-active" <该包样式文件>`；包规模 = `src/client/*.ts` 行数合计。

### 三个名字的处置 «serves: FR-5»

`atb` / `taskboard` / `ssh` 不是待迁页面，是**死引用**：互斥机制整体下线后 `OTHER_ACTIVE_ATTRS` 数组本身即消失，
无需为它们建任务、也不追认历史名字。若认为需求文档的名字需要更正，属需求文档返工，不在设计阶段改。

## 看板迁移步骤（FR-2/FR-3/FR-4 的落地顺序） «serves: FR-2, FR-3, FR-4»

一次只改一类东西，每步可独立验证：

1. **加 helper**：`dsh-pmboard/src/client/page/page-panel.ts` + 单测（假 ctx 断言两次注册的 name/key/id/label 与 id 同源）。
2. **加页面文件夹骨架**：`dsh-pmboard/src/client/page/{register.ts,host.ts}`；`index.ts` 改调 `registerPmboardPage`；
   模块 `inject` 与 `dsh.client.inject` 增加 `'layout'`。
3. **命令式看板接容器**：`board-mount.ts` 导出 `attachBoard(container)`（现有 `onMount` 逻辑原样搬运）。
4. **跳转归位**：`session-jump.ts` 删 `closeHostPanel`，改 `layout.selectPanel(null)`；`index.ts` 接线。
5. **拆旧机制**：删 `board-shell.ts`、`dom.ts` 的 `ACTIVE_ATTR` / `OTHER_ACTIVE_ATTRS` / `conversationColumn`、
   `ACTIVATE_EVENT` 广播与入口 `OPEN_EVENT`、`styles/base.ts` 与 `styles/panel.ts` 的属性选择器。
   `footer-action.ts` 的去留：其「悬停速览进行中需求」是入口按钮的附带功能，入口消失即一并消失；
   若要保留该速览，应作为新交互另开需求——本次不夹带。
6. **清死引用**：`grep` 复验零命中（见 §行为等价验证）。

## 其余 4 页的迁移要点 «serves: FR-5»

每页同一套动作：`registerPagePanel` 注册两端 → `main` 宿主挂进 `attachBoard` → 删自身入口
（`sidebar-entry.ts` 或 footer-action 接线）→ 删 `ACTIVE_ATTR` / `OTHER_ACTIVE_ATTRS` 与属性 CSS → 删 `board-shell` 引用。
本轮只交上表清单，不动这 4 个包的代码；逐页排期由拆分阶段决定。

## 文件级改动盘点 «serves: FR-1, FR-2, FR-3, FR-4»

**新增**

- `packages/web/dsh-pmboard/src/client/page/page-panel.ts`（+ 同包单测；**不动 page-kit**——dsh-pmboard 与该包无依赖关系）
- `packages/web/dsh-pmboard/src/client/page/register.ts`
- `packages/web/dsh-pmboard/src/client/page/host.ts`

**修改**

- `dsh-pmboard/src/client/index.ts`（改注册、加 `layout` inject、存 pageRuntime）
- `dsh-pmboard/src/client/board-mount.ts`（导出 `attachBoard`；不再建 shell）
- `dsh-pmboard/src/client/session-jump.ts`（删 `closeHostPanel`；加 `selectPanel(null)`）
- `dsh-pmboard/src/client/dom.ts`（删属性常量与互斥表）
- `dsh-pmboard/src/client/styles/base.ts`、`styles/panel.ts`（删属性选择器）
- `dsh-pmboard/package.json`（`dsh.client.inject` 与模块 `inject` 同步加 `layout`）

**删除**

- `dsh-pmboard/src/client/board-shell.ts`

**不动**

- 数据层、HTTP 路由、`view.ts` 渲染结构，以及其余 4 个页面的源码（只出清单）。

## 行为等价验证设计 «serves: FR-2, FR-3, FR-4»

### 跑什么、看什么 «serves: FR-2, FR-3, FR-4»

| 层级 | 命令 | 期望 |
|---|---|---|
| 静态 | `grep -r "data-dsh-pm-active" packages/web/dsh-pmboard/src` | 零命中（退出码 1） |
| 静态 | `grep -rn "board-shell\|createBoardShell\|ACTIVE_ATTR\|OTHER_ACTIVE_ATTRS\|closeHostPanel" packages/web/dsh-pmboard/src` | 无代码命中 |
| 单测 | `pnpm --filter dsh-pmboard test` | 全绿（含新 helper 单测） |
| 构建 | `pnpm --filter dsh-pmboard build:client` | `verify-client-build.mjs` OK（体积 / 关键符号 / wrap 哨兵 三道门） |
| 冒烟 | `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` | 全绿 |
| 端到端 | 见下方 E2E | 4 条断言全过 |

### E2E（浏览器，:13080） «serves: FR-2, FR-3»

对已在跑的实例（**不重启、不改端口**）：用 Playwright 打开 `http://127.0.0.1:13080`，断言

1. 侧栏存在 `button[aria-label="项目看板"]`；点击后该按钮 `aria-current="page"`，主列出现 `.dsh-pm-board`；
2. 点 `.dsh-pm-window`（窗口 chip）→ 该按钮不再 `aria-current="page"`，对话容器可见，且目标会话 head 变化；
3. 归档会话 chip（`.dsh-pm-window.is-archived`）点击后出现明确文案（alert/title），不静默；
4. 打开看板后刷新页面 → 不自动回到看板（`activePanelId` 初值为 null）。

注：仓库未内置 Playwright（`node_modules` 无 playwright），脚本以一次性 `npx playwright` 运行，
输出留作验收证据；**不把 Playwright 加进依赖**（避免扩大改动面）。

### 对照的输入输出（行为等价） «serves: FR-2»

旧/新两版对同一批输入应给出相同业务结果：

- 相同 `state`（`GET /dashboard/api/reqboard/state`）→ `view.ts` 的 HTML 输出逐字节相同
  （`buildBoard` 是纯函数，可单测直接比对）；
- 相同点击（`data-action="jump-session"`）→ 同一个 `openSession(sid)` 调用 + 新增一次 `selectPanel(null)`。

## 观察与待裁决（不夹带） «serves: FR-3»

**列表视图的归档按钮**：卡片视图的窗口 chip 对归档会话是「可点 + 明确原因」（符合 FR-3），但列表视图
`renderListCard` 对归档会话**不渲染**「会话」按钮（`views/board.ts:261-271`）——是既有的静默分支。
本设计按「行为等价」原则**不改它**。若确认时要求两处口径一致，请明确指出；那属于行为变更，须另开需求或在拆分阶段显式列入。

## 回滚 «serves: FR-4»

回滚 = 一次提交内还原：恢复 `board-shell.ts`、`dom.ts` 的属性常量、`styles/*` 的属性选择器、
`index.ts` 的 `sidebar.footer.action` 注册与 `session-jump.ts` 的 `closeHostPanel`。
新旧两套挂载不共享状态文件、不动数据层，回滚无需数据修复。
