---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10]
sides: [frontend, backend]
---

# 测试用例（REQ-260923134706-e72f）

## 1. 用例表 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-9, FR-10 -->

| 编号 | 用例（断言什么） | 实际文件 | serves |
|---|---|---|---|
| TC-1 | 面板头两层：REQ 胶囊 + 标题行、状态胶囊 + 一句话 + 相对时间；7 节点各自状态词正确 | tests/node-panel.test.ts | FR-2 |
| TC-2 | 基础信息折叠默认展开、执行流程默认收起；实施节点无基础信息块、有 [流程图][泳道] 切换 | tests/node-panel.test.ts | FR-3, FR-5 |
| TC-3 | 六节点基础信息内容：立项五字段 / 需求分析产物清单 / 设计逐份已交未交 / 拆分计划+DAG / 验收材料+验收单统计 / 归档徽标+合并去向+一句话结论 | tests/node-panel.test.ts | FR-4 |
| TC-4 | 执行流程三段齐全；提示词片段条目带 open-doc 且路径=真实文件；路由壳显示「含 N 个子片段」；无留痕显示空态 | tests/node-panel.test.ts | FR-6 |
| TC-5 | 执行动作对照：构造有/无台账记录的 StageDetail → ✅/⬜ 与出处文案正确（不冤枉 agent：无记录必须 ⬜） | tests/node-panel.test.ts | FR-6 |
| TC-6 | 面板 HTML 不含底部三按钮、不含遮罩层类；含 × 关闭按钮 | tests/node-panel.test.ts | FR-1, FR-9 |
| TC-7 | STAGE_PROCESS 防漂移：每条 cite 能在对应阶段片段语料（fragments/<stage>/**.md）里找到；每个 kind=file 的 promptRef 文件 existsSync | tests/node-panel-process-map.test.ts | FR-6 |
| TC-8 | 六份 brainstorming 模板的示范定义行被 DEF_LINE_RE 认出且前缀正确；feature 模板章节覆盖 requiredRootSectionsFor('feature') | tests/template-clause-gate.test.ts | FR-10 |
| TC-9 | isolation-log 路由：k 非法 → 400；端口未装配 → available=false + 空清单；window 过滤生效 | tests/isolation-router.test.ts | FR-6 |
| TC-10 | session progress 透出 promptDifficulty（有记录/无记录两种） | tests/api-client.test.ts 或 stages 路由测试 | FR-2 |
| TC-11 | 样式作用域隔离：styles/node-panel.ts 每条规则的选择器都在 .dsh-pm-np 作用域内（或 :root 变量定义），无裸全局选择器 | tests/node-panel-styles.test.ts | FR-8 |

## 2. 覆盖矩阵 <!-- serves: FR-1 -->

| FR | 单测 | 端到端（人工浏览器验收，步骤见验收标准整体） |
|---|---|---|
| FR-1 锚定下拉/无遮罩/外点关闭 | TC-6（结构断言） | 步骤 2、8 |
| FR-2 面板头 | TC-1, TC-10 | 步骤 3 |
| FR-3 基础信息折叠 | TC-2, TC-3 | 步骤 6 |
| FR-4 六节点内容 | TC-3 | 步骤 5、6 |
| FR-5 实施双视图 | TC-2 | 步骤 4、5 |
| FR-6 执行流程对照 | TC-4, TC-5, TC-7, TC-9 | 步骤 7 |
| FR-7 泳道 | TC-2（结构） | 步骤 4（窄窗口无裁切） |
| FR-8 苹果风/720px | TC-11（作用域隔离） | 步骤 2、8 目测 |
| FR-9 无底栏 | TC-6 | 步骤 2 |
| FR-10 模板门禁一致 | TC-8 | 本需求自身过 G2 即实测 |

## 3. 验收命令 <!-- serves: FR-1 -->

```bash
cd agent-dh/packages/web/dsh-pmboard
pnpm vitest run tests/node-panel.test.ts tests/node-panel-process-map.test.ts tests/template-clause-gate.test.ts tests/isolation-router.test.ts
pnpm vitest run                                  # 全量回归（不破坏既有测试）
pnpm build                                       # host + client 构建（dist/index.mjs + lib/client.js）
```

浏览器人工验收 = 需求文档「验收标准（整体）」8 步（:13080 需重启后硬刷新）。
