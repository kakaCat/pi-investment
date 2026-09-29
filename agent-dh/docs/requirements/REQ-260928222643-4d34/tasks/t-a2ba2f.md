# t-a2ba2f 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·复核

> 任务卡骨架（自动链懒展开时只建了 TaskRecord、未落卡文档；本文件由窗口 `session-f17b3bd0` 按队列里的卡面事实回填，内容取自该子卡的实施方案与验收标准）

## 在做什么
反面断言看板消费方保留（board-mount.ts 的 fetchInjectionInfo 恰好 1 处、api.ts 两函数保留、node-panel-process.ts 函数保留、后端 injection-log/isolation-log 路由保留）；调用方收敛断言；非粘滞断言；git diff 变更面与 REQBOARD_SCHEMA_VERSION 未变核对；记录回滚路径。 [子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 解决什么问题
把父卡 **t-316227**（迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归）的交付拆成「复核」阶段并独立验收，避免父卡一步到位、问题不可定位。

## 范围
- 阶段：test
- 端侧：frontend
- 子卡阶段：review

## 得到什么结果

在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-mount.test.ts tests/client-api-resolve.test.ts（期望全绿、exit 0）；再对照 docs/requirements/REQ-260928222643-4d34/design/data-model.md 逐条确认无字段/schema 变更。

## 实施方案（implementation）
反面断言看板消费方保留（board-mount.ts 的 fetchInjectionInfo 恰好 1 处、api.ts 两函数保留、node-panel-process.ts 函数保留、后端 injection-log/isolation-log 路由保留）；调用方收敛断言；非粘滞断言；git diff 变更面与 REQBOARD_SCHEMA_VERSION 未变核对；记录回滚路径。 [子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 上游产出摘要（dependsSummary）
- t-4397da

## 执行留痕（自动链 run）
- 状态：done｜尝试次数：0
- 产出（completed）：
- 对 REQ-260928222643-4d34 父卡 t-316227「迁移与兼容核验」逐条给出设计与实现偏离结论：无偏离。①反面断言（看板消费方保留）：board-mount.ts 的 fetchInjectionInfo 恰好 1 处且为真实调用，api.ts 两函数保留，node-panel-process.ts 的 renderProcessFold/ProcessFoldContext 函数本体保留，后端 /injection-log、/isolation-log 两条只读路由与处理器保留——逐项与设计 I-7/父卡实施方案一致。②调用方收敛：NodePanelInput 全 src 仅渲染器 node-panel.ts 使用，唯一调用方 conversation-progress.ts 已改内联调用且两文件零 injection/isolation，设计 T-4 的「唯一调用点同批修改、无遗留调用方」成立。③非粘滞：board-focus.ts/board-entry.ts 对 storage/URL/history/cookie 零命中，符合 T-1/T-3。④schem…
- 落盘改动（filesChanged）：
- （无落盘改动）

## 执行方式提示（executorHint）
本卡由自动链执行完成；卡面事实以 `../queue.json` 为准。不读会话历史，按本卡自足复核。
