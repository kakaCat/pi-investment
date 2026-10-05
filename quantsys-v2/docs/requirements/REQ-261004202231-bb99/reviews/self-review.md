---
req_id: REQ-261004202231-bb99
title: 自审（交付前）
doc: reviews/self-review
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 自审（2026-10-05 · REQ-261004202231-bb99）

## 结论：可交付（但有两条台账遗留，见文末）

## 逐条对照需求

| 条款 | 判定 | 依据 |
|---|---|---|
| FR-1 v2 内下线记忆实现 | ✅ | 15 端点 404；domain/memory 与仓储删除；无残留符号；启动日志无记忆注册 |
| FR-2 摘除三个外部消费方 | ✅ | 客户端库方法、监控前端页面与路由、agent-dh 工具全部删除；web 构建 exit 0 |
| FR-3 数据与迁移处置 | ✅ | 先 dump（5,693B/16 行）再双库 DROP；4 脚本标作废；漂移测试 6 passed |
| FR-4 叙述落档 | ✅ | 架构页 memory-subsystem-retired.md + 索引；agent-dh 记忆页口径更新 |
| FR-5 看板探针迁 agent-os | ✅ | 探针改查 agent-os；类型与注册表口径同步；不可用时显式 degraded（不再静默 0） |
| FR-6 agent-ts 迁 agent-os | ✅ | provider 首选 agent-os；召回审计 list/stats 迁移、feedback 显式退役；审计写入迁 agent-os；蒸馏端点映射删除 |

## 自查发现的问题（已处理 / 已登记）

1. `agent-os/cli.ts` 用 `import.meta`，jest 下编译不过（而该模块现在会被记忆链加载）→ 已改为从 `process.cwd()` 推导，并顺带修正了从来就不对的默认 CLI 路径。
2. 台账里两张残留子卡（t-3b3641 / t-cdb919）的完工门禁要求「改动文件晚于子卡开工」，而实际改动早于它们 → 台账遗留，非交付缺陷。
3. `quantsys-v2/.env` 已改为 git 不再跟踪（原 stash 冲突一侧含 PGPASSWORD），本地文件保留。

## 遗留（交验收时请一并裁决）

- 两张子卡的台账状态（见上第 2 条）需要人工取消或补凭证。
- agent-os 侧的 schema 三方漂移（memories 两套形状）是**手工并集补齐**的，正式修法应出一版对账迁移（已写进 [agent-os 本机重建](file:///Users/mac/Documents/ai/pi-investment/agent-dh/docs/work-logs/2026-10/agent-os-restore.md)）。
