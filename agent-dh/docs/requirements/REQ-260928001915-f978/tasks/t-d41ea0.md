# t-d41ea0 实现 DAG 布局引擎·测试

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
实现 DAG 布局引擎·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/dag-layout.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

## 汇报 1（2026-09-28T05:49:34.442Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【测试·链执行回填】实现 DAG 布局引擎·测试：测试卡 t-d41ea0（实现 DAG 布局引擎·测试）结论：目标命令全绿，FR-3 布局引擎通过测试门。本卡为测试阶段·结论族，未改动仓库任何文件（filesChanged=[]）。

### 完成项

- 测试卡 t-d41ea0（实现 DAG 布局引擎·测试）结论：目标命令全绿，FR-3 布局引擎通过测试门。本卡为测试阶段·结论族，未改动仓库任何文件（filesChanged=[]）。
- 目标命令 npx tsx demo/dag-layout.test.ts → 25 通过 / 0 失败，退出码 0：覆盖 [1] 12卡3层节点坐标完备、[2] 纵向层级自上而下+同层折行、[3] 横向层级自左向右+同层纵向堆叠(MAX_ROWS=8)、[4] 画布尺寸自适应且节点落在界内、[5] 缺 layer 降级第0层、[6] hitTest 命中/容差、[7] 纯函数回归（无 _bary 污染、确定性）。
- 编译门 npx tsc demo/dag-layout.ts --noEmit → 退出码 0（无诊断）；npx tsc demo/dag-layout.test.ts --noEmit → 退出码 0。
- 父卡 t-4256bf 验收复核：grep -c "'vertical'\|'horizontal'" demo/dag-layout.ts = 5（≥2 达标）；grep -c 'export function calculateLayout' = 1。
- 被测文件哈希：dag-layout.ts sha256 35c23913c2e4f8f3bca8e02ed891951211ebc82b54e7b7a63e82e3e66ba9b19d；dag-layout.test.ts sha256 17d3b92b03c174a4782fe8790b225e5ebb738d8b67387b1fa7428750d8026941（与复核卡记录一致，测试期间未变）。

---
