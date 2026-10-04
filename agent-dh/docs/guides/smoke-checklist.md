---
id: guides-smoke-checklist
title: agent-dh 冒烟清单（一条命令一项）
summary: 实例活着吗 / 代码生效了吗 / 身份与基因组对不对 / 模型通不通 / 能不能真去 v2 取数——按这个顺序，每项一条命令、都有期望输出。
type: guide
status: living
updated: 2026-10-04
owners: [agent-dh]
tags: [guide, smoke, ops, launchd, genome]
---

# agent-dh 冒烟清单

**这页回答**：改完东西（或怀疑它坏了）之后，按什么顺序、用什么命令、看到什么算正常。

> 来源：2026-10-04 本机运行态恢复（[work-log](../work-logs/2026-10/agent-dh-machine-restore.md)）。
> 全部命令在本机实跑过；`cd` 到 `agent-dh/` 后执行。

## 0. 最小闭环（4 条命令，30 秒）

```bash
cd /Users/mac/Documents/ai/pi-investment/agent-dh

lsof -nP -iTCP:13080 -sTCP:LISTEN            # ① 端口：应有一行 node … LISTEN
launchctl list | grep com.pi-investment      # ② 守护：dsh + probe 两行（第 2 列 = 上次退出码，0/- 才对）
python3 scripts/health_probe.py; echo "exit=$?"   # ③ 探针：三行 OK + exit=0
curl -s -m 5 127.0.0.1:5001/health           # ④ 后端：{"status":"ok",...}
```

## 1. 逐项检查（含期望输出）

| # | 检查什么 | 命令 | 正常的样子 |
|---|---|---|---|
| 1 | 依赖是**符号链接**（不是硬链接副本） | `python3 scripts/relink-profile.py --check` | `symlink-ok=N`、0 漂移、exit 0 |
| 2 | 代码是否**真的生效**（不是改完没重启） | `./scripts/restart-with-build.sh --verify-only` | L1 依赖 / L2 `20/20` / L3 **内容指纹一致** / L4 manifest → ✅ |
| 3 | 身份注册表 | `cat .dsh-data/profiles/agent-dh/agents.json | head -12` | `instance.account = agent_brain`；agents[] 里 `investor` 是 primary |
| 4 | 基因组版本 | `grep genome_version .dsh-data/genome/genome.json`；`tail -40 .dsh-data/state/launchd.out.log | grep genome` | `"genome_version": "g3"`；日志 `[genome] loaded: g3, 4 sections + 6 tools` |
| 5 | 谁是谁（提示词里的自我认知） | 在 UI 里问「你是谁」 | 应出现「PI 投资顾问·投资脑」「本实例投资账户：agent_brain」——不再是"未注册角色 / 所属实例 unknown" |
| 6 | 模型通路（LLM 真能答） | 见下方「一次性 headless 任务」 | 有正常回答、exit 0；AUTH 401 = key 失效（换 `.dsh-data/.env` 里的 key，或用 Kimi 备用通路） |
| 7 | 工具 → v2 真取数 | 同上 headless，但改成"用投资工具查 600519 最近 5 根日K" | 它调用 `data_fetch_kline`；返回条数应与 v2 库内该区间行数**对得上** |
| 8 | 页面插件路由 | 带 token 访问 `/dashboard/api/board` | `health` 段里 `quantsys-v2 status=ok / db=healthy` |

> token 取法（**每次重启都换**）：
> `grep -o 'token=[A-Za-z0-9_-]*' .dsh-data/state/launchd.out.log | tail -1`
> 然后用 `curl -s -c /tmp/j -L "http://127.0.0.1:13080/?<token>"` 换 cookie，再 `curl -b /tmp/j .../dashboard/api/board`。

## 2. 一次性 headless 任务（不进 UI 就能验 LLM + 工具）

```bash
cd /Users/mac/Documents/ai/pi-investment/agent-dh
env -u DSH_PROFILE DSH_HOME=$PWD/.dsh-data node --import tsx/esm \
  node_modules/@deepseek-ai/dsh/lib/bin.js --profile dh-headless \
  "用投资工具查 600519.SH 最近 5 根日K，只回报工具名与条数"
```

- 这个 `dh-headless` profile 是**一次性测试用**（`.dsh-data/profiles/dh-headless/`，不入库）：只挂 `dsh-base + dsh-headless + bundle-stock`。
- 想验备用模型：把它的 `cordis.patch.yml` 里 `agent-loop` 的 `provider/model` 改成 `kimi-coding / kimi-for-coding` 再跑（2026-10-04 实测通过）。
- 注意它会打印 `trading: pending (waiting for service: genome)` —— 那个 profile 没挂 evolution bundle，属预期。

## 3. 已知降级（看到别慌）

| 现象 | 原因 | 现状 |
|---|---|---|
| 日志刷 `[AgentOSClient] Retrying … ECONNREFUSED 127.0.0.1:8080` | agent-os 未起 | 23 个工具（`memory_search`/`experience_*`/`learning_*`/`evolution_*`/`board_*`/`notification_*`/`agent_os_*`/`scheduler_manage`）无后端；**规则 R-008（决策前检索历史教训）因此落空** |
| `launchd.err.log` 里有 `/bin/bash: … Operation not permitted` | 2026-10-04 首装 launchd 时的 TCC 失败**历史行** | 历史留痕，不是现行故障（见 [STARTUP](STARTUP.md#为什么入口是-python-而不是-bashtcc2026-10-04-实测)） |
| 探针偶发一条 FAIL 告警 | 安装/重启窗口内端口未起 | 探针只在**状态翻转**时发一次，恢复后自动回到 OK |

## 4. 出问题时先看哪里

1. `.dsh-data/state/launchd.err.log` / `launchd.out.log`（服务自身）
2. `.dsh-data/state/agent-dh-probe.log`（外部判据 + 告警投递回执）
3. `launchctl print gui/$(id -u)/com.pi-investment.dsh | head -30`（守护视角：环境变量、上次退出码、重试次数）
4. 重启：`launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`（**别手工 `./scripts/start.sh`**，会被 KeepAlive 抢端口）
