# .dsh-home 并入 .dsh-data：撤除挂载层

**日期**：2026-09-14
**提交**：`414383f8`（布局改造）、（本文件所在提交，发版工具链收口）
**触发**：用户提问「.dsh-data 和 .dsh-home 可以合并吗」

## 结论

合并了。`DSH_HOME` 现在**就是**数据目录 `agent-dh/.dsh-data`，`.dsh-home` 已消失，
start.sh 里 7 处 `_link_dir` / `_link_file` 挂载调用全部删除。

## 为什么要合并（不是洁癖）

原先两层：`DSH_HOME=.dsh-home`（脚手架）+ `DSH_DATA_DIR=.dsh-data`（真数据），
由 start.sh 把数据挂进 home。**这层会自己坏**，因为三个文件级挂载点的写盘方全部用
原子写（临时文件 + rename），而 `rename` 会把符号链接替换成普通文件：

| 挂载点 | 写盘方 | 状态（合并前实测） |
|---|---|---|
| `dsh-reqboard.json` | `dsh-pmboard` 自有 store（`temp+fsync+rename`，`src/host/store.ts`） | **已炸** |
| `.credentials.yaml` | `dsh-credentials-local`（`writeFileAtomic`） | 引信已装 |
| `pet.json` | 不在本仓库 | 引信已装 |

已炸的表现：`.dsh-home/dsh-reqboard.json` 是 **250251 字节的真文件**（实例 PID 86555 持有），
`.dsh-data/dsh-reqboard.json` 冻结在 **2026-09-12 22:11 的 96064 字节** ——
**备份 .dsh-data 会漏掉真实台账**，而 `_link_file` 遇到含内容的真文件只告警不覆盖，
所以这个分裂是永久且静默的（只往 launchd 日志写一行没人看的东西）。

未炸的那个更危险：`.credentials.yaml` 一旦在 UI 里被写一次，`.dsh-home` 就会长出
第二份凭证库 = 两套 cookie 签名密钥 = 反复 401（该故障已发生过三次）。

而这层本来只是「DSH_HOME 曾在仓库外（`~/.dsh-agent-dh`）」时代的遗留 —— 两个目录
现在都在 `agent-dh/` 下，分工没有职责了，留下的只有「同一个状态有两个候选位置」。

## 改了什么

- **`scripts/start.sh`**：`DSH_HOME=DSH_DATA_DIR`；删掉 `_link_dir`/`_link_file` 两个函数
  及其全部调用；删掉 settings.yaml 的链接清理段（合并后它本来就在正确位置）；
  保留 `sessions/storages/skills/attachments` 的 `mkdir`；
  新增**上一层布局残留检测**（`.dsh-home` 若还有内容就喊出来 —— 静默的旧副本比报错危险）。
  profile 内 `state/`、`data/` 的同树目录链接保留（目录链接不会被原子写破坏，
  且 lifecycle 按 `$PROFILE_DIR/state` 找状态文件）。
- **`config/cordis.yml` + `cordis.yml`**：撤掉 settings 的 `config.path` 绝对路径覆盖 ——
  缺省解析 `join(resolveDshHome(), "settings.yaml")` 现在自然落在唯一那份上。
  `genomeDir` 的显式指定**保留**：那个插件的缺省是硬编码的 `~/.dsh-agent-dh/genome`
  （旧 home，已删除），不跟随 `DSH_HOME`，删掉这行会让基因组写到不存在的路径。
- **发版工具链跟着布局走**：`relink-profile.py` / `deploy-verify.py` /
  `restart-with-build.sh` / `rfc010-quick-start.sh` 的解析根 `.dsh-home` → `.dsh-data`。
- **修掉两个真 bug**（都是"体检对象整个是错的"，见下节）。
- 文档同步：`glossary.md` / `agent-dh-overview.md` / `identity-and-agents-json.md`。

## 顺带修掉的两个真 bug

**① 体检脚本的 profile 名写死为 `investment`**，而 start.sh 的缺省是 `agent-dh`，
`:13080` 实跑的就是 `agent-dh`（`ps eww` 无 `DSH_PROFILE`）—— 也就是说发版工具链
一直在体检那个**休眠的** profile。改为与 start.sh 同规则（`DSH_PROFILE`，缺省 `agent-dh`），
只保留一个来源。

**② 检查集为空却当成通过**。指向现役 profile 后，`relink-profile.py --check` 报
「0 个安装条目」并退出码 1 —— 因为托管布局下 profile 的 `package.json` **不声明**任何
`file:` 依赖，插件是按包名从**进程 cwd** 的 node_modules 解析的（start.sh 末尾
`cd "$PROJECT_ROOT"` + `NODE_PATH="$PROJECT_ROOT/node_modules"`，PROJECT_ROOT 即 agent-dh）。
补了运行时解析根作为回退检查集（同一套判据、同样可自动修复），并打印它验的是哪个根。
`deploy-verify.py` 的 L1 是转调 `relink-profile.py --check`，一处修复两处受益；
它的 L2 还另有一个 `return dirs`（1 个值）vs `return dirs, skipped`（2 个值）的崩溃，
恰好只在"profile 无插件作用域目录"时触发 —— 修了。

## 迁移怎么做的

一次性脚本（`/tmp/dsh-merge-migrate.sh`，未入库），每步校验、失败即停：

1. 停机（`./scripts/stop.sh`；launchd 作业当时未加载，走 pidfile + 监听校验路径）
2. `.dsh-home` 整份备份到 `.deploy-backup/dsh-home-pre-merge-20260914/`（14MB）
3. **对账**（同名冲突逐项取"实例真正在读的那份"）：
   - 台账：取 `.dsh-home` 的活文件（250251B）覆盖死副本；死副本另存为证据
   - `.anonymous-user-id`：两份内容**不同**，取 `.dsh-home`（实例读取位）
   - `.credentials.yaml` / `pet.json` / `sessions` / `storages` / `skills` / `attachments`：
     都是指向 `.dsh-data` 的符号链接，用 `unlink` 只删链接（**不用 `rm -r`**，
     对指向目录的链接会跟随进去删真数据）
   - `.agent-presets/`：以 `.dsh-home` 那份为准，**`.dsh-data` 里的 `liangshen` 残留一并消失**
     （它原本是惰性的，合并后会变成"活的"，必须在这次一起清掉）
4. `profiles/` 下沉（含 `node_modules`）；`.dsh-data/profiles` 迁移前为空，整批移动
5. 其余顶层条目下沉，**同名一律拒绝覆盖**
6. `agents.json` 的 `dsh_home` 字段（`.dsh-data/` 与其 profile 副本两处）
7. 确认 `.dsh-home` 已空 → `rmdir`；整份留在备份目录

工具链全量 `--force-config` 起一次，使活 profile 补丁与仓库 `config/cordis.yml` 一致
（已先确认 profile 的 `package.json` 无 `dependencies` 声明、且活补丁与仓库配置
只差 settings 覆盖块与注释，所以重生成是安全的）。

## 验收（合并后实测）

| 项 | 结果 |
|---|---|
| 活进程环境 | `DSH_HOME=DSH_DATA_DIR=/Users/yunpeng/pi-investment/agent-dh/.dsh-data` |
| `.dsh-home` | 不存在，且重启后未重建 |
| 实例持有的关键文件 | `settings.yaml` / `dsh-reqboard.json` / `pet.json` / `.credentials.yaml` / `agents.json` 全部落在 `.dsh-data` 下 |
| 台账 | API 返回 revision **400**、22 条需求（= 活台账；死副本是 9-12 的旧版） |
| 会话 | `session/list` **238** 条，跨度 2026-08-20 ~ 09-14 |
| 预设 | 默认 `investment`，可用 `[cordis, investment, minimal, ptc, standard]`，**无 liangshen** |
| 生效默认模型 | `{provider: v1, model: claude-fable-5-1}` —— 该值**只存在于** `settings.yaml` |
| settings 单一来源 | 全盘只有 `.dsh-data/settings.yaml`（1495B），进程只持有它一个 fd |
| `relink-profile.py --check` | **24/24 symlink-ok**，退出码 0（验的是运行时解析根） |
| `deploy-verify.py` | L1 OK、L3 OK、L4 manifest 写到新路径 |

### 归档掉的死快照：`settings-temp.yaml`

`.dsh-data/settings-temp.yaml`（2026-09-12 19:03，1033B）是迁移期的旧设置快照
（里面 `agent-default-model` 还是 `deepseek-official/deepseek-v4-flash`）。全仓库按名字
零命中，但进程持有它的 fd。判定方法：实例生效的默认模型是 `v1/claude-fable-5-1`，
而 temp 里**根本没有这个模型** ⇒ 加载的是 `settings.yaml`，temp 是目录 watcher 的 fd 产物。
已归档到备份目录并重启复核：所有生效值与归档前一致 → 确认惰性。

## 遗留

- **L2 产物层 FAIL**：`scheduler` 产物陈旧（`dist/index.mjs` 09-13 19:03:13
  vs `src/tools/SchedulerManageTool/prompt.ts` 09-13 19:04:11，差 58 秒）。
  **与本次改动无关**（本次未碰任何 `packages/` 源码），是 09-13 那次编辑后没重新构建。
  处置：`pnpm build`（或走 `restart-with-build.sh` 的完整链路）。
- `.dsh-data` 里还留着几份历史备份目录（`sessions-backup`、`session-backup-20260911-021800`、
  `backup-ungrouped-cleanup-20260908-140939`、`sessions-backup-all` 等），未清理。
- `.dsh-data/profiles/investment`（休眠 profile，24 个插件链接）保留未动 —— 回滚用。
- launchd 作业 `com.pi-investment.dsh` 仍未加载（本次全程手工 `start.sh`）。
