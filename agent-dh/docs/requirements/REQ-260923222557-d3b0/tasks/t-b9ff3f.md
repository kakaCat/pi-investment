# t-b9ff3f 测试补齐与全量回归

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
测试补齐与全量回归

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
pmboard vitest 全绿（含 TC-1..TC-8）；plugin-schema 冒烟通过；无新增失败（与基线对照）。

## 实施方案（implementation）
补齐所有用例后：cd packages/web/dsh-pmboard && npx vitest run；再跑 agent-dh 根 plugin-schema.smoke.test.ts。验证：两套件全绿。

## 上游产出摘要（dependsSummary）
- 弹框超时调整为 1 小时（domain 常量单点修改）
- worktree 提示词文本三份（implementing 路由档 + task_done/archived 事件常量）
- 子任务完成与归档两处事件注入接线
- 面板头部：进展胶囊与状态词修正
- 面板文档行：已交可点、未交占位

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T15:56:04.498Z，窗口 session-959cebfe-094f-4f09-894d-20a5c35d4d62）

本需求 8 条验收用例全部有断言跑得起来（TC-1..TC-8），故障注入（投递失败不阻断转移、旧 plan 兼容）也在内；全量回归同一时刻被隔壁窗口的在飞重构拖着 9 条红色，逐条核过——没有一条是本需求引入的。

### 完成项

- TC-1..TC-5（头部取词与状态词）：tests/stage-panel.test.ts + tests/node-panel.test.ts 新断言，绿
- TC-6/TC-7（文档行可点/未交占位）：tests/node-panel.test.ts 新断言，绿
- TC-8 补齐（此前只改了值没有门）：tests/concurrency-limits.test.ts 新增——两常量 = 3_600_000，且全 src 扫描无旧 600_000/900_000 残留；扫描器自带「命中文件数 > 50」自检防目录失效假绿；正则用 \b 边界，3_600_000 不会误判（已用独立脚本证明：3_600_000 不命中、裸 600_000/900_000 命中）
- 故障注入：tests/worktree-injection.test.ts 5 条（投递失败仍完成转移、无端口不阻断、非 done 不言、两条事件路径各一次）全绿
- plugin-schema 冒烟：agent-dh npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → 21/21 通过
- 面板相关套件：stage-panel 54 + node-panel 27 + concurrency-limits 8 全绿
- 全量回归对照（同一工作区、间隔十几分钟两次）：改前 1752 passed / 9 failed → 改后 1756 passed / 9 failed——失败集合逐条同名零变化，通过数 +4 恰为本轮新增用例；本需求新增用例 100% 绿
- 9 条失败逐条归属核验（全部为隔壁窗口在飞改动，非本需求）：①repository.test（RandomIdFactory 时间戳 id）②client-view buildBoard 期待 dsh-pm-archived-bar（该串在本包只剩 CSS，渲染方已随对方 view 拆分消失，且该测试文件被对方修改）③④design-completeness-gate 两条（对方 application/gate 在飞）⑤layer-boundary（对方新增层门禁）⑥size-budget（对方新增尺寸门禁，超标文件 = src/index.ts 431 行；HEAD 版即 415 行，本就超 400，我加的 2 行不改变通过与否）⑦⑧template-address-injection 两条（对方模板地址注入在飞，tsc 报错全落在其 domain/template）⑨typecheck（tsc 报错文件全部为对方在飞模块：CaptureHook/h3-inject/node-input-package/domain-template/gate-wiring，无一条指向本需求文件）

### 改动文件

- `packages/web/dsh-pmboard/tests/concurrency-limits.test.ts`

### 下一步

t7：兼容核验 + 构建部署与线上验收（含重启 :13080 使宿主侧改动生效）

---
