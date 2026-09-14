# REQ-dfd8b6 实施计划：修复 agent-dh 内存看门狗重启循环

- 需求：REQ-dfd8b6（bug）《修复 agent-dh 内存看门狗重启循环（heap-watch 无退避 + 会话投影重建爆内存）》
- 立项依据：用户直接指令「agent-dh 在反复重启，你查看一下原因」→「修复」
- 制定日期：2026-09-14
- 关联证据页：[DSH 内存看门狗与「反复重启」判别](../../guides/dsh-heap-watch-and-restart-loop.md)

## 一、问题与根因（已实测）

**现象**：2026-09-14 22:45:27 / 22:55:32 / 23:05:36 三次重启，间隔正好 10 分钟。

**因果链**：

1. launchd 作业 `com.pi-investment.dsh-heap-watch`（`StartInterval=600s`、`AUTO_RESTART=1`）每 10 分钟采样 :13080 监听进程 RSS；
2. 三次触发值 **7632 / 7717 / 7674MB**（V8 old-space 上限 8192MB），阈值 6144MB（= 上限 75%）→ 连续 `launchctl kickstart -k`；
3. 高水位的来源：**重启后 DSH 全量重建 session projection cache**——`storages/session_projcache/sessions` 在 22:56 一次写 62 个投影，对应压缩会话 **714.8MB**（单会话最大 113.8MB；会话库总量 881MB / 263 个）；
4. 旧版看门狗「超阈值就重启」既无退避、也无有效性判定，且只投 error 事件（Agent OS 侧不外发通知）→ **重启→重建→再超阈值** 自持循环，且对用户全程静默。

**旁证**：22:56 那次重建落盘完成后，23:05 起的实例命中热缓存，RSS 回落至 672MB（23:15 采样）、732MB（23:17），循环自行终止 → 说明重启本身不是错的，缺的是**头寸 + 围栏 + 告警**。

**诱因**：当日 DSH_HOME/profile 迁移（19:55 / 21:56 / 22:41）使既有投影缓存失效、必须全量重建。

## 二、修复方案（两条腿：给峰值留头寸 + 给看门狗加围栏）

### A. 堆上限留头寸（治「为什么会撞阈值」）
`agent-dh/.env` 增加 `DSH_MAX_OLD_SPACE=16384`（`start.sh` 启动时 source）。
看门狗阈值自适应为 75% → **12288MB**，实测 7.7GB 级重建峰值不再触发自动重启。
64GB 机器可承受；`.env` 被 `.gitignore` 忽略、不入库，故在文档中登记，回退=删该行。

### B. 看门狗退避围栏与告警升级（治「循环与静默」）
`scripts/dsh-heap-watch.sh`：

| 能力 | 行为 | 环境变量 |
|---|---|---|
| 重启台账 | 每次真实重启记 `logs/dsh-heap-watch-restarts.tsv`（ts/rss/旧pid/新pid），保留 24h | — |
| 每小时上限 → 退避 | 滚动 1 小时重启次数 ≥ 上限仍超阈值 → **只告警不再重启** | `MAX_RESTARTS_PER_HOUR`（默认 3） |
| 逃生阀 | 退避时仍要重启 | `ALLOW_RESTART_BEYOND_CAP=1` |
| 告警升级 | 单次重启=error 事件；1 小时内第 2 次起 → `alerts` 群 high（含轨迹 + 最重的 5 个会话 + 处置入口） | `HEAP_WATCH_ALERT_COOLDOWN`（默认 1800s） |
| 恢复即清零 | RSS 回落阈值以下 → 台账作废（判定重启有效） | — |
| 零副作用钩子 | 只打印动作，不重启/不外发/不写台账 | `HEAP_WATCH_DRY_RUN=1` |

**保留不改**：通道不可用绝不 kill；kickstart 失败不 kill；重启后 60s 未监听 → 失败告警；阈值自适应；`kickstart -k` 为唯一重启入口。

**明确不做**：不自动删除/归档任何会话（数据动作需人工确认）；不改 DSH 框架的投影重建逻辑（非本仓代码）。

## 三、任务表

| key | 任务 | 阶段 | 端侧 | 依赖 | 验收 |
|---|---|---|---|---|---|
| t1 | 加固 `scripts/dsh-heap-watch.sh`：台账 + 每小时上限退避 + 告警升级 + DRY_RUN 钩子 | implement | backend | — | `bash -n` 通过；故障注入 5 场景（正常水位/首次超阈值/退避/逃生阀/通道不可用）全部符合预期 |
| t2 | 抬高堆上限并登记：`agent-dh/.env` `DSH_MAX_OLD_SPACE=16384` | implement | backend | — | `source .env` 后为 16384；看门狗将自适应阈值 12288；`.env` 仍被 gitignore |
| t3 | 运维文档：新增 `guides/dsh-heap-watch-and-restart-loop.md`（判别口径/根因/处置手册），挂进 wiki 卷 9 与故障排查手册 | doc | doc | t1 | `wiki_probe.py` 无新增死链；README 卷 9 与 troubleshooting A 节均有入口 |
| t4 | 故障注入与零副作用验收 | test | backend | t1 | 断言全 PASS；测试前后实例 pid 与 launchd `runs` 不变 |
| t5 | 合并 main + 部署后核验（R-017）+ 归档材料 | merge | backend | t1,t2,t3,t4 | 线上脚本与 worktree 字节一致；线上 DRY_RUN 抽样不产生副作用；reqboard 收尾与归档材料齐备 |

## 四、风险与回退

- **抬高上限的代价**：真泄漏时可增长到 12GB 才被看门狗接管（64GB 机器，可接受）；回退=删 `.env` 中的行。
- **退避的代价**：退避期间若真的撞上限，会由 launchd KeepAlive 重新拉起（等价一次重启），但不再被 10 分钟节拍反复打断。
- **合并风险**：主工作区有他人未提交改动（含 `agent-dh/scripts/start.sh`）→ 本需求**不碰** `start.sh`，避开冲突；合并走 `--ff-only`，冲突则停手。
- **不做数据删除**：会话瘦身只给诊断信息与文档步骤，删除/归档由人工决定。
