# DSH_HOME 迁入项目内（:13080）

**日期**：2026-09-13
**触发**：GUI `http://127.0.0.1:13080/` 反复打不开（401），排查发现根因是**签名密钥漂移**，顺势完成 2026-09-12 预留的"数据搬进项目内"迁移。

## 一、问题根因（为什么反复 401）

`dsh web` 的鉴权设计（`@deepseek-ai/dsh-client-connection` README）：

- 每进程随机生成 `launchToken`，打印并打开 `?token=...` 的地址
- 该 token 只在 `GET /` 上兑换一次，写一个 **authority 绑定 + 密钥签名**的 cookie，默认 **30 天**有效
- 密钥持久化在 `$DSH_HOME/.credentials.yaml` 的 `client-connection/browser-session` 记录

**所以正常 dsh 一个月最多碰一次 token**，用户无感。而本机当时存在**三份凭证库、两个不同密钥**：

| 路径 | secret sha256(前16) | 用途 |
|---|---|---|
| `~/.dsh-agent-dh/.credentials.yaml` | `58294f9fe44d9343` | 当时 :13080 现役 |
| `~/.dsh/.credentials.yaml` | `ed89d00dd562b3bf` | 主 dsh :3080 |
| `agent-dh/.dsh-data/.credentials.yaml` | `ed89d00dd562b3bf` | 9/12 未完成的迁移快照 |

9/12 的数据迁移在两套布局之间来回切，**每切一次密钥就换一次，浏览器里所有 cookie 全部作废** → 表现为"启动好久还是不能用"。不是启动慢，是钥匙过期。

## 二、9/12 迁移的实际状态（与 `DATA_MIGRATION.md` 描述不符）

切换前实测：

| | `~/.dsh-agent-dh`（现役） | `.dsh-data`（"已迁移"） |
|---|---|---|
| sessions | 191 文件，最新 09-13 01:51 | 119 文件，最新 09-12 19:57 |
| genome/ | ✅ | ❌ 整个目录不存在 |
| skills/ | ✅ | ❌ 不存在 |
| dsh-reqboard.json | ✅ 96KB | ❌ 不存在 |
| attachments/ | ✅ | ❌ 不存在 |

`.dsh-data` 只是 9/12 17:00–19:57 的**部分快照**，服务当晚就回滚到 `~/.dsh-agent-dh` 继续跑至今。`DATA_MIGRATION.md` 的"数据已迁移"不成立。

另有一个运行时坑：现役 profile 是 `investment`，而 managed 模式缺省是 `agent-dh`（`.dsh-home/profiles/agent-dh` 已存在但从未成功启动过）。

## 三、本次做法

**先补齐数据、验证等价，再切**，全程可回滚。

1. **备份**：`~/dsh-migration-backup-20260913-015934/`（plist、两份凭证、settings、现役 cordis.patch.yml）
2. **数据合并**：`rsync -a --exclude node_modules ~/.dsh-agent-dh/ → agent-dh/.dsh-data/`（**不 `--delete`**）。合并后 genome 272 文件**零差异**、skills 8=8、reqboard 同尺寸、sessions 取并集
3. **密钥延续**：rsync 覆盖了 `.dsh-data/.credentials.yaml`，使其与现役同为 `58294f9f`。**authority(127.0.0.1:13080) 与密钥都没变 → 浏览器里现有 cookie 继续有效，无需重新交换 token**
4. **profile 对齐**：新建 `.dsh-home/profiles/investment/`
   - `cordis.patch.yml` 用**现役那份**（只改写 2 处绝对路径：`genomeDir`、`profileDir`），保证行为零变化
   - `package.json` 只留 `dsh.profile.bundles`（现役那份的 `link:../../../pi-investment/...` 相对路径在新深度会失效）
   - `node_modules` → 仓库 `agent-dh/node_modules`（现役 profile 的 `../../../../../` 相对符号链接**深度敏感**，搬目录必断）
5. **补链**：`node_modules/@pi-investment/lifecycle -> ../../packages/lifecycle`（仓库 link farm 里唯一缺的一个）
6. **等价性验证**（关键）：`--dump-config` 对比现役与新 profile 的组合结果 —— **683 行逐字节一致，仅 `genomeDir` 一处差异**（即预期改动）。14 条 `entry not found` 警告两边相同，属既有现象
7. **切 plist**：移除 `DSH_HOME` 覆盖（→ 进入项目内托管模式），保留 `DSH_PROFILE=investment`；日志路径改指 `.dsh-data/state/`
8. **重启**：`launchctl bootout` + `bootstrap`（改 plist 内容必须重载，`kickstart` 不会重读）

## 四、切换后状态

- 进程 PID 58066，`DSH_HOME=/Users/yunpeng/pi-investment/agent-dh/.dsh-home`，profile=investment
- `genome` 加载成功（g32）；裸地址 401、带 token 303→200（4.8ms）
- 本文件相关改动（`genomeDir` 硬编码）随本次一并合入

## 四之二、补记：数据复制了，但运行实例看不见（当日发现并修复）

切换后用户反馈"数据没复制到 agent-dh 项目里"。核查结论：**数据确实在**——

| | 旧 home `~/.dsh-agent-dh` | `agent-dh/.dsh-data` |
|---|---|---|
| sessions | 191 | **203**（并集） |
| genome | 272 文件 | rsync 空跑**零差异** |
| dsh-reqboard.json | 96064 字节 | **逐字节相同** |
| skills / attachments | 8 / 全 | 8 / 全 |

`rsync -ain ~/.dsh-agent-dh/ .dsh-data/` 空跑只剩 2 条（都是切换后新写的会话），无遗漏。

**但运行实例看不见** —— `DSH_HOME` 是 `.dsh-home`，而 start.sh 托管模式只挂了 4 项
（`settings.yaml` / `.credentials.yaml` / `sessions` / `storages`），其余顶层状态项一个没挂：

| `.dsh-data` 有 | `.dsh-home` 暴露 | 后果 |
|---|---|---|
| `dsh-reqboard.json` | ❌ | **真损坏**：`dsh-pmboard` 按 `$DSH_HOME/dsh-reqboard.json` 取台账（`src/index.ts:39`，`LEDGER_FILE`），读不到就当空板 → 14 条 REQ 在实例里消失 |
| `skills/` · `attachments/` · `pet.json` | ❌ | 附件与 skill 根取不到 |
| `genome/` | ❌ | 无影响——config 里写了绝对 `genomeDir` |

**修复**（提交 `89df4f4e`）：start.sh 新增 `_link_file()`（单文件版非破坏性链接：源缺失则跳过、
**不建悬空链接**；真实文件则告警**拒绝替换**，与 `_link_dir` 同策略），并挂上这四项。

**验证**：六种行为干跑（首挂/幂等/源缺失/目标真实文件/目标含内容目录/空位挂上）全对；
重启后线上跑的是幂等分支（无告警 = 已挂对），`/dashboard/api/reqboard/` 返回
**14 条 REQ / revision 257**，与文件一致。

**教训**：迁 DSH_HOME 时「数据已复制」≠「实例可见」。判定依据必须是**运行实例的读数**
（API 响应 / 启动日志），不是数据目录的文件清单——后者只证明磁盘上有，不证明应用读得到。

## 四之三、发版工具链重定位（同日续查）

上一节修的是"实例看不见数据"，顺着查发现**发版工具链整个指着旧 home**：

| 位置 | 原值 |
|---|---|
| `relink-profile.py:46` | `FALLBACK_PROFILES[0] = ~/.dsh-agent-dh/profiles/investment` |
| `deploy-verify.py:38` | 同上 |
| `restart-with-build.sh:28` | `PROFILE_DIR="$HOME/.dsh-agent-dh/profiles/investment"` |

后果分两层：

1. **门禁验错对象**。跑 `relink-profile.py --check` 打印的是 `profile: ~/.dsh-agent-dh/...`，
   并给出一句 "OK: 29 个符号链接" —— 而真正在跑的是 `.dsh-home`。这个"OK"什么都不保证。
2. **发版脚本会撞墙**。`restart-with-build.sh`（CLAUDE.md 写的"正常发版走它即可"）
   会 `cd` 到旧 home 跑**它那份旧 start.sh**：硬编码 `DSH_HOME=$HOME/.dsh-agent-dh`，
   与仓库版差 418 行，且**没有 EADDRINUSE 互斥**。结果是撞 13080 端口失败，而真正该
   relink 的 `.dsh-home` 一次都不会被碰到。

**修复**（`6c18245a`）：三者改为**从脚本自身位置反推** profile
（`scripts/` → `agent-dh/` → `.dsh-home/profiles/<name>`），旧路径降级为兜底，
且被选中时**打印警告**——不再可能静默验错对象。`restart-with-build.sh` 的启动分支
一并修正：托管布局的 profile 目录里没有 `start.sh`，改用 `$SCRIPT_DIR/start.sh`，
cwd 取 `PROJECT_ROOT`（与 launchd 拉起实例的 `process.cwd()` 一致）。

**连带修复**（`3f78e54c`）：改指向后 `--check` 把 25 个条目全判成 `linked-unverified`
（旧目标下是 `symlink-ok`）——门禁悄悄变松：只判得出"不是副本"，判不出"指向本仓库"。
根因是 `find_repo_root` 只从 `package.json` 的 `file:`/`link:` 声明反推，而托管布局的
profile package.json **只有 `dsh.profile.bundles`，零声明**，仓库根推不出 → `repo_index` 空
→ 未声明条目一律降级。补三个与声明无关的锚点（`node_modules` 解软链后 / profile 自身 /
脚本自身）后，现役 profile **25/25 symlink-ok**。

四种形态判定已逐一实测：仓库内→`symlink-ok`、仓库外→`symlink-bad`、
普通目录→`copy`、悬空→`symlink-dangling`。

**教训**：改 DSH_HOME 布局时，**跟着改的不只是运行时，还有工具链**。运行时错了会报错，
工具链错了只会给你一句漂亮的 "OK"。

## 五、遗留

- `~/.dsh-agent-dh`（1.5GB）保留作为回滚，**未删除**
- `config/cordis.yml` 与现役 `cordis.patch.yml` 仍有 253 行分叉（repo 那份是 09-12 21:40 改的，现役停在 19:53）。本次**以现役为准**，分叉未处理
- 插件默认值 `packages/genome/src/index.ts:32` 硬编码 `~/.dsh-agent-dh/genome`，不跟随 `DSH_HOME`——这是本次必须显式写 `genomeDir` 的原因。建议后续改为 DSH_HOME 相对
- `.dsh-data/state/launchd.out.log` 混有 9/12 迁移带来的历史日志（前 1392 行）
- `.dsh-data/profiles/` 里有 9/12 那份未启用的 profile 副本；现役是 `.dsh-home/profiles/investment`，未清理
- 挂载清单是**手写枚举**的。若日后有新插件按 `$DSH_HOME/<名字>` 落状态，需同步加进 start.sh（现无自动发现机制）

## 六、回滚

```bash
cp ~/dsh-migration-backup-20260913-015934/com.pi-investment.dsh.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.pi-investment.dsh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pi-investment.dsh.plist
```

`~/.dsh-agent-dh` 原样保留，回滚后即回到切换前状态（含原密钥 → 原 cookie 恢复有效）。
