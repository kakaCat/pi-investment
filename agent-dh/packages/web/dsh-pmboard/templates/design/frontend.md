---
requirement_refs: [FR-1]
---

# 前端设计（{{REQ_ID}}）

> 条件必交：requirement.md front-matter sides 含 frontend 时要求本份；不含则不交。
> 本文档面向：前端开发、UI 设计、测试——写清楚页面结构、组件职责、数据流。

## 原型页面 <!-- serves: FR-1 -->

（可视化原型：`prototypes/<name>.html`（由 prototype.html 模板生成，每功能点一个锚点区块）；
截图贴本目录。原型讲结构与交互路径，不求视觉精细；定稿后换正式交互稿。

**填写要求**：
- 原型必须**可点击操作**，不是静态截图拼接
- 标注**交互路径**：点什么 → 发生什么 → 跳转哪里
- 标注**关键元素**：按钮、表单、弹窗的触发条件

**文件命名**：prototypes/需求简称.html，如 prototypes/template-landing.html）

## 目录与包结构 <!-- serves: FR-1 -->

（文件落在哪个包/目录：新增文件的路径、目录划分理由——
组件树讲逻辑结构，本节讲物理落点。

**填写要求**：
- 路径写**完整相对路径**：packages/web/dsh-pmboard/src/components/TemplatePreview.vue
- "落此处的理由"必须回答：为什么不放其他包/目录？（复用边界、职责归属）

**示范**：
- ❌ 错误："新增组件"（没说在哪）
- ✅ 正确："packages/web/dsh-pmboard/src/components/TemplatePreview.vue
  理由：模板预览是 pmboard 专有功能，不复用到其他插件，故放 pmboard 包内"）

```
packages/web/<pkg>/src/
├── components/        （本需求新增：XxxPanel.vue）
├── views/             （既有，不改）
└── api/               （本需求改动：yyy.ts）
```

| 路径（完整相对路径） | 内容（文件名+一句话职责） | 新增/改动 | 落此处的理由（为什么不放别处） |
|---|---|---|---|
| packages/web/dsh-pmboard/src/components/TemplatePreview.vue | 模板预览弹窗组件 | 新增 | pmboard 专有，不跨插件复用 |

## 组件结构 <!-- serves: FR-1 -->

（ASCII 组件树：页面 → 容器 → 子组件，展示层级关系与数据流向。

**填写要求**：
- 树不能只有名字，每个组件后面**括号注职责**
- 用箭头标注**数据流向**：→（props 下传）/ ←（emit 上报）/ ↔（双向绑定）
- 标注**关键 Props 和 Events**

**示范**：
```
P-1 需求详情页（展示需求全文+产物清单）
├── C-1 文档清单组件（展示 artifacts，Props: artifacts[]）
│   └── → 点击文档时 emit('preview', artifact_id)
└── C-2 模板预览弹窗（展示模板内容，Props: visible, template_key）
    └── ← 关闭时 emit('close')
```）

```
P-1 页面名（职责）
├── C-1 组件名（职责）
│   └── C-1-1 子组件（职责）
└── C-2 组件名（职责）
```

## 页面与组件（编号表） <!-- serves: FR-1 -->

（每个页面/组件一行，P-x = 页面，C-x = 组件。编号用于 test-cases 的"被测对象"引用。

**"职责"列填写要求**：
- 不是一个词，是**一句话动宾结构**："展示什么 + 响应什么操作"
- ❌ 错误："文档列表"
- ✅ 正确："展示需求目录内的文档清单，点击文档弹出预览"

**"数据来源"列填写要求**：
- 写清楚**接口路径 / Vuex 状态 / Props 来源**
- 示范：GET /api/requirements/:id/artifacts / props.artifacts / store.state.currentReq）

| 编号 | 类型 | 名称 | 职责（动宾结构，含响应操作） | 数据来源（接口/状态/Props） | 新增/改动 | serves |
|---|---|---|---|---|---|---|
| P-1 | 页面 | 需求详情页 | 展示需求全文 + 文档清单，点击文档弹出预览 | GET /api/requirements/:id | 改动 | FR-1 |
| C-1 | 组件 | 文档清单 | 展示 artifacts 列表，支持筛选与排序 | props.artifacts | 新增 | FR-1 |

## 状态管理 <!-- serves: FR-1 -->

（哪些数据放 Vuex / Pinia，哪些用组件内 data——状态共享边界。

**填写要求**：
- 全局状态：写清楚**状态名 + 更新时机 + 哪些组件读**
- 组件状态：写清楚为什么不提升为全局（生命周期、复用边界）

**示范**：
- 全局状态 currentRequirement：当前打开的需求对象，进入详情页时加载，
  P-1/C-1/C-2 三个组件都读它
- 组件状态 previewVisible（C-2）：预览弹窗显隐，仅 C-2 内部使用，关闭页面即销毁，
  不需要跨组件共享）

## 路由与导航 <!-- serves: FR-1 -->

（新增/改动的路由，权限控制。

**填写要求**：
- 路由路径写**完整**：/pmboard/requirements/:id/artifacts
- meta 字段写清楚：title（页面标题）/ requiresAuth（是否需要登录）/ breadcrumb（面包屑）

**示范**：
```js
{
  path: '/pmboard/requirements/:id/artifacts',
  component: RequirementDetail,
  meta: {
    title: '需求详情',
    requiresAuth: true,
    breadcrumb: ['项目看板', '需求列表', '详情']
  }
}
```）

## 样式与主题 <!-- serves: FR-1 -->

（新增的样式变量、主题适配、响应式断点。

**填写要求**：
- CSS 变量写清楚**用途 + 取值**
- 响应式断点写清楚**屏幕宽度 + 布局变化**

**示范**：
- 新增 CSS 变量 --template-preview-width: 800px（预览弹窗默认宽度）
- 响应式：< 768px 时预览弹窗改为全屏（移动端））

## 依赖与第三方库 <!-- serves: FR-1 -->

（新增的 npm 包、为什么选它、版本约束。

**填写要求**：
- 包名 + 版本 + 用途 + 选型理由（为什么不用 A 而用 B）

**示范**：
- marked@^4.0.0：markdown 渲染，选它因为体积小（50KB）且支持 GFM 语法
- 不用 markdown-it：体积大（200KB）且我们不需要插件扩展）
