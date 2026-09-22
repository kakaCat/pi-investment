---
requirement_refs: [FR-4]
---

# 前端设计（REQ-example）

> 示例说明：REQ-example 的 sides=backend（本份实际不交，见 requirement front-matter
> 的 design_exempt）。本范例假设 sides 含 frontend 的假想变体——
> 看板需求详情页加「模板预览」区块，演示本模板怎么填。

## 原型页面 <!-- serves: FR-4 -->

（prototypes/template-preview.html：单栏布局，上=文档清单，下=选中文档的骨架预览。）

## 目录与包结构 <!-- serves: FR-4 -->

```
packages/web/dsh-pmboard/src/
├── client/
│   └── views/         （本需求改动：RequirementDetail.vue 挂预览区块）
│   └── components/    （本需求新增：TemplatePreviewPanel.vue）
└── application/       （既有，不改）
```

| 路径 | 内容 | 新增/改动 | 落此处的理由 |
|---|---|---|---|
| client/components/TemplatePreviewPanel.vue | 预览面板组件 | 新增 | 可复用展示组件归 components/ |
| client/views/RequirementDetail.vue | 需求详情页挂载点 | 改动 | 页面级归属 views/，与既有结构一致 |

## 组件结构 <!-- serves: FR-4 -->

```
需求详情页（既有）
├── 基本信息区（既有）
└── 模板预览区（新增）
    ├── 文档清单列表（新增）
    └── 骨架预览面板（新增）
```

## 页面与组件 <!-- serves: FR-4 -->

| 编号 | 类型 | 名称 | 职责 | 数据来源 | 新增/改动 |
|---|---|---|---|---|---|
| P-1 | 页面 | 需求详情页 | 模板预览区的挂载点 | — | 改动 |
| C-1 | 组件 | 文档清单列表 | 列出本类型会落盘的文档及落盘状态 | host 文件服务接口 | 新增 |
| C-2 | 组件 | 骨架预览面板 | 渲染选中骨架的 markdown | host 文件服务接口 | 新增 |

## 状态与数据流 <!-- serves: FR-4 -->

需求 id → 查产物登记（kind=template_skeleton）→ 逐个取文件内容 → 渲染。

## 样式与风格 <!-- serves: FR-4 -->

| 项 | 取值 | 来源/理由 |
|---|---|---|
| 设计体系 | 沿用 dsh-pmboard 看板既有组件与宿主主题 token | 同一插件内不另立风格 |
| 布局 | 详情页右侧抽屉（宽 480px），清单上/预览下两栏 | 与既有「任务详情抽屉」同构 |
| 色彩与字体 | 全部用宿主 CSS 变量（--dsh-bg / --dsh-fg / --dsh-border），新增色值 = 0 | 主题一致性 |
| 响应式 | 不适配窄屏（<768px 抽屉改全屏遮罩） | 内部工具页，桌面为主 |
| 暗黑/主题 | 跟随宿主主题切换（只用 CSS 变量即自动满足） | 零额外成本 |
| 样式落点 | TemplatePreviewPanel.vue 的 scoped style，不加公共 css 文件 | 单组件样式不外溢 |

## 交互与异常态 <!-- serves: FR-4 -->

| 状态 | UI 表现 | 用户可做什么 | 触发条件 |
|---|---|---|---|
| 成功 | 清单+预览正常渲染 | 切换文档查看 | 产物已登记 |
| 加载中 | 骨架屏 | 等待 | 接口请求中 |
| 空态 | 「该节点暂无模板骨架」+ 说明文案 | 返回 | 未落盘（被幂等跳过/降级） |
| 报错态 | 错误提示 + 重试按钮 | 重试 | 接口 5xx / 超时 |
