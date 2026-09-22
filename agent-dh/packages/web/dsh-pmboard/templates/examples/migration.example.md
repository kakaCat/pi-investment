---
requirement_refs: [RF-1]
---

# 迁移设计（REQ-rf-example：profile 依赖副本迁回符号链接）

> 示例说明：本份用另一个（refactor 类型）需求做例——migration.md 只在
> 「有存量数据/旧调用方」时交，feature 的迁移考量写进 architecture.md 即可。
> 背景：pnpm install 把 profile 的 @pi-investment/* 依赖换成硬链接副本，
> 被编辑过的文件静默过期（2026-09-11 事故）。

## 迁移步骤 <!-- serves: RF-1 -->

| 编号 | 操作 | 验证（跑什么看到什么算过） | 失败回滚 |
|---|---|---|---|
| M-1 | `python3 scripts/relink-profile.py --check` 体检 | exit 1 且列出漂移清单 | 无需回滚（只读） |
| M-2 | `python3 scripts/relink-profile.py` 逐个换回符号链接（旧副本备份到 .deploy-backup/<ts>/） | 输出每包 backup → symlink 记录 | 从 .deploy-backup/<ts>/ 拷回 |
| M-3 | 再跑 --check | exit 0 | 同步骤 2 回滚 |
| M-4 | `launchctl kickstart -k` 重启实例 | :13080 健康检查 200 | bootout 后用备份目录启动 |

## 回滚路径 <!-- serves: RF-1 -->

整体失败：`cp -R .deploy-backup/<ts>/@pi-investment node_modules/` 恢复全部副本，
重启验证。备份目录在确认稳定一周后才清理。

## 兼容期行为 <!-- serves: RF-1 -->

迁移中允许混合态（部分符号链接/部分副本）：读侧无差异（Node 解析不区分），
写侧以「--check exit 0」为完成标志；混合态期间禁止 pnpm install（会再复制）。

## 灰度与观测 <!-- serves: RF-1 -->

单实例无灰度；观测 = 重启后 grep 关键符号于运行时加载的文件（确认新代码生效），
异常阈值 = 健康检查连续 2 次失败 → 回滚。
