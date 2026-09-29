# t-dbed64 集成测试与文档·联调

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
集成测试与文档·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-dbed64.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

## 汇报 1（2026-09-28T05:49:55.631Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【联调·链执行回填】集成测试与文档·联调：接口联调（本卡验收项）通过：对 integration.ts 的 7 组对外接口逐一给出「请求样例 → 期望响应 → 实际返回」，25/25 一致（探针 docs/requirements/REQ-260928001915-f978/demo/__probe-t-dbed64.ts，exit 0）。逐条：I1 validateQueueFile(passed=true,issues=0)；I2 resolveTasks(parent=1/child=2/solo=3, tA.kids=[tA1,tA2])；I3 findCriticalPath(集合={tA,tB,tD},size=3) 与 detectCycle(null)；I4 renderDagHtml(nodes=6,cards=6,paths=4,e-crit=2,e-done=1,card-chain=1,ready-dot=1；focus=true 时 nodes=3/paths=2)；I5 calculateLayout(pos=6)+hitTest(命中 tA / 空白 null)；I6 降级(有环→‘循环依赖’、空图→‘暂无任务’、坏数据→V-2,V-3,V-6)；I7 createDagViewer(不抛异常,pos=6,事件 3/3,dir→horizontal,visible=3,destroy 解绑)。

### 完成项

- 接口联调（本卡验收项）通过：对 integration.ts 的 7 组对外接口逐一给出「请求样例 → 期望响应 → 实际返回」，25/25 一致（探针 docs/requirements/REQ-260928001915-f978/demo/__probe-t-dbed64.ts，exit 0）。逐条：I1 validateQueueFile(passed=true,issues=0)；I2 resolveTasks(parent=1/child=2/solo=3, tA.kids=[tA1,tA2])；I3 findCriticalPath(集合={tA,tB,tD},size=3) 与 detectCycle(null)；I4 renderDagHtml(nodes=6,cards=6,paths=4,e-crit=2,e-done=1,card-chain=1,ready-dot=1；focus=true 时 nodes=3/paths=2)；I5 calculateLayout(pos=6)+h…
- 端到端集成测试 81/81 通过（integration.test.ts，四档真实队列：本需求 40 卡 / 小图 12 卡 / 中图 20 卡 / 压力 65 卡），逐 FR-1…FR-7 断言全部 ok。
- 一键构建 build-demo.py 退出码 0：四轴频次统计 + esbuild 打 integration.ts 为 IIFE(window.DagDemo) + selftest.mjs 104/104 全绿 + 写出 dag-card-types-demo.html（120,688 字节；UTF-8 字符数 110,846）。
- 产物注入联调通过：构建产物内联 bundle 经 node --check 语法通过；bundle 暴露 77 个导出、21 个模块符号全部在场；无残留 __DATA_JSON__ / /*__DAG_BUNDLE__*/ 注入标记；template.html 实际消费的 7 个符号（PHASE_LABEL/STATUS_LABEL/STAGE_LABEL/SIDE_LABEL/esc/cardHtml/createDagViewer）在 IIFE 全局上类型全部匹配；四档数据集标签齐全；bundle 内无未转义 </script>。
- 逐模块单测四份退出码均 0：dag-layout / critical-path(36/36) / interaction / edge-renderer。
- 父卡验收结果复核：demo/*.ts 计数 17（≥7）；dag-card-types-demo.html 存在；README.md 含 'python3'(1) 与 'build-demo.py'(2)。
- 边界说明：本阶段为接口层联调，未做浏览器可视化人工目检——Canvas 与 DOM 双后端已在 Node 假 canvas / 渲染字符串逐接口断言，真机目检留给测试子卡(t-66570e)。

### 改动文件

- `docs/requirements/REQ-260928001915-f978/demo/__probe-t-dbed64.ts`
- `docs/requirements/REQ-260928001915-f978/demo/dag-card-types-demo.html`

---
