# 面板迁移清单（其余 4 页）· 可排期

> REQ-260928185112-e20d（refactor）· serves: **FR-5** · 子卡 t-10e948（父卡 t-c7f36f「迁移清单收口（其余 4 页）」）
> 事实基线：**2026-09-28 20:5x CST 对本仓工作区 /Users/yunpeng/pi-investment/agent-dh 的实测**（口径与逐条命令见 §4）。
> 上游依据：`docs/requirements/REQ-260928185112-e20d/design/migration.md`（设计 2/2）、`requirement.md`（FR-5）。

## 0. 口径与结论摘要

- **口径**：「页面包」= `packages/web/<pkg>` 下自带 `src/client` 的 web 插件；「同款」= 使用 conversation 覆盖层机制（自身 `src/client/dom.ts` 导出 `ACTIVE_ATTR`，由 `page-kit.createBoardShell` 挂到会话列并靠 `html[data-dsh-*-active]` 显隐）。
- **实测结论**：`packages/web` 下 7 个一级包 = 页面包 6 + 共享 kit 1（`page-kit`）；其中**同款面板 5 个**（`dsh-pmboard` + 本清单 4 页），**待迁 4 项**（`dsh-pmboard` 已由 FR-2/FR-3/FR-4 迁移完毕，不重复列）。
- **关联 CSS 口径**：`grep -c "data-dsh-<前缀>-active" <该包>/src/client/styles.ts`（含注释行；命中行号逐个列出）。
- **规模口径**：主口径 = 顶层 `src/client/*.ts` 文件数 / 行数（与设计表 4 页数值同量级）；另附递归全量供对照。

## 1. 面板清单（现有入口 / 依赖属性 / 关联 CSS / 改造工作量 / 风险）

| 页面 | 现有入口 | 依赖属性 | 关联 CSS | 改造工作量 | 风险 |
|---|---|---|---|---|---|
| **双线执行** `@pi-investment/dashboard-execution` | `src/client/index.ts:124` `slots.inject('sidebar.footer.action')`（官方槽；label `'智能执行'` = `footer-action.ts:20`）。另有**未被 import** 的 `src/client/sidebar-entry.ts`（page-kit 包装，死代码） | `data-dsh-exec-active`（`dom.ts:12`）+ `OTHER_ACTIVE_ATTRS` 6 项（`dom.ts:14`） | **4 条**：`styles.ts:34,35,36,38` | **小**：9 ts / 1989 行；已有 controller + onMount 契约，改面与 dsh-pmboard 同构（新增 `page/{register.ts,host.ts}`、删 footer-action + 属性机、CSS 改锚） | **低-中**：①入口从「侧栏底部槽」迁到「面板列表」，位置/顺序变化需视觉确认；②`addEventListener` ×5（client 全目录）需 dispose 完整；③`sidebar-entry.ts` 死代码须一并清（否则迁移后双入口风险） |
| **账户持仓** `@pi-investment/dashboard-holdings` | `src/client/index.ts:80` `mountSidebarEntry({...})`（**page-kit DOM 注入**到侧栏 logo 行下方；label `'账户持仓'`）。另有**未被 import** 的 `src/client/footer-action.ts`（死代码） | `data-dsh-hld-active`（`dom.ts:12`）+ `OTHER_ACTIVE_ATTRS`（`dom.ts:15`，多行数组） | **4 条**：`styles.ts:34,35,36,38`（另 `services/parts.ts:72` 为说明性提及，非选择器） | **小-中**：9 ts / 1521 行；额外两处耦合：`injectSolveStyles('dsh-hld')`（solve-kit 样式）与「挂载不取数」契约 | **中**：①FR-2 同款语义——`onMount` 里启动即取数的历史缺陷（REQ-6cbbf7）**由 `tests/parts.test.ts` 锁死**，迁移须保住「未在看 = 不取数」（`parts.ts:68-80` 契约注释）；②侧栏行样式 `[data-dsh-hld-entry]`（`styles.ts:30-32`）随入口一起退场，须清；③`footer-action.ts` 死代码清理 |
| **基因进化** `@pi-investment/dashboard-genome` | `src/client/index.ts:33` `mountSidebarEntry(controller)`（**page-kit DOM 注入**；label `'自主进化'`） | `data-dsh-gen-active`（`dom.ts:12`）+ `OTHER_ACTIVE_ATTRS`（`dom.ts:14`） | **9 条**（属性锚最多）：`styles.ts:5,29,31,32,33,34,356,357,359` | **小**：7 ts / 1064 行；`inject: []` 无 sessions 依赖，宿主改造最干净 | **低**：①`inject` 现为**空数组**，须**新增** `'slots'`（+ 需要导航时 `'layout'`）并同步 `package.json` `dsh.client.inject`；②9 条中 `styles.ts:29`（`html[data-dsh-gen-active] .dsh-gen-board { display:flex }`）是**功能锚**，只能改锚不能直删 |
| **公告板** `@pi-investment/dashboard-bulletin` | `src/client/index.ts:75` `mountSidebarEntry({...})`（自有 `sidebar-entry.ts` 委托 page-kit；label `'公告板'`） | `data-dsh-bbd-active`（`dom.ts:12`）+ `OTHER_ACTIVE_ATTRS`（`dom.ts:14`） | **5 条**：`styles.ts:6,36,37,38,42` | **小**：7 ts / 904 行；包体最小 | **低-中**：①入口同时注入 toast 样式（`index.ts:65` `injectToastStyles("dsh-bbd")`），迁后须保留（否则认领/转交弹窗失色）；②`inject` 缺 `'slots'`（现 `['sessions','workspaces']`）须补；③**无测试文件**（`tests/*.test.ts` = 0），回归只能靠 `build:client` + 手工/E2E |

> 4 页共同动作（每页同一套）：`registerPagePanel` 注册两端（`main` + `sidebar.panellist`，id 同源）→ `main` 宿主（`useRef`+`useEffect`）接管现有命令式容器 → 删自身入口（`sidebar-entry.ts` 或 `slot` 注册）→ 删 `ACTIVE_ATTR`/`OTHER_ACTIVE_ATTRS` 与属性选择器 → 删 `createBoardShell`/`board-shell` 引用 → 改锚板容器约束 CSS。

## 2. 逐页排期卡（可直接建任务）

每页的「验收锚点」沿用 FR-5/design §行为等价验证：静态 grep 零命中 + `build:client` 过 `verify-client-build` 哨兵 + 该页 `pnpm --filter <pkg> test` 不新增红 + E2E（侧栏条目 `aria-current="page"`、主列渲染该页、刷新不回面板）。

1. **T-EXEC｜双线执行**（风险低-中）：新增 `page/{register.ts,host.ts,page-runtime.ts?}`；`index.ts` 改调 helper 并删 `slots.inject('sidebar.footer.action')`；删 `footer-action.ts` + `sidebar-entry.ts`（死代码）；`dom.ts` 删属性常量；`styles.ts` 4 条改锚；`inject` + `'layout'`（`'slots'` 已有）；`package.json` `dsh.client.inject` 同步。
2. **T-GEN｜基因进化**（风险低，推荐首开工）：难度最低（`inject: []`、无 sessions），可作 4 页迁移的模板验证页。`styles.ts` 9 条中最少 1 条为功能锚须改锚。
3. **T-BBD｜公告板**（风险低-中）：保留 toast 样式注入；`inject` 补 `'slots'`；补 1 个宿主单测（当前 0 测试）。
4. **T-HLD｜账户持仓**（风险中，建议最后）：先补「挂载不取数」回归断言（`tests/parts.test.ts` 已锁 `mount → null`），迁移后复跑；`injectSolveStyles` 保留；清 `footer-action.ts` 死代码。

依赖：4 页**共享前置裁决**（见 §5：page-kit 处置、helper 落点）→ 每页可并行、独立回滚。

## 3. 与需求文档「8 个面板 / 其余 7 个」的差异（实测）

| 维度 | requirement.md 措辞 | 2026-09-28 实测 |
|---|---|---|
| 面板数量 | 「`packages/web` 下 **8 个面板**（dsh-pmboard / execution / atb / taskboard / ssh / hld / bbd / gen）」 | `packages/web` 一级包 **7 个** = 页面包 **6** + kit 1（`page-kit`）；其中**同款覆盖层面板 5 个** |
| 其余待迁 | 「同款实现另有 **7 个**面板（execution / atb / taskboard / ssh / hld / bbd / gen）」 | **待迁 4 项**：execution / holdings(hld) / genome(gen) / bulletin(bbd) |
| atb / taskboard / ssh | 列为面板 | **死引用**：无对应包、无 git 历史（`git log --all -S` 三条全为 **0**），仅作为字符串残留在 4 个包的 `OTHER_ACTIVE_ATTRS` 数组字面量里 → **不建任务、不追认** |
| 未列出的页面包 | 未提及 | `web-liveness` 是页面包但**不用**该模式（`createBoardShell`/`ACTIVE_ATTR` 在 `web-liveness/src` **零命中**，走 banner 模式）→ **不在迁移面** |

**实际待迁 = 4 项**（dsh-pmboard 由 FR-2/FR-3/FR-4 覆盖），与 `design/migration.md` §面板清单一致（设计表 5 行 = 看板 + 4 页）。

### 3.1 requirement.md 措辞更正建议（**本卡未执行**，登记为待裁决项）

建议把 requirement.md §背景-4 的「`packages/web` 下 8 个面板（…atb / taskboard / ssh…）」与「同款实现另有 7 个面板」改为「`packages/web` 下 5 个同款覆盖层面板（dsh-pmboard / execution / holdings / genome / bulletin）；其中待迁 4 页」，并注明 `atb/taskboard/ssh` 为死引用、`web-liveness` 不属该模式。
纠正路径（父卡实施项所给）：`reqboard_submit(kind=requirement, requirement_id=REQ-260928185112-e20d, change_note="…")`。
**未代执行的理由**（显式登记，不静默）：①本窗口未绑定该需求（`reqboard_status.bound=false`），代提交属跨窗口写；②`requirement.md` 是已人工确认的上游产物，重交会按工具语义给下游文档标「待同步」，属需求方/父卡裁决范围，不在一张 dev 子卡内单方面改动；③本清单 §3 已把差异与建议措辞落盘，信息不丢失。

## 4. 实测命令与输出摘要（可复现）

> 全部在工作区根 `/Users/yunpeng/pi-investment/agent-dh` 执行，2026-09-28 20:5x CST。

```text
### C1 packages/web 一级目录（页面包 vs kit）
bulletin dsh-pmboard execution genome holdings page-kit web-liveness

### C2 使用同款 conversation 覆盖层的页面包（各自 dom.ts 定义 ACTIVE_ATTR）
bulletin
execution
genome
holdings
   → 命令：grep -rl "export const ACTIVE_ATTR" packages/web/*/src
   → 加 dsh-pmboard = 5 个同款面板

### C3 现有入口
execution/src/client/index.ts:124:      slots.inject('sidebar.footer.action', () =>
bulletin/src/client/index.ts:75:    const disposeEntry = mountSidebarEntry({
genome/src/client/index.ts:33:    const disposeSidebar = mountSidebarEntry(controller)
holdings/src/client/index.ts:80:    const disposeEntry = mountSidebarEntry({

### C4 关联 CSS 条数（grep -c "data-<前缀>-active" <pkg>/src/client/styles.ts）
execution -> 4
holdings -> 4
genome -> 9
bulletin -> 5

### C5 死引用（atb/taskboard/ssh）：无包、无 git 历史
git log --all -S dashboard-atb    : 0
git log --all -S dashboard-taskboard : 0
git log --all -S dashboard-ssh    : 0
bulletin/src/client/dom.ts:14:export const OTHER_ACTIVE_ATTRS = ['data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active', 'data-dsh-exec-active', 'data-dsh-hld-active', 'data-dsh-gen-active']
execution/src/client/dom.ts:14:export const OTHER_ACTIVE_ATTRS = ['data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active', 'data-dsh-hld-active', 'data-dsh-bbd-active', 'data-dsh-gen-active']
genome/src/client/dom.ts:14:export const OTHER_ACTIVE_ATTRS = ['data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active', 'data-dsh-hld-active', 'data-dsh-exec-active', 'data-dsh-bbd-active']
holdings/src/client/dom.ts:15:  'data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active',

### C6 规模（顶层 src/client/*.ts；递归全量对照）
execution: top=9 文件/1989 行；recursive=9 文件/1989 行
holdings : top=9 文件/1521 行；recursive=9 文件/1521 行
genome   : top=7 文件/1064 行；recursive=7 文件/1064 行
bulletin : top=7 文件/904 行；recursive=7 文件/904 行
dsh-pmboard: top=22 文件/4384 行；recursive=69 文件/13246 行

### C7 web-liveness（页面包但不属覆盖层模式）
零命中   → grep -rc "createBoardShell|ACTIVE_ATTR" packages/web/web-liveness/src

### C8 inject 现状（模块级 export const inject）
execution: export const inject: string[] = ['slots', 'sessions', 'workspaces']
holdings : export const inject: string[] = ['slots', 'sessions', 'workspaces']
genome   : export const inject: string[] = []
bulletin : export const inject: string[] = ['sessions', 'workspaces']

### C9 page-kit 共享面（4 页共同依赖 —— 非「无共享改动点」）
page-kit/src/client/dom.ts:12           export const ACTIVATE_EVENT = 'dsh-panel-activate'
page-kit/src/client/dom.ts:15           export function sidebarRoot()
page-kit/src/client/dom.ts:23           export function conversationColumn()
page-kit/src/client/board-shell.ts:50   export function createBoardShell(deps)
page-kit/src/client/sidebar-entry.ts:26 export function mountSidebarEntry(opts)

### C10 未被 import 的入口模块（死代码）
execution/src/client/sidebar-entry.ts 被 import 次数: 0
holdings/src/client/footer-action.ts  被 import 次数: 0
```

差异说明（R-013 数据来源标注）：设计与本清单对 4 页规模的数值差 <1%（execution 2000 vs 1989、holdings 1530 vs 1521、genome 1071 vs 1064、bulletin 911 vs 904，口径=顶层 `src/client/*.ts`），属测量时点/计数方式差异，不影响排期结论；`dsh-pmboard` 设计写「24 个 ts、约 4900 行」，与本次任一常用口径（顶层 22/4384、递归 69/13246）都不吻合，**排期时以本清单口径为准**。

## 5. 横切前置裁决项（4 页共同，需先定后开工）

1. **共享改动点 = `page-kit`（修正设计的一处表述）**：design §迁移单位写「页与页之间**没有共享改动点**」——该断言对 `dsh-pmboard`（自包含、不依赖 page-kit，helper 落自己包内）成立，但**对 4 页不成立**：4 页全部经 `@pi-investment/page-kit` 使用 `createBoardShell` / `sidebarRoot` / `conversationColumn` / `ACTIVATE_EVENT` / `mountSidebarEntry`。故 4 页迁移**必须先裁决 page-kit 的处置**：①改 page-kit 一次覆盖 4 页（工作量集中、推荐），或②保留 page-kit、逐页绕过（4 页各写自己的宿主，重复劳动 + page-kit 残留死代码）。
2. **helper 落点**：`registerPagePanel` 目前落在 `packages/web/dsh-pmboard/src/client/page/page-panel.ts`，该文件「零 import」自包含，且 dsh-pmboard 与这 4 页**无依赖关系**。4 页复用需二选一：**迁 helper 到 `page-kit`**（4 页已依赖它的唯一共享面，推荐），或给 4 页新增对 dsh-pmboard 的依赖。选型直接决定每页工作量口径与是否需要动 `page-kit`。
3. **inject 增量（两处同步）**：`execution`/`holdings` 已有 `'slots'`，仅需补 `'layout'`（页面内需要 `selectPanel` 时）；`genome`（现 `[]`）/`bulletin`（现无 `'slots'`）须补 `'slots'`。模块级 `export const inject` 与 `package.json` 的 `dsh.client.inject` **两处都要改**（dsh-pmboard 已示范：两处各含 `layout`）。
4. **CSS 改锚 ≠ 直删**：dsh-pmboard 的 `styles/panel.ts:218` 把属性锚由 `html[data-dsh-pm-active]` **改锚**为 `[data-dsh-pm-view]`（保留 `min-height: 0` 约束）；4 页同样存在「属性锚 + 板容器约束」耦合（如 `genome styles.ts:29`），需逐条判定改锚/直删。
5. **入口副产品不可夹带丢失**：execution 的 footer 按钮「悬停速览进行中需求」、bulletin 的 toast 样式注入、holdings 的 solve-kit 样式注入，均随入口模块迁移或需另行保留——按行为等价原则逐项确认（design §看板迁移步骤 5 同款纪律）。

## 6. 排期建议与不在范围

- **建议顺序**：genome（模板页，风险最低）→ bulletin → execution → holdings（有锁死的取数契约，风险最高）。每页一提交、一独立回滚。
- **不在本清单范围**：4 页源码改动本身（design 明写「本轮只交上表清单，不动这 4 个包的代码」）；数据层 / HTTP 路由 / `reqboard` 协议；`web-liveness` 与 `page-kit` 的代码改动（§5 仅列为前置裁决项）；`requirement.md` 措辞更正（§3.1 待裁决）。
