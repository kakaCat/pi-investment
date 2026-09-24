---
requirement_refs: [FR-2, FR-3]
---

# 前端设计（REQ-example）

## 原型页面 <!-- serves: FR-2 -->

原型文件：`prototypes/template-preview.html`

**原型说明**：
- 点击需求详情页的"文档"标签 → 展示文档清单
- 文档清单中，已生成的模板显示绿色"已生成"标签
- 点击文档名 → 弹出预览弹窗，展示模板 markdown 内容
- 预览弹窗支持全屏/关闭操作

**交互路径**：
1. 用户进入需求详情页 → 右侧显示"文档"标签（默认展开）
2. 用户点击"文档"标签 → 展示文档清单（requirement.md / frontend.md 等）
3. 用户点击 requirement.md → 弹出预览弹窗
4. 预览弹窗显示 markdown 渲染后的内容（标题/章节/填写提示）
5. 用户点击"全屏"按钮 → 弹窗全屏展示
6. 用户点击"关闭"按钮或按 Esc 键 → 弹窗关闭

## 目录与包结构 <!-- serves: FR-2 -->

```
packages/web/dsh-pmboard/src/
├── components/
│   ├── TemplatePreview.vue      （新增）
│   └── DocumentList.vue          （改动）
├── api/
│   └── templates.ts              （新增）
└── views/
    └── RequirementDetail.vue     （改动）
```

| 路径（完整相对路径） | 内容（文件名+一句话职责） | 新增/改动 | 落此处的理由（为什么不放别处） |
|---|---|---|---|
| packages/web/dsh-pmboard/src/components/TemplatePreview.vue | 模板预览弹窗组件：展示模板 markdown 内容，支持全屏/关闭 | 新增 | pmboard 专有功能，不跨插件复用，故放 pmboard 包内 |
| packages/web/dsh-pmboard/src/components/DocumentList.vue | 文档清单组件：展示 artifacts 列表，增加"已生成"标签展示 | 改动 | 既有组件，本次新增模板状态展示逻辑 |
| packages/web/dsh-pmboard/src/api/templates.ts | 模板接口封装：调用 GET /api/templates/:key | 新增 | 接口层独立文件，方便复用和 mock |
| packages/web/dsh-pmboard/src/views/RequirementDetail.vue | 需求详情页：集成文档清单和预览弹窗 | 改动 | 既有页面，本次新增预览弹窗集成 |

## 组件结构 <!-- serves: FR-2 -->

```
P-1 需求详情页 RequirementDetail.vue（展示需求全文 + 文档清单 + 预览弹窗）
  ├── C-1 文档清单 DocumentList（展示 artifacts，Props: artifacts[]）
  │   ├── → 点击文档时 emit('preview', artifact)
  │   └── 每个文档显示：文件名 + 状态标签（已生成/待提交/已归档）
  └── C-2 模板预览弹窗 TemplatePreview（展示模板内容，Props: visible, templateKey）
      ├── ← 关闭时 emit('close')
      ├── 内部组件：markdown 渲染器（使用 marked 库）
      └── 操作按钮：全屏 / 关闭
```

## 页面与组件（编号表） <!-- serves: FR-3 -->

| 编号 | 类型 | 名称 | 职责（动宾结构，含响应操作） | 数据来源（接口/状态/Props） | 新增/改动 | serves |
|---|---|---|---|---|---|---|
| P-1 | 页面 | 需求详情页 RequirementDetail | 展示需求全文 + 产物清单（含模板骨架登记），点击产物弹出预览 | GET /api/requirements/:id + GET /api/requirements/:id/artifacts | 改动 | FR-3 |
| C-1 | 组件 | 文档清单 DocumentList | 展示需求目录内文档树（含新产物 kind 图标：template_skeleton=绿色"已生成"），点击文档 emit preview 事件 | props.artifacts (Array<Artifact>) | 改动 | FR-3 |
| C-2 | 组件 | 骨架预览面板 TemplatePreview | 点击产物后弹出 markdown 预览，调用 GET /api/templates/:key 获取模板全文并渲染 | host 接口 GET /api/templates/:key | 新增 | FR-2 |

## 状态管理 <!-- serves: FR-2 -->

**全局状态（Vuex store）**：
- `currentRequirement`（对象）：当前打开的需求对象（id/title/status/artifacts）
  - 更新时机：进入需求详情页时调用 GET /api/requirements/:id 加载
  - 读取组件：P-1 / C-1 / C-2
  - 为什么全局：多个组件需要读取需求信息，避免重复请求

**组件状态（C-2 内部）**：
- `previewVisible`（boolean）：预览弹窗显隐状态
  - 更新时机：用户点击文档时置 true，点击关闭按钮或按 Esc 时置 false
  - 为什么组件级：仅 C-2 内部使用，关闭页面即销毁，不需要跨组件共享
- `templateContent`（string）：模板内容
  - 更新时机：弹窗打开时调用 GET /api/templates/:key 加载
  - 为什么组件级：每次打开弹窗重新拉取（模板可能更新），不缓存
- `isFullscreen`（boolean）：是否全屏
  - 更新时机：用户点击"全屏"按钮时切换
  - 为什么组件级：UI 状态，不影响其他组件

## 路由与导航 <!-- serves: FR-2 -->

**本需求不新增路由**，复用既有需求详情页路由：

```js
{
  path: '/pmboard/requirements/:id',
  component: RequirementDetail,
  meta: {
    title: '需求详情',
    requiresAuth: true,
    breadcrumb: ['项目看板', '需求列表', '详情']
  }
}
```

**导航变化**：
- 用户点击文档清单中的文档 → 不跳转页面，弹出预览弹窗（在当前页面 overlay）
- 预览弹窗关闭 → 回到需求详情页（不改变 URL）

## 样式与主题 <!-- serves: FR-2 -->

**新增 CSS 变量**：
- `--template-preview-width: 800px`（预览弹窗默认宽度）
- `--template-preview-max-height: 80vh`（预览弹窗最大高度，避免超出屏幕）
- `--doc-status-badge-green: #52c41a`（"已生成"标签颜色）

**响应式设计**：
- `< 768px`（移动端）：预览弹窗改为全屏（width: 100vw, height: 100vh）
- `>= 768px`（桌面端）：预览弹窗居中浮层（width: 800px, max-height: 80vh）

**主题适配**：
- 暗色主题：弹窗背景色 `var(--background-dark)`，markdown 代码块使用 `github-dark` 主题

## 依赖与第三方库 <!-- serves: FR-2 -->

| 包名 | 版本 | 用途 | 选型理由（为什么不用 A 而用 B） |
|---|---|---|---|
| marked | ^4.3.0 | markdown 渲染 | 体积小（gzip 后 20KB），支持 GFM 语法，性能好（1000 行 markdown 渲染 < 50ms）。不用 markdown-it：体积大（gzip 后 80KB）且我们不需要插件扩展 |
| DOMPurify | ^3.0.0 | markdown 渲染后的 XSS 防护 | 行业标准，支持白名单配置，可拦截 `<script>` / `onerror` 等注入。不用 sanitize-html：配置复杂且体积更大 |
| @vueuse/core | ^10.0.0 | useEventListener（监听 Esc 键关闭弹窗） | Vue 3 官方推荐的 composition 工具库，tree-shakable，只引入用到的函数 |
