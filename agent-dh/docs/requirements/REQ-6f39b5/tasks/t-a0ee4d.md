# t-a0ee4d 重写 buildReqDetail()

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
重写 buildReqDetail()

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：frontend

## 验收标准
删除了 8 个节点导航按钮和 11 个折叠区，集成了新组件，签名保持不变

## 上游产出摘要（dependsSummary）
- 实现 buildProgressDots()
- 实现 buildTabs()
- 实现 buildTabContents()

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T18:12:00.015Z，窗口 session-b8de6c05-f09f-4304-8a71-e009e89fa48c）

重写 buildReqDetail() 函数，删除 59 行旧代码，新增 3 行函数调用

### 完成项

- 删除了 8 个节点导航按钮（第 906-908 行）
- 删除了阶段详情动态容器（第 909 行）
- 删除了 11 个折叠区（第 910-964 行）
- 新增 buildProgressDots(req.status) 调用
- 新增 buildTabs() 调用
- 新增 buildTabContents(req, reqTasks, dag, taskCols, comments) 调用
- 函数签名保持不变，调用方无需修改

### 改动文件

- `packages/pages/dsh-pmboard/src/client/view.ts`

### 下一步

实现 Tab 切换交互（dom.ts）

---
## 汇报 2（2026-09-17T02:59:11.791Z，窗口 session-b8de6c05-f09f-4304-8a71-e009e89fa48c）

返工修复：第一版实现偏离技术文档，8 处缺陷全部修复

### 完成项

- 修复崩溃：buildTabContents 调用了不存在的 renderStageDetail → 改为保留 stage-detail 动态容器
- 修复参数：renderReqTimeline(req) → renderReqTimeline(req, now)
- 补迁甘特图 buildGantt(req, tasks, now) 到执行 Tab
- 补迁实施计划 renderPlanSection 到执行 Tab
- 补迁验收 renderVerifySection 到归档 Tab
- 补迁评论表单（add-comment）到时间线 Tab
- 补迁 +任务按钮到执行 Tab
- 消除死代码：progressHtml 传入 buildTabContents 用于执行 Tab
- 头部结构对齐原型：h1 标题 + 进度点移入 detail-head
- board-mount 进入详情页自动 loadStageDetail 当前阶段
- tsc 类型检查通过（0 错误），构建产物符号验证通过

### 改动文件

- `packages/pages/dsh-pmboard/src/client/view.ts`
- `packages/pages/dsh-pmboard/src/client/board-mount.ts`

### 下一步

浏览器刷新验证 UI 与原型一致性

---
## 汇报 3（2026-09-17T04:02:24.765Z，窗口 session-b8de6c05-f09f-4304-8a71-e009e89fa48c）

按用户指令严格对齐 prototype.html：执行 Tab 删除进度条/任务看板(+任务)/甘特图/实施计划，任务列表改表格

### 完成项

- 执行 Tab 严格对齐原型：统计卡片 + DAG（带标题白底卡） + 任务表格
- 删除：进度条、任务看板 section（+任务按钮、taskCols）、甘特图、实施计划
- 新增 buildTaskTable：状态|任务|阶段|依赖|负责人|操作，行点击进任务详情
- DAG 样式对齐原型（白底卡片容器 + dag-title + layers）
- 任务表格样式（dsh-pm-task-table / dsh-pm-task-status 状态徽章）
- 清理死代码：buildTabContents 去掉 progressHtml/taskCols 参数，buildReqDetail 删除死变量
- 测试同步：任务列→表格断言、甘特图/实施计划详情页断言删除（卡面徽章断言保留）
- vitest 54/54 通过，tsc 0 错误，构建通过

### 改动文件

- `packages/pages/dsh-pmboard/src/client/view.ts`
- `packages/pages/dsh-pmboard/src/client/styles.ts`
- `packages/pages/dsh-pmboard/tests/client-view.test.ts`

### 下一步

浏览器强刷验证

---
## 汇报 4（2026-09-17T04:11:23.385Z，窗口 session-b8de6c05-f09f-4304-8a71-e009e89fa48c）

详情页三处修正：时间线去掉完成节点、当前阶段详情/文档记录改折叠、文档记录登记 HTML 原型

### 完成项

- 时间线里程碑回 7 态（去掉 done/完成 —— REQ-9f4a44 后验收直接归档，done 为 legacy 死状态不再呈现）
- 概览 Tab：当前阶段详情改折叠（默认展开）、文档记录改折叠（默认折叠，长列表收纳）
- docLinks 类型扩展 extras 数组（protocol.ts + types.ts），collectReqDocs 展示 extras（🎁 成果文件）
- 台账登记 3 个 HTML 原型为关键成果：prototype.html（详情页）/ lanes-prototype.html（泳道图）/ list-prototype.html（列表）
- 台账已备份（dsh-reqboard.json.bak-req6f39b5-*）
- 测试同步：里程碑 8→7、pending 计数 6→5；vitest 54/54 通过
- tsc 0 错误，构建通过（205,106 字节）

### 改动文件

- `packages/pages/dsh-pmboard/src/client/view.ts`
- `packages/pages/dsh-pmboard/src/shared/protocol.ts`
- `packages/pages/dsh-pmboard/src/client/types.ts`
- `packages/pages/dsh-pmboard/tests/client-view.test.ts`

### 下一步

重启 DSH web（台账启动加载）+ 浏览器强刷验证

---
