# 测试证据 · REQ-260923134706-e72f

> 采集时间：2026-09-23 20:02–20:26 ｜ 采集人：实施窗口 session-f3978f17（本需求 t-9a5797）

## 1. 本需求单元测试（全绿）

```
$ cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run \
    tests/node-panel.test.ts tests/node-panel-styles.test.ts tests/node-panel-process-map.test.ts \
    tests/isolation-router.test.ts tests/template-clause-gate.test.ts tests/session-progress.test.ts

 ✓ tests/node-panel-styles.test.ts      (12 tests)
 ✓ tests/template-clause-gate.test.ts    (5 tests)   ← FR-10：六份模板定义行可解析 + 前缀正确 + feature 模板覆盖策略必填节
 ✓ tests/node-panel.test.ts              (21 tests)  ← TC-1…TC-6：六节点基础信息 / 头两行 / 双视图
 ✓ tests/node-panel-process-map.test.ts  (10 tests)  ← FR-6 防漂移：对照表 cite 逐条能在阶段片段语料里找到
 ✓ tests/isolation-router.test.ts         (6 tests)  ← I-1：isolation-log 只读端点（k 校验/降级/窗口过滤）
 ✓ tests/session-progress.test.ts         (4 tests)  ← FR-2：promptDifficulty 透出（有/无字段两种记录）
 Test Files  6 passed (6)
      Tests  58 passed (58)
```

## 2. 构建与发布

```
$ cd agent-dh/packages/web/dsh-pmboard && pnpm build
✔ dist/index.mjs 707.64 kB（宿主半）
wrapped dsh-pmboard -> lib/client.js 265667 bytes
[verify-client] OK  bundle=284583 bytes, 关键符号齐全, styles.ts 括号配对

$ bash agent-dh/scripts/restart-with-build.sh --check
OK   dsh-pmboard  ./dist/index.mjs  (707639 bytes)
---- dist 产物校验：20/20 通过
状态统计: symlink-ok=3
```

实例：:13080 监听中，pid 88598（启动于 2026-09-23 20:20:20）。
说明：20:20 重启后于 20:02→20:24 期间对 `src/client/node-panel-process.ts` 做过一次**不改变行为**的行数裁剪（402→399 行，为过尺寸门禁），产物已重建并通过上面的新鲜度检查；浏览器实际加载的 bundle 含新面板符号（`np-act-mark`、DAG 泳道 tab）。

## 3. 浏览器整体验收（无头探针 = playwright + 真实登录 cookie）

```
$ /Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py
→ 报告：packages/web/dsh-pmboard/scripts/.probe/acceptance-report.json
→ 截图：a1-impl-panel / a2-swimlane / a3-narrow-swimlane / a4-taskcard / a5-fragment-sidebar /
        a6-process-fold / a7-stage-{立项,需求分析,设计,拆分,验收,归档} / a8-board（同名 .png）
```

| 需求「验收标准（整体）」步骤 | 探针读数 | 结论 |
|---|---|---|
| ① 打开 :13080 进入绑定需求的会话 | 探针用 HMAC cookie 登录成功；流程条节点 = 立项/需求分析/设计/拆分/实施/验收/归档 | ✅ |
| ② 点「实施」→ 面板锚定展开、无遮罩、无底栏、有 × | gap=8px；rightDelta=0；fixedOverlays=0；底部按钮命中=[]；关闭按钮存在=true | ✅ FR-1/FR-9 |
| ③ 面板头两行 | REQ-260923134706-e72f + 标题 / 「实施中」+「7/8 完成 · 剩 1 个 · 进行中 t-9a5797」+「5 小时前」 | ✅ FR-2 |
| ④ 切「泳道」→ 6 列卡片正常、无裁切；切回分层视图 | 6 列（0/1/0/0/0/7）、列宽 220 等宽、列内 overflow-y=auto、越界卡片=[]；窄屏 1000 仍等宽、最右 937<1000；默认 tab = DAG(默认) | ✅ FR-7/FR-5 |
| ⑤ 点任务节点 → 右侧栏打开任务卡 | 右栏内容 = t-256ac4.md（/Users/yunpeng/.../tasks/t-256ac4.md） | ✅ |
| ⑥ 六节点「基础信息」内容符合 FR-4 | 立项=需求描述/分类/文档位置…；需求分析=需求文档条目；设计=✅ 5 份设计文档；拆分=decomposition.md + 📊 DAG 层级；验收=「尚未提交验收材料」（诚实空态）；归档=「暂无归档材料」（诚实空态，本需求未归档） | ✅（2 处诚实空态见评审报告） |
| ⑦ 执行流程三段 + 真实留痕 | 三段标题齐；动作 ✅3/⬜1 带出处；上下文管理 = REPLACED · 输入包 17760 字符 · range[10498,11432]；片段 implementing/light.md 右栏打开真实文件（无 File not found） | ✅ FR-6 |
| ⑧ 点面板外收起；看板页外观不变 | 点面板外 → 面板消失=true；项目看板页 has_board=true、6 lanes、pageerror=[] | ✅ FR-1 / 边界① |
| ⑨ template-clause-gate 全绿 | 见 §1（5 passed） | ✅ FR-10 |

## 4. 全量回归的红灯与出处（如实列出，未擅自改动计划外文件）

```
$ cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run
 Test Files  7 failed | 138 passed (145)
      Tests  8 failed | 1739 passed (1747)
```

| 失败文件 | 失败用例 | 归因 | 归属 |
|---|---|---|---|
| size-budget.test.ts | src 下 .ts ≤400 行 | 本卡引入的 `client/node-panel-process.ts` 402 行 → **已修到 399**；残留 `src/index.ts` 429 行 | 本卡部分已修；残留为**既有红**：`git show HEAD:…/src/index.ts \| wc -l` = 415（>400，且不在 WHITELIST） |
| template-address-injection.test.ts | TC-9 地址段三处逐字一致 | 工作区未提交的「地址段注入」线（`src/domain/template/**`、`src/adapters/TemplateRoot.ts`） | 并行工作线 |
| typecheck.test.ts | tsc 15 个类型错误 | 同上：`src/domain/template/{render,resolve}.ts`、`src/application/internal/node-input-package.ts` | 并行工作线 |
| layer-boundary.test.ts | application/ 越界 import | `application/internal/diag-log.ts -> node:fs / node:path` | 并行工作线 |
| client-view.test.ts | buildBoard 归档栏 | `src/client/views/board.ts` 删掉 54 行（待归类区/归档栏相关） | 并行工作线 |
| design-completeness-gate.test.ts | 2 例 | design 文档集门禁行为变化 | 并行工作线 |
| application/repository.test.ts | RandomIdFactory 格式 | ID 生成格式改为 `REQ-<ts>-<hex4>`，测试仍期望旧格式 | 并行工作线 |

> 上述 6 个文件均不在本需求任务卡的文件范围内（本需求边界明确「不改看板其他页面」），故未改动；如需修复应开独立卡，避免与并行工作线冲突。

## 5. 目测项（需人工，agent 无法代替）

探针只能证明「数字与布尔事实」，以下观感项请人看截图确认：苹果风留白/层级、白底文档列表质感、无粗重投影、泳道卡片密度、窄屏观感 —— 见 §3 的 a1..a8 截图。
