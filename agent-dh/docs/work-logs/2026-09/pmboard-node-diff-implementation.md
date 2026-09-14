# PM Board 节点内容差异化实施报告

**实施日期**: 2026-09-15  
**工作分支**: feat/pmboard-node-diff  
**状态**: P0 阶段完成（拆分、实施、测试节点）

## 实施概要

实现了项目看板节点内容差异化展示功能，根据任务类型（phase）自动识别节点类型，并展示专属的内容区域。

### 核心改动

1. **节点类型识别系统** (`view.ts`)
   - 新增 `NodeType` 类型定义（9种节点类型）
   - 实现 `identifyNodeType()` 函数，基于 `task.phase` 和 `title` 识别节点类型
   - 每种节点类型配备专属图标和标签

2. **专属内容渲染** (`view.ts`)
   - 新增 `renderSpecializedContent()` 分发函数
   - 实现 P0 节点渲染器：
     - `renderDecomposeContent()` - 拆分节点
     - `renderImplementContent()` - 实施节点
     - `renderTestContent()` - 测试节点
   - P1/P2 节点保留占位符

3. **通用信息折叠** (`view.ts`)
   - 新增 `renderCommonContent()` 函数
   - 使用 `<details>` 元素折叠通用信息（属性、时间线、执行记录、评论）
   - 专属内容优先展示，通用信息按需展开

4. **样式系统** (`styles.ts`)
   - 新增 140+ 行 CSS 规则
   - 节点徽章、统计卡片网格、轨道列表
   - 文件变更展示、测试失败用例、覆盖率进度条
   - 响应式布局和状态着色

5. **调用点更新** (`board-mount.ts`)
   - 更新 `buildTaskDetail()` 签名，新增 `allTasks` 参数
   - 传递完整任务列表以支持拆分节点的跨任务分析

## 节点类型定义

| 节点类型 | 识别规则 | 图标 | 专属内容 |
|---------|---------|------|---------|
| `decompose` | title 包含 "拆分" 或 "decompose" | 🔀 | 拆分统计、轨道清单、DAG 图 |
| `implement` | phase === 'implement' | ⚙️ | 文件变更、执行记录、质量指标 |
| `test` | phase === 'test' | 🧪 | 测试概况、失败用例、覆盖率 |
| `review` | phase === 'review' | 👀 | 待实现（P1） |
| `merge` | phase === 'merge' 或 status === 'integrating' | 🔀 | 待实现（P1） |
| `doc` | phase === 'doc' | 📝 | 待实现（P2） |
| `ui` | phase === 'ui' | 🎨 | 待实现（P2） |
| `analysis` | phase === 'analysis' | 🔍 | 待实现（P2） |
| `generic` | 其他 | 📋 | 仅通用信息 |

## 拆分节点（Decompose Node）

### 展示内容

1. **拆分结果统计**
   - 总计任务数
   - 并行轨道数（frontend/backend/fullstack/doc）
   - 预计工期（任务数 × 0.5 天）
   - 完成进度（已完成/总数）

2. **拆分清单**
   - 按端侧分组（UI 轨道、后端轨道、全栈轨道、文档轨道）
   - 每个轨道显示任务数和任务列表
   - 任务 ID 可点击跳转

3. **依赖关系 DAG**
   - 复用现有 `buildDag()` 函数
   - 显示任务间的依赖关系和层级

### 数据来源

- 从 `allTasks` 中过滤出 `requirementId` 匹配的任务
- 按 `task.side` 分组
- 统计 `status === 'done'` 的任务数

## 实施节点（Implementation Node）

### 展示内容

1. **修改文件列表**
   - 文件路径、新增行数、删除行数
   - 汇总统计（文件数、总新增、总删除）

2. **执行记录摘要**
   - 每次执行的时间、结果（✅/❌/⏳/⚠️）
   - 按时间倒序排列

3. **质量指标**
   - 测试覆盖率
   - 代码复杂度（待实现）
   - 类型安全检查

### 数据来源

- 从 `executions[].evidence` 解析文件变更
  - 格式：`"src/auth/login.ts (+45, -12)"`
- 从 `executions[].outcome` 获取执行结果
- 从 `evidence` 中查找包含 "coverage" 或 "覆盖率" 的记录

## 测试节点（Test Node）

### 展示内容

1. **测试概况**
   - 总计用例数
   - 通过数量和百分比
   - 失败数量
   - 跳过数量

2. **失败的测试（如有）**
   - 测试用例名称
   - 预期结果 vs 实际结果
   - 失败文件位置

3. **覆盖率报告（如有）**
   - 语句覆盖率（进度条可视化）
   - 分支覆盖率
   - 函数覆盖率
   - 行覆盖率

### 数据来源

- 从 `executions[].evidence` 解析测试结果
  - 格式：`"18 passed / 2 failed / 0 skipped"`
- 从 `executions[].error` 解析失败用例
  - 格式：`"file.ts:42 Expected: X Actual: Y"`
- 从 `evidence` 中解析覆盖率
  - 关键词：statements, branches, functions, lines

## 通用信息折叠

所有节点类型都保留以下通用信息，默认折叠在 `<details>` 元素中：

- **属性**: 阶段、端侧、依赖、验收标准
- **时间线**: 状态变更历史
- **执行记录**: 完整的执行历史（带错误和证据）
- **评论**: 人工和 agent 的评论，带评论输入框

## 样式特性

### 节点徽章
```html
<span class="dsh-pm-node-badge">🔀 拆分任务</span>
```
- 灰色背景、圆角、带图标和标签
- 显示在任务详情头部

### 统计卡片网格
```css
.dsh-pm-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}
```
- 响应式网格布局
- 每个统计项独立卡片
- 成功/失败状态着色

### 覆盖率进度条
```css
.dsh-pm-coverage-fill {
  background: linear-gradient(90deg, #28a745, #20c997);
  transition: width .3s ease;
}
```
- 渐变绿色进度条
- 平滑动画过渡

## 测试验证

### 编译验证
```bash
pnpm --filter dsh-pmboard build:client
```
✅ 编译成功，无错误

### 输出文件
- `lib/client.cjs` - 82.30 kB (gzip: 20.31 kB)
- `lib/client.js` - 80.1 kB (wrapped)
- `lib/client.d.cts` - 0.69 kB (类型定义)

## 待实现功能（P1/P2）

### P1 - 增强节点
- **评审节点** (`review`)
  - 评审意见列表（按严重性分级）
  - 通过项 vs 改进建议
  - 后续动作跟踪

- **合并节点** (`merge`)
  - 合并统计（提交数、文件数、行数变更）
  - 冲突解决记录
  - CI/CD 检查结果

### P2 - 完善节点
- **文档节点** (`doc`)
  - 文档文件列表
  - 关联接口清单
  - 完成度统计

- **UI 节点** (`ui`)
  - 设计稿预览
  - 设计规范（颜色、字体、间距）
  - 组件清单和交互流程

- **分析节点** (`analysis`)
  - 技术方案对比表
  - 推荐方案和理由
  - 风险点和参考资料

## 遗留问题

1. **拆分节点数据源**
   - 当前需要从外部传入 `allTasks` 参数
   - 已更新 `buildTaskDetail()` 签名
   - 已更新 `board-mount.ts` 调用点

2. **Evidence 数据格式**
   - 当前依赖手工解析字符串
   - 未来应定义结构化的 Evidence 接口
   - 参考设计文档中的 `Evidence` 接口定义

3. **质量指标占位**
   - 代码复杂度暂时显示为 "未知"
   - 需要后端提供复杂度分析数据

## 下一步计划

1. **运行时测试**
   - 在实际环境中测试不同节点类型的展示效果
   - 验证数据解析逻辑的健壮性
   - 检查样式在不同主题下的表现

2. **数据格式标准化**
   - 定义 `ExecutionRecord.evidence` 的结构化格式
   - 后端工具输出标准化的测试结果、覆盖率、文件变更数据

3. **P1 功能实现**
   - 评审节点和合并节点是高频使用场景
   - 优先级高于 P2 的文档/UI/分析节点

## 文件清单

### 修改文件
- `agent-dh/packages/pages/dsh-pmboard/src/client/view.ts` (+283 行)
  - 节点类型识别
  - 专属内容渲染器（拆分、实施、测试）
  - 通用信息折叠
  
- `agent-dh/packages/pages/dsh-pmboard/src/client/styles.ts` (+142 行)
  - 节点差异化样式规则
  - 统计卡片、轨道列表、覆盖率进度条
  
- `agent-dh/packages/pages/dsh-pmboard/src/client/board-mount.ts` (+1 行)
  - 传递 `state.tasks` 到 `buildTaskDetail()`

### 新增文件
- `agent-dh/docs/design/pmboard-node-content-design.md` - 设计文档
- `agent-dh/docs/work-logs/2026-09/pmboard-node-diff-implementation.md` - 本报告

## 参考资料

- [设计文档](../../design/pmboard-node-content-design.md)
- [需求说明](../../design/pmboard-task-page-ui-improvement.md)
- [项目看板架构](../../architecture/project-board-architecture.md)

## 贡献者

- Claude (Kiro) - 设计与实现
- 用户反馈 - 需求来源

---

**注**: 本报告记录 P0 阶段的实现情况，P1/P2 功能将在后续迭代中完成。
