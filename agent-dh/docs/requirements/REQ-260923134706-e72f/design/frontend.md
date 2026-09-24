---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9]
sides: [frontend]
---

# 前端设计（REQ-260923134706-e72f）

## 原型页面 <!-- serves: FR-1 -->

原型 = 设计基线 `packages/web/dsh-pmboard/stage-modals-alpine.html`（可点击操作的完整原型，
非静态截图）：7 节点逐个点开看内容、折叠开合、流程图/泳道切换均已实测。本设计文档把它落到真实插件。

## 目录与包结构 <!-- serves: FR-1 -->

| 落点 | 内容 | 落此处的理由 |
|---|---|---|
| `src/client/node-panel.ts` | 面板渲染器（纯函数） | 与 stage-panel.ts 同层；独立文件避开另一窗口在途改动 |
| `src/client/node-panel-process.ts` | 执行流程对照表与求值 | 单独成模块：对照表是"映射"，测试与演进聚焦在此 |
| `src/client/styles/node-panel.ts` | 样式分片 | styles/ 目录既有分片模式（panel/board/detail/…），styles.ts 末尾拼接 |
| `src/client/conversation-progress.ts` | 挂载点改动 | 面板渲染的唯一消费方 |

## 组件结构 <!-- serves: FR-1, FR-2, FR-3 -->

```
.dsh-pm-cprog-detail-panel（既有壳：absolute / right:0 / top:calc(100%+8px)，宽度改 720px）
├─ .dsh-pm-np-close（×，右上角）
└─ .dsh-pm-np（data-stage / data-state）
   ├─ .dsh-pm-np-req       [REQ-xxxxxxx]胶囊 + 需求标题
   ├─ .dsh-pm-np-head      状态胶囊(.dsh-pm-np-head-state[data-state]) + 一句话(title) + 相对时间(time)
   ├─ <details.dsh-pm-np-fold open>  ℹ️ 基础信息
   │   └─ 各节点专属内容（doc 清单 / info 行 / DAG / 验收统计 / 归档块）
   └─ <details.dsh-pm-np-fold>  🔄 执行流程（默认收起）
       ├─ .dsh-pm-np-sec 📝 提示词注入（片段条目 → open-doc）
       ├─ .dsh-pm-np-sec ⚙️ 执行动作（对照行：✅/⬜ + 出处）
       └─ .dsh-pm-np-sec 🗜️ 上下文管理（真实隔离留痕）
实施节点：基础信息块缺席；面板中段位 .dsh-pm-np-tabs（[流程图][泳道]）+ .dsh-pm-np-pane 双面板。
```

## 页面与组件（编号表） <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9 -->

| 编号 | 类型 | 名称 | 职责（动宾结构，含响应操作） | 数据来源 | 新增/改动 | serves |
|---|---|---|---|---|---|---|
| FE-1 | 组件 | NodePanel | 渲染单节点面板整体 | renderNodePanel 入参 | 新增 | FR-1 |
| FE-2 | 区块 | PanelHead | 展示 REQ 胶囊+标题 / 状态胶囊+一句话+时间 | progress + StageOverview | 新增 | FR-2 |
| FE-3 | 区块 | InfoFold | 展示节点基础信息与产物清单（点击开文档） | StageDetail.artifacts/body | 新增 | FR-3, FR-4 |
| FE-4 | 区块 | ImplViews | 切换流程图/泳道（点击 tab 换面板） | StageDetail.body.tasks | 新增 | FR-5, FR-7 |
| FE-5 | 区块 | ProcessFold | 展示执行流程三段对照（点击片段开文件） | STAGE_PROCESS + 留痕 | 新增 | FR-6 |
| FE-6 | 控件 | CloseBtn | 收起面板（点击） | - | 新增 | FR-9 |
| FE-7 | 行为 | OutsideClose | 点面板外收起 | document mousedown（既有） | 沿用 | FR-1 |
| FE-8 | 行为 | OpenDoc | 文档条目右侧栏打开 | data-action=open-doc（既有） | 沿用 | FR-3 |

## 状态管理 <!-- serves: FR-1 -->

无新增全局状态。折叠态 = 原生 `<details>` 的 DOM 态；泳道/流程图切换 = DOM 态
（data-action=np-switch-view 委托监听，切 display）。15s 轮询只在数据真变时重渲染，
此时折叠/视图回到默认态（基础信息开、执行流程收、流程图）——与设计稿一致，不做状态持久化。

## 路由与导航 <!-- serves: FR-1 -->

无路由变更。面板在会话页就地展开；文档跳转走既有 open-doc → 右侧栏。

## 样式与主题 <!-- serves: FR-8 -->

新增分片 `NODE_PANEL_CSS`，**全部选择器以 `.dsh-pm-np` 开头**（含折叠头），不改既有全局选择器，
看板其他页面零影响。苹果风取值（与设计稿实测一致）：

- 面板：白底 / 1px 细边 rgba(0,0,0,.12) / 圆角 10px / 阴影 0 8px 28px rgba(0,0,0,.18) / padding 12px 14px；
  宽 `min(720px, calc(100vw - 130px))`，max-height 68vh 内滚；无遮罩。
- 文字：#1d1d1f 正文 / #6e6e73 辅助 / #86868b 三级；链接蓝 #0071e3。
- 折叠头：浅灰 #f5f5f7 底、圆角 12px、hover #ebebf0；▸ 字形展开旋转 90°。
- 胶囊：状态/分类/REQ 编号均为 980px 全圆角；状态色沿用流程节点四态（done 绿/current 蓝/pending 灰）。
- 文档列表：白底圆角 12px、逐行细分隔线、hover #fafafa。
- 泳道：每道 = grid 96px 标签 + 自适应卡片流；卡片定宽 178px、横向滚动（4px 细滚动条）；
  状态道左标签带状态色点（in_progress 蓝/integrating 紫/testing 橙/in_review 品红/done 绿）。

## 依赖与第三方库 <!-- serves: FR-1 -->

零新增裸包依赖（client 自包含约束不破）。React 既有；无 Alpine（设计稿的 Alpine 仅演示用，插件用 React 壳 + 纯字符串渲染）。
