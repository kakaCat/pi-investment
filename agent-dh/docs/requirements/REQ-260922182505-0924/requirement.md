# REQ-260922182505-0924 删除 triage 遗留兼容路径并清理 pmboard 垃圾文件

> 类型：bug ｜ 难度：simple ｜ 立项窗口：w-9faaac35（investor）
> 来源：2026-09-24 立项链路走查发现（台账实证：triages 共 2 条、pending=0、最新 2026-09-08）。

## 复现步骤（问题现象）

1. `grep -rn "triage" src/` → 后端路由/前端面板/判定层/类型层仍有 10+ 处引用；
2. `GET /dashboard/api/reqboard/triage` 仍可用（旧流程接口在装配运行）；
3. `reqboard_capture`/`reqboard_create` 的前置检查仍查"遗留 pending 建议卡"（`hasPendingSuggestion`）——检查对象（旧流程产物）已不再产生，属永远对着尸体站岗；
4. `src/application/internal/support.ts.bak2/.bak3/.bak4` 三个无引用备份文件混入源码树。

期望：死代码删除；实际：仍在运行与维护面内。

## 根因

M2 自动分类流程（SessionSyncService）2026-09 退役时只删了实现本体，兼容层（triage 路由 + 前端面板 + pending 建议卡判定）保留用于"处理遗留卡"。遗留卡已在 2026-09-08 前全部处理完毕（台账实证 0 pending），兼容层失去存在意义但无人删除。

## 功能点

### BUG-1: 删除 triage 兼容路径（后端+前端+判定层）
删 routers/triage.ts 整文件与 routes.ts 的 4 个挂载点；删 client/api.ts 4 个接口、board.ts 的 buildTriage 渲染、board-mount 的 triage 状态、types.ts 的 TriageList/TriageRecord；摘 window.ts 的 hasPendingSuggestion/pendingSuggestionFor 及其在 capture/create 前置检查中的调用；protocol.ts 的 TriageRecord 类型删除、台账 triages 字段保留只读兼容（老台账记录不迁移不报错，读取时忽略即可）。

### BUG-2: 删除 .bak 垃圾文件
删 src/application/internal/support.ts.bak2/.bak3/.bak4（无引用、不入构建）。

## 边界

- **做**：上述两处删除 + 相关测试同步（引用 triage 的测试一并删/改）+ 全量回归。
- **不做**：不迁移/清理台账里的 2 条已 resolve 历史 triage 记录（只读兼容）；不动看板其他视图；不动 acceptance-criteria 等存量红灯测试（属另一条治理线）。
- **不做**：DSH 框架层任何改动。

## 回归

- 删除后 `vitest run packages/web/dsh-pmboard` 失败集与主干基线差集为空；
- `grep -rn "triage" src/ tests/` 只剩历史注释/文档引用（或为零）；
- 部署后 `GET /dashboard/api/reqboard/triage` 返回 404/未知路由，看板正常渲染无 triage 面板；
- 验收命令可执行：见 design/test-cases.md。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| BUG-1 | 🔴 **未被接收** | — |
| BUG-2 | 🔴 **未被接收** | — |

> 🔴 **未被接收（2 条）**：BUG-1、BUG-2

<!-- reqboard:marks:end -->
