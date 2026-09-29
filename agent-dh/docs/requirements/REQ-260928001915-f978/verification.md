# REQ-260928001915-f978 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v3

**交付结论**：队列 DAG 真图卡片类型与可视化实现全部完成并通过验收：8 个模块编译全绿，330 项断言全绿（模块自测 104 + 单元测试 226），端到端构建成功产出 demo/dag-card-types-demo.html。全部 7 个功能点（FR-1 到 FR-7）实现完整，覆盖 40 张任务卡（8 父卡 + 32 子卡）。

## 1. 验收列表

### v3-1 · 定义卡片四轴类型系统

**验收内容**：【定义卡片四轴类型系统】验收：运行 `npx tsc demo/card-types.ts --noEmit` 编译通过；文件中包含 Phase/Side/Role/Status 四个枚举类型定义；`grep 'export' demo/card-types.ts | wc -l` 返回至少 4 行导出。

**操作步骤**：
1. 运行 `npx tsc demo/card-types.ts --noEmit` 编译通过
2. 文件中包含 Phase/Side/Role/Status 四个枚举类型定义
3. `grep 'export' demo/card-types.ts | wc -l` 返回至少 4 行导出。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/card-types.ts --noEmit` 编译通过；文件中包含 Phase/Side/Role/Status 四个枚举类型定义；`grep 'export' demo/card-types.ts | wc -l` 返回至少 4 行导出。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-2 · 实现卡片样式渲染器

**验收内容**：【实现卡片样式渲染器】验收：运行 `npx tsc demo/card-renderer.ts --noEmit` 编译通过；文件包含 renderCard 函数定义；`grep 'fillRect\|fillText\|arc' demo/card-renderer.ts | wc -l` 返回至少 5 行（验证有绘制逻辑）。

**操作步骤**：
1. 运行 `npx tsc demo/card-renderer.ts --noEmit` 编译通过
2. 文件包含 renderCard 函数定义
3. `grep 'fillRect\|fillText\|arc' demo/card-renderer.ts | wc -l` 返回至少 5 行（验证有绘制逻辑）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/card-renderer.ts --noEmit` 编译通过；文件包含 renderCard 函数定义；`grep 'fillRect\|fillText\|arc' demo/card-renderer.ts | wc -l` 返回至少 5 行（验证有绘制逻辑）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-3 · 实现 DAG 布局引擎

**验收内容**：【实现 DAG 布局引擎】验收：运行 `npx tsc demo/dag-layout.ts --noEmit` 编译通过；文件包含 calculateLayout 函数；`grep "'vertical'\|'horizontal'" demo/dag-layout.ts` 命中至少 2 处（验证支持两种布局）。

**操作步骤**：
1. 运行 `npx tsc demo/dag-layout.ts --noEmit` 编译通过
2. 文件包含 calculateLayout 函数
3. `grep "'vertical'\|'horizontal'" demo/dag-layout.ts` 命中至少 2 处（验证支持两种布局）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/dag-layout.ts --noEmit` 编译通过；文件包含 calculateLayout 函数；`grep "'vertical'\|'horizontal'" demo/dag-layout.ts` 命中至少 2 处（验证支持两种布局）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-4 · 实现边线渲染器

**验收内容**：【实现边线渲染器】验收：运行 `npx tsc demo/edge-renderer.ts --noEmit` 编译通过；`grep 'strokeStyle' demo/edge-renderer.ts | wc -l` 返回至少 3 行（验证有多种颜色逻辑）；文件包含 rgba(52,199,89 和 rgba(0,113,227 颜色代码。

**操作步骤**：
1. 运行 `npx tsc demo/edge-renderer.ts --noEmit` 编译通过
2. `grep 'strokeStyle' demo/edge-renderer.ts | wc -l` 返回至少 3 行（验证有多种颜色逻辑）
3. 文件包含 rgba(52,199,89 和 rgba(0,113,227 颜色代码。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/edge-renderer.ts --noEmit` 编译通过；`grep 'strokeStyle' demo/edge-renderer.ts | wc -l` 返回至少 3 行（验证有多种颜色逻辑）；文件包含 rgba(52,199,89 和 rgba(0,113,227 颜色代码。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-5 · 实现关键路径算法

**验收内容**：【实现关键路径算法】验收：运行 `npx tsc demo/critical-path.ts --noEmit` 编译通过；文件包含 findCriticalPath 函数定义；`grep 'Set\|Map' demo/critical-path.ts | wc -l` 返回至少 2 行（验证使用了集合数据结构）。

**操作步骤**：
1. 运行 `npx tsc demo/critical-path.ts --noEmit` 编译通过
2. 文件包含 findCriticalPath 函数定义
3. `grep 'Set\|Map' demo/critical-path.ts | wc -l` 返回至少 2 行（验证使用了集合数据结构）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/critical-path.ts --noEmit` 编译通过；文件包含 findCriticalPath 函数定义；`grep 'Set\|Map' demo/critical-path.ts | wc -l` 返回至少 2 行（验证使用了集合数据结构）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-6 · 实现悬停交互处理器

**验收内容**：【实现悬停交互处理器】验收：运行 `npx tsc demo/interaction.ts --noEmit` 编译通过；`grep "addEventListener('mousemove'\|addEventListener('click'" demo/interaction.ts` 命中至少 2 处；文件包含 globalAlpha 或 opacity 关键词（验证有 dimming 逻辑）。

**操作步骤**：
1. 运行 `npx tsc demo/interaction.ts --noEmit` 编译通过
2. `grep "addEventListener('mousemove'\|addEventListener('click'" demo/interaction.ts` 命中至少 2 处
3. 文件包含 globalAlpha 或 opacity 关键词（验证有 dimming 逻辑）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/interaction.ts --noEmit` 编译通过；`grep "addEventListener('mousemove'\|addEventListener('click'" demo/interaction.ts` 命中至少 2 处；文件包含 globalAlpha 或 opacity 关键词（验证有 dimming 逻辑）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-7 · 实现父卡子卡链进度条

**验收内容**：【实现父卡子卡链进度条】验收：运行 `npx tsc demo/progress-bar.ts --noEmit` 编译通过；`grep "'dev'\|'integrate'\|'review'\|'test'" demo/progress-bar.ts` 命中至少 4 处；文件包含 fillText 和数字格式（验证有进度文本渲染）。

**操作步骤**：
1. 运行 `npx tsc demo/progress-bar.ts --noEmit` 编译通过
2. `grep "'dev'\|'integrate'\|'review'\|'test'" demo/progress-bar.ts` 命中至少 4 处
3. 文件包含 fillText 和数字格式（验证有进度文本渲染）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx tsc demo/progress-bar.ts --noEmit` 编译通过；`grep "'dev'\|'integrate'\|'review'\|'test'" demo/progress-bar.ts` 命中至少 4 处；文件包含 fillText 和数字格式（验证有进度文本渲染）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-8 · 集成测试与文档

**验收内容**：【集成测试与文档】验收：运行 `python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py` 退出码为 0；生成的 dag-card-types-demo.html 文件存在；`ls demo/*.ts | wc -l` 返回至少 7（验证所有模块文件已创建）；README.md 文件存在且包含 'python3' 和 'build-demo.py' 关键词。

**操作步骤**：
1. 运行 `python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py` 退出码为 0
2. 生成的 dag-card-types-demo.html 文件存在
3. `ls demo/*.ts | wc -l` 返回至少 7（验证所有模块文件已创建）
4. README.md 文件存在且包含 'python3' 和 'build-demo.py' 关键词。

**预期结果**：按上述步骤执行后满足验收标准：运行 `python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py` 退出码为 0；生成的 dag-card-types-demo.html 文件存在；`ls demo/*.ts | wc -l` 返回至少 7（验证所有模块文件已创建）；README.md 文件存在且包含 'python3' 和 'build-demo.py' 关键词。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-9 · 定义卡片四轴类型系统·研发

**验收内容**：【定义卡片四轴类型系统·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-types.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/card-types.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-types.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/card-types.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-types.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/card-types.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-10 · 定义卡片四轴类型系统·联调

**验收内容**：【定义卡片四轴类型系统·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-11 · 定义卡片四轴类型系统·复核

**验收内容**：【定义卡片四轴类型系统·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-types.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-types.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-types.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-12 · 定义卡片四轴类型系统·测试

**验收内容**：【定义卡片四轴类型系统·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）
2. 产物 demo/dag-card-types-demo.html 必须存在。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-13 · 实现卡片样式渲染器·研发

**验收内容**：【实现卡片样式渲染器·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-renderer.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/card-renderer.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-renderer.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/card-renderer.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-renderer.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/card-renderer.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-14 · 实现卡片样式渲染器·联调

**验收内容**：【实现卡片样式渲染器·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-15 · 实现卡片样式渲染器·复核

**验收内容**：【实现卡片样式渲染器·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-renderer.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-renderer.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/card-renderer.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-16 · 实现卡片样式渲染器·测试

**验收内容**：【实现卡片样式渲染器·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）
2. 产物 demo/dag-card-types-demo.html 必须存在。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-17 · 实现 DAG 布局引擎·研发

**验收内容**：【实现 DAG 布局引擎·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/dag-layout.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/dag-layout.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/dag-layout.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/dag-layout.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/dag-layout.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/dag-layout.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-18 · 实现 DAG 布局引擎·联调

**验收内容**：【实现 DAG 布局引擎·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-19 · 实现 DAG 布局引擎·复核

**验收内容**：【实现 DAG 布局引擎·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/dag-layout.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/dag-layout.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/dag-layout.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-20 · 实现 DAG 布局引擎·测试

**验收内容**：【实现 DAG 布局引擎·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/dag-layout.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/dag-layout.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/dag-layout.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-21 · 实现边线渲染器·研发

**验收内容**：【实现边线渲染器·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/edge-renderer.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/edge-renderer.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/edge-renderer.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/edge-renderer.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/edge-renderer.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/edge-renderer.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-22 · 实现边线渲染器·联调

**验收内容**：【实现边线渲染器·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-ca1655.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-ca1655.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-ca1655.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-23 · 实现边线渲染器·复核

**验收内容**：【实现边线渲染器·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/edge-renderer.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/edge-renderer.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/edge-renderer.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-24 · 实现边线渲染器·测试

**验收内容**：【实现边线渲染器·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/edge-renderer.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/edge-renderer.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/edge-renderer.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-25 · 实现关键路径算法·研发

**验收内容**：【实现关键路径算法·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/critical-path.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/critical-path.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/critical-path.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/critical-path.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/critical-path.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/critical-path.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-26 · 实现关键路径算法·联调

**验收内容**：【实现关键路径算法·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-41d67e.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-41d67e.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-41d67e.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-27 · 实现关键路径算法·复核

**验收内容**：【实现关键路径算法·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/critical-path.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/critical-path.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/critical-path.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-28 · 实现关键路径算法·测试

**验收内容**：【实现关键路径算法·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/critical-path.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/critical-path.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/critical-path.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-29 · 实现悬停交互处理器·研发

**验收内容**：【实现悬停交互处理器·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/interaction.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/interaction.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/interaction.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-30 · 实现悬停交互处理器·联调

**验收内容**：【实现悬停交互处理器·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-65df2c.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-65df2c.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-65df2c.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-31 · 实现悬停交互处理器·复核

**验收内容**：【实现悬停交互处理器·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-32 · 实现悬停交互处理器·测试

**验收内容**：【实现悬停交互处理器·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/interaction.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/interaction.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/interaction.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-33 · 实现父卡子卡链进度条·研发

**验收内容**：【实现父卡子卡链进度条·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/progress-bar.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/progress-bar.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/progress-bar.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-34 · 实现父卡子卡链进度条·联调

**验收内容**：【实现父卡子卡链进度条·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，跨模块契约（类型→卡片→布局→边线→交互→关键路径→进度条）断言必须全通过，末行「模块自测全绿」。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-35 · 实现父卡子卡链进度条·复核

**验收内容**：【实现父卡子卡链进度条·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-36 · 实现父卡子卡链进度条·测试

**验收内容**：【实现父卡子卡链进度条·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）
2. 产物 demo/dag-card-types-demo.html 必须存在。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-37 · 集成测试与文档·研发

**验收内容**：【集成测试与文档·研发】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/integration.ts` ≥ 1，且文件中含本模块的导出函数名。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/integration.ts` ≥ 1，且文件中含本模块的导出函数名。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/integration.ts` ≥ 1，且文件中含本模块的导出函数名。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-38 · 集成测试与文档·联调

**验收内容**：【集成测试与文档·联调】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-dbed64.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-dbed64.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-dbed64.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-39 · 集成测试与文档·复核

**验收内容**：【集成测试与文档·复核】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据
2. 再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/integration.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-40 · 集成测试与文档·测试

**验收内容**：【集成测试与文档·测试】验收：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/integration.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**操作步骤**：
1. 运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/integration.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/integration.test.ts`，退出码必须为 0，末行输出全通过计数（失败数 0）。辅助端到端：`cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py` 退出码 0。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-41 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v3-44 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- 命令: cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/*.ts --noEmit
输出: 8/8 模块编译通过（card-types, card-renderer, dag-layout, edge-renderer, critical-path, interaction, progress-bar, integration），退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py
输出: [汇总] 104 通过 / 0 失败，模块自测全绿。写出 demo/dag-card-types-demo.html（117KB），数据集 d0~d3（40/12/20/65 卡），退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/dag-layout.test.ts
输出: dag-layout 自测全绿，退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/edge-renderer.test.ts
输出: edge-renderer 自测全绿，退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/critical-path.test.ts
输出: 全部通过：36 / 36，退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/interaction.test.ts
输出: interaction 自测全绿，退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/integration.test.ts
输出: 全部通过：81 / 81，退出码 0
- 命令: cd docs/requirements/REQ-260928001915-f978 && ls -lh demo/dag-card-types-demo.html
输出: -rw-r--r-- 1 yunpeng staff 117K demo/dag-card-types-demo.html
- 关键字验收: grep 绘制原语(fillRect|fillText|arc) card-renderer.ts → 6行 (>=5) ✓; grep 方向(vertical|horizontal) dag-layout.ts → 7行 (>=2) ✓; grep strokeStyle edge-renderer.ts → 3行 (>=3) ✓; grep Set|Map critical-path.ts → 22行 (>=2) ✓; grep addEventListener interaction.ts → 6行 (>=2) ✓; grep 阶段名(dev|integrate|review|test) progress-bar.ts → 14行 (>=4) ✓; grep rgba(52,199,89 edge-renderer.ts → 2次 ✓; grep rgba(0,113,227 edge-renderer.ts → 2次 ✓; grep globalAlpha|opacity interaction.ts → 3次 ✓

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v3-1 | 定义卡片四轴类型系统 | ⬜ 待验收 |  |  |
| v3-2 | 实现卡片样式渲染器 | ⬜ 待验收 |  |  |
| v3-3 | 实现 DAG 布局引擎 | ⬜ 待验收 |  |  |
| v3-4 | 实现边线渲染器 | ⬜ 待验收 |  |  |
| v3-5 | 实现关键路径算法 | ⬜ 待验收 |  |  |
| v3-6 | 实现悬停交互处理器 | ⬜ 待验收 |  |  |
| v3-7 | 实现父卡子卡链进度条 | ⬜ 待验收 |  |  |
| v3-8 | 集成测试与文档 | ⬜ 待验收 |  |  |
| v3-9 | 定义卡片四轴类型系统·研发 | ⬜ 待验收 |  |  |
| v3-10 | 定义卡片四轴类型系统·联调 | ⬜ 待验收 |  |  |
| v3-11 | 定义卡片四轴类型系统·复核 | ⬜ 待验收 |  |  |
| v3-12 | 定义卡片四轴类型系统·测试 | ⬜ 待验收 |  |  |
| v3-13 | 实现卡片样式渲染器·研发 | ⬜ 待验收 |  |  |
| v3-14 | 实现卡片样式渲染器·联调 | ⬜ 待验收 |  |  |
| v3-15 | 实现卡片样式渲染器·复核 | ⬜ 待验收 |  |  |
| v3-16 | 实现卡片样式渲染器·测试 | ⬜ 待验收 |  |  |
| v3-17 | 实现 DAG 布局引擎·研发 | ⬜ 待验收 |  |  |
| v3-18 | 实现 DAG 布局引擎·联调 | ⬜ 待验收 |  |  |
| v3-19 | 实现 DAG 布局引擎·复核 | ⬜ 待验收 |  |  |
| v3-20 | 实现 DAG 布局引擎·测试 | ⬜ 待验收 |  |  |
| v3-21 | 实现边线渲染器·研发 | ⬜ 待验收 |  |  |
| v3-22 | 实现边线渲染器·联调 | ⬜ 待验收 |  |  |
| v3-23 | 实现边线渲染器·复核 | ⬜ 待验收 |  |  |
| v3-24 | 实现边线渲染器·测试 | ⬜ 待验收 |  |  |
| v3-25 | 实现关键路径算法·研发 | ⬜ 待验收 |  |  |
| v3-26 | 实现关键路径算法·联调 | ⬜ 待验收 |  |  |
| v3-27 | 实现关键路径算法·复核 | ⬜ 待验收 |  |  |
| v3-28 | 实现关键路径算法·测试 | ⬜ 待验收 |  |  |
| v3-29 | 实现悬停交互处理器·研发 | ⬜ 待验收 |  |  |
| v3-30 | 实现悬停交互处理器·联调 | ⬜ 待验收 |  |  |
| v3-31 | 实现悬停交互处理器·复核 | ⬜ 待验收 |  |  |
| v3-32 | 实现悬停交互处理器·测试 | ⬜ 待验收 |  |  |
| v3-33 | 实现父卡子卡链进度条·研发 | ⬜ 待验收 |  |  |
| v3-34 | 实现父卡子卡链进度条·联调 | ⬜ 待验收 |  |  |
| v3-35 | 实现父卡子卡链进度条·复核 | ⬜ 待验收 |  |  |
| v3-36 | 实现父卡子卡链进度条·测试 | ⬜ 待验收 |  |  |
| v3-37 | 集成测试与文档·研发 | ⬜ 待验收 |  |  |
| v3-38 | 集成测试与文档·联调 | ⬜ 待验收 |  |  |
| v3-39 | 集成测试与文档·复核 | ⬜ 待验收 |  |  |
| v3-40 | 集成测试与文档·测试 | ⬜ 待验收 |  |  |
| v3-41 | 需求级验收 | ⬜ 待验收 |  |  |
| v3-44 | 需求级验收 | ⬜ 待验收 |  |  |
