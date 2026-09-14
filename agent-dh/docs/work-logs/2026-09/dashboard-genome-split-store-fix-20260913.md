---
id: wl-2026-09-dashboard-genome-split-store-fix-20260913
title: 自主进化看板串库修复：④⑤ 读到 g1 空库（REQ-3952b7）
type: worklog
status: archived
updated: 2026-09-13
owners: [w-57873eb8]
tags: [worklog, 2026-09]
distilled_into: docs/architecture/page-plugin-contract.md
---

# 自主进化看板串库修复：④⑤ 读到 g1 空库（REQ-3952b7）

> **结论已合并进 L2**：[页面插件契约](../../architecture/page-plugin-contract.md)（2026-09-14 提炼自本篇）。本页保留为**过程证据**；要结论请看上层页面，本页只用于追溯。

- 日期：2026-09-13
- 窗口：w-57873eb8（investor）
- 需求：REQ-3952b7（bug）
- 触发：用户报障「自主进化里的候选生命周期流水线和谱系时间线 数据不对」

## 一、现象

:13080 GUI「自主进化」页 ④候选生命周期流水线为空、⑤谱系时间线只有 4 条 g1「初始基因组快照」，
①②段版本全为 v1；而 ③ 一致性诊断显示全绿（空库天然自洽 = 假阳性健康）。

## 二、取证（三方交叉，2026-09-13 16:16 实时）

| 出处 | 读数 |
|---|---|
| 页面接口 `GET :13080/dashboard/api/genome` | genomeVersion=**g1**，candidates=[]，history=4 |
| 实例日志 `.dsh-data/state/launchd.out.log:1623` | `[genome] loaded: **g35**` |
| `genome_list` 工具 | constitution v1 / principles v6 / **rules v22** / **lessons v9** |
| 真库 `.dsh-data/genome/` | g35，history 37 条，candidates 14 条（11 watching / 2 promoted / 1 rejected） |

**结论：基因组没坏，是看板读错了库。**

## 三、根因

`dashboard-genome`（页面宿主插件）的 `genomeDir` 走插件默认值 `~/.dsh-agent-dh/genome`
（`packages/pages/genome/src/index.ts` 原第 25 行硬编码），而现役 `genome` 插件在
`.dsh-home/profiles/investment/cordis.patch.yml:170` 显式配的是 `.dsh-data/genome`。

`~/.dsh-agent-dh/genome` 不是旧真库，而是 **2026-09-13 02:38 被重新 init 出来的空库**
（git 仅 2 次提交、内容全 g1）——最可能是迁移后另一 profile（`.dsh-home/profiles/agent-dh/
cordis.patch.yml:209` 的 genomeDir 仍指旧 home）启动时找不到文件触发 `ensureInitialized` 新建。

**这类 bug 早有伏笔**：`docs/work-logs/2026-09/dsh-home-migration-20260913.md` 五、遗留第 136 行已点名
「插件默认值 `packages/genome/src/index.ts:32` 硬编码 `~/.dsh-agent-dh/genome`，不跟随 DSH_HOME」，
但当天只给 `genome` 主插件补了显式路径，**漏了两个页面插件**（dashboard-genome / dashboard-execution）。
迁移改了运行时，没改同源的所有读者 → 页面静默读空库。

## 四、修复

不再各自写死路径，也不在 profile 里再抄一遍绝对路径（那是「把硬编码换个地方」），改为**运行时同源 + env 兜底**：

| 层 | 改动 |
|---|---|
| 解析器（新） | `packages/pages/genome/src/genome-dir.ts`、`packages/pages/execution/src/shared/genome-dir.ts`：① 显式 config ② **运行中 genome 插件实际目录** ③ DSH_GENOME_DIR ④ `<DSH_DATA_DIR>/genome` ⑤ `<DSH_HOME>/genome` ⑥ 遗留默认 |
| 页面宿主 | 两页均 `ctx.inject(['genome'])` 惰性取插件实际目录；聚合服务支持**惰性目录解析**（服务晚注入也即时生效） |
| 可观测 | 启动日志打印「genome data dir = … (source: …)」；`/dashboard/api/genome` 响应新增 `genomeDir` / `genomeDirSource`——读哪个库、凭什么选的，一眼可见 |

profile 配置**零改动**（两页仍 `config: {}`）：目录不再由配置文件各写一份，而是跟随 genome 插件，
从结构上消除「改一处漏一处」的可能。

## 五、验证

1. 单测（新增，14 条全过）：`packages/pages/{genome,execution}/tests/genome-dir.test.ts` —— 锁死解析链优先级，
   尤其「运行中 genome 插件目录压过一切 env」与「空白串视为未配置」。
2. 页面包全量回归：`npx vitest run packages/pages` → 19 文件 **199 通过**（0 失败）。
3. schema 冒烟门禁：`npx vitest run tests/plugin-schema.smoke.test.ts` → 19 通过。
4. 端到端读真库（服务器同款 env，tsx 脚本）：`DSH_DATA_DIR=.dsh-data` → 解析 `.dsh-data/genome`（source=DSH_DATA_DIR）
   → genomeVersion **g35**、段版本 **v1/v6/v22/v9**、候选 **14**、谱系 **37**、最新 **g35 rules v22** —— 与工具读数一致。
5. 重启 :13080 后复验页面接口 `genomeDirSource` 应为 `genome-plugin`（跟随插件），④⑤ 渲染 14/37。

## 六、遗留与风险

- `~/.dsh-agent-dh/genome` 空库仍在，且 `.dsh-home/profiles/agent-dh/cordis.patch.yml:209` 仍指着它：
  该 profile 若跑规则进化，会往**分叉的空基因组**里写且“成功”。本次未动它（避免跨 profile 改动），
  列为待办：要么把该 profile 的 genomeDir 对齐 `.dsh-data/genome`，要么让该 profile 不再加载 genome 插件。
- `packages/genome/src/index.ts:32`（dist 加载）默认值仍是硬编码旧 home。本次未动（要重建 dist，
  且现役 profile 已显式配置）。若要彻底收敛，建议把 `genome-dir.ts` 的解析链提为共享模块并让 genome 插件复用。
- 配置层已把全部入口对齐 `.dsh-data/genome`（见第七节）；`~/.dsh-agent-dh/genome` 空库仍在磁盘、
  已无任何配置指向它，是否删除待定。
## 七、配置层对齐（2026-09-13 追加 · 用户裁定「cordis 里配置就可以」）

放弃改 `packages/genome` 的 dist 代码（默认值 + 门禁 + 公开访问器），改走**纯配置**路线：不动 dist，
不会触发「构建失败清空 dist」的风险。

先查清 genomeDir 的声明源共 3 类：

1. **仓库模板 `config/cordis.yml`** —— start.sh 的脚手架源。⚠️ `_ensure_from()` 只在目标**缺失**时复制，
   已存在的 profile 一律保留（2026-09-12 加固，防手改被冲掉）→ **改模板不影响存量 profile**，
   每个 profile 的 `cordis.patch.yml` 必须单独改。
2. 各 profile 的 `cordis.patch.yml`（运行时真正生效的那份）。
3. `agents.json` 的 `instance.genome_dir`（**当前无任何代码读取**，纯声明；与 `instance.account` 不同，
   后者由 lifecycle 注入提示词）。

现役投资脑 profile 三处本就一致（`.dsh-data/genome`）。本次把其余入口补齐（全改 `.dsh-agent-dh` → `.dsh-data/genome`）：

| 文件 | 说明 |
|---|---|
| `.dsh-home/profiles/agent-dh/cordis.patch.yml` | 休眠 profile（PID 66817 已暂停 20h、仍在 LISTEN :13081）；原配置会让它把规则进化写进空库。**该 profile 目录随后按用户指令整体删除（见第八节）** |
| `~/.dsh/profiles/investment/cordis.patch.yml` | 不带 `DSH_HOME` 直接 `dsh --profile investment` 时的入口 |
| `.dsh-data/profiles/investment/cordis.patch.yml` | 2026-09-12 那份未启用副本 |

未动：`*.bak*`、`state/*backup*`、`config-backup-auto`（由 restarter 每次重启刷新，属运行时产物）。

**生效时机**：genomeDir 在**进程启动时**读取。:13080 已于 16:25 重启（新配置本就是对的，无需再动）；
:13081 那个暂停进程本需重启才会读到新值（`SIGCONT` 恢复不重读配置），实际处理是**直接杀掉**（见第八节）。

**残余风险（本次明确接受）**：配置文件是唯一防线——新 profile 若忘写 `genomeDir`，插件仍会按硬编码默认值
落到 `~/.dsh-agent-dh/genome` 并**静默 git init 出一个空基因组**（`initializeFromTemplates()`，只打一行 info 日志）。
靠 `config/cordis.yml` 模板 + start.sh 脚手架兜住新建路径；若日后要治本，再考虑给 `packages/genome` 加“找不到
基因组要响”的门禁（那需要重建 dist）。
## 八、旧 home 与休眠 profile 清理（2026-09-13 16:42 · 用户指令）

用户指令原文：「~/.dsh-agent-dh 直接删除，profile 目录清掉，一会重启，13081杀死」

**删除前只读勘查**（合计 172K + 28K，无活跃配置指向旧 home；残留引用全是注释与脚本兜底）：

- `~/.dsh-agent-dh/` = 2026-09-13 02:38 误建的空基因组（g1）+ `profiles/investment/state/pending-resume.json`（陈旧）
- `.dsh-home/profiles/agent-dh/` = 迁移日（9/12 19:15）遗留的休眠 profile，其 `agents.json` 仍自称
  `instance: investment / port: 13080 / dsh_home ~/.dsh-agent-dh`（旧 home 的过期副本）

**执行**：

1. **杀掉 :13081 残留**：两条进程链均为 SIGSTOP 挂起态，按精确 PID 处理——`66801/66802/66817`（9/12 19:43 起）
   与 `46468/46469/46484`（9/13 01:10 起，挂在交互 zsh 下）。端口 13081 已释放，全盘无 13081 进程残留。
2. **归档后删除**（不可逆，故先留小归档）：`/tmp/dsh-cleanup-20260913/dsh-agent-dh.tgz`（21KB）、
   `profile-agent-dh.tgz`（4.8KB）；两个目录已从磁盘移除，`.dsh-home/profiles/` 现只剩 `investment`。
   ⚠️ 该归档**随后按用户指令删除**（2026-09-13 17:30）——磁盘上已无任何副本，仅本文件与 git 提交留痕。
3. **复验**：`:13080` 正常（`genomeDirSource=genome-plugin`、g35 / 14 候选 / 37 谱系）；
   `relink-profile.py --check` 仍 **25/25 symlink-ok**（legacy 路径被删未影响该门禁）。

**连带影响**：`docs/work-logs/2026-09/dsh-home-migration-20260913.md` §六 的「回滚到旧 home」路径就此失效。
不过该回滚在本次勘查时已被证伪——旧 home 的 profile 目录早被清空，回滚只会拿到那个 g1 空基因组。

**随后一并清理（用户追加指令「清掉」，2026-09-13 17:28）**：

| 路径 | 体积 | 内容 | 处置 |
|---|---|---|---|
| `~/.dsh/profiles/investment/` | **387M** | 旧布局 profile 副本（node_modules 占绝大部分；另含 start.sh/stop.sh/restart-with-build.sh 三份已分叉的历史脚本、`state/` 日志台账、`verify_*.mts`） | 归档后删除 |
| `.dsh-data/profiles/investment/` | 2.9M | 2026-09-12 未启用副本（含 12 个 `cordis.patch.yml*.bak` 历史版本） | 归档后删除 |

- 删前勘查：无进程引用；**无会话/凭据等独有数据**（`sessions`/`.credentials.yaml` 只存在于 `DSH_DATA_DIR`，不在这两份副本里）。
- 归档：先存 `/tmp/dsh-cleanup-20260913/legacy-home-dsh-profiles-investment.tgz`（3.9M，已排除 node_modules 与 *.log）
  与 `legacy-dsh-data-profiles-investment.tgz`（429K）；⚠️ **随后按用户指令一并删除**（2026-09-13 17:30）。
  至此四处遗留副本在磁盘上已无任何副本（含归档），仅本文件与 git 提交留痕。
- **顺带修掉一处悬空引用**：`scripts/rfc010-quick-start.sh:12` 硬编码 `DSH_DIR="$HOME/.dsh/profiles/investment"`，
  删目录后会直接报「DSH 目录不存在」。已改为从脚本自身位置反推 `../.dsh-home/profiles/investment`，启动提示改成
  `$SCRIPT_DIR/start.sh 13080`（托管布局的 profile 目录里没有 start.sh）——`bash -n` 通过、路径自检解析到现役 profile。
- 复验：`:13080` 正常（g36 / `genomeDirSource=genome-plugin` / 15 候选 / 38 谱系）；`relink-profile.py --check` 仍 **25/25**。
- 保留的「死兜底」（仅加注释说明、未删）：`relink-profile.py` 与 `deploy-verify.py` 的 `LEGACY_PROFILES` 仍列着这两个
  已删除路径——它们只在「回滚到旧 home」场景被选中，现已空转，保留是为语义显式。


