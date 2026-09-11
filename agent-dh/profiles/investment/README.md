# DSH Investment Profile

这是 Agent-DH 的 DSH Profile 配置模板。插件以**指向 agent-dh 源码目录的 `file:` 依赖 + 符号链接**方式接入。

> **历史注记（2026-09-11）**：本文件此前描述的是一套 `local-packages/*.tgz` 打包流程
> （`pack-for-profile.sh` / `pnpm run repack` / `local-packages/`），但那套东西**从未落地**：
> `pack-for-profile.sh` 是 0 字节空文件，profile 里没有 `local-packages/` 目录，profile 的
> `package.json` 也没有 `scripts` 字段（`pnpm run repack` 直接报错），实际用的是 `file:` 相对路径。
> 已按实际架构重写。

## 架构说明

```
agent-dh/
  ├── packages/          # 插件源码（TypeScript，tsx 直载，无构建步骤）
  │   └── pages/         # dashboard-* 页面包
  └── profiles/investment/      # Profile 配置模板（本目录）

~/.dsh/profiles/investment/     # 实际安装位置
  ├── node_modules/@pi-investment/   # 每个包一个**符号链接** → agent-dh/packages/*
  ├── .deploy-backup/                # relink 时的旧副本备份（可回滚）
  ├── state/                         # 运行时状态（pid/日志）
  ├── package.json                   # 依赖声明（file: 相对路径）
  ├── cordis.patch.yml               # 插件加载配置
  ├── start.sh / stop.sh             # 启停脚本
  └── restart-with-build.sh          # 重启（含校验 + 重新链接）
```

## ⚠️ 依赖必须是符号链接，不能是 pnpm 的硬链接副本

`pnpm install` 对 `file:` 依赖做的是**硬链接**。硬链接共享 inode，看起来"实时同步"，
但只在**没人替换过该文件**时成立：任何一次 Write/Edit（写临时文件再 rename）都会换掉
inode、**断链**，profile 静默停在旧版本，**没有任何报错**。

而且它是**部分**过期 —— 没被编辑过的文件仍是硬链接、看起来正常，只有被编辑过的才落后，
所以极容易误判成"已部署"。

2026-09-11 的事故就是这样：profile 冻结在当天 02:23 的 `pnpm install`，此后全天提交的
RFC 015 工作（分钟线 / 交易状态 / 可交易性闸门 / 产业链图谱 / 政策事件源，25 个新文件 +
21 个改动文件）**全部没有生效**，而发版流程"看起来是成功的"。

**因此 `node_modules/@pi-investment/*` 必须全部是指向仓库的符号链接。**

## 安装 / 部署

```bash
# 1. 依赖（在 agent-dh 根目录）
cd agent-dh && pnpm install

# 2. 装进 profile。用 relink 脚本统一成符号链接 —— 别手写 ln，
#    也别指望 pnpm install 的产物是"活"的（见上一节）
python3 agent-dh/scripts/relink-profile.py

# 3. 重启（:13080 由 launchd 托管，kill 会被 KeepAlive 立刻拉回）
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

`agent-dh/scripts/restart-with-build.sh` 把这三步串起来了，正常发版走它即可。

### 日常改代码后的流程

因为依赖是符号链接，**改源码 → 重启即生效**，没有中间打包步骤：

```bash
vim agent-dh/packages/investment/src/tools/MyTool/MyTool.ts
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

唯一要注意的是：**只要跑过 `pnpm install`，就要重跑一次 `relink-profile.py`**
（pnpm 会把符号链接换回硬链接副本）。

### 体检

```bash
python3 agent-dh/scripts/relink-profile.py --check   # 有漂移则退出码 1
```

## 启停

```bash
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh   # 重启
./stop.sh                                                    # 停止（内部 bootout）
./start.sh                                                   # 启动 / 恢复托管
```

`kill` 停不掉本实例：launchd 作业 `com.pi-investment.dsh` 带 `KeepAlive`，进程被杀后会被
立刻拉起，脚本会"看起来成功"但服务仍在跑。停机必须 `bootout`（`stop.sh` 已封装）。

## 新增插件

1. 在 `agent-dh/packages/` 下建包
2. `~/.dsh/profiles/investment/package.json` 加一条 `file:` 依赖
3. `~/.dsh/profiles/investment/cordis.patch.yml` 加插件加载项
4. `cd agent-dh && pnpm install`
5. `python3 agent-dh/scripts/relink-profile.py`（把新包也变成符号链接）
6. 重启

映射由 `package.json` 的 `file:` 声明推导，新增包会被 relink 脚本自动纳入，无需改脚本。

## 常见问题

### Q: 改了代码但没生效？

```bash
python3 agent-dh/scripts/relink-profile.py --check   # 先看是不是又变成硬链接副本了
```

若显示 `copy`，运行 `relink-profile.py` 后重启。

### Q: 怎么确认线上跑的是哪份代码？

```bash
ls -la ~/.dsh/profiles/investment/node_modules/@pi-investment/
```

全是 `->` 符号链接才对。`--check` 的退出码 0 是权威判定。

### Q: 怎么回滚一次 relink？

`relink-profile.py` 会把旧副本备份到 `~/.dsh/profiles/investment/.deploy-backup/<时间戳>/`，
把里面的条目 `mv` 回 `node_modules/@pi-investment/` 即可。

## 参考

- [Agent-DH README](../../README.md)
- [Agent-DH CLAUDE.md](../../CLAUDE.md)
- [DSH 文档](https://github.com/deepseek-ai/dsh)
