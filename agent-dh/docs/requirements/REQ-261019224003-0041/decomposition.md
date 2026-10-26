# 拆分计划 · REQ-261019224003-0041

> 目标：A1 收编 dsh-workprocess 四包 + 投影接缝接管 implementing 期子卡执行 + goal/pm-workflow 收尾（P1–P6）。
> 做法：七张卡——搬迁(t1) → 依赖与构建配置(t2) → 装载清单(t3)；数据契约(t4)先行于接缝(t5)；旧名收尾(t6)在接缝就位后；真机验收(t7)兜底。
> 实施仓库：dsh-pmboard（`/Volumes/ORICO/doc/github/dsh/dsh-pmboard`）。判据全部可跑，见各卡 acceptance。

## 改动盘点

| 类型 | 对象 | 对应卡 |
|---|---|---|
| 新增 | `workprocess/` 四包目录（源码+tests+client+构建配置+cordis.patch.yml） | t1 |
| 修改 | `pm/package.json`（增四包 `workspace:*`）、`pm/tsdown.config.mjs`（四条内联正则）、`tsconfig.json`/`vitest.base.mts`/`vitest.config.ts`（补命令包映射）、`scripts/package-boundary-check.mts`（pm-core allow 增 workprocess、L2 放行三包） | t2 |
| 修改 | `pm/cordis.patch.yml`（1 行 → 5 行 insert）；desktop profile 摘除四条独立 bundle 行（迁移兼容） | t3 |
| 修改 | pm-core 任务卡领域：`blockedReason` / `closePolicy` 字段（读写兼容、非法值抛错） | t4 |
| 新增/替换 | pm-core 投影器 `projectWorkProcess`；`pm/src/adapters/goal-round-lifecycle.ts` / `goal-round-ports.ts` 换血为驱动器+投影/写回适配；`dive-core/round-state.ts` 回合契约归属改指 workprocess | t5 |
| 修改/删除 | 17 个 `import pm-goal*` 文件改接或摘除；配置面旧名三组映射摘除；`goal/*`、`pm-workflow/` 保持删除 | t6 |
| 验证 | 装载复现 + 真机全 auto 流程 + 人工门回归 | t7 |

## 覆盖对照表

| 需求条款 | 内容摘要 | 接收任务 |
|---|---|---|
| FR-1 | 四包源码收编 | t1 |
| FR-2 | 装载形态收敛（五条 insert 行 + profile 迁移） | t3 |
| FR-3 | 依赖与内联构建 | t2 |
| FR-4 | 配置面与分层清单对齐 | t2 |
| FR-5 | 投影接缝（pm 台账 → workprocess 事实） | t5 |
| FR-6 | 驱动接管与许可合并 | t5 |
| FR-7 | pm 卡面字段扩展 | t4 |
| FR-8 | goal/pm-workflow 退役收尾 | t6 |
| FR-9 | 可跑验收面 | t7 |

## 任务表

| key | title | phase | side | depends_on |
|---|---|---|---|---|
| t1 | 收编四包源码进 workprocess/ | implement | backend | — |
| t2 | 依赖声明与构建/映射/分层清单对齐 | implement | backend | t1 |
| t3 | 装载清单五条行 + profile 迁移 | implement | backend | t2 |
| t4 | pm 卡面新增 blockedReason/closePolicy 字段 | implement | backend | — |
| t5 | 投影器 + 写回适配 + 驱动接管起链 | implement | backend | t1, t4 |
| t6 | goal/pm-workflow 旧名收尾 | implement | backend | t5 |
| t7 | 装载与全链路真机验收 | test | fullstack | t3, t5, t6 |
