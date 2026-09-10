# self_finalize(exit) 与 boot-recovery I3 语义冲突：exit 会静默清空工作区（修复报告）

- 日期：2026-09-10 21:46 CST
- 角色/窗口：investor / w-50fc8c52（实例 :13080）
- 触发：用户询问"self_finalize 这个功能有什么作用"→ 核查时发现真实 bug，用户指令"全部修复"
- 提交：`57b0f00b`（fix(lifecycle)），8 files changed, +383/-13
- 影响面：`@pi-investment/lifecycle`（self_finalize / 启动自愈），全程未影响交易类功能

## 1. 缺陷（P0）

`self_finalize(action='exit')` 的清场逻辑是"清 pending/pendingDone/attempt → `process.exit(0)`"，**不回干线**。
而启动自愈 `boot-recovery` 的不变量 I3 恰好是：

> HEAD 停在 `agent-self/*` 且无 pending/pendingDone → 判定为"崩溃滞留"→ 自动 `git checkout <干线>`。

两者对**同一状态**（`HEAD=agent-self/*` 且无 pending）给出**互相矛盾的定义**：
exit 认为"这是我按设计退出的正常态"，I3 认为"这是崩溃留下的孤儿态"。
merge/rollback 之所以没事，是因为它们自己就会先 checkout 回干线。

后果链（静默、无任何报错）：

1. `self_restart` 重启前把工作区未提交的 `agent-dh/` 改动（含**其他窗口**的改到一半的文件）检查点化到 `agent-self/*`；
2. 退出走 `exit` → 清 pending → 进程退出；
3. launchd 拉起新进程 → boot-recovery 判定孤儿 → `checkout <干线>`；
4. 只存在于 wip 提交上的文件（被检查点收走的未提交改动）**从磁盘消失**；
5. stranded-wip 看门狗短路（HEAD 已不是 `agent-self/*`，且无 pending）→ **没有人被告知**。

现场证据：临时钩子下实测本实例 `self_restart` → 新进程 PID 48694（`Thu Sep 10 21:33:06 2026`），
`state/boot-recovery-audit.jsonl` 落了一条 `checkoutBase` 记录；工作区里 w-8f2c4cc5 的 5 个执行看板文件
（`packages/pages/execution/*`）消失。内容本身没丢（还在 wip 分支里），**丢的是磁盘态与知情权**——
这正是它"静默"的定义。此前我已按同一手法手工恢复过一次这批文件，本次把它脚本化。

## 2. 修复

### P0：exit 退出前显式收尾（新增 `src/exit-finalize.ts`）

`exitFinalize(repo, {checkpoint, base})` 的顺序**不可交换**：

1. 检查点分支相对干线有独有内容（`git cherry` patch-id 语义）→ 归档到具名分支
   `wip/rescued-<原分支 slug>-<MMDD-HHmm>`（同名冲突自动 `-2/-3`）；
2. **先 `checkout(base)`**——再回填；若先回填，文件与 HEAD 相同（等于没改），紧接着的 checkout 会用干线版本覆盖它；
3. 从归档分支把独有文件按路径取回，并 `git restore --staged` → 保持**未提交改动**形态（`git status` 可见、可撤销）；
4. 已归档的检查点分支删除（`git branch -D`）；归档失败则**绝不删**（那时 wip 是独有内容的唯一载体）；
5. 清理 pending 后退出。摘要写入工具返回 `note` + `osWrite('lifecycle:finalize')` 审计。

### P1：启动自愈 I3-救援 + 主动播报（`boot-recovery.ts` + `index.ts`）

I3 切回干线**之前**，先判断该 wip 是否有独有内容，有则推入 `rescueWip` 动作建归档分支（归档失败不阻断启动）。
新增 `announceWipRescue`：把"归档分支名 + 取回命令 + 勿盲目 merge"注入在线根 agent
（投递模式复用 stranded 看门狗：roots 匹配 → 未就绪则等 `agent/created`，30 分钟窗口）。

**P0 与 P1 的刻意不对称**：P0 走"归档 + 取回工作区"（设计性退出时进程还活着、状态完全已知，可以更进取）；
P1 走"归档 + 只播报"（崩溃路径状态未知——不能替用户猜想哪些改动该回到工作区）。
两者共同底线：**任何可能让文件从磁盘消失的路径都必须先建立具名归属**。

### P2：修文档（`tools/SelfFinalizeTool/prompt.ts` + `index.ts` 注释）

原文案"exit=仅保存状态并退出"就是本次误导的来源之一。改为如实描述新语义，
并显式警告"会真的退出进程（由 launchd 拉起）"、与 `merge` 的区别；`note` 进入输出 schema 与渲染。

## 3. 测试与验证

- 新增 `tests/exit-finalize.test.ts`（真实 git，无 mock）：归档 = 同一提交（`rev-parse` 相等）、
  HEAD 回干线、其它窗口的改动**仍在磁盘**且为 ` M`/`??` 未提交形态、检查点分支已收；
  无检查点 / 不在检查点分支 / 无独有内容（不建归档分支但照样收分支）等分支全覆盖。
- `tests/boot-recovery.test.ts` 增：I3-救援动作先于 `checkoutBase` 且归档内容零丢失、无独有内容不建分支、
  `rescueBranchName` 确定性与单级 ref（分支名里的 `/` 被 slug 化，避免造 `refs/heads/wip/rescued/...`）。
- 结果：lifecycle `64/64` 通过；插件 schema 冒烟 `19/19`；`tsdown --dts` 构建通过（含类型检查）。
- 修复过程中被测试抓住的真问题：初版把"删检查点分支"与"归档成功"强绑定，导致无独有内容的滞留空分支
  永远收不掉；改为"已成功回干线 + （无独有内容 或 归档成功）"。

## 4. 遗留

- 活体验证（真跑 `exit`）与 boot I3 无动作确认。
- `self_finalize(exit)` 现在会**真的结束进程**——工具文案已警告，但语义上它仍是"关闭"而非"提交"，
  想保留改动回干线请用 `merge`。
- 其他窗口（w-8f2c4cc5）在 `packages/pages/execution/*` 的 5 个文件仍未被合并：属于他人的在途工作，
  等待 owner 收回或用户裁决（已有具名归档分支 + 现工作区副本双份保留）。
