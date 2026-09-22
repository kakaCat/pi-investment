# t-af2e01 [FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
[FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：fullstack

## 得到什么结果
curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' 返回 agent-dh 绝对路径；相关测试全绿；实证：工作区=dsh-pmboard 会话看板打开文档链接成功。

## 实施方案（implementation）
改 src/http/routers/stages.ts handleState；改 src/client/board-mount.ts 缓存 workspaceRoot 并在 open-doc 动作拼绝对路径；conversation-progress.ts 同步；面板渲染处绝对化显示；stages 路由测试 + file-address 绝对路径测试。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T02:21:40.561Z，窗口 session-9faaac35-2641-473c-a5dc-ea6e6d11efbf）

看板/会话进度打开文档不再依赖你当前会话的工作区：state 端点暴露服务端工作区根，客户端把相对路径拼成绝对路径再打开——在任何会话（含 dsh-pmboard 工作区）都能打开需求文档；产物按钮悬停可见绝对路径（~ 缩写）；立项回执直接打印绝对路径

### 完成项

- stages.handleState 增 workspaceRoot（deps.cwd ?? process.cwd()）与 homeDir 字段
- open-doc.ts 增工作区根缓存 + absolutizeDocPath/displayDocPath + openDocInSidebar 内部绝对化（两处调用点自动生效）
- board-mount fetchState 后缓存根
- stage-panel 3 处 + verification 1 处产物按钮加绝对路径 title
- CaptureRequirement 立项回执 note 输出绝对路径
- 新增 state-workspace-root.test.ts 7 用例；关联 5 套件 100/100 全绿
- client-view 1 失败为存量（git stash 实证 HEAD 即红，archived-bar 断言与本次无关）

### 改动文件

- `packages/web/dsh-pmboard/src/http/routers/stages.ts`
- `packages/web/dsh-pmboard/src/client/open-doc.ts`
- `packages/web/dsh-pmboard/src/client/board-mount.ts`
- `packages/web/dsh-pmboard/src/client/types.ts`
- `packages/web/dsh-pmboard/src/client/stage-panel.ts`
- `packages/web/dsh-pmboard/src/client/views/verification.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/CaptureRequirement.ts`
- `packages/web/dsh-pmboard/tests/state-workspace-root.test.ts`
- `packages/web/dsh-pmboard/tests/stage-panel.test.ts`

### 下一步

t3 开启 nodeIsolation 并重启（客户端 bundle 也需重建才能上浏览器生效，并入 t3 的重启步骤）

---
