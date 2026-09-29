# REQ-260928185112-e20d 拆分计划

> 页面插件统一 `main` 插槽：看板迁移样板 + 其余面板迁移清单（refactor）
> 设计依据：`design/architecture.md`、`design/migration.md`（均已落章确认）

## 一、目标与做法

把项目看板（唯一被改的插件 `packages/web/dsh-pmboard/`）从「会话列 DOM 覆盖层 + `html[data-dsh-pm-active]` 显隐」
迁到 DSH 原生页面机制：`main` keyed 插槽（`key=PANEL_ID`）+ `sidebar.panellist` 条目（`id=PANEL_ID`，同源）+
`ctx.layout.selectPanel(null)` 回对话；并把其余 4 个同款页面整理成可排期清单。

两处关键边界（详细理由见设计文档）：

- `dsh-pmboard` **自包含**：依赖只有 `@deepseek-ai/dsh-tools`，**不 import `@pi-investment/page-kit`**（helper 落在本包的 `src/client/page/`）；
- 其余 4 个页面包（execution / holdings / genome / bulletin）与 `page-kit` 的源码**一行不改**，只出清单。

## 二、边界（本次不做）

- 不改看板业务逻辑、视觉与数据层（`view.ts` 渲染结构、`/dashboard/api/reqboard/*`、`queue.json` 全不动）；
- 不把命令式看板重写为 React（薄宿主 + `ref` 挂载）；
- 不引入 URL 路由；不新增 npm 依赖；
- 不批量改其余页面；不修与本迁移无关的既有缺陷（发现即另立项）。

## 三、代码层面变更盘点（全部在 dsh-pmboard 内）

**新增**

1. `packages/web/dsh-pmboard/src/client/page/page-panel.ts` —— registerPagePanel（两端同源注册）
2. `packages/web/dsh-pmboard/src/client/page/register.ts` —— 本页注册（id=项目看板）
3. `packages/web/dsh-pmboard/src/client/page/host.ts` —— 薄 React 宿主（useRef + useEffect）
4. `packages/web/dsh-pmboard/tests/client-page-panel.test.ts` —— helper 单测

**修改**

5. `src/client/index.ts` —— 改注册、加 `layout` inject、存 page-runtime
6. `src/client/board-mount.ts` —— 导出 `attachBoard(container)`
7. `src/client/session-jump.ts` —— 删 `closeHostPanel`、改 `selectPanel(null)`
8. `src/client/dom.ts` —— 删属性常量与互斥表
9. `src/client/styles/base.ts`、`styles/panel.ts` —— 删属性选择器
10. `packages/web/dsh-pmboard/package.json` —— `dsh.client.inject` 与模块 inject 加 `layout`

**删除**

11. `src/client/board-shell.ts`（其生命周期职责由宿主承接）

**产出文档**

12. `docs/requirements/REQ-260928185112-e20d/migration-checklist.md` —— 其余 4 页的可排期清单

## 四、批次与依赖

- **批次 1（纯新增，零调用方）**：t1 helper。行为零变化，可独立合入。
- **批次 2（接线）**：t2 宿主 + attachBoard → t3 两端注册与 index 接线。
- **批次 3（导航与拆旧）**：t4 跳转归位 → t5 拆 board-shell/属性机制。
- **批次 4（验证与清单）**：t6 行为等价验证 → t7 清单收口。

依赖严格单向、无前向引用：t1 → t2 → t3 → t4 → t5 → t6 → t7。

## 五、任务表

| 卡 | 标题 | 批次 | 依赖 | 验收要点 |
|---|---|---|---|---|
| t1 | 新增页面注册 helper registerPagePanel | 1 | — | 单测全绿 + 两次注册同名同 id + 不 import page-kit |
| t2 | 命令式看板改由宿主挂载（attachBoard） | 2 | t1 | 现有测试全绿 + disposer 清定时器/监听 |
| t3 | 注册两端并接线（index.ts） | 2 | t2 | build:client 过三闸 + 不再注册 sidebar.footer.action |
| t4 | 跳转语义归位（selectPanel(null)） | 3 | t3 | 测试全绿 + closeHostPanel 零命中 |
| t5 | 拆除旧机制（属性显隐/互斥/壳） | 3 | t4 | 属性与壳零命中 + build 三闸不退化 |
| t6 | 行为等价验证（含 E2E） | 4 | t5 | 6 类命令全过 + E2E 4 条断言留证 |
| t7 | 迁移清单收口（其余 4 页） | 4 | t6 | 清单文件 4 行五列齐 + 实测命令输出 |

### 覆盖对照（需求条款 ↔ 接收任务）

| 需求条款 | 说明 | 接收任务 |
|---|---|---|
| FR-1 | 页面注册标准 helper（main 与 sidebar.panellist 两端同源） | t1 |
| FR-2 | 看板页面化：薄宿主挂载 + 轮询生命周期 | t2, t3 |
| FR-3 | 跳转语义归位：selectPanel(null) + openSession | t4 |
| FR-4 | 旧机制清除：属性显隐 / 互斥 / board-shell | t5 |
| FR-5 | 其余页面迁移清单 | t7 |

（t6 是行为等价验证卡，不接收单一条款；表头「需求条款 / 接收任务」为覆盖门禁的读取口径。）

每张卡的 implementation 与可证伪 acceptance 见任务卡（批准后自动落库），此处只给全局视图。

## 六、面板口径差异（批准前请知悉）

需求文档写「8 个面板 / 其余 7 个」，实测**只有 5 个页面包存在**：dsh-pmboard、execution、holdings、genome、bulletin；
`atb` / `taskboard` / `ssh` 无对应包、无 git 历史（`git log --all -S"dashboard-atb"` 为空），
只残留在各面板 `OTHER_ACTIVE_ATTRS` 字符串里。因此迁移清单为 **4 项**（看板本体由 t1–t6 覆盖）。
需求文档的「8 个 / 7 项」措辞与实际不符，t7 会把该差异连同实测命令写进清单；
若要直接更正 requirement.md 的措辞，走 `reqboard_submit(kind=requirement, change_note=...)`（上游返工，需重新落章）。

## 七、交棒

本计划经人批准后 `reqboard_decompose` 落库任务卡并进入实施；
实施按 t1 → t7 顺序推进，卡完成用 `reqboard_task_move` 推进并逐卡汇报。
