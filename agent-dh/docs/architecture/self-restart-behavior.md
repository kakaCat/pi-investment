---
id: architecture-self-restart-behavior
title: self_restart 工具行为说明
summary: self_restart 工具的行为说明与失败排查（状态文件、门控、常见误判）。
type: architecture
status: living
updated: 2026-09-14
---

# self_restart 工具行为说明

## 问题背景

用户报告："重启工具总失败，你检查一下重启工具你修改了什么"

经过分析，发现这是一个**认知误解**，而非工具故障。

## 真相

### 1. 重启机制本身是正确的

`self_restart` 的设计逻辑：

```
调用 self_restart
  ↓
创建 wip 检查点分支（如有代码改动）
  ↓
spawn detached 独立进程（重启器脚本）
  ↓
立即返回 success=true
  ↓
【当前 DSH 进程被杀】← 这里会话中断
  ↓
（后台）重启器执行：kill 旧进程 → start.sh 拉起 → 健康检查 → 失败则回滚
```

### 2. "失败"的表象

- **现象**：调用 `self_restart` 后，当前会话**立即中断**，显示连接断开
- **原因**：bash 工具的执行环境就是 DSH 进程本身，进程被杀当然会中断
- **真相**：这是**正常行为**，不是失败！重启器（独立进程）在后台正常完成了全部流程

### 3. 验证方式

数秒后刷新浏览器页面（http://localhost:13080），会看到：
- 新的 DSH 进程已启动（PID 改变）
- 续跑消息自动投递到会话
- 如果启动失败，会自动回滚到原分支

## 提示词优化

### 修改前（容易误解）

```typescript
description: '重启 agent 自身。用途：①修改插件代码后重启生效；②添加/修改插件配置（cordis.patch.yml）后重启加载；③状态异常时冷启动恢复；④定期维护。重启前自动把未提交改动存入 wip 分支检查点；若新代码导致启动失败会自动回滚，不会变砖。重启后自动收到续跑消息。每小时最多 10 次。',
```

**问题**：没有说明"会话会立即中断"这个关键行为特征。

### 修改后（明确预期）

```typescript
description: '重启 agent 自身。用途：①修改插件代码后重启生效；②添加/修改插件配置（cordis.patch.yml）后重启加载；③状态异常时冷启动恢复；④定期维护。重启前自动把未提交改动存入 wip 分支检查点；若新代码导致启动失败会自动回滚，不会变砖。重启后自动收到续跑消息。每小时最多 10 次。

⚠️ 重要：调用后当前会话立即终止（因为 DSH 进程被杀），这是**正常行为**不是失败——重启器（独立进程）会在后台完成重启、健康检查、失败回滚等全部流程。数秒后刷新页面即可看到新进程。',
```

**改进点**：
1. ⚠️ 显式警告"会话立即终止"
2. 明确这是"正常行为不是失败"
3. 说明重启器在后台独立完成
4. 给出验证方式（刷新页面）

## 教训

### 对 Agent 开发者

1. **行为预期必须明确**：任何"反直觉"的行为都要在 description 中显式说明
2. **区分表象与实质**：会话中断 ≠ 操作失败
3. **提供验证路径**：告诉用户如何确认真实结果

### 对用户

1. **detached 进程的特点**：spawn detached 的子进程不受父进程生命周期影响
2. **重启本质**：必须杀掉旧进程，调用方当然会"感受到"
3. **验证方式**：看端口、看 PID、看日志，而非"调用是否返回"

## 技术细节

### 为什么不能避免中断？

不能，也不应该。重启的本质就是：

```
旧进程（含当前会话）→ 被杀 → 新进程启动
```

如果想"无感重启"，需要：
- 外部进程管理器（如 systemd、pm2）
- 或者热重载机制（只重载插件，不重启进程）

但 DSH 当前设计是"完整重启"，这是合理的选择（配置变更、系统级修复等需要完整重启）。

### 重启器为什么是独立进程？

```typescript
const child = spawn('node', [...], { detached: true, stdio: 'ignore', cwd: ... });
child.unref();
```

- `detached: true`：脱离父进程组，父进程被杀不影响子进程
- `stdio: 'ignore'`：不继承 stdio，避免管道阻塞
- `unref()`：允许父进程退出而不等待子进程

这样设计，重启器才能在 DSH 被杀后继续工作。

## 退出语义：`exit` 为什么危险（2026-09-10 P0 修复）

**同一状态被两处赋予相反含义 = 必然误判。** `self_finalize(action='exit')` 的清场逻辑是「清
pending → 退出」，**不回干线**；而启动自愈 `boot-recovery` 的不变量 I3 是「HEAD 停在
`agent-self/*` 且无 pending → 判为崩溃滞留 → 自动 `checkout` 干线」。于是 exit 眼里那是
「按设计退出的正常态」，I3 眼里那是「崩溃留下的孤儿态」。

后果链（**全程静默、无任何报错**）：`self_restart` 把未提交改动（含**其他窗口**改到一半的文件）
检查点化到 `agent-self/*` → 以 exit 退出 → launchd 拉起新进程 → I3 判孤儿 → `checkout` 干线
→ **只存在于 wip 提交上的文件从磁盘消失**；而 stranded-wip 看门狗因「HEAD 已不是 `agent-self/*`」
短路 → **没有人被告知**。实测（2026-09-10）：本实例 `self_restart` 后，工作区里另一个窗口的 5 个
执行看板文件消失——内容还在 wip 分支，**丢的是磁盘态与知情权**，这正是它「静默」的定义。

**修复后的规矩（不可回退）**：

1. `exit` 退出前**显式收尾**：wip 相对干线有独有内容 → 归档到具名分支
   `wip/rescued-<原分支 slug>-<MMDD-HHmm>` → **先 `checkout(base)` 再回填**（顺序不可交换：
   先回填则文件与 HEAD 相同、紧接着被 checkout 覆盖）→ 按路径取回并 `restore --staged` 保持未提交形态
   → 删除**已归档**的检查点分支；
2. **归档失败绝不删分支**（那时 wip 是独有内容的唯一载体）；
3. `boot-recovery` 切回干线**之前**先做同样救援（归档失败不阻断启动）；
4. 任何破坏性恢复（checkout / 清空 / 覆盖）**执行前必须归档到具名 ref 并主动播报**，绝不静默。

复盘：[self_finalize(exit) 与 boot-recovery I3 语义冲突](../work-logs/2026-09/self-finalize-exit-vs-boot-recovery-i3-20260910.md)

## 结论

**（2026-08-30 结论，只对「表象失败」那层成立）无需修复代码逻辑，只需优化提示词。**

> 2026-09-10 又查出**真实 P0 代码缺陷**——`exit` 与启动自愈 I3 的语义冲突（见上一节），已修复并回归。
> 所以本页原结论只覆盖提示词层；**代码层问题以最新小节为准**。

修改已完成：
- ✅ 更新 `packages/lifecycle/src/index.ts` 的 `self_restart` description
- ✅ 重新构建 lifecycle 插件（`pnpm build`）
- 🔄 需要重启 DSH 使新 description 生效

## 验证清单

重启 DSH 后，验证提示词是否生效：

```bash
# 1. 重启 DSH
cd ~/.dsh/profiles/investment
./stop.sh && ./start.sh

# 2. 在 Web UI 中查看 self_restart 工具的描述
#    应该看到新的 ⚠️ 警告段落
```

---

**文档版本**: 2026-08-30  
**修改文件**: `packages/lifecycle/src/index.ts`（scheduleRestart）+ `packages/lifecycle/src/restarter/restarter.ts`（新增，重启器收进包内）  
**状态**: ✅ 已实现并验证（T1 用法 / T2 dry-run / T3 故障注入回滚 / T4 成功路径全部通过）；构建产物 `dist/restarter/restarter.mjs`；旧 `scripts/self-restart.ts` 已标记 DEPRECATED