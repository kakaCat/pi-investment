# 技能装载机制（Skill Loading）——排障实录与标准流程

> 2026-09-05 排障定案（w-8366e526）。曾连续 4+ 次重启技能不可见，根因是**改错 home + 误解 skill registry 分层架构**。本文记录真相与正确装载姿势，避免后人重蹈覆辙。

## 一、两个 DSH home（最容易踩的坑）

本机有两个 dsh home，**13080 实例只读后者**：

| 目录 | 归属 | 说明 |
|---|---|---|
| `~/.dsh/` | 主实例（:3080） | agent-dh 文档/CILA 旧指这里，已过时 |
| `~/.dsh-agent-dh/` | **本 investment profile（:13080）** | `start.sh` 显式隔离：`export DSH_HOME=~/.dsh-agent-dh`（注释："与主实例 ~/.dsh 隔离"） |

**判据**：`ps eww <PID>` 看 `DSH_HOME`；`lsof -p <PID> | grep cordis` 看实际读取的配置文件。
**运行真身**：`~/.dsh-agent-dh/profiles/investment/cordis.patch.yml` + `~/.dsh-agent-dh/settings.yaml`。

## 二、skill registry 分层架构（rc.1+）

dsh-web-app 的 cordis.patch.yml 明确：

- skill **registry** 在 host plane，按 scope 分层（tools-registry shape）。
- **host 层的 skill-filesystem / tool-skill 被 dsh-web-app 禁用**（`- id: skill-filesystem / disabled: true`）——preset 层负责各 preset 的 agent。
- 每个 preset（内置 standard/cordis/ptc、第三方 liangshen）在自己的 `agent.cordis.yml` composition 里声明 `skill-filesystem`（无 realm，注册进该 preset 的 layer）+ `tool-skill`（给 agent catalog 与 loader）。
- agent 读其 scope chain 选中的 merged catalog。

**推论**：在本 profile 的 `cordis.patch.yml` 顶层覆盖 skill-filesystem 注册的是 **host 层（被禁用）→ 无效**。正确注入点是 agent 实际挂载的 **preset composition**。

## 三、investor 实际用的 skill-filesystem

- investor（agent-loop agents）有全量工具 → **不挂 liangshen**（梁神 phase-1/PTC 只露极少工具）。
- 其实挂的是内置 preset（standard 系），其 skill-filesystem **无 config → 默认 roots**：
  - user-dsh：`<DSH_HOME>/skills` = `~/.dsh-agent-dh/skills`（默认必扫）
  - user-agents：`~/.agents/skills`；project roots（按会话 cwd 找）
  - bundled（未设 env `DSH_BUNDLED_SKILL_DIR` → 无）
- 默认 roots 里技能目录不存在/为空 → catalog 空 = **正常现象，不是故障**。provider 一直健康（有 watcher 惰性推送，放技能后 catalog 实时更新、无需重启）。

## 四、标准装载流程（加新技能/排障）

技能**真身**统一放 `agent-dh/skills/<skill>/`（git 版本管理、review），运行时经 user-dsh root 软链暴露：

```bash
# 1. 真身（git）
mkdir -p agent-dh/skills/<skill> && ... # 写 SKILL.md，frontmatter 必须有 name

# 2. 软链到运行时入口（user-dsh root）
ln -sfn /Users/yunpeng/pi-investment/agent-dh/skills/<skill> ~/.dsh-agent-dh/skills/<skill>

# 3. 验证（无需重启，watcher 实时推送）
#    skill 工具应能列出并加载该技能
```

已装载：`engine-heal-evolve`、`opportunity-funnel`（软链均指向 agent-dh/skills 真身）。

**排障速查**：
1. 技能在 catalog 里查不到 → 先确认软链存在：`ls -la ~/.dsh-agent-dh/skills/`
2. 确认进程 DSH_HOME：`ps eww $(lsof -ti:13080 -sTCP:LISTEN) | grep -o 'DSH_HOME=[^ ]*'`
3. 别改错 home（见第一节）；别在 profile patch 顶层注册 skill-filesystem（host 层被禁，见第二节）。
4. 想加自定义根：改 investor 实际挂载的 preset 源（内置 preset 在 `dsh-agent-presets/presets/*/agent.cordis.yml`）——但**软链 user-dsh root 已够用且最不易碎**，默认优先。

## 五、曾走的弯路（供复盘）

- 在 `~/.dsh/profiles/investment/cordis.patch.yml`（主实例配置）改 4 次 + 重启 4 次——全打在错误 home，永远不生效。
- 探针技能放 `~/.dsh/skills/`（主实例 user-dsh root）——错 home。
- 改真身 profile patch 顶层覆盖 skill-filesystem + customSkillDirs（host 层，被 web-app 禁用）——无效。
- 改第三方 liangshen preset 源注入 customSkillDirs——investor 不挂 liangshen，无效且污染第三方包（已回滚）。
- **正解**：无需任何 config 注入，利用默认 user-dsh root（`~/.dsh-agent-dh/skills`）+ 软链 git 真身，开箱即用。
