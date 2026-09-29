# t-cf42de 集成测试与文档·研发

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
集成测试与文档·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/integration.ts` ≥ 1，且文件中含本模块的导出函数名。

## 汇报 1（2026-09-28T05:49:40.683Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【研发·链执行回填】集成测试与文档·研发：定位并修复集成构建断链：修复前 python3 demo/build-demo.py 退出码 5（[汇总] 102 通过 / 1 失败，失败项「无 parentId 且无子卡 -> solo」）。根因＝该断言把「本需求队列恰好含独立卡」当测试前提，而队列随拆分推进已变成 40 卡 = 8 父卡 + 32 子卡、solo=0，测的是数据构型而非模块契约。改法：solo 判定改用合成样例（与队列构型解耦），并新增「真实队列角色三分覆盖且互斥」不变量（parentN=parentId 去重数、childN=含 parentId 数、三者之和=任务数）。

### 完成项

- 定位并修复集成构建断链：修复前 python3 demo/build-demo.py 退出码 5（[汇总] 102 通过 / 1 失败，失败项「无 parentId 且无子卡 -> solo」）。根因＝该断言把「本需求队列恰好含独立卡」当测试前提，而队列随拆分推进已变成 40 卡 = 8 父卡 + 32 子卡、solo=0，测的是数据构型而非模块契约。改法：solo 判定改用合成样例（与队列构型解耦），并新增「真实队列角色三分覆盖且互斥」不变量（parentN=parentId 去重数、childN=含 parentId 数、三者之和=任务数）。
- build-demo.py 四档数据集标签对齐父卡口径与 README：小图 · 12 卡 7 层 / 中图 · 20 卡 5 层 / 压力 · 65 卡 12 层 83 边（原标签只写线索特征，与 README「小图 12 卡 / 中图 20 卡 / 压力 65 卡」不一致）。
- 新增 demo/integration.test.ts：只走集成入口（validateQueueFile → resolveTasks → renderDagHtml / createDagViewer），用四档真实队列（本需求 / 小图 12 卡 / 中图 20 卡 / 压力 65 卡）逐 FR-1…FR-7 做端到端断言，81/81 全绿。覆盖：V-1..V-6 校验、角色派生与父卡 kids、卡数=任务数、节点数=任务数、SVG 边线条数=edges 数、子卡链条数=父卡数、ready 绿点=ready[] 数、关键路径⊆任务集且非空、只看主线收缩到关键路径、Canvas 视图绑事件/切方向/销毁、小图与压力档覆盖、环/空图/悬空边降级负向对照。路径定位与 cwd 解耦并做「目录名必须等于 req」防串档。
- README.md 新增「单独跑测试（不构建）」章节（4 个模块单测 + 集成测试的 npx tsx 命令），修正数据集口径，补充 selftest 角色派生与 integration.test.ts 覆盖说明。
- 回归验证全绿：build-demo.py 退出码 0（104/0）并重新生成 dag-card-types-demo.html（连续两次构建 sha256 一致＝幂等）；4 个模块单测 25/36/36/48 全绿；tsc 全绿；在需求目录与 agent-dh 仓库根两种 cwd 下集成测试均 81/81。

### 改动文件

- `docs/requirements/REQ-260928001915-f978/demo/selftest.mjs`
- `docs/requirements/REQ-260928001915-f978/demo/build-demo.py`
- `docs/requirements/REQ-260928001915-f978/demo/integration.test.ts`
- `docs/requirements/REQ-260928001915-f978/demo/README.md`
- `docs/requirements/REQ-260928001915-f978/demo/dag-card-types-demo.html`

---
