# REQ-b63a7d 存量台账路径清理报告（t5）

> 生成时间：2026-09-18；台账：`.dsh-data/dsh-reqboard.json`（workspaceRoot=/Users/yunpeng/pi-investment/agent-dh）
> 工具：`packages/pages/dsh-pmboard/scripts/normalize-ledger-paths.ts`（复用 domain 归一层，无第二套实现）

## 一、dry-run 实测（未写盘）

```
工作区根：/Users/yunpeng/pi-investment/agent-dh
扫描路径：692
需变更：114（normalized=91, dropped=4, deduped=19）
```

| 动作 | 条数 | 说明 |
|---|---|---|
| normalized | 91 | 剥掉仓库根相对前缀（`agent-dh/`）与工作区内绝对前缀（`/Users/.../agent-dh/`） |
| dropped | 4 | brace-glob 汇总写法（如 `quantsys-v2/tests/{a.py,b.py}`）——不是文件，剔除 |
| deduped | 19 | 归一后与既有登记重复（典型：`agent-dh/docs/x` 与 `docs/x` 同一条） |

`--verify` 实测：**OK —— 台账内不存在会被判 403 的路径写法**（0 条）。

## 二、为什么本次**没有 apply**（诚实标注，不静默跳过）

`JsonLedgerRepository` 把整份台账缓存在内存（`private ledger`），运行中改盘会在下一次
mutate 时被内存副本**静默覆盖**。本窗口在 t1–t6 关闭过程中刚对台账做过多次 mutate
（任务状态推进），此刻 apply 必被覆盖。脚本内置护栏：文件 120s 内被写过即拒绝 `--apply`。

**正确的 apply 窗口 = 实例停服期间**（与 t7 重启同窗口）：

```bash
# 1) 先停实例（该实例由 launchd 托管，kill 会被 KeepAlive 拉起）
launchctl bootout gui/$(id -u)/com.pi-investment.dsh
# 2) 清理（自动备份到 <ledger>.bak-normalize-<ts>）
cd /Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard
npx tsx scripts/normalize-ledger-paths.ts --file ../../../.dsh-data/dsh-reqboard.json --apply
npx tsx scripts/normalize-ledger-paths.ts --file ../../../.dsh-data/dsh-reqboard.json --verify
# 3) 拉起
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pi-investment.dsh.plist
```

## 三、影响评估：不 apply 也不影响本次修复

t2（写入侧归一）已堵住新脏数据来源；t3/t4 让读取侧对存量写法**照常可读**（归一层兜底 +
host 单点判定 openable）。因此存量清理是**数据卫生**，不是功能前置——故本任务降级为
"脚本就绪 + dry-run/verify 通过"，apply 待停服窗口执行。
