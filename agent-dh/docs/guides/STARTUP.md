---
id: guides-startup
title: Agent-DH 启动指南
summary: 运行目录与 profile 现状（DSH_HOME=.dsh-data）、启停与 launchd，含 GUI 401 根因与迁移/布局合并的坑。
type: guide
status: living
updated: 2026-10-04
---

# Agent-DH 启动指南

> ⚠️ **本文的「架构变更 / 项目结构 / 迁移说明」是 2026-08 的形态，已过时**（当时设想 agent-dh 是独立应用）。
> 现役形态见下面的「现状速查」；日常操作以 [快速参考卡片](QUICKREF.md) 与 [构建与发版规范](../standards/build-and-release.md) 为准。

## 现状速查（2026-09-13 起）

| 项 | 现状 |
|---|---|
| DSH_HOME | `agent-dh/.dsh-data` —— **home 就是数据目录本身**（`.dsh-home` 已于 2026-09-14 撤除，不再是两层） |
| profile 目录 | `.dsh-data/profiles/agent-dh`（实跑就是 `agent-dh`；`DSH_PROFILE` 可覆盖，缺省 `agent-dh`）。旧文档里的 `investment` 是历史，**别再照抄** |
| 运行数据 | 同 DSH_HOME：`sessions/` `storages/` `genome/` `skills/` `attachments/` `dsh-reqboard.json` `agents.json` |

> **为什么不再分两层**：`.dsh-home` 是「DSH_HOME 曾在本仓库外」时代的遗留——靠 `start.sh` 把数据**符号链接**挂进去。
> 但写盘方（reqboard store / credentials / pet.json）都用「临时文件 + rename」的原子写，而 **`rename` 会把符号链接替换成真文件**：
> 实测 `dsh-reqboard.json` 真文件（250KB）落在 `.dsh-home`，而 `.dsh-data` 那份冻结在 09-12（96KB）——**备份会漏掉真实台账**，
> 且 `_link_file` 遇真文件只告警不覆盖 = **永久静默分裂**（同一份状态两个候选位置）。布局合并复盘：[.dsh-home 并入 .dsh-data](../work-logs/2026-09/dsh-home-data-merge.md)。
| :13080 托管 | launchd 作业 `com.pi-investment.dsh`：重启 `launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`、停止 `launchctl bootout`——**不要 kill，也不要手工 `./start.sh`**（KeepAlive 会拉起，紧接着必然 EADDRINUSE） |

**GUI 反复打不开（401）的根因：凭证密钥漂移。** `dsh web` 每进程随机生成 launchToken，换取一次
「authority 绑定 + 密钥签名」的 cookie（默认 30 天），密钥存在 `$DSH_HOME/.credentials.yaml` 的
`client-connection/browser-session`。**换 home / 换密钥 = 浏览器里所有 cookie 立即作废**——
表现为"启动好久还是不能用"，其实不是启动慢，是钥匙过期（本机曾同时存在三份凭证库、两个密钥）。

**迁移（换 home / 换 profile 目录）的正确姿势**（可回滚，且全程不换钥匙）：

1. 备份 plist、两份凭证、settings、现役 `cordis.patch.yml`；
2. `rsync -a --exclude node_modules <旧 home>/ <新 home>/`（**不要 `--delete`**）；
3. **验证等价**：genome 文件数、skills 数、reqboard 体积、sessions 取并集——对不上就别切；
4. **密钥延续**：让新 home 的 `.credentials.yaml` 与现役**同一份**（authority 与 secret 都不变 → 浏览器 cookie 继续有效，无需重换 token）；
5. profile 的 `cordis.patch.yml` 用**现役那份**，只改写 `genomeDir` / `profileDir` 两处绝对路径，保证行为零变化；
6. 切换后按 [定时巡检清单](routine-checks.md) 验服务与工具绑定。

完整取证与回滚路径：[DSH_HOME 迁入项目内（事故复盘）](../work-logs/2026-09/dsh-home-migration-20260913.md)。

## 从 DSH 实例内启动的坑（2026-10-04 实测）

**症状**：在 DSH 应用内起的 shell（或 agent 会话）里跑 `./scripts/start.sh`，会**继承**那个实例的
`DSH_HOME`（如 `~/.dsh`）与 `DSH_PROFILE`（如 `desktop`）。本脚本原样采信 → 按"外部模式"处理、
不生成 profile 脚手架 → dsh 拒启：`profile "desktop" is managed exclusively by the Electron application`。
同一份继承值还会让 `relink-profile.py` 去体检**别人的 home**（报一句"OK"而真正目标没查），
让 `restart-with-build.sh` 把 manifest 写进一个不存在的 profile 并让 L1 报假失败。

**现口径（三个脚本同一规则）**：环境值只在**本仓数据目录里真有该 profile** 时才算数，否则回落
`agent-dh` 并**大声打印忽略了什么**。要显式用仓库外的 home 才需 opt-in：

```bash
./scripts/start.sh                                   # 正常：自动忽略继承值
DSH_ALLOW_EXTERNAL_HOME=1 ./scripts/start.sh         # 逃生舱：确实要外置 home 时
DSH_INVESTMENT_PROFILE=/abs/path ./scripts/relink-profile.py --check   # 显式指定 profile 目录
```

> 判据不是"有没有设"，而是"那个 home 里有没有本 profile"。**空集不是通过**。

## 架构变更

**之前**：启动配置在 `~/.dsh/profiles/investment/`（外部 DSH profile）  
**现在**：启动配置在 `agent-dh/` 项目内，agent-dh 是独立应用

## 快速启动

```bash
# 1. 安装依赖
pnpm install

# 2. 启动（默认端口 13080）
pnpm start

# 3. 或指定端口
pnpm start -- 13081

# 4. 开发模式（详细日志）
pnpm start:dev
```

## 项目结构

```
agent-dh/
├── config/
│   └── cordis.yml          # 插件配置（从 ~/.dsh 迁移）
├── scripts/
│   └── start.sh            # 启动脚本
├── packages/               # 业务插件
│   ├── investment/
│   ├── trading/
│   └── ...
├── src/
│   └── main.ts            # 启动入口（保留，未来可用）
└── package.json           # 包含启动命令
```

## 配置管理

### 插件配置

编辑 `config/cordis.yml` 来管理插件：

```yaml
- id: investment
  name: '@pi-investment/investment'
  config:
    quantsysV2:
      baseURL: http://localhost:5001
```

### 环境变量

在项目根目录创建 `.env` 文件：

```bash
DEEPSEEK_API_KEY=sk-...
QUANTSYS_V2_API_URL=http://localhost:5001
```

## 与旧方式的对比

### 旧方式（DSH Profile）

```bash
cd ~/.dsh/profiles/investment
./start.sh
```

- ✗ 配置在用户目录，不在版本控制中
- ✗ 源码和配置分离
- ✗ 部署时需要手动同步配置

### 新方式（项目内启动）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
pnpm start
```

- ✓ 配置在项目内，纳入版本控制
- ✓ 源码和配置统一管理
- ✓ 部署简单（git clone + pnpm install + pnpm start）

## 迁移说明

如果你之前使用 DSH profile 方式启动，现在可以：

1. **停止旧实例**：
   ```bash
   launchctl bootout gui/$(id -u)/com.pi-investment.dsh
   ```

2. **使用新方式启动**：
   ```bash
   cd /Users/yunpeng/pi-investment/agent-dh
   pnpm start
   ```

3. **（可选）删除旧配置**：
   ```bash
   # 备份后可删除
   rm -rf ~/.dsh/profiles/investment
   rm ~/Library/LaunchAgents/com.pi-investment.dsh.plist
   ```

## launchd 托管 + 外部探针（2026-10-04 现役）

本实例由 launchd 守护：`RunAtLoad` + `KeepAlive`（崩了自动拉起），配套一个**独立**的存活探针
（与 API 进程无关，进程死了它照样跑）。plist 模板入库在 `deployment/launchd/`：

| 文件 | 作用 |
|---|---|
| `deployment/launchd/com.pi-investment.dsh.plist` | 服务守护（:13080） |
| `deployment/launchd/com.pi-investment.agent-dh-probe.plist` | 探针，5 分钟一轮 |
| `scripts/launchd_launcher.py` | launchd 入口代理（见下"TCC"一节） |
| `scripts/health_probe.py` | 判据：端口 + pidfile + HTTP(<500)；日志年龄只报不判；经 `FEISHU_WEBHOOK_URL` 告警，**状态翻转才发一次** |

```bash
# 安装（模板改动后需重新 cp + bootstrap）
cp deployment/launchd/*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pi-investment.dsh.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pi-investment.agent-dh-probe.plist

# 重启（**唯一正确入口**；手工 ./scripts/start.sh 会被 KeepAlive 抢端口）
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh

# 停机（内部走 bootout）
./scripts/stop.sh

# 状态与日志
launchctl list | grep com.pi-investment
tail -f .dsh-data/state/launchd.out.log .dsh-data/state/agent-dh-probe.log
```

⚠️ **不要用 `launchctl submit`**：RFC-016 记录过一次 submit 死循环，把所有实例杀掉 10.7 小时。

### 为什么入口是 Python 而不是 bash（TCC，2026-10-04 实测）

macOS 把 `~/Documents` 的读取**按二进制**授权。launchd 直接拉 `/bin/bash` 跑本仓脚本会被拒：

```
shell-init: error retrieving current directory: getcwd: Operation not permitted
/bin/bash: .../scripts/start.sh: Operation not permitted      # launchctl 里退出码 126
```

对照实验（同一受保护文件，逐个二进制）：

| 入口二进制 | launchd 下能读 `~/Documents`？ |
|---|---|
| `/bin/bash` | ❌ Operation not permitted |
| `/usr/bin/python3`（系统） | ❌ Operation not permitted |
| `/opt/homebrew/bin/python3`（shim） | ❌ 启动即退出码 78 |
| **homebrew `Python.framework` 真身** | ✅ 可读，**且子进程继承**（`→ /bin/bash` 实测通过） |

所以本作业的入口是已获授权的 framework Python，由 `scripts/launchd_launcher.py`
再以**子进程**方式拉起 `scripts/start.sh`（授权被子进程继承）。
**脆弱点**：plist 里写着 `/opt/homebrew/opt/python@3.13/...` 这条 opt 符号链接——
哪天 python@3.13 被卸载/换次版本，服务与探针会**同时**起不来，改那一行即可。

## 故障排查

### 问题：找不到 @deepseek-ai/dsh

**解决**：
```bash
pnpm install
```

### 问题：端口已被占用

**解决**：
```bash
# 查看占用端口的进程
lsof -ti:13080

# 杀死进程
kill $(lsof -ti:13080)

# 或使用其他端口
pnpm start -- 13081
```

### 问题：插件加载失败

**解决**：
```bash
# 检查插件是否已构建
pnpm build:clients

# 查看详细日志
pnpm start:dev
```

## 开发指南

### 添加新插件

1. 在 `packages/` 下创建新插件
2. 在 `config/cordis.yml` 中注册
3. 重启 agent-dh

### 修改配置

1. 编辑 `config/cordis.yml`
2. 重启 agent-dh（配置不支持热加载）

### 调试

```bash
# 详细日志模式
pnpm start:dev

# 或直接运行
node --import tsx/esm src/main.ts --verbose
```