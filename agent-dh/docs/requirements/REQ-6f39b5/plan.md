# REQ-6f39b5 技术设计与实施计划

**需求**：项目看板需求详情页界面优化  
**当前阶段**：planning（技术设计）  
**上游需求文档**：[requirement.md](./requirement.md)

---

## 1. 技术设计概览

### 1.1 核心目标

优化需求详情页的信息架构，解决当前存在的问题：
- ❌ **功能重复**：8 个节点导航按钮 + 折叠区域，功能重叠
- ❌ **信息过载**：11 个折叠区默认混在一起，找信息费力
- ❌ **层级混乱**：监控信息（进度条）埋在折叠区底部

### 1.2 解决方案

**采用 4 Tab 分组 + 8 态进度点**架构：

```
┌─────────────────────────────────────────────────┐
│  头部：ID、状态、窗口、更新时间、操作按钮       │
├─────────────────────────────────────────────────┤
│  8 态进度点：立项 → 需求分析 → 技术设计 →       │
│             拆分 → 实施 → 验收 → 完成 → 归档    │
├─────────────────────────────────────────────────┤
│  Tab 导航：📋 概览 | ⚙️ 执行 | 📅 时间线 | 📦 归档 │
├─────────────────────────────────────────────────┤
│  Tab 内容区（动态切换）                         │
│  - 概览：需求描述、文档记录、当前阶段详情      │
│  - 执行：任务 DAG、任务列表、甘特图             │
│  - 时间线：状态变更记录、评论                  │
│  - 归档：归档材料、合并去向                    │
└─────────────────────────────────────────────────┘
```

---


## 2. 现有代码结构

### 2.1 目录树

```
packages/pages/dsh-pmboard/
├── package.json              # 插件配置
├── tsdown.client.config.ts   # 客户端构建配置
├── scripts/
│   ├── wrap-client.mjs       # 客户端打包包装
│   └── verify-client-build.mjs  # 构建验证
├── src/
│   ├── index.ts              # 服务端入口（cordis 插件）
│   ├── shared/
│   │   └── protocol.ts       # 🔑 共享协议（状态机、闸门规则）
│   ├── host/                 # 服务端逻辑
│   │   ├── store.ts          # 数据存储
│   │   ├── routes.ts         # HTTP 路由
│   │   ├── agent-tools.ts    # Agent 工具注册
│   │   ├── rollup.ts         # 状态自动推进
│   │   ├── artifact-gates.ts # 人工闸门
│   │   ├── stage-prompts.ts  # 阶段提示词
│   │   └── ...
│   └── client/               # 🎯 客户端渲染（本次改造重点）
│       ├── view.ts           # 🔑 视图渲染（buildReqDetail 在这里）
│       ├── styles.ts         # 🔑 样式定义
│       ├── dom.ts            # DOM 事件绑定
│       ├── api.ts            # 客户端 API 调用
│       ├── stage-panel.ts    # 阶段面板
│       └── ...
└── lib/
    └── client.js             # 构建产物（浏览器加载）
```

### 2.2 关键文件说明

#### 🔑 `src/shared/protocol.ts`
- **作用**：定义需求/任务状态机、闸门规则、DAG 校验
- **本次影响**：无需修改（状态定义保持不变）
- **包含**：
  - `RequirementStatus`：7 个需求主态（draft/brainstorming/planning/...）
  - `TaskStatus`：6 个任务主态（todo/in_progress/...）
  - `REQUIREMENT_TRANSITIONS`：状态转移规则
  - `HUMAN_GATES`：人工闸门定义

#### 🔑 `src/client/view.ts`（本次改造核心）
- **作用**：数据 → HTML 的纯渲染函数
- **关键函数**：
  - `buildReqDetail(req, tasks, ...): string` - 需求详情页主渲染函数
  - `buildDag(tasks): string` - 任务 DAG 渲染
  - `buildTaskColumns(tasks): string` - 任务列表渲染
  - `renderComments(comments): string` - 评论渲染
- **本次改造**：
  - ✅ 删除 8 个节点导航按钮
  - ✅ 删除 11 个折叠区统一容器
  - ✅ 新增 `buildProgressDots()`
  - ✅ 新增 `buildTabs()`
  - ✅ 新增 `buildTabContents()`

#### 🔑 `src/client/styles.ts`（本次改造样式）
- **作用**：CSS 样式字符串（构建时注入 HTML）
- **本次新增样式**：
  - `.dsh-pm-progress-dots` - 8 态进度点容器
  - `.dsh-pm-dot` / `.dsh-pm-dot-wrapper` - 进度点样式
  - `.dsh-pm-tabs` - Tab 导航栏
  - `.dsh-pm-tab` - 单个 Tab 按钮
  - `.dsh-pm-tab-content` - Tab 内容区

#### 🎯 `src/client/workflow-constants.ts`（本次新建）
- **作用**：流程节点定义常量（对接唯一事实源）
- **导出**：
  - `WORKFLOW_STAGES`：7 个流程节点（label/color/order）
  - `PROGRESS_DOT_STAGES`：8 态进度点顺序
  - `LANE_STAGES`：6 个泳道顺序
- **引用规范**：所有流程节点名必须从这里引用，禁止硬编码

#### `src/client/dom.ts`
- **作用**：客户端事件绑定
- **本次新增**：Tab 切换事件监听

### 2.3 构建流程

```bash
# 1. TypeScript 编译（tsdown）
tsdown -c tsdown.client.config.ts
# 产物：lib/client.js

# 2. 包装（wrap-client.mjs）
# 添加 UMD 包装、polyfill 注入

# 3. 验证（verify-client-build.mjs）
# 检查构建产物完整性
```

### 2.4 数据流

```
服务端（host/routes.ts）
  ↓ HTTP API
前端浏览器加载（lib/client.js）
  ↓ 调用 api.ts
获取需求/任务数据
  ↓ 传入 view.ts
buildReqDetail() 渲染 HTML
  ↓ 注入到 DOM
用户交互（dom.ts 事件绑定）
  ↓ 调用 api.ts
触发服务端状态变更
  ↓ 更新数据
重新渲染
```

---

## 8. 四视角技术设计

### 7.1 UI 视角

#### 2.1.1 组件结构变化

**删除**：
- ❌ `.dsh-pm-stage-nav`（8 个节点导航按钮）
- ❌ 11 个 `<details>` 折叠区统一容器

**新增**：
- ✅ `.dsh-pm-progress-dots`（8 态进度点）
- ✅ `.dsh-pm-tabs`（4 个 Tab 按钮）
- ✅ `.dsh-pm-tab-content`（4 个内容区）

#### 2.1.2 Tab 内容分组

| Tab | 显示内容 | 数据来源 |
|-----|---------|---------|
| 📋 概览 | 需求描述、文档记录、当前阶段详情 | `req.description`, `renderDocSection()`, `renderStageDetail()` |
| ⚙️ 执行 | 任务 DAG、任务列表、甘特图 | `buildDag()`, `buildTaskColumns()`, `buildGantt()` |
| 📅 时间线 | 状态变更、评论 | `renderReqTimeline()`, `renderComments()` |
| 📦 归档 | 归档材料、合并去向 | `renderArchiveSection()` |

#### 2.1.3 8 态进度点设计

```html
<div class="dsh-pm-progress-dots">
  <div class="dsh-pm-dot-wrapper completed">
    <div class="dsh-pm-dot"></div>
    <span class="dsh-pm-dot-label">立项</span>
  </div>
  <!-- 当前态：current class -->
  <div class="dsh-pm-dot-wrapper current">
    <div class="dsh-pm-dot"></div>
    <span class="dsh-pm-dot-label">实施</span>
  </div>
  <!-- 未来态：默认灰色 -->
  <div class="dsh-pm-dot-wrapper">
    <div class="dsh-pm-dot"></div>
    <span class="dsh-pm-dot-label">验收</span>
  </div>
</div>
```

**状态映射逻辑**（workflow-stages.md 定义）：
- `completed`：status < 当前态
- `current`：status === 当前态
- 默认：status > 当前态

---

### 7.2 前端视角

#### 2.2.1 常量文件（新建）

**`src/client/workflow-constants.ts`**

```typescript
/**
 * 流程节点定义（唯一事实源对应前端实现）
 * 权威定义：docs/architecture/workflow-stages.md
 */

export const WORKFLOW_STAGES = {
  draft: { label: '立项', color: '#9aa4b2', order: 0 },
  brainstorming: { label: '需求分析', color: '#f0a020', order: 1 },
  planning: { label: '技术设计', color: '#c2255c', order: 2 },
  decomposing: { label: '拆分', color: '#8e44ad', order: 3 },
  implementing: { label: '实施', color: '#4a7dff', order: 4 },
  accepting: { label: '验收', color: '#17a2b8', order: 5 },
  done: { label: '完成', color: '#28a745', order: 6 },
  archived: { label: '归档', color: '#28a745', order: 7 }
} as const

export type WorkflowStage = keyof typeof WORKFLOW_STAGES

/** 8 态进度点顺序（含过渡态 done） */
export const PROGRESS_DOT_STAGES: readonly WorkflowStage[] = [
  'draft', 'brainstorming', 'planning', 'decomposing',
  'implementing', 'accepting', 'done', 'archived'
] as const

/** 6 个泳道（不含归档、取消） */
export const LANE_STAGES: readonly WorkflowStage[] = [
  'draft', 'brainstorming', 'planning',
  'decomposing', 'implementing', 'accepting'
] as const
```

#### 2.2.2 核心函数改造

**`src/client/view.ts` 中的 `buildReqDetail()`**

改造点：
1. **删除** `<div class="dsh-pm-stage-nav">` 的 8 个按钮
2. **新增** `buildProgressDots(req.status)` 渲染 8 态进度点
3. **删除** 11 个 `<details>` 的平铺结构
4. **新增** `buildTabContent(req, tasks, ...)` 渲染 4 个 Tab

伪代码：
```typescript
export function buildReqDetail(req: RequirementRecord, tasks: TaskRecord[], ...): string {
  const progressDots = buildProgressDots(req.status)
  const tabs = buildTabs()
  const tabContents = buildTabContents(req, tasks, ...)
  
  return `
    <div class="dsh-pm-detail">
      <div class="dsh-pm-detail-head">...</div>
      ${actionBar}
      ${gateHint}
      ${progressDots}  <!-- 新增 -->
      ${tabs}          <!-- 新增 -->
      ${tabContents}   <!-- 新增 -->
    </div>`
}
```

#### 2.2.3 新增渲染函数

**`buildProgressDots(currentStatus: RequirementStatus): string`**
- 遍历 `PROGRESS_DOT_STAGES`
- 根据 `order` 判断 completed / current / 默认
- 返回 HTML 字符串

**`buildTabs(): string`**
- 渲染 4 个 Tab 按钮（概览默认 active）

**`buildTabContents(req, tasks, ...): string`**
- 调用现有函数组装 4 个 Tab 内容区
- 概览 Tab 默认显示（`display: block`）

#### 2.2.4 交互逻辑

**Tab 切换**（`src/client/dom.ts`）

```typescript
// 监听 Tab 按钮点击
container.addEventListener('click', e => {
  const tab = (e.target as HTMLElement).closest('[data-tab]')
  if (!tab) return
  
  const tabName = tab.getAttribute('data-tab')
  
  // 切换 active 状态
  container.querySelectorAll('.dsh-pm-tab').forEach(t => t.classList.remove('active'))
  tab.classList.add('active')
  
  // 切换内容区
  container.querySelectorAll('.dsh-pm-tab-content').forEach(c => c.style.display = 'none')
  const content = container.querySelector(`[data-tab-content="${tabName}"]`)
  if (content) (content as HTMLElement).style.display = 'block'
})
```

---

### 3.3 后端视角

#### 2.3.1 API 兼容性

**无需后端改动**：
- 本次优化纯前端 UI 重构
- 后端 API 状态字段保持不变（`draft` / `brainstorming` / `planning` 等）
- 前端通过 `workflow-constants.ts` 做状态映射

#### 2.3.2 状态映射规则

| 后端状态 | 前端显示 | 说明 |
|---------|---------|------|
| `draft` | 立项 | - |
| `brainstorming` | 需求分析 | 旧名"头脑风暴" |
| `planning` | 技术设计 | 旧名"计划" |
| `decomposing` | 拆分 | - |
| `implementing` | 实施 | 旧名"执行" |
| `accepting` | 验收 | - |
| `done` | 完成 | 过渡态 |
| `archived` | 归档 | 最终态 |

---

### 3.4 测试视角

#### 2.4.1 功能测试

| 测试项 | 步骤 | 预期结果 |
|-------|------|---------|
| 8 态进度点显示 | 打开不同状态的需求详情 | 进度点正确高亮当前态 |
| Tab 切换 | 点击 4 个 Tab | 内容区正确切换，无闪烁 |
| 内容完整性 | 检查 4 个 Tab 内容 | 所有原折叠区内容都能找到 |
| 响应式 | 缩小浏览器窗口 | 进度点/Tab 自适应 |

#### 2.4.2 兼容性测试

| 测试项 | 验证点 |
|-------|-------|
| 后端状态映射 | `brainstorming` → "需求分析" |
| 旧代码调用 | `buildReqDetail()` 签名不变，旧调用点无需改动 |
| 样式不冲突 | 新 class 不影响其他页面 |

#### 2.4.3 性能测试

| 指标 | 目标 |
|------|------|
| 详情页渲染时间 | < 100ms（100 个任务） |
| Tab 切换响应 | < 50ms |
| 内存占用 | 无明显增长 |

---

## 8. 任务拆解与 DAG

### 7.1 任务列表

| Key | 标题 | Phase | Side | Depends On | Acceptance |
|-----|------|-------|------|------------|------------|
| t-001 | 创建 workflow-constants.ts | implement | frontend | - | 文件存在，导出 WORKFLOW_STAGES / PROGRESS_DOT_STAGES / LANE_STAGES |
| t-002 | 实现 buildProgressDots() | implement | frontend | t-001 | 函数存在，返回 HTML 包含 8 个进度点 |
| t-003 | 实现 buildTabs() | implement | frontend | - | 函数存在，返回 4 个 Tab 按钮 HTML |
| t-004 | 实现 buildTabContents() | implement | frontend | t-003 | 函数存在，返回 4 个 Tab 内容区 HTML |
| t-005 | 重写 buildReqDetail() | implement | frontend | t-002, t-003, t-004 | 删除节点导航和折叠区，集成新组件 |
| t-006 | 实现 Tab 切换交互 | implement | frontend | t-005 | 点击 Tab 正确切换内容区 |
| t-007 | 添加样式（进度点 + Tab） | implement | frontend | t-006 | 样式文件更新，视觉对齐原型 |
| t-008 | 适配泳道图与列表视图 | implement | frontend | t-001 | 泳道图/列表视图引用 workflow-constants，显示正确 |
| t-009 | 功能测试 | test | fullstack | t-008 | 测试清单全部通过 |
| t-010 | 文档更新 | doc | doc | t-009 | README 补充 Tab 使用说明 |

### 7.2 DAG 可视化

```
L0:  t-001  t-003
      ↓      ↓
L1:  t-002  t-004
      ↓  ↙
L2:  t-005
       ↓
L3:  t-006
       ↓
L4:  t-007
       ↓
L5:  t-008
       ↓
L6:  t-009
       ↓
L7:  t-010
```

### 3.3 关键路径

**t-001 → t-002 → t-005 → t-006 → t-007 → t-008 → t-009 → t-010**

预计工期：**3-4 天**

---

## 8. 风险与应对

### 7.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 删除折叠区导致功能丢失 | 高 | 中 | t-004 完成后人工对照检查，确保所有内容都映射到 Tab |
| Tab 切换性能问题 | 中 | 低 | 使用 CSS display 而非 DOM 销毁重建 |
| 旧代码调用点断裂 | 高 | 低 | buildReqDetail() 签名保持不变 |

### 7.2 兼容性风险

| 风险 | 应对 |
|------|------|
| 后端状态名未来变更 | workflow-constants.ts 集中管理，只需改一处 |
| 其他页面样式冲突 | 使用 `.dsh-pm-` 前缀，作用域隔离 |

---

## 8. 验收标准

### 7.1 功能验收

- ✅ 详情页包含 8 态进度点，当前态正确高亮
- ✅ 4 个 Tab 可正常切换，内容完整无遗漏
- ✅ 删除了 8 个节点导航按钮和 11 个折叠区
- ✅ 泳道图/列表视图流程节点名称对齐

### 7.2 代码质量

- ✅ workflow-constants.ts 包含注释，引用权威定义
- ✅ 所有新函数有 JSDoc 注释
- ✅ 无 ESLint 错误
- ✅ 无硬编码流程节点名（必须引用常量）

### 7.3 测试覆盖

- ✅ 功能测试清单全部通过
- ✅ 兼容性测试无回归
- ✅ 性能指标达标

---

## 8. 部署计划

### 7.1 构建

```bash
cd packages/pages/dsh-pmboard
pnpm build:client
pnpm verify:client
```

### 7.2 验证

1. 启动 DSH :13080
2. 打开任意需求详情页
3. 检查 8 态进度点 + 4 Tab 是否正常
4. 切换不同状态的需求验证进度点高亮

### 7.3 回滚预案

如果发现严重问题：
```bash
git revert <commit-hash>
pnpm build:client
# 重启 DSH
```

---

## 8. 参考文档

- **唯一事实源**：[docs/architecture/workflow-stages.md](../../architecture/workflow-stages.md)
- **需求文档**：[requirement.md](./requirement.md)
- **原型**：[prototype.html](./prototype.html) / [lanes-prototype.html](./lanes-prototype.html) / [list-prototype.html](./list-prototype.html)
- **RFC 014**：[014-requirement-board.md](../../rfcs/014-requirement-board.md)

---

**编写时间**：2026-09-16  
**负责人**：w-b8de6c05  

## 3.5 本次改造代码清单

### 📁 需要修改的文件

```
packages/pages/dsh-pmboard/src/client/
├── view.ts                    # 🔧 修改（核心）
│   ├── buildReqDetail()       #   - 删除：8 个节点导航按钮
│   │                          #   - 删除：11 个折叠区统一容器
│   │                          #   - 新增：调用 buildProgressDots()
│   │                          #   - 新增：调用 buildTabs()
│   │                          #   - 新增：调用 buildTabContents()
│   ├── buildProgressDots()    #   - 新增函数
│   ├── buildTabs()            #   - 新增函数
│   └── buildTabContents()     #   - 新增函数
│
├── styles.ts                  # 🔧 修改
│   ├── .dsh-pm-progress-dots  #   - 新增样式：8 态进度点容器
│   ├── .dsh-pm-dot            #   - 新增样式：进度点圆形
│   ├── .dsh-pm-dot-wrapper    #   - 新增样式：进度点包装器
│   ├── .dsh-pm-tabs           #   - 新增样式：Tab 导航栏
│   ├── .dsh-pm-tab            #   - 新增样式：Tab 按钮
│   └── .dsh-pm-tab-content    #   - 新增样式：Tab 内容区
│
├── dom.ts                     # 🔧 修改
│   └── Tab 切换事件监听        #   - 新增：监听 .dsh-pm-tab 点击
│
└── workflow-constants.ts      # ✨ 新建文件
    ├── WORKFLOW_STAGES        #   - 导出：7 个流程节点定义
    ├── PROGRESS_DOT_STAGES    #   - 导出：8 态进度点顺序
    └── LANE_STAGES            #   - 导出：6 个泳道顺序
```

### 📁 不需要修改的文件

```
packages/pages/dsh-pmboard/src/
├── shared/
│   └── protocol.ts            # ✅ 保持不变（状态定义不变）
├── host/
│   ├── routes.ts              # ✅ 保持不变（API 不变）
│   ├── store.ts               # ✅ 保持不变（数据模型不变）
│   └── ...                    # ✅ 所有服务端文件都不变
└── client/
    ├── api.ts                 # ✅ 保持不变（API 调用不变）
    ├── stage-panel.ts         # ✅ 保持不变
    └── ...                    # ✅ 其他渲染辅助函数不变
```

### 📊 改动统计

| 操作 | 文件数 | 说明 |
|------|--------|------|
| ✨ 新建 | 1 | workflow-constants.ts |
| 🔧 修改 | 3 | view.ts, styles.ts, dom.ts |
| ✅ 不变 | 15+ | 所有服务端文件 + 其他客户端文件 |

### 🎯 改动热点（代码行数估算）

| 文件 | 新增行数 | 删除行数 | 净增减 |
|------|---------|---------|--------|
| workflow-constants.ts | ~50 | 0 | +50 |
| view.ts | ~150 | ~80 | +70 |
| styles.ts | ~120 | 0 | +120 |
| dom.ts | ~30 | 0 | +30 |
| **合计** | **~350** | **~80** | **+270** |

### 📝 详细改动清单

#### 1️⃣ workflow-constants.ts（新建，~50 行）

```typescript
/**
 * 流程节点定义常量
 * 权威定义：docs/architecture/workflow-stages.md
 */

export const WORKFLOW_STAGES = {
  draft: { label: '立项', color: '#9aa4b2', order: 0 },
  brainstorming: { label: '需求分析', color: '#f0a020', order: 1 },
  planning: { label: '技术设计', color: '#c2255c', order: 2 },
  decomposing: { label: '拆分', color: '#8e44ad', order: 3 },
  implementing: { label: '实施', color: '#4a7dff', order: 4 },
  accepting: { label: '验收', color: '#17a2b8', order: 5 },
  done: { label: '完成', color: '#28a745', order: 6 },
  archived: { label: '归档', color: '#28a745', order: 7 }
} as const

export type WorkflowStage = keyof typeof WORKFLOW_STAGES

export const PROGRESS_DOT_STAGES: readonly WorkflowStage[] = [
  'draft', 'brainstorming', 'planning', 'decomposing',
  'implementing', 'accepting', 'done', 'archived'
] as const

export const LANE_STAGES: readonly WorkflowStage[] = [
  'draft', 'brainstorming', 'planning',
  'decomposing', 'implementing', 'accepting'
] as const
```


### 🔑 改造策略：更新而非删除

**现有代码结构**（第 804-850 行）：
```typescript
// 第 804-806 行：8 个节点导航按钮
<div class="dsh-pm-stage-nav" id="dsh-pm-stage-nav">
  ${ALL_STAGE_KEYS.map(s => `<button ...>${STAGE_LABELS[s]}</button>`).join('')}
</div>

// 第 807 行：阶段详情容器（动态加载）
<div class="dsh-pm-stage-detail" id="dsh-pm-stage-detail-container"></div>

// 第 808-850+ 行：11 个折叠区（<details>）
<details class="dsh-pm-fold" open>
  <summary>📄 需求描述</summary>
  ...
</details>
<details class="dsh-pm-fold" open>
  <summary>📁 文档记录</summary>
  ...
</details>
// ... 9 个折叠区
```

**改造策略**：

✅ **更新（不是删除文件）**
- 保留 `view.ts` 文件和 `buildReqDetail()` 函数
- 保留函数签名（参数、返回类型）
- 保留其他辅助渲染函数（`renderDocSection`、`renderReqTimeline` 等）

❌ **删除代码段**（第 804-850+ 行）
- 删除第 804-806 行：`<div class="dsh-pm-stage-nav">` 及 8 个按钮
- 删除第 807 行：`<div class="dsh-pm-stage-detail">` 动态容器
- 删除第 808-850+ 行：11 个 `<details class="dsh-pm-fold">` 折叠区

✅ **新增代码段**（在删除位置）
- 新增：`buildProgressDots(req.status)` 调用（8 态进度点）
- 新增：`buildTabs()` 调用（4 个 Tab 按钮）
- 新增：`buildTabContents(req, tasks, ...)` 调用（4 个 Tab 内容区）

**代码改动对比**：

```diff
  export function buildReqDetail(req, tasks, now, archived) {
    // ... 前面保持不变（第 774-802 行）
    
    return `
      <div class="dsh-pm-detail">
        <div class="dsh-pm-detail-head">...</div>
        ${actionBar}
        ${gateHint}
        
-       <!-- 删除：8 个节点导航按钮（第 804-806 行）-->
-       <div class="dsh-pm-stage-nav">
-         ${ALL_STAGE_KEYS.map(s => `<button ...>`).join('')}
-       </div>
-       
-       <!-- 删除：阶段详情动态容器（第 807 行）-->
-       <div class="dsh-pm-stage-detail"></div>
-       
-       <!-- 删除：11 个折叠区（第 808-850+ 行）-->
-       <details class="dsh-pm-fold" open>
-         <summary>📄 需求描述</summary>
-         ...
-       </details>
-       <details class="dsh-pm-fold" open>
-         <summary>📁 文档记录</summary>
-         ...
-       </details>
-       <!-- ... 9 个折叠区 -->

+       <!-- 新增：8 态进度点 -->
+       ${buildProgressDots(req.status)}
+       
+       <!-- 新增：4 个 Tab -->
+       ${buildTabs()}
+       
+       <!-- 新增：4 个 Tab 内容区 -->
+       ${buildTabContents(req, reqTasks, dag, taskCols, comments)}
        
      </div>`
  }
```

**为什么是更新而非删除？**

1. **函数签名保持不变** → 调用方无需修改
2. **辅助函数复用** → `renderDocSection()`、`renderReqTimeline()` 等在新 Tab 中复用
3. **逐步迁移** → 可以先注释掉旧代码，验证新代码后再删除
4. **回滚容易** → 保留文件历史，出问题可快速回退

---

#### 2️⃣ view.ts（修改，+150/-80 行）

**删除部分**（~80 行）：
```typescript
// ❌ 删除：8 个节点导航按钮
<div class="dsh-pm-stage-nav">
  <button data-stage="draft">立项</button>
  <button data-stage="brainstorming">需求分析</button>
  // ... 6 个按钮
</div>

// ❌ 删除：11 个折叠区统一容器
<details class="dsh-pm-fold">
  <summary>需求描述</summary>
  ...
</details>
// ... 10 个折叠区
```

**新增部分**（~150 行）：
```typescript
import { WORKFLOW_STAGES, PROGRESS_DOT_STAGES } from './workflow-constants'

// ✅ 新增函数：渲染 8 态进度点
function buildProgressDots(currentStatus: RequirementStatus): string {
  const currentOrder = WORKFLOW_STAGES[currentStatus]?.order ?? -1
  
  return `<div class="dsh-pm-progress-dots">${
    PROGRESS_DOT_STAGES.map(stage => {
      const { label, order } = WORKFLOW_STAGES[stage]
      const state = order < currentOrder ? 'completed' 
                  : order === currentOrder ? 'current' 
                  : ''
      return `
        <div class="dsh-pm-dot-wrapper ${state}">
          <div class="dsh-pm-dot"></div>
          <span class="dsh-pm-dot-label">${label}</span>
        </div>`
    }).join('')
  }</div>`
}

// ✅ 新增函数：渲染 4 个 Tab
function buildTabs(): string {
  return `
    <div class="dsh-pm-tabs">
      <button class="dsh-pm-tab active" data-tab="overview">📋 概览</button>
      <button class="dsh-pm-tab" data-tab="execution">⚙️ 执行</button>
      <button class="dsh-pm-tab" data-tab="timeline">📅 时间线</button>
      <button class="dsh-pm-tab" data-tab="archive">📦 归档</button>
    </div>`
}

// ✅ 新增函数：渲染 4 个 Tab 内容
function buildTabContents(
  req: RequirementRecord,
  tasks: TaskRecord[],
  dag: string,
  taskCols: string,
  comments: string
): string {
  return `
    <!-- 概览 Tab（默认显示） -->
    <div class="dsh-pm-tab-content active" data-tab-content="overview">
      ${renderReqDescription(req)}
      ${renderDocSection(req)}
      ${renderStageDetail(req)}
    </div>
    
    <!-- 执行 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="execution">
      ${dag}
      ${taskCols}
    </div>
    
    <!-- 时间线 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="timeline">
      ${renderReqTimeline(req)}
      ${comments}
    </div>
    
    <!-- 归档 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="archive">
      ${renderArchiveSection(req)}
    </div>`
}

// ✅ 修改函数：buildReqDetail()
export function buildReqDetail(req: RequirementRecord, tasks: TaskRecord[], ...): string {
  const dag = buildDag(reqTasks)
  const taskCols = buildTaskColumns(reqTasks)
  const comments = renderComments(req.comments)
  const actionBar = renderActionBar(req)
  const gateHint = gateHintFor(req.status)
  
  // 新增调用
  const progressDots = buildProgressDots(req.status)
  const tabs = buildTabs()
  const tabContents = buildTabContents(req, reqTasks, dag, taskCols, comments)
  
  return `
    <div class="dsh-pm-detail">
      <div class="dsh-pm-detail-head">...</div>
      ${actionBar}
      ${gateHint}
      ${progressDots}   <!-- 新增 -->
      ${tabs}           <!-- 新增 -->
      ${tabContents}    <!-- 新增 -->
    </div>`
}
```

#### 3️⃣ styles.ts（新增 ~120 行）

```css
/* 8 态进度点 */
.dsh-pm-progress-dots {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin: 20px 0;
  padding: 12px 0;
}

.dsh-pm-dot-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.dsh-pm-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--dsw-border, #ddd);
  opacity: 0.4;
  transition: all 0.3s;
}

.dsh-pm-dot-wrapper.completed .dsh-pm-dot {
  opacity: 1;
  background: #28a745;
}

.dsh-pm-dot-wrapper.current .dsh-pm-dot {
  width: 14px;
  height: 14px;
  opacity: 1;
  background: #4a7dff;
  box-shadow: 0 0 0 4px rgba(74,125,255,0.15);
}

.dsh-pm-dot-label {
  font-size: 11px;
  color: var(--dsw-text-secondary, #999);
  white-space: nowrap;
  text-align: center;
}

.dsh-pm-dot-wrapper.current .dsh-pm-dot-label {
  color: #4a7dff;
  font-weight: 600;
}

.dsh-pm-dot-wrapper.completed .dsh-pm-dot-label {
  color: #28a745;
  font-weight: 500;
}

/* Tab 导航 */
.dsh-pm-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--dsw-border, #eee);
  padding: 0 20px;
}

.dsh-pm-tab {
  padding: 12px 24px;
  border: none;
  background: none;
  color: var(--dsw-text-secondary, #666);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.dsh-pm-tab:hover {
  background: rgba(74,125,255,0.05);
  color: var(--dsw-text-primary, #333);
}

.dsh-pm-tab.active {
  color: #4a7dff;
  border-bottom-color: #4a7dff;
  font-weight: 600;
}

/* Tab 内容区 */
.dsh-pm-tab-content {
  padding: 24px;
  display: none;
}

.dsh-pm-tab-content.active {
  display: block;
}
```

#### 4️⃣ dom.ts（新增 ~30 行）

```typescript
// ✅ 新增：Tab 切换事件监听
container.addEventListener('click', e => {
  const tab = (e.target as HTMLElement).closest('.dsh-pm-tab')
  if (!tab) return
  
  const tabName = tab.getAttribute('data-tab')
  if (!tabName) return
  
  // 切换 Tab active 状态
  container.querySelectorAll('.dsh-pm-tab').forEach(t => {
    t.classList.remove('active')
  })
  tab.classList.add('active')
  
  // 切换内容区显示
  container.querySelectorAll('.dsh-pm-tab-content').forEach(content => {
    content.classList.remove('active')
  })
  
  const targetContent = container.querySelector(
    `.dsh-pm-tab-content[data-tab-content="${tabName}"]`
  )
  if (targetContent) {
    targetContent.classList.add('active')
  }
})
```

---

**预计工期**：3-4 天