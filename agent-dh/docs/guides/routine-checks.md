---
id: guide-routine-checks
title: 定时巡检清单（有问题才打扰）
type: guide
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [guide, ops, checks]
---

# 定时巡检清单

**这页回答**：哪些检查该定期跑、跑什么命令、什么算有问题、出了问题找谁。

原则：**探针用退出码说话，无问题不打扰**（有问题才通知；日常流水只写 memory，不上公告板）。

| 检查 | 频率 | 命令 | 判据 | 代表问题 |
|---|---|---|---|---|
| **依赖链接漂移** | 发版前 + 每周 | `python3 agent-dh/scripts/relink-profile.py --check` | 退出码 1 = 有副本漂移 | profile 指向硬链接副本 → 改了不生效 |
| **数据卫生（悬空引用）** | 每周 | `python3 quantsys-v2/scripts/data_hygiene_probe.py` | 退出码 1 = 有问题 | 派生/审计数据指向已删对象（R-020） |
| **文档 wiki** | 每周 | `python3 agent-dh/scripts/wiki_probe.py` | 退出码 1 = 现行页有死链/孤儿/缺字段/type-status 越界/索引过期 | 死链、孤儿页、字段越界 |
| **文档索引一致性** | 每周 | `python3 agent-dh/scripts/docs_index.py --check` | 退出码 1 = 自动区与文档不一致（改了页面没重跑生成） | INDEX / 最近改动 / 日志台账过期 |
| **工具 schema** | 每次改工具 | `cd agent-dh && npx vitest run tests/plugin-schema.smoke.test.ts` | 非 0 = 违规 | 启动即崩那类 |
| **服务健康** | 每日（盘前） | `lsof -nP -iTCP:13080 -sTCP:LISTEN`、quantsys-v2 `:5001` | 端口未监听 = 服务没起 | 服务挂了但没人知道 |
| **调度看门狗** | 每日 | `scheduler_manage(list)` 看未执行/连挂任务 | 有连挂 2 次的 = 问题 | 定时任务空转/连挂 |
| **公告板未闭环** | 每日 | `board_read(status=active)` | 有 open/blocked 且逾期 | 派出去的活没人接 |
| **告警队列** | 每日 | `market_alert(level=high)` | 有 high = 需处置 | 风险信号被漏看 |
| **归档债（待写页）** | 每周 | `wiki_probe` 输出的 stub 列表 | 只减不增为健康 | 被引用却没写的主题越积越多 |
| **待提炼队列** | 每周 | `wiki_probe` 输出的「待提炼队列」（`distilled_into` 为空） | 逾期（>30 天）只减不增为健康 | 结论只躺在 L3 日志里，L2 认知长不上去 |
| **构建产物一致性** | 发版后 | `grep -c <新增符号> <pkg>/dist/index.mjs`（或 `lib/client.js`） | 恒为 0 = 没生效 | 构建成功但内容没进去 |

## 怎么用

1. **盘前 5 分钟**：服务健康 + 告警队列 + 公告板未闭环（有 high 告警先处置，其余后置）；
2. **每周一次**：数据卫生 + wiki 探针 + 文档索引一致性 + 依赖链接漂移（含待提炼队列）；
3. **每次改工具/发版**：schema 冒烟 + 产物 grep（**不看退出码，看内容**）；
4. 发现问题的处置路径见 [故障排查手册](troubleshooting.md)；**探针绿就不通报**（避免消息疲劳）。

## 依据

- 数据卫生周巡检与 `data_hygiene_probe.py`（R-020 的检测层）；
- wiki 探针（2026-09-13 新增）与文档索引生成器 `docs_index.py`（2026-09-14 新增：让 front-matter 有消费者）；
- **待提炼队列**（2026-09-14 新增）：L3 日志 `distilled_into` 为空的即待办，把「整理文档」变成有终点的活；
- 调度看门狗与公告板生命周期（RFC 009 / RFC 014）。

## 相关页面

- [故障排查手册](troubleshooting.md) · [构建与发版规范](../standards/build-and-release.md)
- [数据与降级规范](../standards/data-and-degradation.md) · [agent-dh Wiki 首页](../README.md)