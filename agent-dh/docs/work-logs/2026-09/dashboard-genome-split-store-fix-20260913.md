# 自主进化看板串库修复：④⑤ 读到 g1 空库（REQ-3952b7）

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
| `.dsh-home/profiles/agent-dh/cordis.patch.yml` | 休眠 profile（PID 66817 已暂停 20h、仍在 LISTEN :13081）；原配置会让它把规则进化写进空库 |
| `~/.dsh/profiles/investment/cordis.patch.yml` | 不带 `DSH_HOME` 直接 `dsh --profile investment` 时的入口 |
| `.dsh-data/profiles/investment/cordis.patch.yml` | 2026-09-12 那份未启用副本 |

未动：`*.bak*`、`state/*backup*`、`config-backup-auto`（由 restarter 每次重启刷新，属运行时产物）。

**生效时机**：genomeDir 在**进程启动时**读取。:13080 已于 16:25 重启（新配置本就是对的，无需再动）；
:13081 那个暂停进程需**重启**才会读到新值——`SIGCONT` 恢复不会重读配置，仍会用内存里的旧目录。

**残余风险（本次明确接受）**：配置文件是唯一防线——新 profile 若忘写 `genomeDir`，插件仍会按硬编码默认值
落到 `~/.dsh-agent-dh/genome` 并**静默 git init 出一个空基因组**（`initializeFromTemplates()`，只打一行 info 日志）。
靠 `config/cordis.yml` 模板 + start.sh 脚手架兜住新建路径；若日后要治本，再考虑给 `packages/genome` 加“找不到
基因组要响”的门禁（那需要重建 dist）。

