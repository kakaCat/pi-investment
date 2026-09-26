---
requirement_id: REQ-260926140539-457b
kind: notes
title: 拆分阶段补记（落库与追溯补齐）
created: 2026-09-26
---

# 拆分阶段补记

## 1. 本阶段完成的事

1. **拆分计划已获人批准**（plan.approvedVia=session，20 个任务）。
2. **20 张任务卡已落库**：`t-8c8edc` … `t-c010b8`，含 depends_on DAG（19 张有依赖）、
   可证伪 acceptance（20 张）、实施方案（20 张，落在 description / context）。
3. **追溯覆盖补齐**：`decomposition.md` 新增 §1 RTM 覆盖对照表（48 条「根编号 ↔ 任务卡」绑定），
   并补 `FR-6`（修改需求时 RTM 更新策略）→ t2/t14/t15/t16、`FR-10`（性能优化）→ t10/t19 的 serves 标注。
   结果：**FR-1 … FR-11 全部 received**（此前 11 条全 unreceived）。

## 2. 为什么需要人工补这步（根因，响亮报出）

「批准计划 → 自动落库任务卡并进入实施」这条自动链路在当前构建中**不可用**：

| 环节 | 现状 | 位置 |
| --- | --- | --- |
| 文字证据批准计划 | 只落 `plan.approvedAt`，**不**触发门合并 | `application/use-cases/ConfirmArtifact.ts` |
| 门合并（批准即拆分+进实施） | 调 `deps.jobs.start({kind:'reqboard_decompose'})`，但 **deps.jobs 从未装配** → 抛错即中止，不推进 | `application/internal/confirm-settle.ts:224`；`application/ports.ts:352` |
| `reqboard_decompose` 工具 | **已删除**（REQ-260925234037-1503） | `src/tools/index.ts` 无该导出 |
| 声称的替代（Dive Armed 自动拆分） | **桩实现**：`getActiveRequirement()` 直接 `return null` | `application/dive/ReqboardDiveManager.ts:110-115` |

结论：批准计划后不会自动拆分；且 `decomposing → implementing` 是代码级人工闸门
（`GateCatalog` G3：humanOnly=true），agent 调用被拒（`human_gate`）。故本需求的任务卡
由窗口按已批准计划经看板建卡通道落库，收尾推进由人在看板/确认门完成。

## 3. 待办

- [ ] 人确认后推进 `decomposing → implementing`（G3 人工门）。
- [ ] 进入实施后按卡序开工：`t-8c8edc`（类型定义）→ `t-93f4da`（lifecycle）→ … 。
- [ ] 后续把上述自动链路缺陷单独立项修复（`deps.jobs` 装配 + decompose 落库实现 + DiveManager 落地）。
