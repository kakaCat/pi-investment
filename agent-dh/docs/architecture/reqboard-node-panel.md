---
id: reqboard-node-panel
title: 节点详情面板（锚定式 node-panel）
summary: 会话流程条节点点开后的就地面板：锚定在流程条下方右侧、无遮罩无底栏；「基础信息」按节点给该看的，「执行流程」把该阶段提示词的纪律与真实台账做规定 vs 实际对照；实施节点改 DAG·泳道双视图（REQ-260923134706-e72f）。
type: architecture
status: living
updated: 2026-09-23
owners: [session-f3978f17]
tags: [reqboard, node-panel, gui, REQ-260923134706-e72f]
---

# 节点详情面板（锚定式 node-panel）

> 来源：REQ-260923134706-e72f；设计基线：`packages/web/dsh-pmboard/stage-modals-alpine.html`（用户多轮评审定稿）。
> 前身是 REQ-31e11f 的 `stage-panel.ts`（居中大弹框、节点间不同质的纯文字流水账）——**本页描述替代它的形态**，
> 看板页与需求详情页不受影响（边界见 §6）。

## 1. 解决什么问题

会话顶部流程条能点节点之后，人真正想问的是两件事：

1. **这一步交付了什么**（产物、设计文档、DAG、验收统计、归档去向）——散在文字里翻不到；
2. **这一步背后到底发生了什么**（注入了哪份提示词、规定动作有没有做、上下文怎么被压缩传递）——原来完全看不见。

同时，旧弹框居中盖住整页、"打开项目看板/收起"三条底栏打断阅读，长文档路径内联在面板里既挤又难点。

## 2. 形态（用户可见）

| 维度 | 定稿形态 |
|---|---|
| 位置 | 贴着流程条**下方右侧**展开（间隙 8px，右边缘对齐），**无全屏遮罩** |
| 关闭 | 右上角 × ｜ 点面板外部（二者其一） |
| 底栏 | 无（不再有「打开项目看板 / 打开需求看板 / 收起」） |
| 尺寸/观感 | 白底细边小圆角 10px，最宽 720px，超 68vh 内部滚动；浅灰折叠头 + 胶囊标签 + 细分隔线 |
| 面板头 | 第一行 = 需求编号胶囊 + 需求标题；第二行 = 节点状态胶囊 + 一句话进展 + 最近动态相对时间 |
| 两段折叠 | 「ℹ️ 基础信息」默认**展开**（实施节点没有这一段）；「🔄 执行流程」默认**收起** |

## 3. 各节点基础信息（按节点给该看的）

| 节点 | 基础信息内容 |
|---|---|
| 立项 draft | 需求描述 / 分类 / 文档位置 / 来源窗口 / 创建时间 |
| 需求分析 brainstorming | 已登记的 requirement 产物文档清单 |
| 设计 design | 设计文档逐份「✅ 已交 / ⬜ 未交」（条件文档、豁免有标注） |
| 拆分 decomposing | 拆分计划文档 + 📊 DAG 层级（按最长依赖链分层，节点可点开任务卡） |
| 实施 implementing | **不设基础信息**，直接 [DAG] [泳道] 双视图，默认 DAG |
| 验收 accepting | 验收材料 + 验收单统计（共 N 项 / 通过 / 不通过 / 待裁决） |
| 归档 archived | ✅ 已归档徽标 + 归档文档清单 + 🔗 合并到项目清单 + 💡 一句话结论 |

泳道 = 6 列看板（待开始 / 开发中 / 联调中 / 测试中 / 待复核 / 已完成），列头带数量胶囊，列内卡片竖排可纵滑，点卡片开任务卡。

## 4. 「执行流程」= 规定 vs 实际（本面板最要紧的一段）

三段固定结构（`src/client/node-panel-process.ts`）：

| 段 | 规定一侧（真源） | 实际一侧（留痕） |
|---|---|---|
| 📝 提示词注入 | 该阶段应为的片段入口（`<stage>/light`、`<stage>/<category>`、`common/iron-rules`） | `state/prompt-injection-log.json` 经 `GET /dashboard/api/reqboard/injection-log`：真实 routeKey / 命中层级 / fragmentIds / 字符数 / 时间；路由壳（三段 id）显示「含 N 个子片段」而不假装有文件 |
| ⚙️ 执行动作 | `STAGE_PROCESS` 里每条 `actions[].cite`（**逐字取自该阶段提示词片段**的纪律原文） | 该节点**真实台账**：产物登记/人工确认（artifacts）、状态推进（timeline）、任务流转（tasks.executions）、验收单、归档材料 → ✅ 已做 / ⬜ 未见记录 + 出处 |
| 🗜️ 上下文管理 | 该阶段规定的压缩/保留/下阶段注入口径 | `state/node-isolation-log.json`：status（replaced/skipped/rejected/fallback）/ 替换区间 range / 输入包 packageChars / reason |

两条纪律：

- **实际只认持久台账**，不声称是「窗口工具调用日志」——PTC 模式下窗口内部调用统一呈现为 `run_code`，
  不落库、不按节点切分，做不到就不说。
- **对照表不许腐烂**：`tests/node-panel-process-map.test.ts` 逐条断言 `actions[].cite` 能在对应阶段片段语料里找到、
  且引用的片段文件真实存在——提示词改了而面板没跟上，测试变红。

立项节点无阶段提示词（由 CaptureTool 引导段驱动），其动作为结构性事实（需求存在即 ✅），并额外显示「👤 用户选择（立项四问）」。

## 5. 数据来源与接口

| 数据 | 入口 |
|---|---|
| 全流程节点概览（面板主数据） | `fetchStageOverview` → `StageOverview`（与看板同源，契约见 reqboard-stage-detail.md） |
| 会话进度 + 需求头（含 `promptDifficulty`） | `GET /dashboard/api/reqboard/session/:id/progress` |
| 提示词注入留痕 | `GET /dashboard/api/reqboard/injection-log?window=<session>` |
| 节点隔离留痕（本期新增，**只读**） | `GET /dashboard/api/reqboard/isolation-log?window=<session>&k=<n>` |
| 打开文档全文 | 面板内一律 `data-action="open-doc"` → 官方右侧栏（面板不内联全文） |

挂载点：`src/client/conversation-progress.ts`（会话标题栏槽位），面板 HTML 由 `node-panel.ts` 纯函数产出、经 `dangerouslySetInnerHTML` 注入；折叠用原生 `<details>`，视图切换走事件委托（不发网络请求）。

## 6. 边界与纪律

- **只作用于面板根节点之下**：类名一律 `dsh-pm-` 前缀，样式是独立分片 `src/client/styles/node-panel.ts`，拼进 `styles.ts`，不改既有分片；看板其他页面（需求详情/泳道看板/工具卡/Token 页）外观不动。
- **不内联长文档全文**：面板是索引不是阅读器。
- **不改会话顶部流程条本身**（节点/连线/token 维持原样）。
- **动作映射表是代码里的静态表**：不做后台可编辑（可编辑化会立刻产生漂移）；要改就是改代码 + 过防漂移单测。
- **数据诚实**：无产物/无任务/无动作/无留痕显示明确空态，拿不到的字段宁可不显示、绝不伪造条目。

## 7. 已知偏差 / 待办

- 实施节点的视图切换按钮实现文案是「**DAG** / 泳道」（与拆分节点统一命名，经用户裁定），需求文档字面写的是「流程图 / 泳道」——如需统一，改一处文案即可。
- 宿主入口 `src/index.ts` 单文件超 400 行（**HEAD 上即 415 行，属既有红**，不在尺寸门禁白名单允许范围内），会让「全量测试绿」长期不可达，建议单开拆分卡。

## 8. 追溯

- 需求档案：`docs/requirements/REQ-260923134706-e72f/`（requirement / design×7 / decomposition / verification / tests/evidence.md / reviews/self-review.md）
- 验收证据：该目录 `tests/evidence.md` + `packages/web/dsh-pmboard/scripts/.probe/acceptance-report.json`（无头浏览器 8 步读数）+ a1..a8 截图
- 名词口径：[pmboard-ui-glossary.md](pmboard-ui-glossary.md)（本页替代其 §5 的旧 stage-panel 描述）
