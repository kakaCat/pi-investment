---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10]
sides: [frontend, backend]
---

# 拆分计划（REQ-260923134706-e72f）

> 目标 + 做法一句话：把已定稿的节点弹框设计稿落到 pmboard 插件（新增渲染/样式/对照表模块 + 只读端点 + 接线），
> 并把「模板与门禁矛盾」修掉；契约（对照表/端点）先行，渲染随后，挂载最后。
> 本计划须**人批准**后才能落任务卡（reqboard_decompose）。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点 | 需求条款 |
| I-x | interfaces.md 接口清单（§I-1…I-5） | 接口 |
| FE-x | frontend.md 页面与组件编号表 | 页面 / 组件 |
| BE-x | backend.md 服务与接口实现编号表 | 服务/模块 |
| UC-x | use-cases.md 主流程 | 用户场景 |
| TC-x | test-cases.md 用例表 | 测试用例 |
| t-x | 本文档任务表 | 任务 |

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| t1 | （落库后回填） | 建立执行流程对照表与求值器 | FR-6 | I-4 + src/client/node-panel-process.ts | implement | frontend | — | M | `pnpm vitest run tests/node-panel-process-map.test.ts` 全绿；STAGE_PROCESS 覆盖 7 节点 |
| t2 | （落库后回填） | 新增 isolation-log 只读端点并接线 | FR-6 | I-1 + src/http/routers/isolation.ts、routes.ts、src/index.ts | implement | backend | — | S | `pnpm vitest run tests/isolation-router.test.ts` 全绿（k 校验/降级/窗口过滤） |
| t3 | （落库后回填） | progress 接口透出 promptDifficulty | FR-2 | I-2 + src/http/routers/stages.ts | implement | backend | — | S | TC-10 对应断言全绿（有/无字段两种记录） |
| t4 | （落库后回填） | 实现节点面板渲染器 node-panel.ts | FR-1, FR-2, FR-3, FR-4, FR-5, FR-9 | I-3 + src/client/node-panel.ts | implement | frontend | t1 | M | `pnpm vitest run tests/node-panel.test.ts` 全绿（TC-1…TC-6） |
| t5 | （落库后回填） | 新增苹果风样式分片并接入拼接链 | FR-7, FR-8 | frontend.md 样式与主题节 + src/client/styles/node-panel.ts、styles.ts | ui | frontend | t4 | M | `pnpm build:client` 通过（wrap+verify 哨兵绿）+ TC-11 全绿 |
| t6 | （落库后回填） | 把新面板挂进会话流程条 | FR-1, FR-6, FR-9 | FE-1/FE-6/FE-7 + src/client/conversation-progress.ts、api.ts | implement | frontend | t2, t3, t4, t5 | M | 构建+重启后实测：点节点开面板、×/外点关闭、tab 切换、open-doc 打开文档（UC-1/UC-4/UC-5） |
| t7 | （落库后回填） | 修复六份 brainstorming 模板消除门禁矛盾 | FR-10 | backend.md 不适用；templates/brainstorming/*.md ×6 + tests/template-clause-gate.test.ts | implement | fullstack | — | M | `pnpm vitest run tests/template-clause-gate.test.ts` 全绿；`grep -c 'G[12]' templates/brainstorming/bug.md` 目标表处为 0 |
| t8 | （落库后回填） | 构建发布并做浏览器整体验收 | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 | 全部落点 | test | fullstack | t6, t7 | S | `pnpm vitest run` 全量绿 + `pnpm build` 绿 + 需求文档「验收标准（整体）」8 步实测通过 |

## 覆盖对照

| 需求条款 | 接口（interfaces） | 页面/模块（frontend/backend） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 | I-3（1） | FE-1, FE-6, FE-7（3） | TC-6（1） | t4, t6（2） | ✅ |
| FR-2 | I-2, I-3（2） | FE-2（1） | TC-1, TC-10（2） | t3, t4（2） | ✅ |
| FR-3 | I-3（1） | FE-3（1） | TC-2, TC-3（2） | t4（1） | ✅ |
| FR-4 | I-3（1） | FE-3（1） | TC-3（1） | t4（1） | ✅ |
| FR-5 | I-3（1） | FE-4（1） | TC-2（1） | t4（1） | ✅ |
| FR-6 | I-1, I-4（2） | FE-5, BE-1, BE-2, BE-3, BE-4（5） | TC-4, TC-5, TC-7, TC-9（4） | t1, t2, t6（3） | ✅ |
| FR-7 | I-3（1） | FE-4（1） | TC-2（1） | t4, t5（2） | ✅ |
| FR-8 | —（纯样式条款，无运行时接口） | frontend.md 样式与主题节（1） | TC-11（1） | t5（1） | ✅ |
| FR-9 | I-3（1） | FE-6（1） | TC-6（1） | t6（1） | ✅ |
| FR-10 | —（纯模板+测试条款，无运行时接口） | —（改 templates/ 与 tests/，无运行时模块） | TC-8（1） | t7（1） | ✅ |
| **合计** | I-1…I-4 全部有主（4） | FE/BE 全部有主（9） | TC-1…TC-11 全部有主（11） | 8 任务 | 10/10 条款有主 |

## 覆盖完整性规则执行说明

- FR-8 / FR-10 的「接口」格写 ——：纯样式 / 纯模板条款，无运行时接口（括号已注理由），与规则 1 的豁免口径一致。
- 反向检查：I-1…I-4、FE-1…FE-8、BE-1…BE-4、TC-1…TC-11 均在上表有人认领，无超范围设计。
- 依赖安全序：t1/t2/t3/t7 无依赖先行；t4 依赖 t1（对照表契约）；t5 依赖 t4（样式对着真实结构写）；t6 依赖 t2/t3/t4/t5（挂载要数据与样式就位）；t8 收尾。
