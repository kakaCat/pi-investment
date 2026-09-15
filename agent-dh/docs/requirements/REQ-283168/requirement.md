# 需求说明（REQ-283168）

**分类**：bug

**背景**：用户发现项目看板（dsh-pmboard）页面展示与之前不同——丢失「列表 + 泳道」双视图切换，只剩单一泳道视图；随后确认会话头部的需求进度条样式也一并丢失。

根因（已查实）：双视图实现当年以 `git stash` 暂存（stash@{0}，描述"暂存主工作区更改以便合并 feat/pmboard-node-diff"）后**从未 pop**；后续 P0/P1/P2 提交（5e2c6ed1 / 86aae7f6 / 41feb8f5）覆盖工作区，stash 中的 view.ts / board-mount.ts / styles.ts 改动随之沉没，只在 board-mount.ts 留下一处悬空调用 `buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())`。`conversation-progress.ts` 当时是 untracked 文件，侥幸存活但未入库。

**目标**：从 stash 恢复双视图代码并合并回主干，看板重新支持「列表 / 泳道」两种视图切换，会话头部进度条样式恢复；全部改动入库，杜绝同类静默丢失。

**边界（不做什么）**：
- 不重写看板架构，只做恢复性合并；
- 不顺手修复 P2 遗留的 client-view.test.ts:501 断言过期（属 P2 工作线，另行决策）；
- 不动与看板无关的代码。

**验收标准**：
1. `packages/pages/dsh-pmboard/src/client/view.ts` 含 buildListView / renderListToolbar / 视图切换逻辑，board-mount.ts 恢复 `switch-view` / `list-sort` / 分页状态；
2. `lib/client.js` 重建，关键符号（buildListView、renderListCard、NO_ARCHIVED、sessionChipHtml、dsh-pm-cprog 等）全部存在；
3. 页面 :13080 刷新后看板出现视图切换控件，列表视图可排序 / 分页；
4. 会话头部需求进度条样式（.dsh-pm-cprog*）恢复渲染；
5. 相关改动全部 commit，工作区干净。

**相关**：[related-docs.md](related-docs.md)（历史看板文档索引）/ [verification.md](verification.md)
