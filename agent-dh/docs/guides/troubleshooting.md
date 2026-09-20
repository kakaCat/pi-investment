---
id: guide-troubleshooting
title: 故障排查手册（症状 → 根因 → 处置）
type: guide
status: living
updated: 2026-09-15
owners: [w-1cee2467]
tags: [guide, troubleshooting, ops]
---

# 故障排查手册

**这页回答**：遇到这些症状，先看哪里、大概率是什么、怎么修。
（缺陷类需求归档的既定落点：**新问题按"症状 / 影响 / 根因 / 修复 / 防回归"补进这里**。）

## 结论先行

1. **先分清三层**：进程与端口（跑没跑）→ 装载（插件与工具在不在）→ 数据（数是不是新的）。大多数"功能不对"其实在后两层。
2. **"改了没生效"永远是第一嫌疑**：dist 包没 build、profile 硬链接断链、client 半没重新打包、改的是 worktree 跑的却是主仓。**先怀疑生效路径，再怀疑代码逻辑**。
3. **静默失败最危险**：解析失败兜默认值、空结果当成功、缓存冒充实时。看到"一切正常但没效果"时，第一件事是找**兜底分支**。

## A. 服务与端口

| 症状 | 大概率根因 | 处置 |
|---|---|---|
| `./start.sh` 报 **EADDRINUSE** | `:13080` 由 launchd 托管，旧进程还在（`kill` 会被 KeepAlive 秒级拉起） | 重启用 `launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`；停止用该实例的 `stop.sh`（内部走 `bootout`） |
| 页面打不开 / 白屏 | 进程没起，或 client 半加载失败 | `lsof -nP -iTCP:13080 -sTCP:LISTEN`；看 DSH 日志；确认 `lib/client.js` 是最新产物 |
| 想停某个实例却把别的实例干掉了 | 用了模糊匹配（`pkill -f "dsh web"`） | 见 [边界与安全规范](../standards/security-and-boundaries.md)：按 pidfile 或 launchd 标签精确停 |
| **每 10 分钟整点重启一次**（间隔固定） | `dsh-heap-watch` 超内存阈值自动 kickstart，**不是崩溃** | 见 [DSH 内存看门狗与「反复重启」判别](dsh-heap-watch-and-restart-loop.md)：取证据 → 看 `logs/dsh-heap-watch-restarts.tsv` → 退避告警则按处置手册压峰值 |

## B. 插件与工具

| 症状 | 大概率根因 | 处置 |
|---|---|---|
| 启动即崩，日志 UNSUPPORTED_SCHEMA | 工具 schema 缺 `additionalProperties` | 按 [工具开发规范](../standards/tool-development.md) 补全并跑 schema 冒烟 |
| 工具列表里没有新加的工具 | dist 包没 build / profile 硬链接断链 / 插件没注册进 profile 配置 | `relink-profile.py --check` → relink → build → **grep dist 里的符号** → kickstart |
| 工具能调但返回明显是旧逻辑 | profile 指向硬链接副本（部分过期） | relink 后重启；**不要只重启** |
| 页面按钮 / 新面板不出现 | client 半没重新打包，或 `lib/client.js` 没提交 | `npx tsdown -c tsdown.client.config.ts && node scripts/wrap-client.mjs` → 刷新页面；grep 新类名确认打进去了 |

## C. 数据与信号

| 症状 | 大概率根因 | 处置 |
|---|---|---|
| 风控 / 信号数字与账户事实不符（如回撤远超实际亏损） | 数据源冻结仍被当实时；窗口过短 | 按 [数据与降级规范](../standards/data-and-degradation.md) 三招交叉验证；降级期间信号一律"待复核"，不直接下单 |
| 某接口 / 工具恒返回空 | 解析失败静默兜底，或幂等把空结果当有效 | 找兜底分支；空结果应显式报错或重算覆盖 |
| 数据里出现指向已删对象的行 | 悬空引用（删除时没查引用方） | 跑 `data_hygiene_probe.py`；补数据契约与删除策略 |
| 全市场批量信号同向且数量异常（如 50+ 只全 SELL） | 信号源策略本身 error / invalid | 先核验策略健康（`strategy_list` 看结构轴与业绩轴），异常批量默认跳过 |

## D. 文档与 wiki

| 症状 | 根因 | 处置 |
|---|---|---|
| 页面指向的文件不存在（死链） | 改名 / 删除后没更新引用 | `python3 agent-dh/scripts/wiki_probe.py` 定位并修 |
| 新写的页面没人能找到 | 孤儿页（没从首页或上层页链过去） | 挂进 [wiki 首页](../README.md) 对应卷 |
| 归档被拒 | 缺必填文档 / 合并去向不合法 / 没申报说明书更新点 | 看报错里的具体项；规范见 [需求归档规范](../architecture/requirement-archive.md) |

## E. 协作与环境（本轮真实踩过）

| 症状 | 根因 | 处置 |
|---|---|---|
| worktree 里测试全挂（模块找不到） | worktree 缺包级 `node_modules`（本地链接） | 给 worktree 建符号链接指向主仓的包级 `node_modules` |
| 测试跑得出来但依赖解析失败 | 跑在 worktree 而依赖指向主仓（或反之） | 明确 cwd 与符号链接指向；**在哪个树里改就在哪个树里验证** |
| `git merge` 报 "local changes would be overwritten" | 主工作区有他人未提交改动 | **停手**：不要 checkout / restore 批量覆盖；先把自己的分支 rebase 到 main 再 ff 合并 |
| 页面上「之前有」的功能不见了（视图/按钮/面板消失，无报错） | 实现被 `git stash` 暂存后未 pop，后续提交把它覆盖沉没；或功能文件 untracked 从未入库 | `git stash list` + `git reflog` + `git fsck --lost-found` 三路找回；恢复后连 untracked 文件一起入库；**stash 即负债**——跨会话暂存转分支，清 stash 前先导出 patch 备份（REQ-283168） |
| 提交自称「已构建核验」但线上带失败测试 | 发版核验只跑了构建没跑测试——构建只证产物存在 | **发版核验必含全量测试**；静态扫描器报「扫描器可能失效」时先查源码正则/模板串里的裸反引号（扫描器会把它当模板串起点吞掉后文），别怀疑门禁本身；wip 基线归一前先 diff 视图文件，防新版渲染被旧版盖掉（REQ-f0579a） |

## 依据

- 2026-09-11：`pnpm install` 造成硬链接副本 → 部署静默停在旧版；同日 `:13080` 被 kill 后 EADDRINUSE；
- K 线冻结期的假熔断（-10.71% vs 真实 -6.77%）；
- `strategy_stock_matching` 800/800 行悬空引用、105 天无人发现；
- 工具 schema 缺字段导致全量启动崩溃；
- 本轮实踩：client 半产物未重建 → 新按钮不出现；worktree 缺 node_modules → 测试全挂；主仓脏改动 → merge 被拒；
- 2026-09-15：看板双视图被 stash@{0} 沉没数月（暂存后未 pop + P0/P1/P2 覆盖），`conversation-progress.ts` 以 untracked 状态裸奔（REQ-283168）。
- 2026-09-20：HEAD 带 17 个失败测试上线（构建核验漏跑测试）；output-contract 扫描器被 TaskStatusTool 正则字面量里的裸反引号致盲；wip 基线归一盖掉三处看板新渲染（REQ-f0579a）。

## 相关页面

- [构建与发版规范](../standards/build-and-release.md) · [测试与门禁规范](../standards/testing.md)
- [数据与降级规范](../standards/data-and-degradation.md) · [定时巡检清单](routine-checks.md)
- [需求看板实操](reqboard-workflow.md)
