# DSH Profile 插件部署静默失效修复

**日期**：2026-09-11
**影响**：`~/.dsh/profiles/investment` 的插件代码静默滞后，当天全部 RFC 015 工作未上线

## 现象

线上 agent（`:13080`）跑的代码与仓库 main 不一致，但**没有任何报错**：
启动正常、日志干净、"发版"流程看起来成功。实际 profile 冻结在当天 02:23 最后一次
`pnpm install` 的状态。

审计结果（profile vs 仓库工作区）：

| 类别 | 数量 | 含义 |
|---|---|---|
| profile-only | 1 | 副本里有、仓库没有 |
| differs | 21 | 两边都有但内容不同 = 未部署的编辑 |
| repo-only | 25 | 仓库有、副本没有 = 未部署的新文件 |

其中 repo-only 的 25 个文件里有 12 个是**全新工具**（`MinuteKlineTool` / `TradingStatusTool` /
`StockEventsTool` / `IndexConstituentsTool` / `ChainListTool` / `ChainScanTool` /
`SymbolChainTool` / `RecallAuditTool`），以及 `trading/src/utils/tradability.ts`
——即 RFC 015 的「可交易性闸门接入真实下单路径」这类交易安全逻辑也不在线。

## 根因

`pnpm` 对 `file:` 依赖做的是**硬链接**。

- 硬链接共享 inode，所以**安装当时**确实实时同步 —— 这正是"看起来能用"的来源。
- 但任何一次**替换式写入**（Write/Edit、绝大多数编辑器的临时文件 + rename）都会换掉 inode，
  **断链**，profile 那边从此停在旧版本。
- 失败是**静默的**：没有任何报错，因为断链后两边都是合法文件。
- 更隐蔽的是**部分过期**：没被编辑过的文件仍保持硬链接、看起来"是同步的"，只有被编辑过的
  才落后 —— 极易误判为"已经部署好了"。

决定性证据（设备+inode 比对）：

```
investment/package.json   profile ino=64346072  links=2  ← 硬链接仍在
                          repo    ino=64346072  links=2
investment/src/index.ts   profile ino=66827927  links=1  ← 已断链
                          repo    ino=71061447  links=1
```

**放大因素**：文档里的错误心智模型。`agent-dh/CLAUDE.md` 原文写着
"When you run `pnpm build` in agent-dh, the built JavaScript is immediately available to
the DSH profile (via file: links)" —— 这句话是错的（`pnpm build` 根本不碰 profile），
它直接导致了"改完代码就算部署完了"的误解。

**连带发现**：`agent-dh/profiles/investment/README.md` 整篇描述的是一套
`local-packages/*.tgz` 打包流程（`pack-for-profile.sh` / `pnpm run repack`），
但那套东西从未落地 —— `pack-for-profile.sh` 是 0 字节空文件（且 `docs/work-logs/2026-09/
temp-solutions-audit.md` 早已将其列为待删除），profile 里没有 `local-packages/` 目录，
profile 的 `package.json` 也没有 `scripts` 字段（`pnpm run repack` 直接报错）。

## 修复

### 机制：硬链接副本 → 符号链接

把 profile 的 `node_modules/@pi-investment/*` 全部改成指向仓库源码的符号链接。
符号链接解析到仓库路径，**不存在"忘记部署"这个失败模式**，也与 `tsx` 直载 TS 的设计一致。

- 26 个包：25 个转换为符号链接（21 个新转换 + 4 个原本就是），1 个（`dashboard-execution`）刻意排除。
- 旧副本先 `mv` 到 `~/.dsh/profiles/investment/.deploy-backup/20260911-224207/` 作为回滚点。
- 被取代的 profile-only `trading/src/tools/M4CircuitBreakerTool/drawdownTrust.ts` 随备份移走
  （已由 commit `db0ccc30` 收编进 `core-tool`，`M4CircuitBreakerTool` 改为
  `import from '@pi-investment/core-tool'`，丢弃无损）。

**刻意排除 `dashboard-execution`**：它有另一个会话未提交的改动（`board-mount.ts` /
`index.ts` / `dashboard-routes.ts`，新增 orphaned-task-cleanup 端点）。核实其副本与 `HEAD`
**逐字节一致**，所以保持副本 = 跑的是纯已提交代码。跨会话地把别人未提交的工作推上线，
不应由这次修复代劳。

### 新增产物

- `agent-dh/scripts/relink-profile.py`：映射由 profile `package.json` 的 `file:` 声明推导
  （不硬编码包列表，新增包自动纳入）。支持 `--check`（有漂移退出码 1，可进 CI）/ `--dry-run` /
  `--exclude` / 自动备份。
- `agent-dh/scripts/restart-with-build.sh`：接入 relink 步骤；新增**未提交改动告警**
  （符号链接模型下，工作区脏文件重启即上线）；修正日志路径
  （原写 `~/.dsh-agent-dh/logs/dsh.log`，实际是 `state/launchd.out.log`）。
- 文档纠正：`agent-dh/CLAUDE.md` 的 `pnpm build` 错误说法、
  `agent-dh/profiles/investment/README.md` 整篇重写、
  删除 0 字节的 `agent-dh/scripts/pack-for-profile.sh`。

## 验证

重启后（`launchctl kickstart -k gui/501/com.pi-investment.dsh`）：

- 新 pid 79772，`runs = 3`（较重启前 +1，**无重启循环**）；90 秒内 pid / 横幅数 / 日志 mtime 均无变化。
- 启动日志无模块解析错误，`[genome] loaded: g27, 4 sections + 6 tools registered`，web 服务在听。
- **正向验证**：此前缺失的 12 个新工具目录现在都能从 agent 实际加载的路径
  （`node_modules/@pi-investment/*/src/tools/`）访问到。

> 注意 `node_modules/@pi-investment/*` 现在**必须**是符号链接。再跑 `pnpm install` 会把它换回
> 硬链接副本，必须重跑 `relink-profile.py`（`restart-with-build.sh` 已内置 `--check` 自动修复）。

## 遗留

- `dashboard-execution` 仍是副本，待那个会话提交后执行 `relink-profile.py` 纳入
  （`--check` 会持续报它漂移，属预期）。
- 更彻底的做法是让 profile 指向一个**专用生产检出**（pinned 到 main）而非开发工作区，
  这样多人并行时的未提交改动不可能泄漏到线上（5001 已是这个模式）。本次先按"符号链接到
  仓库工作区"落地，用 `restart-with-build.sh` 的脏工作区告警兜住风险。
