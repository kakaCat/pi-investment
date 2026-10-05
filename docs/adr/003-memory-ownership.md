# ADR-003: 记忆归属 agent 侧（quantsys-v2 不再承载记忆）

> 日期：2026-10-05
> 状态：已决策（用户裁决）并已实施
> 决策人：用户 + 本窗口（session-ebe42d9f）
> 关联：[REQ-261004202231-bb99](../requirements/)（实现在 `quantsys-v2/docs/requirements/REQ-261004202231-bb99/`）、
> [记忆子系统已下线](../../quantsys-v2/docs/architecture/memory-subsystem-retired.md)、
> [agent-os 本机重建](../../agent-dh/docs/work-logs/2026-10/agent-os-restore.md)

## 背景

quantsys-v2 曾承载一整条记忆链路（15 个 `/api/memory*` 端点 + `domain/memory` + 两个仓储 + 10 个测试）。
实测它已经**半死**：

| 事实 | 证据 |
|---|---|
| 召回审计表在生产**从来不存在** | `quant.memory_recall_audit` 查不到；端点却长期返回「200 + 空数组」 |
| 记忆表只有测试串 | `quant.memory_entries` 16 行，全是「测试记忆写入 - W3 冒烟测试」 |
| 迁移 013 从未真正生效 | 无一行 `source=distiller` |
| agent 真正在用的工具早已改道 | agent-dh 的 4 个记忆工具自 2026-08-25 起走 agent-os |
| 但旧 agent 仍在用 v2 | agent-ts 的 provider 链首选 `V2MemoryProvider`，召回审计工具直连 v2 |
| 看板也在用 v2 | 仪表盘 M6「盘后经验沉淀」探针直连 v2 的 memory 搜索 |

**结论**：这不是「要不要保留能力」的问题，而是「一条已经空转的链路还在被三处消费」。

## 决策

1. **记忆的归属在 agent 侧**：读写、召回审计、蒸馏都由 **agent-os（`:8080`）** 承载；quantsys-v2 只保留数据与量化。
2. **v2 侧清零**：15 个端点、领域实现、仓储、测试、端口、两处注册点全部删除；记忆相关表**先备份后 DROP**；迁移脚本保留但标注作废。
3. **消费方一律改道 agent-os**：quantsys-v2-client、web-frontend、agent-dh（含看板探针）、agent-ts。
4. **降级必须显式**：看板探针在 agent-os 不可达时返回 degraded（`unknown`），**不允许**退化成「今日无新增」这种看起来正常的假象。

## 后果

- **正面**：v2 的接口面与依赖面各减一块；分层违规因删掉 `domain/memory` 的方向违规而下降（322 → 319，其中 memory 相关归零）；
  「返回 200 ≠ 在工作」这条教训进入说明书。
- **代价**：记忆观测能力比 v2 时代更弱（agent-os 没有 stats/逐条反馈端点，`stats` 改为客户端从 list 派生、`feedback` 显式退役）——
  这是**能力净减**，已在复盘里如实登记。
- **遗留**：agent-os 自身的 schema 三方漂移（`memories` 两套形状）本机是手工并集补齐，应由 agent-os 出一版对账迁移。

## 迁移路径（已执行）

见 [deletion-checklist.md](../../quantsys-v2/docs/requirements/REQ-261004202231-bb99/deletion-checklist.md) 的第五~十一节（逐文件清单 + 逐项实测证据 + 提交号）。
