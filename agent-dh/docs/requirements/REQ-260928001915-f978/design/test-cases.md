# 测试用例设计（REQ-260928001915-f978）

> 每章标题行必须带 `serves: FR-x` 标注（缺标注 = 孤儿章节被门禁拦）。

## 卡片类型系统测试 `serves: FR-1`

### TC-1：七类任务类型彩色徽标 `serves: FR-1`

**输入**：包含 7 个任务的 DAG，每个任务 `phase` 不同（implement/test/doc/review/ui/analysis/merge）

**预期输出**：
- `implement` 徽标显示蓝色（`background: rgba(0,113,227,.13); color: #0062c4`）
- `test` 徽标显示橙色（`background: rgba(255,149,0,.15); color: #b26a00`）
- `doc` 徽标显示紫色（`background: rgba(88,86,214,.13); color: #4b49b8`）
- `review` 徽标显示粉色（`background: rgba(233,30,99,.12); color: #c2185b`）
- `ui` 徽标显示青色（`background: rgba(6,182,212,.15); color: #0e7490`）
- `analysis` 徽标显示灰色（`background: rgba(87,83,78,.14); color: #57534e`）
- `merge` 徽标显示绿色（`background: rgba(52,199,89,.15); color: #1d8a3c`）

**验证命令**：
```bash
# 生成测试 DAG HTML
python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py
# 浏览器打开 /tmp/dag-card-types-demo.html
# 目视检查「① 卡片类型展示」区域的 7 张卡片徽标颜色
```

### TC-2：四类端侧徽标 `serves: FR-1`

**输入**：包含 4 个任务的 DAG，每个任务 `side` 不同（backend/frontend/fullstack/doc）

**预期输出**：
- `backend` 徽标显示紫色（`background: rgba(124,58,237,.12); color: #7c3aed`）
- `frontend` 徽标显示粉色（`background: rgba(219,39,119,.12); color: #db2777`）
- `fullstack` 徽标显示绿色（`background: rgba(34,197,94,.12); color: #16a34a`）
- `doc` 徽标显示橙色（`background: rgba(251,146,60,.14); color: #ea580c`）

**验证命令**：同 TC-1，检查端侧徽标颜色

### TC-3：父卡结构（左侧蓝条 + 子卡链进度） `serves: FR-1, FR-7`

**输入**：`role='parent'` 任务，含 4 个子卡（1 done、1 in_progress、2 todo）

**预期输出**：
- 卡片左侧显示 3px 宽蓝条（`.card-crown`，`background: rgba(0,113,227,.55)`）
- 底部显示子卡链进度条：4 个竖条 + `2/4` 文本
  - 第 1 个竖条绿色（`.on`，`background: #34c759`）
  - 第 2 个竖条蓝色（`.now`，`background: #0071e3`）
  - 第 3、4 个竖条灰色（`background: rgba(0,0,0,.12)`）

**验证命令**：
```bash
# 打开 demo HTML，检查「② 角色三态」区域第 1 张卡片（父任务）
# 目视：左侧蓝条 + 底部进度条
```

### TC-4：子卡缩进与左侧竖线 `serves: FR-1`

**输入**：`role='child'` 任务

**预期输出**：
- 卡片宽度 190px（普通卡 208px）
- 左侧缩进 18px（`margin-left: 18px`）
- 卡片内左侧 4px 处显示灰色竖线（`::before` 伪元素，`width: 2px; background: rgba(0,0,0,.08)`）

**验证命令**：同 TC-3，检查「② 角色三态」区域第 2 张卡片（子任务）

### TC-5：ready 绿点 `serves: FR-2`

**输入**：任务 id 存在于 `QueueFile.ready[]`

**预期输出**：
- 卡片右上角 (`right: 6px; top: 6px`) 显示 6px 圆点
- 绿色（`background: #34c759`）+ 光晕（`box-shadow: 0 0 0 3px rgba(52,199,89,.2)`）

**验证命令**：
```bash
# 打开 demo HTML，检查「③ 真实 DAG 可视化」区域
# DAG 数据的 ready 数组含 3 个任务 id，这 3 张卡应显示右上角绿点
```

## DAG 渲染测试 `serves: FR-2, FR-3`

### TC-6：依赖边渲染 `serves: FR-2, FR-3`

**输入**：`QueueFile.edges = [{ from: 't-1', to: 't-2' }, { from: 't-1', to: 't-3' }]`

**预期输出**：
- SVG `<path>` 元素连接节点 t-1 → t-2 和 t-1 → t-3
- 曲线使用 Bézier 三次曲线（`C` 命令）
- 箭头标记（`marker-end="url(#m-base)"`）
- 如果两端都是 `status='done'`，边线绿色（`.e-done`，`stroke: rgba(52,199,89,.5)`）

**验证命令**：
```bash
# 打开 demo HTML
# 浏览器开发者工具检查 SVG 元素
# 应有 14 条 <path> 元素（对应 DAG 数据的 14 条边）
```

### TC-7：纵向/横向布局切换 `serves: FR-3`

**输入**：
- 纵向模式（`direction='tb'`）：同层任务按 `availWidth` 分列，y 坐标逐层递增
- 横向模式（`direction='lr'`）：同层任务按 `maxRows=8` 限高分列，x 坐标逐层递增

**预期输出**：
- 纵向：节点 `style="left:Xpx; top:Ypx"`，同层任务 y 相同
- 横向：同层任务 x 相同

**验证命令**：
```bash
# 打开 demo HTML
# 点击「纵向」/「横向」按钮
# 观察节点位置变化：纵向呈瀑布流，横向呈泳道
```

### TC-8：状态底色 `serves: FR-1, FR-2`

**输入**：6 种状态的任务（todo/in_progress/integrating/testing/in_review/done）

**预期输出**：
- `todo`：浅灰（`#fafafa`）
- `in_progress`：浅蓝（`rgba(0,113,227,.06)`）
- `integrating`：浅紫（`rgba(142,68,173,.07)`）
- `testing`：浅橙（`rgba(255,149,0,.08)`）
- `in_review`：浅粉（`rgba(233,30,99,.06)`）
- `done`：浅绿（`rgba(52,199,89,.08)`）

**验证命令**：目视检查 demo HTML 中各状态卡片底色

## 交互测试 `serves: FR-4, FR-5`

### TC-9：悬停高亮上游 `serves: FR-4, FR-5`

**输入**：鼠标悬停在任务 B（依赖 A）上

**预期输出**：
- B 卡片：黑色轮廓（`box-shadow: 0 0 0 2px #1f2733`）+ `.hi-self` 类
- A 卡片：橙色轮廓（`box-shadow: 0 0 0 2px rgba(255,149,0,.9)`）+ `.hi-up` 类
- A→B 边线：橙色加粗（`stroke: #ff9500; stroke-width: 2`）
- 其他节点：半透明（`opacity: .18`）
- 移开鼠标：恢复正常

**验证命令**：
```bash
# 打开 demo HTML
# 鼠标悬停在任意非起点节点上
# 观察该节点黑框、上游节点橙框、边线橙色
```

### TC-10：悬停高亮下游 `serves: FR-4, FR-5`

**输入**：鼠标悬停在任务 A（被 C 依赖）上

**预期输出**：
- A 卡片：黑色轮廓 + `.hi-self`
- C 卡片：蓝色轮廓（`box-shadow: 0 0 0 2px rgba(0,113,227,.9)`）+ `.hi-down`
- A→C 边线：蓝色加粗（`stroke: #0071e3; stroke-width: 2`）
- 其他节点：半透明

**验证命令**：同 TC-9，悬停在起点或中间节点

### TC-11：点击钉住 `serves: FR-5`

**输入**：
1. 点击任务 B
2. 移开鼠标
3. 再次点击 B

**预期输出**：
- 第 1 次点击：B 及其上下游高亮，移开鼠标高亮**保持**
- 第 2 次点击：清除高亮

**验证命令**：
```bash
# 打开 demo HTML
# 点击任意节点，移开鼠标，高亮应保持
# 再点一次同一节点，高亮清除
```

### TC-12：点击空白清除高亮 `serves: FR-5`

**输入**：钉住状态下，点击画布空白区域

**预期输出**：清除高亮，恢复正常显示

**验证命令**：钉住后点击节点之间的空白处

## 关键路径与主线折叠测试 `serves: FR-6, FR-7`

### TC-13：关键路径标记 `serves: FR-6`

**输入**：包含关键路径的 DAG（如 demo 的 12 层 DAG，关键路径长度 8）

**预期输出**：
- 关键路径节点：虚线轮廓（`outline: 2px dashed rgba(0,113,227,.55)`）+ `.crit` 类
- 关键路径边线：蓝色加粗（`.e-crit`，`stroke: rgba(0,113,227,.75); stroke-width: 1.8`）
- 图例显示"关键路径 X 步"

**验证命令**：
```bash
# 打开 demo HTML
# 点击「关键路径」按钮
# 观察被虚线框标记的节点（应为从起点到终点的最长路径）
```

### TC-14：主线折叠（只看主线） `serves: FR-6, FR-7`

**输入**：点击「只看主线」按钮

**预期输出**：
- 只显示关键路径上的节点
- 非关键路径节点隐藏
- 有支线的节点卡角显示 `+N 支线` 徽标（`.branch-chip`）
- 按钮文本变为"展开全图"

**验证命令**：
```bash
# 打开 demo HTML
# 选择「压力图」数据集（83 边 12 层）
# 点击「只看主线」
# 节点数应从 65 降到关键路径节点数（约 12-15 个）
# 某些节点卡角显示 +N 支线
```

### TC-15：主线展开 `serves: FR-6, FR-7`

**输入**：主线折叠状态下，点击「展开全图」按钮

**预期输出**：
- 显示全部节点
- `+N 支线` 徽标消失
- 按钮文本变回"只看主线"

**验证命令**：接 TC-14，点击「展开全图」

## 边界与错误测试 `serves: FR-2`

### TC-16：空 DAG `serves: FR-2`

**输入**：`tasks = []`

**预期输出**：显示占位文本"暂无任务"

**验证命令**：
```typescript
const html = renderDag({ tasks: [], edges: [], ready: [] }, defaultState)
assert(html.includes('暂无任务'))
```

### TC-17：edges 引用不存在的任务 `serves: FR-2`

**输入**：`edges = [{ from: 't-1', to: 't-999' }]`，但 `tasks` 里无 t-999

**预期输出**：
- 控制台警告："边 t-1 → t-999 引用了不存在的任务"
- 该边不渲染
- 其他正常节点和边正常显示

**验证命令**：手工构造错误数据并调用 `renderDag()`

### TC-18：循环依赖 `serves: FR-2, FR-6`

**输入**：`t-1.dependsOn=['t-2'], t-2.dependsOn=['t-3'], t-3.dependsOn=['t-1']`

**预期输出**：
- 控制台错误："检测到循环依赖"
- 渲染错误提示："DAG 存在循环依赖"

**验证命令**：手工构造循环依赖数据

### TC-19：layer 缺失 `serves: FR-3`

**输入**：任务的 `layer` 字段为 `undefined`

**预期输出**：
- 控制台警告："任务缺少 layer 字段，重新计算"
- 调用 `topoLevels()` 重算 layer
- 正常渲染

**验证命令**：手工删除任务的 `layer` 字段

## 数据契约校验测试 `serves: FR-2`

### TC-20：V-1 规则（tasks 非空） `serves: FR-2`

**输入**：`{ tasks: [] }`

**预期输出**：`validateQueueFile()` 返回 `{ passed: false, issues: [{ rule: 'V-1', message: '...' }] }`

### TC-21：V-3 规则（requirementId 一致） `serves: FR-2`

**输入**：`tasks[0].requirementId = 'REQ-A'`，但 `requirement_id = 'REQ-B'`

**预期输出**：`{ passed: false, issues: [{ rule: 'V-3', ... }] }`

### TC-22：V-6 规则（ready 合法） `serves: FR-2`

**输入**：`ready = ['t-1']`，但 `tasks[0].status = 'done'`

**预期输出**：`{ passed: false, issues: [{ rule: 'V-6', message: 'ready 包含非 todo 任务' }] }`

## 回归测试 `serves: FR-2`

### TC-23：现有层级列表仍可用 `serves: FR-2`

**目的**：确保新设计不破坏现有功能

**输入**：调用旧 `renderDag(tasks)` 签名

**预期输出**：兼容适配器返回简单层级列表 HTML（向后兼容）

**验证命令**：运行现有单元测试（如果有）
