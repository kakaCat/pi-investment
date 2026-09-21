# t-3e64cb 骨架接线：bizToolviews 注册入口 + BizRow 布局 + task_move 示范卡

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
骨架接线：bizToolviews 注册入口 + BizRow 布局 + task_move 示范卡

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build WRAP_SENTINEL 门禁绿）；重启后新会话一次 reqboard_task_move 调用折叠行显示 't-xxx → 开工' 样式中文动作

## 实施方案（implementation）
参照 ui-tool ask-question-toolview 注册模式；样式注入走 styles.ts 同款；只用 react external，禁新增 bare npm 依赖；构建后 restart-with-build.sh 重启实测

## 上游产出摘要（dependsSummary）
- 契约卡：toolviews 数据契约 + 纯函数骨架 + renderSmart 签名

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T03:24:37.197Z，窗口 session-85447f15-ee57-44ef-8fd0-d8526111c0b3）

骨架接线完成：bizToolviews 注册入口（tool.call.toolview 插槽，逐卡 try/catch）+ BizRow 通用行布局（icon+标题+摘要+展开体+错误红标）+ fallbackRow 兜底 + task_move 示范卡 + client/index.ts 挂载；build:client 通过（WRAP_SENTINEL 门禁绿）

### 完成项

- toolviews/biz-row.ts：BizRow 布局 + FallbackRow + makeBizRow 工厂（react createElement，零新增依赖）
- toolviews/index.ts：registerBizToolviews（9 卡注册）
- client/index.ts 挂载（slots 块内，同款 try/catch）
- build:client 门禁绿；契约/卡片单测随 t1/t3 覆盖

### 改动文件

- `packages/pages/dsh-pmboard/src/client/toolviews/biz-row.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/index.ts`
- `packages/pages/dsh-pmboard/src/client/index.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/task-move.ts`

### 下一步

重启后新会话实测折叠行中文动作（t2 live 验收）

---
